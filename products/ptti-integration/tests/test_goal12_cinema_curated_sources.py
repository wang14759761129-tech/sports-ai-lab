import copy
import json
import sys
import unittest
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from cinema_curated_sources import CurationError, build_curated_sources  # noqa: E402
from match_library_index import build_indexes  # noqa: E402


class CinemaCuratedSourcesGoal12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.internal, cls.public = build_indexes(REPO_ROOT, generated_at="2026-10-15T00:00:00+00:00")
        cls.observations = json.loads((INTEGRATION_DIR / "fixtures" / "goal12-cinema-curation-observations.json").read_text(encoding="utf-8"))

    def build(self, index=None, observations=None):
        return build_curated_sources(index or self.internal, observations or copy.deepcopy(self.observations), "2026-10-15T15:00:00Z")

    def test_three_candidates_are_exact_id_selected_and_http_checked(self):
        result = self.build()
        self.assertEqual(len(result["featured_sources"]), 3)
        self.assertEqual({row["discipline_claim"] for row in result["featured_sources"]}, {"MS", "WS", "WD"})
        self.assertEqual({row["source_id"] for row in result["featured_sources"]}, {
            "video-source:youtube:0QgbtsBWZhk",
            "video-source:youtube:KCGdLksBH7s",
            "video-source:youtube:O241nV8y4Dc",
        })
        self.assertTrue(all(row["external_watch"]["http_head_status"] == "HTTP_200" for row in result["featured_sources"]))

    def test_all_rights_and_match_links_remain_at_recorded_unknown_state(self):
        result = self.build()
        for row in result["featured_sources"]:
            self.assertIsNone(row["match_link"]["canonical_match_id"])
            self.assertEqual(row["match_link"]["status"], "UNKNOWN")
            self.assertEqual(row["rights"]["public_listing"], "UNKNOWN")
            self.assertEqual(row["rights"]["embedding"], "UNKNOWN")
            self.assertEqual(row["rights"]["thumbnail_display"], "UNKNOWN")
            self.assertEqual(row["rights"]["local_analysis"], "NOT_GRANTED")
            self.assertEqual(row["rights"]["redistribution"], "NOT_GRANTED")
            self.assertIsNone(row["thumbnail"]["url"])

    def test_reachable_page_does_not_mean_external_or_native_playback(self):
        result = self.build()
        for row in result["featured_sources"]:
            self.assertEqual(row["external_watch"]["actual_video_playback"], "NOT_TESTED")
            self.assertEqual(row["availability"]["current_external_visual_playback"], "NOT_TESTED")
            self.assertEqual(row["availability"]["desktop_native_playback"], "NOT_TESTED")
            self.assertEqual(row["availability"]["vision_analysis"], "NOT_TESTED")
            self.assertEqual(row["availability"]["current_session_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_first_source_preserves_historical_embed_block_without_claiming_permission(self):
        result = self.build()
        first = next(row for row in result["featured_sources"] if row["video_id"] == "0QgbtsBWZhk")
        self.assertEqual(first["availability"]["latest_recorded_embed_technical_status"], "BLOCKED_OBSERVED")
        self.assertEqual(first["availability"]["embedding_permission"], "UNKNOWN")

    def test_strict_public_index_is_rejected_even_when_empty(self):
        with self.assertRaisesRegex(CurationError, "Only INTERNAL_REVIEW"):
            self.build(index=self.public)

    def test_unknown_duplicate_and_privileged_fields_fail_closed(self):
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["source_id"] = "video-source:missing"
        with self.assertRaisesRegex(CurationError, "Unknown source_id"):
            self.build(observations=observations)
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"].append(copy.deepcopy(observations["selected_sources"][0]))
        with self.assertRaisesRegex(CurationError, "Duplicate source_id"):
            self.build(observations=observations)
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["rights"] = {"public_listing": "ALLOWED"}
        with self.assertRaisesRegex(CurationError, "cannot override protected"):
            self.build(observations=observations)

    def test_mismatched_publisher_is_not_promoted(self):
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["publisher_check"]["author_name"] = "Unrelated Publisher"
        row = self.build(observations=observations)["featured_sources"][0]
        self.assertEqual(row["publisher_check"]["status"], "PUBLISHER_METADATA_MISMATCH_REVIEW_REQUIRED")
        self.assertEqual(row["match_link"]["status"], "UNKNOWN")

    def test_shortlist_is_capped_at_three_sources(self):
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"].append({"source_id": "video-source:youtube:extra000001", "checked_at": "2026-10-15T14:00:00Z", "official_page_http_status": 200})
        with self.assertRaisesRegex(CurationError, "limited to three"):
            self.build(observations=observations)

    def test_internal_only_and_public_projection_remain_empty(self):
        result = self.build()
        self.assertEqual(result["audience"], "INTERNAL_REVIEW_ONLY")
        self.assertFalse(result["strict_public_fallback"])
        self.assertEqual(self.public["video_sources"], [])

    def test_no_private_paths_or_video_bytes_are_projected(self):
        payload = json.dumps(self.build(), ensure_ascii=False)
        for forbidden in ("C:\\", "file://", "filesystem_path", "video_bytes", "i.ytimg.com"):
            self.assertNotIn(forbidden, payload)

    def test_observation_requires_timestamp_and_http_status(self):
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["checked_at"] = "not-a-time"
        with self.assertRaisesRegex(CurationError, "ISO-8601"):
            self.build(observations=observations)
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["official_page_http_status"] = "200"
        with self.assertRaisesRegex(CurationError, "HTTP status"):
            self.build(observations=observations)

    def test_event_evidence_cannot_smuggle_match_or_rights_claims(self):
        observations = copy.deepcopy(self.observations)
        observations["selected_sources"][0]["event_identity_evidence"]["canonical_match_id"] = "pro:wtt:invented"
        with self.assertRaisesRegex(CurationError, "unsupported claims"):
            self.build(observations=observations)

    def test_unknown_input_versions_are_rejected(self):
        observations = copy.deepcopy(self.observations)
        observations["contract_version"] = "ptti.cinema-curation-observations/0.2"
        with self.assertRaisesRegex(CurationError, "Unsupported curation observation"):
            self.build(observations=observations)
        index = copy.deepcopy(self.internal)
        index["contract_version"] = "ptti.match-library-index/0.2"
        with self.assertRaisesRegex(CurationError, "Unsupported match-library index"):
            self.build(index=index)


if __name__ == "__main__":
    unittest.main()
