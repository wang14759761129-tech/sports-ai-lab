import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

INTEGRATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRATION / "scripts"))
from build_goal12_6_identity_report import build  # noqa: E402


class MatchIdentityGoal126Tests(unittest.TestCase):
    def test_existing_cinema_contract_accepts_new_projection(self):
        report, projection = build()
        schema = json.loads((INTEGRATION / "contracts/cinema-source-review-v0.1.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(projection)
        self.assertEqual(report["cinema_contract_version"], "ptti.cinema-source-review/0.1")

    def test_exact_video_metadata_never_creates_canonical_match(self):
        report, projection = build()
        for evidence, source in zip(report["records"], projection["featured_sources"]):
            self.assertEqual(evidence["video_id"], source["video_id"])
            self.assertEqual(evidence["oembed_observation"]["http_status"], 200)
            self.assertIsNone(evidence["identity"]["provider_match_id"])
            self.assertIsNone(evidence["canonical_match_id"])
            self.assertIsNone(source["match_link"]["canonical_match_id"])
            self.assertEqual(source["match_link"]["status"], "UNKNOWN")

    def test_conflicting_wtt_event_id_removed_without_erasing_history(self):
        report, projection = build()
        doha = next(row for row in projection["featured_sources"] if row["video_id"] == "KCGdLksBH7s")
        conflict = "https://www.worldtabletennis.com/eventInfo?eventId=3108"
        self.assertNotIn(conflict, [row["url"] for row in doha["match_claim"]["evidence_sources"]])
        old = json.loads((INTEGRATION / "fixtures/goal12-3-selected-source-observations.json").read_text(encoding="utf-8"))
        self.assertIn(conflict, json.dumps(old))
        doha_evidence = next(row for row in report["records"] if row["video_id"] == "KCGdLksBH7s")
        self.assertEqual(doha_evidence["excluded_or_limited_sources"][0]["observation_method"], "SEARCH_INDEX_RESULT_NOT_LIVE_RENDER")

    def test_embed_html_and_platform_terms_do_not_upgrade_rights_or_playback(self):
        report, projection = build()
        self.assertFalse(report["policy_reference"]["per_video_rights_upgraded"])
        for row in report["records"]:
            self.assertTrue(row["oembed_observation"]["embedded_html_present"])
            for key in ("public_listing", "external_viewing", "thumbnail_display", "embedding"):
                self.assertEqual(row["rights"][key], "UNKNOWN")
            self.assertEqual(row["rights"]["local_analysis"], "NOT_GRANTED")
            self.assertEqual(row["rights"]["redistribution"], "NOT_GRANTED")
            for key in ("external_visual", "embedding", "desktop_native", "vision"):
                self.assertEqual(row["playback"][key], "NOT_TESTED")
        self.assertEqual(projection["catalog_snapshot"]["strict_public_video_source_count"], 0)

    def test_date_confidence_and_missing_athlete_identity_are_preserved(self):
        report, _ = build()
        records = {row["video_id"]: row for row in report["records"]}
        self.assertIsNone(records["0QgbtsBWZhk"]["identity"]["match_date"])
        self.assertEqual(records["KCGdLksBH7s"]["identity"]["match_date_status"], "OFFICIAL_DATED_FINAL_REPORT")
        self.assertEqual(records["O241nV8y4Dc"]["identity"]["match_date_status"], "SECONDARY_CATALOG_ONLY")
        self.assertTrue(all(row["identity"]["local_start_time"] is None for row in report["records"]))

    def test_export_is_reproducible_and_contains_no_private_media(self):
        report, projection = build()
        self.assertEqual((report, projection), build())
        payload = json.dumps((report, projection))
        for forbidden in ("file://", "C:\\", "video_bytes", "database_path", "thumbnail_url"):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
