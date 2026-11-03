import json
import re
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INTEGRATION_ROOT = REPOSITORY_ROOT / "products" / "ptti-integration"
sys.path.insert(0, str(INTEGRATION_ROOT))

from goal27_match_experience import build_public_delta, validate_public_delta  # noqa: E402


PACKAGE_ROOT = INTEGRATION_ROOT / "generated" / "goal27-match-experience-v0.1"
REVIEW_PATH = PACKAGE_ROOT / "internal" / "review-source.json"
OUTPUT_PATH = PACKAGE_ROOT / "public" / "match-experience-delta-v0.1.json"
BASE_PATH = INTEGRATION_ROOT / "generated" / "goal15-main-fan-universe-public-v0.2" / "match-library-strict-public.json"
GENERATED_AT = "2026-10-22T04:57:20Z"


class Goal27MatchExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        cls.base = json.loads(BASE_PATH.read_text(encoding="utf-8"))
        cls.delta = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_official_match_highlight_is_a_safe_additive_catalog_row(self):
        rebuilt = build_public_delta(self.review, GENERATED_AT)
        self.assertEqual(rebuilt, self.delta)
        validate_public_delta(self.delta, self.base)
        self.assertEqual(len(self.delta["matches"]), 1)
        self.assertEqual(len(self.delta["video_sources"]), 1)
        self.assertIsNone(self.delta["matches"][0]["provider_match_id"])
        self.assertIsNone(self.delta["matches"][0]["event"]["date"])
        self.assertEqual(self.delta["video_sources"][0]["content_type_claim"], "HIGHLIGHTS")
        self.assertEqual(self.delta["video_sources"][0]["canonical_match_id"], self.delta["matches"][0]["match_id"])

    def test_external_link_does_not_claim_embed_thumbnail_or_playback(self):
        source = self.delta["video_sources"][0]
        self.assertEqual(source["rights"]["external_viewing"], "ALLOWED")
        self.assertEqual(source["rights"]["embedding"], "UNKNOWN")
        self.assertEqual(source["rights"]["thumbnail_display"], "NOT_ALLOWED")
        self.assertEqual(source["rights"]["download"], "NOT_GRANTED")
        self.assertEqual(source["availability"]["latest_recorded_playback_status"], "NOT_TESTED")
        self.assertEqual(source["availability"]["territory_availability"], "UNKNOWN")
        self.assertEqual(source["availability"]["current_session_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")

    def test_source_match_and_evidence_ids_must_resolve_exactly(self):
        for mutate in (
            lambda value: value["video_sources"][0].__setitem__("canonical_match_id", "match:guessed"),
            lambda value: value["matches"][0].__setitem__("video_source_ids", ["video-source:youtube:other"]),
            lambda value: value["video_sources"][0]["rights"].__setitem__("evidence_source_ids", ["evidence:missing"]),
            lambda value: value["video_sources"][0].__setitem__("official_url", "https://www.youtube.com/watch?v=aaaaaaaaaaa"),
            lambda value: value["matches"][0].__setitem__("provider_match_id", "WTT-FAKE-ID"),
            lambda value: value["video_sources"][0].__setitem__("private_media_path", "C:\\\\Private\\\\clip.mp4"),
        ):
            invalid = json.loads(json.dumps(self.delta))
            mutate(invalid)
            with self.assertRaises(ValueError):
                validate_public_delta(invalid, self.base)

    def test_unsafe_rights_or_playback_escalation_is_rejected(self):
        mutations = (
            lambda value: value["video_sources"][0]["rights"].__setitem__("embedding", "ALLOWED"),
            lambda value: value["video_sources"][0]["rights"].__setitem__("thumbnail_display", "ALLOWED"),
            lambda value: value["video_sources"][0]["availability"].__setitem__("latest_recorded_playback_status", "PASS"),
            lambda value: value["video_sources"][0]["availability"].__setitem__("territory_availability", "GLOBAL_AVAILABLE"),
        )
        for mutate in mutations:
            invalid = json.loads(json.dumps(self.delta))
            mutate(invalid)
            with self.assertRaises(ValueError):
                validate_public_delta(invalid, self.base)

    def test_public_projection_excludes_review_only_fields(self):
        forbidden_keys = {"review-source.json", "review_source", "media_bytes", "thumbnail_url", "local_path", "database_path"}

        def visit(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden_keys & set(value))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, str):
                self.assertIsNone(re.search(r"(?<![A-Za-z0-9])(?:[A-Z]:\\|[A-Za-z]:/|/Users/|/home/)", value))

        visit(self.delta)


if __name__ == "__main__":
    unittest.main()
