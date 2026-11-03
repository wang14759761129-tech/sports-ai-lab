"""Opt-in, content-free diagnostics for native Vision playback QA."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_LOG_PATH: Path | None = None
_EVENT_LIMIT = 256
_EVENT_COUNT = 0
_UI_STATES = {
    "loading", "ready", "error", "selected", "media_ready", "media_error",
    "playing", "paused", "seeked", "rate_selected", "unmounted",
}
_ERROR_CLASSES = {"http_error", "network_error", "schema_error", "aborted", "unknown"}
_RESPONSE_KEYS = {
    "video_id", "title", "match_id", "source_sha256", "duration_ms", "width", "height",
    "fps", "rights_status", "rights_confirmed", "source_note", "availability_status",
    "hash_status", "file_size",
}


def diagnostics_enabled() -> bool:
    return os.environ.get("PTTI_PLAYBACK_DIAGNOSTICS") == "1"


def _diagnostic_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is None:
        _LOG_PATH = Path(tempfile.gettempdir()) / (
            f"ptti-playback-diagnostics-{os.getpid()}-{time.time_ns()}.jsonl"
        )
    return _LOG_PATH


def _append(event: str, **fields) -> bool:
    """Append only allowlisted scalar metadata; never accept request or media text."""
    global _EVENT_COUNT
    if not diagnostics_enabled() or _EVENT_COUNT >= _EVENT_LIMIT:
        return False
    payload = {"event": event, "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    payload.update(fields)
    line = (json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")
    with _LOCK:
        if _EVENT_COUNT >= _EVENT_LIMIT:
            return False
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
        fd = os.open(_diagnostic_path(), flags, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        _EVENT_COUNT += 1
    return True


def _loopback_header(value: str | None, *, origin: bool = False) -> tuple[str, int | None, str]:
    if not value:
        return "missing", None, "missing"
    try:
        from urllib.parse import urlsplit

        parsed = urlsplit(value if origin else "//" + value)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except ValueError:
        return "invalid", None, "invalid"
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return "non_loopback", None, "non_loopback"
    return "loopback", port, host


def _safe_scheme(value: str | None) -> str:
    if not value:
        return "missing"
    try:
        from urllib.parse import urlsplit

        scheme = urlsplit(value).scheme
    except ValueError:
        return "other"
    return scheme if scheme in {"http", "https"} else "other"


def request_metadata(request, *, reason: str | None = None, status: int | None = None) -> dict:
    """Return safe request metadata; raw Origin, Host, IP and query are never retained."""
    host_class, host_port, host_name = _loopback_header(request.headers.get("host"))
    origin_value = request.headers.get("origin")
    origin_class, origin_port, origin_name = _loopback_header(origin_value, origin=True)
    if origin_class == "loopback":
        from urllib.parse import urlsplit

        parsed = urlsplit(origin_value)
        origin_class = (
            "same_origin_loopback"
            if (parsed.scheme, parsed.netloc) == (request.url.scheme, request.url.netloc)
            else "mismatch"
        )
    client_host = request.client.host if request.client else None
    client_class = "loopback" if client_host in {"127.0.0.1", "::1", "testclient"} else "non_loopback"
    values = {
        "route": "vision_sources" if request.url.path == "/api/video-evidence/videos" else "vision_media",
        "path": "/api/video-evidence/videos" if request.url.path == "/api/video-evidence/videos" else "/api/video-evidence/videos/{video_id}/media",
        "url_scheme": request.url.scheme if request.url.scheme in {"http", "https"} else "other",
        "url_host": (request.url.hostname or "").casefold() if (request.url.hostname or "").casefold() in {"127.0.0.1", "localhost", "::1"} else "non_loopback",
        "url_port": request.url.port,
        "method": request.method if request.method in {"GET", "HEAD"} else "other",
        "host_class": host_class,
        "host_name": host_name,
        "host_port": host_port,
        "origin_class": origin_class,
        "origin_scheme": _safe_scheme(origin_value),
        "origin_name": origin_name,
        "origin_port": origin_port,
        "client_class": client_class,
    }
    if reason is not None:
        values["reason"] = reason
    if status is not None:
        values["status"] = status
    return values


def record_backend_request(request, *, status: int, reason: str | None = None, **shape) -> bool:
    allowed = {"response_type", "row_count", "available_count", "eligible_count",
               "game_1_present", "response_keys", "rights_counts", "media_type"}
    if set(shape) - allowed or type(status) is not int or not 100 <= status <= 599:
        return False
    if reason is not None and reason not in {
        "non_loopback_host", "non_loopback_client", "origin_mismatch", "production_mode",
        "http_error", "server_exception",
    }:
        return False
    for key in ("row_count", "available_count", "eligible_count"):
        value = shape.get(key)
        if value is not None and (type(value) is not int or not 0 <= value <= 10000):
            return False
    if "game_1_present" in shape and type(shape["game_1_present"]) is not bool:
        return False
    if "response_type" in shape and shape["response_type"] != "array":
        return False
    if "media_type" in shape and shape["media_type"] not in {
        "video/mp4", "video/quicktime", "video/x-matroska", "video/x-msvideo",
        "application/octet-stream", "other",
    }:
        return False
    if "response_keys" in shape and (
        not isinstance(shape["response_keys"], list)
        or len(shape["response_keys"]) > len(_RESPONSE_KEYS)
        or any(key not in _RESPONSE_KEYS for key in shape["response_keys"])
    ):
        return False
    rights_counts = shape.get("rights_counts")
    if rights_counts is not None and (
        not isinstance(rights_counts, dict)
        or set(rights_counts) - {"LICENSED_FOR_ANALYSIS", "RESEARCH_NONCOMMERCIAL"}
        or any(type(value) is not int or not 0 <= value <= 10000 for value in rights_counts.values())
    ):
        return False
    recorded = _append(
        "vision_http", **request_metadata(request, reason=reason, status=status), **shape
    )
    try:
        request.state.playback_diagnostic_recorded = True
    except AttributeError:
        pass
    return recorded


def record_server_started(port: int, database_location: str) -> bool:
    if database_location not in {"os_temp_qa", "ptti_dev"}:
        return False
    return _append("desktop_server_started", port=int(port), database_location=database_location)


def record_qa_database_rejected() -> bool:
    return _append("qa_database_rejected", reason="outside_os_temp")


def record_ui_state(payload) -> bool:
    """Persist only the fixed Vision state fields; reject all free-form values."""
    if not isinstance(payload, dict) or not isinstance(payload.get("state"), str) or payload["state"] not in _UI_STATES:
        return False
    allowed = {
        "state", "http_status", "row_count", "eligible_count", "game_1_present",
        "error_class", "playback_rate",
    }
    if set(payload) - allowed:
        return False
    state = payload["state"]
    http_status = payload.get("http_status")
    row_count = payload.get("row_count")
    eligible_count = payload.get("eligible_count")
    game_1_present = payload.get("game_1_present")
    error_class = payload.get("error_class")
    playback_rate = payload.get("playback_rate")
    if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
        return False
    for count in (row_count, eligible_count):
        if count is not None and (type(count) is not int or not 0 <= count <= 10000):
            return False
    if game_1_present is not None and type(game_1_present) is not bool:
        return False
    if error_class is not None and (not isinstance(error_class, str) or error_class not in _ERROR_CLASSES):
        return False
    if state == "ready" and (row_count is None or eligible_count is None or game_1_present is None):
        return False
    if state == "error" and error_class is None:
        return False
    if state == "rate_selected" and (
        type(playback_rate) not in {int, float} or playback_rate not in {0.25, 0.5, 1, 2}
    ):
        return False
    if state != "rate_selected" and playback_rate is not None:
        return False
    return _append(
        "vision_ui_state", state=state, http_status=http_status,
        row_count=row_count, eligible_count=eligible_count,
        game_1_present=game_1_present, error_class=error_class,
        playback_rate=playback_rate,
    )


def record_source_response(request, rows: list[dict]) -> bool:
    rights_counts: dict[str, int] = {}
    available_count = 0
    eligible = []
    for row in rows:
        rights = row.get("rights_status")
        if rights in {"LICENSED_FOR_ANALYSIS", "RESEARCH_NONCOMMERCIAL"}:
            rights_counts[rights] = rights_counts.get(rights, 0) + 1
            eligible.append(row)
        if row.get("availability_status") == "AVAILABLE":
            available_count += 1
    return record_backend_request(
        request,
        status=200,
        response_type="array",
        row_count=len(rows),
        available_count=available_count,
        eligible_count=len(eligible),
        game_1_present=any(
            row.get("match_id") == "game_1"
            or (isinstance(row.get("title"), str) and "game_1" in row["title"].casefold())
            for row in eligible
        ),
        response_keys=sorted({key for row in rows for key in row if key in _RESPONSE_KEYS}),
        rights_counts=rights_counts,
    )


def record_media_response(request, *, status: int, media_type: str | None = None) -> bool:
    safe_type = media_type if media_type in {"video/mp4", "video/quicktime", "video/x-matroska", "video/x-msvideo", "application/octet-stream"} else "other"
    return record_backend_request(request, status=status, media_type=safe_type)
