from apps.desktop import configure_dual_source_preview, is_development_preview
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

def test_score_navigation_preview_uses_one_build_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PTTI_SCORE_NAV_PREVIEW", "1")
    monkeypatch.setenv("PTTI_PREVIEW_PRODUCT_NAME", "PTTI 比分导航")
    monkeypatch.setenv("PTTI_PREVIEW_VERSION", "0.1")
    monkeypatch.setenv("PTTI_PREVIEW_BUILD_ID", "abc123def0")
    monkeypatch.setenv("PTTI_PREVIEW_COMMIT", "abc123def01234567890")
    with TestClient(create_app(tmp_path / "qa.db")) as client:
        health=client.get("/api/health").json()
    assert health["score_navigation_preview"] is True
    assert health["product_name"] == "PTTI 比分导航"
    assert health["version"] == "0.1"
    assert health["build_id"] == "abc123def0"
    assert health["build_commit"] == "abc123def01234567890"


def test_video_first_preview_is_development_only():
    assert is_development_preview("PTTI-Video-First-v0.5-Preview.exe")
    assert not is_development_preview("PTTI-Video-First.exe")


def test_video_feed_preview_identity_and_isolation(tmp_path, monkeypatch):
    assert is_development_preview("PTTI-Video-First-v0.5.1-Preview.exe")
    monkeypatch.setenv("PTTI_VIDEO_FEED_PREVIEW", "1")
    monkeypatch.setenv("PTTI_MATCH_LIBRARY_PREVIEW", "1")
    with TestClient(create_app(tmp_path / "qa.db")) as client:
        assert client.get("/api/health").json()["video_feed"] is True


def test_dual_source_preview_is_registered_and_uses_dedicated_dev_database(tmp_path, monkeypatch):
    assert is_development_preview("PTTI-Dual-Source-v0.6.1-Preview.exe")
    preview_env = {"PTTI_DB": "C:/PTTI/matches.db", "PTTI_SCORE_NAV_PREVIEW": "1"}
    configure_dual_source_preview(tmp_path, preview_env)
    assert preview_env["PTTI_ENV"] == "development"
    assert preview_env["PTTI_DB"] == str(
        tmp_path / "PTTI-Dev" / "DualSource-v061-Preview" / "matches.db"
    )
    assert preview_env["PTTI_SCORE_NAV_PREVIEW"] == "0"
    assert preview_env["PTTI_MATCH_LIBRARY_PREVIEW"] == "1"
    assert preview_env["PTTI_VIDEO_FEED_PREVIEW"] == "1"


def test_dual_source_health_exposes_single_build_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("PTTI_DUAL_SOURCE_PREVIEW", "1")
    monkeypatch.setenv("PTTI_MATCH_LIBRARY_PREVIEW", "1")
    monkeypatch.setenv("PTTI_VIDEO_FEED_PREVIEW", "1")
    monkeypatch.setenv("PTTI_PREVIEW_PRODUCT_NAME", "PTTI 双来源比赛观看")
    monkeypatch.setenv("PTTI_PREVIEW_VERSION", "0.6.1")
    monkeypatch.setenv("PTTI_PREVIEW_BUILD_ID", "abc123def0")
    monkeypatch.setenv("PTTI_PREVIEW_COMMIT", "abc123def01234567890")
    with TestClient(create_app(tmp_path / "qa.db")) as client:
        health = client.get("/api/health").json()
    assert health["dual_source_preview"] is True
    assert health["video_feed"] is True
    assert health["video_first"] is True
    assert health["start_page"] == "home"
    assert health["product_name"] == "PTTI 双来源比赛观看"
    assert health["version"] == "0.6.1"
    assert health["build_id"] == "abc123def0"
    assert health["build_commit"] == "abc123def01234567890"
