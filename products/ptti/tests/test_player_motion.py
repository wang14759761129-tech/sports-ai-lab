from backend.player_motion import (
    build_person_crop,
    evaluate_track_window,
    halpe26_observations,
    globalize_keypoints,
    motion_metrics,
    pose_quality_state,
    supports_pose_tracking_manifest,
    list_motion_exclusions,
    record_motion_exclusion,
)
from backend.tracking_validation_workbench import (
    list_tracking_window_reviews,
    record_tracking_window_review,
    workbench_root,
)


def _record(frame, **updates):
    return {
        "frame": frame,
        "role": "NEAR_PLAYER",
        "tracking_status": "ACCEPTED",
        "visibility": "VISIBLE",
        "mask_area": 4000,
        "bbox": [30, 20, 70, 100],
        "decision": "FORWARD_REVERSE_AGREE",
        **updates,
    }


def test_track_quality_gate_accepts_only_complete_trusted_window():
    records = [_record(frame) for frame in range(10)]
    decision = evaluate_track_window(
        records, [], role="NEAR_PLAYER", start_frame=0, end_frame=10,
        frame_size=(100, 120),
    )
    assert decision.status == "POSE_READY"
    assert decision.coverage == 1.0
    assert decision.motion_eligible is True


def test_track_quality_gate_sends_mask_conflict_to_review_and_skips_untrusted_frames():
    records = [_record(frame) for frame in range(10)]
    records[4] = _record(4, tracking_status="REVIEW_REQUIRED", decision="FORWARD_REVERSE_CONFLICT")
    decision = evaluate_track_window(
        records,
        [{"type": "MASK_CONFLICT", "role": "NEAR_PLAYER", "frame": 4,
          "status": "REVIEW_REQUIRED"}],
        role="NEAR_PLAYER", start_frame=0, end_frame=10,
        frame_size=(100, 120),
    )
    assert decision.status == "REVIEW"
    assert decision.motion_eligible is False
    assert "UNRESOLVED_TRACK_EVENT" in decision.reasons


def test_confirmed_out_of_frame_window_returns_no_pose_not_tracking_failure():
    records = [_record(frame, tracking_status="SUPPRESSED_OUT_OF_FRAME",
                       visibility="OUT_OF_FRAME", mask_area=0) for frame in range(10)]
    decision = evaluate_track_window(
        records,
        [{"type": "OUT_OF_FRAME", "role": "NEAR_PLAYER", "frame": 0,
          "status": "CONFIRMED"}],
        role="NEAR_PLAYER", start_frame=0, end_frame=10,
        frame_size=(100, 120),
    )
    assert decision.status == "NO_POSE"
    assert "PLAYER_NOT_VISIBLE" in decision.reasons


def test_confirmed_out_of_frame_evidence_suppresses_otherwise_good_window():
    decision = evaluate_track_window(
        [_record(frame) for frame in range(10)],
        [{"type": "OUT_OF_FRAME", "role": "NEAR_PLAYER", "frame": 4,
          "status": "CONFIRMED"}],
        role="NEAR_PLAYER", start_frame=0, end_frame=10,
        frame_size=(100, 120),
    )
    assert decision.status == "NO_POSE"
    assert decision.motion_eligible is False
    assert "PLAYER_OUT_OF_FRAME" in decision.reasons


def test_person_crop_adds_dynamic_margin_and_clips_to_frame():
    crop = build_person_crop((200, 160), [5, 20, 55, 140], margin_x=0.2, margin_y=0.1)
    assert crop == {"x": 0, "y": 8, "width": 65, "height": 144}


def test_crop_keypoints_map_back_to_original_video_coordinates():
    points = [{"joint": "left_wrist", "x": 12.5, "y": 22.0, "score": 0.9}]
    mapped = globalize_keypoints(points, origin=(100, 50))
    assert mapped == [{"joint": "left_wrist", "x_global": 112.5,
                       "y_global": 72.0, "score": 0.9}]


def test_halpe26_output_preserves_raw_points_and_selects_required_body_joints():
    crop_points = [[float(index), float(index + 1)] for index in range(26)]
    raw, selected = halpe26_observations(crop_points, [.9] * 26, origin=(100, 200))
    assert len(raw) == 26
    assert len(selected) == 13
    wrist = next(item for item in selected if item["joint"] == "left_wrist")
    assert wrist == {"joint": "left_wrist", "x_global": 109.0,
                     "y_global": 210.0, "score": 0.9}


def test_pose_quality_uses_joint_evidence_and_track_quality():
    scores = {joint: 0.8 for joint in ["nose", "left_shoulder", "right_shoulder",
                                      "left_elbow", "right_elbow", "left_hip",
                                      "right_hip", "left_knee"]}
    assert pose_quality_state(scores, track_quality="POSE_READY") == "GOOD"
    assert pose_quality_state(scores, track_quality="REVIEW") == "NO_POSE"
    assert pose_quality_state({"left_wrist": 0.2}, track_quality="POSE_READY") == "LOW_CONFIDENCE"


def test_motion_metrics_are_2d_proxies_and_need_continuous_identity():
    poses = [
        {"frame": 0, "timestamp_ms": 0, "player_role": "NEAR_PLAYER",
         "track_quality": "POSE_READY", "identity_continuous": True, "pose_quality": "GOOD",
         "keypoints": {
             "left_shoulder": {"x_global": 20, "y_global": 20, "score": .9},
             "right_shoulder": {"x_global": 40, "y_global": 20, "score": .9},
             "left_hip": {"x_global": 22, "y_global": 50, "score": .9},
             "right_hip": {"x_global": 38, "y_global": 50, "score": .9},
             "left_ankle": {"x_global": 10, "y_global": 90, "score": .9},
             "right_ankle": {"x_global": 50, "y_global": 90, "score": .9},
             "left_knee": {"x_global": 14, "y_global": 70, "score": .9},
             "right_knee": {"x_global": 46, "y_global": 70, "score": .9},
             "left_wrist": {"x_global": 5, "y_global": 35, "score": .9},
             "right_wrist": {"x_global": 55, "y_global": 35, "score": .9},
         }},
        {"frame": 1, "timestamp_ms": 33, "player_role": "NEAR_PLAYER",
         "track_quality": "POSE_READY", "identity_continuous": True, "pose_quality": "GOOD",
         "keypoints": {
             "left_shoulder": {"x_global": 21, "y_global": 20, "score": .9},
             "right_shoulder": {"x_global": 41, "y_global": 20, "score": .9},
             "left_hip": {"x_global": 23, "y_global": 50, "score": .9},
             "right_hip": {"x_global": 39, "y_global": 50, "score": .9},
             "left_ankle": {"x_global": 11, "y_global": 90, "score": .9},
             "right_ankle": {"x_global": 51, "y_global": 90, "score": .9},
             "left_knee": {"x_global": 15, "y_global": 70, "score": .9},
             "right_knee": {"x_global": 47, "y_global": 70, "score": .9},
             "left_wrist": {"x_global": 6, "y_global": 34, "score": .9},
             "right_wrist": {"x_global": 56, "y_global": 34, "score": .9},
         }},
    ]
    metrics = motion_metrics(poses)
    assert metrics["status"] == "AVAILABLE"
    assert metrics["stance_width_proxy_px"] == 40.0
    assert metrics["lateral_movement_proxy_px"] == 1.0
    assert metrics["wrist_observations"] == 4
    assert metrics["claims"] == "2D estimates; not biomechanical conclusions"

    poses[1]["identity_continuous"] = False
    assert motion_metrics(poses)["status"] == "INSUFFICIENT_CONTINUOUS_IDENTITY"


def test_motion_metrics_do_not_bridge_separate_quality_gated_segments():
    template = {
        "track_quality": "POSE_READY", "identity_continuous": True,
        "pose_quality": "GOOD", "player_role": "NEAR_PLAYER",
        "keypoints": {
            "left_shoulder": {"x_global": 10, "y_global": 10, "score": .9},
            "right_shoulder": {"x_global": 20, "y_global": 10, "score": .9},
            "left_hip": {"x_global": 11, "y_global": 20, "score": .9},
            "right_hip": {"x_global": 19, "y_global": 20, "score": .9},
        },
    }
    poses = [
        {**template, "timestamp_ms": 0},
        {**template, "timestamp_ms": 33, "keypoints": {**template["keypoints"],
         "left_shoulder": {"x_global": 11, "y_global": 10, "score": .9}}},
        {**template, "timestamp_ms": 1000, "keypoints": {**template["keypoints"],
         "left_shoulder": {"x_global": 900, "y_global": 10, "score": .9}}},
        {**template, "timestamp_ms": 1033, "keypoints": {**template["keypoints"],
         "left_shoulder": {"x_global": 901, "y_global": 10, "score": .9}}},
    ]
    metrics = motion_metrics(poses)
    assert metrics["continuous_segment_count"] == 2
    assert metrics["lateral_movement_proxy_px"] == 0.25


def test_tracking_validation_workbench_appends_human_labels_under_dev_only(tmp_path):
    row = record_tracking_window_review(
        job_id="a" * 32, sample_id="game_3-t60", source_sha256="b" * 64,
        start_frame=30, end_frame=60, role="FAR_PLAYER", visibility="PARTIAL",
        identity="FAR_PLAYER", track_quality="GOOD", localappdata=tmp_path,
    )
    assert row["source"] == "USER_REVIEW"
    assert workbench_root(tmp_path).is_relative_to(tmp_path.resolve())
    assert list_tracking_window_reviews(tmp_path) == [row]


def test_tracking_validation_workbench_rejects_invalid_review_labels(tmp_path):
    try:
        record_tracking_window_review(
            job_id="../main", sample_id="game_3-t60", source_sha256="b" * 64,
            start_frame=0, end_frame=30, role="NEAR_PLAYER", visibility="VISIBLE",
            identity="NEAR_PLAYER", track_quality="GOOD", localappdata=tmp_path,
        )
    except ValueError as error:
        assert "INVALID_TRACKING_VALIDATION_REVIEW" in str(error)
    else:
        raise AssertionError("invalid job IDs must never be accepted")


def test_pose_manifest_accepts_current_and_structurally_verified_legacy_anchor_runs():
    row_near = {"role": "NEAR_PLAYER", "object_id": 1}
    row_far = {"role": "FAR_PLAYER", "object_id": 2}
    common = {"status": "ANCHOR_GUIDED_COMPLETE", "dataset": "Extended OpenTTGames",
              "commercial_use": False, "source_sha256": "a" * 64,
              "records": [row_near, row_far], "anchors": [{"frame": 0}]}
    current = {**common, "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING"}
    legacy = {**common, "schema_version": "anchor-guided-player-tracking-v1"}
    assert supports_pose_tracking_manifest(current)
    assert supports_pose_tracking_manifest(legacy)
    assert not supports_pose_tracking_manifest({**legacy, "anchors": []})
    assert not supports_pose_tracking_manifest({**legacy, "records": [{**row_near, "object_id": 2}]})


def test_motion_exclusion_is_append_only_and_separate_from_tracking_truth(tmp_path):
    row = record_motion_exclusion(job_id="a" * 32, source_sha256="b" * 64,
                                  start_frame=30, end_frame=60, role="FAR_PLAYER",
                                  localappdata=tmp_path)
    assert row["action"] == "EXCLUDE_FROM_MOTION_ANALYSIS"
    assert row["source"] == "USER_REVIEW"
    assert list_motion_exclusions("a" * 32, tmp_path) == [row]
