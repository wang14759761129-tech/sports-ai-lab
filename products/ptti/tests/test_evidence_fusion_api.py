import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import evidence_fusion_api
from backend.player_motion import player_motion_job_root
from backend.player_motion_api import router as player_motion_router


JOB_ID = "a" * 32
VIDEO_SHA = "b" * 64


def make_client(tmp_path, monkeypatch, split="TRAIN"):
    local = tmp_path / "local"
    local.mkdir()
    monkeypatch.setattr(evidence_fusion_api, "_localappdata", lambda: local)
    monkeypatch.setattr(evidence_fusion_api, "load_tracking_evidence",
                        lambda job_id, root: ({"job_id": job_id, "source_sha256": VIDEO_SHA},
                                              local / "source.mp4"))
    motion_root = player_motion_job_root(JOB_ID, local)
    motion_root.mkdir(parents=True)
    (motion_root / "player_motion.json").write_text(json.dumps({
        "sample_id": "game_2-t60", "official_split": split, "source_sha256": VIDEO_SHA,
    }), encoding="utf-8")

    run = local / "PTTI-Dev" / "vision-v2-evidence-fusion" / "evaluation" / "dev" / "run-1"
    sample = run / "game_2-t60"
    sample.mkdir(parents=True)
    (sample / "clip_manifest.json").write_text(json.dumps({
        "sample_id": "game_2-t60", "official_split": "TRAIN", "video_sha256": VIDEO_SHA,
        "tracking_job_id": JOB_ID,
        "timeline_audit": {"first_timestamp_ms": 60_000, "processing_frames": 300,
                           "processing_fps": 30},
    }), encoding="utf-8")
    (sample / "hit_candidates.json").write_text(json.dumps([{
        "event_id": "raw-1", "event_type": "HIT", "status": "SUGGESTED", "frame": 3,
        "processing_frame": 3, "source_frame": 7212, "timestamp_ms": 60_100,
        "candidate_player": "NEAR_PLAYER", "confidence": None, "evidence_score": .72,
        "evidence_level": "FULL_EVIDENCE", "evidence_components": {"wrist_proximity_proxy": {
            "value": .8, "evidence": "racket-side proxy"}}, "source_modules": ["RACKETVISION_RAW"],
        "sequence_index": 1, "interval_from_previous_ms": None,
    }]), encoding="utf-8")
    (sample / "frame_evidence.jsonl").write_text(json.dumps({
        "processing_frame": 3, "timestamp_ms": 60_100,
        "ball": {"visible": True, "x": 12, "y": 14},
    }) + "\n", encoding="utf-8")
    (run / "hit_event_evaluation.json").write_text(json.dumps({
        "aggregate": {"by_tolerance": {"pm3": {"f1": .5}}},
    }), encoding="utf-8")

    app = FastAPI()
    app.include_router(player_motion_router(), prefix="/api/vision")
    return TestClient(app), local, sample


def test_hit_event_review_is_local_append_only_and_keeps_raw_candidate(tmp_path, monkeypatch):
    client, local, sample = make_client(tmp_path, monkeypatch)
    url = f"/api/vision/v2/player-motion/jobs/{JOB_ID}/hit-events"

    before = (sample / "hit_candidates.json").read_text(encoding="utf-8")
    response = client.get(url)
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "dev"
    assert body["clip_start_timestamp_ms"] == 60_000
    assert body["events"][0]["raw_status"] == "SUGGESTED"
    assert body["events"][0]["frame"] == 3
    assert body["ball_observations"] == [{"frame": 3, "timestamp_ms": 60_100,
                                          "visible": True, "x": 12, "y": 14}]
    assert body["research_metrics"]["by_tolerance"]["pm3"]["f1"] == .5

    confirmed = client.post(url + "/reviews", json={
        "action": "CONFIRM", "event_id": "raw-1", "timestamp_ms": 60_100,
        "player": "NEAR_PLAYER",
    })
    adjusted = client.post(url + "/reviews", json={
        "action": "ADJUST", "event_id": "raw-1", "timestamp_ms": 60_133.333,
        "player": "FAR_PLAYER",
    })
    added = client.post(url + "/reviews", json={
        "action": "ADD", "timestamp_ms": 60_200, "player": "FAR_PLAYER",
    })
    assert [confirmed.status_code, adjusted.status_code, added.status_code] == [200, 200, 200]
    assert confirmed.json()["raw_candidate_modified"] is False
    assert (sample / "hit_candidates.json").read_text(encoding="utf-8") == before

    after = client.get(url).json()
    raw_event = next(row for row in after["events"] if row["event_id"] == "raw-1")
    added_event = next(row for row in after["events"] if row["status"] == "USER_ADDED")
    assert raw_event["status"] == "SUGGESTED"
    assert raw_event["review"]["action"] == "ADJUST"
    assert raw_event["review"]["player"] == "FAR_PLAYER"
    assert added_event["review"]["action"] == "ADD"
    correction_file = local / "PTTI-Dev" / "vision-v2-evidence-fusion" / "reviews" / f"{VIDEO_SHA}.jsonl"
    assert len(correction_file.read_text(encoding="utf-8").splitlines()) == 3
    assert after["policy"] == {"official_test_split": "NOT_ACCESSED",
                               "production_database": "NOT_ACCESSED",
                               "raw_candidates_preserved": True}


def test_hit_event_review_fails_closed_for_non_train_motion(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch, split="TEST")
    response = client.get(f"/api/vision/v2/player-motion/jobs/{JOB_ID}/hit-events")
    assert response.status_code == 404
    assert "TRAIN" in response.json()["detail"]
