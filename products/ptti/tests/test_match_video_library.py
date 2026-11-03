"""Synthetic media bytes exercise engineering contracts, not vision accuracy."""
import sqlite3
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


def test_match_favorites_use_existing_feed_favorites_table(workspace):
    client, _root, _tmp = workspace
    catalog = client.get("/api/video-evidence/library").json()
    match_id = catalog["matches"][0]["match_id"]
    key = f"match:{match_id}"

    saved = client.put("/api/video-evidence/library/feed/favorite", json={"key": key, "saved": True})
    assert saved.status_code == 200, saved.text
    assert key in saved.json()["favorites"]
    assert key in client.get("/api/video-evidence/library").json()["feed_favorites"]

    removed = client.put("/api/video-evidence/library/feed/favorite", json={"key": key, "saved": False})
    assert removed.status_code == 200, removed.text
    assert key not in removed.json()["favorites"]
    assert client.put("/api/video-evidence/library/feed/favorite", json={
        "key": "match:unknown-match", "saved": True,
    }).status_code == 404


def test_online_sources_share_match_but_not_timeline_or_analysis(workspace):
    client, _root, _tmp = workspace
    match = client.get("/api/video-evidence/library").json()["matches"][0]["match_id"]
    rows = []
    for provider, identity in [("BILIBILI", "BV1Hm4y1g7My"), ("YOUTUBE", "H77vNFk3neg")]:
        body = {"provider": provider, "source_id": identity, "title": "ENGINEERING_QA_MAPPING_ONLY", "user_confirmed_match": True}
        response = client.post(f"/api/video-evidence/library/matches/{match}/online-sources", json=body)
        assert response.status_code == 200, response.text
        row = response.json()
        assert row["video_source"]["match_id"] == match
        assert row["video_source"]["analysis_permission"] == "DENIED"
        assert row["video_source"]["is_full_match"] is None
        assert row["video_source"]["embed_permission"] == "UNKNOWN"
        assert client.post(f"/api/video-evidence/library/matches/{match}/online-sources", json=body).json() == row
        rows.append(row)
    assert rows[0]["video_source"]["provenance"]["timeline_id"] != rows[1]["video_source"]["provenance"]["timeline_id"]
    assert len(client.get("/api/video-evidence/library").json()["matches"][0]["online_sources"]) == 2


def test_online_source_mapping_requires_confirmation_and_valid_id(workspace):
    client, _root, _tmp = workspace
    match = client.get("/api/video-evidence/library").json()["matches"][0]["match_id"]
    url = f"/api/video-evidence/library/matches/{match}/online-sources"
    body = {"provider": "BILIBILI", "source_id": "BV1Hm4y1g7My", "title": "QA", "user_confirmed_match": False}
    assert client.post(url, json=body).status_code == 400
    body.update(user_confirmed_match=True, source_id="https://evil.invalid")
    assert client.post(url, json=body).status_code == 400


def test_online_sources_survive_backend_restart(tmp_path):
    path = tmp_path / "isolated-test.db"
    with TestClient(create_app(path)) as client:
        match = client.get("/api/video-evidence/library").json()["matches"][0]["match_id"]
        url = f"/api/video-evidence/library/matches/{match}/online-sources"
        body = {"provider": "BILIBILI", "source_id": "BV1Qa1234567", "title": "ENGINEERING_QA_ONLY", "user_confirmed_match": True}
        response = client.post(url, json=body)
        assert response.status_code == 200
        original = response.json()
    with TestClient(create_app(path)) as client:
        row = next(m for m in client.get("/api/video-evidence/library").json()["matches"] if m["match_id"] == match)
        assert row["online_sources"] == [original]
        assert client.post(url, json=body).json() == original


def test_folder_candidates_do_not_auto_bind_filename(workspace):
    client, root, _tmp = workspace
    row = scan(client, root)
    assert row["status"] == "COMPLETED" and len(row["candidates"]) == 1
    item = row["candidates"][0]
    assert item["suggested_match_ids"] and item["status"] == "REVIEW_REQUIRED"
    assert client.get("/api/video-evidence/videos").json() == []
    assert (root / "do-not-read.db").read_bytes() == b"NOT_A_VIDEO"


def test_recursive_folder_preview_records_metadata_and_registers_duplicate_once(workspace):
    client, root, _tmp = workspace
    nested = root / "Season 2025" / "Round 2"
    nested.mkdir(parents=True)
    # Same bytes deliberately test duplicate identity only; this is not media playback evidence.
    (nested / "same-content.mkv").write_bytes((root / "王楚钦 Felix LEBRUN.mp4").read_bytes())
    (nested / "notes.txt").write_text("not media", encoding="utf-8")
    row = scan(client, root)
    assert row["status"] == "COMPLETED"
    assert len(row["candidates"]) == 2
    assert {Path(c["relative_path"]) for c in row["candidates"]} == {
        Path("王楚钦 Felix LEBRUN.mp4"), Path("Season 2025") / "Round 2" / "same-content.mkv"
    }
    duplicate = next(c for c in row["candidates"] if c["relative_path"].endswith("same-content.mkv"))
    assert duplicate["duplicate_of_candidate_id"]
    assert client.get("/api/video-evidence/videos").json() == []  # Preview does not import.

    original = next(c for c in row["candidates"] if not c["duplicate_of_candidate_id"])
    response = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm', json={
        "candidate_id": original["candidate_id"], "match_type": "MD", "event_name": "用户填写赛事",
        "event_year": 2025, "player_a": "组合 A", "player_b": "组合 B",
        "content_type": "FULL_MATCH", "rights_status": "PERSONAL_VIEW_ONLY",
        "source_note": "获准个人观看，不允许分析或传播",
    })
    assert response.status_code == 200, response.text
    video = response.json()
    assert video["personal_library"] == {
        "match_type": "MD", "event_name": "用户填写赛事", "event_year": 2025,
        "match_date": None, "player_a": "组合 A", "player_b": "组合 B",
        "content_type": "FULL_MATCH", "completeness_status": "NOT_VERIFIED",
    }
    duplicate_response = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm', json={
        "candidate_id": duplicate["candidate_id"], "rights_status": "PERSONAL_VIEW_ONLY",
        "source_note": "相同内容复用",
    })
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["video_id"] == video["video_id"]
    repeated = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm', json={
        "candidate_id": original["candidate_id"], "match_type": "MD", "rights_status": "PERSONAL_VIEW_ONLY",
        "source_note": "获准个人观看，不允许分析或传播",
    })
    assert repeated.json()["video_id"] == video["video_id"]
    assert len(client.get("/api/video-evidence/videos").json()) == 1


def test_duplicate_cannot_be_registered_before_its_canonical_candidate(workspace):
    client, root, _tmp = workspace
    nested = root / "nested"
    nested.mkdir()
    (nested / "duplicate.mp4").write_bytes((root / "王楚钦 Felix LEBRUN.mp4").read_bytes())
    row = scan(client, root)
    duplicate = next(c for c in row["candidates"] if c["duplicate_of_candidate_id"])
    response = client.post(f'/api/video-evidence/library/folders/{row["scan_id"]}/confirm', json={
        "candidate_id": duplicate["candidate_id"]
    })
    assert response.status_code == 400
    assert "先确认" in response.json()["detail"]
    assert client.get("/api/video-evidence/videos").json() == []


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


@pytest.mark.parametrize("rights_status", ["PERSONAL_VIEW_ONLY", "PENDING_REVIEW", "USER_SELF_CAPTURED", "USER_OWNED", "LICENSED"])
def test_personal_or_unresolved_rights_cannot_start_ai_evidence_import(workspace, rights_status):
    client, root, _tmp = workspace
    response = client.post("/api/video-evidence/videos", json={
        "path": str(root / "王楚钦 Felix LEBRUN.mp4"), "title": "仅权利状态测试",
        "rights_status": rights_status, "rights_confirmed": True,
        "source_note": "合成工程测试；不代表真实比赛授权",
    })
    assert response.status_code == 200, response.text
    video_id = response.json()["video_id"]
    for _ in range(100):
        row = next(v for v in client.get("/api/video-evidence/videos").json() if v["video_id"] == video_id)
        if row["hash_status"] == "VERIFIED":
            break
        time.sleep(.01)
    rejected = client.post("/api/video-evidence/imports", json={
        "video_id": video_id, "path": str(root / "not-read.jsonl")
    })
    assert rejected.status_code == 400
    assert "未包含本机 AI 分析许可" in rejected.json()["detail"]


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
    assert len(rows) == 9
    assert len({r["video_id"] for r in rows}) == 9
    for row in rows:
        if row["provider"] == "BILIBILI":
            assert row["full_match"] is False
            assert row["video_source"]["is_full_match"] is None
            assert row["video_source"]["embed_permission"] == "UNKNOWN"
            assert row["video_source"]["analysis_permission"] == "DENIED"
            assert row["video_source"]["playback_verified"] is True
            assert "登录/试看" in row["playback_limitation"]
            continue
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


def test_story_and_card_favorite_toggles_persist_with_legacy_compatibility(workspace):
    client, _, tmp = workspace
    db_path = tmp / "library.db"
    match_id = "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"
    legacy_key = "official:0QgbtsBWZhk"
    catalog = client.get("/api/video-evidence/library").json()
    assert any(row["match_id"] == match_id for row in catalog["matches"])
    source = next(row for row in catalog["official_videos"] if row["video_id"] == "0QgbtsBWZhk")
    assert source["match_id"] == match_id
    other_match_id = next(row["match_id"] for row in catalog["matches"] if row["match_id"] != match_id)
    other_key = f"match:{other_match_id}"

    # Card save uses the match key; Story cancellation must delete its durable row.
    match_key = f"match:{match_id}"
    saved = client.put("/api/video-evidence/library/feed/favorite", json={"key": match_key, "saved": True})
    assert saved.status_code == 200, saved.text
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (match_key,)).fetchone() == (match_key,)

    story_removed = client.put("/api/video-evidence/library/feed/favorite", json={"key": match_key, "saved": False})
    assert story_removed.status_code == 200, story_removed.text
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (match_key,)).fetchone() is None

    # Story save and the card's subsequent cancellation use the same exact match key.
    story_saved = client.put("/api/video-evidence/library/feed/favorite", json={"key": match_key, "saved": True})
    assert story_saved.status_code == 200, story_saved.text
    card_removed = client.put("/api/video-evidence/library/feed/favorite", json={"key": match_key, "saved": False})
    assert card_removed.status_code == 200, card_removed.text
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (match_key,)).fetchone() is None

    # A legacy source key and canonical match key can coexist; each is deleted only by its exact key.
    with sqlite3.connect(db_path) as db:
        db.executemany("INSERT INTO media_feed_favorites(source_key) VALUES (?)", [(legacy_key,), (match_key,), (other_key,)])
    api_rows = client.get("/api/video-evidence/library").json()["feed_favorites"]
    assert set(api_rows) == {legacy_key, match_key, other_key}
    assert client.put("/api/video-evidence/library/feed/favorite", json={"key": legacy_key, "saved": False}).status_code == 200
    assert client.put("/api/video-evidence/library/feed/favorite", json={"key": match_key, "saved": False}).status_code == 200
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (legacy_key,)).fetchone() is None
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (match_key,)).fetchone() is None
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (other_key,)).fetchone() == (other_key,)

    # Reopening the application against the same explicit QA path must read the committed state.
    with TestClient(create_app(db_path)) as reopened:
        assert reopened.get("/api/video-evidence/library").json()["feed_favorites"] == [other_key]


def test_match_favorite_write_failure_keeps_persisted_state(workspace):
    client, _, tmp = workspace
    match_id = "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"
    favorite_key = f"match:{match_id}"
    endpoint = "/api/video-evidence/library/feed/favorite"
    saved = client.put(endpoint, json={"key": favorite_key, "saved": True})
    assert saved.status_code == 200, saved.text
    with sqlite3.connect(tmp / "library.db") as db:
        db.execute(
            "CREATE TRIGGER reject_goal112_favorite_delete BEFORE DELETE ON media_feed_favorites "
            "BEGIN SELECT RAISE(ABORT, 'QA forced favorite delete failure'); END"
        )
    with TestClient(create_app(tmp / "library.db"), raise_server_exceptions=False) as failing_client:
        failing = failing_client.put(endpoint, json={"key": favorite_key, "saved": False})
        assert failing.status_code == 500
        assert favorite_key in failing_client.get("/api/video-evidence/library").json()["feed_favorites"]
    with sqlite3.connect(tmp / "library.db") as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (favorite_key,)).fetchone() == (favorite_key,)


@pytest.mark.parametrize("timestamp,reason", [("invalid", "INVALID_TIMESTAMP"), (None, "MISSING_TIMESTAMP"),
    ("2099-01-01T00:00:00+00:00", "FUTURE_TIMESTAMP"), ("2000-01-01T00:00:00+00:00", "EXPIRED")])
def test_catalog_withholds_bad_metadata_without_crashing(workspace, monkeypatch, timestamp, reason):
    import json
    client, _, _ = workspace
    original_read = Path.read_text
    source_path = Path(__file__).resolve().parents[1] / "data/professional/official_video_sources.json"
    payload = json.loads(original_read(source_path, encoding="utf-8"))
    target_id = payload["videos"][0]["video_id"]
    payload["videos"][0]["metadata_verified_at"] = timestamp
    monkeypatch.setattr(Path, "read_text", lambda path, *args, **kwargs:
        json.dumps(payload) if path == source_path else original_read(path, *args, **kwargs))
    response = client.get("/api/video-evidence/library")
    assert response.status_code == 200
    data = response.json()
    assert target_id not in [row["video_id"] for row in data["official_videos"]]
    assert data["metadata_review"]["withheld_counts"][reason] == 1


def test_favorite_select_failure_rolls_back_mutation(workspace, monkeypatch):
    from contextlib import contextmanager
    client, _, tmp = workspace
    key = "official:0QgbtsBWZhk"
    endpoint = "/api/video-evidence/library/feed/favorite"
    assert client.put(endpoint, json={"key": key, "saved": True}).status_code == 200
    repository = client.app.state.repository
    connect = repository.connect

    class FailVerificationSelect:
        def __init__(self, db):
            self.db, self.changed = db, False

        def execute(self, sql, *args):
            if self.changed and sql.startswith("SELECT source_key FROM media_feed_favorites"):
                raise sqlite3.OperationalError("QA verification SELECT failure")
            if sql.startswith("DELETE FROM media_feed_favorites"):
                self.changed = True
            return self.db.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.db, name)

    @contextmanager
    def failing_connect():
        with connect() as db:
            yield FailVerificationSelect(db)

    monkeypatch.setattr(repository, "connect", failing_connect)
    with TestClient(client.app, raise_server_exceptions=False) as failing:
        assert failing.put(endpoint, json={"key": key, "saved": False}).status_code == 500
    with sqlite3.connect(tmp / "library.db") as db:
        assert db.execute("SELECT source_key FROM media_feed_favorites WHERE source_key=?", (key,)).fetchone() == (key,)


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
