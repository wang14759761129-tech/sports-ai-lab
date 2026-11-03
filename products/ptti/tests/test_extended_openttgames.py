from backend.extended_openttgames import (
    ExtendedOpenTTGamesAdapter, derive_rally_ground_truth, evaluate_segments, _hungarian_max,
)
from fastapi.testclient import TestClient
from backend.main import create_app
import pytest
from scripts.evaluate_extended_openttgames import _require_child


def test_native_events_preserve_labels_and_use_explicit_pts():
    adapter = ExtendedOpenTTGamesAdapter(fps=120)
    events = adapter.parse({
        "3": "left_forehand_serve neutral left_foot_lifted",
        "9": "net",
        "15": "right_winner",
        "20": "right_backhand_chop back_heavy both_feet_planted",
        "22": "xright_unknown_extension",
    }, pts_ms={3: 25.0})
    serve, bounce, ending, chop, unknown = events
    assert (serve["event_type"], serve["player_side"], serve["hand"], serve["technique"]) == (
        "STROKE", "left", "FOREHAND", "SERVE")
    assert (serve["lean"], serve["feet"]) == ("neutral", "left_foot_lifted")
    assert serve["timestamp_ms"] == 25 and serve["timestamp_source"] == "SOURCE_PTS"
    assert bounce["event_type"] == "NET"
    assert bounce["timestamp_source"] == "FRAME_RATE_ESTIMATE"
    assert (ending["event_type"], ending["native_label_tail"], ending["player_side"]) == (
        "RALLY_ENDING", "winner", "right")
    assert chop["technique"] == "CHOP"
    assert unknown["event_type"] == "UNKNOWN_NATIVE_EVENT"
    assert unknown["native_label"] == "xright_unknown_extension"


def test_derived_rallies_are_explicit_and_incomplete_events_are_retained():
    adapter = ExtendedOpenTTGamesAdapter(fps=120)
    events = adapter.parse({"0": "left_forehand_serve neutral unknown", "30": "right_out",
                            "50": "right_net", "60": "right_forehand_serve neutral unknown"})
    result = derive_rally_ground_truth(events, frame_count=100)
    assert result["ground_truth_type"] == "DERIVED_NOT_NATIVE"
    assert len(result["segments"]) == 1
    segment = result["segments"][0]
    assert segment["ground_truth_type"] == "DERIVED"
    assert segment["start_source"] == "serve_annotation"
    assert segment["end_source"] == "rally_ending_annotation"
    assert segment["ending_type"] == "out"
    assert {item["reason"] for item in result["incomplete_ground_truth"]} == {
        "ENDING_WITHOUT_SERVE", "MISSING_RALLY_ENDING"}


def test_annotations_outside_video_are_incomplete_not_scored():
    events = ExtendedOpenTTGamesAdapter(fps=120).parse(
        {"3": "left_forehand_serve neutral unknown", "101": "right_out"})
    result = derive_rally_ground_truth(events, frame_count=100)
    assert result["segments"] == []
    assert result["incomplete_ground_truth"][0]["reason"] == "ANNOTATION_OUTSIDE_VIDEO"


def test_segment_evaluation_uses_global_assignment_and_keeps_misses_and_false_suggestions():
    predictions = [{"start_ms": 0, "end_ms": 100}, {"start_ms": 40, "end_ms": 140},
                   {"start_ms": 400, "end_ms": 500}]
    truth = [{"start_ms": 0, "end_ms": 100}, {"start_ms": 80, "end_ms": 180}]
    result = evaluate_segments(predictions, truth, min_iou=0.1)
    assert result["matched_rallies"] == 2
    assert result["false_rallies"] == 1
    assert result["missed_rallies"] == 0
    assert result["precision"] == 2 / 3
    assert result["recall"] == 1
    assert _hungarian_max([[0.9, 0.8], [0.85, 0.1]]) == [1, 0]


def test_segment_evaluation_accepts_close_boundaries_when_temporal_iou_is_low():
    result = evaluate_segments([{"start_ms": 400, "end_ms": 500}],
                               [{"start_ms": 0, "end_ms": 100}], min_iou=0.1,
                               max_boundary_delta_ms=500)
    assert result["matched_rallies"] == 1
    assert result["matches"][0]["match_basis"] == "BOUNDARY_PROXIMITY"


def test_ball_ground_truth_missing_sentinel_is_not_a_detection():
    rows = ExtendedOpenTTGamesAdapter(fps=120).parse_ball_track(
        {"5": {"x": 12, "y": 13}, "6": {"x": -1, "y": -1}})
    assert rows[0]["visible"] and rows[0]["timestamp_ms"] == 5 * 1000 / 120
    assert not rows[1]["visible"] and rows[1]["x"] is None


def test_dataset_manager_only_reports_training_and_locks_test_split(tmp_path):
    app = create_app(tmp_path / "research-manager-test.db")
    dataset_root = app.state.data_root / "research-datasets" / "ExtendedOpenTTGames"
    game_dir = dataset_root / "annotations" / "train" / "game_data"
    ball_dir = dataset_root / "annotations" / "train" / "ball_data"
    video_dir = dataset_root / "videos" / "train"
    for folder in (game_dir, ball_dir, video_dir):
        folder.mkdir(parents=True)
    (game_dir / "game_4.json").write_text("{}", encoding="utf-8")
    (ball_dir / "train_4.json").write_text("{}", encoding="utf-8")
    (video_dir / "game_4.mp4").write_bytes(b"qa")
    with TestClient(app) as client:
        response = client.get("/api/vision/research-datasets/extended-openttgames")
    assert response.status_code == 200
    payload = response.json()
    assert payload["commercial_use"] is False
    assert payload["license"] == "CC BY-NC-SA 4.0"
    assert payload["test_split"]["status"] == "LOCKED_NOT_ACCESSED"
    assert len(payload["training"]["annotations"]) == 5
    assert payload["training"]["videos"][3]["status"] == "PARTIAL"


def test_evaluation_path_guard_accepts_only_descendants(tmp_path):
    root = tmp_path / "training"
    allowed = root / "game_4.mp4"
    allowed.parent.mkdir(parents=True)
    allowed.write_bytes(b"qa")
    assert _require_child(allowed, root, "Video") == allowed.resolve()
    with pytest.raises(ValueError, match="must be inside"):
        _require_child(tmp_path / "test_1.mp4", root, "Video")
