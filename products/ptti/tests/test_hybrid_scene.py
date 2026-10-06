import pytest

from backend.hybrid_scene import (
    PersonDetectionCandidate,
    PlayerRoleResolver,
    RTMDetPredictionAdapter,
    SCOREBOARD_MODULE,
    review_priority_v2,
    to_pose_adapter_input,
)


def test_rtmdet_adapter_keeps_only_coco_person_and_preserves_provenance():
    rows = RTMDetPredictionAdapter(score_threshold=0.25).adapt(
        frame=123,
        timestamp_ms=1025,
        predictions=[
            {"bbox": [10, 20, 60, 150], "score": 0.8, "class_id": 0},
            {"bbox": [70, 20, 90, 40], "score": 0.99, "class_id": 32},
            {"bbox": [100, 20, 140, 160], "score": 0.2, "class_id": 0},
        ],
    )
    assert len(rows) == 1
    assert rows[0].to_dict() == {
        "candidate_id": "rtmdet-f000123-d00",
        "frame": 123,
        "timestamp_ms": 1025,
        "label": "person",
        "bbox": [10.0, 20.0, 60.0, 150.0],
        "detector_score": 0.8,
        "detector": "RTMDet",
        "model": "rtmdet_tiny_8xb32-300e_coco",
        "class_id": 0,
        "role": "UNKNOWN",
        "role_candidate": "UNKNOWN",
        "role_evidence": [],
        "status": "SUGGESTED",
    }


def test_person_candidate_rejects_invalid_score_and_box():
    with pytest.raises(ValueError):
        PersonDetectionCandidate("bad", 1, 0, (2, 2, 2, 4), 0.5)
    with pytest.raises(ValueError):
        PersonDetectionCandidate("bad", 1, 0, (1, 2, 4, 8), 1.5)


def test_role_resolver_assigns_near_far_only_for_two_opposing_candidates():
    resolver = PlayerRoleResolver()
    table = [100, 100, 300, 220]
    people = [
        {"candidate_id": "far", "bbox": [5, 20, 70, 130], "detector_score": .9},
        {"candidate_id": "near", "bbox": [330, 70, 395, 260], "detector_score": .8},
    ]
    result = resolver.resolve(table, people, image_size=(400, 300))
    assert {x["candidate_id"]: x["role_candidate"] for x in result} == {
        "far": "FAR_PLAYER", "near": "NEAR_PLAYER"
    }
    assert all(x["role"] == "UNKNOWN" for x in result)
    assert all(x["role_evidence"] for x in result)


def test_role_resolver_does_not_force_player_when_referee_or_extra_person_is_ambiguous():
    resolver = PlayerRoleResolver()
    people = [
        {"candidate_id": "left", "bbox": [5, 20, 70, 130], "detector_score": .9},
        {"candidate_id": "center", "bbox": [180, 20, 220, 140], "detector_score": .9},
        {"candidate_id": "right", "bbox": [330, 70, 395, 260], "detector_score": .8},
    ]
    result = resolver.resolve([100, 100, 300, 220], people, image_size=(400, 300))
    assert all(row["role_candidate"] == "UNKNOWN" for row in result)
    assert all("AMBIGUOUS_PERSON_COUNT" in row["role_evidence"] for row in result)


def test_review_priority_v2_flags_missing_roles_extra_people_and_referee_ambiguity():
    result = review_priority_v2([
        {"role_candidate": "NEAR_PLAYER", "role_evidence": []},
        {"role_candidate": "UNKNOWN", "role_evidence": ["REFEREE_CANDIDATE"]},
        {"role_candidate": "OTHER_PERSON", "role_evidence": []},
    ])
    assert result == {
        "priority": "HIGH",
        "status": "REVIEW_REQUIRED",
        "reasons": ["FAR_PLAYER_MISSING", "PERSON_ROLE_AMBIGUOUS", "TOO_MANY_PERSON_CANDIDATES"],
    }


def test_pose_adapter_input_is_bbox_only_and_does_not_claim_pose_results():
    candidate = PersonDetectionCandidate("p1", 10, 400, (10, 20, 80, 200), .9)
    payload = to_pose_adapter_input(candidate)
    assert payload == {"frame": 10, "timestamp_ms": 400, "person_id": "p1", "bbox": [10.0, 20.0, 80.0, 200.0], "status": "INPUT_READY_NOT_INFERRED"}


def test_scoreboard_is_explicitly_unimplemented_and_does_not_block_scene_gate():
    assert SCOREBOARD_MODULE.status == "NOT_IMPLEMENTED"
    assert SCOREBOARD_MODULE.blocks_scene_gate is False
