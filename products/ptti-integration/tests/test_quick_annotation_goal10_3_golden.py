from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quick_annotation import adapt_quick_annotation, summarize_quick_annotation  # noqa: E402


class QuickAnnotationGoal103GoldenTests(unittest.TestCase):
    def test_cross_endpoint_golden_counts_and_evidence_boundaries(self):
        golden_path = ROOT / "fixtures" / "quick-annotation-v0.2-cross-endpoint-golden.json"
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        input_path = ROOT / "fixtures" / golden["input_fixture"]
        input_bytes = input_path.read_bytes()
        self.assertEqual(hashlib.sha256(input_bytes).hexdigest(), golden["input_sha256"])

        payload = json.loads(input_bytes.decode("utf-8"))
        self.assertEqual(payload["contract_version"], golden["input_contract_version"])
        self.assertEqual(payload["dataset_class"], golden["dataset_class"])
        draft = adapt_quick_annotation(payload)
        stats = summarize_quick_annotation(draft)
        expected = golden["expected"]

        self.assertEqual(stats["sample"]["point_count"], expected["points"]["supplied_count"])
        self.assertEqual(stats["sample"]["score_known_count"], expected["points"]["valid_score_count"])
        self.assertEqual(stats["metrics"]["score_record_coverage"]["denominator"], expected["points"]["score_denominator"])
        self.assertEqual(stats["sample"]["score_unknown_count"], expected["points"]["unknown_winner_count"])

        time_ranges = stats["metrics"]["time_range_coverage"]
        self.assertEqual(time_ranges["numerator"], expected["time_ranges"]["duration_checked_count"])
        self.assertEqual(time_ranges["denominator"], expected["time_ranges"]["known_score_denominator"])
        self.assertEqual(time_ranges["missing_count"], expected["time_ranges"]["missing_or_unknown_count"])
        self.assertEqual(stats["metrics"]["timeline_bound_review_coverage"]["numerator"], expected["time_ranges"]["timeline_bound_count"])

        dataset = draft["dataset"]
        self.assertEqual(dataset["dataset_class"], "SIMULATED_ONLY")
        self.assertEqual(dataset["source_link_status"], expected["sources"]["source_link_status"])
        self.assertEqual(dataset["rights_status"], expected["sources"]["rights_status"])
        self.assertIsNone(dataset["source_video_sha256"])
        self.assertIsNone(dataset["timeline_id"])
        self.assertEqual(dataset["vision_status"], expected["quality"]["vision_status"])
        self.assertEqual(len([dataset["source_id"]]) if dataset["source_id"] else 0,
                         expected["sources"]["referenced_source_count"])
        independently_verified = int(dataset["source_link_status"] == "INDEPENDENTLY_VERIFIED")
        self.assertEqual(independently_verified, expected["sources"]["independently_verified_source_count"])

        playable = sum(
            point["timestamp"]["timeline_binding"] == "BOUND"
            and dataset["source_video_sha256"] is not None
            and point["timestamp"]["start_ms"] is not None
            and point["timestamp"]["end_ms"] is not None
            for point in draft["points"]
        )
        self.assertEqual(playable, expected["playback"]["current_session_playable_count"])
        self.assertEqual(len(draft["points"]), expected["playback"]["point_denominator"])

        stage = stats["rally_stage_distribution"]
        stage_expected = expected["observed_rally_stage"]
        self.assertEqual(stage["numerator"], stage_expected["counts"])
        self.assertEqual(sum(stage["numerator"].values()), stage_expected["observed_count"])
        self.assertEqual(stage["sample_count"], stage_expected["all_point_denominator"])
        self.assertEqual(stage["denominator"], stage_expected["distribution_denominator"])
        self.assertEqual(stage["missing_count"], stage_expected["unknown_or_omitted_count"])
        self.assertFalse(stage_expected["third_ball_attack_inferred"])
        self.assertEqual(stats["evidence_status"], expected["quality"]["evidence_status"])
        self.assertEqual(stats["metrics"]["score_record_coverage"]["sample_status"], expected["quality"]["score_coverage_sample_status"])
        self.assertEqual(time_ranges["sample_status"], expected["quality"]["time_range_sample_status"])
        self.assertEqual(stage["display_caution_threshold"], expected["quality"]["default_display_caution_threshold"])
        self.assertEqual(stage["sample_status"], expected["quality"]["stage_sample_status"])
        self.assertFalse(stage["threshold_is_significance_test"])

        third_ball = stats["metrics"]["third_ball_attack_rate"]
        third_ball_expected = expected["third_ball_attack"]
        self.assertEqual(third_ball["numerator"], third_ball_expected["explicit_yes_count"])
        self.assertEqual(third_ball["denominator"], third_ball_expected["known_value_denominator"])
        self.assertEqual(third_ball["sample_count"], third_ball_expected["all_point_denominator"])
        self.assertEqual(third_ball["missing_count"], third_ball_expected["unknown_or_unobserved_count"])


if __name__ == "__main__":
    unittest.main()
