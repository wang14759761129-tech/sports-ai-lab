from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRATION_DIR / "scripts"))

from build_goal14_main_public_admission import AdmissionError, build_public_index  # noqa: E402

ROOT = INTEGRATION_DIR.parents[1]
INTERNAL_PATH = INTEGRATION_DIR / "generated" / "goal11-match-library" / "match-library-internal-review.json"
ADMISSION_PATH = INTEGRATION_DIR / "fixtures" / "goal14-main-content-admission-v0.1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class MainPublicAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.internal = load(INTERNAL_PATH)
        cls.admission = load(ADMISSION_PATH)

    def build(self, admission: dict | None = None, internal: dict | None = None) -> dict:
        return build_public_index(internal or self.internal, admission or self.admission, "2026-10-18T00:00:00Z")

    def test_one_exact_external_watch_chain_is_projected(self) -> None:
        result = self.build()
        self.assertEqual((len(result["matches"]), len(result["video_sources"]), len(result["stars"])), (1, 1, 2))
        match = result["matches"][0]
        source = result["video_sources"][0]
        self.assertEqual(match["match_id"], "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun")
        self.assertEqual(match["video_source_ids"], ["video-source:youtube:0QgbtsBWZhk"])
        self.assertEqual(match["match_video_link_status"], "HUMAN_VERIFIED")
        self.assertEqual(source["canonical_match_id"], match["match_id"])
        self.assertEqual(source["match_link_status"], "HUMAN_VERIFIED")
        self.assertEqual(source["official_url"], "https://www.youtube.com/watch?v=0QgbtsBWZhk")
        self.assertEqual(source["source_identity_status"], "VERIFIED")
        self.assertEqual(source["source_identity_evidence_scope"], "OFFICIAL_VIDEO_METADATA_ONLY_NOT_VISUAL_PLAYBACK")
        self.assertEqual(source["rights"]["external_viewing"], "ALLOWED")
        self.assertEqual(source["availability"]["current_session_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_media_rights_and_playback_stay_ungranted_or_unknown(self) -> None:
        result = self.build()
        source = result["video_sources"][0]
        self.assertEqual(source["rights"]["embedding"], "UNKNOWN")
        self.assertEqual(source["rights"]["thumbnail_display"], "NOT_ALLOWED")
        self.assertEqual(source["thumbnail"]["url"], None)
        self.assertEqual(source["rights"]["local_analysis"], "NOT_GRANTED")
        self.assertEqual(source["rights"]["redistribution"], "NOT_GRANTED")
        self.assertEqual(source["availability"]["external_video_visual_latest_recorded"], "NOT_TESTED")
        self.assertEqual(source["availability"]["territory_availability"], "UNKNOWN")
        self.assertEqual(source["availability"]["desktop_native_playback"], "NOT_TESTED")
        self.assertEqual(source["availability"]["vision_analysis"], "NOT_TESTED")
        self.assertEqual(result["local_video_assets"], [])
        self.assertEqual(result["quality_summary"]["total_internal_video_sources_reviewed"], 35)
        self.assertEqual(result["quality_summary"]["excluded_reference_only_records"], 34)

    def test_base_reference_records_remain_unmodified_and_unlinked(self) -> None:
        base_match = next(row for row in self.internal["matches"] if row["match_id"] == "pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun")
        base_source = next(row for row in self.internal["video_sources"] if row["video_id"] == "0QgbtsBWZhk")
        self.assertEqual(base_match["video_source_ids"], [])
        self.assertEqual(base_match["match_video_link_status"], "UNKNOWN")
        self.assertEqual(base_match["rights"]["public_listing"], "UNKNOWN")
        self.assertIsNone(base_source["canonical_match_id"])
        self.assertEqual(base_source["rights"]["public_listing"], "UNKNOWN")

    def test_rejects_wrong_match_or_source_identity(self) -> None:
        for key, value, message in (
            ("match_id", "match:guessed", "unknown-match-or-source-reference"),
            ("source_id", "video-source:youtube:other", "unknown-match-or-source-reference"),
        ):
            mutated = json.loads(json.dumps(self.admission))
            mutated["admissions"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(AdmissionError, message):
                self.build(mutated)

    def test_rejects_missing_or_inconsistent_direct_video_link_evidence(self) -> None:
        mutations = [
            (lambda row: row.update(relationship_evidence_ids=["wtt-china-smash-2025-final"]), "missing-direct-match-link-evidence"),
            (lambda row: row["source_facts"].update(video_id="different123"), "video-id-mismatch"),
            (lambda row: row["source_facts"].update(original_title="unrelated video"), "official-title-mismatch"),
            (lambda row: row["source_facts"].update(round="Semifinal"), "source-round-mismatch"),
        ]
        for mutate, expected in mutations:
            changed = json.loads(json.dumps(self.admission))
            mutate(changed["admissions"][0])
            with self.subTest(expected=expected), self.assertRaisesRegex(AdmissionError, expected):
                self.build(changed)

    def test_rejects_permission_or_evidence_escalation(self) -> None:
        mutations = [
            (lambda row: row["external_viewing_basis"].update(status="UNKNOWN"), "external-link-not-approved"),
            (lambda row: row["external_viewing_basis"].update(scope="ANY_PLATFORM_CONTENT"), "overbroad-external-link-scope"),
            (lambda row: row["media_rights"].update(embedding="ALLOWED"), "embedding-needs-explicit-grant"),
            (lambda row: row["media_rights"].update(local_analysis="ALLOWED"), "local-analysis-not-granted"),
            (lambda row: row["availability"].update(territory_availability="GLOBAL"), "unverified-territory-upgrade"),
            (lambda row: row["availability"].update(external_video_visual_latest_recorded="PASS"), "unverified-playback-upgrade"),
        ]
        for mutate, expected in mutations:
            changed = json.loads(json.dumps(self.admission))
            mutate(changed["admissions"][0])
            with self.subTest(expected=expected), self.assertRaisesRegex(AdmissionError, expected):
                self.build(changed)


if __name__ == "__main__":
    unittest.main()
