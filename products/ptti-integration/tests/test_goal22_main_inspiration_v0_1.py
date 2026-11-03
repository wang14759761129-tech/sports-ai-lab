import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

BUILDER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_fan_inspiration_v0_1.py"
spec = importlib.util.spec_from_file_location("build_fan_inspiration_v0_1", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


class Goal22InspirationPackageTests(unittest.TestCase):
    def setUp(self):
        self.package = builder.build_package(generated_at="2026-10-20T00:00:00Z")
        self.schema = builder.read_json(builder.SCHEMA_PATH)

    def test_strict_package_validates_and_preserves_7_17_8_baseline_inputs(self):
        jsonschema.Draft202012Validator(self.schema).validate(self.package)
        self.assertEqual(self.package["input_identity"]["base_sha256"], builder.EXPECTED_BASE_SHA256)
        self.assertEqual(self.package["input_identity"]["goal17_delta_sha256"], builder.EXPECTED_DELTA_SHA256)
        self.assertEqual(len(self.package["clips"]), 11)
        self.assertEqual(len(self.package["match_watch_sources"]), 7)
        self.assertEqual(len(self.package["clips"]) + len(self.package["match_watch_sources"]), 18)

    def test_all_source_rows_keep_independent_playback_and_rights_states(self):
        sources = self.package["clips"] + self.package["match_watch_sources"]
        self.assertEqual(len({s["source_id"] for s in sources}), 18)
        self.assertEqual(len({s["original_url"] for s in sources}), 18)
        for source in sources:
            self.assertEqual(source["verification"]["external_system_browser_open"], "NOT_TESTED")
            self.assertEqual(source["verification"]["video_started"], "NOT_TESTED")
            self.assertEqual(source["verification"]["complete_watch"], "UNVERIFIED")
            self.assertEqual(source["verification"]["territory"], "UNKNOWN")
            self.assertEqual(source["rights"]["embed"], "UNKNOWN_NOT_GRANTED")
            self.assertIn(source["rights"]["thumbnail_display"], {"NOT_ALLOWED", "NOT_GRANTED_PENDING_APPROVAL"})
            self.assertEqual(source["rights"]["download"], "NOT_GRANTED")
            self.assertEqual(source["rights"]["local_analysis"], "NOT_GRANTED")
            self.assertEqual(source["rights"]["redistribution"], "NOT_GRANTED")

    def test_highlights_remain_event_level_and_full_match_is_only_a_title_claim(self):
        for item in self.package["clips"]:
            if item["video_category"] == "EVENT_HIGHLIGHTS_TITLE_CLAIM":
                self.assertIsNone(item["match_id"])
                self.assertEqual(item["athlete_association_status"], "UNASSIGNED_EVENT_LEVEL")
        full_claims = [s for s in self.package["match_watch_sources"] if s["video_category"] == "FULL_MATCH_TITLE_CLAIM"]
        self.assertEqual(len(full_claims), 5)
        self.assertTrue(all(s["full_match_completeness"] == "UNVERIFIED" for s in full_claims))

    def test_international_reaction_is_a_single_report_not_population_sentiment(self):
        reaction = self.package["international_reactions"][0]
        self.assertEqual(reaction["language"], "fr")
        self.assertEqual(reaction["credibility"]["audience_representativeness"], "NOT_CLAIMED")
        self.assertEqual(reaction["content_kind"], "SINGLE_MEDIA_REPORT")
        self.assertEqual(reaction["rights"]["article_republication"], "NOT_GRANTED")

    def test_three_match_gear_dossiers_keep_every_gear_unknown(self):
        self.assertEqual(len(self.package["gear_dossiers"]), 3)
        for dossier in self.package["gear_dossiers"]:
            self.assertEqual(dossier["evidence_status"], "NOT_VERIFIED_FOR_SPECIFIC_MATCH")
            for participant in dossier["participants"]:
                self.assertEqual({i["category"] for i in participant["items"]}, set(builder.GEAR_CATEGORIES))
                self.assertTrue(all(i["status"] == "UNKNOWN" and i["brand"] is None and i["model"] is None for i in participant["items"]))

    def test_five_watch_routes_fail_closed_and_do_not_claim_playback(self):
        routes = {route["mode"]: route for route in self.package["watch_routes"]}
        self.assertEqual(len(routes), 5)
        self.assertEqual(routes["OFFICIAL_EMBED"]["state"], "BLOCKED_NO_EXPLICIT_EMBED_PERMISSION")
        self.assertEqual(routes["OFFICIAL_PAGE"]["state"], "OUTBOUND_LINKS_REGISTERED_PLAYBACK_NOT_TESTED")
        self.assertEqual(routes["AUTHORIZED_SOURCE"]["state"], "NO_AUTHORIZED_SOURCE_REGISTERED")
        self.assertEqual(routes["LIVE_SCORE"]["state"], "NO_LIVE_SCORE_VERIFIED")
        self.assertTrue(all(r["playback_evidence"] == "NOT_TESTED" for r in routes.values()))

    def test_strict_export_has_no_internal_paths_or_review_material(self):
        self.assertEqual(builder.validate_package(self.package), [])
        encoded = json.dumps(self.package, ensure_ascii=False).lower()
        for forbidden in ("internal_path", "database_path", "source_manifest", "review_queue", "build_log", "candidate-review-internal"):
            self.assertNotIn(forbidden, encoded)
        self.assertNotIn("thumbnail_url", encoded)
        self.assertNotIn("video_bytes", encoded)

    def test_validator_rejects_playback_permission_and_highlight_binding_escalation(self):
        bad = json.loads(json.dumps(self.package))
        bad["clips"][0]["verification"]["video_started"] = "PASS"
        self.assertTrue(any("video_started" in error for error in builder.validate_package(bad)))
        bad = json.loads(json.dumps(self.package))
        highlight = next(c for c in bad["clips"] if c["video_category"] == "EVENT_HIGHLIGHTS_TITLE_CLAIM")
        highlight["match_id"] = "invented-match"
        self.assertIn("event_highlight_match_binding_escalated", builder.validate_package(bad))

    def test_builder_rejects_duplicate_sources_or_unapproved_publication_rights(self):
        supplement = builder.read_json(builder.SUPPLEMENT_PATH)
        duplicate = json.loads(json.dumps(supplement))
        duplicate["video_content"][0]["source_id"] = "video-source:youtube:0QgbtsBWZhk"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplement.json"
            path.write_text(json.dumps(duplicate), encoding="utf-8")
            with patch.object(builder, "SUPPLEMENT_PATH", path):
                with self.assertRaisesRegex(builder.PackageError, "duplicate_video_source_id_or_url"):
                    builder.build_package(generated_at="2026-10-20T00:00:00Z")
        denied = json.loads(json.dumps(supplement))
        denied["video_content"][0]["rights"]["external_viewing"] = "UNKNOWN"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplement.json"
            path.write_text(json.dumps(denied), encoding="utf-8")
            with patch.object(builder, "SUPPLEMENT_PATH", path):
                with self.assertRaisesRegex(builder.PackageError, "source_not_admitted_for_external_link"):
                    builder.build_package(generated_at="2026-10-20T00:00:00Z")

    def test_builder_rejects_unapproved_supplement_fields(self):
        supplement = builder.read_json(builder.SUPPLEMENT_PATH)
        supplement["internal_review_path"] = "private/review.json"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplement.json"
            path.write_text(json.dumps(supplement), encoding="utf-8")
            with patch.object(builder, "SUPPLEMENT_PATH", path):
                with self.assertRaisesRegex(builder.PackageError, "goal22_supplement_has_unapproved_fields"):
                    builder.build_package(generated_at="2026-10-20T00:00:00Z")

    def test_goal17_external_link_adapter_refuses_permission_escalation(self):
        delta = builder.read_json(builder.DELTA_PATH)
        changed = json.loads(json.dumps(delta))
        changed["video_sources"][0]["embed_permission"] = "ALLOWED"
        with self.assertRaisesRegex(builder.PackageError, "goal17_embed_permission_not_unknown_not_granted"):
            builder._rights_from_goal17_delta(changed["video_sources"][0])

    def test_strict_rights_preserve_explicit_thumbnail_denial(self):
        self.assertEqual(
            builder._public_rights({
                "public_listing": "ALLOWED",
                "external_viewing": "ALLOWED",
                "embedding": "UNKNOWN",
                "thumbnail_display": "NOT_ALLOWED",
                "download": "NOT_GRANTED",
                "local_analysis": "NOT_GRANTED",
                "redistribution": "NOT_GRANTED",
            })["thumbnail_display"],
            "NOT_ALLOWED",
        )

    def test_builder_rejects_mismatched_video_id_and_original_url(self):
        base = builder.read_json(builder.BASE_PATH)
        source = json.loads(json.dumps(base["video_sources"][0]))
        source["official_url"] = "https://www.youtube.com/watch?v=another-video"
        with self.assertRaisesRegex(builder.PackageError, "source_video_id_original_url_mismatch"):
            builder._base_item(source, match_by_id={}, evidence_by_id={})

    def test_season_highlight_cannot_be_bound_to_a_single_match(self):
        bad = json.loads(json.dumps(self.package))
        season = next(item for item in bad["clips"] if item["video_category"] == "SEASON_HIGHLIGHTS_TITLE_CLAIM")
        season["match_id"] = "invented-match"
        self.assertIn("event_highlight_match_binding_escalated", builder.validate_package(bad))


if __name__ == "__main__":
    unittest.main()
