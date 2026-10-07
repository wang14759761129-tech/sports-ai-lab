import json
import hashlib
from pathlib import Path

import pytest

from backend.hit_event_v02 import (
    HitEventV02Config,
    HitSequenceDecoder,
    RawHitCandidateGenerator,
    StrokeIntervalPrior,
    TemporalCandidateClusterer,
    apply_pose_rerank,
    config_sha256,
    summarize_hard_negative_overlap,
)


def config(**updates):
    value = {
        "schema_version": "hit-event-v0.2", "status": "DRAFT_DEV_ONLY",
        "minimum_kinematic_score": .18, "max_ball_gap_ms": 120,
        "max_normalized_ball_speed_per_second": 2.779,
        "minimum_pre_post_observations": 2, "cluster_window_ms": 66.667,
        "interval_floor_ms": 316.667, "sequence_break_ms": 3966.667,
        "decoder_selection_floor": .6, "same_side_penalty": .4,
        "alternation_reward": .08, "short_interval_penalty": .4,
        "pose_for_hit": False, "pose_rerank_max_delta": 0,
    }
    value.update(updates)
    return HitEventV02Config.from_dict(value)


def make_frames(xs, *, pose=False):
    frames = []
    for index, x in enumerate(xs):
        players = {
            "NEAR_PLAYER": {"track": {"bbox": [max(0, x-15), 20, x+20, 180],
                                         "tracking_status": "ACCEPTED"}, "pose": None},
            "FAR_PLAYER": {"track": {"bbox": [130, 20, 180, 180],
                                        "tracking_status": "ACCEPTED"}, "pose": None},
        }
        if pose:
            players["NEAR_PLAYER"]["pose"] = {
                "pose_quality": "GOOD",
                "keypoints": {"left_wrist": {"x": x, "y": 90, "score": .99}},
            }
        frames.append({
            "video_sha256": "a" * 64, "timestamp_ms": index * 1000 / 30,
            "processing_frame": index, "source_frame": index * 4,
            "frame_size": {"width": 200, "height": 200},
            "ball": {"visible": True, "x": x, "y": 100, "model_evidence": .8},
            "players": players,
        })
    return frames


def test_draft_config_is_pose_off_and_hash_is_stable():
    path = Path(__file__).parents[1] / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_DRAFT_CONFIG.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    loaded = HitEventV02Config.from_dict(value)

    assert loaded.status == "DRAFT_DEV_ONLY"
    assert loaded.pose_for_hit is False
    assert config_sha256(loaded) == config_sha256(value)


def test_video_level_split_is_locked_and_hash_verified_without_event_level_leakage():
    path = Path(__file__).parents[1] / "configs" / "evidence-fusion" / "HIT_EVENT_V0_2_SPLIT.json"
    digest_path = path.with_suffix(path.suffix + ".sha256")
    expected = digest_path.read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    split = json.loads(path.read_text(encoding="utf-8"))
    groups = split["split_policy"]
    development = set(groups["development"])
    calibration = set(groups["calibration"])
    holdout = set(groups["internal_holdout"])

    assert development == {"game_1", "game_2", "game_3"}
    assert calibration == {"game_4"}
    assert holdout == {"game_5"}
    assert not development & calibration
    assert not development & holdout
    assert not calibration & holdout
    assert "not a pristine" in groups["historical_exposure"]
    assert split["official_test_split"] == "NOT_ACCESSED"
    assert split["production_database"] == "NOT_ACCESSED"


def test_raw_generator_uses_ball_kinematics_without_pose_candidate_creation():
    frames = make_frames([20, 30, 40, 50, 60, 50, 40, 30, 20])

    candidates = RawHitCandidateGenerator(config()).generate(frames)

    assert candidates
    assert all(row["pose_used_for_generation"] is False for row in candidates)
    assert all("RTMPOSE" not in row["source_modules"] for row in candidates)
    assert all(row["evidence_components"]["pre_ball_observations"] == 2 for row in candidates)
    assert all(row["evidence_components"]["post_ball_observations"] == 2 for row in candidates)


def test_wrist_motion_cannot_create_a_candidate_without_ball_kinematics():
    frames = make_frames([40] * 12, pose=True)
    for index, frame in enumerate(frames):
        frame["players"]["NEAR_PLAYER"]["pose"]["keypoints"]["left_wrist"]["x"] = index * 30

    assert RawHitCandidateGenerator(config()).generate(frames) == []


def test_balltrack_speed_outlier_is_retained_as_raw_but_flagged():
    frames = make_frames([20, 30, 40, 50, 190, 180, 170, 160, 150])

    candidates = RawHitCandidateGenerator(config(max_normalized_ball_speed_per_second=.2)).generate(frames)

    assert candidates
    assert any(row["ball_quality"] == "JUMP_SUSPECT" for row in candidates)
    assert any(row["filter_reason"] == "BALLTRACK_JUMP" for row in candidates)


def test_decoder_never_promotes_balltrack_jump_to_filtered_hit():
    prior = StrokeIntervalPrior.from_development_intervals([300, 350, 400])
    candidate = {
        "event_id": "jump-hit", "timestamp_ms": 500, "evidence_score": .99,
        "candidate_player": "NEAR_PLAYER", "identity_status": "CONFIDENT",
        "ball_quality": "JUMP_SUSPECT", "filter_reason": "BALLTRACK_JUMP",
    }

    result = HitSequenceDecoder(config(), prior).decode([candidate])

    assert result["accepted"] == []
    assert result["suppressed"][0]["decision"] == "BALLTRACK_QUALITY"


def test_clusterer_keeps_strongest_candidate_and_records_removed_raw_events():
    candidates = [
        {"event_id": "a", "timestamp_ms": 100, "evidence_score": .6},
        {"event_id": "b", "timestamp_ms": 150, "evidence_score": .9},
        {"event_id": "c", "timestamp_ms": 400, "evidence_score": .7},
    ]

    result = TemporalCandidateClusterer(66.667).cluster(candidates)

    assert [row["event_id"] for row in result["kept"]] == ["b", "c"]
    assert result["suppressed_count"] == 1
    assert result["suppressed"][0]["decision"] == "SUPPRESSED_DUPLICATE_CLUSTER"


def test_cluster_window_does_not_chain_across_multiple_contacts():
    candidates = [
        {"event_id": "a", "timestamp_ms": 0, "evidence_score": .6},
        {"event_id": "b", "timestamp_ms": 50, "evidence_score": .9},
        {"event_id": "c", "timestamp_ms": 100, "evidence_score": .8},
    ]

    result = TemporalCandidateClusterer(60).cluster(candidates)

    assert [row["event_id"] for row in result["kept"]] == ["b", "c"]
    assert result["cluster_count"] == 2
    assert result["suppressed_count"] == 1


def test_cluster_window_is_inclusive_at_serialized_timestamp_boundary():
    rows = [
        {"event_id": "anchor", "timestamp_ms": 0.0, "evidence_score": .7},
        {"event_id": "edge", "timestamp_ms": 66.667, "evidence_score": .9},
    ]

    result = TemporalCandidateClusterer(66.666).cluster(rows)

    assert result["cluster_count"] == 1
    assert [row["event_id"] for row in result["kept"]] == ["edge"]
    assert result["suppressed"][0]["selected_event_id"] == "edge"


def test_decoder_softly_suppresses_same_side_conflict_and_keeps_alternation():
    prior = StrokeIntervalPrior.from_development_intervals([275, 316.667, 375, 733.333])
    decoder = HitSequenceDecoder(config(), prior)
    candidates = [
        {"event_id": "near-1", "timestamp_ms": 0, "evidence_score": .9,
         "candidate_player": "NEAR_PLAYER", "identity_status": "CONFIDENT"},
        {"event_id": "near-fp", "timestamp_ms": 700, "evidence_score": .85,
         "candidate_player": "NEAR_PLAYER", "identity_status": "CONFIDENT"},
        {"event_id": "far-2", "timestamp_ms": 1400, "evidence_score": .9,
         "candidate_player": "FAR_PLAYER", "identity_status": "CONFIDENT"},
    ]

    result = decoder.decode(candidates)

    assert [row["event_id"] for row in result["accepted"]] == ["near-1", "far-2"]
    assert any(row["decision"] == "SEQUENCE_GLOBAL_OPTIMUM" for row in result["suppressed"])
    assert result["accepted"][1]["decoder_reason"] == "ALTERNATING_PLAYER_SEQUENCE"


def test_uncertain_identity_does_not_receive_hard_alternation_constraint():
    prior = StrokeIntervalPrior.from_development_intervals([300, 350, 400])
    decoder = HitSequenceDecoder(config(), prior)
    candidates = [
        {"event_id": "a", "timestamp_ms": 0, "evidence_score": .85,
         "candidate_player": "NEAR_PLAYER", "identity_status": "UNCERTAIN"},
        {"event_id": "b", "timestamp_ms": 700, "evidence_score": .82,
         "candidate_player": "NEAR_PLAYER", "identity_status": "UNCERTAIN"},
    ]

    result = decoder.decode(candidates)

    assert len(result["accepted"]) == 2
    assert all(row["sequence_review_required"] for row in result["accepted"])


def test_decoder_surfaces_near_optimal_alternating_event_for_review():
    prior = StrokeIntervalPrior.from_development_intervals([300, 350, 400])
    decoder = HitSequenceDecoder(config(), prior)
    candidates = [
        {"event_id": "near-weak", "timestamp_ms": 0, "evidence_score": .508841,
         "candidate_player": "NEAR_PLAYER", "identity_status": "CONFIDENT"},
        {"event_id": "far-strong", "timestamp_ms": 833.333, "evidence_score": .855552,
         "candidate_player": "FAR_PLAYER", "identity_status": "CONFIDENT"},
    ]

    result = decoder.decode(candidates)

    review = {row["event_id"]: row for row in result["review_candidates"]}
    assert "near-weak" in review
    assert review["near-weak"]["status"] == "REQUIRES_REVIEW"
    assert review["near-weak"]["review_reason"] == "NEAR_OPTIMAL_SEQUENCE"
    assert review["near-weak"]["decoder_trace"]["regret_to_best_block_path"] < .02
    assert all(row["event_id"] != "near-weak" for row in result["accepted"])


def test_decoder_routes_ambiguous_above_floor_candidate_to_review():
    prior = StrokeIntervalPrior.from_development_intervals([300, 350, 400])
    decoder = HitSequenceDecoder(config(), prior)
    candidates = [
        {"event_id": "strong", "timestamp_ms": 0, "evidence_score": .95,
         "candidate_player": "NEAR_PLAYER", "identity_status": "CONFIDENT"},
        {"event_id": "ambiguous", "timestamp_ms": 100, "evidence_score": .606,
         "candidate_player": "UNKNOWN", "identity_status": "UNCERTAIN"},
    ]

    result = decoder.decode(candidates)

    assert [row["event_id"] for row in result["accepted"]] == ["strong"]
    assert result["review_candidates"][0]["event_id"] == "ambiguous"
    assert result["review_candidates"][0]["review_reason"] == "IDENTITY_UNCERTAIN"
    suppressed = next(row for row in result["suppressed"] if row["event_id"] == "ambiguous")
    assert suppressed["decision"] == "SEQUENCE_GLOBAL_OPTIMUM"
    assert "SEQUENCE_GLOBAL_OPTIMUM" in suppressed["rejection_reasons"]
    assert suppressed["decoder_trace"]["best_block_path_utility"] > 0


def test_pose_rerank_never_creates_candidates_and_is_off_by_default():
    frames = make_frames([1, 2, 3], pose=True)
    candidate = {"event_id": "existing", "timestamp_ms": frames[1]["timestamp_ms"],
                 "evidence_score": .7, "source_modules": ["RACKETVISION_RAW"]}

    result = apply_pose_rerank([candidate], frames, config())

    assert len(result) == 1
    assert result[0]["event_id"] == "existing"
    assert result[0]["evidence_score"] == .7
    assert result[0]["pose_rerank_applied"] is False


def test_pose_rerank_is_bounded_and_only_applies_to_existing_candidate():
    frames = make_frames([1, 2, 3], pose=True)
    cfg = config(pose_for_hit=True, pose_rerank_max_delta=.05)
    candidate = {"event_id": "existing", "timestamp_ms": frames[1]["timestamp_ms"],
                 "candidate_player": "NEAR_PLAYER", "evidence_score": .7,
                 "source_modules": ["RACKETVISION_RAW"]}

    result = apply_pose_rerank([candidate], frames, cfg)

    assert len(result) == 1
    assert result[0]["evidence_score"] < .75
    assert result[0]["pose_rerank_applied"] is True


def test_pose_quality_alone_does_not_rerank_without_ball_wrist_support():
    frames = make_frames([1, 2, 3], pose=True)
    frame = frames[1]
    frame["players"]["NEAR_PLAYER"]["pose"]["keypoints"] = {
        "left_wrist": {"x": 180, "y": 180, "score": .99},
        "right_wrist": {"x": 175, "y": 175, "score": .99},
    }
    candidate = {"event_id": "existing", "timestamp_ms": frame["timestamp_ms"],
                 "candidate_player": "NEAR_PLAYER", "evidence_score": .7,
                 "source_modules": ["RACKETVISION_RAW"]}

    result = apply_pose_rerank([candidate], frames, config(pose_for_hit=True, pose_rerank_max_delta=.05))

    assert result[0]["evidence_score"] == .7
    assert result[0]["pose_rerank_applied"] is False


def test_bounce_and_net_overlap_is_development_diagnostic_only():
    result = summarize_hard_negative_overlap(
        [{"event_id": "h1", "timestamp_ms": 100}],
        [{"event_id": "b1", "timestamp_ms": 150, "event_type": "BOUNCE"},
         {"event_id": "n1", "timestamp_ms": 120, "event_type": "NET"}],
        window_ms=60,
    )

    assert result["scope"].startswith("TRAIN_DEV_DIAGNOSTIC_ONLY")
    assert result["by_event_type"]["BOUNCE"]["candidate_near_event_count"] == 1
    assert result["by_event_type"]["NET"]["candidate_near_event_count"] == 1
