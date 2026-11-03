from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quick_annotation import QuickAnnotationError, adapt_quick_annotation, summarize_quick_annotation  # noqa: E402


def sample_v01() -> dict:
    return json.loads((ROOT / "fixtures" / "quick-annotation-v0.1-valid-simulated.json").read_text(encoding="utf-8"))


def sample_v02() -> dict:
    return json.loads((ROOT / "fixtures" / "quick-annotation-v0.2-valid-simulated.json").read_text(encoding="utf-8"))


class QuickAnnotationReliabilityTests(unittest.TestCase):
    def test_score_denominator_includes_points_without_time_ranges(self):
        payload = sample_v01()
        payload["points"] = []
        for point_number in range(1, 21):
            payload["points"].append({
                "point_id": f"SIMULATED_ONLY%3Aquick-match-001/g01/p{point_number:03d}",
                "server": "unknown",
                "winner": "player" if point_number % 2 == 1 or point_number == 20 else "opponent",
                "observed_tactics": {"serve_spin": "unknown"},
                "rally_start_ms": 1000 * point_number if point_number <= 12 else None,
                "rally_end_ms": 1000 * point_number + 500 if point_number <= 12 else None,
            })

        draft = adapt_quick_annotation(payload)
        stats = summarize_quick_annotation(draft)

        self.assertEqual(stats["sample"]["point_count"], 20)
        self.assertEqual(stats["sample"]["score_known_count"], 20)
        self.assertEqual(stats["metrics"]["time_range_coverage"]["numerator"], 12)
        self.assertEqual(stats["metrics"]["time_range_coverage"]["denominator"], 20)
        self.assertEqual(stats["metrics"]["time_range_coverage"]["missing_count"], 8)
        self.assertEqual(stats["metrics"]["timeline_bound_review_coverage"]["numerator"], 0)
        self.assertEqual(stats["metrics"]["tactical_fields"]["serve_spin"]["denominator"], 0)
        self.assertEqual(stats["metrics"]["tactical_fields"]["serve_spin"]["missing_count"], 20)

    def test_v01_remains_unchanged_and_stage_is_unavailable_not_inferred(self):
        draft = adapt_quick_annotation(sample_v01())
        self.assertEqual(draft["contract_version"], "ptti.quick-annotation/0.1")
        self.assertNotIn("observed_rally_stage", draft["points"][0])
        self.assertEqual(draft["points"][0]["protocol_fields"]["rally_length"], "unknown")
        self.assertEqual(draft["points"][4]["protocol_fields"]["rally_length"], 8)
        stats = summarize_quick_annotation(draft)
        self.assertEqual(stats["rally_stage_distribution"]["status"], "NOT_AVAILABLE_INPUT_V0_1")
        self.assertFalse(stats["automatic_formal_report_promotion"])

    def test_v02_copies_only_explicit_stage_and_never_maps_it_to_exact_protocol_fields(self):
        draft = adapt_quick_annotation(sample_v02())
        point = draft["points"][0]
        self.assertEqual(draft["contract_version"], "ptti.quick-annotation/0.2")
        self.assertEqual(point["observed_rally_stage"], "END_AFTER_1_2_CONTACTS")
        self.assertEqual(point["protocol_fields"]["rally_length"], "unknown")
        self.assertEqual(point["protocol_fields"]["third_ball_attack"], "unknown")
        self.assertEqual(point["field_derivation"]["rally_stage"], "COPIED_ONLY_FROM_EXPLICIT_USER_OBSERVATION")
        stats = summarize_quick_annotation(draft)
        self.assertEqual(stats["rally_stage_distribution"]["numerator"], {
            "END_AFTER_1_2_CONTACTS": 1,
            "END_AFTER_3_4_CONTACTS": 1,
            "END_AFTER_5_PLUS_CONTACTS": 1,
        })
        self.assertEqual(stats["rally_stage_distribution"]["denominator"], 3)
        self.assertEqual(stats["rally_stage_distribution"]["missing_count"], 2)
        self.assertEqual(stats["rally_stage_distribution"]["sample_status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(stats["review_candidates"][0]["point_id"], point["point_id"])
        self.assertLessEqual(len(stats["review_candidates"]), 2)
        self.assertEqual(stats["metrics"]["third_ball_attack_rate"]["numerator"], 1)
        self.assertEqual(stats["metrics"]["third_ball_attack_rate"]["denominator"], 1)
        self.assertEqual(stats["metrics"]["third_ball_immediate_success"]["numerator"], 0)
        self.assertEqual(stats["metrics"]["third_ball_immediate_success"]["denominator"], 1)
        self.assertEqual(stats["metrics"]["third_ball_server_point_conversion"]["numerator"], 0)
        self.assertEqual(stats["metrics"]["third_ball_server_point_conversion"]["denominator"], 1)

    def test_v02_optional_stage_defaults_to_unknown_and_invalid_stage_is_rejected(self):
        payload = sample_v02()
        payload["points"][0].pop("observed_rally_stage")
        draft = adapt_quick_annotation(payload)
        self.assertEqual(draft["points"][0]["observed_rally_stage"], "UNKNOWN")
        payload = sample_v02()
        payload["points"][0]["observed_rally_stage"] = "THIRD_BALL_ATTACK"
        with self.assertRaises(QuickAnnotationError) as caught:
            adapt_quick_annotation(payload)
        self.assertEqual(caught.exception.code, "INVALID_RALLY_STAGE")

    def test_gap_blocks_derived_score_then_backfill_restores_later_score(self):
        payload = sample_v01()
        payload["points"] = payload["points"][:1] + payload["points"][2:3]
        before = adapt_quick_annotation(payload)
        self.assertFalse(before["protocol"]["sequence_valid"])
        self.assertEqual(before["points"][1]["protocol_fields"]["server_score_before"], "unknown")
        self.assertFalse(summarize_quick_annotation(before)["sample"]["protocol_sequence_valid"])

        second = sample_v01()["points"][1]
        payload["points"].insert(1, second)
        after = adapt_quick_annotation(payload)
        self.assertTrue(after["protocol"]["sequence_valid"])
        self.assertEqual(after["points"][2]["score_before_player_opponent"], {"player": 1, "opponent": 1})
        self.assertTrue(summarize_quick_annotation(after)["sample"]["protocol_sequence_valid"])

    def test_changed_winner_recomputes_following_scores_and_game_counts(self):
        payload = sample_v01()
        before = summarize_quick_annotation(adapt_quick_annotation(payload))
        payload["points"][0]["winner"] = "opponent"
        after_draft = adapt_quick_annotation(payload)
        after = summarize_quick_annotation(after_draft)
        self.assertEqual(after_draft["points"][1]["score_before_player_opponent"], {"player": 0, "opponent": 1})
        self.assertEqual(before["sample"]["game_counts"]["1"]["player_wins"], 2)
        self.assertEqual(after["sample"]["game_counts"]["1"]["player_wins"], 1)
        self.assertEqual(after["sample"]["game_counts"]["1"]["opponent_wins"], 3)

    def test_score_without_timeline_counts_but_is_not_video_bound(self):
        payload = sample_v01()
        payload["video_context"].update(source_id=None, duration_ms=None, duration_status="UNKNOWN")
        for point in payload["points"]:
            point["rally_start_ms"] = point["rally_end_ms"] = None
        stats = summarize_quick_annotation(adapt_quick_annotation(payload))
        self.assertEqual(stats["sample"]["score_known_count"], 4)
        self.assertEqual(stats["metrics"]["score_record_coverage"]["numerator"], 4)
        self.assertEqual(stats["metrics"]["time_range_coverage"]["numerator"], 0)
        self.assertEqual(stats["metrics"]["timeline_bound_review_coverage"]["value"], 0)
        self.assertIsNone(stats["dataset"]["timeline_id"])

    def test_unknown_tactics_are_missing_not_known_technique_counts(self):
        payload = sample_v01()
        payload["points"] = payload["points"][:2]
        payload["points"][0]["observed_tactics"] = {"serve_spin": "unknown"}
        payload["points"][1]["observed_tactics"] = {"serve_spin": "unclear"}
        stats = summarize_quick_annotation(adapt_quick_annotation(payload))
        spin = stats["metrics"]["tactical_fields"]["serve_spin"]
        self.assertEqual(spin["numerator"], {})
        self.assertEqual(spin["denominator"], 0)
        self.assertEqual(spin["missing_count"], 2)
        self.assertEqual(spin["sample_status"], "NOT_ESTIMABLE")

    def test_small_samples_are_cautioned_without_significance_claim(self):
        stats = summarize_quick_annotation(adapt_quick_annotation(sample_v01()))
        metric = stats["metrics"]["server_point_win_rate"]
        self.assertEqual(metric["sample_status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(metric["display_caution_threshold"], 5)
        self.assertFalse(metric["threshold_is_significance_test"])
        self.assertLessEqual(len(stats["review_candidates"]), 2)
        self.assertTrue(all(item["status"] == "REVIEW_CANDIDATE_NOT_VIDEO_BOUND" for item in stats["review_candidates"]))

    def test_v02_unknown_version_still_fails_closed(self):
        payload = sample_v02()
        payload["contract_version"] = "ptti.quick-annotation/0.3"
        with self.assertRaises(QuickAnnotationError) as caught:
            adapt_quick_annotation(payload)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_VERSION")

    def test_stats_refuse_a_quick_draft_with_promoted_rights_or_timeline(self):
        for field, value in (("rights_status", "ALLOWED"), ("timeline_id", "timeline-1"), ("vision_status", "PASS")):
            draft = adapt_quick_annotation(sample_v01())
            draft["dataset"][field] = value
            with self.subTest(field=field), self.assertRaises(QuickAnnotationError) as caught:
                summarize_quick_annotation(draft)
            self.assertEqual(caught.exception.code, "UNSAFE_DRAFT_PROMOTION")

    def test_synthetic_source_cannot_be_mixed_into_human_annotation(self):
        payload = sample_v01()
        payload["dataset_class"] = "HUMAN_QUICK_DRAFT"
        payload["dataset_id"] = "dataset-user-1"
        payload["match_id"] = "match-user-1"
        payload["video_context"]["source_id"] = "SIMULATED_ONLY:source-001"
        for index, point in enumerate(payload["points"], 1):
            point["point_id"] = f"match-user-1/g01/p{index:03d}"
        with self.assertRaises(QuickAnnotationError) as caught:
            adapt_quick_annotation(payload)
        self.assertEqual(caught.exception.code, "SIMULATED_CANNOT_BE_HUMAN")

    def test_v02_preserves_ten_all_server_rotation_without_changing_v01_rows(self):
        payload = sample_v02()
        payload["points"] = []
        for point_number in range(1, 23):
            payload["points"].append({
                "point_id": f"SIMULATED_ONLY%3Aquick-match-v02-001/g01/p{point_number:03d}",
                "server": "unknown", "winner": "unknown", "observed_tactics": {},
                "rally_start_ms": None, "rally_end_ms": None,
                "observed_rally_stage": "UNKNOWN",
            })
        rows = [point["protocol_fields"] for point in adapt_quick_annotation(payload)["points"]]
        self.assertEqual([rows[index]["server"] for index in (19, 20, 21)], ["opponent", "player", "opponent"])
        self.assertEqual(rows[20]["server_score_before"], "unknown")

    def test_cli_can_write_stats_sidecar_without_changing_draft_or_csv(self):
        script = ROOT / "scripts" / "run_quick_annotation.py"
        fixture = ROOT / "fixtures" / "quick-annotation-v0.2-valid-simulated.json"
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            paths = [folder / "draft.json", folder / "rows.csv", folder / "stats.json"]
            result = subprocess.run([
                sys.executable, str(script), "--input", str(fixture),
                "--output-json", str(paths[0]), "--output-csv", str(paths[1]),
                "--output-stats-json", str(paths[2]), "--display-caution-threshold", "2",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            draft = json.loads(paths[0].read_text(encoding="utf-8"))
            stats = json.loads(paths[2].read_text(encoding="utf-8"))
            self.assertEqual(draft["contract_version"], "ptti.quick-annotation/0.2")
            self.assertEqual(stats["contract_version"], "ptti.quick-annotation-stats/0.1")
            self.assertEqual(stats["evidence_status"], "SIMULATED_ONLY")
            self.assertIn("automatic_vision_promotion", stats)
            self.assertEqual(stats["rally_stage_distribution"]["sample_status"], "DESCRIPTIVE_ONLY")
            self.assertFalse(stats["rally_stage_distribution"]["threshold_is_significance_test"])

    def test_versioned_input_and_stats_schemas_validate_real_outputs(self):
        schema_dir = ROOT / "contracts"
        for schema_name, payload in (
            ("quick-annotation-v0.1.schema.json", sample_v01()),
            ("quick-annotation-v0.2.schema.json", sample_v02()),
        ):
            schema = json.loads((schema_dir / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(payload)), [], schema_name)
        v01_schema = json.loads((schema_dir / "quick-annotation-v0.1.schema.json").read_text(encoding="utf-8"))
        self.assertTrue(list(Draft202012Validator(v01_schema).iter_errors(sample_v02())))
        human_with_synthetic_source = sample_v01()
        human_with_synthetic_source["dataset_class"] = "HUMAN_QUICK_DRAFT"
        human_with_synthetic_source["dataset_id"] = "dataset-user-001"
        human_with_synthetic_source["match_id"] = "match-user-001"
        for index, point in enumerate(human_with_synthetic_source["points"], 1):
            point["point_id"] = f"match-user-001/g01/p{index:03d}"
        self.assertTrue(list(Draft202012Validator(v01_schema).iter_errors(human_with_synthetic_source)))
        stats_schema = json.loads((schema_dir / "quick-annotation-stats-v0.1.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(stats_schema)
        stats = summarize_quick_annotation(adapt_quick_annotation(sample_v02()))
        self.assertEqual(list(Draft202012Validator(stats_schema).iter_errors(stats)), [])

        bad = sample_v02()
        bad["points"][0]["observed_rally_stage"] = "ATTACKED_ON_THIRD"
        errors = list(Draft202012Validator(json.loads((schema_dir / "quick-annotation-v0.2.schema.json").read_text(encoding="utf-8"))).iter_errors(bad))
        self.assertTrue(errors)

    def test_display_caution_threshold_is_configurable_but_not_a_significance_test(self):
        draft = adapt_quick_annotation(sample_v02())
        stats = summarize_quick_annotation(draft, display_caution_threshold=2)
        self.assertEqual(stats["metrics"]["server_point_win_rate"]["display_caution_threshold"], 2)
        self.assertEqual(stats["metrics"]["server_point_win_rate"]["sample_status"], "DESCRIPTIVE_ONLY")
        self.assertFalse(stats["metrics"]["server_point_win_rate"]["threshold_is_significance_test"])
        with self.assertRaises(QuickAnnotationError) as caught:
            summarize_quick_annotation(draft, display_caution_threshold=0)
        self.assertEqual(caught.exception.code, "INVALID_DISPLAY_THRESHOLD")


if __name__ == "__main__":
    unittest.main()
