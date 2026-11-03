from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from jsonschema import Draft202012Validator, FormatChecker


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from adapters import (  # noqa: E402
    adapt_desktop_video_source,
    adapt_local_video_asset,
    adapt_timeline_mapping,
    adapt_web_match_record,
    adapt_web_match_records,
    build_contract,
    require_exact_contract_version,
    to_web_safe_payload,
    UnsupportedContractVersion,
)


FIXTURES = PACKAGE / "fixtures"


def read_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class WebMatchAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = read_json("web-match-records.json")
        cls.contract = adapt_web_match_records(cls.records)

    def test_four_real_public_web_fixture_records_convert(self):
        self.assertEqual(len(self.records), 4)
        self.assertEqual(len(self.contract["matches"]), 4)
        self.assertEqual(len(self.contract["video_sources"]), 4)
        self.assertEqual(self.contract["contract_version"], "ptti.match-media/0.2")

    def test_web_fixture_conforms_to_versioned_schema(self):
        schema = json.loads((PACKAGE / "contracts" / "match-media-v0.2.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(self.contract)), [])

    def test_v0_1_consumer_schema_explicitly_rejects_v0_2(self):
        schema = json.loads((PACKAGE / "contracts" / "match-media-v0.1.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(self.contract))
        self.assertTrue(
            any(
                error.validator == "const"
                and list(error.path) == ["contract_version"]
                and error.validator_value == "ptti.match-media/0.1"
                for error in errors
            ),
            "A v0.1-only consumer must reject v0.2 explicitly at contract_version.",
        )

    def test_exact_version_preflight_rejects_v0_2_for_v0_1_consumer(self):
        with self.assertRaises(UnsupportedContractVersion) as caught:
            require_exact_contract_version(self.contract, "ptti.match-media/0.1")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_CONTRACT_VERSION")
        self.assertEqual(caught.exception.expected_version, "ptti.match-media/0.1")
        self.assertEqual(caught.exception.received_version, "ptti.match-media/0.2")

    def test_exact_version_preflight_accepts_only_the_declared_version(self):
        self.assertEqual(
            require_exact_contract_version(self.contract, "ptti.match-media/0.2"),
            "ptti.match-media/0.2",
        )
        for malformed in (None, [], {}, {"contract_version": None}, {"contract_version": 2}):
            with self.subTest(payload=malformed):
                with self.assertRaises(UnsupportedContractVersion) as caught:
                    require_exact_contract_version(malformed, "ptti.match-media/0.1")
                self.assertEqual(caught.exception.code, "UNSUPPORTED_CONTRACT_VERSION")

    def test_missing_match_link_status_and_player_ids_stay_unknown(self):
        for record, match, source in zip(self.records, self.contract["matches"], self.contract["video_sources"]):
            with self.subTest(record=record["id"]):
                self.assertNotIn("matchLinkStatus", record)
                self.assertEqual(source["match_link_status"], "UNKNOWN")
                self.assertEqual(match["participants"], [])
                self.assertEqual(match["participant_names_unassigned"], record["players"])

    def test_event_ids_only_come_from_explicit_fields_or_official_wtt_event_urls(self):
        self.assertEqual(self.contract["matches"][0]["event"]["event_id"], "2866")
        self.assertEqual(self.contract["matches"][1]["event"]["event_id"], "2866")
        self.assertEqual(self.contract["matches"][2]["event"]["event_id"], "2536")
        self.assertIsNone(self.contract["matches"][3]["event"]["event_id"])

        record = copy.deepcopy(self.records[0])
        record["platformUrl"] = "https://worldtabletennis.com.evil.example/eventInfo?eventId=999"
        record["sourceEvidence"] = [record["platformUrl"]]
        self.assertIsNone(adapt_web_match_record(record)["match"]["event"]["event_id"])

        conflicted = copy.deepcopy(self.records[0])
        conflicted["eventId"] = "999"
        self.assertIsNone(adapt_web_match_record(conflicted)["match"]["event"]["event_id"])

    def test_source_names_are_not_guessed_into_sides(self):
        match = self.contract["matches"][1]
        self.assertEqual(match["participants"], [])
        self.assertEqual(match["participant_names_unassigned"], ["Fan Zhendong", "Lin Gaoyuan"])

    def test_event_pages_and_video_pages_remain_distinct(self):
        kinds = [source["resource_kind"] for source in self.contract["video_sources"]]
        self.assertEqual(kinds, ["OFFICIAL_EVENT_PAGE", "VIDEO_PAGE", "VIDEO_PAGE", "UNKNOWN"])
        self.assertEqual(self.contract["video_sources"][3]["evidence"]["external_video_page"]["status"], "NOT_TESTED")

    def test_external_page_visual_evidence_does_not_upgrade_embed_or_desktop(self):
        source = self.contract["video_sources"][1]
        self.assertEqual(source["evidence"]["external_video_page"]["status"], "EXTERNAL_VIDEO_PAGE_VISUAL_PASS")
        self.assertEqual(source["evidence"]["embed_playback"]["status"], "NOT_TESTED")
        self.assertEqual(source["evidence"]["desktop_native_playback"]["status"], "NOT_TESTED")

    def test_only_two_fixture_records_carry_external_visual_pass_evidence(self):
        passed = [
            source for source in self.contract["video_sources"]
            if source["evidence"]["external_video_page"]["status"] == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS"
        ]
        self.assertEqual(len(passed), 2)
        self.assertTrue(all(source["evidence"]["embed_playback"]["status"] == "NOT_TESTED" for source in passed))
        self.assertTrue(all(source["evidence"]["desktop_native_playback"]["status"] == "NOT_TESTED" for source in passed))

    def test_web_visual_pass_retains_page_publisher_source_audio_and_prompt_facts(self):
        evidence = self.contract["video_sources"][1]["evidence"]["external_video_page"]
        self.assertEqual(evidence["requested_url"], self.records[1]["videoOriginalUrl"])
        self.assertTrue(evidence["url_exact_match"])
        self.assertIn(self.records[1]["videoOriginalUrl"], evidence["source_evidence_urls"])
        self.assertTrue(evidence["page_title"])
        self.assertTrue(evidence["publisher_verified"])
        self.assertTrue(evidence["source_evidence_verified"])
        self.assertTrue(evidence["title_matches_match"])
        self.assertFalse(evidence["login_prompt_seen"])
        self.assertFalse(evidence["region_prompt_seen"])
        self.assertFalse(evidence["verification_prompt_seen"])
        self.assertEqual(evidence["audio_status"], "UNKNOWN")
        self.assertFalse(evidence["audio_confirmation_observed"])
        self.assertFalse(evidence["audio_confirmation_observed"])

    def test_four_web_records_keep_rights_unknown_and_are_not_publicly_projected(self):
        public = to_web_safe_payload(self.contract)
        self.assertEqual(len(self.records), 4)
        self.assertEqual(public["video_sources"], [])
        self.assertEqual(public["matches"], [])
        for source in self.contract["video_sources"]:
            for permission in (
                "metadata_listing", "thumbnail_display", "external_viewing",
                "embedding", "local_analysis", "model_training", "redistribution",
            ):
                self.assertEqual(source["rights"][permission], "UNKNOWN", (source["source_id"], permission))
            self.assertIsNone(source["thumbnail_url"])
            self.assertEqual(source["rights"]["basis_urls"], [])
        self.assertEqual(self.contract["video_sources"][3]["content_type"], "ARTICLE")
        self.assertEqual(self.contract["video_sources"][3]["resource_kind"], "UNKNOWN")

    def test_source_only_article_classification_requires_both_label_and_official_article_url(self):
        record = copy.deepcopy(self.records[3])
        self.assertEqual(adapt_web_match_record(record)["video_source"]["content_type"], "ARTICLE")
        record["sourceEvidence"] = ["https://example.test/description?artId=4731"]
        self.assertEqual(adapt_web_match_record(record)["video_source"]["content_type"], "UNKNOWN")
        record = copy.deepcopy(self.records[3])
        record["platform"] = "WTT result source"
        self.assertEqual(adapt_web_match_record(record)["video_source"]["content_type"], "UNKNOWN")

    def test_web_match_identity_and_source_identity_are_not_merged(self):
        for record, match, source in zip(self.records, self.contract["matches"], self.contract["video_sources"]):
            self.assertEqual(match["match_id"], f"web-match:{record['id']}")
            self.assertEqual(source["source_id"], f"web-source:{record['id']}")
            self.assertEqual(source["match_id"], match["match_id"])
            self.assertTrue(all(member["player_id"] is None for side in match["participants"] for member in side["members"]))
            self.assertEqual(match["participant_names_unassigned"], record["players"])

    def test_one_second_progress_is_not_a_visual_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["timeAtFinalObservationSeconds"] = 3
        adapted = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(adapted["status"], "REVIEW_REQUIRED")
        self.assertIn("TIMELINE_ADVANCE_LT_5_SECONDS", adapted["validation_failures"])

    def test_negative_timeline_observation_fails_and_is_sanitized(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["timeAtFirstObservationSeconds"] = -1
        evidence = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(evidence["status"], "REVIEW_REQUIRED")
        self.assertIn("TIMELINE_OBSERVATION_INVALID", evidence["validation_failures"])
        self.assertIsNone(evidence["time_first_seconds"])

    def test_same_youtube_host_but_different_video_id_is_not_a_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["finalUrl"] = "https://www.youtube.com/watch?v=another-video"
        adapted = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(adapted["status"], "REVIEW_REQUIRED")
        self.assertFalse(adapted["url_exact_match"])

    def test_missing_publisher_or_verification_time_is_not_a_pass(self):
        missing_publisher = copy.deepcopy(self.records[1])
        missing_publisher["playbackEvidence"].pop("publisher")
        publisher_result = adapt_web_match_record(missing_publisher)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(publisher_result["status"], "REVIEW_REQUIRED")
        self.assertIn("PUBLISHER_UNVERIFIED", publisher_result["validation_failures"])

        missing_time = copy.deepcopy(self.records[1])
        missing_time["playbackEvidence"].pop("testedAt")
        time_result = adapt_web_match_record(missing_time)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(time_result["status"], "REVIEW_REQUIRED")
        self.assertIn("VERIFICATION_TIME_MISSING", time_result["validation_failures"])

    def test_unchanged_visual_frames_are_not_a_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["visualFramesChanged"] = False
        adapted = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(adapted["status"], "REVIEW_REQUIRED")
        self.assertIn("VISUAL_FRAMES_UNCHANGED", adapted["validation_failures"])

    def test_unverified_audio_never_becomes_audio_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"].pop("audibleOutputConfirmed")
        adapted = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(adapted["status"], "REVIEW_REQUIRED")
        self.assertEqual(adapted["audio_status"], "UNKNOWN")
        self.assertNotEqual(adapted["audio_status"], "AUDIO_CONFIRMED")
        self.assertIn("AUDIO_STATUS_MISSING", adapted["validation_failures"])

        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["audibleOutputConfirmed"] = False
        explicit_false = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(explicit_false["status"], "EXTERNAL_VIDEO_PAGE_VISUAL_PASS")
        self.assertEqual(explicit_false["audio_status"], "UNKNOWN")
        self.assertFalse(explicit_false["audio_confirmation_observed"])

    def test_publisher_claim_without_wtt_cross_source_is_not_verified(self):
        record = copy.deepcopy(self.records[1])
        record["sourceEvidence"] = [record["videoOriginalUrl"]]
        evidence = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(evidence["status"], "REVIEW_REQUIRED")
        self.assertFalse(evidence["publisher_verified"])
        self.assertIn("OFFICIAL_MATCH_SOURCE_MISSING", evidence["validation_failures"])

    def test_wtt_cross_source_for_a_different_event_does_not_verify_video(self):
        record = copy.deepcopy(self.records[1])
        record["eventId"] = "2866"
        record["sourceEvidence"] = [
            "https://www.worldtabletennis.com/eventInfo?eventId=9999",
            record["videoOriginalUrl"],
        ]
        evidence = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(evidence["status"], "REVIEW_REQUIRED")
        self.assertFalse(evidence["source_evidence_verified"])
        self.assertIn("OFFICIAL_MATCH_SOURCE_MISSING", evidence["validation_failures"])

    def test_missing_territory_does_not_claim_global_availability_and_fails_visual_gate(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"].pop("territory")
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")
        self.assertIn("TERRITORY_STATUS_MISSING", adapted["evidence"]["external_video_page"]["validation_failures"])
        self.assertIsNone(adapted["evidence"]["external_video_page"]["territory"])
        self.assertEqual(adapted["territory"]["status"], "UNKNOWN")
        self.assertEqual(adapted["territory"]["territories"], [])

    def test_player_or_event_title_mismatch_does_not_verify_video(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["pageTitle"] = "Another Match | WTT Finals Men Doha 2023"
        evidence = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(evidence["status"], "REVIEW_REQUIRED")
        self.assertFalse(evidence["title_matches_match"])
        self.assertIn("PAGE_TITLE_MISMATCH", evidence["validation_failures"])

    def test_invalid_calendar_verification_date_is_not_a_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["testedAt"] = "2026-02-30"
        evidence = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(evidence["status"], "REVIEW_REQUIRED")
        self.assertIn("VERIFICATION_TIME_MISSING", evidence["validation_failures"])

    def test_unknown_territory_stays_unknown(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["territory"] = "UNKNOWN"
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["territory"]["status"], "UNKNOWN")
        self.assertEqual(adapted["evidence"]["external_video_page"]["territory"], "UNKNOWN")

    def test_external_visual_pass_never_sets_native_or_vision_pass(self):
        adapted = adapt_web_match_record(self.records[1])
        source = adapted["video_source"]
        self.assertEqual(source["evidence"]["external_video_page"]["status"], "EXTERNAL_VIDEO_PAGE_VISUAL_PASS")
        self.assertEqual(source["evidence"]["desktop_native_playback"]["status"], "NOT_TESTED")
        self.assertEqual(source["evidence"]["embed_playback"]["status"], "NOT_TESTED")
        self.assertNotIn("vision_result", source["evidence"])

    def test_missing_title_or_source_evidence_blocks_visual_pass(self):
        missing_title = copy.deepcopy(self.records[1])
        missing_title["playbackEvidence"].pop("pageTitle")
        title_result = adapt_web_match_record(missing_title)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(title_result["status"], "REVIEW_REQUIRED")
        self.assertIn("PAGE_TITLE_MISSING", title_result["validation_failures"])

        missing_source = copy.deepcopy(self.records[1])
        missing_source["sourceEvidence"] = ["https://www.worldtabletennis.com/eventInfo?eventId=1"]
        source_result = adapt_web_match_record(missing_source)["video_source"]["evidence"]["external_video_page"]
        self.assertEqual(source_result["status"], "REVIEW_REQUIRED")
        self.assertIn("SOURCE_EVIDENCE_MISSING_TARGET", source_result["validation_failures"])

    def test_observed_login_region_or_verification_prompt_blocks_visual_pass(self):
        for field in ("loginPromptSeen", "regionPromptSeen", "verificationPromptSeen"):
            with self.subTest(field=field):
                record = copy.deepcopy(self.records[1])
                record["playbackEvidence"][field] = True
                adapted = adapt_web_match_record(record)["video_source"]["evidence"]["external_video_page"]
                self.assertEqual(adapted["status"], "REVIEW_REQUIRED")

    def test_claimed_playback_with_no_visual_or_time_progress_is_review_required(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["timeAtFinalObservationSeconds"] = 2
        record["playbackEvidence"]["visualFramesChanged"] = False
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")

    def test_external_visual_claim_without_review_date_is_not_a_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"].pop("testedAt", None)
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")

    def test_naive_datetime_and_huge_times_fail_closed(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["testedAt"] = "2026-10-12T12:30:00"
        record["playbackEvidence"]["timeAtFirstObservationSeconds"] = 1
        record["playbackEvidence"]["timeAtFinalObservationSeconds"] = 10**1000
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")

    def test_redirect_to_other_host_does_not_pass(self):
        record = copy.deepcopy(self.records[1])
        record["playbackEvidence"]["finalUrl"] = "https://unrelated.example.test/watch"
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")

    def test_external_url_and_embed_claim_do_not_prove_embed_playback(self):
        record = copy.deepcopy(self.records[1])
        record["embedAllowed"] = True
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["rights"]["embedding"], "ALLOWED")
        self.assertEqual(adapted["evidence"]["embed_playback"]["status"], "NOT_TESTED")

    def test_thumbnail_url_is_omitted_without_explicit_display_permission(self):
        record = copy.deepcopy(self.records[1])
        record["thumbnailUrl"] = "https://images.example.test/poster.jpg"
        record.pop("thumbnailDisplayPermission", None)
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertIsNone(adapted["thumbnail_url"])

    def test_unknown_region_does_not_become_global(self):
        source = self.contract["video_sources"][1]
        self.assertEqual(source["territory"]["status"], "UNKNOWN")
        self.assertEqual(source["territory"]["territories"], [])

    def test_source_only_record_is_not_a_video_or_full_match(self):
        source = self.contract["video_sources"][3]
        self.assertEqual(source["resource_kind"], "UNKNOWN")
        self.assertEqual(source["content_type"], "ARTICLE")
        self.assertIsNone(source["evidence"]["external_video_page"]["final_url"])

    def test_unsafe_urls_and_duplicate_ids_are_rejected(self):
        record = copy.deepcopy(self.records[0])
        record["platformUrl"] = "javascript:alert(1)"
        record["sourceEvidence"] = "https://this-is-not-an-array.example/"
        with self.assertRaisesRegex(ValueError, "no safe HTTPS"):
            adapt_web_match_record(record)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            adapt_web_match_records([self.records[0], self.records[0]])

    def test_video_page_does_not_fall_back_to_an_event_article_url(self):
        record = copy.deepcopy(self.records[1])
        record["videoOriginalUrl"] = None
        record["platformUrl"] = None
        with self.assertRaisesRegex(ValueError, "no safe HTTPS"):
            adapt_web_match_record(record)

    def test_malformed_player_field_does_not_split_a_string_into_names(self):
        record = copy.deepcopy(self.records[0])
        record["players"] = "not-a-list"
        adapted = adapt_web_match_record(record)
        self.assertEqual(adapted["match"]["participant_names_unassigned"], [])


class DesktopAndLocalAdapterTests(unittest.TestCase):
    def test_local_analysis_license_does_not_grant_public_or_training_rights(self):
        asset = adapt_local_video_asset(read_json("desktop-local-asset.json"))
        rights = asset["rights"]
        self.assertEqual(rights["local_analysis"], "ALLOWED")
        for key in ("metadata_listing", "thumbnail_display", "external_viewing", "embedding", "model_training", "redistribution"):
            self.assertEqual(rights[key], "UNKNOWN", key)
        self.assertEqual(rights["basis_urls"], [])

    def test_explicit_denial_wins_over_local_analysis_license_label(self):
        source = read_json("desktop-local-asset.json")
        source["permissions"]["local_analysis"] = "DENIED"
        asset = adapt_local_video_asset(source)
        self.assertEqual(asset["rights"]["local_analysis"], "DENIED")

    def test_local_absolute_paths_database_and_private_notes_are_not_serialized(self):
        asset = adapt_local_video_asset(read_json("desktop-local-asset.json"))
        public = to_web_safe_payload({"matches": [], "video_sources": [], "local_video_assets": [asset], "timeline_mappings": []})
        serialized = json.dumps({"asset": asset, "web": public})
        for private_value in ("D:\\\\PrivateResearch", "C:\\\\Users", "qa.sqlite3", "private_reviewer_note"):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(public["local_video_assets"], [])

    def test_desktop_local_source_identity_and_rational_timeline_are_kept(self):
        asset = adapt_local_video_asset(read_json("desktop-local-asset.json"))
        self.assertEqual(asset["source_sha256"], "a" * 64)
        self.assertEqual(asset["timeline"]["time_base"], {"numerator": 1, "denominator": 15360})
        self.assertEqual(asset["timeline"]["frame_rate"], {"numerator": 120, "denominator": 1})
        self.assertEqual(asset["vision_result"]["status"], "NO_VERIFIED_RESULT")

    def test_generic_playback_verified_flag_does_not_create_native_pass(self):
        record = read_json("untrusted-inputs.json")["desktop_source_without_rights"]
        adapted = adapt_desktop_video_source(record)
        self.assertEqual(adapted["evidence"]["desktop_native_playback"]["status"], "NOT_TESTED")
        self.assertEqual(adapted["evidence"]["embed_playback"]["status"], "NOT_TESTED")
        self.assertEqual(adapted["territory"]["status"], "UNKNOWN")
        self.assertIsNone(adapted["thumbnail_url"])

    def test_desktop_source_metadata_is_allowlisted_and_deidentified(self):
        raw = read_json("desktop-video-source.json")
        adapted = adapt_desktop_video_source(raw)
        self.assertEqual(adapted["source_id"], "desktop-source:fixture-desktop-source-01")
        self.assertEqual(adapted["canonical_url"], "https://publisher.example.test/match/01")
        self.assertEqual(adapted["rights"]["embedding"], "DENIED")
        self.assertEqual(adapted["rights"]["basis_urls"], ["https://publisher.example.test/terms"])
        self.assertEqual(adapted["evidence"]["page_access"]["status"], "OFFICIAL_PAGE_ACCESS_PASS")
        self.assertEqual(adapted["evidence"]["embed_playback"]["status"], "NOT_TESTED")
        serialized = json.dumps(adapted)
        for private_value in ("E:\\\\LocalVault", "private.sqlite3", "private_notes"):
            self.assertNotIn(private_value, serialized)

    def test_desktop_external_pass_claim_requires_same_host_and_evidence(self):
        raw = read_json("desktop-video-source.json")
        raw["video_source"]["external_video_page"] = {
            "status": "EXTERNAL_VIDEO_PAGE_VISUAL_PASS",
            "checked_at": "2026-10-12",
            "final_url": "https://unrelated.example.test/video",
            "time_first_seconds": 2,
            "time_last_seconds": 14,
            "visual_frames_changed": True,
            "evidence_ref": "browser-review-01",
        }
        adapted = adapt_desktop_video_source(raw)
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")

    def test_desktop_external_pass_claim_uses_exact_url_and_five_second_floor(self):
        raw = read_json("desktop-video-source.json")
        raw["video_source"]["external_video_page"] = {
            "status": "EXTERNAL_VIDEO_PAGE_VISUAL_PASS",
            "checked_at": "2026-10-12",
            "final_url": "https://publisher.example.test/match/01",
            "time_first_seconds": 2,
            "time_last_seconds": 7,
            "visual_frames_changed": True,
            "page_title": "Fixture Match Video",
            "title_matches_match": True,
            "publisher": "Fixture Official Publisher",
            "publisher_verified": True,
            "source_evidence_urls": ["https://publisher.example.test/match/01"],
            "source_evidence_verified": True,
            "login_prompt_seen": False,
            "region_prompt_seen": False,
            "verification_prompt_seen": False,
            "audible_output_confirmed": False,
            "territory": "UNKNOWN",
            "evidence_ref": "browser-review-01",
        }
        exact = adapt_desktop_video_source(raw)["evidence"]["external_video_page"]
        self.assertEqual(exact["status"], "EXTERNAL_VIDEO_PAGE_VISUAL_PASS")
        self.assertEqual(exact["audio_status"], "UNKNOWN")
        self.assertFalse(exact["audio_confirmation_observed"])
        raw["video_source"]["external_video_page"].pop("evidence_ref")
        no_ref = adapt_desktop_video_source(raw)["evidence"]["external_video_page"]
        self.assertEqual(no_ref["status"], "REVIEW_REQUIRED")
        self.assertIn("EVIDENCE_REFERENCE_MISSING", no_ref["validation_failures"])
        raw["video_source"]["external_video_page"]["evidence_ref"] = "browser-review-01"
        raw["video_source"]["external_video_page"]["time_last_seconds"] = 6
        short = adapt_desktop_video_source(raw)["evidence"]["external_video_page"]
        self.assertEqual(short["status"], "REVIEW_REQUIRED")
        self.assertIn("TIMELINE_ADVANCE_LT_5_SECONDS", short["validation_failures"])

    def test_desktop_page_access_pass_without_url_or_date_is_review_required(self):
        raw = read_json("desktop-video-source.json")
        raw["video_source"]["page_access"] = {"status": "OFFICIAL_PAGE_ACCESS_PASS"}
        adapted = adapt_desktop_video_source(raw)
        self.assertEqual(adapted["evidence"]["page_access"]["status"], "REVIEW_REQUIRED")

    def test_web_safe_projection_requires_both_listing_and_external_view_rights(self):
        contract = build_contract(web_records=self.records, local_assets=[read_json("desktop-local-asset.json")])
        projected = to_web_safe_payload(contract)
        self.assertEqual(projected["video_sources"], [])
        self.assertEqual(projected["matches"], [])
        self.assertEqual(projected["local_video_assets"], [])

    @property
    def records(self):
        return read_json("web-match-records.json")

    def test_untrusted_web_claim_does_not_cross_to_native_or_embedding(self):
        record = read_json("untrusted-inputs.json")["inconsistent_web_playback"]
        adapted = adapt_web_match_record(record)["video_source"]
        self.assertEqual(adapted["evidence"]["external_video_page"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(adapted["evidence"]["desktop_native_playback"]["status"], "NOT_TESTED")
        self.assertEqual(adapted["evidence"]["embed_playback"]["status"], "NOT_TESTED")

    def test_mismatched_vision_sha_or_timeline_is_demoted(self):
        source = read_json("desktop-local-asset.json")
        source["vision_result"] = read_json("untrusted-inputs.json")["mismatched_vision_result"]
        asset = adapt_local_video_asset(source)
        self.assertEqual(asset["vision_result"]["status"], "REVIEW_REQUIRED")
        self.assertIsNone(asset["vision_result"]["result_ref"])

    def test_unverified_timeline_offset_is_removed(self):
        mapping = adapt_timeline_mapping(read_json("untrusted-inputs.json")["unverified_timeline_mapping"])
        self.assertEqual(mapping["status"], "UNKNOWN")
        self.assertIsNone(mapping["offset_ms"])
        self.assertIsNone(mapping["scale"])
        self.assertEqual(mapping["evidence_refs"], [])

    def test_human_verified_timeline_requires_evidence_refs(self):
        raw = {
            "mapping_id": "mapping-fixture",
            "from_source_id": "source-a",
            "to_source_id": "source-b",
            "status": "HUMAN_VERIFIED",
            "offset_ms": 500,
            "scale": 1,
            "evidence_refs": [],
        }
        mapping = adapt_timeline_mapping(raw)
        self.assertEqual(mapping["status"], "REVIEW_REQUIRED")
        self.assertIsNone(mapping["offset_ms"])

    def test_human_verified_timeline_requires_a_date_and_finite_transform(self):
        raw = {
            "mapping_id": "mapping-fixture",
            "from_source_id": "source-a",
            "to_source_id": "source-b",
            "status": "HUMAN_VERIFIED",
            "verified_at": "2026-10-12",
            "offset_ms": float("inf"),
            "scale": 1,
            "evidence_refs": ["review-fixture-1"],
        }
        mapping = adapt_timeline_mapping(raw)
        self.assertEqual(mapping["status"], "REVIEW_REQUIRED")
        self.assertIsNone(mapping["offset_ms"])

    def test_naive_verified_at_and_huge_offset_fail_closed(self):
        raw = {
            "mapping_id": "mapping-fixture",
            "from_source_id": "source-a",
            "to_source_id": "source-b",
            "status": "HUMAN_VERIFIED",
            "verified_at": "2026-10-12T12:30:00",
            "offset_ms": 10**1000,
            "scale": 1,
            "evidence_refs": ["review-fixture-1"],
        }
        mapping = adapt_timeline_mapping(raw)
        self.assertEqual(mapping["status"], "REVIEW_REQUIRED")
        self.assertIsNone(mapping["offset_ms"])

    def test_complete_human_verified_timeline_mapping_is_retained(self):
        raw = {
            "mapping_id": "mapping-fixture",
            "from_source_id": "source-a",
            "to_source_id": "source-b",
            "status": "HUMAN_VERIFIED",
            "verified_at": "2026-10-12",
            "offset_ms": 250,
            "scale": 1.0,
            "evidence_refs": ["review-fixture-1"],
        }
        mapping = adapt_timeline_mapping(raw)
        self.assertEqual(mapping["status"], "HUMAN_VERIFIED")
        self.assertEqual(mapping["offset_ms"], 250)
        self.assertEqual(mapping["evidence_refs"], ["review-fixture-1"])

    def test_bad_local_sha_and_bad_identifiers_are_rejected(self):
        source = read_json("desktop-local-asset.json")
        source["source_sha256"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            adapt_local_video_asset(source)
        bad = read_json("desktop-local-asset.json")
        bad["local_asset_id"] = "../secret"
        asset = adapt_local_video_asset(bad)
        self.assertEqual(asset["local_asset_id"], "sha256:" + "a" * 24)

    def test_pending_local_file_hash_is_not_exported_as_verified_identity(self):
        source = read_json("desktop-local-asset.json")
        source["hash_status"] = "PENDING"
        with self.assertRaisesRegex(ValueError, "SHA-256 is not verified"):
            adapt_local_video_asset(source)


if __name__ == "__main__":
    unittest.main()
