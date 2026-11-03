"""Offline schema contract tests; never imports the backend app or opens a DB."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


def load_unique_json(path: Path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


class FoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_unique_json(ROOT / "contracts" / "foundation-v0.1.schema.json")
        cls.records = load_unique_json(ROOT / "contracts" / "foundation-v0.1.examples.json")
        cls.discovery_schema = load_unique_json(ROOT / "contracts" / "personal-discovery-v0.1.schema.json")
        cls.discovery_example = load_unique_json(ROOT / "contracts" / "personal-discovery-v0.1.synthetic-example.json")
        Draft202012Validator.check_schema(cls.schema)
        Draft202012Validator.check_schema(cls.discovery_schema)
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())
        cls.discovery_validator = Draft202012Validator(cls.discovery_schema, format_checker=FormatChecker())

    def assertValid(self, record):
        self.assertEqual(list(self.validator.iter_errors(record)), [])

    def assertInvalid(self, record):
        self.assertTrue(list(self.validator.iter_errors(record)))

    def test_schema_has_unique_keys_and_all_twelve_mock_examples_validate(self):
        self.assertEqual(len(self.records), 12)
        self.assertEqual({row["kind"] for row in self.records}, {
            "MatchIdentity", "MediaSource", "VideoAsset", "PlaybackState", "Moment", "Rally",
            "PointEvent", "Prediction", "PoseEvidence", "CoachAnnotation", "UserCollection", "RightsEvidence",
        })
        for row in self.records:
            self.assertValid(row)

    def test_missing_media_timeline_is_rejected(self):
        moment = copy.deepcopy(next(row for row in self.records if row["kind"] == "Moment"))
        moment["timeline_anchor"] = None
        self.assertInvalid(moment)

    def test_provider_embeddable_does_not_grant_embed_permission(self):
        playback = copy.deepcopy(next(row for row in self.records if row["kind"] == "PlaybackState"))
        playback["provider_embeddable"] = True
        playback["embed_permission"] = "UNKNOWN"
        self.assertValid(playback)

    def test_rights_allowed_without_use_specific_evidence_is_rejected(self):
        rights = copy.deepcopy(next(row for row in self.records if row["kind"] == "RightsEvidence"))
        rights["permissions"]["remote_display"]["status"] = "ALLOWED"
        self.assertInvalid(rights)

    def test_mock_cannot_be_marked_as_real_verification(self):
        record = copy.deepcopy(self.records[0])
        record["provenance"]["verification"] = "VERIFIED"
        self.assertInvalid(record)

    def test_inference_provenance_cannot_be_attached_to_non_model_record(self):
        record = copy.deepcopy(self.records[0])
        record["provenance"]["inference"] = copy.deepcopy(
            next(row for row in self.records if row["kind"] == "PoseEvidence")["provenance"]["inference"]
        )
        self.assertInvalid(record)

    def test_simulated_event_cannot_have_real_match_identity(self):
        event = copy.deepcopy(next(row for row in self.records if row["kind"] == "PointEvent"))
        event["identity"]["match_id"] = "pro:wtt:unverified"
        self.assertInvalid(event)

    def test_unrecognized_fields_fail_closed(self):
        record = copy.deepcopy(self.records[0])
        record["internal_source_path"] = "C:/private/review.json"
        self.assertInvalid(record)

    def test_point_event_coach_annotation_requires_an_exact_target(self):
        annotation = copy.deepcopy(next(row for row in self.records if row["kind"] == "CoachAnnotation"))
        annotation["scope"] = "POINT_EVENT"
        self.assertInvalid(annotation)

    def test_local_discovery_example_is_valid_and_contains_no_media_or_query(self):
        self.assertEqual(list(self.discovery_validator.iter_errors(self.discovery_example)), [])
        raw = json.dumps(self.discovery_example)
        self.assertNotIn("search_query", raw)
        self.assertNotIn("local_path", raw)
        self.assertEqual(self.discovery_example["local_progress"], [])

    def test_local_discovery_rejects_paths_and_unapproved_progress(self):
        profile = copy.deepcopy(self.discovery_example)
        profile["local_progress"] = [{
            "video_asset_id": "C:\\private\\practice.mp4",
            "asset_sha256": "a" * 64,
            "position_seconds": 12,
            "duration_seconds": 30,
            "asset_kind": "USER_LOCAL",
            "availability": "AVAILABLE",
            "identity_method": "VERIFIED_SHA256",
            "playback_rights": "USER_CONFIRMED",
            "rights_evidence_id": "rights:fixture",
            "updated_at": "2026-10-28T00:00:00Z",
        }]
        self.assertTrue(list(self.discovery_validator.iter_errors(profile)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
