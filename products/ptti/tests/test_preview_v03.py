from apps.desktop import is_development_preview
from backend.main import create_app
from fastapi.testclient import TestClient

def test_v03_preview_allowlist():
    assert is_development_preview("PTTI-Video-Evidence-v0.3-Preview.exe")
    assert not is_development_preview("PTTI.exe")
    assert not is_development_preview("untrusted-preview.exe")

def test_preview_health_reports_build_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PTTI_PREVIEW_VERSION", "0.3-video-evidence-preview")
    monkeypatch.setenv("PTTI_PREVIEW_COMMIT", "verified-commit")
    monkeypatch.setenv("PTTI_EVIDENCE_PREVIEW", "1")
    with TestClient(create_app(tmp_path / "qa.db")) as client:
        health=client.get("/api/health").json()
        assert health["version"] == "0.3-video-evidence-preview"
        assert health["build_commit"] == "verified-commit"
        assert health["start_page"] == "videoEvidence"

def test_v04_video_first_home_and_isolated_executable(tmp_path, monkeypatch):
    assert is_development_preview("PTTI-Match-Library-v0.4-Preview.exe")
    monkeypatch.setenv("PTTI_MATCH_LIBRARY_PREVIEW", "1")
    monkeypatch.setenv("PTTI_EVIDENCE_PREVIEW", "1")
    with TestClient(create_app(tmp_path / "qa.db")) as client:
        health=client.get("/api/health").json()
        assert health["start_page"] == "home" and health["video_first"]
