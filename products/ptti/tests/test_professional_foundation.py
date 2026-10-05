import copy
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.professional import ProfessionalMatchInput
from backend.repository import Repository


def client_for(tmp_path):
    return TestClient(create_app(tmp_path / "professional.sqlite"))


def test_registry_uses_stable_ids_and_keeps_legacy_rank_unknown(tmp_path):
    with client_for(tmp_path) as client:
        players = client.get("/api/players").json()
        ids = [item["athlete"]["athlete_id"] for item in players]
        assert len(ids) == len(set(ids)) == 16
        fan = client.get("/api/players/athlete:legacy:fan-zhendong").json()["athlete"]
        ma = client.get("/api/players/athlete:legacy:ma-long").json()["athlete"]
        assert fan["canonical_name_zh"] == "樊振东" and fan["current_world_rank"] is None
        assert ma["canonical_name_zh"] == "马龙" and ma["current_world_rank"] is None


def test_duplicate_display_names_do_not_merge_athlete_identity(tmp_path):
    from pathlib import Path
    manifest = json.loads((Path(__file__).parents[1] / "data/professional/registry.json").read_text(encoding="utf-8-sig"))
    extra = copy.deepcopy(manifest["athletes"][0])
    extra["athlete_id"] = "athlete:test:duplicate-display-name"
    extra["current_ranking"] = None
    extra["group_codes"] = []
    manifest["athletes"].append(extra)
    manifest["schema_version"] += "-duplicate-name-test"
    repo = Repository(tmp_path / "duplicate.sqlite")
    repo.seed_professional(manifest)
    matches = repo.list_athletes(search="Sora MATSUSHIMA")
    assert len(matches) == 2
    assert len({row["athlete_id"] for row in matches}) == 2


def test_ranking_history_is_append_only_across_weekly_snapshots(tmp_path):
    from pathlib import Path
    db = tmp_path / "rankings.sqlite"
    repo = Repository(db)
    manifest = json.loads((Path(__file__).parents[1] / "data/professional/registry.json").read_text(encoding="utf-8-sig"))
    repo.seed_professional(manifest)
    next_week = copy.deepcopy(manifest)
    next_week["schema_version"] = "professional-foundation-test-week-42"
    next_week["ranking_snapshot"]["ranking_week"] = 42
    next_week["ranking_snapshot"]["ranking_date"] = "2026-10-12"
    next_week["ranking_snapshot"]["source_id"] = "ranking-week-42-test"
    next_week["sources"].append({"source_id": "ranking-week-42-test", "source_url": "https://example.org/ranking", "source_type": "TEST", "retrieved_at": "2026-10-12T00:00:00Z"})
    repo.seed_professional(next_week)
    history = repo.get_rankings("athlete:135996")
    assert [(row["ranking_week"], row["rank"]) for row in history] == [(42, 1), (41, 1)]
    conflicting = copy.deepcopy(manifest)
    conflicting["schema_version"] = "professional-foundation-test-conflicting-week-41"
    conflicting["athletes"][0]["current_ranking"]["rank"] = 2
    with pytest.raises(ValueError, match="immutable and conflicts"):
        repo.seed_professional(conflicting)
    assert [(row["ranking_week"], row["rank"]) for row in repo.get_rankings("athlete:135996")] == [(42, 1), (41, 1)]


def test_new_seed_version_refreshes_profile_provenance_without_resetting_groups(tmp_path):
    from pathlib import Path
    manifest = json.loads((Path(__file__).parents[1] / "data/professional/registry.json").read_text(encoding="utf-8-sig"))
    repo = Repository(tmp_path / "seed-upgrade.sqlite")
    initial = copy.deepcopy(manifest)
    initial["schema_version"] = "seed-upgrade-test-v1"
    repo.seed_professional(initial)
    repo.set_group_members("TTI_PRIORITY", ["athlete:121558"])
    updated = copy.deepcopy(initial)
    updated["schema_version"] = "seed-upgrade-test-v2"
    updated["sources"].append({"source_id": "new-profile-source", "source_url": "https://example.org/profile", "source_type": "TEST", "retrieved_at": "2026-10-06T00:00:00Z"})
    player = next(a for a in updated["athletes"] if a["athlete_id"] == "athlete:121558")
    player["source_ids"].append("new-profile-source")
    repo.seed_professional(updated)
    assert "new-profile-source" in repo.get_athlete("athlete:121558")["source_ids"]
    assert repo.get_group("TTI_PRIORITY")["athlete_ids"] == ["athlete:121558"]
    assert len(repo.get_rankings("athlete:121558")) == 1


def test_older_professional_group_table_migrates_additively(tmp_path):
    db = tmp_path / "older-groups.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE athlete_groups (group_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, description TEXT NOT NULL)")
        connection.execute("INSERT INTO athlete_groups VALUES ('EXISTING', 'Existing', 'Preserve this group')")
    repo = Repository(db)
    with repo.connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(athlete_groups)")}
        existing = connection.execute("SELECT display_name, description, user_edited FROM athlete_groups WHERE group_code='EXISTING'").fetchone()
    assert "user_edited" in columns
    assert existing == ("Existing", "Preserve this group", 0)


def test_profile_api_returns_rank_source_and_match_relations(tmp_path):
    with client_for(tmp_path) as client:
        profile = client.get("/api/players/athlete:135996").json()
        assert profile["athlete"]["current_world_rank"] == 1
        assert profile["athlete"]["ranking_year"] == 2026
        assert profile["athlete"]["ranking_date"] == "2026-10-05"
        assert profile["rankings"][0]["source"]["source_type"] == "OFFICIAL_ITTF_WTT_RANKING_API"
        assert len(profile["matches"]) == 1
        assert profile["matches"][0]["players"]["player_a"]["athlete_id"] == "athlete:121558"
        assert profile["matches"][0]["analysis_status"] == "NOT_ANALYZED"


def test_data_editable_priority_group_and_professional_match_api(tmp_path):
    with client_for(tmp_path) as client:
        members = client.put("/api/player-groups/TTI_PRIORITY/members", json={"athlete_ids": ["athlete:121558", "athlete:123980"]})
        assert members.status_code == 200
        priority = client.get("/api/players?group_code=TTI_PRIORITY").json()
        assert {p["athlete"]["athlete_id"] for p in priority} == {"athlete:121558", "athlete:123980"}
        created = client.post("/api/professional-matches", json={
            "event_name": "Local catalog smoke test", "player_a_id": "athlete:121558", "player_b_id": "athlete:123980",
            "external_reference_url": "https://www.worldtabletennis.com/eventInfo?eventId=3098",
            "video_source_type": "REFERENCE_ONLY", "rights_status": "REFERENCE_ONLY"
        })
        assert created.status_code == 201
        assert created.json()["analysis_status"] == "NOT_ANALYZED"
        assert created.json()["players"]["player_a"]["canonical_name_zh"] == "王楚钦"
        assert client.get("/api/professional-matches?athlete_id=athlete:121558").json()


@pytest.mark.parametrize("payload", [
    {"event_name": "x", "player_a_id": "a", "player_b_id": "a"},
    {"event_name": "x", "player_a_id": "a", "player_b_id": "b", "external_reference_url": "file:///secret.mp4", "video_source_type": "REFERENCE_ONLY", "rights_status": "REFERENCE_ONLY"},
    {"event_name": "x", "player_a_id": "a", "player_b_id": "b", "external_reference_url": "https://example.org/video", "video_local_path": "C:/protected/video.mp4", "video_source_type": "REFERENCE_ONLY", "rights_status": "REFERENCE_ONLY"},
])
def test_professional_match_rejects_invalid_identity_and_unauthorized_video(payload):
    with pytest.raises(Exception):
        ProfessionalMatchInput.model_validate(payload)


def test_authorized_existing_local_file_is_only_video_ready_state(tmp_path):
    video = tmp_path / "owned-match.mp4"
    video.write_bytes(b"test fixture")
    record = ProfessionalMatchInput.model_validate({
        "event_name": "Authorized local fixture", "player_a_id": "a", "player_b_id": "b",
        "video_source_type": "LOCAL_USER_VIDEO", "rights_status": "USER_AUTHORIZED", "video_local_path": str(video)
    }).to_record()
    assert record["analysis_status"] == "VIDEO_READY"
    reference = ProfessionalMatchInput.model_validate({
        "event_name": "Reference only", "player_a_id": "a", "player_b_id": "b",
        "video_source_type": "REFERENCE_ONLY", "rights_status": "REFERENCE_ONLY", "external_reference_url": "https://example.org/match"
    }).to_record()
    assert reference["analysis_status"] == "NOT_ANALYZED"


def test_local_video_registration_requires_rights_and_keeps_video_next_to_isolated_database(tmp_path, monkeypatch):
    import json
    import vision.quality as quality

    monkeypatch.setattr(quality, "video_metadata", lambda path: {
        "width": 1920, "height": 1080, "fps": 50.0, "duration": 7200.0,
        "codec": "h264", "bitrate": 10000000, "frame_count": 360000,
        "aspect_ratio": "16:9", "rate_variable": False,
    })
    database = tmp_path / "qa" / "matches.db"
    metadata = {"event_name": "Local authorized video QA", "player_a_id": "athlete:121558",
                "player_b_id": "athlete:123980", "event_date": "2026-10-06"}
    with client_for(database.parent) as client:
        denied = client.post("/api/professional-matches/local-video",
                             data={"metadata": json.dumps(metadata), "video_source_note": "Owner recorded video", "rights_confirmed": "false"},
                             files={"file": ("match.mp4", b"video", "video/mp4")})
        assert denied.status_code == 422
        assert not (database.parent / "professional-videos").exists()

        missing_source = client.post("/api/professional-matches/local-video",
                                     data={"metadata": json.dumps(metadata), "rights_confirmed": "true"},
                                     files={"file": ("match.mp4", b"video", "video/mp4")})
        assert missing_source.status_code == 422
        assert not (database.parent / "professional-videos").exists()

        response = client.post("/api/professional-matches/local-video",
                               data={"metadata": json.dumps(metadata), "video_source_note": "Owner recorded video", "rights_confirmed": "true"},
                               files={"file": ("match.mp4", b"video", "video/mp4")})
        assert response.status_code == 201, response.text
        record = response.json()
        video = Path(record["video_local_path"])
        assert video.parent == database.parent / "professional-videos"
        assert video.read_bytes() == b"video"
        assert record["analysis_status"] == "VIDEO_READY"
        assert record["rights_status"] == "USER_AUTHORIZED"
        assert record["video_source_note"] == "Owner recorded video"
        assert record["video_metadata"]["quality"]["level"] == "VISION"
        assert record["video_metadata"]["duration"] == 7200.0
        assert len(record["video_metadata"]["sha256"]) == 64


def test_local_video_registration_rejects_unsupported_extension(tmp_path):
    import json
    metadata = {"event_name": "Bad extension", "player_a_id": "athlete:121558",
                "player_b_id": "athlete:123980"}
    with client_for(tmp_path) as client:
        response = client.post("/api/professional-matches/local-video",
                               data={"metadata": json.dumps(metadata), "video_source_note": "Licensed local research copy", "rights_confirmed": "true"},
                               files={"file": ("match.webm", b"video", "video/webm")})
        assert response.status_code == 422
        assert not (tmp_path / "professional-videos").exists()


def test_local_video_registration_runs_real_ffprobe_without_changing_source(tmp_path):
    import hashlib
    import subprocess

    source = tmp_path / "owner-recorded-match.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=size=320x240:rate=25:duration=1", "-c:v", "libx264", "-n", str(source)],
                   check=True)
    original = source.read_bytes()
    metadata = {"event_name": "Real ffprobe QA", "player_a_id": "athlete:121558",
                "player_b_id": "athlete:123980"}
    with client_for(tmp_path / "qa") as client:
        response = client.post("/api/professional-matches/local-video",
                               data={"metadata": json.dumps(metadata),
                                     "video_source_note": "Locally recorded practice match",
                                     "rights_confirmed": "true"},
                               files={"file": (source.name, original, "video/mp4")})
    assert response.status_code == 201, response.text
    record = response.json()
    assert source.read_bytes() == original
    assert record["video_original_filename"] == source.name
    assert record["video_metadata"]["width"] == 320
    assert record["video_metadata"]["height"] == 240
    assert record["video_metadata"]["orientation_degrees"] == 0
    assert record["video_metadata"]["audio_streams"] == []
    assert record["video_metadata"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert record["analysis_status"] == "VIDEO_READY"


def test_authorized_professional_short_clip_is_isolated_and_linked(tmp_path, monkeypatch):
    import vision.quality as quality
    import vision.service as vision_service

    media = {"width": 1280, "height": 720, "fps": 30.0, "duration": 10.0,
             "codec": "h264", "bitrate": 1000, "frame_count": 300,
             "aspect_ratio": "16:9", "rate_variable": False}
    monkeypatch.setattr(quality, "video_metadata", lambda path: media)
    monkeypatch.setattr(vision_service, "video_metadata", lambda path: media)
    def submit(self, *args, **kwargs):
        job = {"id": "job-test", "status": "running", "stage": "queued"}
        kwargs["on_update"](job)
        return job
    monkeypatch.setattr(vision_service.VisionService, "submit", submit)
    database_root = tmp_path / "PTTI-Dev"
    metadata = {"event_name": "Clip linkage QA", "player_a_id": "athlete:121558",
                "player_b_id": "athlete:123980"}
    with client_for(database_root) as client:
        created = client.post("/api/professional-matches/local-video",
                              data={"metadata": json.dumps(metadata), "video_source_note": "Authorized local source",
                                    "rights_confirmed": "true"},
                              files={"file": ("full-match.mp4", b"original-video", "video/mp4")})
        assert created.status_code == 201, created.text
        match_id = created.json()["match_id"]
        denied = client.post(f"/api/vision/professional-matches/{match_id}/balltrack-clip",
                             data={"source_note": "Authorized short clip", "rights_confirmed": "false"},
                             files={"file": ("clip.mp4", b"clip", "video/mp4")})
        assert denied.status_code == 422
        response = client.post(f"/api/vision/professional-matches/{match_id}/balltrack-clip",
                               data={"source_note": "Authorized short clip", "rights_confirmed": "true"},
                               files={"file": ("rally.mp4", b"short-clip", "video/mp4")})
        assert response.status_code == 200, response.text
        assert response.json()["scope"] == "SHORT_CLIP"
        saved = client.get("/api/professional-matches").json()
        record = next(match for match in saved if match["match_id"] == match_id)
        analysis = record["video_analysis"]
        assert analysis["status"] == "running"
        assert analysis["job_id"] == "job-test"
        assert analysis["clip_filename"] == "rally.mp4"
        assert analysis["source_note"] == "Authorized short clip"
        assert Path(analysis["clip_path"]).parent == database_root / "vision" / "user_uploads"
        assert Path(record["video_local_path"]).read_bytes() == b"original-video"


def test_professional_clip_rejects_full_match_before_submission(tmp_path, monkeypatch):
    import vision.quality as quality
    import vision.service as vision_service

    media = {"width": 1920, "height": 1080, "fps": 50.0, "duration": 61.0,
             "codec": "h264", "bitrate": 1000, "frame_count": 3050,
             "aspect_ratio": "16:9", "rate_variable": False}
    monkeypatch.setattr(quality, "video_metadata", lambda path: media)
    monkeypatch.setattr(vision_service, "video_metadata", lambda path: media)
    submitted = []
    monkeypatch.setattr(vision_service.VisionService, "submit", lambda *args, **kwargs: submitted.append(True))
    root = tmp_path / "PTTI-Dev"
    with client_for(root) as client:
        created = client.post("/api/professional-matches/local-video",
                              data={"metadata": json.dumps({"event_name": "Long match", "player_a_id": "athlete:121558",
                                                             "player_b_id": "athlete:123980"}),
                                    "video_source_note": "Authorized source", "rights_confirmed": "true"},
                              files={"file": ("full.mp4", b"original", "video/mp4")})
        match_id = created.json()["match_id"]
        response = client.post(f"/api/vision/professional-matches/{match_id}/balltrack-clip",
                               data={"source_note": "Authorized excerpt", "rights_confirmed": "true"},
                               files={"file": ("long.mp4", b"too-long", "video/mp4")})
        assert response.status_code == 422
        assert not submitted
        assert list((root / "vision" / "user_uploads").iterdir()) == []
