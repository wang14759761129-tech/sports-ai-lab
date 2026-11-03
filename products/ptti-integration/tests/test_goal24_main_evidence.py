import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BUILDER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_goal24_main_evidence.py"
spec = importlib.util.spec_from_file_location("build_goal24_main_evidence", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


class Goal24MainEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.package = builder.build_package(generated_at="2026-10-21T00:00:00Z")

    def test_report_is_schema_valid_and_tied_to_fixed_inputs(self):
        self.assertEqual(builder.validate_package(self.package), [])
        self.assertEqual(self.package["input_identity"]["match_library_sha256"], builder.EXPECTED_MATCH_LIBRARY_SHA256)
        self.assertEqual(self.package["input_identity"]["fan_inspiration_sha256"], builder.EXPECTED_FAN_INSPIRATION_SHA256)
        self.assertEqual(len(self.package["match_reports"]), 1)

    def test_report_reuses_an_existing_official_source_and_existing_match_video(self):
        report = self.package["match_reports"][0]
        self.assertEqual(report["article"]["source_id"], "goal15-wtt-singapore-smash-2026-ms-final")
        self.assertEqual(report["linked_video"]["source_id"], "video-source:youtube:cDccQqVlMnc")
        self.assertEqual(report["match_id"], "pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final")
        self.assertEqual(report["recorded_result"]["status"], "OFFICIAL_WTT_RESULT_CROSSCHECKED")
        self.assertEqual(report["game_scores"], [[11, 3], [11, 8], [11, 8], [11, 9]])

    def test_publication_date_and_direct_page_state_are_not_inferred(self):
        article = self.package["match_reports"][0]["article"]
        self.assertIsNone(article["published_at"])
        self.assertEqual(article["published_at_status"], "NOT_RECORDED_NO_DATE_IN_REVIEWED_SOURCE")
        self.assertEqual(article["content_observation"], "OFFICIAL_DOMAIN_SEARCH_EXCERPT_SURFACED")
        self.assertEqual(article["direct_page_status"], "COOKIE_CONSENT_SHELL_ONLY")

    def test_report_does_not_escalate_playback_or_reuse_rights(self):
        report = self.package["match_reports"][0]
        self.assertEqual(report["linked_video"]["video_started"], "NOT_TESTED")
        self.assertEqual(report["linked_video"]["complete_watch"], "UNVERIFIED")
        self.assertEqual(report["rights"]["article_republication"], "NOT_GRANTED")
        self.assertEqual(report["rights"]["image_reuse"], "NOT_GRANTED")
        self.assertEqual(report["rights"]["video_embed"], "UNKNOWN_NOT_GRANTED")

    def test_validator_rejects_invented_date_or_playback(self):
        bad = copy.deepcopy(self.package)
        bad["match_reports"][0]["article"]["published_at"] = "2026-03-01"
        self.assertTrue(builder.validate_package(bad))
        bad = copy.deepcopy(self.package)
        bad["match_reports"][0]["linked_video"]["video_started"] = "PASS"
        self.assertTrue(builder.validate_package(bad))
        bad = copy.deepcopy(self.package)
        bad["match_reports"][0]["game_scores"][0] = [11, 1]
        self.assertTrue(builder.validate_package(bad))
        bad = copy.deepcopy(self.package)
        bad["match_reports"][0]["participants"][1]["athlete_id"] = "athlete:unknown"
        self.assertTrue(builder.validate_package(bad))

    def test_builder_rejects_modified_input_identity(self):
        with patch.object(builder, "EXPECTED_FAN_INSPIRATION_SHA256", "0" * 64):
            with self.assertRaisesRegex(builder.PackageError, "fan_inspiration_identity_mismatch"):
                builder.build_package()

    def test_builder_rejects_unmatched_video_binding(self):
        with patch.object(builder, "VIDEO_SOURCE_ID", "video-source:youtube:not-present"):
            with self.assertRaisesRegex(builder.PackageError, "linked_video_missing_or_match_mismatch"):
                builder.build_package()


if __name__ == "__main__":
    unittest.main()
