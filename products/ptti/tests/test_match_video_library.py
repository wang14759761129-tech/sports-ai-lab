"""Synthetic media bytes exercise engineering contracts, not vision accuracy."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.match_library import VideoSourceProvider


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    media = {"duration": 10.0, "fps": 30.0, "width": 640, "height": 360, "codec": "h264"}
    monkeypatch.setattr("backend.match_library.video_metadata", lambda _path: media)
    monkeypatch.setattr("backend.video_evidence.video_metadata", lambda _path: media)
    root = tmp_path / "中文 视频 folder"
    root.mkdir()
    (root / "王楚钦 Felix LEBRUN.mp4").write_bytes(b"ENGINEERING_QA_SYNTHETIC_ONLY")
    (root / "do-not-read.db").write_bytes(b"NOT_A_VIDEO")
    with TestClient(create_app(tmp_path / "library.db")) as client:
        yield client, root, tmp_path


def scan(client, root):
    result = client.post("/api/video-evidence/library/folders", json={
        "path": str(root), "rights_status": "RESEARCH_NONCOMMERCIAL",
        "rights_confirmed": True, "source_note": "仅合成工程测试"})
    assert result.status_code == 200, result.text
    identity = result.json()["scan_id"]
    for _ in range(100):
        row = next(r for r in client.get("/api/video-evidence/library/folders").json() if r["scan_id"] == identity)
        if row["status"] not in {"RUNNING", "QUEUED"}:
            return row
        time.sleep(.01)
    pytest.fail("index worker did not finish")


def test_catalog_preserves_real_metadata_and_does_not_invent_media(workspace):
    client, _root, _tmp = workspace
    result = client.get("/api/video-evidence/library").json()
    assert len(result["athletes"]) == 16
    assert result["summary"] == {"matches": 6, "playable_professional": 0, "local_playable": 0}
    assert all(m["video_source"]["status"] == "SOURCE_LINK_ONLY" for m in result["matches"])
    assert all(not m["video_source"]["frame_access"] for m in result["matches"])


def test_folder_candidates_do_not_auto_bind_filename(workspace):
    client, root, _tmp = workspace
    row = scan(client, root)
    assert row["status"] == "COMPLETED" and len(row["candidates"]) == 1
    item = row["candidates"][0]
    assert item["suggested_match_ids"] and item["status"] == "REVIEW_REQUIRED"
    assert client.get("/api/video-evidence/videos").json() == []
    assert (root / "do-not-read.db").read_bytes() == b"NOT_A_VIDEO"


def test_confirm_is_idempotent_and_mapping_requires_explicit_review(workspace):
    client, root, _tmp = workspace
    row = scan(client, root)
    body = {"candidate_id": row["candidates"][0]["candidate_id"]}
    url = f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm'
    first = client.post(url, json=body).json()
    second = client.post(url, json=body).json()
    assert first["video_id"] == second["video_id"]
    assert first["match_id"] is None and first["athlete_ids"] == []
    mapping = f'/api/video-evidence/library/videos/{first["video_id"]}/match'
    mid = row["candidates"][0]["suggested_match_ids"][0]
    assert client.put(mapping, json={"match_id": mid, "user_confirmed": False}).status_code == 400
    assert client.put(mapping, json={"match_id": mid, "user_confirmed": True}).status_code == 200
    assert client.put(mapping, json={"match_id": mid, "user_confirmed": True}).status_code == 200
    linked = client.get("/api/video-evidence/library").json()
    assert linked["summary"]["playable_professional"] == 1
    other = next(m["match_id"] for m in linked["matches"] if m["match_id"] != mid)
    assert client.put(mapping, json={"match_id": other, "user_confirmed": True}).status_code == 400


def test_changed_source_cannot_be_confirmed(workspace):
    client, root, _tmp = workspace
    row = scan(client, root)
    item = row["candidates"][0]
    Path(item["path"]).write_bytes(b"CHANGED_SOURCE")
    assert client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm',
                       json={"candidate_id": item["candidate_id"]}).status_code == 400
    assert client.get("/api/video-evidence/videos").json() == []


def test_repeated_scan_detects_registered_and_moved_media(workspace):
    client, root, _tmp = workspace
    row = scan(client, root)
    video = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm',
                       json={"candidate_id": row["candidates"][0]["candidate_id"]}).json()
    for _ in range(100):
        if client.get("/api/video-evidence/videos").json()[0]["hash_status"] == "VERIFIED":
            break
        time.sleep(.01)
    Path(video["original_path"]).rename(root / "已移动.mp4")
    second = scan(client, root)
    assert second["candidates"][0]["existing_video_id"] == video["video_id"]
    restored = client.post(f'/api/video-evidence/library/folders/{second["scan_id"]}/confirm',
                           json={"candidate_id": second["candidates"][0]["candidate_id"]}).json()
    assert restored["video_id"] == video["video_id"]
    assert len(client.get("/api/video-evidence/videos").json()) == 1


def test_research_holdout_and_test_media_excluded(workspace):
    client, _root, tmp = workspace
    root = tmp / "ExtendedOpenTTGames"
    root.mkdir()
    (root / "game_5.mp4").write_bytes(b"DO_NOT_READ")
    (root / "test_1.mp4").write_bytes(b"DO_NOT_READ")
    assert scan(client, root)["candidates"] == []


def test_permissions_and_network_share_fail_closed(workspace):
    client, root, _tmp = workspace
    for changes in ({"rights_confirmed": False}, {"path": r"\\server\share"}, {"source_note": " "}):
        body = {"path": str(root), "rights_confirmed": True, "rights_status": "LICENSED", "source_note": "许可"}
        assert client.post("/api/video-evidence/library/folders", json={**body, **changes}).status_code == 400


def test_remote_urls_never_claim_media_rights():
    for url in ("https://www.worldtabletennis.com/", "javascript:alert(1)", "file:///private"):
        source = VideoSourceProvider.describe({"match_id": "m", "external_reference_url": url}, [])
        assert source["status"] != "LOCAL_READY" and not source["embedding_verified"]
        assert not source["frame_access"]
        if not url.startswith("https:"):
            assert source["official_url"] is None


def test_recent_views_survive_application_restart_without_mutating_evidence(workspace):
    client, root, tmp = workspace
    row = scan(client, root)
    video = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm',
                       json={"candidate_id": row["candidates"][0]["candidate_id"]}).json()
    assert client.post(f'/api/video-evidence/library/videos/{video["video_id"]}/opened').status_code == 200
    with TestClient(create_app(tmp / "library.db")) as restarted:
        catalog = restarted.get("/api/video-evidence/library").json()
        assert catalog["videos"][0]["last_opened_at"]
        assert catalog["videos"][0]["match_id"] is None
        assert restarted.post('/api/video-evidence/library/videos/unknown/opened').status_code == 404


def test_official_catalog_does_not_claim_analysis_rights_or_playback(workspace):
    client, _, _ = workspace
    rows = client.get("/api/video-evidence/library").json()["official_videos"]
    assert len(rows) == 8
    assert len({r["video_id"] for r in rows}) == 8
    for row in rows:
        assert row["playback_status"] in {"EMBED_NOT_TESTED", "EMBED_BLOCKED"}
        assert row["watch_page_status"] in {"NOT_TESTED", "LOGIN_REQUIRED", "PLAYBACK_VERIFIED"}
        assert row["full_match"] is True
        assert row["embeddable_api"] is None
        assert row["local_analysis_allowed"] is False
        assert row["rights"] == "REFERENCE_ONLY_NOT_LICENSE_GRANTED"
        assert row["video_source"]["is_full_match"] is None
        assert row["video_source"]["playback_verified"] is (row["watch_page_status"] == "PLAYBACK_VERIFIED")
        assert row["duration_seconds"] is None or row["duration_seconds"] > 0
        assert row["provenance"]["metadata_method"] == "YOUTUBE_OEMBED"


def test_thumbnail_missing_video_and_missing_tool_fail_safely(workspace, monkeypatch):
    client, root, tmp = workspace
    assert client.get("/api/video-evidence/library/videos/missing/thumbnail").status_code == 404
    row = scan(client, root)
    video = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm',
        json={"candidate_id": row["candidates"][0]["candidate_id"]}).json()
    for _ in range(100):
        if client.get("/api/video-evidence/videos").json()[0]["source_sha256"]:
            break
        time.sleep(.01)
    monkeypatch.setattr("backend.match_library.tempfile.gettempdir", lambda: str(tmp))
    monkeypatch.setattr("backend.match_library.shutil.which", lambda _: None)
    assert client.get(f'/api/video-evidence/library/videos/{video["video_id"]}/thumbnail').status_code == 503
    assert client.get("/api/video-evidence/library").json()["summary"]["local_playable"] == 1


def test_thumbnail_is_atomic_cached_and_single_frame(workspace, monkeypatch):
    client, root, tmp = workspace
    row = scan(client, root)
    video = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm',
        json={"candidate_id": row["candidates"][0]["candidate_id"]}).json()
    for _ in range(100):
        if client.get("/api/video-evidence/videos").json()[0]["source_sha256"]:
            break
        time.sleep(.01)
    calls = []
    import subprocess
    original_run = subprocess.run
    def run(command, **kwargs):
        if command[0] != "test-ffmpeg":
            return original_run(command, **kwargs)
        calls.append(command)
        assert command[command.index("-frames:v") + 1] == "1"
        assert kwargs["timeout"] == 15
        Path(command[-1]).write_bytes(b"SYNTHETIC_THUMBNAIL_TEST_ONLY")
    monkeypatch.setattr("backend.match_library.tempfile.gettempdir", lambda: str(tmp))
    monkeypatch.setattr("backend.match_library.shutil.which", lambda _: "test-ffmpeg")
    monkeypatch.setattr("backend.match_library.subprocess.run", run)
    url = f'/api/video-evidence/library/videos/{video["video_id"]}/thumbnail'
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 200
    assert len(calls) == 1
    assert not list((tmp / "PTTI-Video-First-Thumbnails").glob("*.part.jpg"))


def test_feed_favorite_idempotence_and_restart(workspace):
    client, _, tmp = workspace
    endpoint = "/api/video-evidence/library/feed/favorite"
    payload = {"key": "official:aFs7HJ0NX18", "saved": True}
    assert client.put(endpoint, json=payload).status_code == 200
    assert client.put(endpoint, json=payload).json()["favorites"] == [payload["key"]]
    assert client.put(endpoint, json={"key": "official:invented", "saved": True}).status_code == 404
    with TestClient(create_app(tmp / "library.db")) as restarted:
        assert restarted.get("/api/video-evidence/library").json()["feed_favorites"] == [payload["key"]]
        assert restarted.put(endpoint, json={**payload, "saved": False}).json()["favorites"] == []


def test_known_embed_failure_keeps_platform_constraints_separate(workspace):
    client, _, _ = workspace
    rows = client.get("/api/video-evidence/library").json()["official_videos"]
    blocked = [r for r in rows if r["playback_status"] == "EMBED_BLOCKED"]
    assert len(blocked) == 2
    for row in blocked:
        assert row["native_playback_test"]["error_code"] == 150
        assert row["native_playback_test"]["error_class"] == "EMBEDDING_DISALLOWED"
        assert row["region_restrictions_api"] is None
        assert row["local_analysis_allowed"] is False
