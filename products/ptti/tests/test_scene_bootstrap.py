import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.scene_bootstrap import DetectionCandidate, apply_review, attach_roles
from backend.scene_bootstrap import MODEL_ID, MODEL_REVISION, MODEL_SHA256, PROMPT_PROFILES
from backend.scene_bootstrap import table_box_quality, frame_review_priority, assign_near_far_candidates, temporal_player_presence
from backend.vision_v2 import KeyframeSampler, SceneBoundaryDetector


def test_detection_schema_and_cautious_spatial_roles():
    item = DetectionCandidate(
        candidate_id="f1-d0", frame=1, timestamp_ms=42, label="person",
        bbox=(1, 2, 10, 20), detector_score=0.8, prompt="person.",
    )
    assert item.to_dict()["detector_score"] == 0.8
    assert item.to_dict()["status"] == "SUGGESTED"
    assert item.to_dict()["source"] == "extended_openttgames"
    assert item.to_dict()["model"] == MODEL_ID
    assert len(MODEL_REVISION) == 40 and len(MODEL_SHA256) == 64
    assert "table tennis table" in PROMPT_PROFILES["bootstrap-a"]
    assert attach_roles([item.to_dict()])[0]["role"] == "UNKNOWN"
    assert attach_roles([item.to_dict()], (0, 5, 12, 15))[0]["role"] == "UNKNOWN"
    table = (100, 40, 300, 150)
    left = {**item.to_dict(), "bbox": (110, 10, 130, 35)}
    right = {**item.to_dict(), "bbox": (280, 10, 300, 35)}
    assert attach_roles([left], table)[0]["spatial_hint"] == "PLAYER_LEFT_CANDIDATE"
    assert attach_roles([right], table)[0]["spatial_hint"] == "PLAYER_RIGHT_CANDIDATE"


def test_new_scene_preview_executable_fails_closed_to_development():
    from apps.desktop import is_development_preview
    assert is_development_preview("PTTI-Vision-Lab-v2-Scene-Preview.exe")
    assert is_development_preview("PTTI-Scene-Bootstrap-Preview-v2.exe")
    assert not is_development_preview("PTTI.exe")


def test_table_box_quality_reports_iou_overshoot_and_center_error():
    metrics = table_box_quality((0, 0, 12, 12), (2, 2, 10, 10), image_size=(20, 20))
    assert metrics["iou"] == 64 / 144
    assert metrics["width_overshoot_fraction"] == 0.5
    assert metrics["height_overshoot_fraction"] == 0.5
    assert metrics["center_deviation_px"] == 0


def test_review_priority_and_likely_ok_are_conservative():
    candidates = [
        {"label": "table tennis table", "bbox": [100, 100, 300, 250], "detector_score": .8,
         "spatial_hint": "TABLE_CANDIDATE", "visualization_suppressed": False},
        {"label": "person", "bbox": [20, 10, 70, 200], "detector_score": .8,
         "spatial_hint": "PLAYER_LEFT_CANDIDATE"},
        {"label": "person", "bbox": [320, 10, 370, 200], "detector_score": .8,
         "spatial_hint": "PLAYER_RIGHT_CANDIDATE"},
    ]
    result = frame_review_priority(candidates, image_size=(400, 300))
    assert result["priority"] == "LOW"
    assert result["status"] == "LIKELY_OK"
    result = frame_review_priority(candidates[:2], image_size=(400, 300))
    assert result["priority"] == "HIGH"
    assert result["status"] == "REVIEW_REQUIRED"


def test_near_far_are_spatial_candidates_not_player_identity():
    table = (100, 100, 300, 240)
    people = [
        {"label": "person", "bbox": [10, 20, 60, 150], "spatial_hint": "PLAYER_LEFT_CANDIDATE"},
        {"label": "person", "bbox": [340, 80, 390, 260], "spatial_hint": "PLAYER_RIGHT_CANDIDATE"},
    ]
    assigned = assign_near_far_candidates(people, table)
    assert [x["role_candidate"] for x in assigned] == ["FAR_PLAYER_CANDIDATE", "NEAR_PLAYER_CANDIDATE"]
    assert all(x["role"] == "UNKNOWN" for x in assigned)


def test_temporal_player_presence_marks_gap_without_synthesizing_box():
    frames = [
        {"frame": 0, "timestamp_ms": 0, "detections": [{"spatial_hint": "PLAYER_RIGHT_CANDIDATE", "bbox": [1, 2, 3, 4]}]},
        {"frame": 10, "timestamp_ms": 100, "detections": []},
        {"frame": 20, "timestamp_ms": 200, "detections": [{"spatial_hint": "PLAYER_RIGHT_CANDIDATE", "bbox": [2, 3, 4, 5]}]},
    ]
    result = temporal_player_presence(frames)
    assert result[1]["temporal_player_presence"]["PLAYER_RIGHT_CANDIDATE"] == "TEMPORARILY_MISSING"
    assert result[1]["detections"] == []
    sparse = [{**row, "timestamp_ms": row["timestamp_ms"] * 200} for row in frames]
    sparse_result = temporal_player_presence(sparse)
    assert sparse_result[1]["temporal_player_presence"]["PLAYER_RIGHT_CANDIDATE"] == "NOT_OBSERVED"


def test_scene_cut_candidate_is_reused_by_keyframe_sampler():
    detector = SceneBoundaryDetector(threshold=0.5, minimum_gap_frames=1)
    dark = [[[0, 0, 0] for _ in range(8)] for _ in range(8)]
    bright = [[[255, 255, 255] for _ in range(8)] for _ in range(8)]
    detector.observe(0, 0, dark)
    cut = detector.observe(25, 1000, bright)
    assert cut is not None
    frames = KeyframeSampler(10).sample(100, 25, scene_cut_frames=[cut.frame])
    candidate = next(x for x in frames if x.frame == cut.frame)
    assert "SCENE_CHANGE" in candidate.reasons
    assert candidate.timestamp_ms == cut.timestamp_ms


def test_user_review_is_a_projection_and_never_mutates_raw_evidence():
    raw = [{"candidate_id": "d1", "role": "UNKNOWN", "bbox": [0, 0, 5, 5]}]
    projected = apply_review(raw, [{"candidate_id": "d1", "action": "SET_ROLE", "role": "REFEREE"}])
    assert raw[0] == {"candidate_id": "d1", "role": "UNKNOWN", "bbox": [0, 0, 5, 5]}
    assert projected[0]["user_correction"] == {"role": "REFEREE", "status": "CORRECTED"}


def test_scene_bootstrap_api_serves_only_dev_results_and_persists_corrections(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    db = tmp_path / "PTTI-Dev" / "qa" / "matches.db"
    app = create_app(db)
    root = tmp_path / "PTTI-Dev" / "vision-v2" / "scene-bootstrap"
    (root / "frames").mkdir(parents=True)
    (root / "scene_bootstrap_overlay").mkdir(parents=True)
    raw = [{"candidate_id": "f1-d0", "frame": 1, "timestamp_ms": 1000,
            "label": "person", "bbox": [1, 2, 10, 20], "detector_score": 0.8,
            "role": "UNKNOWN", "spatial_hint": "HUMAN_CANDIDATE"}]
    payload = {"status": "RESEARCH_CANDIDATES_READY", "detections": raw,
               "keyframes": [{"frame": 1, "image": "frame-000001.jpg",
                              "overlay": "overlay-frame-000001.jpg", "detections": raw}]}
    (root / "scene_bootstrap.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "scene_bootstrap_eval_manifest.json").write_text(json.dumps({
        "status": "MULTI_MATCH_RESEARCH_EVALUATION", "dataset": "Extended OpenTTGames",
        "license": "CC BY-NC-SA 4.0", "official_split": "training only",
        "games": [{"game": "game_1"}], "prompt_summary": {"official_bootstrap_a": {"per_game": {}}},
        "frame_results": [{"prompt_id": "official_bootstrap_a", "game": "game_1", "slot": 1,
                           "timestamp_seconds": 1, "image": "multi-match-frames/game_1/sample-01.jpg",
                           "overlay_asset": "game_1-overlay-sample-01.jpg", "width": 400, "height": 300,
                           "table_found": True, "both_player_candidates": True,
                           "selected_table_bbox": [100, 100, 300, 250],
                           "detections": [{"candidate_id": "game_1-s01-d0", "label": "person",
                                           "bbox": [10, 10, 60, 100], "detector_score": .8,
                                           "spatial_hint": "PLAYER_LEFT_CANDIDATE", "role": "UNKNOWN"}]}],
    }), encoding="utf-8")
    (root / "frames" / "frame-000001.jpg").write_bytes(b"image")
    (root / "scene_bootstrap_overlay" / "overlay-frame-000001.jpg").write_bytes(b"overlay")
    (root / "multi-match-frames" / "game_1").mkdir(parents=True)
    (root / "multi-match-frames" / "game_1" / "sample-01.jpg").write_bytes(b"sample")
    (root / "multi-match-frames" / "game_1" / "overlay-sample-01.jpg").write_bytes(b"overlay sample")

    with TestClient(app) as client:
        assert client.get("/api/vision/v2/scene-bootstrap/assets/frame-000001.jpg").content == b"image"
        assert client.get("/api/vision/v2/scene-bootstrap/assets/overlay-frame-000001.jpg").content == b"overlay"
        assert client.get("/api/vision/v2/scene-bootstrap/assets/game_1-sample-01.jpg").content == b"sample"
        assert client.get("/api/vision/v2/scene-bootstrap/assets/..%2fscene_bootstrap.json").status_code == 404
        changed = client.post("/api/vision/v2/scene-bootstrap/reviews", json={
            "candidate_id": "f1-d0", "action": "SET_ROLE", "role": "PLAYER_A"})
        assert changed.status_code == 200 and changed.json()["raw_preserved"] is True
        reviewed = client.get("/api/vision/v2/scene-bootstrap").json()
        assert reviewed["detections"][0]["user_correction"]["role"] == "PLAYER_A"
        assert reviewed["keyframes"][0]["detections"][0]["user_correction"]["role"] == "PLAYER_A"
        assert reviewed["multi_match_evaluation"]["games"][0]["game"] == "game_1"
        assert reviewed["keyframes"][0]["review"]["priority"] in {"HIGH", "MEDIUM", "LOW"}
        cross_game = reviewed["multi_match_evaluation"]["keyframes"][0]
        assert cross_game["image_asset"] == "game_1-sample-01.jpg"
        changed_cross_game = client.post("/api/vision/v2/scene-bootstrap/reviews", json={
            "candidate_id": "game_1-s01-d0", "action": "SET_ROLE", "role": "NEAR_PLAYER"})
        assert changed_cross_game.status_code == 200 and changed_cross_game.json()["raw_preserved"] is True
        assert client.get("/api/vision/v2/scene-bootstrap/assets/game_1-overlay-sample-01.jpg").content == b"overlay sample"
        reviewed_cross_game = client.get("/api/vision/v2/scene-bootstrap").json()
        assert reviewed_cross_game["multi_match_evaluation"]["keyframes"][0]["detections"][0]["user_correction"]["role"] == "NEAR_PLAYER"
        assert client.post("/api/vision/v2/scene-bootstrap/reviews", json={
            "candidate_id": "f1-d0", "action": "REJECT"}).status_code == 200
        rejected = client.get("/api/vision/v2/scene-bootstrap").json()
        assert rejected["detections"][0]["user_correction"]["status"] == "REJECTED"
        assert client.post("/api/vision/v2/scene-bootstrap/reviews", json={
            "candidate_id": "missing", "action": "REJECT"}).status_code == 404

    stored = json.loads((root / "scene_bootstrap.json").read_text(encoding="utf-8"))
    assert "user_correction" not in stored["detections"][0]
    reviews = json.loads((root / "reviews.json").read_text(encoding="utf-8"))
    assert reviews[0]["role"] == "PLAYER_A" and reviews[1]["action"] == "REJECT"
    assert all("recorded_at" in entry for entry in reviews)


def test_scene_bootstrap_absent_state_is_truthful_and_noncommercial(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = create_app(tmp_path / "isolated" / "matches.db")
    with TestClient(app) as client:
        response = client.get("/api/vision/v2/scene-bootstrap")
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_RUN"
    assert response.json()["commercial_use"] is False
    assert response.json()["keyframes"] == []

