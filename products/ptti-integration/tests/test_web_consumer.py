from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from alpha_demo import build_alpha_demo
from web_consumer import InvalidContract, consume_contract, load_contract
from adapters import UnsupportedContractVersion


DEMO_PATH = PACKAGE / "generated" / "alpha-demo" / "alpha-demo-ptti.match-media-0.2.json"


class ReadOnlyWebConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract, _ = build_alpha_demo()

    def test_review_catalog_preserves_ids_rights_and_evidence_but_omits_local_assets(self):
        payload = consume_contract(self.contract, view="review")
        self.assertEqual(payload["contract_version"], "ptti.match-media/0.2")
        self.assertEqual(len(payload["matches"]), 4)
        self.assertEqual(len(payload["video_sources"]), 4)
        self.assertEqual(payload["local_video_assets"], [])
        self.assertTrue(all(source["source_id"].startswith("web-source:") for source in payload["video_sources"]))
        self.assertTrue(all(source["rights"]["embedding"] == "UNKNOWN" for source in payload["video_sources"]))
        self.assertTrue(all(source["evidence"]["desktop_native_playback"]["status"] == "NOT_TESTED" for source in payload["video_sources"]))
        self.assertNotIn("local_locator_ref", json.dumps(payload))
        self.assertNotIn("fixture-local-licensed-01", json.dumps(payload))

    def test_public_view_fails_closed_for_unknown_rights_and_synthetic_fixture(self):
        payload = consume_contract(self.contract, view="public")
        self.assertEqual(payload["matches"], [])
        self.assertEqual(payload["video_sources"], [])
        self.assertEqual(payload["local_video_assets"], [])

    def test_public_view_needs_listing_and_external_viewing_and_thumbnail_has_own_gate(self):
        contract = copy.deepcopy(self.contract)
        source = next(row for row in contract["video_sources"] if row["source_id"].startswith("web-source:"))
        source["rights"]["metadata_listing"] = "ALLOWED"
        source["rights"]["external_viewing"] = "ALLOWED"
        source["thumbnail_url"] = "https://images.example.test/cover.jpg"
        payload = consume_contract(contract, view="public")
        self.assertEqual([row["source_id"] for row in payload["video_sources"]], [source["source_id"]])
        self.assertEqual(payload["video_sources"][0]["rights"]["embedding"], "UNKNOWN")
        self.assertNotIn("thumbnail_url", payload["video_sources"][0])
        source["rights"]["thumbnail_display"] = "ALLOWED"
        payload_with_thumbnail_right = consume_contract(contract, view="public")
        self.assertEqual(payload_with_thumbnail_right["video_sources"][0]["thumbnail_url"], source["thumbnail_url"])

    def test_v01_and_missing_version_are_rejected_without_fallback(self):
        for version in ("ptti.match-media/0.1", None):
            contract = copy.deepcopy(self.contract)
            if version is None:
                contract.pop("contract_version")
            else:
                contract["contract_version"] = version
            with self.subTest(version=version), self.assertRaises(UnsupportedContractVersion):
                consume_contract(contract, view="review")

    def test_invalid_references_and_unknown_views_are_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["video_sources"][0]["match_id"] = "web-match:missing"
        with self.assertRaises(InvalidContract):
            consume_contract(contract, view="review")
        with self.assertRaises(ValueError):
            consume_contract(self.contract, view="legacy")  # type: ignore[arg-type]

    def test_filters_keep_match_source_ids_and_dont_mutate_input(self):
        before = copy.deepcopy(self.contract)
        match_id = self.contract["matches"][0]["match_id"]
        payload = consume_contract(self.contract, view="review", match_id=match_id, discipline="MS")
        self.assertEqual([row["match_id"] for row in payload["matches"]], [match_id])
        self.assertTrue(all(row["match_id"] == match_id for row in payload["video_sources"]))
        self.assertEqual(self.contract, before)
        with self.assertRaises(ValueError):
            consume_contract(self.contract, view="review", discipline="XX")  # type: ignore[arg-type]

    def test_cli_reads_existing_export_and_emits_contract_only_to_stdout(self):
        result = subprocess.run(
            [sys.executable, str(PACKAGE / "scripts" / "consume_web_export.py"), str(DEMO_PATH), "--view", "public"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["contract_version"], "ptti.match-media/0.2")
        self.assertEqual(payload["video_sources"], [])
        self.assertEqual(result.stderr, "")

    def test_file_loader_does_not_rewrite_input_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(self.contract), encoding="utf-8")
            before = path.read_bytes()
            loaded = load_contract(path)
            consume_contract(loaded, view="review")
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
