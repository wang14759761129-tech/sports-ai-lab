from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_full_dev_hit_v02.py"
SPEC = importlib.util.spec_from_file_location("run_full_dev_hit_v02", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def test_locked_calibration_and_holdout_games_are_rejected_before_io(tmp_path):
    for game in (4, 5):
        try:
            module.resolve_full_dev_inputs(game, tmp_path)
        except ValueError as exc:
            assert str(exc) == "ONLY_LOCKED_DEV_GAMES_1_TO_3_ARE_ALLOWED"
        else:
            raise AssertionError("locked game was accepted")


def test_ball_context_requires_two_observations_on_both_sides():
    frames = []
    for index in range(9):
        frames.append({"timestamp_ms": index * 1000 / 120,
                       "ball": {"visible": index in {0, 1, 2, 6, 7, 8}}})
    truth = [{"event_id": "stroke", "timestamp_ms": 4 * 1000 / 120}]

    result = module.ball_context_coverage(frames, truth, window_ms=40)

    assert result["events_with_ball_context"] == 1
    frames[6]["ball"]["visible"] = False
    frames[7]["ball"]["visible"] = False
    frames[8]["ball"]["visible"] = False
    result = module.ball_context_coverage(frames, truth, window_ms=40)
    assert result["events_with_ball_context"] == 0


def test_stage_attrition_reports_raw_and_cluster_losses_separately():
    truth = [{"event_id": "a", "timestamp_ms": 10, "source_frame": 1, "native_label": "forehand_loop"},
             {"event_id": "b", "timestamp_ms": 20, "source_frame": 2, "native_label": "backhand_push"}]
    def evaluation(matched):
        return {"by_tolerance": {"tol": {"matches": [{"ground_truth_index": index}
                                                          for index in matched]}}}
    metrics = {"raw": evaluation({0}), "cluster": evaluation(set()),
               "decoded": evaluation(set()), "review_mode": evaluation(set())}

    result = module.stage_attrition(truth, metrics, "tol")

    assert [row["loss_stage"] for row in result] == ["TEMPORAL_CLUSTER_LOSS", "RAW_GENERATOR_MISS"]
