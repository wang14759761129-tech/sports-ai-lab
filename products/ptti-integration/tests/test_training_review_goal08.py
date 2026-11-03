"""GOAL 08 local-only processing tests; all sample rows are test data."""
import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from match_intelligence import (  # noqa: E402
    AnalysisValidationError, POINT_FIELDS, build_synthetic_demo, change_point_annotation,
    parse_protocol_v03_csv, serialize_protocol_csv,
)
from training_review import (  # noqa: E402
    REVIEW_VERSION, build_training_report, csv_template, import_human_training_csv,
    import_simulated_csv, synthetic_declaration,
)


def raw_csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=POINT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class TrainingReviewTests(unittest.TestCase):
    def setUp(self):
        self.base = build_synthetic_demo()
        self.original_csv = serialize_protocol_csv(self.base)
        self.original_decl = synthetic_declaration(self.original_csv)

    def test_blank_template_has_exact_importable_21_field_header(self):
        template = csv_template()
        self.assertEqual(template.decode("utf-8").strip().split(","), list(POINT_FIELDS))
        self.assertEqual(parse_protocol_v03_csv(template), [])

    def test_csv_to_report_preserves_simulated_evidence_denominators_and_point_refs(self):
        bundle = import_simulated_csv(self.original_csv, self.original_decl)
        report = build_training_report(bundle, csv_sha256=self.original_decl["csv_sha256"],
                                       generated_at="2026-10-13T00:00:00Z")
        self.assertEqual(report["report_version"], REVIEW_VERSION)
        self.assertEqual(report["sample"]["point_count"], 24)
        self.assertEqual(report["metrics"]["server_point_win_rate"]["numerator"], 13)
        self.assertEqual(report["metrics"]["receiver_point_win_rate"]["numerator"], 11)
        self.assertEqual(report["metrics"]["third_ball_attack_rate"]["denominator"], 18)
        self.assertEqual(report["metrics"]["third_ball_attack_rate"]["missing_count"], 2)
        self.assertEqual(report["metrics"]["third_ball_immediate_success"]["numerator"], 3)
        self.assertEqual(report["metrics"]["third_ball_point_conversion"]["numerator"], 7)
        self.assertEqual(report["metrics"]["rally_length_mean"]["denominator"], 22)
        self.assertEqual(report["metrics"]["rally_length_mean"]["missing_count"], 2)
        self.assertEqual(report["metrics"]["key_point_player_win_rate"]["sample_count"], 10)
        self.assertEqual(report["dataset"]["evidence_status"], "SIMULATED_ONLY")
        self.assertIsNone(report["dataset"]["source_video_sha256"])
        self.assertIsNone(report["dataset"]["video_timeline"]["pts"])
        self.assertEqual(report["dataset"]["vision_status"], "NOT_TESTED")
        self.assertEqual(report["point_refs"][0]["csv_record_number"], 2)
        self.assertEqual(report["point_records"][0]["fields"]["rally_length"], 5)
        self.assertTrue(report["watchlist"])
        self.assertTrue(all(ref["point_id"] for ref in report["watchlist"]))

    def test_edit_then_reimport_changes_csv_hash_bundle_hash_and_expected_metric(self):
        original = import_simulated_csv(self.original_csv, self.original_decl)
        edited = change_point_annotation(original, game_number=1, point_number=1, field="rally_length", value=7)
        edited_csv = serialize_protocol_csv(edited)
        declaration = synthetic_declaration(edited_csv, parent_csv_sha256=self.original_decl["csv_sha256"])
        reimported = import_simulated_csv(edited_csv, declaration)
        before = build_training_report(original, csv_sha256=self.original_decl["csv_sha256"], generated_at="2026-10-13T00:00:00Z")
        after = build_training_report(reimported, csv_sha256=declaration["csv_sha256"], generated_at="2026-10-13T00:00:00Z")
        self.assertNotEqual(before["dataset"]["annotation_csv_sha256"], after["dataset"]["annotation_csv_sha256"])
        self.assertNotEqual(before["dataset"]["annotation_bundle_sha256"], after["dataset"]["annotation_bundle_sha256"])
        self.assertEqual(after["dataset"]["annotation_provenance"]["method"], "SIMULATED_INTERACTIVE_EDIT")
        self.assertEqual(after["metrics"]["rally_length_mean"]["numerator"], before["metrics"]["rally_length_mean"]["numerator"] + 2)
        self.assertEqual(after["metrics"]["rally_length_mean"]["denominator"], before["metrics"]["rally_length_mean"]["denominator"])
        self.assertEqual(after["metrics"]["server_point_win_rate"], before["metrics"]["server_point_win_rate"])
        self.assertEqual(before["point_records"][0]["fields"]["rally_length"], 5)
        self.assertEqual(after["point_records"][0]["fields"]["rally_length"], 7)

    def test_simulated_declaration_rejects_changed_bytes_and_fake_human_or_video_binding(self):
        invalid = copy.deepcopy(self.original_decl)
        invalid["dataset_class"] = "HUMAN_ANNOTATION"
        with self.assertRaisesRegex(AnalysisValidationError, "UNSUPPORTED_SYNTHETIC_DECLARATION"):
            import_simulated_csv(self.original_csv, invalid)
        invalid = copy.deepcopy(self.original_decl)
        invalid["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(AnalysisValidationError, "INVALID_SYNTHETIC_DECLARATION"):
            import_simulated_csv(self.original_csv, invalid)
        with self.assertRaisesRegex(AnalysisValidationError, "ANNOTATION_CSV_HASH_MISMATCH"):
            import_simulated_csv(self.original_csv + b" ", self.original_decl)

    def test_duplicate_point_id_illegal_field_wrong_score_order_and_unknown_version_reject(self):
        base_rows = copy.deepcopy(self.base["points"])
        cases = (
            ("duplicate-point", lambda rows: rows[1].update(point_number=1), "SYNTHETIC_IDENTITY_EDIT_FORBIDDEN"),
            ("invalid-field", lambda rows: rows[0].update(serve_length="super_short"), "INVALID_CATEGORY"),
            ("wrong-score", lambda rows: rows[1].update(server_score_before=99), "SYNTHETIC_IDENTITY_EDIT_FORBIDDEN"),
            ("wrong-order", lambda rows: rows.reverse(), "SYNTHETIC_ORIGIN_MISMATCH"),
        )
        for label, mutate, error in cases:
            with self.subTest(label=label):
                rows = copy.deepcopy(base_rows)
                mutate(rows)
                data = raw_csv(rows)
                declaration = synthetic_declaration(data, parent_csv_sha256=self.original_decl["csv_sha256"])
                with self.assertRaisesRegex(AnalysisValidationError, error):
                    import_simulated_csv(data, declaration)
        invalid = copy.deepcopy(self.original_decl)
        invalid["declaration_version"] = "ptti.training-simulated-declaration/9"
        with self.assertRaisesRegex(AnalysisValidationError, "UNSUPPORTED_SYNTHETIC_DECLARATION"):
            import_simulated_csv(self.original_csv, invalid)

    def _manual_test_inputs(self, directory: str):
        # This one-row record and byte file are ephemeral QA data, not a real match or video.
        row = copy.deepcopy(self.base["points"][0])
        row["match_id"] = "TEST_ONLY:manual-pipeline"
        row["notes"] = "TEST ONLY; no match, video, athlete, or rights have been verified."
        csv_bytes = raw_csv([row])
        source = Path(directory) / "test-only-source.bin"
        source.write_bytes(b"TEST ONLY: not a video")
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        manifest = {
            "manifest_version": "ptti.manual-point-annotation/0.1", "dataset_id": "TEST_ONLY:dataset",
            "match_id": row["match_id"], "source_id": "TEST_ONLY:source", "source_sha256": sha,
            "annotator_ref": "TEST_ONLY:reviewer", "annotated_at": "2026-10-13T12:00:00Z",
            "evidence_ref": "TEST_ONLY:annotation", "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
        }
        binding = {
            "binding_version": "ptti.training-source-binding/0.1", "dataset_id": manifest["dataset_id"],
            "match_id": manifest["match_id"], "source_id": manifest["source_id"],
            "local_asset_id": "TEST_ONLY:asset", "source_sha256": sha,
            "match_link_status": "HUMAN_REVIEWED_DECLARATION",
            "local_analysis_permission": "DECLARED_ALLOWED",
            "rights_basis_ref": "TEST_ONLY:no_real_rights", "reviewer_ref": "TEST_ONLY:reviewer",
            "reviewed_at": "2026-10-13T12:00:00Z", "analysis_method": "HUMAN_MANUAL",
        }
        return csv_bytes, source, manifest, binding

    def test_ephemeral_manual_pipeline_checks_byte_hash_but_never_claims_vision_or_audited_rights(self):
        with tempfile.TemporaryDirectory() as directory:
            data, source, manifest, binding = self._manual_test_inputs(directory)
            # No real video is shipped. Isolate the metadata probe in this test only.
            with patch("training_review._require_video_stream_metadata"):
                bundle = import_human_training_csv(data, manifest, source, binding)
            report = build_training_report(bundle, csv_sha256=hashlib.sha256(data).hexdigest(),
                                           generated_at="2026-10-13T12:00:00Z", binding=binding)
            self.assertEqual(report["dataset"]["source_video_sha256"], manifest["source_sha256"])
            self.assertEqual(report["dataset"]["evidence_status"], "DECLARED_NOT_INDEPENDENTLY_AUDITED")
            self.assertEqual(report["dataset"]["vision_status"], "NOT_TESTED")
            self.assertEqual(report["dataset"]["match_link_status"], "HUMAN_REVIEWED_DECLARATION_NOT_AUDITED")
            self.assertEqual(report["metrics"]["server_point_win_rate"]["sample_status"], "INSUFFICIENT_SAMPLE")
            self.assertNotIn(str(source), json.dumps(report))

    def test_manual_import_rejects_modified_source_bad_hash_wrong_link_vision_claim_and_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            data, source, manifest, binding = self._manual_test_inputs(directory)
            with patch("training_review._require_video_stream_metadata"):
                wrong = copy.deepcopy(binding)
                wrong["match_id"] = "another-match"
                with self.assertRaisesRegex(AnalysisValidationError, "MATCH_SOURCE_BINDING_MISMATCH"):
                    import_human_training_csv(data, manifest, source, wrong)
                wrong = copy.deepcopy(binding)
                wrong["analysis_method"] = "VISION"
                with self.assertRaisesRegex(AnalysisValidationError, "VISION_EVIDENCE_FORBIDDEN"):
                    import_human_training_csv(data, manifest, source, wrong)
                wrong = copy.deepcopy(binding)
                wrong["match_link_status"] = "UNKNOWN"
                with self.assertRaisesRegex(AnalysisValidationError, "UNVERIFIED_MATCH_SOURCE_LINK"):
                    import_human_training_csv(data, manifest, source, wrong)
                wrong = copy.deepcopy(binding)
                wrong["local_analysis_permission"] = "UNKNOWN"
                with self.assertRaisesRegex(AnalysisValidationError, "LOCAL_ANALYSIS_PERMISSION_NOT_DECLARED"):
                    import_human_training_csv(data, manifest, source, wrong)
                wrong_manifest = copy.deepcopy(manifest)
                wrong_manifest["source_sha256"] = "0" * 64
                with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_HASH_MISMATCH"):
                    import_human_training_csv(data, wrong_manifest, source, binding)
                source.write_bytes(b"TEST ONLY: source changed after declaration")
                with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_HASH_MISMATCH"):
                    import_human_training_csv(data, manifest, source, binding)
                source.unlink()
                with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_FILE_NOT_FOUND"):
                    import_human_training_csv(data, manifest, source, binding)

    def test_synthetic_csv_cannot_enter_manual_annotation_path(self):
        with tempfile.TemporaryDirectory() as directory:
            data, source, manifest, binding = self._manual_test_inputs(directory)
            manifest["match_id"] = self.base["dataset"]["match_id"]
            binding["match_id"] = manifest["match_id"]
            with patch("training_review._require_video_stream_metadata"):
                with self.assertRaisesRegex(AnalysisValidationError, "INVALID_MANUAL_MANIFEST"):
                    import_human_training_csv(self.original_csv, manifest, source, binding)

    def test_fake_source_bytes_fail_video_metadata_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            data, source, manifest, binding = self._manual_test_inputs(directory)
            with self.assertRaisesRegex(AnalysisValidationError, "SOURCE_NOT_VIDEO|MEDIA_PROBE_UNAVAILABLE"):
                import_human_training_csv(data, manifest, source, binding)

    def test_cli_demo_writes_reproducible_report_and_compares_one_edit(self):
        script = ROOT / "scripts" / "run_training_review.py"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(script), "--demo", "--output-dir", directory],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(directory)
            before = json.loads((root / "simulated-report.json").read_text(encoding="utf-8"))
            after = json.loads((root / "simulated-report-edited.json").read_text(encoding="utf-8"))
            comparison = json.loads((root / "comparison.json").read_text(encoding="utf-8"))
            self.assertNotEqual(comparison["original_csv_sha256"], comparison["edited_csv_sha256"])
            self.assertEqual(before["metrics"]["rally_length_mean"]["numerator"] + 2,
                             after["metrics"]["rally_length_mean"]["numerator"])
            self.assertEqual(result.stdout, subprocess.run([sys.executable, str(script), "--demo", "--output-dir", directory],
                                                            capture_output=True, text=True, check=True).stdout)

    def test_cli_reads_a_declared_csv_and_writes_separate_json_and_chinese_summary(self):
        script = ROOT / "scripts" / "run_training_review.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "points.csv"
            declaration_path = root / "declaration.json"
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            csv_path.write_bytes(self.original_csv)
            declaration_path.write_text(json.dumps(self.original_decl), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(script), "--csv", str(csv_path), "--declaration", str(declaration_path),
                "--output-json", str(json_path), "--output-md", str(markdown_path),
                "--generated-at", "2026-10-13T00:00:00Z",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(report["dataset"]["annotation_csv_sha256"], self.original_decl["csv_sha256"])
            self.assertIn("训练比赛战术复盘", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
