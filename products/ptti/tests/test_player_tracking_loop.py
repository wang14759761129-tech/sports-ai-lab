import copy

import pytest

from backend.player_tracking_loop import (
    RecoveryEpisodeGate,
    candidate_identifier,
    choose_reassociation,
    classify_track_health,
    confirm_seed,
    tracking_status_for,
)


def sample():
    return {
        "sample_id": "game_4-t30",
        "frames": 300,
        "width": 1920,
        "height": 1080,
        "clip_sha256": "a" * 64,
        "start_seconds": 30,
        "sample_fps": 30,
    }


def detections():
    return [
        {"candidate_id": "left", "bbox": [100, 250, 360, 900], "score": 0.94},
        {"candidate_id": "right", "bbox": [1450, 300, 1780, 1040], "score": 0.91},
        {"candidate_id": "umpire", "bbox": [840, 100, 1030, 400], "score": 0.85},
    ]


def test_seed_confirmation_binds_fixed_object_ids_and_preserves_raw_output():
    raw = detections()
    original = copy.deepcopy(raw)

    result = confirm_seed(
        sample=sample(),
        raw_detections=raw,
        near_candidate_id="right",
        far_candidate_id="left",
        frame_index=19,
        user_confirmed=True,
        athlete_mapping={"NEAR_PLAYER": "athlete-a", "FAR_PLAYER": "athlete-b"},
    )

    assert raw == original
    assert result["raw_detections"] == original
    assert [(row["object_id"], row["role"], row["source"])
            for row in result["selected_seeds"]] == [
        (1, "NEAR_PLAYER", "USER_CONFIRMED_SEED"),
        (2, "FAR_PLAYER", "USER_CONFIRMED_SEED"),
    ]
    assert result["seed_frame"] == 19
    assert result["timestamp_ms"] == 30633
    assert result["athlete_mapping"]["NEAR_PLAYER"] == "athlete-a"


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"bbox": [100, 100, 300, 700], "mask_area": 50000}, "HEALTHY"),
        ({"bbox": None, "mask_area": 0}, "LOST"),
        ({"bbox": None, "mask_area": 0, "previous_bbox": [0, 100, 100, 600],
          "previous_previous_bbox": [20, 100, 120, 600]}, "OUT_OF_FRAME"),
        ({"bbox": [100, 100, 300, 700], "mask_area": 100,
          "previous_bbox": [90, 100, 290, 700]}, "SUSPECT"),
        ({"bbox": [100, 100, 400, 700], "mask_area": 50000,
          "other_bbox": [110, 100, 410, 700]}, "IDENTITY_UNCERTAIN"),
    ],
)
def test_track_health_distinguishes_lost_out_of_frame_and_suspect(kwargs, expected):
    value = classify_track_health(frame_size=(1920, 1080), **kwargs)
    assert value["status"] == expected
    assert value["reason"]


def test_reassociation_uses_multiple_signals_and_keeps_role_identity():
    result = choose_reassociation(
        role="FAR_PLAYER",
        candidates=[
            {"candidate_id": "expected", "bbox": [100, 250, 360, 900]},
            {"candidate_id": "umpire", "bbox": [850, 100, 1040, 410]},
        ],
        previous_bbox=[110, 250, 370, 900],
        predicted_bbox=[105, 250, 365, 900],
        seed_bbox=[100, 250, 360, 900],
        frame_size=(1920, 1080),
    )
    assert result["decision"] == "AUTO_REACQUIRED"
    assert result["candidate"]["candidate_id"] == "expected"
    assert result["candidate"]["association"]["role"] == "FAR_PLAYER"


def test_reassociation_requires_user_when_candidates_are_ambiguous():
    result = choose_reassociation(
        role="NEAR_PLAYER",
        candidates=[
            {"candidate_id": "a", "bbox": [800, 200, 1100, 900]},
            {"candidate_id": "b", "bbox": [805, 205, 1105, 905]},
        ],
        previous_bbox=[800, 200, 1100, 900],
        predicted_bbox=[800, 200, 1100, 900],
        seed_bbox=[800, 200, 1100, 900],
        frame_size=(1920, 1080),
    )
    assert result["decision"] == "REQUIRES_USER_CONFIRMATION"
    assert result["candidate"] is None


def test_reassociation_does_not_offer_unrelated_referee_as_player_candidate():
    result = choose_reassociation(
        role="FAR_PLAYER",
        candidates=[
            {"candidate_id": "far-player", "bbox": [90, 230, 380, 940]},
            {"candidate_id": "referee", "bbox": [850, 80, 1030, 390]},
        ],
        previous_bbox=[100, 250, 360, 900],
        predicted_bbox=[95, 240, 370, 920],
        seed_bbox=[100, 250, 360, 900],
        frame_size=(1920, 1080),
    )
    assert result["decision"] == "AUTO_REACQUIRED"
    assert result["candidate"]["candidate_id"] == "far-player"
    assert [row["candidate_id"] for row in result["ranked"]] == ["far-player"]
    assert [row["candidate_id"] for row in result["rejected_candidates"]] == ["referee"]


def test_reassociation_returns_no_candidate_when_all_boxes_are_geometrically_unrelated():
    result = choose_reassociation(
        role="FAR_PLAYER",
        candidates=[{"candidate_id": "other-side-person", "bbox": [1450, 120, 1780, 550]}],
        previous_bbox=[30, 250, 340, 960],
        predicted_bbox=[20, 245, 330, 955],
        seed_bbox=[30, 250, 340, 960],
        frame_size=(1920, 1080),
    )
    assert result["decision"] == "NO_CANDIDATE"
    assert result["ranked"] == []
    assert result["rejected_candidates"][0]["candidate_id"] == "other-side-person"


def test_recovery_episode_throttles_reviews_until_track_is_stable_again():
    gate = RecoveryEpisodeGate(retry_interval=30, healthy_reset_frames=3)
    assert gate.due_roles({"FAR_PLAYER": "SUSPECT"}, frame=84) == ["FAR_PLAYER"]
    gate.mark_attempts(["FAR_PLAYER"], frame=84)
    gate.mark_review_requested("FAR_PLAYER", frame=84)
    assert not gate.may_request_review("FAR_PLAYER", frame=89)
    assert gate.due_roles({"FAR_PLAYER": "SUSPECT"}, frame=89) == []
    assert gate.due_roles({"FAR_PLAYER": "SUSPECT"}, frame=114) == ["FAR_PLAYER"]
    assert not gate.may_request_review("FAR_PLAYER", frame=114)
    assert gate.may_request_review("FAR_PLAYER", frame=174)
    gate.observe("FAR_PLAYER", "HEALTHY", frame=115)
    gate.observe("FAR_PLAYER", "SUSPECT", frame=116)
    assert not gate.is_episode_stable("FAR_PLAYER")
    gate.observe("FAR_PLAYER", "HEALTHY", frame=117)
    gate.observe("FAR_PLAYER", "HEALTHY", frame=118)
    assert gate.observe("FAR_PLAYER", "HEALTHY", frame=119) is True
    assert gate.may_request_review("FAR_PLAYER", frame=120)
    assert gate.due_roles({"FAR_PLAYER": "SUSPECT"}, frame=120) == ["FAR_PLAYER"]


def test_recovery_episode_reports_a_loss_once_and_scene_reset_reopens_review():
    gate = RecoveryEpisodeGate(retry_interval=30, healthy_reset_frames=3)
    assert gate.mark_loss_reported("NEAR_PLAYER") is True
    assert gate.mark_loss_reported("NEAR_PLAYER") is False
    gate.mark_review_requested("NEAR_PLAYER", frame=10)
    gate.reset_for_scene_change()
    assert gate.may_request_review("NEAR_PLAYER", frame=11)
    assert gate.mark_loss_reported("NEAR_PLAYER") is True


def test_missing_reassociation_candidate_is_safe_for_role_comparison():
    assert candidate_identifier({"decision": "NO_CANDIDATE", "candidate": None}) is None
    assert candidate_identifier({"decision": "REQUIRES_USER_CONFIRMATION"}) is None
    assert candidate_identifier({"candidate": {"candidate_id": "player-1"}}) == "player-1"


def test_reverse_propagation_without_a_mask_is_marked_unassessed_not_lost():
    assert tracking_status_for(frame_index=12, seed_frame=20, mask_area=0,
                               health_status="HEALTH_NOT_ASSESSED_REVERSE", direction="REVERSE") == "HEALTH_NOT_ASSESSED_REVERSE"
    assert tracking_status_for(frame_index=12, seed_frame=20, mask_area=1000,
                               health_status="HEALTH_NOT_ASSESSED_REVERSE", direction="REVERSE") == "TRACKED_REVERSE"
    assert tracking_status_for(frame_index=21, seed_frame=20, mask_area=0,
                               health_status="LOST", direction="FORWARD") == "LOST"


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"near_candidate_id": "left", "far_candidate_id": "left", "user_confirmed": True},
         "TWO_DISTINCT_USER_CONFIRMED_SEEDS_REQUIRED"),
        ({"near_candidate_id": "missing", "far_candidate_id": "right", "user_confirmed": True},
         "SEED_CANDIDATE_NOT_FOUND"),
        ({"near_candidate_id": "right", "far_candidate_id": "left", "user_confirmed": False},
         "TWO_DISTINCT_USER_CONFIRMED_SEEDS_REQUIRED"),
        ({"near_candidate_id": "right", "far_candidate_id": "left", "user_confirmed": True,
          "frame_index": 300}, "FRAME_OUT_OF_RANGE"),
    ],
)
def test_seed_validation_fails_closed(kwargs, message):
    values = {"sample": sample(), "raw_detections": detections(), "frame_index": 0,
              "near_candidate_id": "right", "far_candidate_id": "left", "user_confirmed": True}
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        confirm_seed(**values)


def test_seed_bbox_correction_is_validated_and_recorded():
    result = confirm_seed(
        sample=sample(), raw_detections=detections(), near_candidate_id="right",
        far_candidate_id="left", frame_index=0, user_confirmed=True,
        near_bbox=[1400, 250, 1800, 1070],
    )
    near = result["selected_seeds"][0]
    assert near["user_bbox_adjusted"] is True
    assert near["bbox"] == [1400, 250, 1800, 1070]
    with pytest.raises(ValueError, match="INVALID_SEED_BBOX"):
        confirm_seed(
            sample=sample(), raw_detections=detections(), near_candidate_id="right",
            far_candidate_id="left", frame_index=0, user_confirmed=True,
            near_bbox=[-1, 0, 100, 100],
        )
