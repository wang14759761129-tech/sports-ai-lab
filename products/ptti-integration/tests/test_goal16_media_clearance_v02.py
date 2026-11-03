from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_goal16_public_media.py"
SPEC = importlib.util.spec_from_file_location("build_goal16_public_media", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class Goal16MediaClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = MODULE.read_json(MODULE.REVIEW_PATH)
        cls.public = MODULE.read_json(MODULE.PUBLIC_PATH)

    def test_strict_media_package_and_source_manifest_validate(self):
        result = MODULE.validate_files()
        self.assertEqual(result["reviewed_candidate_count"], 9)
        self.assertEqual(result["editorial_profile_cleared_count"], 4)
        self.assertEqual(result["not_cleared_count"], 5)
        self.assertEqual(result["strict_public_assets"], 4)
        self.assertEqual(result["derivatives"], 8)

    def test_all_nine_candidates_have_a_specific_review_and_unlinked_match_status(self):
        MODULE.validate_schema(self.review, MODULE.REVIEW_SCHEMA_PATH, "review")
        self.assertEqual(len({item["asset_id"] for item in self.review["assets"]}), 9)
        self.assertTrue(all(item["match_photo_use"] == "NOT_CLEARED_NO_GOAL15_MATCH_LINK" for item in self.review["assets"]))

    def test_only_four_scoped_editorial_assets_enter_public_package(self):
        MODULE.validate_schema(self.public, MODULE.PUBLIC_SCHEMA_PATH, "public")
        expected = MODULE.EXPECTED_APPROVED_IDS
        self.assertEqual({item["asset_id"] for item in self.public["assets"]}, expected)
        self.assertTrue(all(item["use_scope"] == "ATHLETE_PROFILE_EDITORIAL_ONLY" for item in self.public["assets"]))
        self.assertTrue(all(item["promotion_use"] == "NOT_CLEARED_NO_ENDORSEMENT_OR_HOMEPAGE_PROMOTION" for item in self.public["assets"]))

    def test_photos_never_become_goal15_match_photography(self):
        self.assertTrue(all(item["match_id"] is None for item in self.public["assets"]))
        self.assertTrue(all(item["match_link_status"] == "NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE" for item in self.public["assets"]))

    def test_personality_warning_and_description_conflict_remain_blocked(self):
        by_id = {item["asset_id"]: item for item in self.review["assets"]}
        for asset_id in (
            "commons:2018-yog:mixed-final-098",
            "commons:2018-yog:sun-yingsha-final-061",
            "commons:munich-2022:felix-lebrun-850-9499",
            "commons:2018-yog:lin-yun-ju-bronze-544",
        ):
            self.assertNotEqual(by_id[asset_id]["editorial_profile_use"], "CLEARED_SCOPED")
        self.assertIn("description_conflict", by_id["commons:2018-yog:sun-yingsha-final-061"]["clearance_status"].lower())

    def test_chen_xingtong_does_not_join_by_name_without_canonical_id(self):
        item = next(row for row in self.review["assets"] if row["asset_id"] == "commons:acttc-2016:chen-xingtong-2")
        self.assertIsNone(item["athlete_id"])
        self.assertEqual(item["clearance_status"], "NOT_CLEARED_CANONICAL_ATHLETE_ID_UNKNOWN")

    def test_public_schema_rejects_promotional_scope_or_internal_path(self):
        bad = copy.deepcopy(self.public)
        bad["assets"][0]["use_scope"] = "HOMEPAGE_HERO"
        with self.assertRaises(MODULE.MediaPackageError):
            MODULE.validate_schema(bad, MODULE.PUBLIC_SCHEMA_PATH, "public")
        bad = copy.deepcopy(self.public)
        bad["assets"][0]["internal_path"] = "C:/private/reviewed-originals/photo.jpg"
        with self.assertRaises(MODULE.MediaPackageError):
            MODULE.validate_schema(bad, MODULE.PUBLIC_SCHEMA_PATH, "public")

    def test_public_schema_rejects_match_link_or_uncredited_asset(self):
        bad = copy.deepcopy(self.public)
        bad["assets"][0]["match_id"] = "pro:wtt:goal15:unverified"
        with self.assertRaises(MODULE.MediaPackageError):
            MODULE.validate_schema(bad, MODULE.PUBLIC_SCHEMA_PATH, "public")
        bad = copy.deepcopy(self.public)
        bad["assets"][0]["attribution"] = ""
        with self.assertRaises(MODULE.MediaPackageError):
            MODULE.validate_schema(bad, MODULE.PUBLIC_SCHEMA_PATH, "public")

    def test_derivative_path_traversal_is_rejected(self):
        bad = copy.deepcopy(self.public)
        bad["assets"][0]["derivatives"][0]["path"] = "assets/../../private.jpg"
        with self.assertRaises(MODULE.MediaPackageError):
            MODULE.validate_schema(bad, MODULE.PUBLIC_SCHEMA_PATH, "public")

    def test_builder_rejects_a_source_sha_mismatch_before_derivative_generation(self):
        with patch.object(MODULE, "sha256_file", return_value="0" * 64):
            with self.assertRaisesRegex(MODULE.MediaPackageError, "reviewed original SHA-256 mismatch"):
                MODULE.build()

    def test_existing_strict_match_library_remains_five_match_package(self):
        data = MODULE.read_json(MODULE.OLD_STRICT_PACKAGE)
        self.assertEqual(data["view"], "STRICT_PUBLIC")
        self.assertEqual(len(data["matches"]), 5)


if __name__ == "__main__":
    unittest.main()
