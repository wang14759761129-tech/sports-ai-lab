import math
import copy
import hashlib
import json
import tempfile
import sys
import unittest
from pathlib import Path

INTEGRATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRATION_ROOT))

from match_intelligence import (
    AnalysisValidationError,
    POINT_FIELDS,
    analyze_bundle,
    guard_match_media_linkage,
    build_synthetic_demo,
    change_point_annotation,
    demo_with_mutation,
    import_manual_csv,
    parse_protocol_v03_csv,
    serialize_protocol_csv,
    validate_bundle,
)


class MatchIntelligenceDemoTests(unittest.TestCase):
    def setUp(self):
        self.bundle = build_synthetic_demo()

    def test_fixture_is_24_points_and_preserves_exact_21_field_protocol(self):
        self.assertEqual(len(self.bundle["points"]), 24)
        self.assertEqual(tuple(self.bundle["points"][0]), POINT_FIELDS)
        self.assertTrue(all(set(row) == set(POINT_FIELDS) for row in self.bundle["points"]))
        self.assertEqual(self.bundle["dataset"]["dataset_class"], "SIMULATED_ONLY")
        self.assertTrue(self.bundle["dataset"]["match_id"].startswith("SIMULATED_ONLY:"))
        self.assertIsNone(self.bundle["dataset"]["source_binding"]["source_sha256"])
        self.assertIsNone(self.bundle["dataset"]["source_binding"]["timeline_id"])
        self.assertEqual(self.bundle, build_synthetic_demo())

    def test_summary_counts_points_serves_third_ball_and_unknowns_with_denominators(self):
        result = analyze_bundle(self.bundle)
        summary = result["summary"]
        self.assertEqual(summary["point_count"], 24)
        self.assertEqual(summary["point_wins"]["counts"], {"player": 13, "opponent": 11})
        self.assertEqual(summary["point_wins"]["denominator"], 24)
        self.assertEqual(summary["rally_length"]["denominator"], 22)
        self.assertEqual(summary["rally_length"]["unknown_count"], 2)
        self.assertEqual(summary["third_ball_attack_rate"]["denominator"], 18)
        self.assertEqual(summary["third_ball_attack_rate"]["unresolved_eligibility"], 2)
        self.assertEqual(summary["third_ball_attack_rate"]["not_applicable"], 4)
        self.assertEqual(summary["third_ball_immediate_outcome"]["distribution"]["row_count"], 12)
        self.assertIn("not point winner", result["limitations"][1])
        self.assertEqual(result["dataset"]["human_review_status"], "SIMULATED_ONLY")

    def test_demo_mutation_reports_expected_and_observed_mean_change(self):
        result = demo_with_mutation(self.bundle)
        self.assertEqual(result["evidence_class"], "SIMULATED_ONLY")
        self.assertEqual(result["change"]["expected_mean_delta"], round(2 / 22, 6))
        self.assertEqual(result["change"]["actual_mean_delta"], round(2 / 22, 6))

    def test_editing_one_rally_annotation_recomputes_descriptive_summary(self):
        bundle = copy.deepcopy(self.bundle)
        before = analyze_bundle(bundle)

        updated = change_point_annotation(
            bundle, game_number=1, point_number=1, field="rally_length", value="7"
        )
        after = analyze_bundle(updated)

        self.assertEqual(before["dataset"]["dataset_class"], "SIMULATED_ONLY")
        self.assertEqual(before["summary"]["point_count"], 24)
        self.assertEqual(before["summary"]["rally_length"]["denominator"], 22)
        self.assertEqual(after["summary"]["rally_length"]["denominator"], 22)
        self.assertEqual(after["summary"]["rally_length"]["numerator_sum"],
                         before["summary"]["rally_length"]["numerator_sum"] + 2)
        self.assertTrue(math.isclose(
            after["summary"]["rally_length"]["mean"] - before["summary"]["rally_length"]["mean"],
            2 / 22,
            abs_tol=0.0001,
        ))
        provenance = after["dataset"]["provenance"]
        self.assertEqual(provenance["method"], "SIMULATED_INTERACTIVE_EDIT")
        self.assertEqual(provenance["parent_dataset_id"], self.bundle["dataset"]["dataset_id"])
        self.assertEqual(provenance["parent_input_sha256"], before["input_sha256"])
        self.assertEqual(provenance["edit"], {
            "point_id": "SIMULATED_ONLY%3Agoal07-match-001/g01/p001",
            "field": "rally_length", "before": 5, "after": 7,
        })
        self.assertTrue(after["dataset"]["dataset_id"].startswith("SIMULATED_ONLY:edit-"))
        self.assertEqual(after["dataset"]["human_review_status"], "SIMULATED_ONLY")
        self.assertIsNone(after["dataset"]["source_binding"]["source_sha256"])

    def test_manual_annotation_edit_requires_reimport_to_keep_csv_hash_accurate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            source.write_bytes(b"local-only test fixture bytes")
            csv_bytes = serialize_protocol_csv(self.bundle).replace(
                b"SIMULATED_ONLY:goal07-match-001", b"match:manual-demo"
            )
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = {
                "manifest_version": "ptti.manual-point-annotation/0.1", "dataset_id": "manual:demo",
                "match_id": "match:manual-demo", "source_id": "source:manual-demo", "source_sha256": source_sha,
                "annotator_ref": "reviewer:test", "annotated_at": "2026-10-13T12:00:00Z",
                "evidence_ref": "annotation:test", "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
            }
            imported = import_manual_csv(csv_bytes, manifest, source)
            with self.assertRaisesRegex(AnalysisValidationError, "MANUAL_ANNOTATIONS_REQUIRE_REIMPORT"):
                change_point_annotation(imported, game_number=1, point_number=1, field="rally_length", value=7)

    def test_edit_does_not_mutate_original_bundle(self):
        original = copy.deepcopy(self.bundle)
        change_point_annotation(self.bundle, game_number=1, point_number=1, field="rally_length", value=7)
        self.assertEqual(self.bundle, original)

    def test_simulated_edit_provenance_rejects_tampered_parent_and_after_value(self):
        edited = change_point_annotation(self.bundle, game_number=1, point_number=1, field="rally_length", value=7)
        bad_parent = copy.deepcopy(edited)
        bad_parent["dataset"]["provenance"]["parent_input_sha256"] = "f" * 64
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_SIMULATION_EDIT_PROVENANCE"):
            validate_bundle(bad_parent)
        bad_after = copy.deepcopy(edited)
        bad_after["dataset"]["provenance"]["edit"]["after"] = 9
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_SIMULATION_EDIT_PROVENANCE"):
            validate_bundle(bad_after)

    def test_duplicate_natural_point_id_is_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][1]["point_number"] = 1
        with self.assertRaisesRegex(AnalysisValidationError, "DUPLICATE_POINT_ID"):
            validate_bundle(invalid)

    def test_wrong_match_association_is_rejected_without_name_guessing(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][0]["match_id"] = "another-match-with-similar-title"
        with self.assertRaisesRegex(AnalysisValidationError, "MATCH_ASSOCIATION_MISMATCH"):
            validate_bundle(invalid)

    def test_missing_or_extra_protocol_field_is_rejected(self):
        missing = copy.deepcopy(self.bundle)
        del missing["points"][0]["serve_spin"]
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_POINT_FIELDS"):
            validate_bundle(missing)
        extra = copy.deepcopy(self.bundle)
        extra["points"][0]["athlete_name"] = "invented"
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_POINT_FIELDS"):
            validate_bundle(extra)

    def test_invalid_category_and_blank_notes_are_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][0]["serve_length"] = "very_short"
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_CATEGORY"):
            validate_bundle(invalid)
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][0]["notes"] = "  "
        with self.assertRaisesRegex(AnalysisValidationError, "MISSING_ANNOTATION_NOTE"):
            validate_bundle(invalid)

    def test_out_of_order_points_are_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][0], invalid["points"][1] = invalid["points"][1], invalid["points"][0]
        with self.assertRaisesRegex(AnalysisValidationError, "POINT_SEQUENCE_INVALID"):
            validate_bundle(invalid)

    def test_invalid_service_order_and_score_progression_are_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][1]["server"] = "opponent"
        invalid["points"][1]["receiver"] = "player"
        with self.assertRaisesRegex(AnalysisValidationError, "SERVICE_ORDER_INVALID"):
            validate_bundle(invalid)
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][1]["receiver_score_before"] = 3
        with self.assertRaisesRegex(AnalysisValidationError, "SCORE_PROGRESSION_INVALID"):
            validate_bundle(invalid)

    def test_conflicting_winner_outcome_and_third_ball_eligibility_are_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][0]["point_outcome"] = "loss"
        with self.assertRaisesRegex(AnalysisValidationError, "POINT_OUTCOME_CONFLICT"):
            validate_bundle(invalid)
        invalid = copy.deepcopy(self.bundle)
        invalid["points"][1]["third_ball_side"] = "forehand"
        with self.assertRaisesRegex(AnalysisValidationError, "THIRD_BALL_ELIGIBILITY_CONFLICT"):
            validate_bundle(invalid)

    def test_unknown_contract_and_dataset_versions_are_rejected(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["contract_version"] = "ptti.match-media/0.2"
        with self.assertRaisesRegex(AnalysisValidationError, "UNSUPPORTED_ANALYSIS_VERSION"):
            validate_bundle(invalid)
        invalid = copy.deepcopy(self.bundle)
        invalid["dataset"]["source_protocol"]["version"] = "0.4"
        with self.assertRaisesRegex(AnalysisValidationError, "UNSUPPORTED_SOURCE_PROTOCOL"):
            validate_bundle(invalid)

    def test_simulated_bundle_cannot_export_to_real_match_media(self):
        with self.assertRaisesRegex(AnalysisValidationError, "SIMULATED_ONLY_NOT_EXPORTABLE"):
            guard_match_media_linkage(self.bundle)

    def test_21_field_csv_round_trip_keeps_uncertainty_and_simulated_identity(self):
        parsed = parse_protocol_v03_csv(serialize_protocol_csv(self.bundle))
        self.assertEqual(len(parsed), 24)
        self.assertEqual(parsed[0]["match_id"], "SIMULATED_ONLY:goal07-match-001")
        self.assertEqual(parsed[3]["rally_length"], "unknown")
        self.assertEqual(parsed[3]["third_ball_attack"], "unclear")

    def test_simulated_bundle_cannot_claim_a_real_source_binding(self):
        invalid = copy.deepcopy(self.bundle)
        invalid["dataset"]["source_binding"]["source_id"] = "real-source-01"
        with self.assertRaisesRegex(AnalysisValidationError, "SIMULATION_SOURCE_BINDING_FORBIDDEN"):
            validate_bundle(invalid)

    def test_json_schema_accepts_fixture_and_rejects_synthetic_real_binding(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional for this standard-library runtime")
        schema_path = INTEGRATION_ROOT / "contracts" / "match-intelligence-v0.1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(set(schema["$defs"]["point"]["properties"]), set(POINT_FIELDS))
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(self.bundle)), [])
        edited = change_point_annotation(self.bundle, game_number=1, point_number=1, field="rally_length", value="7")
        self.assertEqual(list(validator.iter_errors(edited)), [])
        edited["dataset"]["provenance"]["parent_input_sha256"] = "not-a-sha"
        self.assertTrue(list(validator.iter_errors(edited)))
        invalid = copy.deepcopy(self.bundle)
        invalid["dataset"]["source_binding"]["source_id"] = "real-source-001"
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_manual_manifest_schema_is_versioned_and_forbids_synthetic_match_ids(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional for this standard-library runtime")
        path = INTEGRATION_ROOT / "contracts" / "manual-point-annotation-v0.1.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        manifest = {
            "manifest_version": "ptti.manual-point-annotation/0.1", "dataset_id": "annotation:test-01",
            "match_id": "match:explicit-id", "source_id": "source:explicit-id", "source_sha256": "a" * 64,
            "annotator_ref": "reviewer:local-01", "annotated_at": "2026-10-13T12:00:00Z",
            "evidence_ref": "annotation-record:01", "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
        }
        self.assertEqual(list(validator.iter_errors(manifest)), [])
        manifest["match_id"] = "SIMULATED_ONLY:goal07-match-001"
        self.assertTrue(list(validator.iter_errors(manifest)))

    def test_committed_json_demo_is_reproducible(self):
        result_path = INTEGRATION_ROOT / "generated" / "goal07-simulated-analysis.json"
        saved = json.loads(result_path.read_text(encoding="utf-8"))
        expected = demo_with_mutation(self.bundle)
        self.assertEqual(saved, expected)
        self.assertNotEqual(saved["before"]["input_sha256"], saved["after"]["input_sha256"])

    def test_csv_export_contains_the_21_protocol_fields_and_no_sidecar_columns(self):
        encoded = serialize_protocol_csv(self.bundle).decode("utf-8")
        self.assertEqual(tuple(encoded.splitlines()[0].split(",")), POINT_FIELDS)
        self.assertEqual(len(encoded.splitlines()), 25)
        self.assertIn("SIMULATED_ONLY:", encoded.splitlines()[1])  # Point identity stays in the synthetic namespace.

    def test_manual_import_refuses_pts_claims_not_supported_by_v03(self):
        csv_bytes = serialize_protocol_csv(self.bundle)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            source.write_bytes(b"test-only bytes; not a video")
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest = {
                "manifest_version": "ptti.manual-point-annotation/0.1",
                "dataset_id": "manual-test-only", "match_id": "test-only-match", "source_id": "test-only-source",
                "source_sha256": sha, "annotator_ref": "test-only", "annotated_at": "2026-10-13T12:00:00Z",
                "evidence_ref": "test-only", "timestamp_semantics": "PTS_BOUND",
            }
            with self.assertRaisesRegex(AnalysisValidationError, "PTS_BINDING_UNSUPPORTED_BY_PROTOCOL"):
                import_manual_csv(csv_bytes, manifest, source)

    def test_manual_import_requires_selected_source_and_matching_hash(self):
        csv_bytes = b"not consumed before source checks"
        manifest = {
            "manifest_version": "ptti.manual-point-annotation/0.1",
            "dataset_id": "manual-test-only", "match_id": "test-only-match", "source_id": "test-only-source",
            "source_sha256": "0" * 64, "annotator_ref": "test-only", "annotated_at": "2026-10-13T12:00:00Z",
            "evidence_ref": "test-only", "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
        }
        with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_FILE_NOT_FOUND"):
            import_manual_csv(csv_bytes, manifest, Path("missing-source-file"))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            source.write_bytes(b"test-only bytes; not a video")
            with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_HASH_MISMATCH"):
                import_manual_csv(csv_bytes, manifest, source)

    def test_manual_import_rejects_non_protocol_csv_after_source_identity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            source.write_bytes(b"test-only bytes; not a video")
            manifest = {
                "manifest_version": "ptti.manual-point-annotation/0.1",
                "dataset_id": "manual-test-only", "match_id": "test-only-match", "source_id": "test-only-source",
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "annotator_ref": "test-only",
                "annotated_at": "2026-10-13T12:00:00Z", "evidence_ref": "test-only",
                "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
            }
            with self.assertRaisesRegex(AnalysisValidationError, "PROTOCOL_FIELDS_MISMATCH"):
                import_manual_csv(b"match_id,point_number\nfoo,1\n", manifest, source)


if __name__ == "__main__":
    unittest.main()
