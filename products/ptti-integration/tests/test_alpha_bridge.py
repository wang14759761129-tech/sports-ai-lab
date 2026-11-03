from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from alpha_bridge import build_bridge, binding_sandbox, inspect_binding, inspect_native_acceptance, write_bridge
from alpha_demo import read_fixture
from adapters import UnsupportedContractVersion


class AlphaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.records = read_fixture("web-alpha-46f1826d.json")
        self.report = read_fixture("native-user-acceptance-goal04.json")
        self.sandbox, self.binding = binding_sandbox()

    def test_bridge_has_four_real_matches_and_no_public_permission_uplift(self):
        result = build_bridge(self.records, self.report)
        self.assertEqual(result["counts"], {"real_matches": 4, "real_sources": 4, "public_sources": 0, "real_local_assets": 0})
        for view in result["web"].values():
            self.assertEqual(view["local_video_assets"], [])
            self.assertNotIn("synthetic", json.dumps(view).lower())
        self.assertTrue(all(not row["local_asset_ids"] for row in result["real_associations"]))

    def test_explicit_sandbox_links_match_source_asset_and_pts_without_native_pass(self):
        source, asset = self.sandbox["video_sources"][0], self.sandbox["local_video_assets"][0]
        self.assertEqual(source["match_id"], asset["match_id"])
        self.assertEqual(inspect_binding(self.sandbox, self.binding), {"status": "SIMULATED_ONLY", "failures": [], "time_seconds": 15.0})
        self.assertEqual(asset["desktop_playback"]["status"], "NOT_TESTED")
        self.assertEqual(asset["vision_result"]["status"], "NO_VERIFIED_RESULT")

    def test_source_version_hash_and_pending_hash_fail_closed(self):
        for field, value, error in (("source_version_id", None, "SOURCE_VERSION_ID_MISSING"),
                                    ("hash_status", "PENDING", "SOURCE_VERSION_HASH_PENDING_OR_INVALID"),
                                    ("source_version_sha256", "b" * 64, "LOCAL_BYTES_HASH_MISMATCH")):
            binding = {**self.binding, field: value}
            result = inspect_binding(self.sandbox, binding)
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn(error, result["failures"])

    def test_pts_time_base_origin_and_timeline_negative_cases(self):
        for update in ({"time_base": None}, {"time_base": {"numerator": 1, "denominator": 0}},
                       {"time_base": {"numerator": 1, "denominator": 120}}, {"observation_pts": True},
                       {"observation_pts": 1.5}, {"origin_pts": None}, {"observation_pts": -1},
                       {"timeline_id": "different"}, {"time_basis": "FPS_ESTIMATE"},
                       {"observation_pts": 999999999}):
            with self.subTest(update=update):
                result = inspect_binding(self.sandbox, {**self.binding, **update})
                self.assertEqual(result["status"], "REJECTED")
                self.assertIsNone(result["time_seconds"])

    def test_pts_uses_explicit_origin_not_fps(self):
        result = inspect_binding(self.sandbox, {**self.binding, "observation_pts": 245760, "origin_pts": 15360})
        self.assertEqual(result["time_seconds"], 15.0)

    def test_missing_source_asset_or_review_cannot_create_edge(self):
        for update in ({"source_id": "missing"}, {"local_asset_id": "missing"},
                       {"review_status": "REVIEW_REQUIRED"}, {"evidence_refs": []},
                       {"reviewed_at": None}):
            self.assertEqual(inspect_binding(self.sandbox, {**self.binding, **update})["status"], "REJECTED")

    def test_synthetic_record_cannot_enter_real_catalog(self):
        self.records[0]["fixture_only"] = True
        with self.assertRaisesRegex(ValueError, "Real catalog rejects synthetic"):
            build_bridge(self.records, self.report)

    def test_native_user_confirmation_kept_but_unbound_and_vision_unknown(self):
        result = build_bridge(self.records, self.report)
        assessment = result["native_acceptance"]["assessment"]
        self.assertEqual(assessment["status"], "UNBOUND_REVIEW_REQUIRED")
        self.assertEqual(assessment["operations"]["play"], "USER_REPORTED_PASS")
        self.assertIn("exe_sha256", assessment["missing_bindings"])
        self.assertEqual(assessment["vision_analysis"], "NOT_TESTED")
        self.assertTrue(all(row["evidence"]["desktop_native_playback"]["status"] == "NOT_TESTED"
                            for row in result["web"]["internal_review"]["video_sources"]))

    def test_complete_claim_on_synthetic_asset_never_becomes_native_pass(self):
        report = {**self.report, "app_git_sha": "c" * 40, "exe_sha256": "d" * 64,
                  "source_sha256": "a" * 64, "source_id": self.binding["source_id"],
                  "local_asset_id": self.binding["local_asset_id"], "tested_at": "2026-10-13T00:00:00Z"}
        result = inspect_native_acceptance(self.sandbox, report, self.binding)
        self.assertEqual(result["status"], "UNBOUND_REVIEW_REQUIRED")
        self.assertIn("verified_source_version_binding", result["missing_bindings"])

    def test_sidecar_and_contract_versions_reject_silent_downgrade(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            inspect_binding(self.sandbox, {**self.binding, "binding_version": "0.0"})
        with self.assertRaises(UnsupportedContractVersion):
            inspect_binding({**self.sandbox, "contract_version": "ptti.match-media/0.1"}, self.binding)

    def test_latest_san_snapshot_is_bound_to_exact_commit_and_file_hash(self):
        import hashlib
        manifest = read_fixture("alpha-bridge-inputs.json")
        self.assertEqual(manifest["web_git_sha"], "46f1826d80edf19147cc492e26c5461048841608")
        actual = hashlib.sha256((PACKAGE / "fixtures" / manifest["web_snapshot_file"]).read_bytes()).hexdigest()
        self.assertEqual(actual, manifest["web_snapshot_sha256"])

    def test_native_manifest_hashes_are_not_inferred_from_other_branch_head(self):
        bridge = build_bridge(self.records, self.report)
        raw = bridge["native_acceptance"]["reported"]
        self.assertIsNone(raw["app_git_sha"])
        self.assertIsNone(raw["exe_sha256"])
        self.assertIsNone(raw["source_sha256"])

    def test_original_contract_remains_v02_and_source_types_are_preserved(self):
        bridge = build_bridge(self.records, self.report)
        catalog = bridge["web"]["internal_review"]
        self.assertEqual(catalog["contract_version"], "ptti.match-media/0.2")
        types = {row["source_id"]: row["resource_kind"] for row in catalog["video_sources"]}
        self.assertEqual(types["web-source:doha-2023-ms-final"], "OFFICIAL_EVENT_PAGE")
        self.assertEqual(types["web-source:doha-2023-ms-sf-fan-lin"], "VIDEO_PAGE")
        self.assertEqual(catalog["timeline_mappings"], [])

    def test_exports_are_split_readonly_repeatable_and_refuse_overwrite(self):
        before = copy.deepcopy(self.records)
        bridge = build_bridge(self.records, self.report)
        self.assertEqual(self.records, before)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_bridge(root, bridge)
            self.assertEqual(first, write_bridge(root, bridge))
            public = json.loads((root / "web-strict-public.json").read_text(encoding="utf-8"))
            self.assertEqual(public["video_sources"], [])
            self.assertNotIn("local_locator_ref", (root / "web-internal-review.json").read_text(encoding="utf-8"))
            (root / "web-strict-public.json").write_text("changed")
            with self.assertRaises(FileExistsError):
                write_bridge(root, bridge)


if __name__ == "__main__":
    unittest.main()
