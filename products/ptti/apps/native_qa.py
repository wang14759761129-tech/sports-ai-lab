"""Fail-closed, isolated persistent configuration for the GEX-03 Native QA build."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import tempfile
import uuid
from datetime import datetime, timezone


NATIVE_QA_PORT = 48761
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "ptti.native-qa-identity/0.2"


class NativeQAError(RuntimeError):
    pass


def _absolute_path(path: str | os.PathLike[str]) -> Path:
    """Normalize lexically without Windows Store LocalAppData redirection."""
    expanded = os.path.expanduser(os.fspath(path))
    return Path(os.path.normpath(os.path.abspath(expanded)))


def _path_key(path: str | os.PathLike[str]) -> str:
    """OS-aware comparison key for already-normalized identity paths."""
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


@dataclass(frozen=True)
class NativeQAConfig:
    root: Path
    database: Path
    qa_data: Path
    webview2_user_data: Path
    research_data: Path
    identity_file: Path
    database_ready_file: Path
    build_commit: str
    instance_id: str
    port: int

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def webview_options(self) -> dict[str, object]:
        return {"private_mode": False, "storage_path": str(self.webview2_user_data)}


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _assert_no_reparse(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if _is_reparse_point(current):
            raise NativeQAError(f"Native QA isolation path contains a reparse point: {current}")


def _assert_writable_directory(path: Path) -> None:
    probe = path / f".ptti-native-qa-write-check-{uuid.uuid4().hex}"
    try:
        with probe.open("x", encoding="ascii") as stream:
            stream.write("ok")
    except OSError as exc:
        raise NativeQAError(f"Native QA storage directory is not writable: {path}") from exc
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise NativeQAError(f"Native QA could not remove its own write-check file: {probe}") from exc


def _check_qa_database(path: Path) -> None:
    """Read-only integrity check for an existing, already-claimed QA database."""
    if not path.exists():
        return
    if not path.is_file() or _is_reparse_point(path):
        raise NativeQAError("Native QA database path is not a regular file; preserving it")
    from urllib.parse import quote

    stable_path = _absolute_path(path)
    uri = "file:" + quote(stable_path.as_posix(), safe="/:\\") + "?mode=ro"
    connection = None
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2)
        result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise NativeQAError("Native QA database is corrupt or unreadable; preserving its contents") from exc
    finally:
        if connection is not None:
            connection.close()
    if result != ("ok",):
        raise NativeQAError("Native QA database failed its integrity check; preserving its contents")


def _port_from_environment(env: dict[str, str], default: int) -> int:
    raw = env.get("PTTI_NATIVE_QA_PORT")
    try:
        port = default if raw is None else int(raw, 10)
    except (TypeError, ValueError) as exc:
        raise NativeQAError("Native QA port must be a fixed decimal TCP port") from exc
    if not 1024 <= port <= 65535:
        raise NativeQAError("Native QA port must be between 1024 and 65535")
    return port


def validate_native_qa_candidate(
    executable: str | os.PathLike[str],
    local_app_data: str | os.PathLike[str],
    candidate_root: str | os.PathLike[str] | None,
) -> str:
    """Accept only the isolated, hash-identified Video First R4 preview package."""
    if not isinstance(candidate_root, (str, os.PathLike)) or not str(candidate_root).strip():
        raise NativeQAError("Native QA requires the explicit candidate package directory")
    executable_input = _absolute_path(executable)
    root_input = _absolute_path(candidate_root)
    local_input = _absolute_path(local_app_data)
    allowed_builds_input = local_input / "PTTI-Builds"
    info_input = root_input / "build-info.json"
    checksum_input = root_input / f"{executable_input.name}.sha256"
    for path in (executable_input, root_input, local_input, allowed_builds_input, info_input, checksum_input):
        _assert_no_reparse(path)
    exe = executable_input
    root = root_input
    local = local_input
    allowed_builds = _absolute_path(local / "PTTI-Builds")
    if exe.name.casefold() != "ptti-video-first-r4-preview.exe":
        raise NativeQAError("Native QA executable name does not match the isolated R4 preview")
    if root != exe.parent or not root.is_relative_to(allowed_builds):
        raise NativeQAError("Native QA candidate must be inside this user's isolated PTTI-Builds folder")
    if not exe.is_file():
        raise NativeQAError("Native QA candidate executable is missing")
    info_path = root / "build-info.json"
    checksum_path = root / f"{exe.name}.sha256"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        checksum = checksum_path.read_text(encoding="ascii").strip().split()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeQAError("Native QA candidate metadata or SHA-256 sidecar is unreadable") from exc
    if not isinstance(info, dict):
        raise NativeQAError("Native QA candidate build information is not an object")
    commit = info.get("commit")
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        raise NativeQAError("Native QA candidate build commit is invalid")
    expected_info = (
        info.get("product_name") == "PTTI Video First R4"
        and info.get("version") == "0.6.1-R4"
        and info.get("environment") == "DEVELOPMENT"
        and info.get("source_tree_dirty") is False
        and info.get("official_release") is False
        and info.get("media_included") is False
    )
    if not expected_info:
        raise NativeQAError("Native QA candidate is not a clean, non-release R4 preview")
    if len(checksum) != 2 or checksum[1] != exe.name:
        raise NativeQAError("Native QA candidate SHA-256 sidecar has an invalid format")
    digest = hashlib.sha256()
    with exe.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != checksum[0].casefold():
        raise NativeQAError("Native QA candidate executable SHA-256 does not match its sidecar")
    return commit


def configure_native_qa(
    local_app_data: str | os.PathLike[str],
    environ: dict[str, str] | None,
    build_commit: str,
    *,
    temp_root: str | os.PathLike[str] | None = None,
    default_port: int = NATIVE_QA_PORT,
) -> NativeQAConfig | None:
    """Prepare the same QA origin, profile, and SQLite path for one exact build.

    Each commit gets its own durable LocalAppData root. Earlier TEMP QA data is
    intentionally not discovered, moved, deleted, or treated as a migration.
    Existing identity files are read and verified; they are never rewritten.
    """
    env = os.environ if environ is None else environ
    if env.get("PTTI_NATIVE_QA") != "1":
        return None
    if not isinstance(build_commit, str) or not _COMMIT.fullmatch(build_commit):
        raise NativeQAError("Native QA requires the exact 40-character preview build commit")

    local_input = _absolute_path(local_app_data)
    _assert_no_reparse(local_input)
    local = local_input
    expected_parent = _absolute_path(local / "PTTI-Dev" / "NativeQA" / "GEX03")
    root = expected_parent / build_commit
    storage = root / "webview2-user-data"
    research_data = root / "research-data"
    qa_data = root / "qa-data"
    expected_db = _absolute_path(qa_data / "matches.db")
    identity_file = root / "qa-identity.json"
    database_ready_file = qa_data / "database-ready.json"
    db_value = env.get("PTTI_PREVIEW_QA_DB")
    if not isinstance(db_value, str) or not db_value.strip():
        raise NativeQAError("Native QA requires an explicit isolated PTTI_PREVIEW_QA_DB")
    db_input = _absolute_path(db_value)
    temp_input = _absolute_path(temp_root or tempfile.gettempdir())
    _assert_no_reparse(temp_input)
    _assert_no_reparse(db_input)
    temp = temp_input
    db = db_input
    if _path_key(expected_parent).startswith(_path_key(temp).rstrip("\\/") + os.sep):
        raise NativeQAError("Native QA storage must be outside the OS temporary directory")
    if _path_key(db) != _path_key(expected_db):
        raise NativeQAError("Native QA database must use the exact isolated Native QA path for this commit")
    if _path_key(db).startswith(_path_key(temp).rstrip("\\/") + os.sep):
        raise NativeQAError("Native QA database must be outside the OS temporary directory")
    if _path_key(db) in {
        _path_key(local / "PTTI" / "matches.db"),
        _path_key(local / "PTTI-Dev" / "matches.db"),
    }:
        raise NativeQAError("Native QA database collides with a user database")

    port = _port_from_environment(env, default_port)
    if port in {5173, 8765}:
        raise NativeQAError("Native QA may not reuse Founder Web QA or backend ports")
    for protected in (local / "PTTI", local / "PTTI-Dev" / "VideoFirst-R4-Preview"):
        protected_path = _absolute_path(protected)
        if _path_key(root) == _path_key(protected_path) or _path_key(root).startswith(
            _path_key(protected_path).rstrip("\\/") + os.sep
        ):
            raise NativeQAError("Native QA storage may not overlap a formal or existing R4 profile")

    _assert_no_reparse(local)
    _assert_no_reparse(expected_parent)
    _assert_no_reparse(root)
    _assert_no_reparse(storage)
    _assert_no_reparse(research_data)
    _assert_no_reparse(qa_data)
    _assert_no_reparse(temp)
    _assert_no_reparse(db)

    if _path_key(db_value) != _path_key(db):
        raise NativeQAError("PTTI_PREVIEW_QA_DB could not be resolved consistently")

    if root.exists():
        if _is_reparse_point(root):
            raise NativeQAError("Native QA root is a reparse point")
        if not identity_file.is_file():
            raise NativeQAError("Existing Native QA root has no identity file; preserving unknown data")
        try:
            identity = json.loads(identity_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NativeQAError("Native QA identity file is corrupt; preserving its contents") from exc
        if identity.get("schema") != _SCHEMA:
            raise NativeQAError("Native QA identity schema mismatch")
        if identity.get("build_commit") != build_commit:
            raise NativeQAError("Native QA root belongs to a different build")
        if _path_key(identity.get("database", "")) != _path_key(db):
            raise NativeQAError("Native QA root is already bound to a different database")
        if identity.get("port") != port:
            raise NativeQAError("Native QA root is already bound to a different fixed port")
        if _path_key(identity.get("storage_path", "")) != _path_key(storage):
            raise NativeQAError("Native QA storage path changed; refusing to migrate or overwrite")
        if _path_key(identity.get("research_data_path", "")) != _path_key(research_data):
            raise NativeQAError("Native QA research data path changed; refusing to migrate or overwrite")
        if _path_key(identity.get("qa_data_path", "")) != _path_key(qa_data):
            raise NativeQAError("Native QA persistent data path changed; refusing to migrate or overwrite")
        instance_id = identity.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise NativeQAError("Native QA identity file has no stable instance id")
        for required_directory in (storage, research_data, qa_data):
            if not required_directory.is_dir():
                raise NativeQAError(f"Previously initialized Native QA directory is missing; preserving data: {required_directory}")
        if database_ready_file.exists():
            try:
                ready = json.loads(database_ready_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise NativeQAError("Native QA database readiness record is corrupt; preserving all data") from exc
            if (ready.get("schema") != "ptti.native-qa-database-ready/0.1"
                    or ready.get("build_commit") != build_commit
                    or ready.get("instance_id") != instance_id
                    or _path_key(ready.get("database", "")) != _path_key(db)):
                raise NativeQAError("Native QA database readiness identity mismatch; preserving all data")
            if not db.is_file():
                raise NativeQAError("Previously initialized Native QA database is missing; refusing to create an empty replacement")
        _check_qa_database(db)
    else:
        if db.exists():
            raise NativeQAError("An unclaimed QA database already exists; preserving it and refusing reuse")
        root.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir()
        storage.mkdir()
        research_data.mkdir()
        qa_data.mkdir()
        _assert_writable_directory(storage)
        _assert_writable_directory(research_data)
        _assert_writable_directory(qa_data)
        instance_id = str(uuid.uuid4())
        identity = {
            "schema": _SCHEMA,
            "build_commit": build_commit,
            "instance_id": instance_id,
            "protocol": "http",
            "host": "127.0.0.1",
            "port": port,
            "origin": f"http://127.0.0.1:{port}",
            "database": str(db),
            "storage_path": str(storage),
            "research_data_path": str(research_data),
            "qa_data_path": str(qa_data),
        }
        try:
            with identity_file.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(identity, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except FileExistsError as exc:
            raise NativeQAError("Native QA identity was concurrently initialized; restart and verify") from exc

    storage.mkdir(parents=True, exist_ok=True)
    research_data.mkdir(parents=True, exist_ok=True)
    qa_data.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse(root)
    _assert_no_reparse(storage)
    _assert_no_reparse(research_data)
    _assert_no_reparse(qa_data)
    _assert_writable_directory(storage)
    _assert_writable_directory(qa_data)

    env.update({
        "PTTI_ENV": "development",
        "PTTI_PREVIEW": "1",
        "PTTI_PREVIEW_PROFILE": "video-first-r4",
        "PTTI_NATIVE_QA_ROOT": str(root),
        "PTTI_NATIVE_QA_INSTANCE_ID": instance_id,
        "PTTI_NATIVE_QA_PORT": str(port),
        "PTTI_DB": str(db),
        "PTTI_PREVIEW_QA_DB": str(db),
        "PTTI_RESEARCH_DATA_ROOT": str(research_data),
        "PTTI_NATIVE_QA_DATA_ROOT": str(qa_data),
        "PTTI_VIDEO_FEED_PREVIEW": "1",
        "WEBVIEW2_USER_DATA_FOLDER": str(storage),
    })
    env.pop("PTTI_DESKTOP_DEPLOY_ROOT", None)
    return NativeQAConfig(root, db, qa_data, storage, research_data, identity_file,
                          database_ready_file, build_commit, instance_id, port)


def mark_native_qa_database_ready(config: NativeQAConfig) -> None:
    """Mark the isolated DB after app initialization; never replace this marker."""
    if not config.database.is_file():
        raise NativeQAError("Native QA application database was not created; refusing to report it ready")
    _check_qa_database(config.database)
    value = {
        "schema": "ptti.native-qa-database-ready/0.1",
        "build_commit": config.build_commit,
        "instance_id": config.instance_id,
        "database": str(config.database),
        "initialized_at": datetime.now(timezone.utc).isoformat(),
    }
    if config.database_ready_file.exists():
        try:
            existing = json.loads(config.database_ready_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NativeQAError("Native QA database readiness record is corrupt; preserving it") from exc
        if any(existing.get(key) != value[key] for key in ("schema", "build_commit", "instance_id", "database")):
            raise NativeQAError("Native QA database readiness record does not match this candidate")
        return
    try:
        with config.database_ready_file.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise NativeQAError("Native QA database readiness marker was concurrently initialized") from exc


def bind_native_qa_port(port: int) -> socket.socket:
    """Reserve the exact loopback port for Uvicorn; never fall back to a new port."""
    if not isinstance(port, int) or not 1024 <= port <= 65535 or port in {5173, 8765}:
        raise NativeQAError("Invalid or reserved Native QA port")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(128)
        return sock
    except OSError as exc:
        sock.close()
        if exc.errno in {48, 98, 10048, 10013}:
            raise NativeQAError(f"Native QA port {port} is occupied or unavailable; refusing to choose another port") from exc
        raise NativeQAError(f"Native QA could not bind 127.0.0.1:{port}: {exc}") from exc


def health_matches_native_qa(
    payload: object,
    expected_commit: str,
    expected_instance_id: str,
    expected_origin: str,
    expected_qa_data_root: str | None = None,
) -> bool:
    valid = (
        isinstance(payload, dict)
        and payload.get("build_commit") == expected_commit
        and payload.get("native_qa_instance_id") == expected_instance_id
        and payload.get("native_qa_origin") == expected_origin
        and payload.get("video_feed") is True
    )
    if not valid or expected_qa_data_root is None:
        return bool(valid)
    return payload.get("native_qa_data_root") == expected_qa_data_root
