import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import player_motion_api
from backend.player_motion import player_motion_job_root


def test_exclude_motion_window_is_append_only_and_recomputes_only_effective_metrics(tmp_path, monkeypatch):
    job_id = "a" * 32
    monkeypatch.setattr(player_motion_api, "_local", lambda: tmp_path)
    result = {
        "schema_version": "player-motion-v0.1", "status": "COMPLETE",
        "source_sha256": "b" * 64,
        "video": {"frame_count": 60},
        "records": [
            {"frame": frame, "timestamp_ms": frame * 33, "player_role": "NEAR_PLAYER",
             "track_quality": "POSE_READY", "identity_continuous": True,
             "pose_quality": "GOOD", "keypoints": {
                 "left_shoulder": {"x_global": 10 + frame, "y_global": 10, "score": .9},
                 "right_shoulder": {"x_global": 20 + frame, "y_global": 10, "score": .9},
             }} for frame in (0, 1)
        ],
    }
    root = player_motion_job_root(job_id, tmp_path)
    root.mkdir(parents=True)
    (root / "player_motion.json").write_text(json.dumps(result), encoding="utf-8")
    app = FastAPI()
    app.include_router(player_motion_api.router(), prefix="/api/vision")
    client = TestClient(app)

    saved = client.post(f"/api/vision/v2/player-motion/jobs/{job_id}/exclusions",
                        json={"start_frame": 0, "end_frame": 1, "role": "NEAR_PLAYER"})
    assert saved.status_code == 200
    assert saved.json()["production_database"] == "NOT_ACCESSED"

    response = client.get(f"/api/vision/v2/player-motion/jobs/{job_id}/result")
    assert response.status_code == 200
    body = response.json()
    assert len(body["records"]) == 2
    assert len(body["user_exclusions"]) == 1
    assert body["effective_metrics_after_user_exclusions"]["NEAR_PLAYER"]["status"] == "INSUFFICIENT_CONTINUOUS_IDENTITY"


def test_source_serves_local_browser_compatible_copy_after_verifying_original(tmp_path, monkeypatch):
    job_id = "c" * 32
    monkeypatch.setattr(player_motion_api, "_local", lambda: tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"verified-original")
    root = player_motion_job_root(job_id, tmp_path)
    root.mkdir(parents=True)
    preview = root / "player_motion_source_preview.mp4"
    preview.write_bytes(b"browser-compatible-copy")
    monkeypatch.setattr(player_motion_api, "load_tracking_evidence",
                        lambda requested, local: ({"job_id": requested}, source))
    app = FastAPI()
    app.include_router(player_motion_api.router(), prefix="/api/vision")
    response = TestClient(app).get(f"/api/vision/v2/player-motion/jobs/{job_id}/source")
    assert response.status_code == 200
    assert response.content == b"browser-compatible-copy"
    assert response.headers["content-type"].startswith("video/mp4")
