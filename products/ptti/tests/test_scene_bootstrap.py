import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.scene_bootstrap import DetectionCandidate, apply_review, attach_roles
from backend.scene_bootstrap import MODEL_ID, MODEL_REVISION, MODEL_SHA256, PROMPT_PROFILES
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
    (root / "frames" / "frame-000001.jpg").write_bytes(b"image")
    (root / "scene_bootstrap_overlay" / "overlay-frame-000001.jpg").write_bytes(b"overlay")

    with TestClient(app) as client:
        assert client.get("/api/vision/v2/scene-bootstrap/assets/frame-000001.jpg").content == b"image"
        assert client.get("/api/vision/v2/scene-bootstrap/assets/overlay-frame-000001.jpg").content == b"overlay"
        assert client.get("/api/vision/v2/scene-bootstrap/assets/..%2fscene_bootstrap.json").status_code == 404
        changed = client.post("/api/vision/v2/scene-bootstrap/reviews", json={
            "candidate_id": "f1-d0", "action": "SET_ROLE", "role": "PLAYER_A"})
        assert changed.status_code == 200 and changed.json()["raw_preserved"] is True
        reviewed = client.get("/api/vision/v2/scene-bootstrap").json()
        assert reviewed["detections"][0]["user_correction"]["role"] == "PLAYER_A"
        assert reviewed["keyframes"][0]["detections"][0]["user_correction"]["role"] == "PLAYER_A"
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

