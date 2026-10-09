import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def score_client(tmp_path, monkeypatch):
    media = {"duration": 120.0, "fps": 30.0, "width": 640, "height": 360, "codec": "h264"}
    monkeypatch.setattr("backend.video_evidence.video_metadata", lambda _path: media)
    monkeypatch.setattr("backend.match_library.video_metadata", lambda _path: media)
    root = tmp_path / "score QA"
    root.mkdir()
    client = TestClient(create_app(tmp_path / "score-qa.db"))
    videos = []
    for n in (1, 2):
        source = root / f"match {n}.mp4"
        source.write_bytes(f"ISOLATED SCORE QA VIDEO {n}".encode())
        response = client.post("/api/video-evidence/videos", json={
            "path": str(source), "title": f"QA match {n}", "match_id": None,
            "rights_status": "USER_OWNED", "rights_confirmed": True,
            "source_note": "隔离工程测试，不是比赛结论"})
        assert response.status_code == 200, response.text
        video = response.json()
        for _ in range(200):
            video = next(v for v in client.get("/api/video-evidence/videos").json()
                         if v["video_id"] == video["video_id"])
            if video["hash_status"] == "VERIFIED":
                break
            time.sleep(.01)
        assert video["hash_status"] == "VERIFIED"
        videos.append((video, source))
    yield client, videos, tmp_path
    client.close()


def body(video, **changes):
    return {"video_asset_id": video["video_id"], "game_number": 1, "point_number": 1,
            "score_a_before": 9, "score_b_before": 9, "point_start_ms": 10000,
            "point_end_ms": 12000, "score_display_ms": 11000,
            "point_winner_id": "UNKNOWN", "server_id": "UNKNOWN",
            "player_a_id": "UNKNOWN", "player_b_id": "UNKNOWN",
            "verification_status": "CONFIRMED", "request_id": "qa-create-1", **changes}


def test_score_create_search_and_idempotency(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    payload = body(video)
    first = client.post("/api/video-evidence/scores", json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/video-evidence/scores", json=payload)
    assert second.json()["point_id"] == first.json()["point_id"]
    assert first.json()["video_sha256"] == video["source_sha256"]
    assert first.json()["provenance"]["score_semantics"] == "BEFORE_POINT"
    assert first.json()["point_winner_id"] == "UNKNOWN"
    assert client.get("/api/video-evidence/scores?video_id=" + video["video_id"] + "&score_a=9&score_b=9").json()[0]["flags"]["deuce"] is False
    changed = {**payload, "point_end_ms": 13000}
    assert client.post("/api/video-evidence/scores", json=changed).status_code == 409
    assert client.get(f"/api/video-evidence/scores/export?format=json&video_id={video['video_id']}").status_code == 200
    assert "比分复盘索引" in client.get(f"/api/video-evidence/scores/export?format=html&video_id={video['video_id']}").text
    assert client.get(f"/api/video-evidence/scores/export?format=csv&video_id={video['video_id']}").text.startswith("\ufeff")


@pytest.mark.parametrize("a,b,expected", [(9, 9, (False, False)), (10, 9, (True, False)),
                                           (9, 10, (False, True)), (10, 10, (False, False))])
def test_game_point_rules(score_client, a, b, expected):
    client, videos, _ = score_client
    video = videos[0][0]
    payload = body(video, score_a_before=a, score_b_before=b,
                   request_id=f"rule-{a}-{b}", point_number=a + b + 1)
    result = client.post("/api/video-evidence/scores", json=payload)
    assert result.status_code == 200, result.text
    flags = result.json()["flags"]
    assert (flags["game_point_a"], flags["game_point_b"]) == expected


def test_match_point_requires_known_match_format(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    known = body(video, score_a_before=10, score_b_before=9, games_a_before=2,
                 games_b_before=1, match_best_of=5, request_id="match-point-known")
    row = client.post("/api/video-evidence/scores", json=known).json()
    assert row["flags"]["match_point_a"] is True
    assert len(client.get("/api/video-evidence/scores?critical=MATCH_POINT").json()) == 1
    unknown = body(video, score_a_before=10, score_b_before=9, point_number=2,
                   request_id="match-point-unknown")
    row = client.post("/api/video-evidence/scores", json=unknown).json()
    assert row["flags"]["match_point"] == "UNKNOWN"


def test_confirm_requires_both_bounds_and_score(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    draft = body(video, verification_status="REVIEW_REQUIRED", point_end_ms=None,
                 request_id="incomplete-draft")
    row = client.post("/api/video-evidence/scores", json=draft)
    assert row.status_code == 200, row.text
    bad_confirm = {**draft, "request_id": "bad-confirm", "verification_status": "CONFIRMED"}
    assert client.post("/api/video-evidence/scores", json=bad_confirm).status_code == 400
    assert client.delete(f"/api/video-evidence/scores/{row.json()['point_id']}").json() == {"deleted": True}


def test_search_mixes_confirmed_and_unbounded_drafts(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    draft = body(video, point_number=1, verification_status="REVIEW_REQUIRED",
                 point_start_ms=None, point_end_ms=None, request_id="unbounded-draft")
    confirmed = body(video, point_number=2, point_start_ms=20000, point_end_ms=22000,
                     request_id="bounded-confirmed")
    assert client.post("/api/video-evidence/scores", json=draft).status_code == 200
    assert client.post("/api/video-evidence/scores", json=confirmed).status_code == 200

    result = client.get("/api/video-evidence/scores?video_id=" + video["video_id"])

    assert result.status_code == 200, result.text
    rows = result.json()
    assert len(rows) == 2
    assert {row["verification_status"] for row in rows} == {"REVIEW_REQUIRED", "CONFIRMED"}


def test_edit_history_undo_and_draft_delete_protection(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    created = client.post("/api/video-evidence/scores", json=body(video)).json()
    edit = body(video, score_a_before=10, request_id="edit-one",
                expected_updated_at=created["updated_at"])
    changed = client.put(f"/api/video-evidence/scores/{created['point_id']}", json=edit)
    assert changed.status_code == 200, changed.text
    history = client.get(f"/api/video-evidence/scores/{created['point_id']}/history").json()
    assert len(history) == 2
    restored = client.post(f"/api/video-evidence/scores/{created['point_id']}/undo", json={}).json()
    assert restored["score_a_before"] == 9
    assert len(client.get(f"/api/video-evidence/scores/{created['point_id']}/history").json()) == 4
    assert client.delete(f"/api/video-evidence/scores/{created['point_id']}").status_code == 409


def test_legacy_point_endpoint_cannot_overwrite_score_moment(score_client):
    client, videos, _ = score_client
    video = videos[0][0]
    created = client.post("/api/video-evidence/scores", json=body(video)).json()
    legacy = {"video_id": video["video_id"], "game_number": 1, "score_a": 0, "score_b": 0,
              "start_ms": 10000, "end_ms": 12000, "tags": [], "evidence_ids": [], "notes": ""}
    result = client.put(f"/api/video-evidence/points/{created['point_id']}", json=legacy)
    assert result.status_code == 400
    current = client.get("/api/video-evidence/scores?video_id=" + video["video_id"]).json()[0]
    assert current["score_a_before"] == 9


def test_cross_video_playlist_is_ordered_and_idempotent(score_client):
    client, videos, _ = score_client
    ids = []
    for index, (video, _path) in enumerate(videos):
        row = client.post("/api/video-evidence/scores", json=body(
            video, point_number=index + 1, point_start_ms=20000 + index * 10000,
            point_end_ms=22000 + index * 10000, request_id=f"playlist-{index}")).json()
        ids.append(row["point_id"])
    first = client.post("/api/video-evidence/scores/playlist", json=ids).json()
    second = client.post("/api/video-evidence/scores/playlist", json=ids).json()
    assert first == second
    clips = client.get("/api/video-evidence/evidence").json()
    score_clips = [next(c for c in clips if c["evidence_id"] == identity) for identity in first["evidence_ids"]]
    assert [c["video_id"] for c in score_clips] == [v[0]["video_id"] for v in videos]


def test_changed_video_identity_rejected(score_client):
    client, videos, _ = score_client
    video, path = videos[0]
    path.write_bytes(path.read_bytes() + b"changed")
    result = client.post("/api/video-evidence/scores", json=body(video))
    assert result.status_code == 400
    assert "不可用" in result.json()["detail"]
