import json
from types import SimpleNamespace
from urllib.parse import urlsplit

from backend import playback_diagnostics as diagnostics


class FakeURL:
    def __init__(self, value):
        self._parsed = urlsplit(value)

    @property
    def scheme(self):
        return self._parsed.scheme

    @property
    def netloc(self):
        return self._parsed.netloc

    @property
    def hostname(self):
        return self._parsed.hostname

    @property
    def port(self):
        return self._parsed.port

    @property
    def path(self):
        return self._parsed.path


def reset_log(monkeypatch, tmp_path, enabled="1"):
    monkeypatch.setenv("PTTI_PLAYBACK_DIAGNOSTICS", enabled)
    monkeypatch.setattr(diagnostics, "_LOG_PATH", tmp_path / "native.jsonl")
    monkeypatch.setattr(diagnostics, "_EVENT_COUNT", 0)


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def test_diagnostics_are_opt_in_and_frontend_payload_is_allowlisted(monkeypatch, tmp_path):
    reset_log(monkeypatch, tmp_path, enabled="0")
    assert diagnostics.record_ui_state({"state": "loading"}) is False
    assert not (tmp_path / "native.jsonl").exists()

    monkeypatch.setenv("PTTI_PLAYBACK_DIAGNOSTICS", "1")
    safe = {
        "state": "ready", "http_status": 200, "row_count": 1,
        "eligible_count": 1, "game_1_present": True,
    }
    assert diagnostics.record_ui_state(safe) is True
    assert diagnostics.record_ui_state({**safe, "video_path": r"C:\private\video.mp4"}) is False
    assert diagnostics.record_ui_state({"state": "error", "error_class": r"C:\private\video.mp4"}) is False
    event = read_events(tmp_path / "native.jsonl")[0]
    assert event["event"] == "vision_ui_state"
    assert event["game_1_present"] is True
    assert "video_path" not in event


def test_source_response_logs_shape_and_loopback_ports_without_content(monkeypatch, tmp_path):
    reset_log(monkeypatch, tmp_path)
    request = SimpleNamespace(
        headers={"host": "127.0.0.1:45678", "origin": "http://127.0.0.1:45678"},
        url=FakeURL("http://127.0.0.1:45678/api/video-evidence/videos"),
        client=SimpleNamespace(host="127.0.0.1"),
        method="GET",
    )
    rows = [{
        "video_id": "private-id", "title": "game_1",
        "match_id": "game_1", "rights_status": "RESEARCH_NONCOMMERCIAL",
        "availability_status": "AVAILABLE", "source_sha256": "private-hash",
        "source_note": r"C:\private\video.mp4",
    }]
    assert diagnostics.record_source_response(request, rows) is True
    event = read_events(tmp_path / "native.jsonl")[0]
    assert event["status"] == 200
    assert event["route"] == "vision_sources"
    assert event["path"] == "/api/video-evidence/videos"
    assert event["url_scheme"] == event["origin_scheme"] == "http"
    assert event["url_host"] == event["origin_name"] == "127.0.0.1"
    assert event["url_port"] == event["host_port"] == event["origin_port"] == 45678
    assert event["host_port"] == event["origin_port"] == 45678
    assert event["origin_class"] == "same_origin_loopback"
    assert event["row_count"] == event["eligible_count"] == 1
    assert event["game_1_present"] is True
    serialized = json.dumps(event)
    assert "private-id" not in serialized
    assert "private-hash" not in serialized
    assert "video.mp4" not in serialized
    assert "title" in event["response_keys"]


def test_request_diagnostics_redact_non_loopback_origin(monkeypatch, tmp_path):
    reset_log(monkeypatch, tmp_path)
    request = SimpleNamespace(
        headers={"host": "127.0.0.1:45678", "origin": "https://outside.example/private"},
        url=FakeURL("http://127.0.0.1:45678/api/video-evidence/videos"),
        client=SimpleNamespace(host="127.0.0.1"),
        method="GET",
    )
    assert diagnostics.record_backend_request(request, status=403, reason="origin_mismatch") is True
    event = read_events(tmp_path / "native.jsonl")[0]
    assert event["origin_class"] == "non_loopback"
    assert event["origin_name"] == "non_loopback"
    assert "outside.example" not in json.dumps(event)
    assert "private" not in json.dumps(event)
