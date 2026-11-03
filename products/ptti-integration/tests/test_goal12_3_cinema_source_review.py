import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from cinema_source_review import SourceReviewError, build_source_review  # noqa: E402
from match_library_index import build_indexes  # noqa: E402


class CinemaSourceReviewGoal12_3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.public = build_indexes(REPO_ROOT, generated_at="2026-10-15T00:00:00Z")
        cls.observations = json.loads((INTEGRATION_DIR / "fixtures" / "goal12-3-selected-source-observations.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((INTEGRATION_DIR / "contracts" / "cinema-source-review-v0.1.schema.json").read_text(encoding="utf-8"))

    def build(self, observations=None, generated_at="2026-10-15T15:20:00Z"):
        return build_source_review(self.index, observations or copy.deepcopy(self.observations), generated_at)

    def test_selected_records_are_unique_internal_and_unlinked(self):
        result = self.build()
        self.assertEqual(result["catalog_snapshot"], {
            "unique_video_sources": 35,
            "registered_match_records": 6,
            "canonical_video_match_links": 0,
            "strict_public_video_source_count": 0,
        })
        self.assertEqual(result["summary"]["selected_sources"], 3)
        self.assertEqual(result["summary"]["official_pages_http_200"], 3)
        self.assertEqual(result["summary"]["external_visual_playback_pass"], 0)
        for source in result["featured_sources"]:
            self.assertIsNone(source["match_link"]["canonical_match_id"])
            self.assertEqual(source["match_link"]["status"], "UNKNOWN")
            self.assertEqual(source["watch_status"]["external_visual_video_playback"], "NOT_TESTED")
            self.assertEqual(source["watch_status"]["in_app_entry"], "EXTERNAL_ONLY_PERMISSION_UNVERIFIED")
            self.assertEqual(source["content_claim"]["completeness"], "UNVERIFIED")
            self.assertEqual(source["thumbnail"]["url"], None)
            self.assertEqual(source["rights"], {
                "public_listing": "UNKNOWN", "external_viewing": "UNKNOWN", "thumbnail_display": "UNKNOWN",
                "embedding": "UNKNOWN", "local_analysis": "NOT_GRANTED", "redistribution": "NOT_GRANTED",
            })

    def test_review_json_conforms_to_versioned_schema(self):
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(self.build()), key=lambda item: list(item.path))
        self.assertEqual(errors, [])

    def test_unknown_or_duplicate_source_ids_are_rejected(self):
        obs = copy.deepcopy(self.observations)
        obs["sources"][0]["source_id"] = "video-source:missing"
        with self.assertRaisesRegex(SourceReviewError, "unknown source_id"):
            self.build(obs)
        obs = copy.deepcopy(self.observations)
        obs["sources"][1]["source_id"] = obs["sources"][0]["source_id"]
        with self.assertRaisesRegex(SourceReviewError, "duplicate source_id"):
            self.build(obs)

    def test_rights_identity_playback_and_thumbnail_cannot_be_promoted_by_input(self):
        for field, value in (("rights", {"public_listing": "ALLOWED"}), ("canonical_match_id", "real-match"), ("match_id", "real-match"), ("thumbnail_url", "https://example.invalid/image.jpg"), ("playback_pass", True), ("vision_pass", True)):
            with self.subTest(field=field):
                obs = copy.deepcopy(self.observations)
                obs["sources"][0][field] = value
                with self.assertRaisesRegex(SourceReviewError, "cannot override rights, links, or playback evidence"):
                    self.build(obs)

    def test_event_claim_does_not_create_match_link_without_video_id_reference(self):
        result = self.build()
        for source in result["featured_sources"]:
            self.assertFalse(source["match_claim"]["official_source_references_video_id"])
            self.assertEqual(source["match_link"]["status"], "UNKNOWN")
            self.assertEqual(source["match_link"]["join_policy"], "EXACT_EVIDENCE_REQUIRED_NO_AUTOMATIC_JOIN_BY_TITLE_EVENT_OR_PLAYER_NAME")

    def test_http_page_success_does_not_promote_visual_playback(self):
        result = self.build()
        self.assertEqual(result["summary"]["official_pages_http_200"], 3)
        self.assertEqual(result["summary"]["external_visual_playback_pass"], 0)
        self.assertTrue(all(row["watch_status"]["official_page_request"] == "HTTP_200_PAGE_ONLY" for row in result["featured_sources"]))

    def test_public_projection_nonzero_fails_closed(self):
        index = copy.deepcopy(self.index)
        index["quality_summary"]["public_eligible"]["video_sources"] = 1
        with self.assertRaisesRegex(SourceReviewError, "strict-public projection must remain empty"):
            build_source_review(index, copy.deepcopy(self.observations), "2026-10-15T15:20:00Z")

    def test_invalid_http_status_and_reversed_event_window_fail(self):
        obs = copy.deepcopy(self.observations)
        obs["sources"][0]["page_probe"]["http_status"] = 999
        with self.assertRaisesRegex(SourceReviewError, "numeric HTTP_HEAD result"):
            self.build(obs)
        obs = copy.deepcopy(self.observations)
        obs["sources"][1]["event_match_review"]["event_window"]["start"] = "2025-05-26"
        with self.assertRaisesRegex(SourceReviewError, "start must not follow end"):
            self.build(obs)
        obs = copy.deepcopy(self.observations)
        obs["sources"][1]["event_match_review"]["match_date"]["value"] = "2024-05-25"
        with self.assertRaisesRegex(SourceReviewError, "does not match the reviewed event year"):
            self.build(obs)

    def test_missing_video_id_reference_is_not_hidden_by_candidate_match_id(self):
        obs = copy.deepcopy(self.observations)
        first = obs["sources"][0]
        first["unlinked_match_review_candidate"] = "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"
        result = self.build(obs)
        source = result["featured_sources"][0]
        self.assertIsNone(source["match_link"]["canonical_match_id"])
        self.assertEqual(source["match_link"]["unlinked_review_candidate_match_id"], "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun")


if __name__ == "__main__":
    unittest.main()
