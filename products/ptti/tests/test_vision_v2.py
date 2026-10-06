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
        "scene-classifier": ModuleAvailability(dependencies=True, checkpoint=False),
        "co-tracker": ModuleAvailability(dependencies=True, checkpoint=True),
    }
    result = {item.id: item for item in VisionModuleManager(availability).snapshot()}

    assert result["balltrack"].state == ModuleState.READY
    assert result["grounding-dino"].state == ModuleState.NOT_INSTALLED
    assert result["scene-classifier"].state == ModuleState.AVAILABLE
    assert result["co-tracker"].state == ModuleState.DISABLED

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


def color_frame(value):
    return [[[value, value, value] for _ in range(8)] for _ in range(8)]
