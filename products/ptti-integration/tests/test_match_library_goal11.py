import copy
import json
import sys
import unittest
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from match_library_index import (  # noqa: E402
    CatalogError,
    _deduplicate_sources,
    _source_permission,
    build_indexes,
)


class MatchLibraryGoal11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review, cls.public = build_indexes(REPO_ROOT, generated_at="2026-10-15T00:00:00+00:00")

    def test_index_uses_35_unique_video_source_records_and_drops_one_snapshot_duplicate(self):
        summary = self.review["quality_summary"]
        self.assertEqual(summary["source_snapshot_rows"], 36)
        self.assertEqual(summary["unique_video_sources"], 35)
        self.assertEqual(summary["duplicate_snapshot_rows_removed"], 1)
        self.assertEqual(summary["video_sources_by_platform"], {"BILIBILI": 1, "YOUTUBE": 34})
        self.assertEqual(summary["video_sources_by_match_type"], {"MD": 6, "MS": 12, "WD": 6, "WS": 9, "XD": 2})

    def test_video_source_rows_are_not_promoted_to_canonical_matches(self):
        self.assertEqual(len(self.review["matches"]), 6)
        self.assertTrue(all(row["canonical_match_id"] is None for row in self.review["video_sources"]))
        self.assertTrue(all(row["match_link_status"] == "UNKNOWN" for row in self.review["video_sources"]))
        self.assertTrue(all(row["video_source_ids"] == [] for row in self.review["matches"]))
        self.assertEqual(self.review["analysis_compatibility"]["review_targets_version"], "ptti.review-targets/0.1")
        self.assertEqual(self.review["analysis_compatibility"]["review_evidence_pack_version"], "ptti.review-evidence-pack/0.1")
        self.assertEqual(self.review["analysis_compatibility"]["playback_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_strict_public_projection_excludes_unknown_rights(self):
        self.assertTrue(all(row["rights"]["public_listing"] == "UNKNOWN" for row in self.review["video_sources"]))
        self.assertEqual(self.public["matches"], [])
        self.assertEqual(self.public["video_sources"], [])
        self.assertEqual(self.public["stars"], [])
        self.assertEqual(self.public["quality_summary"]["exclusion_reason"], "No scoped, evidenced public metadata-listing permission is present in these snapshots.")

    def test_no_thumbnail_url_local_path_or_native_vision_claim_leaks(self):
        serialized = json.dumps(self.review, ensure_ascii=False)
        self.assertNotIn("i.ytimg.com", serialized)
        self.assertNotIn("C:\\", serialized)
        self.assertNotIn("video_local_path", serialized)
        self.assertTrue(all(row["thumbnail"]["url"] is None for row in self.review["video_sources"]))
        self.assertTrue(all(row["availability"]["desktop_native_playback"] == "NOT_TESTED" for row in self.review["video_sources"]))
        self.assertTrue(all(row["availability"]["vision_analysis"] == "NOT_TESTED" for row in self.review["video_sources"]))
        self.assertEqual(self.review["quality_summary"]["desktop_native_playback_pass"], 0)

    def test_external_visual_observation_is_limited_and_distinct_from_native(self):
        summary = self.review["quality_summary"]
        self.assertEqual(summary["external_visual_playback_observed_limited"], 6)
        bili = next(row for row in self.review["video_sources"] if row["platform"] == "BILIBILI")
        self.assertEqual(bili["availability"]["external_video_visual_latest_recorded"], "VISUAL_PASS_LIMITED")
        self.assertTrue(any("Login" in str(observation.get("limitations")) or "trial" in str(observation.get("limitations")) for observation in bili["availability"]["external_observations"]))
        self.assertEqual(bili["availability"]["desktop_native_playback"], "NOT_TESTED")
        limited_ids = {row["source_id"] for row in self.review["video_sources"] if row["availability"]["external_video_visual_latest_recorded"] == "VISUAL_PASS_LIMITED"}
        self.assertEqual(limited_ids, {
            "video-source:bilibili:BV1nb421H7jB",
            "video-source:youtube:DTPNEl3-2b0",
            "video-source:youtube:H77vNFk3neg",
            "video-source:youtube:JTUWXpB-NVo",
            "video-source:youtube:ekfCZiIEYi0",
            "video-source:youtube:iQhVLkcGCFE",
        })
        blocked = [row for row in self.review["video_sources"] if row["availability"]["platform_embed"]["latest_recorded_technical_status"] == "BLOCKED_OBSERVED"]
        self.assertEqual(len(blocked), 2)

    def test_completeness_claims_do_not_become_verified_full_matches(self):
        self.assertEqual(self.review["quality_summary"]["completeness_verified"], 0)
        self.assertTrue(all(row["completeness_status"] == "UNVERIFIED" for row in self.review["video_sources"]))

    def test_stars_profiles_retain_sources_and_do_not_invent_personal_content(self):
        self.assertEqual(len(self.review["stars"]), 16)
        self.assertEqual(sum(bool(row["official_profile_url"]) for row in self.review["stars"]), 14)
        evidence_ids = {row["source_id"] for row in self.review["evidence_sources"]}
        for star in self.review["stars"]:
            self.assertTrue(star["evidence_source_ids"])
            self.assertTrue(set(star["evidence_source_ids"]).issubset(evidence_ids))
            self.assertEqual(star["equipment"], {"status": "UNKNOWN", "items": []})
            for field in ("coach_observations", "interviews", "sponsorships", "social_feedback"):
                self.assertEqual(star[field]["status"], "NOT_COLLECTED")

    def test_public_right_requires_scoped_permission_and_evidence(self):
        self.assertEqual(_source_permission({"rights_status": "USER_AUTHORIZED"}, "metadata_listing"), "UNKNOWN")
        self.assertEqual(_source_permission({"full_match": True}, "metadata_listing"), "UNKNOWN")
        self.assertEqual(_source_permission({"usage_permissions": {"metadata_listing": "ALLOWED"}}, "metadata_listing"), "UNKNOWN")
        evidenced = {"usage_permissions": {"metadata_listing": "ALLOWED"}, "permission_evidence": {"metadata_listing": {"evidence_ref": "rights-doc-1", "verified_at": "2026-10-15T00:00:00Z", "issuer": "rights-holder"}}}
        self.assertEqual(_source_permission(evidenced, "metadata_listing"), "ALLOWED")

    def test_duplicate_source_identity_conflict_is_visible_and_not_silently_chosen(self):
        fixture = {
            "platform": "YOUTUBE", "video_id": "WoqgXTjZNSk",
            "official_url": "https://www.youtube.com/watch?v=WoqgXTjZNSk",
            "match_type": "MS", "event": "Event A", "player_a": "A", "player_b": "B",
            "source_verified_at": "2026-10-10T00:00:00Z", "playback_status": "NOT_TESTED",
        }
        other = copy.deepcopy(fixture)
        other["match_type"] = "WS"
        rows, duplicates = _deduplicate_sources([("a.json", fixture), ("b.json", other)])
        self.assertEqual(duplicates, 1)
        self.assertEqual(rows[0]["match_type"], "UNKNOWN")
        self.assertEqual(rows[0]["source_identity_status"], "CONFLICT_REVIEW_REQUIRED")
        self.assertIn("discipline", rows[0]["identity_conflicts"])
        self.assertIsNone(rows[0]["canonical_match_id"])

    def test_invalid_platform_url_identity_is_rejected(self):
        fixture = {"platform": "YOUTUBE", "video_id": "WoqgXTjZNSk", "official_url": "https://www.youtube.com/watch?v=other1234567"}
        with self.assertRaisesRegex(CatalogError, "do not match"):
            _deduplicate_sources([("bad.json", fixture)])


if __name__ == "__main__":
    unittest.main()
