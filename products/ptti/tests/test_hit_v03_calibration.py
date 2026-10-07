import hashlib
import importlib.util
import json
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
player_worker = load("calibration_player_worker")
evaluator = load("evaluate_game4_calibration")
player_runner = load("run_calibration_players")


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


def test_calibration_player_worker_rejects_game5_and_non_calibration_splits():
    with pytest.raises(ValueError, match="ONLY_GAME_4"):
        player_worker.validate_request({"game": "game_5", "split_role": "holdout",
                                        "official_split": "TRAIN"})
    with pytest.raises(ValueError, match="ONLY_GAME_4"):
        player_worker.validate_request({"game": "game_4", "split_role": "dev",
                                        "official_split": "TRAIN"})


def test_calibration_player_worker_rejects_annotation_content_before_io():
    request = {"game": "game_4", "split_role": "CALIBRATION", "official_split": "TRAIN",
               "game_5": "NOT_ACCESSED", "official_test": "NOT_ACCESSED",
               "annotations": {"strokes": []}}
    with pytest.raises(ValueError, match="GT_CONTENT_FORBIDDEN"):
        player_worker.validate_request(request)


def test_calibration_player_worker_uses_verified_rtdetr_model_directory(tmp_path):
    assert player_worker.rtdetr_model_folder(tmp_path) == (
        tmp_path / "vision-v2" / "models" / "rtdetr-r18vd"
    )


def test_player_coverage_keeps_unknown_roles_neutral_and_reports_table_coverage():
    raw = [{"source_frame": 12, "event_id": "candidate-1"}]
    people = [{"bbox": [40, 40, 60, 60], "detector_score": 0.8,
               "candidate_id": "person-1", "role_candidate": "UNKNOWN"}]
    by_frame = {12: {"resolved_people": people}}
    summary = evaluator._player_coverage(raw, by_frame, [0, 0, 100, 100], {"12": [50, 50]})
    assert summary["player_neutral_fallback_frames"] == 1
    assert summary["role_frames"]["unknown_role_person_frame"] == 1
    assert summary["table_geometry"]["coverage"] == 1.0
    assert summary["table_geometry"]["inside_bbox_count"] == 1


def test_calibration_metric_summary_uses_predicted_count_from_primary_tolerance():
    metrics = {"by_tolerance": {"plus_minus_2_processing_frames": {
        "predicted": 4, "matched": 3, "false_positives": 1, "false_negatives": 2,
        "precision": 0.75, "recall": 0.6, "f1": 2 * 0.75 * 0.6 / 1.35,
    }}}
    summary = evaluator._metric_summary(metrics, 60.0)
    assert summary["review_candidates_per_minute"] == 4.0
    assert summary["fp_per_minute"] == 1.0


def test_game4_table_box_uses_only_frozen_game4_manifest_rows(tmp_path, monkeypatch):
    manifest = {"frame_results": [
        {"game": "game_4", "detections": [
            {"label": "table tennis table", "bbox": [10, 20, 90, 80]},
            {"label": "table", "bbox": [30, 35, 70, 60]},
        ]},
        {"game": "game_4", "detections": [
            {"label": "table tennis table", "bbox": [12, 22, 92, 82]},
        ]},
        {"game": "game_5", "detections": [
            {"label": "table tennis table", "bbox": [100, 100, 500, 400]},
        ]},
    ]}
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    digest = player_runner._sha(path)
    monkeypatch.setattr(player_runner, "FROZEN_MANIFEST_SHA", digest)
    bbox, count = player_runner._table_bbox(path)
    assert count == 2
    assert bbox == [11.0, 21.0, 91.0, 81.0]


def test_player_runner_requires_consistent_model_provenance(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps({"model_provenance": {"revision": "fixed"}}), encoding="utf-8")
    second.write_text(json.dumps({"model_provenance": {"revision": "fixed"}}), encoding="utf-8")
    jobs = [{"output": str(first)}, {"output": str(second)}]
    assert player_runner._load_consistent_model_provenance(jobs) == {"revision": "fixed"}

    second.write_text(json.dumps({"model_provenance": {"revision": "changed"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="PROVENANCE_CHANGED"):
        player_runner._load_consistent_model_provenance(jobs)


def test_player_runner_counts_frames_with_both_resolved_roles():
    rows = [
        {"resolved_people": [
            {"role_candidate": "NEAR_PLAYER"}, {"role_candidate": "FAR_PLAYER"},
        ]},
        {"resolved_people": [{"role_candidate": "NEAR_PLAYER"}]},
        {"resolved_people": [{"role_candidate": "UNKNOWN"}]},
    ]
    people, frames = player_runner._summarize_roles(rows)
    assert people["NEAR_PLAYER"] == 2
    assert people["FAR_PLAYER"] == 1
    assert frames["NEAR_PLAYER"] == 2
    assert frames["FAR_PLAYER"] == 1
    assert frames["both_near_and_far"] == 1


def test_frozen_v03_config_hash_and_holdout_locks():
    config_path = ROOT.parents[1] / "configs" / "evidence-fusion" / "HIT_EVENT_V0_3_FROZEN_CONFIG.json"
    record = json.loads(config_path.read_text(encoding="utf-8"))
    config_sha = calibration.canonical_config_sha256(record["config"])
    assert record["config_sha256"] == config_sha
    assert len(record["source_commit"]) == 40
    assert record["status"] == "FROZEN_FOR_GAME_5_INTERNAL_HOLDOUT"
    assert record["research_gate"] == "HIT_EVENT_V0_3_CONFIG_FROZEN"
    assert record["product_gate"] == "HIT_EVENT_V0_2_PARTIAL"
    assert record["limits"]["game_5"] == "LOCKED_NOT_ACCESSED"
    assert record["limits"]["official_test"] == "NOT_ACCESSED"
    assert record["limits"]["production_database"] == "NOT_ACCESSED"
    sidecar = config_path.with_name(config_path.name + ".sha256").read_text(encoding="ascii")
    assert sidecar.split()[0] == hashlib.sha256(config_path.read_bytes()).hexdigest()
