from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR / "scripts"))

from build_goal14_main_content_expansion import (  # noqa: E402
    DEFAULT_BASE,
    DEFAULT_FAN,
    DEFAULT_INTERNAL,
    DEFAULT_REVIEW,
    ExpansionError,
    build_expansion,
)

PACKAGE_SCHEMA = json.loads((INTEGRATION_DIR / "contracts" / "match-library-index-v0.1.schema.json").read_text(encoding="utf-8"))
AUDIT_SCHEMA = json.loads((INTEGRATION_DIR / "contracts" / "goal14-main-content-candidate-audit-v0.1.schema.json").read_text(encoding="utf-8"))
OUTPUT_DIR = INTEGRATION_DIR / "generated" / "goal14-main-content-expansion-v0.1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Goal14MainContentExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = load(DEFAULT_BASE)
        cls.internal = load(DEFAULT_INTERNAL)
        cls.fan = load(DEFAULT_FAN)
        cls.review = load(DEFAULT_REVIEW)
        cls.paths = {"base": DEFAULT_BASE, "internal": DEFAULT_INTERNAL, "fan": DEFAULT_FAN, "review": DEFAULT_REVIEW}
        cls.package, cls.audit = build_expansion(
            cls.base, cls.internal, cls.fan, cls.review, "2026-10-18T10:46:06Z", cls.paths
        )

    def test_generated_package_and_candidate_audit_match_versioned_schemas(self) -> None:
        Draft202012Validator.check_schema(PACKAGE_SCHEMA)
        Draft202012Validator(PACKAGE_SCHEMA, format_checker=FormatChecker()).validate(self.package)
        Draft202012Validator.check_schema(AUDIT_SCHEMA)
        Draft202012Validator(AUDIT_SCHEMA, format_checker=FormatChecker()).validate(self.audit)
        self.assertEqual(self.package, load(OUTPUT_DIR / "match-library-strict-public.json"))
        self.assertEqual(self.audit, load(OUTPUT_DIR / "candidate-review-internal.json"))
        self.assertEqual(self.package["contract_version"], "ptti.match-library-index/0.1")
        for entry in self.package["source_manifest"]:
            path = ROOT / Path(entry["file"])
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])

    def test_additive_package_has_two_new_verified_match_video_edges(self) -> None:
        self.assertEqual((len(self.package["matches"]), len(self.package["video_sources"]), len(self.package["stars"])), (3, 13, 3))
        matches = {row["match_id"]: row for row in self.package["matches"]}
        sources = {row["source_id"]: row for row in self.package["video_sources"]}
        doha_id = "pro:wtt:doha-star-contender-2025:harimoto-jonathan-groth"
        fukuoka_id = "pro:wtt:wtt-finals-fukuoka-2024:chen-xingtong-wang-manyu-ws-final"
        for match_id, video_id in ((doha_id, "jv_XQ6oKaDU"), (fukuoka_id, "lb4UMbE8Pfs")):
            match = matches[match_id]
            source = sources[f"video-source:youtube:{video_id}"]
            self.assertEqual(match["match_video_link_status"], "HUMAN_VERIFIED")
            self.assertEqual(match["video_source_ids"], [source["source_id"]])
            self.assertEqual(source["canonical_match_id"], match_id)
            self.assertEqual(source["match_link_status"], "HUMAN_VERIFIED")
            self.assertEqual(source["completeness_status"], "UNVERIFIED")
            self.assertEqual(source["content_type_claim"], "UNKNOWN")
            self.assertIsNone(match["provider_match_id"])
        self.assertEqual(matches[fukuoka_id]["recorded_result"], {"player_a_games": 3, "player_b_games": 4})
        self.assertTrue(all(p["athlete_id"] is None for p in matches[fukuoka_id]["participants"]))
        self.assertEqual(self.package["quality_summary"]["current_session_playback_pass_count"], 0)

    def test_all_twenty_internal_candidates_have_individual_decisions(self) -> None:
        self.assertEqual(self.audit["candidate_count"], 20)
        self.assertEqual(self.audit["decision_counts"], {
            "PUBLIC_OFFICIAL_EXTERNAL_LINK_ONLY": 10,
            "INTERNAL_ONLY_VIDEO_ID_UNRESOLVED": 10,
        })
        package_sources = {row["source_id"] for row in self.package["video_sources"]}
        for item in self.audit["candidates"]:
            if item["decision"] == "INTERNAL_ONLY_VIDEO_ID_UNRESOLVED":
                self.assertIsNone(item["video_id"])
                self.assertIsNone(item["official_video_url"])
                self.assertNotIn(item["candidate_id"], package_sources)
            else:
                self.assertEqual(item["match_link_status"], "UNKNOWN")
                self.assertIn(f"video-source:youtube:{item['video_id']}", package_sources)

    def test_event_highlights_have_no_guessed_match_or_player_relationship(self) -> None:
        highlights = [row for row in self.package["video_sources"] if row["match_type"] == "UNKNOWN"]
        self.assertEqual(len(highlights), 10)
        self.assertTrue(all(row["canonical_match_id"] is None and row["match_link_status"] == "UNKNOWN" for row in highlights))
        self.assertTrue(all(row["participants_claimed"] == {"unassigned_names": []} for row in highlights))
        self.assertTrue(all(row["completeness_status"] == "UNVERIFIED" for row in highlights))

    def test_all_media_use_and_playback_permissions_fail_closed(self) -> None:
        for source in self.package["video_sources"]:
            self.assertEqual(source["rights"]["public_listing"], "ALLOWED")
            self.assertEqual(source["rights"]["external_viewing"], "ALLOWED")
            self.assertEqual(source["rights"]["embedding"], "UNKNOWN")
            self.assertEqual(source["rights"]["thumbnail_display"], "NOT_ALLOWED")
            self.assertEqual(source["rights"]["local_analysis"], "NOT_GRANTED")
            self.assertEqual(source["rights"]["redistribution"], "NOT_GRANTED")
            self.assertEqual(source["thumbnail"]["url"], None)
            self.assertEqual(source["availability"]["external_video_visual_latest_recorded"], "NOT_TESTED")
            self.assertEqual(source["availability"]["desktop_native_playback"], "NOT_TESTED")
            self.assertEqual(source["availability"]["vision_analysis"], "NOT_TESTED")
            self.assertEqual(source["availability"]["territory_availability"], "UNKNOWN")
        self.assertEqual(self.package["local_video_assets"], [])
        self.assertEqual(self.package["analysis_compatibility"]["playback_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_public_star_addition_is_narrow_and_evidence_backed(self) -> None:
        star = next(row for row in self.package["stars"] if row["athlete_id"] == "athlete:123980")
        self.assertEqual(star["public_listing"], "ALLOWED")
        self.assertEqual(star["public_listing_scope"], "FACTUAL_NAME_STABLE_REGISTRY_ID_AND_OFFICIAL_PROFILE_LINK_ONLY_NO_PORTRAIT_OR_BIOGRAPHY")
        self.assertEqual(star["evidence_source_ids"], ["wtt-profile-123980"])
        self.assertIsNone(star["name_zh"])
        self.assertIsNone(star["association"])

    def test_rejects_duplicate_candidate_ids_and_review_rights_escalation(self) -> None:
        duplicate = copy.deepcopy(self.fan)
        duplicate["clips"][1]["clip_id"] = duplicate["clips"][0]["clip_id"]
        with self.assertRaisesRegex(ExpansionError, "duplicate-candidate-id"):
            build_expansion(self.base, self.internal, duplicate, self.review, "2026-10-18T10:46:06Z", self.paths)

        escalated = copy.deepcopy(self.review)
        escalated["media_rights"]["embedding"] = "ALLOWED"
        with self.assertRaisesRegex(ExpansionError, "media-rights-default-escalation"):
            build_expansion(self.base, self.internal, self.fan, escalated, "2026-10-18T10:46:06Z", self.paths)

    def test_rejects_video_id_url_title_event_or_publisher_mismatch(self) -> None:
        mutations = [
            (lambda d: d["clips"][0].update(official_video_url="https://www.youtube.com/watch?v=other"), "candidate-video-url-mismatch"),
            (lambda d: d["clips"][0].update(title_original="unrelated highlight"), "candidate-title-evidence-mismatch"),
            (lambda d: d["clips"][0].update(publisher="unverified uploader"), "candidate-publisher-mismatch"),
        ]
        for mutate, expected in mutations:
            changed = copy.deepcopy(self.fan)
            mutate(changed)
            with self.subTest(expected=expected), self.assertRaisesRegex(ExpansionError, expected):
                build_expansion(self.base, self.internal, changed, self.review, "2026-10-18T10:46:06Z", self.paths)

        changed_review = copy.deepcopy(self.review)
        changed_review["event_highlight_video_ids"].append("invented-video-id")
        with self.assertRaisesRegex(ExpansionError, "invalid-highlight-allowlist"):
            build_expansion(self.base, self.internal, self.fan, changed_review, "2026-10-18T10:46:06Z", self.paths)

    def test_evidence_references_are_resolvable_in_expanded_package(self) -> None:
        evidence_ids = {row["source_id"] for row in self.package["evidence_sources"]}
        for match in self.package["matches"]:
            self.assertTrue(set(match["evidence_source_ids"]) <= evidence_ids)
            self.assertTrue(set(match["rights"]["evidence_source_ids"]) <= evidence_ids)
        for source in self.package["video_sources"]:
            self.assertTrue(set(source["rights"]["evidence_source_ids"]) <= evidence_ids)
            provenance_ids = {row["source_id"] for row in source["provenance"] if isinstance(row.get("source_id"), str)}
            self.assertTrue(provenance_ids <= evidence_ids)
        for star in self.package["stars"]:
            self.assertTrue(set(star["evidence_source_ids"]) <= evidence_ids)


if __name__ == "__main__":
    unittest.main()
