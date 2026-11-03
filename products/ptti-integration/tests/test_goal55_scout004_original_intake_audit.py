import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GENERATED = ROOT / "products" / "ptti-integration" / "generated"
AUDIT_PATH = GENERATED / "goal55-scout004-r2-ingestion-audit-v0.1" / "internal" / "intake-audit.json"
PRIOR_REVIEW_PATH = GENERATED / "goal55-scout004-r2-page-review-v0.1" / "internal" / "review.json"
INTERNAL_SOURCES_PATH = ROOT / "products" / "ptti" / "data" / "professional" / "official_video_sources.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Scout004OriginalIntakeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = load_json(AUDIT_PATH)

    def test_missing_original_bytes_fail_closed(self):
        self.assertEqual("BLOCKED_MISSING_ORIGINAL_BYTES", self.audit["input"]["status"])
        self.assertFalse(self.audit["input"]["raw_payload_reconstructed"])
        expected = {
            "scout-004-r2-candidates.json": "0081392d484d241278ade74a4959a3126e158164116f8c1f651cbaef1fbd742c",
            "scout-004-r2-candidates.csv": "2e32f4d7aa37500a5252e4a161240230a6cb96c35e8da3a0b1fd35a10ac6bce4",
        }
        for item in self.audit["input"]["expected_files"]:
            self.assertEqual(expected[item["name"]], item["expected_sha256"])
            self.assertFalse(item["available"])
            self.assertIsNone(item["actual_sha256"])
            self.assertEqual("NOT_RUN_NO_BYTES", item["parse_status"])

    def test_rendered_summary_matches_counts_but_c07_highlight_has_transcription_conflict(self):
        previous = load_json(PRIOR_REVIEW_PATH)
        visible = self.audit["rendered_page_comparison"]
        self.assertTrue(visible["matches_previous_page_review"])
        self.assertEqual(15, len(visible["candidate_ids_visible"]))
        self.assertEqual(previous["handoff_claim_counts"]["ready_for_main_review"], visible["grade_counts_visible"]["READY_FOR_MAIN_REVIEW"])
        self.assertEqual(previous["handoff_claim_counts"]["needs_verification"], visible["grade_counts_visible"]["NEEDS_VERIFICATION"])
        self.assertEqual(previous["handoff_claim_counts"]["rejected"], visible["grade_counts_visible"]["REJECTED"])
        old_c07 = next(row for row in previous["candidates"] if row["candidate_id"] == "C07")
        correction = visible["detected_transcription_difference"]
        self.assertEqual("DHxcmcGrpn2", old_c07["video_ids"][1])
        self.assertEqual("DHxcmcGrpn8", correction["currently_rendered_page_value"])
        self.assertEqual("NONE; both values remain unverified claims until the original data and video metadata are available", correction["admission_effect"])

    def test_exact_duplicate_and_internal_unknown_link_are_not_promoted(self):
        dedup = self.audit["exact_dedup_findings"]
        public = dedup["candidate_public_overlap"]
        self.assertEqual("cDccQqVlMnc", public["video_id"])
        self.assertEqual("pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final", public["existing_match_id"])
        internal = dedup["candidate_internal_overlap"]
        self.assertEqual("vYsJLPTEIaI", internal["video_id"])
        self.assertIsNone(internal["canonical_match_id"])
        self.assertEqual("UNKNOWN", internal["match_link_status"])
        self.assertEqual("REFERENCE_ONLY_NOT_LICENSE_GRANTED", internal["rights"])
        raw = load_json(INTERNAL_SOURCES_PATH)
        self.assertEqual(1, sum(row.get("video_id") == internal["video_id"] for row in raw["videos"]))

    def test_admission_stays_zero_and_prior_review_is_unchanged(self):
        admission = self.audit["admission"]
        self.assertEqual(0, admission["new_matches"])
        self.assertEqual(0, admission["new_video_sources"])
        self.assertFalse(admission["strict_public_package_generated"])
        self.assertEqual("NOT_TESTED", self.audit["handoff_evidence_claims"]["playback"])
        self.assertEqual("UNKNOWN", self.audit["handoff_evidence_claims"]["territory"])
        expected = self.audit["prior_review"]["sha256"]
        self.assertEqual(expected, hashlib.sha256(PRIOR_REVIEW_PATH.read_bytes()).hexdigest())

    def test_san_snapshot_is_current_base_only_not_the_composed_main_union(self):
        san = self.audit["san_read_only_compatibility"]
        self.assertEqual("ab484d6cf0336372c742a6a80ebc6072d14aec4e", san["head"])
        self.assertEqual("PASS", san["check"])
        catalog = san["consumed_catalog"]
        self.assertEqual("ptti.match-library-index/0.1", catalog["contract_version"])
        self.assertEqual((5, 15, 8), (catalog["matches"], catalog["video_sources"], catalog["stars"]))
        self.assertIn("no SCOUT candidate consumed", san["scope"])


if __name__ == "__main__":
    unittest.main()
