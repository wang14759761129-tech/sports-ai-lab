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

from fan_content_delivery import DeliveryError, build_delivery_package  # noqa: E402
from fan_content_intelligence import build_from_files  # noqa: E402


FIXTURE = INTEGRATION_DIR / "fixtures" / "goal14-fan-content-observations.json"
REGISTRY = REPO_ROOT / "products" / "ptti" / "data" / "professional" / "registry.json"
LOCALIZATIONS = INTEGRATION_DIR / "fixtures" / "goal14-fan-localization-v0.1.json"
SCHEMA = json.loads((INTEGRATION_DIR / "contracts" / "fan-content-delivery-v0.1.schema.json").read_text(encoding="utf-8"))


def build_local(package=None, localizations=LOCALIZATIONS):
    internal, _ = build_from_files(REPO_ROOT, FIXTURE, REGISTRY, "2026-10-18T04:30:00Z")
    if package is not None:
        internal = package
    return internal, build_delivery_package(internal, localizations)


class Goal14FanContentDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.delivery = build_local()

    def test_delivery_matches_schema_and_is_bound_to_base_and_localization(self):
        Draft202012Validator.check_schema(SCHEMA)
        Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(self.delivery)
        self.assertEqual(self.delivery["contract_version"], "ptti.fan-content-delivery/0.1")
        self.assertEqual(self.delivery["base_contract_version"], self.base["contract_version"])
        self.assertEqual(len(self.delivery["source_manifest"]["base_dataset_sha256"]), 64)

    def test_first_batch_has_three_stars_five_events_twenty_candidates_and_deduplicated_routes(self):
        summary = self.delivery["quality_summary"]
        self.assertEqual((summary["star_count"], summary["event_count"], summary["clip_candidate_count"]), (3, 5, 20))
        self.assertEqual((summary["unique_watch_source_count"], summary["exact_video_url_count"], summary["event_page_only_count"]), (14, 10, 10))
        self.assertEqual((summary["verified_match_count"], summary["match_video_links"]), (0, 0))

    def test_bilingual_titles_are_keyed_and_explicitly_non_official(self):
        self.assertTrue(all(row["title_zh"] for row in self.delivery["events"] + self.delivery["clips"]))
        self.assertTrue(all(row["translation_origin"] == "PTTI_EDITORIAL_TRANSLATION" for row in self.delivery["events"] + self.delivery["clips"]))
        self.assertTrue(all(row["official_translation_status"] == "UNKNOWN" for row in self.delivery["events"] + self.delivery["clips"]))
        stars = {row["athlete_id"]: row for row in self.delivery["stars"]}
        self.assertEqual(stars["athlete:121558"]["name_zh"], "王楚钦")
        self.assertEqual(stars["athlete:135977"]["name_zh"], "菲利克斯·勒布伦")

    def test_star_event_clip_watch_graph_has_no_guessed_match_edges(self):
        self.assertEqual(self.delivery["matches"], [])
        self.assertTrue(all(row["match_id"] is None and row["match_link_status"] == "UNKNOWN" for row in self.delivery["clips"]))
        self.assertEqual({row["path"] for row in self.delivery["relationship_gaps"]}, {"STAR_TO_MATCH", "MATCH_TO_CLIP"})
        self.assertTrue(all(row["status"] == "NOT_ESTABLISHED" for row in self.delivery["relationship_gaps"]))
        watch_edges = [row for row in self.delivery["relationships"] if row["to_type"] == "WATCH_SOURCE"]
        self.assertEqual(len(watch_edges), 20)
        self.assertTrue(all(row["edge_status"] == "ROUTE_LISTED_NOT_PLAYBACK_VERIFIED" for row in watch_edges))

    def test_watch_routes_match_exact_video_id_or_event_page_and_remain_unverified(self):
        watch_sources = {row["watch_source_id"]: row for row in self.delivery["watch_sources"]}
        clips = {row["clip_id"]: row for row in self.delivery["clips"]}
        base_candidates = {row["candidate_id"]: row for row in self.base["content_candidates"]}
        for clip_id, base_candidate in base_candidates.items():
            clip = clips[clip_id]
            watch = watch_sources[clip["watch_source_id"]]
            self.assertEqual(clip["published_at"], base_candidate["published_at"])
            self.assertEqual(clip["publisher"], base_candidate["publisher"])
            self.assertEqual(clip["official_video_url"], base_candidate["official_video_url"])
            self.assertEqual(clip["territory"], "UNKNOWN")
            self.assertEqual(clip["login_or_paywall"], "NOT_TESTED")
            self.assertEqual(watch["playback_status"], "NOT_TESTED")
            self.assertEqual(watch["territory"], "UNKNOWN")
            self.assertEqual(watch["embed_status"], "UNKNOWN")
            if base_candidate["video_id"]:
                self.assertEqual(watch["url"], f"https://www.youtube.com/watch?v={base_candidate['video_id']}")
                self.assertEqual(watch["route_kind"], "OFFICIAL_YOUTUBE_VIDEO")
            else:
                event = next(row for row in self.delivery["events"] if row["event_id"] == clip["event_id"])
                self.assertEqual(watch["url"], event["official_event_page_url"])
                self.assertEqual(watch["route_kind"], "OFFICIAL_EVENT_PAGE_LISTING")

    def test_all_rights_remain_fail_closed_and_public_projection_empty(self):
        rows = self.delivery["events"] + self.delivery["clips"] + self.delivery["watch_sources"]
        for row in rows:
            rights = row["rights"]
            self.assertEqual(rights["public_listing"], "UNKNOWN")
            self.assertEqual(rights["external_viewing"], "UNKNOWN")
            self.assertEqual(rights["embedding"], "UNKNOWN")
            self.assertEqual(rights["thumbnail_display"], "UNKNOWN")
            self.assertEqual(rights["local_analysis"], "NOT_GRANTED")
            self.assertEqual(rights["download"], "NOT_GRANTED")
            self.assertEqual(rights["redistribution"], "NOT_GRANTED")
        self.assertEqual(self.delivery["quality_summary"]["public_eligible_count"], 0)

    def test_localization_refuses_wrong_version_or_unbound_observation_fixture(self):
        data = json.loads(LOCALIZATIONS.read_text(encoding="utf-8"))
        data["contract_version"] = "ptti.fan-content-localization/9.9"
        tmp = INTEGRATION_DIR / "generated" / "goal14" / "_invalid-localization.json"
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(DeliveryError, "unsupported localization"):
                build_local(self.base, tmp)
            data = json.loads(LOCALIZATIONS.read_text(encoding="utf-8"))
            data["source_observations_sha256"] = "0" * 64
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(DeliveryError, "not bound"):
                build_local(self.base, tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_delivery_rejects_match_link_or_rights_escalation(self):
        mutated = copy.deepcopy(self.base)
        mutated["content_candidates"][0]["match_id"] = "match:guessed"
        with self.assertRaisesRegex(DeliveryError, "match identity"):
            build_local(mutated)
        mutated = copy.deepcopy(self.base)
        mutated["events"][0]["rights"]["public_listing"] = "ALLOWED"
        with self.assertRaisesRegex(DeliveryError, "rights state"):
            build_local(mutated)


if __name__ == "__main__":
    unittest.main()
