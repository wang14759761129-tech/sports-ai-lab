import json
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "research" / "hit-v03"


def load(name):
    spec = importlib.util.spec_from_file_location(f"hitv03_{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calibration = load("calibration")
runtime = load("runtime")


def test_calibration_scope_is_game4_train_only():
    calibration.enforce_calibration_scope("game_4", "CALIBRATION", "TRAIN")
    with pytest.raises(ValueError, match="ONLY_GAME_4"):
        calibration.enforce_calibration_scope("game_5", "holdout", "TRAIN")
    with pytest.raises(ValueError, match="ONLY_GAME_4"):
        calibration.enforce_calibration_scope("game_4", "dev", "TRAIN")
    with pytest.raises(ValueError, match="ONLY_GAME_4"):
        calibration.enforce_calibration_scope("game_4", "calibration", "TEST")


def test_calibration_root_is_derived_from_exact_game4_source(tmp_path):
    video = tmp_path / "PTTI-Dev" / "research-datasets" / "ExtendedOpenTTGames" / "videos" / "train" / "game_4.mp4"
    video.parent.mkdir(parents=True)
    video.touch()
    assert calibration.resolve_ptti_dev_root(video).name == "PTTI-Dev"
    with pytest.raises(ValueError, match="CANONICAL_PTTI_DEV_ROOT"):
        calibration.resolve_ptti_dev_root(tmp_path / "game_4.mp4")


def test_first_pass_writer_is_immutable(tmp_path):
    path = tmp_path / "CALIBRATION_FIRST_PASS_UNTOUCHED.json"
    expected = {"status": "FIRST_PASS"}
    digest = calibration.immutable_json(path, expected)
    assert digest
    assert json.loads(path.read_text(encoding="utf-8")) == expected
    with pytest.raises(FileExistsError):
        calibration.immutable_json(path, {"status": "replaced"})
    assert json.loads(path.read_text(encoding="utf-8")) == expected


def test_calibration_variant_budget_is_limited_to_five():
    valid = [{"name": f"v{i}"} for i in range(5)]
    assert calibration.validate_calibration_variants(valid) == valid
    with pytest.raises(ValueError, match="BUDGET_EXCEEDED"):
        calibration.validate_calibration_variants([*valid, {"name": "v5"}])
    with pytest.raises(ValueError, match="UNIQUE"):
        calibration.validate_calibration_variants([{"name": "same"}, {"name": "same"}])


def test_unknown_player_and_missing_table_are_neutral():
    candidate = {"evidence_score": 0.8}
    result = runtime.soft_adjustment(candidate, ball_point=(10, 10), table=None,
                                     player={"minimum_player_candidate_distance": None},
                                     mode="D", config={"table_center_penalty": 0.08,
                                                "person_distance_penalty": 0.12,
                                                "distance_scale": 0.12})
    assert result["evidence_score"] == candidate["evidence_score"]
    assert result["research_soft_penalties"] == {}


def test_frozen_config_requires_calibration_and_dev_backcheck():
    config = {"table_center_penalty": 0.08}
    assert calibration.canonical_config_sha256(config)
    kwargs = {"config": config, "source_commit": "abc", "dev_metrics": {"f1": .48},
              "calibration_metrics": {"f1": .5}, "frozen_at": "2026-10-08"}
    with pytest.raises(ValueError, match="REQUIRES_CALIBRATION"):
        calibration.build_frozen_config_record(**kwargs, calibration_passed=True, dev_backcheck_passed=False)
    record = calibration.build_frozen_config_record(**kwargs, calibration_passed=True, dev_backcheck_passed=True)
    assert record["config_sha256"] == calibration.canonical_config_sha256(config)
    assert record["game_5"] == "LOCKED_NOT_ACCESSED"
