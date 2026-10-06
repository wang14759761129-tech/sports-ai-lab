from backend.anchor_guided_tracker import (
    AnchorGuidedPlayerTracker,
    PlayerIdentityAssociator,
    associate_players,
    checkpoint_matches,
    derive_play_zones,
    fuse_masks,
    schedule_time_anchors,
    visibility_coverage,
)


def test_time_anchor_schedule_uses_seconds_and_keeps_seed_and_final_frame():
    anchors = schedule_time_anchors(frame_count=75, sample_fps=25, interval_seconds=0.5, seed_frame=12)
    assert [item["frame"] for item in anchors] == [0, 12, 25, 37, 50, 62, 74]
    assert [item["timestamp_ms"] for item in anchors] == [0, 480, 1000, 1480, 2000, 2480, 2960]


def test_anchor_schedule_spacing_scales_with_video_fps():
    slow = schedule_time_anchors(frame_count=75, sample_fps=25, interval_seconds=1.0)
    fast = schedule_time_anchors(frame_count=180, sample_fps=60, interval_seconds=1.0)
    assert [row["timestamp_ms"] for row in slow] == [0, 1000, 2000, 2960]
    assert [row["timestamp_ms"] for row in fast] == [0, 1000, 2000, 2983]


def test_play_zones_are_derived_from_table_and_frame_geometry():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    assert zones["near"]["bbox"][1] == 140
    assert zones["far"]["bbox"][3] == 140
    assert zones["near"]["bbox"][0] < 100
    assert zones["far"]["bbox"][2] > 300


def test_play_zones_infer_left_right_side_view_from_confirmed_seeds():
    zones = derive_play_zones(
        table_bbox=[390, 570, 1425, 1005], image_size=(1920, 1080),
        seed_candidates={
            "NEAR_PLAYER": {"candidate_id": "near", "bbox": [1495, 478, 1746, 1024]},
            "FAR_PLAYER": {"candidate_id": "far", "bbox": [202, 414, 459, 911]},
        })
    assert zones["separation_axis"] == "X"
    assert zones["near_seed_side"] == "RIGHT"
    assert zones["near"]["bbox"] == [907.5, 0.0, 1920.0, 1080.0]
    assert zones["far"]["bbox"] == [0.0, 0.0, 907.5, 1080.0]


def test_play_zones_infer_depth_view_when_seed_separation_is_vertical():
    zones = derive_play_zones(
        table_bbox=[100, 100, 300, 180], image_size=(400, 300),
        seed_candidates={
            "NEAR_PLAYER": {"candidate_id": "near", "bbox": [150, 150, 205, 285]},
            "FAR_PLAYER": {"candidate_id": "far", "bbox": [180, 5, 235, 130]},
        })
    assert zones["separation_axis"] == "Y"
    assert zones["near_seed_side"] == "LOWER"
    assert zones["near"]["bbox"] == [0.0, 140.0, 400.0, 300.0]


def test_side_view_role_zone_outranks_center_referee_without_hard_filtering():
    zones = derive_play_zones(
        table_bbox=[390, 570, 1425, 1005], image_size=(1920, 1080),
        seed_candidates={
            "NEAR_PLAYER": {"candidate_id": "near-seed", "bbox": [1495, 478, 1746, 1024]},
            "FAR_PLAYER": {"candidate_id": "far-seed", "bbox": [202, 414, 459, 911]},
        })
    result = associate_players([
        {"candidate_id": "left-player", "bbox": [215, 411, 442, 912]},
        {"candidate_id": "right-player", "bbox": [1484, 525, 1753, 1067]},
        {"candidate_id": "referee", "bbox": [845, 345, 939, 472]},
    ], zones, frame_size=(1920, 1080), references={
        "NEAR_PLAYER": {"bbox": [1495, 478, 1746, 1024]},
        "FAR_PLAYER": {"bbox": [202, 414, 459, 911]},
    })
    assert result["NEAR_PLAYER"]["status"] == "CONFIDENT"
    assert result["NEAR_PLAYER"]["candidate"]["candidate_id"] == "right-player"
    assert result["FAR_PLAYER"]["status"] == "CONFIDENT"
    assert result["FAR_PLAYER"]["candidate"]["candidate_id"] == "left-player"


def test_anchor_association_keeps_near_and_far_ids_distinct_using_table_context():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    candidates = [
        {"candidate_id": "near", "bbox": [150, 150, 205, 285], "detector_score": .81},
        {"candidate_id": "far", "bbox": [185, 5, 235, 130], "detector_score": .74},
        {"candidate_id": "referee", "bbox": [185, 0, 225, 95], "detector_score": .89},
    ]
    result = associate_players(candidates, zones, frame_size=(400, 300))
    assert result["NEAR_PLAYER"]["status"] == "CONFIDENT"
    assert result["NEAR_PLAYER"]["candidate"]["candidate_id"] == "near"
    assert result["FAR_PLAYER"]["status"] in {"AMBIGUOUS", "CONFIDENT"}
    assert result["NEAR_PLAYER"]["candidate"]["candidate_id"] != (
        result["FAR_PLAYER"].get("candidate") or {}).get("candidate_id")


def test_association_fails_closed_without_candidates_or_with_shared_identity():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    empty = associate_players([], zones, frame_size=(400, 300))
    assert {row["status"] for row in empty.values()} == {"FAILED"}
    one = associate_players([{"candidate_id": "only", "bbox": [150, 20, 205, 290], "detector_score": .9}],
                            zones, frame_size=(400, 300))
    assert one["NEAR_PLAYER"]["candidate"] is None
    assert one["FAR_PLAYER"]["candidate"] is None
    assert {row["status"] for row in one.values()} == {"AMBIGUOUS"}


def test_identity_associator_uses_prior_player_motion_without_order_dependent_ids():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    tracker = PlayerIdentityAssociator(zones, frame_size=(400, 300))
    tracker.confirm("NEAR_PLAYER", {"candidate_id": "n0", "bbox": [150, 150, 205, 285]},
                    frame=0, timestamp_ms=0)
    tracker.confirm("FAR_PLAYER", {"candidate_id": "f0", "bbox": [180, 5, 235, 130]},
                    frame=0, timestamp_ms=0)
    candidates = [
        {"candidate_id": "f1", "bbox": [181, 7, 236, 132], "detector_score": .73},
        {"candidate_id": "n1", "bbox": [152, 153, 207, 286], "detector_score": .82},
    ]
    result = tracker.observe(candidates, frame=15, timestamp_ms=500)
    assert result["NEAR_PLAYER"]["candidate"]["candidate_id"] == "n1"
    assert result["FAR_PLAYER"]["candidate"]["candidate_id"] == "f1"
    assert result["NEAR_PLAYER"]["status"] == "CONFIDENT"
    assert result["FAR_PLAYER"]["status"] == "CONFIDENT"


def test_identity_associator_rejects_binding_one_person_to_both_roles():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    tracker = PlayerIdentityAssociator(zones, frame_size=(400, 300))
    candidate = {"candidate_id": "person", "bbox": [150, 20, 205, 290]}
    tracker.confirm("NEAR_PLAYER", candidate, frame=0, timestamp_ms=0)
    try:
        tracker.confirm("FAR_PLAYER", candidate, frame=0, timestamp_ms=0)
    except ValueError as error:
        assert str(error) == "CANDIDATE_ALREADY_BOUND_TO_OTHER_ROLE"
    else:
        raise AssertionError("one detection must not acquire both fixed player identities")


def test_identity_associator_supports_reverse_time_windows_without_relabeling_roles():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    tracker = PlayerIdentityAssociator(zones, frame_size=(400, 300), direction=-1)
    tracker.confirm("NEAR_PLAYER", {"candidate_id": "n1", "bbox": [150, 150, 205, 285]},
                    frame=30, timestamp_ms=1000)
    tracker.confirm("FAR_PLAYER", {"candidate_id": "f1", "bbox": [180, 5, 235, 130]},
                    frame=30, timestamp_ms=1000)
    result = tracker.observe([
        {"candidate_id": "n0", "bbox": [148, 148, 203, 283]},
        {"candidate_id": "f0", "bbox": [179, 4, 234, 129]},
    ], frame=15, timestamp_ms=500)
    assert result["NEAR_PLAYER"]["candidate"]["candidate_id"] == "n0"
    assert result["FAR_PLAYER"]["candidate"]["candidate_id"] == "f0"
    assert tracker.history["NEAR_PLAYER"][-1]["candidate_id"] == "n0"


def test_time_anchor_schedule_includes_cadence_on_both_sides_of_seed():
    anchors = schedule_time_anchors(frame_count=90, sample_fps=30,
                                    interval_seconds=1.0, seed_frame=60)
    assert [item["frame"] for item in anchors] == [0, 30, 60, 89]


def test_anchor_guided_tracker_preserves_fixed_object_ids_and_only_prompts_confident_roles():
    zones = derive_play_zones(table_bbox=[100, 100, 300, 180], image_size=(400, 300))
    tracker = AnchorGuidedPlayerTracker(
        sample_id="qa", frame_count=90, sample_fps=30, interval_seconds=1.0,
        seed_frame=0, zones=zones, frame_size=(400, 300),
        seed_candidates={
            "NEAR_PLAYER": {"candidate_id": "seed-near", "bbox": [150, 150, 205, 285]},
            "FAR_PLAYER": {"candidate_id": "seed-far", "bbox": [180, 5, 235, 130]},
        })
    tracker.observe_anchor(0, [])
    result = tracker.observe_anchor(30, [
        {"candidate_id": "near-1", "bbox": [151, 151, 206, 286]},
        {"candidate_id": "far-1", "bbox": [181, 6, 236, 131]},
    ])
    assert result["roles"]["NEAR_PLAYER"]["status"] == "CONFIDENT"
    assert result["roles"]["FAR_PLAYER"]["status"] == "CONFIDENT"
    assert {(p["object_id"], p["role"]) for p in tracker.prompt_plan()} == {
        (1, "NEAR_PLAYER"), (2, "FAR_PLAYER"),
        (1, "NEAR_PLAYER"), (2, "FAR_PLAYER"),
    }


def test_anchor_checkpoint_requires_all_source_and_window_identity_fields():
    expected = {"source_sha256": "s", "config_sha256": "c", "sample_id": "g1",
                "role": "FAR_PLAYER", "start_frame": 0, "end_frame": 30}
    assert checkpoint_matches(dict(expected, output_sha256="o"), expected)
    assert not checkpoint_matches(dict(expected, source_sha256="changed"), expected)
    assert not checkpoint_matches({key: value for key, value in expected.items() if key != "end_frame"}, expected)


def test_mask_fusion_preserves_raw_masks_and_marks_conflict_for_review():
    forward = [[2 <= x < 6 and 2 <= y < 6 for x in range(8)] for y in range(8)]
    reverse = [[2 <= x < 6 and 2 <= y < 6 for x in range(8)] for y in range(8)]
    agree = fuse_masks(forward, reverse, visibility="VISIBLE")
    assert agree["status"] == "ACCEPTED"
    assert agree["source"] == "FORWARD_REVERSE_AGREE"
    assert agree["forward_raw"] == forward
    assert agree["reverse_raw"] == reverse

    reverse = [[x < 2 and y < 2 for x in range(8)] for y in range(8)]
    conflict = fuse_masks(forward, reverse, visibility="VISIBLE")
    assert conflict["status"] == "REVIEW_REQUIRED"
    assert conflict["final_mask"] is None


def test_reverse_mask_is_never_selected_when_player_is_out_of_frame():
    mask = [[True] * 3 for _ in range(3)]
    result = fuse_masks(None, mask, visibility="OUT_OF_FRAME")
    assert result["status"] == "SUPPRESSED_OUT_OF_FRAME"
    assert result["final_mask"] is None


def test_visible_frame_coverage_uses_only_visible_and_partial_truth():
    result = visibility_coverage([
        {"visibility": "VISIBLE", "mask_present": True},
        {"visibility": "PARTIAL", "mask_present": True},
        {"visibility": "VISIBLE", "mask_present": False},
        {"visibility": "OUT_OF_FRAME", "mask_present": False},
        {"visibility": "UNKNOWN", "mask_present": True},
    ])
    assert result == {"eligible_frames": 3, "mask_available": 2, "coverage": 2 / 3,
                      "out_of_frame": 1, "unknown": 1}
