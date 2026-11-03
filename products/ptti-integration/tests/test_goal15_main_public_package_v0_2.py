from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRATION_DIR / "scripts"))

from project_goal15_main_public_package_v0_2 import (  # noqa: E402
    OUTPUT_PATH,
    SCHEMA_PATH,
    SOURCE_PATH,
    ProjectionError,
    project_public_package,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def walk_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value


class Goal15MainPublicPackageV02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = load(SOURCE_PATH)
        cls.schema = load(SCHEMA_PATH)

    def project(self, source: dict | None = None) -> dict:
        return project_public_package(copy.deepcopy(source if source is not None else self.source), "2026-10-18T20:00:00Z")

    def test_schema_valid_minimal_projection_preserves_public_content_counts(self) -> None:
        package = self.project()
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema, format_checker=FormatChecker()).validate(package)
        self.assertEqual(package["contract_version"], "ptti.match-library-index/0.1")
        self.assertEqual((len(package["matches"]), len(package["video_sources"]), len(package["stars"])), (5, 15, 8))
        self.assertEqual(package["source_manifest"], [])
        self.assertEqual(len(self.source["source_manifest"]), 7)
        self.assertEqual(package["local_video_assets"], [])

    def test_five_exact_match_video_edges_and_ten_event_highlights_remain(self) -> None:
        package = self.project()
        summary = package["quality_summary"]
        self.assertEqual(summary["public_match_video_link_count"], 5)
        self.assertEqual(summary["event_level_highlight_source_count"], 10)
        self.assertEqual(summary["content_type_claim_counts"], {"FULL_MATCH": 3, "HIGHLIGHTS": 10, "SHORTS": 0, "UNKNOWN": 2})
        sources = {row["source_id"]: row for row in package["video_sources"]}
        for match in package["matches"]:
            self.assertEqual(len(match["video_source_ids"]), 1)
            source = sources[match["video_source_ids"][0]]
            self.assertEqual(source["canonical_match_id"], match["match_id"])
            self.assertEqual(source["match_link_status"], "HUMAN_VERIFIED")
            self.assertEqual(match["match_video_link_status"], "HUMAN_VERIFIED")

    def test_rights_unknowns_and_unverified_playback_are_preserved(self) -> None:
        package = self.project()
        original_sources = {row["source_id"]: row for row in self.source["video_sources"]}
        for source in package["video_sources"]:
            original = original_sources[source["source_id"]]
            self.assertEqual(source["rights"], original["rights"])
            self.assertEqual(source["availability"], {
                key: value for key, value in original["availability"].items()
                if key in {
                    "official_page_current", "external_video_visual_latest_recorded", "external_observations",
                    "platform_embed", "desktop_native_playback", "vision_analysis", "current_session_eligibility",
                    "latest_recorded_playback_status", "territory_availability", "recorded_region_restriction", "login_or_paywall",
                }
            })
            self.assertEqual(source["rights"]["embedding"], "UNKNOWN")
            self.assertEqual(source["availability"]["desktop_native_playback"], "NOT_TESTED")
            self.assertEqual(source["availability"]["vision_analysis"], "NOT_TESTED")
        self.assertEqual(package["analysis_compatibility"]["playback_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_nested_unapproved_fields_and_internal_counts_are_excluded_by_allowlists(self) -> None:
        source = copy.deepcopy(self.source)
        source["internal_build_path"] = "<LOCAL_USER_ROOT>\\build"
        source["quality_summary"]["goal15_new_source_count"] = 987
        source["video_sources"][0]["unreviewed_internal_counter"] = 42
        source["video_sources"][0]["provenance"][0]["snapshot"] = "products/ptti-integration/fixtures/private.json"
        source["video_sources"][0]["availability"]["private_debug"] = {"disk_path": "<LOCAL_USER_ROOT>\\secret"}
        package = self.project(source)
        keys = set(walk_keys(package))
        self.assertNotIn("internal_build_path", keys)
        self.assertNotIn("goal15_new_source_count", keys)
        self.assertNotIn("unreviewed_internal_counter", keys)
        self.assertNotIn("snapshot", keys)
        self.assertNotIn("private_debug", keys)
        for internal_count in {
            "goal11_internal_video_source_count", "goal14_highlight_candidate_review_count",
            "goal14_candidate_exact_video_id_count", "goal14_candidate_event_page_only_count",
            "goal14_highlight_links_admitted", "goal15_new_match_count",
            "goal15_new_source_count", "goal15_new_star_count",
        }:
            self.assertNotIn(internal_count, keys)
        self.assertFalse(any("C:\\Users\\" in item or "products/ptti-integration/" in item for item in walk_strings(package)))

    def test_public_value_containing_internal_path_fails_closed(self) -> None:
        source = copy.deepcopy(self.source)
        source["evidence_sources"][0]["description"] = "Internal file products/ptti-integration/generated/private.json"
        with self.assertRaisesRegex(ProjectionError, "internal-path-or-build-reference-in-public-value"):
            self.project(source)

    def test_bad_reference_and_malformed_array_are_rejected(self) -> None:
        source = copy.deepcopy(self.source)
        source["video_sources"][0]["canonical_match_id"] = "pro:wtt:unknown"
        with self.assertRaisesRegex(ProjectionError, "match-video-edge-inconsistent"):
            self.project(source)
        source = copy.deepcopy(self.source)
        source["matches"].append("not-a-record")
        with self.assertRaisesRegex(ProjectionError, "invalid-source-array:matches"):
            self.project(source)

    def test_new_delivery_is_a_single_public_package_and_original_remains_untouched(self) -> None:
        self.assertTrue(OUTPUT_PATH.is_file())
        package = load(OUTPUT_PATH)
        Draft202012Validator(self.schema, format_checker=FormatChecker()).validate(package)
        self.assertEqual(set(path.name for path in OUTPUT_PATH.parent.iterdir()), {OUTPUT_PATH.name, "README-san-handoff.md"})
        self.assertEqual(hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(), "ca714727ebe43fd091b7e52a2c8e31225c6deba65fde30765e9da6f360c12ee2")
        readme = (OUTPUT_PATH.parent / "README-san-handoff.md").read_text(encoding="utf-8")
        output_hash = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
        self.assertIn(output_hash, readme)


if __name__ == "__main__":
    unittest.main()
