import json
import hashlib
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from apps.native_qa import (
    NativeQAError,
    bind_native_qa_port,
    configure_native_qa,
    health_matches_native_qa,
    mark_native_qa_database_ready,
    validate_native_qa_candidate,
)


def _qa_database(local: Path, commit: str) -> Path:
    return local / "PTTI-Dev" / "NativeQA" / "GEX03" / commit / "qa-data" / "matches.db"


def test_native_qa_uses_stable_persistent_localappdata_and_fixed_origin(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "a" * 40)
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}
    first = configure_native_qa(local, env, "a" * 40, temp_root=temp)
    second = configure_native_qa(local, env, "a" * 40, temp_root=temp)

    assert first == second
    assert first.origin == "http://127.0.0.1:48761"
    assert first.webview2_user_data.is_relative_to(local)
    assert not first.webview2_user_data.is_relative_to(temp)
    assert not first.webview2_user_data.is_relative_to(temp)
    assert first.database == database.resolve()
    assert first.qa_data == database.parent.resolve()
    assert first.database.is_relative_to(local)
    assert not first.database.is_relative_to(temp)
    assert first.instance_id
    assert env["PTTI_DB"] == env["PTTI_PREVIEW_QA_DB"]
    assert json.loads(first.identity_file.read_text())["instance_id"] == first.instance_id


def test_native_qa_identity_is_stable_when_path_resolve_redirects_localappdata(tmp_path, monkeypatch):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "f" * 40)
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}

    def redirected_resolve(self, *args, **kwargs):
        raise AssertionError("Native QA must not resolve paths through app-container redirects")

    monkeypatch.setattr(Path, "resolve", redirected_resolve)
    first = configure_native_qa(local, env, "f" * 40, temp_root=temp)
    import sqlite3
    connection = sqlite3.connect(first.database)
    connection.execute("CREATE TABLE restart_probe (value TEXT)")
    connection.execute("INSERT INTO restart_probe VALUES ('kept')")
    connection.commit()
    connection.close()
    mark_native_qa_database_ready(first)

    second = configure_native_qa(local, env, "f" * 40, temp_root=temp)
    assert second == first
    assert second.database.read_bytes()
    assert json.loads(second.identity_file.read_text())["database"] == str(database.absolute())


def test_native_qa_profile_and_origin_survive_separate_process_restarts(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "d" * 40)
    code = (
        "import json, os, sqlite3; from apps.native_qa import configure_native_qa,mark_native_qa_database_ready; "
        "c=configure_native_qa(os.environ['PTTI_TEST_LOCAL'], os.environ, 'd'*40, "
        "temp_root=os.environ['PTTI_TEST_TEMP']); "
        "db=sqlite3.connect(c.database); db.execute('CREATE TABLE IF NOT EXISTS restart_probe (id TEXT PRIMARY KEY, value TEXT)'); "
        "db.execute(\"INSERT OR IGNORE INTO restart_probe VALUES ('qa', 'kept')\"); db.commit(); "
        "probe=db.execute(\"SELECT value FROM restart_probe WHERE id='qa'\").fetchone()[0]; db.close(); "
        "mark_native_qa_database_ready(c); "
        "print(json.dumps({'origin':c.origin,'storage':str(c.webview2_user_data),"
        "'database':str(c.database),'qa_data':str(c.qa_data),'probe':probe,"
        "'instance':c.instance_id,'private_mode':c.webview_options['private_mode']}))"
    )
    child_env = {
        **os.environ,
        "PTTI_NATIVE_QA": "1",
        "PTTI_PREVIEW_QA_DB": str(database),
        "PTTI_NATIVE_QA_PORT": "48761",
        "PTTI_TEST_LOCAL": str(local),
        "PTTI_TEST_TEMP": str(temp),
        "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parents[1]), os.environ.get("PYTHONPATH", "")]),
    }
    first = json.loads(subprocess.check_output([sys.executable, "-c", code], env=child_env, text=True))
    second = json.loads(subprocess.check_output([sys.executable, "-c", code], env=child_env, text=True))

    assert first == second
    assert first["origin"] == "http://127.0.0.1:48761"
    assert first["private_mode"] is False
    assert first["storage"].startswith(str(local))
    assert first["database"] == second["database"]
    assert first["qa_data"].endswith("qa-data")
    assert first["probe"] == second["probe"] == "kept"


def test_non_native_launch_is_unchanged():
    env = {"PTTI_DB": "caller-controlled"}
    assert configure_native_qa("<LOCAL_USER_ROOT>/AppData/Local", env, "a" * 40) is None
    assert env == {"PTTI_DB": "caller-controlled"}


def test_native_qa_fails_closed_on_corrupt_or_mismatched_identity(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "a" * 40)
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}
    first = configure_native_qa(local, env, "a" * 40, temp_root=temp)
    first.identity_file.write_text("{broken")
    with pytest.raises(NativeQAError, match="identity"):
        configure_native_qa(local, env, "a" * 40, temp_root=temp)
    first.identity_file.write_text(json.dumps({"schema": "ptti.native-qa-identity/0.2", "build_commit": "b" * 40}))
    with pytest.raises(NativeQAError, match="different build"):
        configure_native_qa(local, env, "a" * 40, temp_root=temp)


def test_native_qa_rejects_database_outside_exact_commit_qa_root(tmp_path):
    local = tmp_path / "LocalAppData"
    with pytest.raises(NativeQAError, match="exact isolated Native QA path"):
        configure_native_qa(
            local,
            {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(tmp_path / "matches.db")},
            "a" * 40,
            temp_root=tmp_path / "Temp",
        )


def test_native_qa_requires_explicit_database_path(tmp_path):
    with pytest.raises(NativeQAError, match="explicit isolated"):
        configure_native_qa(
            tmp_path / "LocalAppData",
            {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": ""},
            "a" * 40,
            temp_root=tmp_path / "Temp",
        )


def test_native_qa_does_not_reuse_existing_unclaimed_database(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "a" * 40)
    database.parent.mkdir(parents=True)
    database.write_bytes(b"preserve")
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}
    with pytest.raises(NativeQAError, match="no identity file"):
        configure_native_qa(local, env, "a" * 40, temp_root=temp)
    assert database.read_bytes() == b"preserve"


def test_fixed_port_binds_only_loopback_and_conflict_is_explicit():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    port = occupied.getsockname()[1]
    with pytest.raises(NativeQAError, match="occupied"):
        bind_native_qa_port(port)
    occupied.close()

    bound = bind_native_qa_port(port)
    try:
        assert bound.getsockname() == ("127.0.0.1", port)
        assert bound.gettimeout() is None
    finally:
        bound.close()


def test_health_must_match_preview_commit_instance_and_origin():
    expected = {
        "build_commit": "a" * 40,
        "video_feed": True,
        "native_qa_instance_id": "qa-123",
        "native_qa_origin": "http://127.0.0.1:48761",
    }
    assert health_matches_native_qa(expected, "a" * 40, "qa-123", "http://127.0.0.1:48761")
    assert not health_matches_native_qa({**expected, "build_commit": "b" * 40}, "a" * 40, "qa-123", "http://127.0.0.1:48761")
    assert not health_matches_native_qa({**expected, "native_qa_instance_id": "other"}, "a" * 40, "qa-123", "http://127.0.0.1:48761")
    assert not health_matches_native_qa({**expected, "native_qa_origin": "http://127.0.0.1:1"}, "a" * 40, "qa-123", "http://127.0.0.1:48761")
    assert not health_matches_native_qa({**expected, "native_qa_data_root": "wrong"}, "a" * 40, "qa-123", "http://127.0.0.1:48761", "expected")


def test_webview_options_explicitly_enable_persistent_private_data(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    config = configure_native_qa(
        local,
        {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(_qa_database(local, "c" * 40))},
        "c" * 40,
        temp_root=temp,
    )
    assert config.webview_options == {"private_mode": False, "storage_path": str(config.webview2_user_data)}


def test_native_qa_sqlite_is_per_commit_and_legacy_temp_data_is_untouched(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    legacy_root = temp / "PTTI-GEX03B-Native-QA" / ("a" * 40)
    legacy_root.mkdir(parents=True)
    legacy_db = legacy_root / "matches.db"
    legacy_db.write_bytes(b"legacy TEMP data; leave untouched")

    first_env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(_qa_database(local, "a" * 40))}
    second_env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(_qa_database(local, "b" * 40))}
    first = configure_native_qa(local, first_env, "a" * 40, temp_root=temp)
    second = configure_native_qa(local, second_env, "b" * 40, temp_root=temp)

    assert first.database != second.database
    assert first.database.is_relative_to(local) and second.database.is_relative_to(local)
    assert legacy_db.read_bytes() == b"legacy TEMP data; leave untouched"


def test_native_qa_refuses_corrupt_persistent_sqlite_without_replacing_it(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "a" * 40)
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}
    configure_native_qa(local, env, "a" * 40, temp_root=temp)
    database.write_bytes(b"not sqlite")

    with pytest.raises(NativeQAError, match="corrupt"):
        configure_native_qa(local, env, "a" * 40, temp_root=temp)

    assert database.read_bytes() == b"not sqlite"


def test_native_qa_refuses_to_silently_recreate_a_missing_ready_database(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    database = _qa_database(local, "a" * 40)
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(database)}
    config = configure_native_qa(local, env, "a" * 40, temp_root=temp)
    import sqlite3
    connection = sqlite3.connect(database)
    with connection:
        connection.execute("CREATE TABLE qa_record (value TEXT)")
        connection.execute("INSERT INTO qa_record VALUES ('saved')")
    connection.close()
    mark_native_qa_database_ready(config)
    database.unlink()

    with pytest.raises(NativeQAError, match="refusing to create an empty replacement"):
        configure_native_qa(local, env, "a" * 40, temp_root=temp)
    assert not database.exists()


def test_native_qa_storage_must_be_writable(tmp_path):
    from apps.native_qa import _assert_writable_directory

    occupied_by_file = tmp_path / "not-a-directory"
    occupied_by_file.write_text("preserve")
    with pytest.raises(NativeQAError, match="not writable"):
        _assert_writable_directory(occupied_by_file)
    assert occupied_by_file.read_text() == "preserve"


def test_native_qa_refuses_to_recreate_missing_existing_webview_profile(tmp_path):
    local = tmp_path / "LocalAppData"
    temp = tmp_path / "Temp"
    temp.mkdir()
    env = {"PTTI_NATIVE_QA": "1", "PTTI_PREVIEW_QA_DB": str(_qa_database(local, "c" * 40))}
    config = configure_native_qa(local, env, "c" * 40, temp_root=temp)
    import shutil
    shutil.rmtree(config.webview2_user_data)

    with pytest.raises(NativeQAError, match="directory is missing"):
        configure_native_qa(local, env, "c" * 40, temp_root=temp)
    assert not config.webview2_user_data.exists()


def _candidate_fixture(local_app_data: Path):
    root = local_app_data / "PTTI-Builds" / "video-first-r4-test" / "dist" / "PTTI-Video-First-R4-Preview"
    root.mkdir(parents=True)
    exe = root / "PTTI-Video-First-R4-Preview.exe"
    exe.write_bytes(b"isolated-preview-fixture")
    info = {
        "product_name": "PTTI Video First R4",
        "version": "0.6.1-R4",
        "commit": "e" * 40,
        "environment": "DEVELOPMENT",
        "source_tree_dirty": False,
        "official_release": False,
        "media_included": False,
    }
    (root / "build-info.json").write_text(json.dumps(info), encoding="utf-8")
    (root / f"{exe.name}.sha256").write_text(f"{hashlib.sha256(exe.read_bytes()).hexdigest()}  {exe.name}\n", encoding="ascii")
    return root, exe


def test_native_qa_candidate_requires_isolated_build_identity_and_matching_hash(tmp_path):
    local = tmp_path / "LocalAppData"
    root, exe = _candidate_fixture(local)
    assert validate_native_qa_candidate(exe, local, root) == "e" * 40

    exe.write_bytes(b"modified")
    with pytest.raises(NativeQAError, match="SHA-256"):
        validate_native_qa_candidate(exe, local, root)


def test_native_qa_candidate_validation_uses_literal_absolute_paths(tmp_path, monkeypatch):
    local = tmp_path / "LocalAppData"
    root, exe = _candidate_fixture(local)

    def redirected_resolve(self, *args, **kwargs):
        raise AssertionError("Candidate identity must not resolve through app-container redirects")

    monkeypatch.setattr(Path, "resolve", redirected_resolve)
    assert validate_native_qa_candidate(exe, local, root) == "e" * 40


def test_native_qa_rejects_formal_or_outside_candidate_path(tmp_path):
    local = tmp_path / "LocalAppData"
    root, exe = _candidate_fixture(local)
    with pytest.raises(NativeQAError, match="inside this user's isolated"):
        validate_native_qa_candidate(exe, local, tmp_path / "formal-R4")
