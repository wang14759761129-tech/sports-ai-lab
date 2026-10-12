import json
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import psutil

from backend.health_check import (
    HealthCheckError,
    HealthCheckReporter,
    fetch_health_json,
    validate_qa_database_path,
)
from apps.desktop import report_health_startup_failure
from scripts.build_dual_source_v061_preview import PackagerTimeoutError, run_packager
from scripts.ci_windows_candidate import (
    record_health_timeout,
    sanitize_pytest_artifacts,
    summarize_pytest_report,
    verify_health_check_result,
)


def test_health_result_is_accepted_only_after_successful_exit_and_matching_identity(tmp_path):
    qa_root = tmp_path / "qa"
    qa_root.mkdir()
    qa_db = qa_root / "matches.db"
    qa_db.write_bytes(b"isolated test database marker")
    report_path = tmp_path / "reports" / "health-check.json"
    reporter = HealthCheckReporter(report_path, tmp_path, qa_db)
    reporter.stage("normal_exit")
    reporter.succeed({"build_commit": "abc123", "schema_version": "1"}, exit_code=0)

    assert verify_health_check_result(report_path, qa_db, tmp_path, "abc123", returncode=0)
    with pytest.raises(RuntimeError, match="exit normally"):
        verify_health_check_result(report_path, qa_db, tmp_path, "abc123", returncode=2)
    with pytest.raises(RuntimeError, match="source commit"):
        verify_health_check_result(report_path, qa_db, tmp_path, "different", returncode=0)


def test_wrong_qa_database_location_fails_closed_and_error_report_is_sanitized(tmp_path):
    qa_db = tmp_path.parent / "outside" / "matches.db"
    report_path = tmp_path / "health-check.json"
    reporter = HealthCheckReporter(report_path, tmp_path, qa_db)
    reporter.stage("qa_database_validation")
    with pytest.raises(HealthCheckError) as caught:
        validate_qa_database_path(qa_db, tmp_path)
    reporter.fail(caught.value, exit_code=2)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error_type"] == "HealthCheckError"
    assert report["exit_reason"] == "qa_database_outside_temp"
    assert report["stage"] == "qa_database_validation"
    assert str(qa_db) not in report_path.read_text(encoding="utf-8")
    assert report_health_startup_failure(caught.value, reporter) == 2


def test_health_request_failure_has_a_bounded_sanitized_error(monkeypatch):
    def fail_request(*_args, **_kwargs):
        raise TimeoutError("private URL and credentials must not enter diagnostics")

    monkeypatch.setattr("backend.health_check.urllib.request.urlopen", fail_request)
    with pytest.raises(HealthCheckError) as caught:
        fetch_health_json("http://127.0.0.1:43129/api/health", timeout=0.05)
    assert caught.value.reason == "health_http_failed"
    assert "credentials" not in str(caught.value)
    assert "43129" not in str(caught.value)


def test_health_packager_timeout_terminates_its_process_tree(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.build_dual_source_v061_preview.HARD_RAM_FLOOR_BYTES", 0)
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"open({str(child_pid_file)!r},'w').write(str(child.pid)); "
        "time.sleep(60)"
    )
    log_path = tmp_path / "health.log"

    with pytest.raises(PackagerTimeoutError):
        run_packager([sys.executable, "-c", child_code], log_path, timeout_seconds=0.5)

    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            psutil.Process(child_pid).status()
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)
    else:
        pytest.fail("child process from timed-out health check is still running")


def test_failed_ci_run_cannot_upload_candidate():
    workflow = Path(__file__).parents[3] / ".github" / "workflows" / "ptti-playback-candidate.yml"
    text = workflow.read_text(encoding="utf-8")
    candidate_step = text.split("- name: Upload verified candidate only", 1)[1]
    assert "if: success()" in candidate_step
    assert "if: always()" not in candidate_step.split("with:", 1)[0]
    assert "timeout_seconds=120" in Path(__file__).parents[1].joinpath(
        "scripts", "ci_windows_candidate.py"
    ).read_text(encoding="utf-8")


def test_unattended_startup_failure_path_does_not_call_a_modal_dialog():
    source = Path(__file__).parents[1].joinpath("apps", "desktop.py").read_text(encoding="utf-8")
    failure_branch = source.split("if is_health_check_mode():", 1)[1].split(
        "import traceback", 1
    )[0]
    assert "report_health_startup_failure" in failure_branch
    assert "SystemExit(exit_code)" in failure_branch
    assert "MessageBoxW" not in failure_branch


def test_health_timeout_preserves_last_stage_without_sensitive_exception_text(tmp_path):
    report_path = tmp_path / "health-check.json"
    reporter = HealthCheckReporter(report_path, tmp_path, tmp_path / "qa" / "matches.db")
    reporter.stage("backend_initialization")

    assert record_health_timeout(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["stage"] == "backend_initialization"
    assert report["error_type"] == "PackagerTimeoutError"
    assert report["exit_reason"] == "health_check_timeout"


def test_actions_runner_temp_is_accepted_as_the_guarded_database_root(tmp_path):
    from backend.main import resolve_database_path

    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    resolved = resolve_database_path(
        environ={
            "GITHUB_ACTIONS": "true",
            "RUNNER_TEMP": str(runner_temp),
            "PTTI_ENV": "test",
            "PTTI_DB": str(runner_temp / "ptti-ci-qa" / "matches.db"),
            "LOCALAPPDATA": str(tmp_path / "local-app-data"),
        },
        testing=True,
    )
    assert Path(resolved) == runner_temp / "ptti-ci-qa" / "matches.db"


def test_health_check_remains_strictly_bound_to_runner_temp(tmp_path):
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    runner_database = runner_temp / "ptti-ci-qa" / "matches.db"
    os_temp_database = Path(tempfile.gettempdir()) / "ptti-health-check-not-runner-temp.db"

    assert validate_qa_database_path(runner_database, runner_temp) == runner_database.resolve()
    with pytest.raises(HealthCheckError) as caught:
        validate_qa_database_path(os_temp_database, runner_temp)
    assert caught.value.reason == "qa_database_outside_temp"


def test_ci_pytest_summary_classifies_collection_and_masks_machine_paths(tmp_path):
    os_temp = tmp_path / "os-temp-private-root"
    runner_temp = tmp_path / "runner-temp-private-root"
    reports = tmp_path / "reports"
    reports.mkdir()
    junit = reports / "pytest.xml"
    log = reports / "pytest.log"
    suites = ET.Element("testsuites")
    suite = ET.SubElement(suites, "testsuite", tests="1", errors="1", failures="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname="", name="tests.test_bootstrap")
    error = ET.SubElement(case, "error", message="collection failure")
    error.text = (
        f"PRODUCTION_DATABASE_WRITE_GUARD: {os_temp / 'bootstrap.db'} is outside "
        f"{runner_temp}"
    )
    junit.write_bytes(ET.tostring(suites, encoding="utf-8", xml_declaration=True))
    log.write_text(f"{os_temp}\\bootstrap.db rejected by {runner_temp}", encoding="utf-8")

    summary = summarize_pytest_report(junit)
    assert summary == {
        "status": "failed",
        "collection": "failed",
        "collected_cases": 1,
        "collection_errors": 1,
        "test_errors": 0,
        "test_failures": 0,
        "skipped": 0,
        "failure_reason": "database_path_guard_rejected_temp_root",
    }
    sanitize_pytest_artifacts(
        [junit, log], [('OS_TEMP', os_temp), ('RUNNER_TEMP', runner_temp)]
    )

    sanitized_log = log.read_text(encoding="utf-8")
    sanitized_junit = junit.read_text(encoding="utf-8")
    assert str(os_temp) not in sanitized_log + sanitized_junit
    assert str(runner_temp) not in sanitized_log + sanitized_junit
    assert "[OS_TEMP]" in sanitized_log
    assert "[RUNNER_TEMP]" in sanitized_log
    ET.fromstring(sanitized_junit)
