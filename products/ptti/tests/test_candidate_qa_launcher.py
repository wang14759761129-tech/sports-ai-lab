import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import candidate_qa_launcher as launcher


def _write_json(path: Path, payload: dict) -> bytes:
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return data


@pytest.fixture
def candidate_artifact(tmp_path):
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    exe = candidate_dir / launcher.PINNED_CANDIDATE.exe_name
    exe.write_bytes(b"isolated QA executable fixture")
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    build_info = {
        "commit": "a" * 40,
        "version": "test-preview",
    }
    build_bytes = _write_json(candidate_dir / "build-info.json", build_info)
    manifest = {
        "channel": "preview",
        "commit": build_info["commit"],
        "version": build_info["version"],
        "exe": exe.name,
        "files": {
            exe.name: exe_sha,
            "build-info.json": hashlib.sha256(build_bytes).hexdigest(),
        },
    }
    manifest_bytes = _write_json(candidate_dir / "manifest.json", manifest)
    pin = launcher.CandidatePin(
        source_commit=build_info["commit"],
        exe_name=exe.name,
        exe_sha256=exe_sha,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        build_info_sha256=hashlib.sha256(build_bytes).hexdigest(),
    )
    return candidate_dir, pin


def _make_session(temp_root: Path, candidate_dir: Path, pin: launcher.CandidatePin,
                  *, with_db: bool = True) -> tuple[Path, Path]:
    session_dir = temp_root / "PTTI-Candidate-QA-20261012-211411-c3cf3473"
    session_dir.mkdir()
    database_path = session_dir / "matches.db"
    launch = {
        "source_commit": pin.source_commit,
        "exe_sha256": pin.exe_sha256,
        "qa_database_path": str(database_path),
        "pid": 8188,
        "environment": "isolated QA",
        "diagnostics_enabled": True,
    }
    _write_json(session_dir / "launch.json", launch)
    if with_db:
        with sqlite3.connect(database_path) as connection:
            connection.execute("CREATE TABLE media_scan_jobs (scan_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            payload = {
                "scan_id": "scan-1",
                "status": "COMPLETED",
                "candidates": [{"candidate_id": "candidate-1", "status": "REVIEW_REQUIRED"}],
            }
            connection.execute(
                "INSERT INTO media_scan_jobs(scan_id,payload) VALUES (?,?)",
                ("scan-1", json.dumps(payload)),
            )
    return session_dir, database_path


def test_default_launch_plan_creates_fresh_os_temp_session(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()

    first = launcher.prepare_new_plan(
        candidate_dir, temp_root=temp_root, expected=pin, session_id="20261012-220000-a1b2c3d4"
    )
    second = launcher.prepare_new_plan(
        candidate_dir, temp_root=temp_root, expected=pin, session_id="20261012-220001-e5f6a7b8"
    )

    assert first.mode == "new"
    assert second.mode == "new"
    assert first.database_path != second.database_path
    assert first.database_path.parent.parent == temp_root
    assert not first.database_path.exists()
    assert launcher.parse_args(["--candidate-dir", str(candidate_dir)]).resume_session is None


def test_valid_resume_reads_completed_review_candidate_without_mutating_db(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, database_path = _make_session(temp_root, candidate_dir, pin)
    before = hashlib.sha256(database_path.read_bytes()).hexdigest()

    plan = launcher.prepare_resume_plan(
        candidate_dir,
        session_dir,
        temp_root=temp_root,
        expected=pin,
        running_processes=[],
        available_memory_bytes=3 * launcher.GIB,
    )

    assert plan.mode == "resume"
    assert plan.database_path == database_path
    assert plan.scan_count == 1
    assert plan.pending_candidate_count == 1
    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == before


def test_resume_rejects_session_outside_temp(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    outside = tmp_path / f"{temp_root.name}-sibling"
    outside.mkdir()
    session_dir, _ = _make_session(outside, candidate_dir, pin)

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_OUTSIDE_OS_TEMP"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_candidate_identity_mismatch(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin)
    launch_path = session_dir / "launch.json"
    launch = json.loads(launch_path.read_text())
    launch["source_commit"] = "b" * 40
    _write_json(launch_path, launch)

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_IDENTITY_MISMATCH"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_modified_candidate_executable(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin)
    (candidate_dir / pin.exe_name).write_bytes(b"changed executable")

    with pytest.raises(launcher.QALauncherError, match="QA_CANDIDATE_PACKAGE_INVALID"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_missing_database(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin, with_db=False)

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_DATABASE_MISSING"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_database_outside_session(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin)
    production_database = tmp_path / "production.db"
    production_database.write_bytes(b"fixture only; must never be opened")
    launch_path = session_dir / "launch.json"
    launch = json.loads(launch_path.read_text())
    launch["qa_database_path"] = str(production_database)
    _write_json(launch_path, launch)

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_DATABASE_INVALID"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )
    assert production_database.read_bytes() == b"fixture only; must never be opened"


def test_resume_rejects_database_with_wal_sidecar(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, database_path = _make_session(temp_root, candidate_dir, pin)
    Path(str(database_path) + "-wal").write_bytes(b"fixture sidecar")

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_DATABASE_BUSY"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_duplicate_candidate_process(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin)

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_IN_USE"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[(4672, pin.exe_name)], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_rejects_corrupt_database(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, database_path = _make_session(temp_root, candidate_dir, pin)
    database_path.write_bytes(b"not a sqlite database")

    with pytest.raises(launcher.QALauncherError, match="QA_SESSION_DATABASE_INVALID"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=3 * launcher.GIB,
        )


def test_resume_keeps_existing_resource_gate(candidate_artifact, tmp_path):
    candidate_dir, pin = candidate_artifact
    temp_root = tmp_path / "os-temp"
    temp_root.mkdir()
    session_dir, _ = _make_session(temp_root, candidate_dir, pin)

    with pytest.raises(launcher.QALauncherError, match="QA_RESOURCE_GATE"):
        launcher.prepare_resume_plan(
            candidate_dir, session_dir, temp_root=temp_root, expected=pin,
            running_processes=[], available_memory_bytes=launcher.MIN_AVAILABLE_RAM - 1,
        )


def test_child_environment_is_bound_to_qa_database_only(tmp_path):
    qa_database = tmp_path / "os-temp" / "session" / "matches.db"
    environment = launcher.build_qa_environment(
        qa_database,
        {
            "PTTI_DB": r"C:\Users\owner\AppData\Local\PTTI\matches.db",
            "PTTI_ENV": "production",
            "PTTI_DESKTOP_DEPLOY_ROOT": r"C:\PTTI\Launcher",
            "PTTI_VISION_HOME": r"C:\Users\owner\Documents\Vision",
            "PATH": "safe-path",
        },
    )

    assert environment["PTTI_PREVIEW_QA_DB"] == str(qa_database)
    assert environment["PTTI_PLAYBACK_DIAGNOSTICS"] == "1"
    assert "PTTI_DB" not in environment
    assert "PTTI_ENV" not in environment
    assert "PTTI_DESKTOP_DEPLOY_ROOT" not in environment
    assert "PTTI_VISION_HOME" not in environment
    assert environment["PATH"] == "safe-path"
