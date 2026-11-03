from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker


PACKAGE = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PACKAGE))

from adapters import (  # noqa: E402
    UnsupportedContractVersion,
    adapt_desktop_video_source,
    build_contract,
    to_web_safe_payload,
    validate_contract_integrity,
)
from alpha_demo import (  # noqa: E402
    CONTRACT_SCHEMA,
    build_alpha_demo,
    contract_bytes,
    write_demo_files,
)


FIXTURES = PACKAGE / "fixtures"


def read_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class AlphaDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, cls.audit = build_alpha_demo()

    def test_alpha_contract_is_v02_schema_valid_and_integrity_checked(self):
        schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.contract)), [])
        self.assertEqual(self.audit["integrity"]["status"], "PASS")
        self.assertEqual(self.audit["integrity"]["matches"], 4)
        self.assertEqual(self.audit["integrity"]["video_sources"], 6)
        self.assertEqual(self.audit["integrity"]["local_video_assets"], 1)

    def test_ids_are_stable_explicit_and_namespaced(self):
        second, _ = build_alpha_demo()
        self.assertEqual(
            [row["match_id"] for row in self.contract["matches"]],
            [row["match_id"] for row in second["matches"]],
        )
        self.assertEqual(
            [row["source_id"] for row in self.contract["video_sources"]],
            [row["source_id"] for row in second["video_sources"]],
        )
        for relation in self.audit["identity_map"]["match_sources"]:
            self.assertTrue(relation["match_id"].startswith("web-match:"))
            self.assertTrue(all(source.startswith("web-source:") for source in relation["video_source_ids"]))
        asset = self.audit["identity_map"]["local_assets"][0]
        self.assertTrue(asset["local_asset_id"].startswith("fixture-local-"))
        self.assertIsNone(asset["match_id"])
        self.assertEqual(asset["association"], "UNLINKED_REVIEW_REQUIRED")
        self.assertEqual(asset["local_video_source_edge"], "MATCH_GROUP_ONLY_V0_2_HAS_NO_DIRECT_SOURCE_VERSION_ID")

    def test_fixture_only_desktop_source_is_never_public_even_with_allowed_rights(self):
        source = next(
            row for row in self.contract["video_sources"]
            if row["source_id"] == "desktop-source:fixture-desktop-source-01"
        )
        self.assertEqual(source["rights"]["metadata_listing"], "ALLOWED")
        self.assertEqual(source["rights"]["external_viewing"], "ALLOWED")
        self.assertTrue(source["provenance"]["method"].startswith("synthetic-fixture:"))
        public = to_web_safe_payload(self.contract)
        self.assertEqual(public["video_sources"], [])
        self.assertEqual(public["matches"], [])
        self.assertEqual(public["local_video_assets"], [])

    def test_explicit_real_desktop_source_can_project_without_uplifting_territory(self):
        source = copy.deepcopy(read_fixture("desktop-video-source.json"))
        source.pop("fixture_only")
        contract = build_contract(desktop_sources=[source])
        self.assertEqual(validate_contract_integrity(contract)["video_sources"], 1)
        public = to_web_safe_payload(contract)
        self.assertEqual(len(public["video_sources"]), 1)
        self.assertEqual(public["video_sources"][0]["territory"]["status"], "UNKNOWN")

    def test_synthetic_asset_cannot_be_attached_to_a_real_match(self):
        damaged = copy.deepcopy(self.contract)
        damaged["local_video_assets"][0]["match_id"] = damaged["matches"][0]["match_id"]
        with self.assertRaisesRegex(ValueError, "Synthetic/real Match link rejected"):
            validate_contract_integrity(damaged)

    def test_real_local_asset_link_needs_verified_match_and_review_evidence(self):
        records = read_fixture("web-match-records.json")[:1]
        raw_asset = read_fixture("desktop-local-asset.json")
        raw_asset.pop("fixture_only")
        raw_asset["match_id"] = "web-match:doha-2023-ms-final"
        raw_asset["match_link_review_status"] = "REVIEW_REQUIRED"
        contract = build_contract(web_records=records, local_assets=[raw_asset])
        with self.assertRaisesRegex(ValueError, "requires a verified Match identity"):
            validate_contract_integrity(contract)

        records[0]["identityStatus"] = "VERIFIED"
        raw_asset["match_link_review_status"] = "VERIFIED"
        raw_asset["match_link_evidence_refs"] = ["human-review-2026-10-12"]
        contract = build_contract(web_records=records, local_assets=[raw_asset])
        self.assertEqual(validate_contract_integrity(contract)["local_video_assets"], 1)

    def test_cross_system_video_source_link_needs_human_evidence(self):
        records = read_fixture("web-match-records.json")[:1]
        records[0]["identityStatus"] = "VERIFIED"
        desktop = read_fixture("desktop-video-source.json")
        desktop.pop("fixture_only")
        desktop["match_id"] = "web-match:doha-2023-ms-final"
        desktop["match_link_status"] = "REVIEW_REQUIRED"
        contract = build_contract(web_records=records, desktop_sources=[desktop])
        with self.assertRaisesRegex(ValueError, "Cross-system VideoSource Match association"):
            validate_contract_integrity(contract)

        desktop["match_link_status"] = "VERIFIED"
        desktop["match_link_evidence_refs"] = ["crosswalk-review-01"]
        desktop["match_link_reviewer_ref"] = "reviewer-01"
        contract = build_contract(web_records=records, desktop_sources=[desktop])
        self.assertEqual(validate_contract_integrity(contract)["video_sources"], 2)

    def test_dangling_match_and_source_references_are_rejected(self):
        damaged = copy.deepcopy(self.contract)
        damaged["video_sources"][0]["match_id"] = "web-match:missing"
        with self.assertRaisesRegex(ValueError, "references missing Match"):
            validate_contract_integrity(damaged)

        damaged = copy.deepcopy(self.contract)
        damaged["timeline_mappings"] = [{
            "mapping_id": "map-1",
            "from_source_id": "source-missing-a",
            "to_source_id": "source-missing-b",
            "status": "UNKNOWN",
        }]
        with self.assertRaisesRegex(ValueError, "Timeline mapping references a missing VideoSource"):
            validate_contract_integrity(damaged)

        invalid_id = read_fixture("desktop-local-asset.json")
        invalid_id["match_id"] = "../private"
        from adapters import adapt_local_video_asset
        with self.assertRaisesRegex(ValueError, "match_id must be a safe stable id"):
            adapt_local_video_asset(invalid_id)

    def test_unknown_rights_remain_pending_and_have_specific_evidence_requests(self):
        web_sources = [source for source in self.contract["video_sources"] if source["source_id"].startswith("web-source:")]
        self.assertEqual(len(web_sources), 4)
        self.assertTrue(all(source["rights"]["metadata_listing"] == "UNKNOWN" for source in web_sources))
        self.assertTrue(all(source["rights"]["thumbnail_display"] == "UNKNOWN" for source in web_sources))
        self.assertTrue(all(source["rights"]["embedding"] == "UNKNOWN" for source in web_sources))
        fields = {(item["source_id"], item["field"]) for item in self.audit["rights_review_queue"]}
        for source in web_sources:
            for field in ("metadata_listing", "external_viewing", "thumbnail_display", "embedding", "territory"):
                self.assertIn((source["source_id"], field), fields)
        self.assertEqual(self.audit["web_projection"]["status"], "SAFE_EMPTY")

    def test_pending_hash_candidate_is_rejected_and_not_added_to_contract(self):
        candidate = next(item for item in self.audit["rejected_candidates"] if item["kind"] == "local_asset_hash")
        self.assertEqual(candidate["status"], "PENDING")
        self.assertEqual(candidate["reason"], "LOCAL_SOURCE_SHA256_NOT_VERIFIED")
        self.assertNotIn("pending", json.dumps(self.contract).casefold())

    def test_unverified_timeline_candidate_is_rejected_not_serialized_as_a_link(self):
        candidate = next(item for item in self.audit["rejected_candidates"] if item["kind"] == "timeline_mapping")
        self.assertEqual(candidate["decision"], "REJECTED_NOT_A_CONTRACT_EDGE")
        self.assertIsNone(candidate["offset_ms"])
        self.assertEqual(self.contract["timeline_mappings"], [])

    def test_v01_consumer_explicitly_rejects_demo_v02(self):
        self.assertEqual(self.audit["v0_1_consumer"]["status"], "REJECTED_AS_REQUIRED")
        with self.assertRaises(UnsupportedContractVersion):
            from adapters import require_exact_contract_version
            require_exact_contract_version(self.contract, "ptti.match-media/0.1")

    def test_demo_files_are_repeatable_and_refuse_silent_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            contract_path, audit_path = write_demo_files(output_dir)
            first_contract = contract_path.read_bytes()
            first_audit = audit_path.read_bytes()
            write_demo_files(output_dir)
            self.assertEqual(contract_path.read_bytes(), first_contract)
            self.assertEqual(audit_path.read_bytes(), first_audit)
            contract_path.write_text("unexpected", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_demo_files(output_dir)
            write_demo_files(output_dir, replace=True)
            self.assertEqual(contract_path.read_bytes(), contract_bytes(self.contract))


if __name__ == "__main__":
    unittest.main()
