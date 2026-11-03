from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from fan_content_intelligence import (  # noqa: E402
    FanContentError,
    build_fan_content,
    build_from_files,
)


FIXTURE_PATH = INTEGRATION_DIR / "fixtures" / "goal14-fan-content-observations.json"
REGISTRY_PATH = REPO_ROOT / "products" / "ptti" / "data" / "professional" / "registry.json"
SCHEMA_PATH = INTEGRATION_DIR / "contracts" / "fan-content-intelligence-v0.1.schema.json"
OBSERVATIONS = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
REGISTRY = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
MANIFEST = [{"logical_name": "test-input", "sha256": "a" * 64}]


def build(fixture=None):
    return build_fan_content(
        REGISTRY,
        copy.deepcopy(OBSERVATIONS if fixture is None else fixture),
        generated_at="2026-10-18T04:30:00Z",
        source_manifest=MANIFEST,
    )


class Goal14FanContentIntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.internal, cls.public = build_from_files(
            REPO_ROOT,
            FIXTURE_PATH,
            REGISTRY_PATH,
            generated_at="2026-10-18T04:30:00Z",
        )

    def test_internal_and_strict_public_documents_match_schema(self):
        Draft202012Validator.check_schema(SCHEMA)
        validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
        validator.validate(self.internal)
        validator.validate(self.public)
        self.assertEqual(self.internal["contract_version"], "ptti.fan-content-intelligence/0.1")

    def test_five_events_three_registry_stars_and_twenty_sourced_candidates(self):
        summary = self.internal["quality_summary"]
        self.assertEqual((summary["event_count"], summary["star_count"], summary["candidate_count"]), (5, 3, 20))
        self.assertEqual(summary["exact_video_url_count"], 10)
        self.assertEqual(summary["event_page_only_count"], 10)
        self.assertEqual({event["event_year"] for event in self.internal["events"]}, {2025})
        self.assertEqual(
            {star["athlete_id"] for star in self.internal["stars"]},
            {"athlete:135977", "athlete:121558", "athlete:123980"},
        )

    def test_strict_public_is_empty_and_never_falls_back_to_internal(self):
        self.assertEqual(self.public["view"], "STRICT_PUBLIC")
        for key in ("source_manifest", "evidence_sources", "events", "stars", "content_candidates", "relationships"):
            self.assertEqual(self.public[key], [], key)
        self.assertEqual(self.public["quality_summary"]["public_eligible_count"], 0)
        self.assertIn("must not fall back", self.public["notice"])

    def test_unverified_rights_and_playback_states_are_never_promoted(self):
        rows = self.internal["events"] + self.internal["content_candidates"]
        self.assertTrue(all(row["rights"]["public_listing"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["rights"]["embedding"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["rights"]["thumbnail_display"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["rights"]["local_analysis"] == "NOT_GRANTED" for row in rows))
        self.assertTrue(all(row["rights"]["download"] == "NOT_GRANTED" for row in rows))
        self.assertTrue(all(row["rights"]["redistribution"] == "NOT_GRANTED" for row in rows))
        self.assertTrue(all(row["playback_status"] == "NOT_TESTED" for row in self.internal["content_candidates"]))
        self.assertEqual(self.internal["quality_summary"]["playback_pass_count"], 0)

    def test_known_watch_urls_and_event_page_only_routes_are_distinguished(self):
        by_id = {row["candidate_id"]: row for row in self.internal["content_candidates"]}
        direct = [row for row in by_id.values() if row["video_id"]]
        unresolved = [row for row in by_id.values() if row["video_id"] is None]
        for row in direct:
            self.assertEqual(row["provider"], "YOUTUBE")
            self.assertEqual(row["official_video_url"], f"https://www.youtube.com/watch?v={row['video_id']}")
            self.assertEqual(row["watch_route"]["kind"], "OFFICIAL_YOUTUBE_VIDEO")
            self.assertEqual(row["watch_route"]["status"], "URL_IDENTIFIED_PLAYBACK_NOT_TESTED")
            self.assertEqual(row["publisher"], "World Table Tennis")
        for row in unresolved:
            self.assertEqual(row["provider"], "UNKNOWN")
            self.assertIsNone(row["official_video_url"])
            self.assertEqual(row["watch_route"]["kind"], "OFFICIAL_EVENT_PAGE_LISTING")
            self.assertEqual(row["watch_route"]["status"], "OFFICIAL_LISTING_ONLY_VIDEO_URL_UNRESOLVED")
            self.assertIsNone(row["published_at"])
            self.assertEqual(row["publisher_identity_status"], "EVENT_PAGE_LISTING_ONLY")

    def test_no_match_video_join_is_created_and_relationship_scope_is_limited(self):
        self.assertTrue(all(row["match_id"] is None and row["match_link_status"] == "UNKNOWN" for row in self.internal["content_candidates"]))
        self.assertEqual(self.internal["quality_summary"]["match_video_links"], 0)
        self.assertTrue(all(row["to_type"] == "EVENT" for row in self.internal["relationships"]))
        self.assertTrue(all("NOT_MATCH_LINK" in row["confidence_scope"] or "NOT_CLIP_APPEARANCE" in row["confidence_scope"] for row in self.internal["relationships"]))
        self.assertFalse(any(row["relationship_kind"] == "LISTED_AS_EVENT_RELATED_VIDEO" and row["from_type"] == "ATHLETE" for row in self.internal["relationships"]))

    def test_star_profiles_are_minimal_and_profile_rights_remain_unknown(self):
        serialized = json.dumps(self.internal, ensure_ascii=False)
        self.assertNotIn("date_of_birth", serialized)
        self.assertNotIn("current_ranking", serialized)
        for star in self.internal["stars"]:
            self.assertEqual(star["public_listing"], "UNKNOWN")
            self.assertEqual(star["portrait_url"], None)
            self.assertEqual(star["display_permissions"]["portrait_display"], "UNKNOWN")
            self.assertEqual(star["equipment_status"], "UNKNOWN")
            self.assertEqual(star["coach_observation_status"], "NOT_COLLECTED")

    def test_no_local_paths_thumbnails_or_video_bytes_escape(self):
        serialized = json.dumps(self.internal, ensure_ascii=False)
        self.assertNotIn("C:\\", serialized)
        self.assertNotIn("i.ytimg.com", serialized)
        self.assertNotIn("video_local_path", serialized)
        self.assertNotIn("video_bytes", serialized)
        self.assertTrue(all(row["thumbnail_url"] is None for row in self.internal["content_candidates"]))

    def test_existing_35_record_internal_catalog_is_hashed_but_not_joined(self):
        reference = json.loads((INTEGRATION_DIR / "generated" / "goal11-match-library" / "match-library-internal-review.json").read_text(encoding="utf-8"))
        self.assertEqual(reference["quality_summary"]["unique_video_sources"], 35)
        self.assertEqual(reference["analysis_compatibility"]["catalog_sources_linked_to_review_data"], 0)
        self.assertTrue(any(row["logical_name"] == "goal11-match-library-internal-reference" for row in self.internal["source_manifest"]))
        self.assertEqual(len(self.internal["content_candidates"]), 20)
        self.assertFalse(any(row.get("source_id") for row in self.internal["content_candidates"]))

    def test_duplicate_candidate_id_is_rejected(self):
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][1]["candidate_id"] = fixture["content_candidates"][0]["candidate_id"]
        with self.assertRaisesRegex(FanContentError, "duplicate candidate_id"):
            build(fixture)

    def test_candidate_cannot_upgrade_rights_or_insert_match_identity(self):
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][0]["rights"] = {"public_listing": "ALLOWED"}
        with self.assertRaisesRegex(FanContentError, "unsupported, inferred, or missing"):
            build(fixture)
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][0]["match_id"] = "match:guessed"
        with self.assertRaises(FanContentError):
            build(fixture)

    def test_wrong_video_id_or_title_evidence_is_rejected(self):
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][0]["video_id"] = "AAAAAAAAAAA"
        with self.assertRaisesRegex(FanContentError, "does not bind"):
            build(fixture)
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][0]["title"] = "invented highlight title"
        with self.assertRaisesRegex(FanContentError, "title"):
            build(fixture)

    def test_unknown_event_or_unsupported_protocol_is_rejected(self):
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["content_candidates"][0]["event_id"] = "event:unknown"
        with self.assertRaisesRegex(FanContentError, "unknown event_id"):
            build(fixture)
        fixture = copy.deepcopy(OBSERVATIONS)
        fixture["contract_version"] = "ptti.fan-content-intelligence/9.9"
        with self.assertRaisesRegex(FanContentError, "unsupported observation contract"):
            build(fixture)

    def test_unknown_dohaday1_2024_entry_is_not_imported(self):
        titles = [row["title"] for row in self.internal["content_candidates"]]
        self.assertFalse(any("WTTDoha 2024" in title for title in titles))
        self.assertTrue(any("Top Points of Day 2 | #WTTDoha 2025" == title for title in titles))


if __name__ == "__main__":
    unittest.main()
