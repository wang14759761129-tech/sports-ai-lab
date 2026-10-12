"""Launch a verified Preview QA candidate in a fresh or explicitly resumed OS Temp session.

This script is an opt-in QA launcher. Omitting ``--resume-session`` always creates
a new isolated session. Resuming is limited to the archived R4 candidate pinned
below; it never copies, migrates, or edits the old QA database.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import uuid


GIB = 1024**3
MIN_AVAILABLE_RAM = int(2.5 * GIB)
QA_SESSION_PREFIX = "PTTI-Candidate-QA-"
REPARSE_POINT_ATTRIBUTE = 0x400


@dataclass(frozen=True)
class CandidatePin:
    source_commit: str
    exe_name: str
    exe_sha256: str
    manifest_sha256: str
    build_info_sha256: str


@dataclass(frozen=True)
class CandidateArtifact:
    directory: Path
    executable: Path
    source_commit: str
    exe_sha256: str


@dataclass(frozen=True)
class LaunchPlan:
    mode: str
    candidate: CandidateArtifact
    session_directory: Path
    database_path: Path
    scan_count: int = 0
    pending_candidate_count: int = 0


class QALauncherError(RuntimeError):
    """A safe, path-redacted QA preflight failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# These values pin the already archived and verified Run #38218170457 candidate.
# A different EXE requires a separately reviewed pin update.
PINNED_CANDIDATE = CandidatePin(
    source_commit="d6d62c103adafb2a12a996c8d6e73fffb3d41c63",
    exe_name="PTTI-Video-First-R4-Preview.exe",
    exe_sha256="b569e9841ee849e83cc66770e2e5e4afc17041257d71c872710eaa73177eccf7",
    manifest_sha256="e28273b0314dec302bd5a1b9324400668c2ba7f108bb004abcdb968e2600c514",
    build_info_sha256="40abf8175af051482528ec98a3197f1e54110ae70b946df46b699f7fc5838361",
)


def _raise(code: str) -> None:
    raise QALauncherError(code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise QALauncherError("QA_CANDIDATE_PACKAGE_INVALID") from exc
    return digest.hexdigest()


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise QALauncherError("QA_PATH_INVALID") from exc
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & REPARSE_POINT_ATTRIBUTE)


def _reject_reparse_chain(root: Path, path: Path, code: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise QALauncherError(code) from exc
    current = root
    for component in (None, *relative.parts):
        if component is not None:
            current = current / component
        try:
            is_reparse = _is_reparse_point(current)
        except QALauncherError as exc:
            raise QALauncherError(code) from exc
        if is_reparse:
            _raise(code)


def _is_within(path: Path, root: Path) -> bool:
    try:
        common = os.path.commonpath((os.path.normcase(str(path)), os.path.normcase(str(root))))
    except (OSError, ValueError):
        return False
    return common == os.path.normcase(str(root)) and path != root


def _read_json(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QALauncherError(code) from exc
    if not isinstance(value, dict):
        _raise(code)
    return value


def validate_candidate(candidate_directory, *, expected: CandidatePin = PINNED_CANDIDATE) -> CandidateArtifact:
    try:
        original = Path(candidate_directory).expanduser()
        candidate = original.resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise QALauncherError("QA_CANDIDATE_PACKAGE_INVALID") from exc
    if not candidate.is_dir() or _is_reparse_point(original):
        _raise("QA_CANDIDATE_PACKAGE_INVALID")

    manifest_path = candidate / "manifest.json"
    build_info_path = candidate / "build-info.json"
    try:
        _reject_reparse_chain(candidate, manifest_path, "QA_CANDIDATE_PACKAGE_INVALID")
        _reject_reparse_chain(candidate, build_info_path, "QA_CANDIDATE_PACKAGE_INVALID")
    except QALauncherError:
        raise
    manifest = _read_json(manifest_path, "QA_CANDIDATE_PACKAGE_INVALID")
    build_info = _read_json(build_info_path, "QA_CANDIDATE_PACKAGE_INVALID")

    if (
        _sha256(manifest_path) != expected.manifest_sha256
        or _sha256(build_info_path) != expected.build_info_sha256
        or manifest.get("channel") != "preview"
        or manifest.get("commit") != expected.source_commit
        or build_info.get("commit") != expected.source_commit
        or manifest.get("version") != build_info.get("version")
        or manifest.get("exe") != expected.exe_name
    ):
        _raise("QA_CANDIDATE_IDENTITY_MISMATCH")

    files = manifest.get("files")
    if not isinstance(files, dict) or expected.exe_name not in files or len(files) > 5000:
        _raise("QA_CANDIDATE_PACKAGE_INVALID")

    for relative_name, expected_hash in files.items():
        if not isinstance(relative_name, str) or "\\" in relative_name:
            _raise("QA_CANDIDATE_PACKAGE_INVALID")
        relative = PurePosixPath(relative_name)
        if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            _raise("QA_CANDIDATE_PACKAGE_INVALID")
        target = candidate.joinpath(*relative.parts)
        try:
            resolved_target = target.resolve(strict=True)
            if not _is_within(resolved_target, candidate):
                _raise("QA_CANDIDATE_PACKAGE_INVALID")
            _reject_reparse_chain(candidate, target, "QA_CANDIDATE_PACKAGE_INVALID")
        except (OSError, RuntimeError) as exc:
            raise QALauncherError("QA_CANDIDATE_PACKAGE_INVALID") from exc
        if not resolved_target.is_file() or _sha256(resolved_target) != str(expected_hash).casefold():
            _raise("QA_CANDIDATE_PACKAGE_INVALID")

    executable = candidate / expected.exe_name
    if _sha256(executable) != expected.exe_sha256 or str(files[expected.exe_name]).casefold() != expected.exe_sha256:
        _raise("QA_CANDIDATE_IDENTITY_MISMATCH")
    return CandidateArtifact(candidate, executable, expected.source_commit, expected.exe_sha256)


def _resolve_os_temp(temp_root=None) -> Path:
    try:
        root = Path(temp_root if temp_root is not None else tempfile.gettempdir()).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise QALauncherError("QA_OS_TEMP_UNAVAILABLE") from exc
    if not root.is_dir():
        _raise("QA_OS_TEMP_UNAVAILABLE")
    return root


def _require_resource_gate(available_memory_bytes=None) -> None:
    if available_memory_bytes is None:
        available_memory_bytes = _available_memory_bytes()
    if int(available_memory_bytes) < MIN_AVAILABLE_RAM:
        _raise("QA_RESOURCE_GATE")


def _available_memory_bytes() -> int:
    if os.name != "nt":
        _raise("QA_RESOURCE_CHECK_UNAVAILABLE")

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query = kernel32.GlobalMemoryStatusEx
        query.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        query.restype = wintypes.BOOL
        if not query(ctypes.byref(status)):
            _raise("QA_RESOURCE_CHECK_UNAVAILABLE")
    except (AttributeError, OSError) as exc:
        raise QALauncherError("QA_RESOURCE_CHECK_UNAVAILABLE") from exc
    return int(status.ullAvailPhys)


def _running_candidate_processes():
    if os.name != "nt":
        raise QALauncherError("QA_PROCESS_CHECK_UNAVAILABLE")
    try:
        query = (
            "$ErrorActionPreference='Stop'; "
            "$ids=@(Get-CimInstance Win32_Process -Filter \"Name='"
            + PINNED_CANDIDATE.exe_name
            + "'\" | ForEach-Object { [int]$_.ProcessId }); "
            "ConvertTo-Json -InputObject $ids -Compress"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            raise QALauncherError("QA_PROCESS_CHECK_UNAVAILABLE")
        raw = result.stdout.strip()
        if not raw:
            raise QALauncherError("QA_PROCESS_CHECK_UNAVAILABLE")
        value = json.loads(raw)
        pids = value if isinstance(value, list) else ([] if value is None else [value])
        return [(int(pid), PINNED_CANDIDATE.exe_name) for pid in pids]
    except QALauncherError:
        raise
    except Exception as exc:
        raise QALauncherError("QA_PROCESS_CHECK_UNAVAILABLE") from exc


def _require_no_running_candidate(candidate: CandidateArtifact, running_processes=None) -> None:
    processes = _running_candidate_processes() if running_processes is None else running_processes
    expected = candidate.executable.name.casefold()
    if any(str(name).casefold() == expected for _, name in processes):
        _raise("QA_SESSION_IN_USE")


def _validate_session_root(session_directory, temp_root: Path) -> Path:
    try:
        original = Path(session_directory).expanduser().absolute()
        session = original.resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise QALauncherError("QA_SESSION_OUTSIDE_OS_TEMP") from exc
    if not session.is_dir() or not _is_within(session, temp_root):
        _raise("QA_SESSION_OUTSIDE_OS_TEMP")
    try:
        relative = session.relative_to(temp_root)
    except ValueError as exc:
        raise QALauncherError("QA_SESSION_OUTSIDE_OS_TEMP") from exc
    if len(relative.parts) != 1 or not session.name.startswith(QA_SESSION_PREFIX):
        _raise("QA_SESSION_OUTSIDE_OS_TEMP")
    _reject_reparse_chain(temp_root, original, "QA_SESSION_OUTSIDE_OS_TEMP")
    return session


def _read_database(database: Path) -> tuple[int, int]:
    if not database.is_file() or database.stat().st_size == 0:
        _raise("QA_SESSION_DATABASE_MISSING")
    if Path(str(database) + "-wal").exists() or Path(str(database) + "-shm").exists():
        _raise("QA_SESSION_DATABASE_BUSY")
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
        connection.row_factory = sqlite3.Row
        try:
            check = connection.execute("PRAGMA quick_check").fetchone()
            if check is None or check[0] != "ok":
                _raise("QA_SESSION_DATABASE_INVALID")
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(media_scan_jobs)")}
            if not {"scan_id", "payload"}.issubset(columns):
                _raise("QA_SESSION_DATABASE_INVALID")
            rows = connection.execute("SELECT scan_id, payload FROM media_scan_jobs").fetchall()
            if not rows:
                _raise("QA_SESSION_EMPTY")
            settled = 0
            pending = 0
            for row in rows:
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise QALauncherError("QA_SESSION_DATABASE_INVALID") from exc
                if not isinstance(payload, dict) or payload.get("scan_id") != row["scan_id"]:
                    _raise("QA_SESSION_DATABASE_INVALID")
                status = payload.get("status")
                if status in {"QUEUED", "RUNNING"}:
                    _raise("QA_SESSION_SCAN_NOT_SETTLED")
                if status not in {"COMPLETED", "INTERRUPTED", "FAILED"}:
                    _raise("QA_SESSION_DATABASE_INVALID")
                if status in {"COMPLETED", "INTERRUPTED"}:
                    settled += 1
                candidates = payload.get("candidates", [])
                if not isinstance(candidates, list) or any(not isinstance(item, dict) for item in candidates):
                    _raise("QA_SESSION_DATABASE_INVALID")
                pending += sum(
                    1
                    for item in candidates
                    if item.get("status", item.get("review_status")) == "REVIEW_REQUIRED"
                    and not item.get("registered_video_id")
                )
            if settled == 0:
                _raise("QA_SESSION_NO_SETTLED_SCAN")
            return len(rows), pending
        finally:
            connection.close()
    except QALauncherError:
        raise
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise QALauncherError("QA_SESSION_DATABASE_INVALID") from exc


def prepare_resume_plan(
    candidate_directory,
    session_directory,
    *,
    temp_root=None,
    expected: CandidatePin = PINNED_CANDIDATE,
    running_processes=None,
    available_memory_bytes=None,
) -> LaunchPlan:
    candidate = validate_candidate(candidate_directory, expected=expected)
    _require_no_running_candidate(candidate, running_processes)
    _require_resource_gate(available_memory_bytes)
    root = _resolve_os_temp(temp_root)
    session = _validate_session_root(session_directory, root)
    launch_path = session / "launch.json"
    database = session / "matches.db"
    if not launch_path.is_file():
        _raise("QA_SESSION_METADATA_MISSING")
    _reject_reparse_chain(session, launch_path, "QA_SESSION_METADATA_INVALID")
    if not database.is_file():
        _raise("QA_SESSION_DATABASE_MISSING")
    _reject_reparse_chain(session, database, "QA_SESSION_DATABASE_INVALID")

    launch = _read_json(launch_path, "QA_SESSION_METADATA_INVALID")
    if (
        launch.get("source_commit") != candidate.source_commit
        or str(launch.get("exe_sha256", "")).casefold() != candidate.exe_sha256
        or launch.get("environment") != "isolated QA"
        or launch.get("diagnostics_enabled") is not True
    ):
        _raise("QA_SESSION_IDENTITY_MISMATCH")
    if launch.get("PTTI_DB") or launch.get("production_database"):
        _raise("QA_SESSION_IDENTITY_MISMATCH")

    try:
        recorded_database = Path(launch.get("qa_database_path", "")).expanduser().resolve(strict=True)
        database = database.resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise QALauncherError("QA_SESSION_DATABASE_MISSING") from exc
    if recorded_database != database or not _is_within(database, root):
        _raise("QA_SESSION_DATABASE_INVALID")

    scan_count, pending_count = _read_database(database)
    return LaunchPlan("resume", candidate, session, database, scan_count, pending_count)


def prepare_new_plan(
    candidate_directory,
    *,
    temp_root=None,
    expected: CandidatePin = PINNED_CANDIDATE,
    session_id=None,
) -> LaunchPlan:
    candidate = validate_candidate(candidate_directory, expected=expected)
    root = _resolve_os_temp(temp_root)
    identifier = session_id or (
        datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    )
    if not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{8}", identifier):
        _raise("QA_SESSION_ID_INVALID")
    session = root / f"{QA_SESSION_PREFIX}{identifier}"
    if session.exists():
        _raise("QA_SESSION_ALREADY_EXISTS")
    return LaunchPlan("new", candidate, session, session / "matches.db")


def build_qa_environment(database_path: Path, environ=None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    child = dict(source)
    for key in ("PTTI_DB", "PTTI_ENV", "PTTI_DESKTOP_DEPLOY_ROOT", "PTTI_VISION_HOME"):
        child.pop(key, None)
    child["PTTI_PREVIEW_QA_DB"] = str(database_path)
    child["PTTI_PLAYBACK_DIAGNOSTICS"] = "1"
    return child


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Launch the pinned PTTI Preview candidate in an isolated QA session.")
    parser.add_argument("--candidate-dir", required=True, help="Verified candidate folder containing manifest.json")
    parser.add_argument(
        "--resume-session",
        help="Explicitly resume one existing PTTI-Candidate-QA-* directory under OS Temp",
    )
    parser.add_argument("--check-only", action="store_true", help="Run preflight without starting the candidate")
    return parser.parse_args(argv)


def _write_launch_record(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        raise QALauncherError("QA_SESSION_METADATA_WRITE_FAILED") from exc


def _launch(plan: LaunchPlan) -> int:
    if plan.mode == "new":
        try:
            plan.session_directory.mkdir()
        except OSError as exc:
            raise QALauncherError("QA_SESSION_CREATE_FAILED") from exc
        _write_launch_record(
            plan.session_directory / "launch.json",
            {
                "source_commit": plan.candidate.source_commit,
                "exe_sha256": plan.candidate.exe_sha256,
                "qa_database_path": str(plan.database_path),
                "pid": None,
                "environment": "isolated QA",
                "diagnostics_enabled": True,
            },
        )

    env = build_qa_environment(plan.database_path)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        process = subprocess.Popen(
            [str(plan.candidate.executable)],
            cwd=str(plan.candidate.directory),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    except OSError as exc:
        if plan.mode == "new":
            _write_launch_record(
                plan.session_directory / "launch.json",
                {
                    "source_commit": plan.candidate.source_commit,
                    "exe_sha256": plan.candidate.exe_sha256,
                    "qa_database_path": str(plan.database_path),
                    "pid": None,
                    "environment": "isolated QA",
                    "diagnostics_enabled": True,
                    "launch_error": type(exc).__name__,
                },
            )
        raise QALauncherError("QA_CANDIDATE_START_FAILED") from exc

    if plan.mode == "new":
        _write_launch_record(
            plan.session_directory / "launch.json",
            {
                "source_commit": plan.candidate.source_commit,
                "exe_sha256": plan.candidate.exe_sha256,
                "qa_database_path": str(plan.database_path),
                "pid": process.pid,
                "environment": "isolated QA",
                "diagnostics_enabled": True,
            },
        )
    return process.pid


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.resume_session:
            plan = prepare_resume_plan(args.candidate_dir, args.resume_session)
        else:
            plan = prepare_new_plan(args.candidate_dir)
            _require_no_running_candidate(plan.candidate)
            _require_resource_gate()
        if args.check_only:
            print(
                f"QA_PREFLIGHT_OK mode={plan.mode} source={plan.candidate.source_commit} "
                f"scans={plan.scan_count} pending={plan.pending_candidate_count} database=OS_TEMP"
            )
            return 0
        pid = _launch(plan)
        print(f"QA_CANDIDATE_STARTED mode={plan.mode} pid={pid} session={plan.session_directory.name}")
        return 0
    except QALauncherError as exc:
        print(exc.code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
