from backend.vision_v2 import (
    KeyframeSampler,
    ModuleAvailability,
    ModuleState,
    SceneBoundaryDetector,
    VisionModuleManager,
)


def test_keyframe_sampler_combines_periodic_scene_and_recovery_reasons():
    frames = KeyframeSampler(interval_seconds=5).sample(
        frame_count=251,
        fps=25,
        scene_cut_frames=[124],
        tracking_failure_frames=[126],
        requested_frames=[20],
    )

    assert frames[0].frame == 0 and "VIDEO_START" in frames[0].reasons
    at_five_seconds = next(item for item in frames if item.frame == 125)
    assert "PERIODIC" in at_five_seconds.reasons
    assert next(item for item in frames if item.frame == 124).reasons == ("SCENE_CHANGE",)
    recovery = next(item for item in frames if item.frame == 126)
    assert "TRACKER_FAILURE" in recovery.reasons
    assert recovery.timestamp_ms == 5040
    assert frames[-1].frame == 250 and "VIDEO_END" in frames[-1].reasons


def test_scene_boundary_detector_returns_suggestion_with_measured_evidence():
    detector = SceneBoundaryDetector(threshold=0.5, minimum_gap_frames=1)
    first = color_frame(0)
    second = color_frame(255)

    assert detector.observe(0, 0, first) is None
    candidate = detector.observe(25, 1000, second)

    assert candidate is not None
    assert candidate.frame == 25 and candidate.timestamp_ms == 1000
    assert candidate.status == "SUGGESTED"
    assert candidate.evidence[0].type == "HISTOGRAM_CHANGE"
    assert candidate.evidence[0].value == 1.0


def test_scene_boundary_detector_obeys_minimum_gap_after_suggestion():
    detector = SceneBoundaryDetector(threshold=0.5, minimum_gap_frames=10)
    black = color_frame(0)
    white = color_frame(255)
    detector.observe(0, 0, black)

    candidate = detector.observe(5, 200, white)
    assert candidate is not None
    assert detector.observe(10, 400, black) is None
    assert detector.observe(15, 600, white) is not None


def test_module_manager_distinguishes_ready_missing_failed_and_disabled():
    availability = {
        "balltrack": ModuleAvailability(dependencies=True, checkpoint=True),
        "scene-detector": ModuleAvailability(dependencies=True, checkpoint=True),
        "grounding-dino": ModuleAvailability(dependencies=False, checkpoint=False),
        "video-segmenter": ModuleAvailability(dependencies=False, checkpoint=False),
        "player-pose": ModuleAvailability(dependencies=False, checkpoint=False),
        "scoreboard-ocr": ModuleAvailability(dependencies=False, checkpoint=False),
        "grounding-dino-person": ModuleAvailability(dependencies=True, checkpoint=True),
        "rtmdet-person": ModuleAvailability(dependencies=False, checkpoint=False),
        "scoreboard-module": ModuleAvailability(dependencies=False, checkpoint=False),
        "scene-classifier": ModuleAvailability(dependencies=True, checkpoint=False),
        "co-tracker": ModuleAvailability(dependencies=True, checkpoint=True),
    }
    result = {item.id: item for item in VisionModuleManager(availability).snapshot()}

    assert result["balltrack"].state == ModuleState.READY
    assert result["grounding-dino"].state == ModuleState.NOT_INSTALLED
    assert result["scene-classifier"].state == ModuleState.AVAILABLE
    assert result["co-tracker"].state == ModuleState.DISABLED
    assert result["grounding-dino-person"].product_status == "RESEARCH_ONLY"
    assert result["rtmdet-person"].state == ModuleState.NOT_INSTALLED
    assert result["scoreboard-module"].product_status == "NOT_IMPLEMENTED"

    not_connected = VisionModuleManager({
        "scene-detector": ModuleAvailability(dependencies=True, integrated=False),
    }).snapshot()
    scene = next(item for item in not_connected if item.id == "scene-detector")
    assert scene.state == ModuleState.AVAILABLE
    assert "尚未接入" in scene.message

    failed = {"scene-detector": "video decode failed"}
    result = {
        item.id: item
        for item in VisionModuleManager(availability, failed=failed).snapshot()
    }
    assert result["scene-detector"].state == ModuleState.FAILED
    assert result["scene-detector"].message == "video decode failed"


def test_timestamps_and_frame_count_are_validated():
    sampler = KeyframeSampler(interval_seconds=10)
    assert sampler.sample(0, 25) == []
    try:
        sampler.sample(10, 0)
    except ValueError as error:
        assert "fps" in str(error)
    else:
        raise AssertionError("zero FPS must be rejected")


def test_v2_module_status_api_uses_worker_evidence_and_keeps_test_db_isolated(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import backend.vision_api as vision_api
    from backend.main import create_app

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "isolated-localappdata"))

    monkeypatch.setattr(vision_api, "doctor", lambda config: {
        "checkpoint": True,
        "racketvision_commit": "pinned",
        "worker": {"torch": "2.x", "modules": {"cv2": True}},
    })
    app = create_app(tmp_path / "vision-v2.sqlite")
    with TestClient(app) as client:
        result = client.get("/api/vision/v2/modules")
    assert result.status_code == 200
    modules = {item["id"]: item for item in result.json()["modules"]}
    assert modules["balltrack"]["state"] == "READY"
    assert modules["scene-detector"]["state"] == "AVAILABLE"
    assert "尚未接入" in modules["scene-detector"]["message"]
    assert modules["grounding-dino"]["state"] == "NOT_INSTALLED"
    assert result.json()["policy"]["production_database"] == "NOT_ACCESSED"
    modules = {item["id"]: item for item in result.json()["modules"]}
    assert modules["rtmdet-person"]["state"] == "NOT_INSTALLED"
    assert modules["scoreboard-module"]["product_status"] == "NOT_IMPLEMENTED"


def test_scene_api_exposes_frozen_person_baseline_and_separate_unrun_rtmdet(tmp_path, monkeypatch):
    import hashlib
    import json
    from fastapi.testclient import TestClient
    from backend.main import create_app

    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    root = local / "PTTI-Dev" / "vision-v2" / "scene-bootstrap"
    root.mkdir(parents=True)
    baseline = {
        "status": "MULTI_MATCH_RESEARCH_EVALUATION",
        "dataset": "Extended OpenTTGames",
        "license": "CC BY-NC-SA 4.0",
        "official_split": "training only; test split not accessed",
        "games": [],
        "prompt_summary": {
            "official_bootstrap_a": {
                "sampled_frames": 20,
                "both_player_candidate_frames": 11,
                "both_player_candidate_coverage_percent": 55.0,
                "per_game": {},
            }
        },
        "frame_results": [],
    }
    manifest_path = root / "scene_bootstrap_eval_manifest.json"
    manifest_path.write_text(json.dumps(baseline), encoding="utf-8")
    (root / "scene_bootstrap.json").write_text(
        json.dumps({"status": "RESEARCH_CANDIDATES_READY", "detections": [], "keyframes": []}),
        encoding="utf-8",
    )
    app = create_app(tmp_path / "qa.sqlite")
    with TestClient(app) as client:
        result = client.get("/api/vision/v2/scene-bootstrap").json()
        modules = {item["id"]: item for item in client.get("/api/vision/v2/modules").json()["modules"]}
    gdino = result["hybrid_scene"]["person_detectors"]["grounding_dino"]
    assert gdino["baseline_id"] == "GROUNDING_DINO_PLAYER_BASELINE"
    assert gdino["both_player_candidate_frames"] == 11
    assert gdino["candidate_coverage_percent"] == 55.0
    assert gdino["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert result["hybrid_scene"]["person_detectors"]["rtmdet"]["status"] == "NOT_RUN_RUNTIME_NOT_INSTALLED"
    assert result["hybrid_scene"]["scoreboard"]["status"] == "NOT_IMPLEMENTED"
    assert modules["rtmdet-person"]["state"] == "NOT_INSTALLED"
    assert modules["scoreboard-module"]["product_status"] == "NOT_IMPLEMENTED"


def test_scene_detector_status_uses_completed_scene_run_as_integration_evidence(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import backend.vision_api as vision_api
    from backend.main import create_app

    local = tmp_path / "isolated-localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(vision_api, "doctor", lambda config: {
        "worker": {"modules": {"cv2": False}},
    })
    scene_results = local / "PTTI-Dev" / "vision-v2" / "scene-bootstrap"
    scene_results.mkdir(parents=True)
    (scene_results / "scene_bootstrap.json").write_text('{"status":"RESEARCH_CANDIDATES_READY"}', encoding="utf-8")
    app = create_app(tmp_path / "isolated-test.sqlite")
    with TestClient(app) as client:
        result = client.get("/api/vision/v2/modules")
    scene = next(item for item in result.json()["modules"] if item["id"] == "scene-detector")
    assert scene["state"] == "READY"


def color_frame(value):
    return [[[value, value, value] for _ in range(8)] for _ in range(8)]
