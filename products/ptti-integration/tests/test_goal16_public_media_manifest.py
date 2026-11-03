from __future__ import annotations

import copy
import importlib.util
import unittest


SCRIPT = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts/validate_public_media_manifest.py"
SPEC = importlib.util.spec_from_file_location("validate_public_media_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PublicMediaManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = MODULE.load_json(MODULE.MANIFEST_PATH)

    def test_manifest_schema_and_strict_package_identity(self):
        result = MODULE.validate_files()
        self.assertEqual(result, {"candidate_assets": 9, "unresolved_leads": 1, "strict_public_assets": 0, "existing_public_matches": 5})

    def test_candidate_records_keep_match_ids_and_media_hashes_unbound(self):
        MODULE.validate_data(self.data)
        self.assertTrue(all(asset["match_id"] is None for asset in self.data["assets"]))
        self.assertTrue(all(asset["media_sha256"] is None for asset in self.data["assets"]))

    def test_duplicate_asset_id_is_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["assets"][1]["asset_id"] = bad["assets"][0]["asset_id"]
        with self.assertRaisesRegex(MODULE.ManifestValidationError, "asset_id values must be unique"):
            MODULE.validate_data(bad)

    def test_display_permission_promotion_is_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["assets"][0]["display_permission"] = "ALLOWED"
        with self.assertRaises(Exception):
            MODULE.validate_data(bad)

    def test_category_only_lead_cannot_claim_depicted_athlete(self):
        bad = copy.deepcopy(self.data)
        bad["unresolved_leads"][0]["depicted_athletes"] = ["Lin Shidong"]
        with self.assertRaises(Exception):
            MODULE.validate_data(bad)

    def test_fake_or_uncomputed_media_sha_is_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["assets"][0]["media_sha256"] = "a" * 64
        with self.assertRaisesRegex(MODULE.ManifestValidationError, "may only be populated"):
            MODULE.validate_data(bad)

    def test_unknown_fields_are_rejected_by_whitelist_schema(self):
        bad = copy.deepcopy(self.data)
        bad["assets"][0]["internal_source_manifest_path"] = "private/list.json"
        with self.assertRaises(Exception):
            MODULE.validate_data(bad)

    def test_photograph_is_not_linked_to_goal15_match_without_direct_evidence(self):
        bad = copy.deepcopy(self.data)
        bad["assets"][0]["match_id"] = "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun"
        with self.assertRaisesRegex(MODULE.ManifestValidationError, "no Goal15 match-photo link"):
            MODULE.validate_data(bad)


if __name__ == "__main__":
    unittest.main()
