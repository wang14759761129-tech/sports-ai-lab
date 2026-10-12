"""Non-interactive, path-safe status reporting for packaged health checks."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from backend.temp_paths import resolve_temp_root as _resolve_temp_root

HEALTH_CHECK_STAGES = {
    "startup",
    "importing_runtime",
    "qa_database_validation",
    "importing_backend",
    "backend_initialization",
    "service_starting",
    "service_ready",
    "http_check",
    "result_write",
    "normal_exit",
}
_ACTIVE_REPORTER: HealthCheckReporter | None = None


class HealthCheckError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason if reason in {
            "qa_database_outside_temp",
            "health_http_failed",
            "health_http_status",
            "health_response_invalid",
            "health_commit_mismatch",
            "service_shutdown_timeout",
            "health_report_outside_temp",
        } else "health_check_failed"
        super().__init__(self.reason)


def is_health_check_mode(argv=None) -> bool:
    import sys

    return "--deployment-health-check" in (sys.argv if argv is None else argv)


def resolve_temp_root(environ=None) -> Path:
    """Compatibility alias for callers of the health-check module."""
    return _resolve_temp_root(environ)


def _strict_child(path, root: Path) -> Path | None:
    try:
        candidate = Path(path).expanduser().resolve(strict=False)
        relative = candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if relative.parts else None


def validate_qa_database_path(database_path, temp_root) -> Path:
    root = Path(temp_root).expanduser().resolve(strict=False)
    database = _strict_child(database_path, root)
    if database is None or database.suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}:
        raise HealthCheckError("qa_database_outside_temp")
    return database


def fetch_health_json(url: str, *, timeout: float = 5.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                raise HealthCheckError("health_http_status")
            payload = json.load(response)
    except HealthCheckError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise HealthCheckError("health_http_failed") from exc
    if not isinstance(payload, dict):
        raise HealthCheckError("health_response_invalid")
    return payload


def safe_error_type(exc: BaseException) -> str:
    allowed = {
        "HealthCheckError", "TimeoutError", "URLError", "HTTPError", "OSError",
        "RuntimeError", "ValueError", "JSONDecodeError", "CalledProcessError",
        "PackagerTimeoutError", "Exception",
    }
    name = type(exc).__name__
    return name if name in allowed else "OtherError"


def set_health_stage(stage: str) -> None:
    if stage not in HEALTH_CHECK_STAGES:
        raise ValueError("Unknown health-check stage")
    if _ACTIVE_REPORTER is not None:
        _ACTIVE_REPORTER.stage(stage)


def set_active_reporter(reporter: HealthCheckReporter | None) -> None:
    global _ACTIVE_REPORTER
    _ACTIVE_REPORTER = reporter


def get_active_reporter() -> HealthCheckReporter | None:
    return _ACTIVE_REPORTER


class HealthCheckReporter:
    def __init__(self, report_path, temp_root, database_path):
        self.temp_root = Path(temp_root).expanduser().resolve(strict=False)
        report = _strict_child(report_path, self.temp_root)
        if report is None:
            raise HealthCheckError("health_report_outside_temp")
        self.report_path = report
        database = _strict_child(database_path, self.temp_root)
        self.stage_name = "startup"
        self._record = {
            "status": "running",
            "stage": self.stage_name,
            "stage_history": [self.stage_name],
            "database_location": "runner_temp"
            if database is not None else "invalid",
        }
        self._write()

    @classmethod
    def from_environment(cls, environ=None):
        env = os.environ if environ is None else environ
        root = resolve_temp_root(env)
        report_path = env.get("PTTI_HEALTH_CHECK_RESULT")
        database_path = env.get("PTTI_PREVIEW_QA_DB")
        if not report_path:
            report_path = root / f"ptti-health-check-{os.getpid()}.json"
        return cls(report_path, root, database_path or root / "missing-qa.db")

    def _write(self):
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report_path.with_name(self.report_path.name + ".tmp")
        temporary.write_text(json.dumps(self._record, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.report_path)

    def stage(self, stage_name: str):
        if stage_name not in HEALTH_CHECK_STAGES:
            raise ValueError("Unknown health-check stage")
        self.stage_name = stage_name
        self._record.update(status="running", stage=stage_name)
        self._record["stage_history"].append(stage_name)
        self._write()

    def succeed(self, health_payload: dict, *, exit_code: int):
        if exit_code != 0:
            raise HealthCheckError("health_check_failed")
        self.stage("normal_exit")
        safe_health = {}
        for key in ("build_commit", "build_id", "version", "schema_version", "analytics_version"):
            value = health_payload.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_health[key] = value
        self._record.update(status="success", exit_code=0, health=safe_health)
        self._write()

    def fail(self, exc: BaseException, *, exit_code: int):
        reason = exc.reason if isinstance(exc, HealthCheckError) else "startup_exception"
        self._record.update(
            status="failed",
            stage=self.stage_name,
            exit_code=int(exit_code),
            error_type=safe_error_type(exc),
            exit_reason=reason,
        )
        self._write()
