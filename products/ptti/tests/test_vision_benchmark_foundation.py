"""Engineering QA only; fixtures do not prove model accuracy."""
from pathlib import Path
import sys
import json

import pytest

BENCHMARK = Path(__file__).parents[1] / "research" / "vision-benchmark"
sys.path.insert(0, str(BENCHMARK))
from ptti_benchmark.adapters import racketvision_rows, rfdetr_rows  # noqa: E402
from ptti_benchmark.core import (  # noqa: E402
    BallDetection, FrameObservation, METRICS_VERSION, canonical_sha256,
    evaluate_ball, file_sha256, rank_models, trajectory_metrics, verify_manifest, write_report,
)
from ptti_benchmark.cvat import read_cvat_xml  # noqa: E402
from ptti_benchmark.tool_value import validate_tool_card  # noqa: E402


def row(frame, visible=True, x=10, y=10):
    return FrameObservation(frame, frame * 10, (BallDetection(x, y),) if visible else (), "test", "QA")


def test_localization_distinguished_from_presence_and_extra_false_targets():
    result = evaluate_ball([row(0, x=200)], [{"source_frame": 0, "visible": True, "x": 10, "y": 10}], 300, 300, 100)
    assert result["presence_recall"] == 1
    assert result["recall"] == 0
    assert result["false_detections"] == 1
    assert result["catastrophic_errors"]["100"] == 1


def test_sparse_annotation_never_invents_negatives_or_minute_rate():
    labels = [{"source_frame": 0, "visible": True, "x": 10, "y": 10},
              {"source_frame": 9, "visible": None}]
    result = evaluate_ball([row(i) for i in range(10)], labels, 300, 300, 100)
    assert result["false_detections"] == 0
    assert result["unreviewed_labels"] == 1
    assert result["fp_per_min"] is None
    assert result["reviewed_frames"] == 1
    sparse = evaluate_ball([row(0), row(9)], labels + [{"source_frame": 8, "visible": False}], 300, 300, 100)
    assert sparse["fp_per_min"] is None


def test_dense_negative_rate():
    result = evaluate_ball([row(0), row(1)], [{"source_frame": 0, "visible": False},
                                           {"source_frame": 1, "visible": False}], 300, 300, 2)
    assert result["fp_per_min"] == 120


def test_duplicate_frames_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION"):
        evaluate_ball([row(0), row(0)], [], 300, 300, 30)


@pytest.mark.parametrize("kwargs", [{"x": float("nan"), "y": 1}, {"x": 1, "y": 2, "bbox": (2, 2, 1, 1)}])
def test_invalid_observations_rejected(kwargs):
    with pytest.raises(ValueError):
        BallDetection(**kwargs)


def test_trajectory_fragments_and_gap_recovery():
    result = trajectory_metrics([row(0), row(1), row(2, False), row(3), row(4, False)])
    assert result["trajectory_fragment_count"] == 2
    assert result["longest_continuous_track"] == 2
    assert result["longest_missing_run"] == 1
    assert result["recovery_after_gap"] == 1
    assert trajectory_metrics([row(0), row(3)])["status"] == "SPARSE_NOT_EVALUABLE"


def test_adapters_keep_coordinates_and_score_semantics():
    rv = racketvision_rows([{"frame": 120, "visible": True, "pixel_x": 4, "pixel_y": 8, "confidence": .6}], 120)
    rf = rfdetr_rows([{"source_frame": 120, "timestamp_ms": 1000, "detections": [{"x": 4, "y": 8, "score": .6}]}])
    assert rv[0].timestamp_ms == rf[0].timestamp_ms == 1000
    assert rv[0].detections == rf[0].detections


def test_manifest_integrity_and_locked_split(tmp_path):
    asset = tmp_path / "qa.txt"
    asset.write_text("engineering QA")
    record = {"path": str(asset), "sha256": file_sha256(asset)}
    manifest = {"metrics_version": METRICS_VERSION, "clips": [{"id": "qa", "split": "DEV", "scene_strata": ["UNKNOWN"], "video": record, "annotation": record,
                "canonical_labels": str(asset), "canonical_labels_sha256": record["sha256"]}]}
    verify_manifest(manifest)
    manifest["clips"][0]["split"] = "TEST"
    with pytest.raises(ValueError, match="LOCKED_SPLIT"):
        verify_manifest(manifest)
    manifest["clips"][0]["split"] = "DEV"
    asset.write_text("changed")
    with pytest.raises(ValueError, match="ASSET_CHANGED"):
        verify_manifest(manifest)


def test_immutable_report_and_escaped_html(tmp_path):
    target = tmp_path / "report.json"
    write_report(target, {"label": "<script>"})
    assert "&lt;script&gt;" in target.with_suffix(".html").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_report(target, {})
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_cvat_point_box_event_and_explicit_negative(tmp_path):
    source = tmp_path / "annotations.xml"
    source.write_text('<annotations><image id="0"><points label="BALL" points="4,8"/><tag label="HIT"><attribute name="player">NEAR_PLAYER</attribute></tag></image><image id="1"><tag label="BALL_ABSENT"/></image><track id="1" label="BALL"><box frame="2" xtl="2" ytl="4" xbr="6" ybr="8" outside="0"/></track></annotations>')
    mapping = {i: {"source_frame": 100+i, "timestamp_ms": 1000+i*10} for i in range(3)}
    rows = read_cvat_xml(source, mapping)
    assert rows[0]["x"] == 4
    assert rows[1]["attributes"]["player"] == "NEAR_PLAYER"
    assert rows[2]["visible"] is False
    assert rows[3]["x"] == 4 and rows[3]["source_frame"] == 102


def test_cvat_outside_is_unknown_not_negative(tmp_path):
    source = tmp_path / "annotations.xml"
    source.write_text('<annotations><track id="1" label="BALL"><points frame="0" points="1,2" outside="1"/></track></annotations>')
    assert read_cvat_xml(source, {0: {"source_frame": 0, "timestamp_ms": 0}})[0]["visible"] is None


def test_cvat_requires_source_frame_mapping(tmp_path):
    source = tmp_path / "annotations.xml"
    source.write_text('<annotations><image id="0"><points label="BALL" points="1,2"/></image></annotations>')
    with pytest.raises(ValueError, match="FRAME_MAPPING"):
        read_cvat_xml(source, {})


def test_cvat_rejects_entity_expansion(tmp_path):
    source = tmp_path / "annotations.xml"
    source.write_text('<!DOCTYPE a [<!ENTITY e SYSTEM "file:///secret">]><annotations/>')
    with pytest.raises(ValueError, match="UNSAFE_XML"):
        read_cvat_xml(source, {})


def test_core_has_no_framework_imports():
    text = (BENCHMARK / "ptti_benchmark" / "core.py").read_text(encoding="utf-8")
    assert not any(f"import {name}" in text for name in ("torch", "cv2", "onnxruntime", "transformers", "rfdetr"))


def test_tool_cards_disclose_complete_costs_and_risks():
    cards = json.loads((BENCHMARK / "TOOL_VALUE_CARDS.json").read_text(encoding="utf-8"))["cards"]
    assert len(cards) == 13
    for card in cards:
        validate_tool_card(card)
    cards[0]["benefits"]["accuracy"] = 11
    with pytest.raises(ValueError, match="TOOL_SCORE"):
        validate_tool_card(cards[0])


def test_ranking_refuses_different_data_or_metrics():
    result = {"manifest_sha256": "a", "model": "A", "metrics": {"metrics_version": METRICS_VERSION, "f1": .8, "recall": .9}}
    other = {**result, "model": "B", "manifest_sha256": "b"}
    with pytest.raises(ValueError, match="INCOMPARABLE"):
        rank_models([result, other])
    assert rank_models([result])[0]["scope"] == "DESCRIPTIVE_SAME_DEV_DATA_ONLY"


def test_timestamp_alignment_is_checked_before_scoring():
    with pytest.raises(ValueError, match="TIMESTAMP_ALIGNMENT"):
        evaluate_ball([row(10)], [{"source_frame": 10, "timestamp_ms": 0, "visible": True,
                                  "x": 10, "y": 10}], 300, 300, 100)


def test_derived_labels_tampering_is_rejected(tmp_path):
    asset, labels = tmp_path/"video", tmp_path/"labels.json"
    asset.write_text("QA")
    labels.write_text("original")
    record = {"path": str(asset), "sha256": file_sha256(asset)}
    manifest = {"metrics_version": METRICS_VERSION, "clips": [{"id": "qa", "split": "DEV",
                "scene_strata": ["UNKNOWN"], "video": record, "annotation": record,
                "canonical_labels": str(labels), "canonical_labels_sha256": file_sha256(labels)}]}
    verify_manifest(manifest)
    labels.write_text("edited")
    with pytest.raises(ValueError, match="DERIVED_BENCHMARK"):
        verify_manifest(manifest)
