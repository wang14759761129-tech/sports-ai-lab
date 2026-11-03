import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GENERATED = ROOT / "products" / "ptti-integration" / "generated"
REVIEW_PATH = GENERATED / "goal55-scout004-r2-page-review-v0.1" / "internal" / "review.json"


PACKAGE_PATHS = {
    "goal15": GENERATED / "goal15-main-fan-universe-public-v0.2" / "match-library-strict-public.json",
    "goal17": GENERATED / "goal17-1-real-content-v0.1" / "public" / "official-match-video-additions.json",
    "goal22": GENERATED / "goal22-main-inspiration-v0.1" / "public" / "fan-inspiration-v0.1.json",
    "goal24": GENERATED / "goal24-main-evidence-v0.1" / "public" / "match-reports-v0.1.json",
    "goal27": GENERATED / "goal27-match-experience-v0.1" / "public" / "match-experience-delta-v0.1.json",
}

EXPECTED_PACKAGE_SHA256 = {
    "goal15": "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930",
    "goal17": "6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a",
    "goal22": "702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9",
    "goal24": "701213d2bfca2e120b31629ef9422f8fd9a21eef4f341a87614b65fd130effa8",
    "goal27": "9c3662e8bf13fc8c49b37f3826094d744297f938361afba54945ab91fb1a930a",
}
INTERNAL_SOURCES_PATH = ROOT / "products" / "ptti" / "data" / "professional" / "official_video_sources.json"
INTERNAL_REVIEW_ROLLUP_PATH = GENERATED / "goal11-match-library" / "match-library-internal-review.json"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main_union_video_ids():
    ids = set()
    for path in PACKAGE_PATHS.values():
        package = load_json(path)
        for key in ("video_sources", "clips", "match_watch_sources"):
            for row in package.get(key, []):
                video_id = row.get("video_id") or row.get("provider_video_id")
                if not video_id:
                    url = row.get("original_url") or row.get("watch_url") or row.get("official_url") or ""
                    match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
                    video_id = match.group(1) if match else None
                if video_id:
                    ids.add(video_id)
    return ids


def main_union_match_ids():
    ids = set()
    for key in ("goal15", "goal17", "goal27"):
        package = load_json(PACKAGE_PATHS[key])
        ids.update(row["match_id"] for row in package.get("matches", []))
    return ids


class Scout004PageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_json(REVIEW_PATH)

    def test_page_snapshot_is_not_an_ingestion_artifact(self):
        intake = self.review["intake"]
        self.assertEqual("NOT_AVAILABLE", intake["json_attachment"]["retrieval_status"])
        self.assertEqual("NOT_AVAILABLE", intake["csv_attachment"]["retrieval_status"])
        self.assertIn("not an ingestion file", intake["limitation"])
        self.assertEqual(15, len(self.review["candidates"]))

    def test_candidate_grades_match_page_and_candidate_keys_are_unique(self):
        candidates = self.review["candidates"]
        self.assertEqual(15, len({row["candidate_id"] for row in candidates}))
        self.assertEqual({"C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "S1", "S2", "S3"}, {row["candidate_id"] for row in candidates})
        counts = self.review["handoff_claim_counts"]
        self.assertEqual(10, counts["ready_for_main_review"])
        self.assertEqual(4, counts["needs_verification"])
        self.assertEqual(1, counts["rejected"])

    def test_exact_source_dedup_is_only_c07_full_match(self):
        existing_ids = main_union_video_ids()
        candidate_ids = {
            video_id
            for row in self.review["candidates"]
            for video_id in [*row.get("video_ids", []), *row.get("alternative_video_ids", [])]
        }
        self.assertEqual(19, len(existing_ids))
        self.assertEqual(25, len(candidate_ids))
        self.assertEqual({"cDccQqVlMnc"}, candidate_ids & existing_ids)
        overlap = self.review["dedup_summary"]["exact_overlap"]
        self.assertEqual("C07", overlap["candidate_id"])
        self.assertEqual("pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final", overlap["existing_match_id"])
        internal = self.review["dedup_summary"]["internal_source_inventory_overlap"]
        self.assertEqual("S3", internal["candidate_id"])
        self.assertEqual("vYsJLPTEIaI", internal["video_id"])
        self.assertEqual("UNKNOWN", internal["existing_match_link_status"])
        self.assertIsNone(internal["existing_canonical_match_id"])
        self.assertEqual(8, len(main_union_match_ids()))

    def test_no_candidate_is_promoted_or_given_guessed_ptti_identity(self):
        self.assertFalse(self.review["global_media_evidence_from_handoff"]["rights_cleared"])
        self.assertEqual("NOT_GRANTED", self.review["global_media_evidence_from_handoff"]["download"])
        self.assertEqual("NOT_GRANTED", self.review["global_media_evidence_from_handoff"]["redistribution"])
        for candidate in self.review["candidates"]:
            self.assertNotIn("match_id", candidate)
            self.assertNotIn("source_id", candidate)
            self.assertNotIn("athlete_id", candidate)
            self.assertNotEqual("ADMITTED", candidate["main_admission"])
        result = self.review["admission_result"]
        self.assertEqual(0, result["new_strict_public_matches"])
        self.assertEqual(0, result["new_strict_public_video_sources"])

    def test_focus_fact_review_keeps_unknown_video_and_provider_ids(self):
        focus = {row["candidate_id"]: row for row in self.review["focus_fact_review"]}
        self.assertEqual("UNKNOWN", focus["C01"]["wtt_ittf_single_match_record_url"])
        self.assertIsNone(focus["C01"]["ptti_match_id"])
        self.assertEqual("UNKNOWN", focus["C08"]["wtt_ittf_single_match_record_url"])
        self.assertIsNone(focus["C08"]["ptti_match_id"])
        self.assertEqual("UNKNOWN", focus["S1"]["verified_facts"]["match_number"])
        self.assertEqual("UNKNOWN", focus["S1"]["verified_facts"]["exact_game_scores"])

    def test_catalog_hashes_still_match_read_only_baseline(self):
        declared = {row["sha256"] for row in self.review["catalog_baseline"]["main_composed_union"]["packages"]}
        for key, path in PACKAGE_PATHS.items():
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(EXPECTED_PACKAGE_SHA256[key], digest, msg=f"{key} package changed from the reviewed snapshot")
            self.assertIn(digest, declared, msg=f"{key} package hash not represented in review baseline")

    def test_s3_source_is_existing_internal_reference_not_a_new_public_match(self):
        catalog = load_json(INTERNAL_SOURCES_PATH)
        sources = catalog.get("videos", [])
        self.assertEqual(9, len(sources))
        self.assertEqual(
            "fa1d536610561c673f94392ee2e202b6a7dc6989a4818ee1a58daeb924884dc3",
            hashlib.sha256(INTERNAL_SOURCES_PATH.read_bytes()).hexdigest(),
        )
        matches = [row for row in sources if row.get("video_id") == "vYsJLPTEIaI"]
        self.assertEqual(1, len(matches))
        source = matches[0]
        self.assertEqual("REFERENCE_ONLY_NOT_LICENSE_GRANTED", source["rights"])
        self.assertEqual("EMBED_BLOCKED", source["playback_status"])
        self.assertNotIn("match_id", source)
        self.assertNotIn("canonical_match_id", source)
        self.assertEqual(0, self.review["admission_result"]["new_strict_public_video_sources"])
        rollup = load_json(INTERNAL_REVIEW_ROLLUP_PATH)
        self.assertEqual(35, rollup["quality_summary"]["unique_video_sources"])
        self.assertEqual(6, rollup["quality_summary"]["registered_match_records"])


if __name__ == "__main__":
    unittest.main()
