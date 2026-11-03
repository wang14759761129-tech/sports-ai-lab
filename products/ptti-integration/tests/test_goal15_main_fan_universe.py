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

from build_goal15_main_fan_universe import (  # noqa: E402
    AdmissionError,
    BASE_PATH,
    FIXTURE_PATH,
    GENERATOR_PATH,
    SCHEMA_PATH,
    build_package,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Goal15MainFanUniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = load(BASE_PATH)
        cls.fixture = load(FIXTURE_PATH)
        cls.schema = load(SCHEMA_PATH)

    def build(self, fixture: dict | None = None) -> tuple[dict, dict]:
        return build_package(
            copy.deepcopy(self.base),
            copy.deepcopy(fixture if fixture is not None else self.fixture),
            "2026-10-18T10:56:58Z",
            BASE_PATH,
            FIXTURE_PATH,
        )

    def test_package_is_schema_valid_and_additive(self) -> None:
        package, _ = self.build()
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema, format_checker=FormatChecker()).validate(package)
        self.assertEqual((len(package["matches"]), len(package["video_sources"]), len(package["stars"])), (5, 15, 8))
        self.assertEqual(len(package["local_video_assets"]), 0)

    def test_two_new_exact_match_source_links_are_bound(self) -> None:
        package, _ = self.build()
        for match_id, source_id in (
            ("pro:wtt:china-smash-2025:sun-yingsha-wang-manyu-ws-final", "video-source:youtube:ttUevnAZSEY"),
            ("pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final", "video-source:youtube:cDccQqVlMnc"),
        ):
            match = next(row for row in package["matches"] if row["match_id"] == match_id)
            source = next(row for row in package["video_sources"] if row["source_id"] == source_id)
            self.assertEqual(match["video_source_ids"], [source_id])
            self.assertEqual(match["match_video_link_status"], "HUMAN_VERIFIED")
            self.assertEqual(source["canonical_match_id"], match_id)
            self.assertEqual(source["match_link_status"], "HUMAN_VERIFIED")
            self.assertEqual(source["availability"]["current_session_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_full_match_is_a_publisher_title_claim_not_completeness_proof(self) -> None:
        package, _ = self.build()
        new_sources = [row for row in package["video_sources"] if row["video_id"] in {"ttUevnAZSEY", "cDccQqVlMnc"}]
        self.assertEqual({row["content_type_claim"] for row in new_sources}, {"FULL_MATCH"})
        self.assertTrue(all(row["completeness_status"] == "UNVERIFIED" for row in new_sources))
        self.assertTrue(all(row["availability"]["external_video_visual_latest_recorded"] == "NOT_TESTED" for row in new_sources))

    def test_media_rights_and_thumbnails_fail_closed(self) -> None:
        package, _ = self.build()
        for source in package["video_sources"]:
            self.assertIn(source["rights"]["embedding"], {"UNKNOWN", "NOT_ALLOWED"})
            self.assertNotEqual(source["rights"]["local_analysis"], "ALLOWED")
            self.assertNotEqual(source["rights"]["redistribution"], "ALLOWED")
            self.assertIsNone(source["thumbnail"]["url"])
            self.assertEqual(source["availability"]["desktop_native_playback"], "NOT_TESTED")
            self.assertEqual(source["availability"]["vision_analysis"], "NOT_TESTED")

    def test_eight_requested_stars_have_identity_sources_no_portraits_or_gear_claims(self) -> None:
        package, audit = self.build()
        target_ids = {"athlete:121558", "athlete:131163", "athlete:121411", "athlete:137237", "athlete:119588", "athlete:135049", "athlete:135977", "athlete:123980"}
        self.assertEqual({star["athlete_id"] for star in package["stars"]}, target_ids)
        for star in package["stars"]:
            self.assertEqual(star["equipment"]["status"], "UNKNOWN")
            self.assertEqual(star["equipment"]["items"], [])
        for athlete in audit["athlete_review"]:
            self.assertEqual(athlete["official_social_account"], "NOT_VERIFIED")
            self.assertEqual(athlete["social_urls"], [])
            self.assertEqual(athlete["equipment_model"], "UNKNOWN")
            self.assertEqual(athlete["portrait_display"], "NOT_GRANTED_OR_NOT_VERIFIED")

    def test_claimed_content_census_is_explicitly_not_playback(self) -> None:
        package, audit = self.build()
        census = package["quality_summary"]["content_type_claim_counts"]
        self.assertEqual(census["FULL_MATCH"], 3)
        self.assertEqual(census["HIGHLIGHTS"], 10)
        self.assertEqual(census["UNKNOWN"], 2)
        self.assertEqual(package["quality_summary"]["shorts_source_count"], 0)
        self.assertEqual(audit["video_type_review"]["verified_complete_match_count"], 0)
        self.assertEqual(package["quality_summary"]["current_session_playback_pass_count"], 0)

    def test_rejects_duplicate_identity_bad_video_binding_and_rights_escalation(self) -> None:
        mutations = [
            (lambda row: row.update(source_id="video-source:youtube:anotherID"), "source-id-video-id-mismatch"),
            (lambda row: row.update(official_url="https://www.youtube.com/watch?v=bad"), "official-url-video-id-mismatch"),
            (lambda row: row["rights"].update(embedding="ALLOWED"), "media-rights-escalation"),
            (lambda row: row.update(title_claim_participant_b="Unrelated Player"), "video-title-participant-mismatch"),
        ]
        for mutate, expected in mutations:
            fixture = copy.deepcopy(self.fixture)
            mutate(fixture["admissions"][0])
            with self.subTest(expected=expected), self.assertRaisesRegex(AdmissionError, expected):
                self.build(fixture)

    def test_rejects_unknown_contract_or_unverified_evidence_reference(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["contract_version"] = "ptti.goal15-content-admissions/0.99"
        with self.assertRaisesRegex(AdmissionError, "unsupported-admissions-version"):
            self.build(fixture)
        fixture = copy.deepcopy(self.fixture)
        fixture["admissions"][0]["video_evidence_ids"] = ["missing-evidence"]
        with self.assertRaisesRegex(AdmissionError, "unknown-admission-evidence-reference"):
            self.build(fixture)

    def test_manifest_binds_exact_fixture_and_base_bytes(self) -> None:
        package, _ = self.build()
        manifest = {row["file"]: row["sha256"] for row in package["source_manifest"]}
        self.assertEqual(manifest["products/ptti-integration/fixtures/goal15-main-fan-universe-v0.1/admissions.json"], hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest())
        self.assertEqual(manifest["products/ptti-integration/generated/goal14-main-content-expansion-v0.1/match-library-strict-public.json"], hashlib.sha256(BASE_PATH.read_bytes()).hexdigest())
        self.assertEqual(manifest["products/ptti-integration/scripts/build_goal15_main_fan_universe.py"], hashlib.sha256(GENERATOR_PATH.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
