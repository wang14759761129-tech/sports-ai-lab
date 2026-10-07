import json

import pytest

from backend.evidence_fusion import (
    CanonicalVideoTimeline,
    DatasetSideMapping,
    EvidenceFusionConfig,
    HitCandidateEngine,
    aggregate_hit_evaluations,
    build_frame_evidence,
    configuration_sha256,
    evaluate_hit_events,
    load_review_corrections,
    record_review_correction,
)


SHA = "a" * 64


def make_timeline(*, pts=None):
    return CanonicalVideoTimeline(
        video_sha256=SHA,
        source_fps=120,
        processing_fps=30,
        source_frame_start=7200,
        clip_start_timestamp_ms=60_000,
        processing_pts_ms=pts or [0, 1000 / 30, 2000 / 30, 3000 / 30, 4000 / 30],
    )


def test_canonical_timeline_maps_120fps_source_to_30fps_by_pts():
    timeline = make_timeline()

    rows = [timeline.map_processing_frame(frame) for frame in (0, 2, 4)]

    assert [row["source_frame"] for row in rows] == [7200, 7208, 7216]
    assert [row["processing_frame"] for row in rows] == [0, 2, 4]
    assert rows[2]["timestamp_ms"] == pytest.approx(60_133.333333)
    assert rows[2]["timestamp_source"] == "PROCESSING_PTS_PLUS_REGISTERED_ORIGIN"


def test_canonical_timeline_uses_source_pts_when_available_and_rejects_nonmonotonic_pts():
    timeline = CanonicalVideoTimeline(
        video_sha256=SHA,
        source_fps=120,
        processing_fps=30,
        source_frame_start=7200,
        clip_start_timestamp_ms=60_000,
        processing_pts_ms=[0, 33.333, 66.667],
        source_pts_ms={7200: 60_000.2, 7204: 60_033.4, 7208: 60_066.8},
    )
    assert timeline.map_processing_frame(1)["timestamp_ms"] == pytest.approx(60_033.4)
    assert timeline.map_processing_frame(1)["timestamp_source"] == "SOURCE_PTS"
    with pytest.raises(ValueError, match="MONOTONIC"):
        make_timeline(pts=[0, 34, 33])


def test_frame_evidence_joins_by_canonical_time_not_local_frame_number():
    timeline = make_timeline(pts=[0, 1000 / 30])
    frames = build_frame_evidence(
        timeline,
        ball_rows=[
            {"frame": 0, "timestamp_ms": 0, "visible": True, "pixel_x": 50, "pixel_y": 60},
            {"frame": 1, "timestamp_ms": 1000 / 30, "visible": False},
        ],
        tracking_rows=[
            {"frame": 900, "timestamp_ms": 60_000, "role": "NEAR_PLAYER",
             "tracking_status": "ACCEPTED", "bbox": [0, 0, 100, 200]},
        ],
        pose_rows=[
            {"frame": 1234, "timestamp_ms": 60_000, "player_role": "NEAR_PLAYER",
             "pose_quality": "GOOD", "keypoints": {"right_wrist": {"x_global": 52, "y_global": 61, "score": .8}}},
        ],
        source_sha256s={"ball": SHA, "tracking": SHA, "pose": SHA},
        max_join_delta_ms=2,
    )

    assert frames[0]["ball"]["x"] == 50
    assert frames[0]["frame"] == 0
    assert frames[0]["players"]["NEAR_PLAYER"]["track"]["bbox"] == [0, 0, 100, 200]
    assert frames[0]["players"]["NEAR_PLAYER"]["pose"]["keypoints"]["right_wrist"]["x_global"] == 52
    assert frames[1]["players"]["NEAR_PLAYER"]["track"] is None
    assert frames[1]["players"]["NEAR_PLAYER"]["pose"] is None


def test_frame_evidence_rejects_a_different_video_hash_and_keeps_missing_pose_null():
    timeline = make_timeline(pts=[0])
    with pytest.raises(ValueError, match="SOURCE_SHA_MISMATCH"):
        build_frame_evidence(
            timeline,
            ball_rows=[{"frame": 0, "visible": True, "pixel_x": 2, "pixel_y": 3}],
            tracking_rows=[], pose_rows=[],
            source_sha256s={"ball": "b" * 64},
        )

    frames = build_frame_evidence(
        timeline,
        ball_rows=[{"frame": 0, "timestamp_ms": 0, "visible": False}],
        tracking_rows=[], pose_rows=[], source_sha256s={"ball": SHA},
    )
    assert frames[0]["evidence_level"] == "INSUFFICIENT"
    assert frames[0]["players"]["FAR_PLAYER"]["pose"] is None


def test_dataset_side_mapping_fails_closed_until_human_reviewed():
    unreviewed = DatasetSideMapping(
        match_id="game_4", dataset_side_to_role={"left": "FAR_PLAYER", "right": "NEAR_PLAYER"},
        source="annotation convention", evidence="candidate only", review_status="UNREVIEWED",
    )
    reviewed = DatasetSideMapping(
        match_id="game_4", dataset_side_to_role={"left": "FAR_PLAYER", "right": "NEAR_PLAYER"},
        source="Extended OpenTTGames frame labels + reviewed clip frame",
        evidence="near seed bbox is on screen-right; far seed bbox is on screen-left",
        review_status="HUMAN_REVIEWED",
    )
    assert unreviewed.map_side("right") == "UNKNOWN"
    assert reviewed.map_side("right") == "NEAR_PLAYER"
    assert reviewed.map_side("left") == "FAR_PLAYER"


def test_hit_engine_emits_explainable_suggestions_without_probability_claims():
    frames = []
    ball_x = [20, 35, 50, 35, 20]
    wrist_x = [5, 20, 50, 80, 95]
    for index, (x, wrist) in enumerate(zip(ball_x, wrist_x)):
        frames.append({
            "video_sha256": SHA,
            "timestamp_ms": 1000 + index * 1000 / 30,
            "processing_frame": index,
            "frame_size": {"width": 200, "height": 200},
            "ball": {"visible": True, "x": x, "y": 100, "model_evidence": .7},
            "players": {
                "NEAR_PLAYER": {
                    "track": {"tracking_status": "ACCEPTED", "bbox": [0, 0, 120, 200]},
                    "pose": {"pose_quality": "GOOD", "keypoints": {
                        "left_wrist": {"x_global": wrist, "y_global": 100, "score": .8},
                        "right_wrist": {"x_global": wrist, "y_global": 100, "score": .8},
                    }},
                },
                "FAR_PLAYER": {
                    "track": {"tracking_status": "ACCEPTED", "bbox": [130, 0, 190, 200]},
                    "pose": None,
                },
            },
        })

    config = EvidenceFusionConfig.from_dict({
        "schema_version": "hit-event-v0.1",
        "weights": {"ball_player_proximity": .15, "wrist_proximity_proxy": .35,
                    "trajectory_direction_change": .35, "wrist_speed_peak": .05,
                    "pose_quality": .05, "track_health": .05},
        "candidate_threshold": .5,
        "local_peak_radius_frames": 1,
        "minimum_separation_ms": 100,
        "trajectory_window_ms": 33.4,
    })
    events = HitCandidateEngine(config).suggest(frames)

    assert events
    assert all(event["status"] == "SUGGESTED" for event in events)
    assert all(event["confidence"] is None for event in events)
    assert all(event["frame"] == event["processing_frame"] for event in events)
    assert [event["sequence_index"] for event in events] == list(range(1, len(events) + 1))
    assert any("wrist_proximity_proxy" in event["evidence_components"] for event in events)
    assert all("HIT" == event["event_type"] for event in events)


def test_hit_engine_degrades_without_pose_and_does_not_claim_pose_source():
    frames = []
    for index, x in enumerate((20, 40, 60, 40, 20)):
        frames.append({
            "video_sha256": SHA, "timestamp_ms": index * 1000 / 30,
            "processing_frame": index, "source_frame": 7200 + index * 4,
            "evidence_level": "PARTIAL_EVIDENCE",
            "ball": {"visible": True, "x": x, "y": 60, "model_evidence": .7},
            "players": {
                "NEAR_PLAYER": {"track": {"tracking_status": "ACCEPTED",
                                             "bbox": [0, 0, 120, 100]}, "pose": None},
                "FAR_PLAYER": {"track": None, "pose": None},
            },
        })
    config = EvidenceFusionConfig(
        weights={"ball_player_proximity": .2, "trajectory_direction_change": .7,
                 "track_health": .1},
        candidate_threshold=.5, local_peak_radius_frames=1,
        minimum_separation_ms=100, trajectory_window_ms=33.4,
    )
    events = HitCandidateEngine(config).suggest(frames)
    assert events
    assert events[0]["evidence_level"] == "PARTIAL_EVIDENCE"
    assert "RTMPOSE" not in events[0]["source_modules"]
    assert events[0]["confidence"] is None


def test_config_hash_is_stable_and_event_matching_is_one_to_one_at_all_tolerances():
    config = {"schema_version": "hit-event-v0.1", "candidate_threshold": .5}
    assert configuration_sha256(config) == configuration_sha256(dict(config))

    predicted = [{"event_id": "p1", "timestamp_ms": 100}, {"event_id": "p2", "timestamp_ms": 104}]
    truth = [{"event_id": "g1", "timestamp_ms": 102}]
    result = evaluate_hit_events(predicted, truth, tolerances_ms={"one": 1, "three": 3})
    assert result["by_tolerance"]["one"]["matched"] == 0
    assert result["by_tolerance"]["three"]["matched"] == 1
    assert result["by_tolerance"]["three"]["false_positives"] == 1
    assert result["by_tolerance"]["three"]["player_side_accuracy"] is None


def test_aggregate_never_matches_events_from_different_videos():
    tolerance = {"pm3": 100}
    first_video = evaluate_hit_events(
        [{"event_id": "p1", "timestamp_ms": 60_000}], [], tolerances_ms=tolerance)
    second_video = evaluate_hit_events(
        [], [{"event_id": "g1", "timestamp_ms": 60_000}], tolerances_ms=tolerance)

    combined = aggregate_hit_evaluations([("video-a", first_video), ("video-b", second_video)])

    row = combined["by_tolerance"]["pm3"]
    assert row["predicted"] == 1 and row["ground_truth"] == 1
    assert row["matched"] == 0
    assert row["false_positives"] == 1 and row["false_negatives"] == 1
    assert row["f1"] == 0


def test_manual_corrections_are_append_only_and_do_not_mutate_raw_candidates(tmp_path):
    raw = [{"event_id": "raw-1", "timestamp_ms": 100, "candidate_player": "NEAR_PLAYER"}]
    before = json.dumps(raw, sort_keys=True)
    path = tmp_path / "reviews.jsonl"
    record_review_correction(path, video_sha256=SHA, action="CONFIRM", event_id="raw-1",
                             timestamp_ms=102, player="NEAR_PLAYER")
    record_review_correction(path, video_sha256=SHA, action="ADJUST", event_id="raw-1",
                             timestamp_ms=104, player="FAR_PLAYER")

    rows = load_review_corrections(path)
    assert len(rows) == 2
    assert rows[0]["action"] == "CONFIRM"
    assert rows[1]["action"] == "ADJUST"
    assert json.dumps(raw, sort_keys=True) == before
