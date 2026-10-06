import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.sam2_player_tracking import (
    player_tracking_frame_asset,
    player_tracking_snapshot,
    player_tracking_video_asset,
    record_player_tracking_review,
)


def seed_tracking(root: Path):
    root.mkdir(parents=True)
    records = []
    for frame in range(3):
        for object_id, role in ((1, "NEAR_PLAYER"), (2, "FAR_PLAYER")):
            records.append({
                "frame": frame,
                "timestamp_ms": 30000 + frame * 33,
                "object_id": object_id,
                "role": role,
                "bbox": [10, 10, 20, 30],
                "mask_area": 200,
                "tracking_status": "SEEDED" if frame == 0 else "TRACKED",
                "source": "MANUAL_OPERATOR_EXPERIMENT" if frame == 0 else "SAM2_PROPAGATED",
            })
    value = {
        "status": "REAL_GPU_PROPAGATION_COMPLETE",
        "dataset": "Extended OpenTTGames",
        "rights": "CC BY-NC-SA 4.0 research/non-commercial",
        "source_path": "private-local-path.mp4",
        "source_sha256": "abc123",
        "source_bytes": 100,
        "duration_seconds": 0.1,
        "source_fps": 120,
        "sample_fps": 30,
        "frames": 3,
        "seed_assignment": "MANUAL_OPERATOR_EXPERIMENT",
        "seeds": [
            {"object_id": 1, "role": "NEAR_PLAYER", "bbox": [1, 1, 5, 8]},
            {"object_id": 2, "role": "FAR_PLAYER", "bbox": [20, 1, 25, 8]},
        ],
        "role_summary": {
            "NEAR_PLAYER": {"object_id": 1, "frames": 3, "tracked": 3, "track_lost": 0},
            "FAR_PLAYER": {"object_id": 2, "frames": 3, "tracked": 3, "track_lost": 0},
        },
        "identity_uncertain_events": [],
        "scene_cut_candidates": [],
        "scene_cut_real_video_verified": False,
        "tracker_config_sha256": "locked-config-sha",
        "sam2": {"checkpoint_sha256": "def456"},
        "runtime": {"effective_fps": 4.0, "peak_vram_allocated_bytes": 1024},
        "records": records,
    }
    (root / "tracking.json").write_text(json.dumps(value), encoding="utf-8")
    for name in ("player_tracking_overlay.mp4", "player_tracking_near.mp4",
                 "player_tracking_far.mp4", "player_tracking_original.mp4"):
        (root / name).write_bytes(b"preview")
    for view in ("frames", "overlay-frames"):
        (root / view).mkdir()
        for frame in range(1, 4):
            (root / view / f"{frame:05d}.jpg").write_bytes(b"frame")
    return value


def test_player_tracking_snapshot_keeps_source_and_user_review_separate(tmp_path):
    root = tmp_path / "run"
    raw = seed_tracking(root)

    initial = player_tracking_snapshot(root)
    assert initial["status"] == "REAL_GPU_PROPAGATION_COMPLETE"
    assert initial["commercial_use"] is False
    assert initial["review_status"] == "REVIEW_REQUIRED"
    assert "source_path" not in initial
    assert initial["samples"][0]["source"]["NEAR_PLAYER"] == "MANUAL_OPERATOR_EXPERIMENT"

    saved = record_player_tracking_review(root, action="CONFIRM_ROLE_ASSIGNMENT", note="身份顺序正确")
    after = player_tracking_snapshot(root)
    assert saved["raw_preserved"] is True
    assert after["review_status"] == "USER_REVIEWED"
    assert after["reviews"][0]["source"] == "USER_UI"
    assert json.loads((root / "tracking.json").read_text(encoding="utf-8")) == raw


def test_player_tracking_snapshot_exposes_same_config_cross_match_summary(tmp_path):
    root = tmp_path / "runs" / "game4"
    seed_tracking(root)
    summary = {
        "status": "CROSS_MATCH_LOCKED_CONFIG_COMPLETE",
        "dataset": "Extended OpenTTGames",
        "rights": "CC BY-NC-SA 4.0 research/non-commercial",
        "commercial_use": False,
        "tracker_config_sha256": "locked-config-sha",
        "declared_video_count": 2,
        "propagated_video_count": 1,
        "videos": [{"video_id": "game_4", "status": "PROPAGATED"}],
    }
    (root.parent / "cross_match_validation.json").write_text(json.dumps(summary), encoding="utf-8")

    assert player_tracking_snapshot(root)["multi_match_validation"] == summary

    summary["tracker_config_sha256"] = "different-config"
    (root.parent / "cross_match_validation.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="CROSS_MATCH_CONFIG_MISMATCH"):
        player_tracking_snapshot(root)


def test_player_tracking_snapshot_rejects_cross_match_license_drift(tmp_path):
    root = tmp_path / "runs" / "game4"
    seed_tracking(root)
    summary = {
        "dataset": "Extended OpenTTGames",
        "rights": "unknown",
        "commercial_use": False,
        "tracker_config_sha256": "locked-config-sha",
        "videos": [],
    }
    (root.parent / "cross_match_validation.json").write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="CROSS_MATCH_PROVENANCE_INVALID"):
        player_tracking_snapshot(root)


def test_player_tracking_provenance_and_frame_sequence_fail_closed(tmp_path):
    root = tmp_path / "run"
    seed_tracking(root)
    manifest = json.loads((root / "tracking.json").read_text(encoding="utf-8"))
    manifest["rights"] = "unknown"
    (root / "tracking.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="PROVENANCE_INVALID"):
        player_tracking_snapshot(root)

    manifest["rights"] = "CC BY-NC-SA 4.0 research/non-commercial"
    manifest["records"][-1]["frame"] = 10
    (root / "tracking.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="TIMELINE_INVALID"):
        player_tracking_snapshot(root)


def test_player_tracking_asset_paths_and_review_actions_are_allowlisted(tmp_path):
    root = tmp_path / "run"
    seed_tracking(root)
    with pytest.raises(ValueError, match="INVALID_PLAYER_TRACKING_ASSET"):
        player_tracking_video_asset(root, "../matches.db")
    with pytest.raises(ValueError, match="INVALID_PLAYER_TRACKING_FRAME"):
        player_tracking_frame_asset(root, -1, "source")
    with pytest.raises(ValueError, match="INVALID_PLAYER_TRACKING_REVIEW_ACTION"):
        record_player_tracking_review(root, action="WRITE_DATABASE")


def test_player_tracking_desktop_api_uses_ptti_dev_artifacts_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "PTTI-Dev/vision-v2-sam2/runs/multi-match-final/game_4-t30"
    seed_tracking(root)
    app = create_app(tmp_path / "test-only" / "matches.db")
    with TestClient(app) as client:
        snapshot = client.get("/api/vision/v2/player-tracking")
        assert snapshot.status_code == 200
        assert snapshot.json()["production_database"] == "NOT_ACCESSED"
        assert client.get("/api/vision/v2/player-tracking/assets/player_tracking_near.mp4").status_code == 200
        assert client.get("/api/vision/v2/player-tracking/frames/0/source").status_code == 200
        assert client.get("/api/vision/v2/player-tracking/assets/../matches.db").status_code == 404
        saved = client.post("/api/vision/v2/player-tracking/reviews", json={
            "action": "CONFIRM_ROLE_ASSIGNMENT", "note": "测试复核",
        })
        assert saved.status_code == 200
        assert client.get("/api/vision/v2/player-tracking").json()["review_status"] == "USER_REVIEWED"


def test_vision_modules_report_pinned_sam2_worker_when_artifacts_exist(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    worker = local / "PTTI-Dev/vision-v2-sam2/venv/Scripts/python.exe"
    checkpoint = local / "PTTI-Dev/vision-v2-sam2/checkpoints/sam2.1_hiera_small.pt"
    run = local / "PTTI-Dev/vision-v2-sam2/runs/multi-match-final/game_4-t30"
    worker.parent.mkdir(parents=True)
    worker.write_bytes(b"worker")
    checkpoint.parent.mkdir(parents=True)
    with checkpoint.open("wb") as stream:
        stream.truncate(184416285)
    seed_tracking(run)
    monkeypatch.setattr(vision_api, "doctor", lambda config: {
        "checkpoint": False, "racketvision_commit": None,
        "worker": {"modules": {}},
    })

    app = create_app(tmp_path / "test-only" / "matches.db")
    with TestClient(app) as client:
        result = client.get("/api/vision/v2/modules").json()
    module = next(item for item in result["modules"] if item["id"] == "video-segmenter")
    assert module["state"] == "READY"
    assert module["product_status"] == "EXPERIMENTAL"
    assert "锁定配置已在多段真实研究视频运行" in module["message"]
    assert result["policy"]["production_database"] == "NOT_ACCESSED"
