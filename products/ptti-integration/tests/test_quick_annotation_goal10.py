from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from match_intelligence import POINT_FIELDS, parse_protocol_v03_csv  # noqa: E402
from quick_annotation import QUICK_ANNOTATION_VERSION, QuickAnnotationError, adapt_quick_annotation  # noqa: E402


SAMPLE = ROOT / "fixtures" / "quick-annotation-v0.1-valid-simulated.json"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


class QuickAnnotationGoal10Tests(unittest.TestCase):
    def test_simulated_input_converts_to_exact_parseable_21_field_draft(self):
        result = adapt_quick_annotation(load_sample())
        self.assertEqual(result["contract_version"], QUICK_ANNOTATION_VERSION)
        self.assertEqual(result["draft_status"], "SIMULATED_ONLY")
        self.assertEqual(result["protocol"]["fields"], list(POINT_FIELDS))
        self.assertTrue(result["protocol"]["rows_parseable"])
        self.assertFalse(result["protocol"]["formal_bundle_validated"])
        rows = parse_protocol_v03_csv(result["protocol"]["csv_utf8"].encode("utf-8"))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(set(row) == set(POINT_FIELDS) for row in rows))
        self.assertFalse(result["formal_report_eligibility"]["eligible"])
        self.assertEqual(result["review_queue"]["existing_training_quality_audit"], "NOT_RUN")

    def test_score_and_service_rules_derive_only_with_complete_prior_context(self):
        result = adapt_quick_annotation(load_sample())
        rows = [point["protocol_fields"] for point in result["points"]]
        self.assertEqual([(row["server"], row["receiver"]) for row in rows], [
            ("player", "opponent"), ("player", "opponent"), ("opponent", "player"),
            ("opponent", "player"), ("player", "opponent"),
        ])
        self.assertEqual([(rows[i]["server_score_before"], rows[i]["receiver_score_before"]) for i in range(5)],
                         [(0, 0), (1, 0), (1, 1), (1, 2), (2, 2)])
        self.assertEqual(result["points"][1]["field_derivation"]["score"],
                         "RULE_DERIVED_FROM_COMPLETE_DECLARED_GAME_AND_KNOWN_WINNERS")

    def test_partial_context_preserves_unknown_scores_and_unobserved_tactics(self):
        payload = load_sample()
        payload["rules_context"]["games"][0]["coverage"] = "PARTIAL_OR_UNKNOWN"
        result = adapt_quick_annotation(payload)
        row = result["points"][1]["protocol_fields"]
        self.assertEqual((row["server_score_before"], row["receiver_score_before"]), ("unknown", "unknown"))
        self.assertEqual(row["serve_spin"], "unknown")
        self.assertEqual(row["serve_location"], "unknown")
        self.assertEqual(row["rally_length"], "unknown")
        self.assertEqual(result["dataset"]["rights_status"], "UNKNOWN")

    def test_unknown_prior_winner_stops_later_score_derivation(self):
        payload = load_sample()
        payload["points"][1]["winner"] = "unknown"
        result = adapt_quick_annotation(payload)
        self.assertEqual(result["points"][1]["protocol_fields"]["server_score_before"], 1)
        self.assertEqual(result["points"][2]["protocol_fields"]["server_score_before"], "unknown")
        self.assertEqual(result["points"][3]["protocol_fields"]["receiver_score_before"], "unknown")

    def test_winner_does_not_infer_spin_placement_receive_or_shot_count(self):
        payload = load_sample()
        payload["points"][0]["observed_tactics"] = {}
        payload["points"][0]["winner"] = "player"
        row = adapt_quick_annotation(payload)["points"][0]["protocol_fields"]
        for field in ("serve_spin", "serve_location", "receive_type", "third_ball_side", "rally_length"):
            self.assertEqual(row[field], "unknown", field)

    def test_no_source_or_rights_claim_is_created_from_match_or_video_id(self):
        payload = load_sample()
        payload["video_context"]["source_id"] = None
        result = adapt_quick_annotation(payload)
        dataset = result["dataset"]
        self.assertEqual(dataset["source_link_status"], "UNBOUND")
        self.assertEqual(dataset["source_video_sha256"], None)
        self.assertEqual(dataset["timeline_id"], None)
        self.assertEqual(dataset["local_analysis_permission"], "UNKNOWN")
        self.assertEqual(dataset["embed_permission"], "UNKNOWN")
        self.assertEqual(dataset["vision_status"], "NOT_TESTED")

    def test_human_input_is_a_draft_and_user_selected_identity_is_unverified(self):
        payload = load_sample()
        payload["dataset_class"] = "HUMAN_QUICK_DRAFT"
        payload["dataset_id"] = "quick-dataset-user-session-1"
        payload["match_id"] = "web-match-selected-by-user"
        for point in payload["points"]:
            point["point_id"] = point["point_id"].replace(
                "SIMULATED_ONLY%3Aquick-match-001", "web-match-selected-by-user"
            )
        result = adapt_quick_annotation(payload)
        self.assertEqual(result["draft_status"], "LIGHT_ANNOTATION_DRAFT")
        self.assertEqual(result["dataset"]["match_link_status"], "USER_SELECTED_UNVERIFIED")
        self.assertEqual(result["evidence_status"], "REVIEW_REQUIRED")
        self.assertFalse(result["formal_report_eligibility"]["eligible"])

    def test_duplicate_point_id_rejected(self):
        payload = load_sample()
        payload["points"][1]["point_id"] = payload["points"][0]["point_id"]
        self.assertReject(payload, "DUPLICATE_POINT_ID")

    def test_point_match_id_mismatch_rejected(self):
        payload = load_sample()
        payload["points"][0]["point_id"] = "other-match/g01/p001"
        self.assertReject(payload, "POINT_ID_MATCH_MISMATCH")

    def test_out_of_order_point_ids_rejected(self):
        payload = load_sample()
        payload["points"][0], payload["points"][1] = payload["points"][1], payload["points"][0]
        self.assertReject(payload, "POINT_ORDER_INVALID")

    def test_gap_is_parseable_csv_but_blocks_formal_protocol_sequence(self):
        payload = load_sample()
        payload["points"].pop(1)
        result = adapt_quick_annotation(payload)
        self.assertTrue(result["protocol"]["rows_parseable"])
        self.assertFalse(result["protocol"]["sequence_valid"])
        self.assertTrue(any("contiguous Protocol v0.3 sequences" in blocker
                            for blocker in result["formal_report_eligibility"]["blockers"]))

    def test_unknown_version_and_extra_fields_rejected(self):
        payload = load_sample()
        payload["contract_version"] = "ptti.quick-annotation/0.2"
        self.assertReject(payload, "UNSUPPORTED_VERSION")
        payload = load_sample()
        payload["unreviewed_rights"] = "ALLOWED"
        self.assertReject(payload, "INVALID_FIELDS")

    def test_simulated_namespace_required_for_dataset_and_match(self):
        payload = load_sample()
        payload["dataset_id"] = "dataset-looks-real"
        self.assertReject(payload, "SIMULATED_NAMESPACE_REQUIRED")
        payload = load_sample()
        payload["match_id"] = "match-looks-real"
        self.assertReject(payload, "SIMULATED_NAMESPACE_REQUIRED")

    def test_invalid_tactical_label_and_unobserved_input_keys_rejected(self):
        for fixture, code in (("quick-annotation-v0.1-bad-tactic.json", "INVALID_TACTICAL_VALUE"),):
            payload = json.loads((ROOT / "fixtures" / fixture).read_text(encoding="utf-8"))
            self.assertReject(payload, code)
        payload = load_sample()
        payload["points"][0]["observed_tactics"]["point_winner"] = "player"
        self.assertReject(payload, "INVALID_TACTICAL_FIELDS")

    def test_invalid_time_ranges_and_unavailable_duration_rejected(self):
        bad = json.loads((ROOT / "fixtures" / "quick-annotation-v0.1-bad-time-range.json").read_text(encoding="utf-8"))
        self.assertReject(bad, "TIME_RANGE_OUT_OF_BOUNDS")
        payload = load_sample()
        payload["points"][0]["rally_end_ms"] = payload["video_context"]["duration_ms"] + 1
        self.assertReject(payload, "TIME_RANGE_OUT_OF_BOUNDS")
        payload = load_sample()
        payload["video_context"].update(duration_ms=None, duration_status="UNKNOWN")
        self.assertReject(payload, "VIDEO_DURATION_REQUIRED")
        payload = load_sample()
        payload["points"][0]["rally_start_ms"] = None
        self.assertReject(payload, "INCOMPLETE_TIME_RANGE")

    def test_server_rotation_conflict_rejected(self):
        payload = load_sample()
        payload["points"][2]["server"] = "player"
        self.assertReject(payload, "SERVICE_ROTATION_CONFLICT")

    def test_service_rotation_changes_to_each_point_at_deuce(self):
        payload = load_sample()
        payload["points"] = []
        for point_number in range(1, 23):
            payload["points"].append({
                "point_id": f"SIMULATED_ONLY%3Aquick-match-001/g01/p{point_number:03d}",
                "server": "unknown", "winner": "unknown", "observed_tactics": {},
                "rally_start_ms": None, "rally_end_ms": None,
            })
        result = adapt_quick_annotation(payload)
        rows = [point["protocol_fields"] for point in result["points"]]
        self.assertEqual(rows[19]["server"], "opponent")
        self.assertEqual(rows[20]["server"], "player")
        self.assertEqual(rows[21]["server"], "opponent")
        self.assertEqual(rows[20]["server_score_before"], "unknown")

    def test_key_point_candidate_requires_known_derived_9_all_score(self):
        payload = load_sample()
        payload["points"] = []
        for point_number in range(1, 20):
            payload["points"].append({
                "point_id": f"SIMULATED_ONLY%3Aquick-match-001/g01/p{point_number:03d}",
                "server": "unknown", "winner": "player" if point_number % 2 else "opponent",
                "observed_tactics": {}, "rally_start_ms": None, "rally_end_ms": None,
            })
        payload["points"][-1]["winner"] = "unknown"
        result = adapt_quick_annotation(payload)
        self.assertEqual(result["points"][-1]["score_before_player_opponent"], {"player": 9, "opponent": 9})
        self.assertEqual(result["points"][-1]["key_point_status"], "RULE_DERIVED_CANDIDATE")
        payload["rules_context"]["games"][0]["coverage"] = "PARTIAL_OR_UNKNOWN"
        partial = adapt_quick_annotation(payload)
        self.assertEqual(partial["points"][-1]["key_point_status"], "UNKNOWN_SCORE")

    def test_timestamp_is_range_checked_but_never_timeline_bound(self):
        result = adapt_quick_annotation(load_sample())
        timestamp = result["points"][0]["timestamp"]
        self.assertEqual(timestamp["range_status"], "CHECKED_AGAINST_USER_REPORTED_DURATION")
        self.assertEqual(timestamp["timeline_binding"], "UNBOUND")
        self.assertIn("binding=UNBOUND", result["points"][0]["protocol_fields"]["video_timestamp"])
        self.assertIsNone(result["dataset"]["pts"])
        self.assertIsNone(result["dataset"]["time_base"])

    def test_cli_writes_draft_json_and_protocol_csv(self):
        script = ROOT / "scripts" / "run_quick_annotation.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, csv_path = root / "draft.json", root / "points.csv"
            result = subprocess.run([
                sys.executable, str(script), "--input", str(SAMPLE),
                "--output-json", str(json_path), "--output-csv", str(csv_path),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("formal_report_eligible=false", result.stdout)
            self.assertEqual(len(parse_protocol_v03_csv(csv_path.read_bytes())), 5)
            self.assertEqual(output["draft_status"], "SIMULATED_ONLY")
            repeated = subprocess.run([
                sys.executable, str(script), "--input", str(SAMPLE),
                "--output-json", str(json_path), "--output-csv", str(csv_path),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)

    def assertReject(self, payload: dict, code: str) -> None:
        with self.assertRaises(QuickAnnotationError) as caught:
            adapt_quick_annotation(payload)
        self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
