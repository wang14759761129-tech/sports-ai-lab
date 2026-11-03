#!/usr/bin/env python3
"""Build GOAL15's additive, strict-public Fan Universe index.

Only reviewed factual metadata and official outbound links are projected. Media
rights, playback and equipment/social claims fail closed and stay unverified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
BASE_PATH = INTEGRATION_DIR / "generated" / "goal14-main-content-expansion-v0.1" / "match-library-strict-public.json"
FIXTURE_PATH = INTEGRATION_DIR / "fixtures" / "goal15-main-fan-universe-v0.1" / "admissions.json"
OUTPUT_DIR = INTEGRATION_DIR / "generated" / "goal15-main-fan-universe-v0.1"
SCHEMA_PATH = INTEGRATION_DIR / "contracts" / "match-library-index-v0.1.schema.json"
GENERATOR_PATH = Path(__file__).resolve()

CONTRACT = "ptti.match-library-index/0.1"
ADMISSIONS_CONTRACT = "ptti.goal15-content-admissions/0.1"
AUDIT_CONTRACT = "ptti.goal15-content-review/0.1"
ALLOWED_RIGHTS = {
    "public_listing": "ALLOWED",
    "external_viewing": "ALLOWED",
    "thumbnail_display": "NOT_ALLOWED",
    "embedding": "UNKNOWN",
    "local_analysis": "NOT_GRANTED",
    "download": "NOT_GRANTED",
    "redistribution": "NOT_GRANTED",
    "scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
}


class AdmissionError(ValueError):
    """Input is missing identity evidence or attempts to widen public use."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"cannot-read-{path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdmissionError(f"not-an-object-{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AdmissionError(code)


def _unique(rows: list[dict[str, Any]], key: str, error: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get(key)
        _require(isinstance(item_id, str) and item_id and item_id not in result, error)
        result[item_id] = row
    return result


def _new_source(row: dict[str, Any], captured_at: str) -> dict[str, Any]:
    video_id = row.get("video_id")
    source_id = row.get("source_id")
    _require(isinstance(video_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) is not None, "invalid-youtube-video-id")
    _require(source_id == f"video-source:youtube:{video_id}", "source-id-video-id-mismatch")
    _require(row.get("official_url") == f"https://www.youtube.com/watch?v={video_id}", "official-url-video-id-mismatch")
    _require(row.get("publisher") == "World Table Tennis", "publisher-not-verified-wtt")
    _require(row.get("publisher_url") == "https://www.youtube.com/@wttglobal", "publisher-channel-mismatch")
    title = row.get("original_title")
    _require(isinstance(title, str) and title.startswith("FULL MATCH | "), "missing-full-match-title-claim")
    _require(row.get("content_type_claim") == "FULL_MATCH", "content-type-claim-mismatch")
    _require(row.get("rights") == ALLOWED_RIGHTS, "media-rights-escalation")
    _require(row.get("external_link_scope") == "OFFICIAL_YOUTUBE_SHARE_URL_ONLY", "external-link-scope-too-broad")
    _require(row.get("public_listing_scope") == "FACTUAL_MATCH_EVENT_PARTICIPANTS_RESULT_AND_SOURCE_ATTRIBUTION_ONLY", "public-listing-scope-too-broad")

    participants = row.get("participants")
    _require(isinstance(participants, list) and len(participants) == 2, "invalid-match-participants")
    participant_sides = {participant.get("side") for participant in participants if isinstance(participant, dict)}
    _require(participant_sides == {"A", "B"}, "participant-sides-invalid")
    names = {str(participant.get("name_en", "")).casefold() for participant in participants}
    source_names = {str(row.get("title_claim_participant_a", "")).casefold(), str(row.get("title_claim_participant_b", "")).casefold()}
    _require(names == source_names and "" not in names, "video-title-participant-mismatch")

    event = row.get("event")
    _require(isinstance(event, dict) and event.get("event_year") in (2025, 2026), "invalid-event-identity")
    title_lower = title.casefold()
    _require(str(event["event_year"]) in title and "final" in title_lower, "title-event-or-round-mismatch")
    _require(row["match_type"].casefold() in title_lower, "title-match-type-mismatch")
    event_token = "china" if "china" in event["name"].casefold() else "singapore" if "singapore" in event["name"].casefold() else None
    _require(event_token is not None and event_token in title_lower, "title-event-name-mismatch")
    _require(isinstance(row.get("reference_url"), str) and row["reference_url"].startswith("https://www.worldtabletennis.com/"), "non-official-match-reference")
    _require(isinstance(row.get("published_at"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["published_at"]) is not None, "invalid-video-published-date")

    evidence_ids = list(dict.fromkeys([*row.get("match_evidence_ids", []), *row.get("video_evidence_ids", []), *row.get("rights_evidence_ids", [])]))
    _require("youtube-share-link-help" in evidence_ids, "missing-official-link-sharing-basis")
    claimed_type = row["content_type_claim"]
    return {
        "catalog_record_id": f"catalog:youtube:{video_id}",
        "source_id": source_id,
        "video_id": video_id,
        "platform": "YOUTUBE",
        "official_url": row["official_url"],
        "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
        "title": title,
        "original_title": title,
        "display_title_zh": row.get("display_title_zh"),
        "published_at": row["published_at"],
        "event": event["name"],
        "event_display_zh": event.get("name_zh"),
        "event_id": event.get("event_id"),
        "event_year": event["event_year"],
        "match_date": None,
        "match_type": row["match_type"],
        "round": row["round"],
        "participants_claimed": {
            "side_a": next(p["name_en"] for p in participants if p["side"] == "A"),
            "side_b": next(p["name_en"] for p in participants if p["side"] == "B"),
            "unassigned_names": [],
        },
        "publisher": row["publisher"],
        "publisher_url": row["publisher_url"],
        "publisher_identity_status": "VERIFIED",
        "source_identity_status": "VERIFIED",
        "identity_conflicts": [],
        "source_verified_at": captured_at,
        "canonical_match_id": row["match_id"],
        "match_link_status": "HUMAN_VERIFIED",
        "content_type_claim": claimed_type,
        "completeness_status": "UNVERIFIED",
        "permission_status_recorded": "SCOPED_PUBLIC_FACTUAL_METADATA_AND_OFFICIAL_EXTERNAL_LINK_ONLY",
        "rights": {
            **copy.deepcopy(row["rights"]),
            "evidence_status": "OFFICIAL_LINK_ONLY_NO_MEDIA_USE_GRANT",
            "evidence_source_ids": evidence_ids,
        },
        "thumbnail": {"url": None, "source_has_thumbnail_url": True, "display_status": "NOT_DISPLAYED_PERMISSION_NOT_GRANTED"},
        "availability": {
            "official_page_current": "NOT_TESTED",
            "external_video_visual_latest_recorded": "NOT_TESTED",
            "external_observations": [{
                "surface": "OFFICIAL_YOUTUBE_VIDEO_METADATA",
                "checked_at": captured_at,
                "page_accessible": None,
                "visual_playback": "NOT_TESTED",
                "observed_result": "Exact official video title, publisher, match type and round metadata cross-checked against the official WTT result/report.",
                "limitations": "The title's FULL MATCH claim is not a completeness check. Current playback, region, login/paywall, embed permission, thumbnail reuse and native playback are untested or not granted.",
            }],
            "platform_embed": {"permission": "UNKNOWN", "latest_recorded_technical_status": "NOT_TESTED", "historical_attempts": []},
            "desktop_native_playback": "NOT_TESTED",
            "vision_analysis": "NOT_TESTED",
            "current_session_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
            "latest_recorded_playback_status": "NOT_TESTED",
            "territory_availability": "UNKNOWN",
            "recorded_region_restriction": "UNKNOWN",
            "login_or_paywall": "NOT_TESTED",
        },
        "provenance": [{
            "snapshot": "goal15-main-fan-universe-v0.1/admissions.json",
            "recorded_at": captured_at,
            "metadata_method": "OFFICIAL_WTT_RESULT_AND_VERIFIED_WTT_YOUTUBE_METADATA_CROSSCHECK",
            "source_id": evidence_id,
            "source_rights_scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
            "playback_status_recorded": "NOT_TESTED",
        } for evidence_id in evidence_ids],
        "snapshot_count": 1,
        "source_identity_evidence_scope": "OFFICIAL_VIDEO_METADATA_AND_MATCH_REPORT_NOT_VISUAL_PLAYBACK",
    }


def _new_match(row: dict[str, Any]) -> dict[str, Any]:
    source_id = row.get("source_id")
    _require(isinstance(row.get("match_id"), str) and row["match_id"].startswith("pro:wtt:"), "invalid-ptti-match-id")
    _require(row.get("match_type") in {"MS", "WS", "MD", "WD", "XD"}, "invalid-match-type")
    _require(row.get("provider_match_id") is None, "provider-match-id-not-evidenced")
    _require(row.get("result_status") == "OFFICIAL_WTT_RESULT_CROSSCHECKED", "match-result-not-crosschecked")
    _require(row.get("rights") == ALLOWED_RIGHTS, "match-rights-escalation")
    game_result = row.get("recorded_result")
    _require(isinstance(game_result, dict) and set(game_result) == {"player_a_games", "player_b_games"}, "invalid-recorded-result")
    _require(max(game_result.values()) == 4 and min(game_result.values()) < 4, "invalid-best-of-seven-result")
    participants = row["participants"]
    winner_id = row.get("recorded_winner_id")
    expected_winner = next(p["athlete_id"] for p in participants if p["side"] == ("A" if game_result["player_a_games"] > game_result["player_b_games"] else "B"))
    _require(winner_id == expected_winner, "winner-result-mismatch")
    evidence = list(dict.fromkeys([*row.get("match_evidence_ids", []), *row.get("video_evidence_ids", [])]))
    return {
        "match_id": row["match_id"],
        "identity_status": "REGISTERED_PTTI_MATCH_NO_PROVIDER_MATCH_ID",
        "event": copy.deepcopy(row["event"]),
        "match_type": row["match_type"],
        "round": row["round"],
        "round_zh": row.get("round_zh"),
        "display_title_zh": row.get("display_title_zh"),
        "participants": copy.deepcopy(participants),
        "recorded_result": copy.deepcopy(game_result),
        "recorded_winner_id": winner_id,
        "recorded_winner_name": row["recorded_winner_name"],
        "result_status": row["result_status"],
        "reference_url": row["reference_url"],
        "provider_match_id": None,
        "evidence_source_ids": evidence,
        "video_source_ids": [source_id],
        "match_video_link_status": "HUMAN_VERIFIED",
        "rights": {
            "public_listing": "ALLOWED",
            "evidence_status": "SCOPED_FACTUAL_METADATA_ONLY",
            "scope": row["public_listing_scope"],
            "evidence_source_ids": row.get("match_evidence_ids", []),
        },
    }


def _new_athlete(row: dict[str, Any], evidence_map: dict[str, dict[str, Any]], captured_at: str) -> dict[str, Any]:
    athlete_id = row.get("athlete_id")
    _require(isinstance(athlete_id, str) and re.fullmatch(r"athlete:\d+", athlete_id) is not None, "invalid-athlete-id")
    evidence_id = row.get("evidence_source_id")
    evidence = evidence_map.get(evidence_id)
    _require(evidence is not None and evidence.get("url") == row.get("official_profile_url"), "athlete-profile-evidence-mismatch")
    _require(evidence.get("source_type") == "OFFICIAL_ITTF_PLAYER_PROFILE", "athlete-profile-not-official")
    _require(isinstance(row.get("name_en"), str) and row.get("association") == "CHN", "athlete-identity-fields-incomplete")
    return {
        "athlete_id": athlete_id,
        "name_en": row["name_en"],
        "name_zh": row.get("name_zh"),
        "association": row["association"],
        "official_profile_url": row["official_profile_url"],
        "profile_last_verified_at": captured_at,
        "profile_link_status": "NOT_TESTED_IN_USER_BROWSER",
        "name_zh_provenance": "USER_PROVIDED_DISPLAY_LABEL_NOT_IDENTITY_KEY",
        "evidence_source_ids": [evidence_id],
        "public_listing": "ALLOWED",
        "public_listing_scope": "FACTUAL_NAME_STABLE_ID_ASSOCIATION_AND_OFFICIAL_PROFILE_LINK_ONLY_NO_PORTRAIT_OR_BIOGRAPHY",
        "portrait": {"url": None, "display_status": "NOT_DISPLAYED_PERMISSION_NOT_VERIFIED"},
        "equipment": {"status": "UNKNOWN", "items": []},
        "coach_observations": {"status": "NOT_COLLECTED", "items": []},
        "interviews": {"status": "NOT_COLLECTED", "items": []},
        "sponsorships": {"status": "UNKNOWN", "items": []},
        "social_feedback": {"status": "NOT_COLLECTED", "items": []},
        "official_social_accounts": {"status": "NOT_VERIFIED", "items": []},
    }


def build_package(base: dict[str, Any], fixture: dict[str, Any], generated_at: str, base_path: Path, fixture_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _require(base.get("contract_version") == CONTRACT and base.get("view") == "STRICT_PUBLIC", "unsupported-base-package")
    _require(fixture.get("contract_version") == ADMISSIONS_CONTRACT, "unsupported-admissions-version")
    _require(fixture.get("purpose") == "STRICT_PUBLIC_FACTUAL_MATCH_AND_OFFICIAL_EXTERNAL_LINK_ONLY", "admission-purpose-too-broad")
    matches_by_id = _unique(base.get("matches", []), "match_id", "duplicate-base-match-id")
    sources_by_id = _unique(base.get("video_sources", []), "source_id", "duplicate-base-source-id")
    stars_by_id = _unique(base.get("stars", []), "athlete_id", "duplicate-base-athlete-id")
    evidence_rows = list(base.get("evidence_sources", []))
    evidence_by_id = _unique(evidence_rows, "source_id", "duplicate-base-evidence-id")
    new_evidence = fixture.get("evidence_sources", [])
    for evidence in new_evidence:
        _require(evidence.get("source_id") not in evidence_by_id, "duplicate-evidence-source-id")
        evidence_by_id[evidence["source_id"]] = evidence
        evidence_rows.append(copy.deepcopy(evidence))

    additions = fixture.get("admissions", [])
    _require(len(additions) == 2, "unexpected-admission-count")
    added_matches: list[dict[str, Any]] = []
    added_sources: list[dict[str, Any]] = []
    for row in additions:
        _require(row.get("source_id") not in sources_by_id, "duplicate-video-source-id")
        _require(row.get("match_id") not in matches_by_id, "duplicate-match-id")
        evidence_ids = set(row.get("match_evidence_ids", [])) | set(row.get("video_evidence_ids", [])) | set(row.get("rights_evidence_ids", []))
        _require(evidence_ids <= set(evidence_by_id), "unknown-admission-evidence-reference")
        source = _new_source(row, generated_at)
        match = _new_match(row)
        added_sources.append(source)
        added_matches.append(match)

    for row in fixture.get("athletes", []):
        athlete = _new_athlete(row, evidence_by_id, generated_at)
        _require(athlete["athlete_id"] not in stars_by_id, "duplicate-athlete-id")
        stars_by_id[athlete["athlete_id"]] = athlete

    for match in added_matches:
        matches_by_id[match["match_id"]] = match
    for source in added_sources:
        sources_by_id[source["source_id"]] = source
    for match in matches_by_id.values():
        _require(set(match.get("video_source_ids", [])) <= set(sources_by_id), "match-references-missing-source")
    for source in sources_by_id.values():
        if source.get("match_link_status") == "HUMAN_VERIFIED":
            _require(source.get("canonical_match_id") in matches_by_id, "verified-source-references-missing-match")

    manifest = [*copy.deepcopy(base.get("source_manifest", []))]
    manifest.extend([
        {"file": base_path.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(base_path)},
        {"file": fixture_path.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(fixture_path)},
        {"file": GENERATOR_PATH.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(GENERATOR_PATH)},
    ])
    type_counts: dict[str, int] = {}
    for source in sources_by_id.values():
        content_type = source.get("content_type_claim", "UNKNOWN")
        type_counts[content_type] = type_counts.get(content_type, 0) + 1
    package = copy.deepcopy(base)
    package.update({
        "generated_at": generated_at,
        "source_manifest": manifest,
        "matches": list(matches_by_id.values()),
        "video_sources": list(sources_by_id.values()),
        "stars": list(stars_by_id.values()),
        "evidence_sources": evidence_rows,
        "quality_summary": {
            **copy.deepcopy(base.get("quality_summary", {})),
            "public_match_count": len(matches_by_id),
            "public_video_source_count": len(sources_by_id),
            "public_star_count": len(stars_by_id),
            "public_match_video_link_count": sum(1 for source in sources_by_id.values() if source.get("match_link_status") == "HUMAN_VERIFIED"),
            "event_level_highlight_source_count": sum(1 for source in sources_by_id.values() if source.get("content_type_claim") == "HIGHLIGHTS" and source.get("match_link_status") == "UNKNOWN"),
            "content_type_claim_counts": type_counts,
            "full_match_completeness_verified_count": sum(1 for source in sources_by_id.values() if source.get("content_type_claim") == "FULL_MATCH" and source.get("completeness_status") == "VERIFIED"),
            "shorts_source_count": 0,
            "current_session_playback_pass_count": 0,
            "desktop_native_playback_pass_count": 0,
            "vision_analysis_pass_count": 0,
            "official_embed_permission_count": 0,
            "thumbnail_display_permission_count": 0,
            "goal15_new_match_count": len(added_matches),
            "goal15_new_source_count": len(added_sources),
            "goal15_new_star_count": len(fixture.get("athletes", [])),
            "counts_notice": "Content type counts represent official title/source claims, not verified full duration or playback. External official links do not grant embed, thumbnail, local-analysis, download, or redistribution rights.",
        },
        "notice": "GOAL15 strict-public projection contains factual match/event/player metadata, source attribution and official outbound YouTube links only. A FULL MATCH title is a publisher content-type claim; completeness, current visual playback, territory and current-session eligibility remain unverified. No thumbnail is displayed, and no embed, download, local analysis, or redistribution right is granted. No Shorts were verified for this batch.",
    })

    category_counts = {key: type_counts.get(key, 0) for key in ("FULL_MATCH", "HIGHLIGHTS", "SESSION", "CLIP", "UNKNOWN")}
    audit = {
        "contract_version": AUDIT_CONTRACT,
        "view": "INTERNAL_REVIEW",
        "generated_at": generated_at,
        "public_package_sha256": None,
        "athlete_review": [
            {
                "athlete_id": star["athlete_id"],
                "name_en": star.get("name_en"),
                "official_profile_url": star.get("official_profile_url"),
                "official_identity": "PROFILE_ID_EVIDENCE_RECORDED",
                "profile_page_access": star.get("profile_link_status", "INHERITED_FROM_GOAL14_BASE"),
                "official_social_account": "NOT_VERIFIED",
                "social_urls": [],
                "equipment_model": "UNKNOWN",
                "equipment_evidence": [],
                "portrait_display": "NOT_GRANTED_OR_NOT_VERIFIED",
            }
            for star in package["stars"]
        ],
        "video_type_review": {
            "strict_public_source_count": len(sources_by_id),
            "official_title_claim_counts": category_counts,
            "verified_complete_match_count": package["quality_summary"]["full_match_completeness_verified_count"],
            "verified_shorts_count": 0,
            "note": "Classification is based on source/title metadata. No visual playback or completeness review was performed.",
        },
        "community_news_candidates": [
            {"source_id": "goal15-wtt-china-smash-2025-ws-final", "url": "https://www.worldtabletennis.com/eventInfo?eventId=3098", "status": "OFFICIAL_EVENT_NEWS_AND_RESULT_LINK_ONLY"},
            {"source_id": "goal15-wtt-singapore-smash-2026-ms-final", "url": "https://www.worldtabletennis.com/description?artId=5957", "status": "OFFICIAL_MATCH_REPORT_LINK_ONLY"},
        ],
        "not_admitted": [
            {"candidate": "2026 Singapore Smash WD semifinal O241nV8y4Dc", "status": "INTERNAL_CANDIDATE_ONLY", "reason": "Official video title metadata was previously observed, but this pass did not complete an official WTT result-to-video cross-check and stable athlete/source evidence pack; no new match edge is created."},
            {"candidate": "Athlete personal social accounts", "status": "NOT_VERIFIED", "reason": "No account is included without a first-party WTT/ITTF profile or official team source linking the exact account."},
            {"candidate": "Player equipment models and sponsorship", "status": "UNKNOWN", "reason": "No first-party equipment or sponsorship statement tied to an exact model and time period was verified."},
            {"candidate": "WTT/ITTF Shorts", "status": "NO_EXACT_SHORTS_ID_VERIFIED_IN_THIS_PASS", "reason": "No exact official Shorts video ID and source metadata passed review; no placeholder or guessed link is emitted."},
        ],
        "rights_summary": {
            "external_official_share_url": "ALLOWED_WITHIN_PLATFORM_LINK_SHARING_SCOPE",
            "embedding": "UNKNOWN",
            "third_party_thumbnail_display": "NOT_ALLOWED",
            "download": "NOT_GRANTED",
            "local_analysis": "NOT_GRANTED",
            "redistribution": "NOT_GRANTED",
            "territory": "UNKNOWN",
            "external_playback": "NOT_TESTED",
            "desktop_native_playback": "NOT_TESTED",
            "vision_analysis": "NOT_TESTED",
        },
    }
    return package, audit


def write_outputs(package: dict[str, Any], audit: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / "match-library-strict-public.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit["public_package_sha256"] = _sha256(package_path)
    (output_dir / "candidate-review-internal.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-at", help="UTC ISO timestamp for reproducible output")
    parser.add_argument("--base", type=Path, default=BASE_PATH)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    base, fixture = _load(args.base), _load(args.fixture)
    package, audit = build_package(base, fixture, generated_at, args.base.resolve(), args.fixture.resolve())
    schema = _load(SCHEMA_PATH)
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - exercised in dependency-light use
        raise AdmissionError("jsonschema-required-for-public-projection") from exc
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(package)
    write_outputs(package, audit, args.output_dir)
    print(json.dumps({
        "status": "PASS",
        "contract_version": package["contract_version"],
        "view": package["view"],
        "matches": len(package["matches"]),
        "video_sources": len(package["video_sources"]),
        "stars": len(package["stars"]),
        "match_video_links": package["quality_summary"]["public_match_video_link_count"],
        "content_type_claim_counts": package["quality_summary"]["content_type_claim_counts"],
        "native_playback_passes": package["quality_summary"]["desktop_native_playback_pass_count"],
        "output_dir": str(args.output_dir.resolve()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
