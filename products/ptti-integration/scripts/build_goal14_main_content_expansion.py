#!/usr/bin/env python3
"""Build an additive, fail-closed GOAL14 strict-public content package."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
DEFAULT_BASE = INTEGRATION_DIR / "generated" / "goal14-main-admission" / "match-library-strict-public.json"
DEFAULT_INTERNAL = INTEGRATION_DIR / "generated" / "goal11-match-library" / "match-library-internal-review.json"
DEFAULT_FAN = INTEGRATION_DIR / "generated" / "goal14" / "fan-content-delivery-internal-review.json"
DEFAULT_REVIEW = INTEGRATION_DIR / "fixtures" / "goal14-main-content-expansion-v0.1.json"
DEFAULT_OUTPUT = INTEGRATION_DIR / "generated" / "goal14-main-content-expansion-v0.1"

LIBRARY_CONTRACT = "ptti.match-library-index/0.1"
REVIEW_CONTRACT = "ptti.main-content-expansion-review/0.1"
AUDIT_CONTRACT = "ptti.main-content-candidate-audit/0.1"
LINKABLE_HIGHLIGHT_IDS = {
    "xef0VQVV-OE", "WF0H02Br3LE", "zfrkMx5DdRo", "fa2j70xjqoU", "0820Zo3UaGM",
    "y9AYI43XtMI", "YNtnXjGiAcQ", "JZhxfSdn3E4", "AgIDgIo7bSY", "DRWntK5EJj0",
}
ALLOWED_MATCH_MEDIA_RIGHTS = {
    "embedding": "UNKNOWN",
    "thumbnail_display": "NOT_ALLOWED",
    "local_analysis": "NOT_GRANTED",
    "download": "NOT_GRANTED",
    "redistribution": "NOT_GRANTED",
}


class ExpansionError(ValueError):
    """Raised when review evidence is absent, inconsistent, or overbroad."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExpansionError(f"cannot-read-{path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExpansionError(f"not-an-object-{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ExpansionError(code)


def _by_id(rows: list[dict[str, Any]], key: str, error: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get(key)
        _require(isinstance(item_id, str) and item_id and item_id not in result, error)
        result[item_id] = row
    return result


def _youtube_url(video_id: str, url: str) -> bool:
    return url == f"https://www.youtube.com/watch?v={video_id}"


def _source_evidence(
    base: dict[str, Any],
    review: dict[str, Any],
    internal: dict[str, Any],
    fan: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [*base.get("evidence_sources", []), *review.get("evidence_sources", [])]
    base_references: set[str] = set()
    for match in base.get("matches", []):
        base_references.update(item for item in match.get("evidence_source_ids", []) if isinstance(item, str))
        base_references.update(item for item in match.get("rights", {}).get("evidence_source_ids", []) if isinstance(item, str))
    for source in base.get("video_sources", []):
        base_references.update(item for item in source.get("rights", {}).get("evidence_source_ids", []) if isinstance(item, str))
        base_references.update(row.get("source_id") for row in source.get("provenance", []) if isinstance(row, dict) and isinstance(row.get("source_id"), str))
    for star in base.get("stars", []):
        base_references.update(item for item in star.get("evidence_source_ids", []) if isinstance(item, str))
    for row in internal.get("evidence_sources", []):
        if row.get("source_id") in base_references | {"wtt-profile-123980"}:
            rows.append(row)
    existing = {row.get("source_id") for row in rows}

    # The Goal14 source index is an internal evidence snapshot, not a fresh playback test.
    for item in fan.get("source_index", []):
        item_id = item.get("evidence_id")
        if not isinstance(item_id, str) or item_id in existing:
            continue
        description = "; ".join([
            f"Observed claims: {', '.join(item.get('claims', []))}.",
            f"Limitations: {item.get('limitations', 'Not recorded.')}",
        ])
        if item.get("observed_title"):
            description += f" Exact observed title: {item['observed_title']}."
        if item.get("publisher"):
            description += f" Observed publisher: {item['publisher']}."
        if item.get("published_at"):
            description += f" Source-reported publish date: {item['published_at']}."
        rows.append({
            "source_id": item_id,
            "source_type": item.get("kind", "UNKNOWN"),
            "url": item.get("url"),
            "retrieved_at": item.get("observed_at"),
            "description": description,
        })
        existing.add(item_id)
    _by_id(rows, "source_id", "duplicate-evidence-source-id")
    return rows


def _validate_inputs(base: dict[str, Any], internal: dict[str, Any], fan: dict[str, Any], review: dict[str, Any]) -> None:
    _require(base.get("contract_version") == LIBRARY_CONTRACT and base.get("view") == "STRICT_PUBLIC", "unsupported-base-package")
    _require(internal.get("contract_version") == LIBRARY_CONTRACT and internal.get("view") == "INTERNAL_REVIEW", "unsupported-main-internal-index")
    _require(fan.get("contract_version") == "ptti.fan-content-delivery/0.1" and fan.get("view") == "INTERNAL_REVIEW", "unsupported-fan-candidate-package")
    _require(review.get("contract_version") == REVIEW_CONTRACT, "unsupported-review-version")
    _require(review.get("scope") == "SCOPED_PUBLIC_FACTUAL_METADATA_AND_OFFICIAL_EXTERNAL_LINK_ONLY", "overbroad-review-scope")
    _require(review.get("media_rights") == ALLOWED_MATCH_MEDIA_RIGHTS | {"scope_notice": review.get("media_rights", {}).get("scope_notice")}, "media-rights-default-escalation")
    _require(len(fan.get("clips", [])) == 20, "unexpected-candidate-count")
    _by_id(base.get("matches", []), "match_id", "duplicate-base-match-id")
    _by_id(base.get("video_sources", []), "source_id", "duplicate-base-source-id")
    _by_id(base.get("stars", []), "athlete_id", "duplicate-base-athlete-id")
    _by_id(fan.get("clips", []), "clip_id", "duplicate-candidate-id")


def _build_match_and_source(row: dict[str, Any], evidence_ids: set[str], evaluated_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    match_id = row.get("match_id")
    source_id = row.get("source_id") or f"video-source:youtube:{row.get('video_id')}"
    video_id = row.get("video_id")
    _require(isinstance(match_id, str) and match_id and isinstance(video_id, str) and video_id, "missing-match-or-video-id")
    _require(source_id == f"video-source:youtube:{video_id}", "match-source-id-mismatch")
    _require(_youtube_url(video_id, row.get("official_url", "")), "invalid-official-youtube-url")
    _require(row.get("match_link_status") == "HUMAN_VERIFIED", "match-link-not-reviewed")
    _require(row.get("public_listing_scope") == "FACTUAL_MATCH_EVENT_PARTICIPANTS_RESULT_AND_SOURCE_ATTRIBUTION_ONLY", "overbroad-match-listing-scope")
    _require(row.get("external_link_scope") == "OFFICIAL_YOUTUBE_SHARE_URL_ONLY", "overbroad-external-link-scope")
    _require(row.get("media_rights") == ALLOWED_MATCH_MEDIA_RIGHTS, "match-media-rights-escalation")
    _require(row.get("source_identity_status") == "VERIFIED" and row.get("publisher_identity_status") == "VERIFIED", "source-publisher-unverified")
    _require(row.get("completeness_status") == "UNVERIFIED", "completeness-upgrade-not-supported")
    required_evidence = set(row.get("match_evidence_ids", [])) | set(row.get("public_listing_evidence_ids", [])) | set(row.get("external_link_evidence_ids", []))
    _require(required_evidence <= evidence_ids, "unknown-match-evidence-reference")
    _require("youtube-share-link-help" in row.get("external_link_evidence_ids", []), "missing-platform-sharing-basis")

    match = {
        "match_id": match_id,
        "identity_status": "REGISTERED_PTTI_MATCH_NO_PROVIDER_MATCH_ID",
        "event": copy.deepcopy(row["event"]),
        "match_type": row["match_type"],
        "round": row["round"],
        "participants": copy.deepcopy(row["participants"]),
        "recorded_result": copy.deepcopy(row["recorded_result"]),
        "recorded_winner_id": row.get("recorded_winner_id"),
        "recorded_winner_name": row.get("recorded_winner_name"),
        "result_status": row["result_status"],
        "reference_url": row["reference_url"],
        "provider_match_id": row.get("provider_match_id"),
        "evidence_source_ids": sorted(set(row["match_evidence_ids"])),
        "video_source_ids": [source_id],
        "match_video_link_status": "HUMAN_VERIFIED",
        "rights": {
            "public_listing": "ALLOWED",
            "evidence_status": "SCOPED_FACTUAL_METADATA_ONLY",
            "scope": row["public_listing_scope"],
            "evidence_source_ids": sorted(set(row["public_listing_evidence_ids"])),
        },
    }
    source = {
        "catalog_record_id": f"catalog:youtube:{video_id}",
        "source_id": source_id,
        "video_id": video_id,
        "platform": "YOUTUBE",
        "official_url": row["official_url"],
        "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
        "title": row["original_title"],
        "original_title": row["original_title"],
        "event": row["event"]["name"],
        "event_year": row["event"]["event_year"],
        "match_date": row["event"].get("date"),
        "match_type": row["match_type"],
        "round": row["round"],
        "participants_claimed": {
            "side_a": next((p.get("name_en") for p in row["participants"] if p.get("side") == "A"), None),
            "side_b": next((p.get("name_en") for p in row["participants"] if p.get("side") == "B"), None),
            "unassigned_names": [],
        },
        "publisher": row["publisher"],
        "publisher_url": row["publisher_url"],
        "publisher_identity_status": "VERIFIED",
        "source_verified_at": evaluated_at,
        "source_identity_status": "VERIFIED",
        "identity_conflicts": [],
        "canonical_match_id": match_id,
        "match_link_status": "HUMAN_VERIFIED",
        "content_type_claim": "UNKNOWN",
        "completeness_status": "UNVERIFIED",
        "permission_status_recorded": "SCOPED_PUBLIC_METADATA_AND_EXTERNAL_LINK_ONLY",
        "rights": {
            "public_listing": "ALLOWED",
            "external_viewing": "ALLOWED",
            "thumbnail_display": "NOT_ALLOWED",
            "embedding": "UNKNOWN",
            "local_analysis": "NOT_GRANTED",
            "redistribution": "NOT_GRANTED",
            "evidence_status": "SCOPED_EXTERNAL_LINK_ONLY_NO_MEDIA_USE_GRANT",
            "scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
            "evidence_source_ids": sorted(set(row["external_link_evidence_ids"])),
        },
        "thumbnail": {"url": None, "source_has_thumbnail_url": True, "display_status": "NOT_DISPLAYED_PERMISSION_NOT_GRANTED"},
        "availability": {
            "official_page_current": "NOT_TESTED",
            "external_video_visual_latest_recorded": "NOT_TESTED",
            "external_observations": [{
                "surface": "OFFICIAL_YOUTUBE_VIDEO_METADATA",
                "checked_at": evaluated_at,
                "page_accessible": None,
                "visual_playback": "NOT_TESTED",
                "observed_result": "Official event and exact official video metadata cross-checked; no current video frame or playback was tested.",
                "limitations": "Territory, login/paywall, current page rendering, embed permission, and full-match completeness remain unknown or untested.",
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
            "snapshot": "goal14-main-content-expansion-v0.1.json",
            "recorded_at": evaluated_at,
            "metadata_method": "MANUAL_OFFICIAL_WTT_EVENT_AND_VERIFIED_YOUTUBE_METADATA_CROSSCHECK",
            "source_id": evidence_id,
            "source_rights_scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
            "playback_status_recorded": "NOT_TESTED",
        } for evidence_id in sorted(set(row["match_evidence_ids"]) | set(row["external_link_evidence_ids"]))],
        "snapshot_count": 1,
        "source_identity_evidence_scope": "OFFICIAL_VIDEO_METADATA_ONLY_NOT_VISUAL_PLAYBACK",
    }
    return match, source


def _candidate_sources(fan: dict[str, Any], review: dict[str, Any], fan_evidence: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = fan["clips"]
    allowlist = review["event_highlight_video_ids"]
    _require(isinstance(allowlist, list) and len(allowlist) == len(set(allowlist)) == 10, "invalid-highlight-allowlist")
    _require(set(allowlist) == LINKABLE_HIGHLIGHT_IDS, "highlight-allowlist-changed-without-review")
    candidate_by_video: dict[str, dict[str, Any]] = {}
    for clip in candidates:
        video_id = clip.get("video_id")
        if video_id is not None:
            _require(video_id not in candidate_by_video, "duplicate-candidate-video-id")
            candidate_by_video[video_id] = clip
    _require(set(candidate_by_video) == set(allowlist), "allowlisted-video-id-not-in-candidates")

    event_by_id = {row.get("event_id"): row for row in fan.get("events", [])}
    video_source_rows = {row.get("watch_source_id"): row for row in fan.get("watch_sources", [])}
    output_sources: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for clip in candidates:
        video_id = clip.get("video_id")
        event = event_by_id.get(clip.get("event_id"))
        _require(event is not None, "candidate-event-reference-missing")
        watch = video_source_rows.get(clip.get("watch_source_id"))
        _require(watch is not None, "candidate-watch-source-missing")
        if video_id is None:
            _require(clip.get("official_video_url") is None, "event-only-candidate-has-video-url")
            audit_rows.append({
                "candidate_id": clip["clip_id"],
                "event_id": clip["event_id"],
                "event": event["name"],
                "title_original": clip["title_original"],
                "video_id": None,
                "official_video_url": None,
                "related_event_page_url": event["official_event_page_url"],
                "publisher": None,
                "source_evidence_ids": list(clip["source_evidence_ids"]),
                "decision": "INTERNAL_ONLY_VIDEO_ID_UNRESOLVED",
                "reason": "The official event page lists a related-video title, but no exact video ID/URL was resolved; the event page is not counted as a distinct clip link.",
                "match_id": None,
                "match_link_status": "UNKNOWN",
                "playback_status": "NOT_TESTED",
                "territory": "UNKNOWN",
                "embedding": "UNKNOWN",
                "thumbnail_display": "NOT_ALLOWED",
                "download": "NOT_GRANTED",
                "redistribution": "NOT_GRANTED",
            })
            continue

        _require(video_id in allowlist, "unexpected-video-id")
        _require(clip.get("official_video_url") == f"https://www.youtube.com/watch?v={video_id}", "candidate-video-url-mismatch")
        _require(clip.get("publisher") == "World Table Tennis", "candidate-publisher-mismatch")
        event_evidence_ids = [item for item in clip.get("source_evidence_ids", []) if item.startswith(("evidence:wtt-event:", "evidence:wtt-article:"))]
        video_evidence_id = f"evidence:youtube:{video_id}"
        _require(len(event_evidence_ids) == 1 and video_evidence_id in clip.get("source_evidence_ids", []), "candidate-evidence-incomplete")
        event_evidence_id = event_evidence_ids[0]
        event_evidence, video_evidence = fan_evidence.get(event_evidence_id), fan_evidence.get(video_evidence_id)
        _require(event_evidence is not None and video_evidence is not None, "candidate-evidence-not-found")
        _require(video_evidence.get("url") == clip["official_video_url"], "candidate-evidence-url-mismatch")
        _require(video_evidence.get("observed_title") == clip["title_original"], "candidate-title-evidence-mismatch")
        _require(video_evidence.get("publisher") == "World Table Tennis", "candidate-publisher-evidence-mismatch")
        if event_evidence.get("listed_titles"):
            _require(clip["title_original"] in event_evidence["listed_titles"], "candidate-not-listed-by-event")
        else:
            # The Chongqing entry has no provider event ID; the WTT-published video title itself names the event.
            _require(event_evidence.get("kind") == "OFFICIAL_WTT_ARTICLE_SEARCH_INDEX", "candidate-event-link-not-evidenced")
            _require("chongqing 2025" in clip["title_original"].casefold() and "chongqing 2025" in event["name"].casefold(), "candidate-not-named-to-event")
        _require(review["candidate_review_rules"].get("match_join_requires_explicit_match_evidence") is True, "candidate-join-policy-unsafe")
        source_id = f"video-source:youtube:{video_id}"
        evidence_ids = [event_evidence_id, video_evidence_id, "youtube-share-link-help"]
        source = {
            "catalog_record_id": f"catalog:youtube:{video_id}",
            "source_id": source_id,
            "video_id": video_id,
            "platform": "YOUTUBE",
            "official_url": clip["official_video_url"],
            "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
            "title": clip["title_original"],
            "original_title": clip["title_original"],
            "event": event["name"],
            "event_year": event["event_year"],
            "match_date": None,
            "match_type": "UNKNOWN",
            "round": "Event-level highlights; individual match unknown",
            "participants_claimed": {"unassigned_names": []},
            "publisher": "World Table Tennis",
            "publisher_url": "https://www.youtube.com/@wttglobal",
            "publisher_identity_status": "VERIFIED",
            "source_verified_at": f"{video_evidence['observed_at']}T00:00:00Z",
            "source_identity_status": "VERIFIED",
            "identity_conflicts": [],
            "canonical_match_id": None,
            "match_link_status": "UNKNOWN",
            "content_type_claim": "HIGHLIGHTS",
            "completeness_status": "UNVERIFIED",
            "permission_status_recorded": "SCOPED_EVENT_METADATA_AND_EXTERNAL_LINK_ONLY",
            "rights": {
                "public_listing": "ALLOWED",
                "external_viewing": "ALLOWED",
                "thumbnail_display": "NOT_ALLOWED",
                "embedding": "UNKNOWN",
                "local_analysis": "NOT_GRANTED",
                "redistribution": "NOT_GRANTED",
                "evidence_status": "SCOPED_EXTERNAL_LINK_ONLY_NO_MEDIA_USE_GRANT",
                "scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
                "evidence_source_ids": evidence_ids,
            },
            "thumbnail": {"url": None, "source_has_thumbnail_url": True, "display_status": "NOT_DISPLAYED_PERMISSION_NOT_GRANTED"},
            "availability": {
                "official_page_current": "NOT_TESTED",
                "external_video_visual_latest_recorded": "NOT_TESTED",
                "external_observations": [{
                    "surface": "OFFICIAL_YOUTUBE_METADATA_SNAPSHOT",
                    "checked_at": f"{video_evidence['observed_at']}T00:00:00Z",
                    "page_accessible": None,
                    "visual_playback": "NOT_TESTED",
                    "observed_result": "Exact official title, video ID, publisher, and event listing are present in the recorded metadata snapshot.",
                    "limitations": "This is metadata evidence only. Current page access, playback, territory, embed permission, and content reuse are not verified.",
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
                "snapshot": "fan-content-delivery-internal-review.json",
                "recorded_at": f"{video_evidence['observed_at']}T00:00:00Z",
                "metadata_method": "OFFICIAL_WTT_EVENT_AND_VERIFIED_YOUTUBE_METADATA_SNAPSHOT",
                "source_id": evidence_id,
                "source_rights_scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
                "playback_status_recorded": "NOT_TESTED",
            } for evidence_id in evidence_ids],
            "snapshot_count": 1,
            "source_identity_evidence_scope": "OFFICIAL_VIDEO_METADATA_ONLY_NOT_VISUAL_PLAYBACK",
        }
        output_sources.append(source)
        audit_rows.append({
            "candidate_id": clip["clip_id"],
            "event_id": clip["event_id"],
            "event": event["name"],
            "title_original": clip["title_original"],
            "video_id": video_id,
            "official_video_url": clip["official_video_url"],
            "related_event_page_url": event["official_event_page_url"],
            "publisher": "World Table Tennis",
            "published_at": clip.get("published_at"),
            "source_evidence_ids": list(clip["source_evidence_ids"]),
            "decision": "PUBLIC_OFFICIAL_EXTERNAL_LINK_ONLY",
            "reason": "Exact official YouTube video ID/title and verified publisher are recorded, and the official event page lists the title. No match-level edge or media-use rights are inferred.",
            "match_id": None,
            "match_link_status": "UNKNOWN",
            "playback_status": "NOT_TESTED",
            "territory": "UNKNOWN",
            "embedding": "UNKNOWN",
            "thumbnail_display": "NOT_ALLOWED",
            "download": "NOT_GRANTED",
            "redistribution": "NOT_GRANTED",
        })
    return output_sources, audit_rows


def build_expansion(base: dict[str, Any], internal: dict[str, Any], fan: dict[str, Any], review: dict[str, Any], generated_at: str, paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(base, internal, fan, review)
    fan_evidence = _by_id(fan.get("source_index", []), "evidence_id", "duplicate-fan-evidence-id")
    source_evidence = _source_evidence(base, review, internal, fan)
    evidence_map = _by_id(source_evidence, "source_id", "duplicate-output-evidence-id")
    admitted_matches: list[dict[str, Any]] = []
    admitted_match_sources: list[dict[str, Any]] = []
    for row in review["additional_match_admissions"]:
        match, source = _build_match_and_source(row, set(evidence_map), review["evaluated_at"])
        admitted_matches.append(match)
        admitted_match_sources.append(source)

    existing_match_ids = {row["match_id"] for row in base["matches"]}
    existing_source_ids = {row["source_id"] for row in base["video_sources"]}
    _require(not existing_match_ids.intersection(row["match_id"] for row in admitted_matches), "duplicate-expanded-match-id")
    _require(not existing_source_ids.intersection(row["source_id"] for row in admitted_match_sources), "duplicate-expanded-source-id")

    stars_by_id = {row["athlete_id"]: copy.deepcopy(row) for row in base["stars"]}
    internal_stars = _by_id(internal.get("stars", []), "athlete_id", "duplicate-internal-athlete-id")
    for admission in review["additional_star_admissions"]:
        athlete_id = admission.get("athlete_id")
        _require(athlete_id not in stars_by_id and athlete_id in internal_stars, "unknown-or-duplicate-public-star")
        source_row = internal_stars[athlete_id]
        _require(source_row.get("public_listing") == "UNKNOWN", "star-already-admitted-or-state-conflict")
        _require(admission.get("public_listing_review") == "ALLOWED_SCOPED_FACTUAL_PROFILE_LINK", "star-public-listing-not-reviewed")
        _require(admission.get("public_listing_scope") == "FACTUAL_NAME_STABLE_REGISTRY_ID_AND_OFFICIAL_PROFILE_LINK_ONLY_NO_PORTRAIT_OR_BIOGRAPHY", "overbroad-star-listing-scope")
        refs = admission.get("evidence_ids", [])
        _require(refs == ["wtt-profile-123980"] and all(ref in evidence_map for ref in refs), "missing-star-profile-evidence")
        star = copy.deepcopy(source_row)
        star["public_listing"] = "ALLOWED"
        star["public_listing_scope"] = admission["public_listing_scope"]
        # Keep only the explicit identity/profile evidence reviewed for this public projection.
        star["name_zh"] = None
        star["association"] = None
        star["evidence_source_ids"] = sorted(set(refs))
        stars_by_id[athlete_id] = star

    candidate_sources, candidate_audit_rows = _candidate_sources(fan, review, fan_evidence)
    all_sources = [*base["video_sources"], *admitted_match_sources, *candidate_sources]
    all_matches = [*base["matches"], *admitted_matches]
    _by_id(all_sources, "source_id", "duplicate-expanded-video-source-id")
    _by_id(all_matches, "match_id", "duplicate-expanded-match-id")
    source_ids = {row["source_id"] for row in all_sources}
    for match in all_matches:
        _require(all(source_id in source_ids for source_id in match.get("video_source_ids", [])), "match-refers-to-missing-source")
    for source in all_sources:
        if source["match_link_status"] == "HUMAN_VERIFIED":
            _require(source.get("canonical_match_id") in existing_match_ids | {row["match_id"] for row in admitted_matches}, "source-link-refers-to-missing-match")

    used_evidence = set()
    for match in base.get("matches", []):
        used_evidence.update(match.get("evidence_source_ids", []))
        used_evidence.update(match.get("rights", {}).get("evidence_source_ids", []))
    for source in base.get("video_sources", []):
        used_evidence.update(source.get("rights", {}).get("evidence_source_ids", []))
        used_evidence.update(row.get("source_id") for row in source.get("provenance", []) if isinstance(row, dict) and isinstance(row.get("source_id"), str))
    for star in base.get("stars", []):
        used_evidence.update(star.get("evidence_source_ids", []))
    for match in admitted_matches:
        used_evidence.update(match["evidence_source_ids"])
        used_evidence.update(match["rights"]["evidence_source_ids"])
    for source in admitted_match_sources + candidate_sources:
        used_evidence.update(source["rights"]["evidence_source_ids"])
        used_evidence.update(row["source_id"] for row in source["provenance"])
    for star in stars_by_id.values():
        if star["athlete_id"] == "athlete:123980":
            used_evidence.update(star.get("evidence_source_ids", []))
    _require(used_evidence <= set(evidence_map), "projected-evidence-reference-missing")

    manifest = []
    for key in ("base", "review", "internal", "fan"):
        path = paths[key]
        manifest.append({"file": path.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(path)})
    package = {
        "contract_version": LIBRARY_CONTRACT,
        "view": "STRICT_PUBLIC",
        "generated_at": generated_at,
        "source_manifest": manifest,
        "matches": all_matches,
        "video_sources": all_sources,
        "local_video_assets": [],
        "stars": list(stars_by_id.values()),
        "evidence_sources": [row for row in source_evidence if row["source_id"] in used_evidence or row["source_id"] in {
            evidence_id for admission in review["additional_match_admissions"] for evidence_id in admission["external_link_evidence_ids"]
        }],
        "rights_review_queue": [],
        "quality_summary": {
            "public_match_count": len(all_matches),
            "public_video_source_count": len(all_sources),
            "public_star_count": len(stars_by_id),
            "public_match_video_link_count": sum(len(row["video_source_ids"]) for row in all_matches),
            "event_level_highlight_source_count": len(candidate_sources),
            "current_session_playback_pass_count": 0,
            "official_embed_permission_count": 0,
            "thumbnail_display_permission_count": 0,
            "goal11_internal_video_source_count": len(internal.get("video_sources", [])),
            "goal14_highlight_candidate_review_count": len(fan.get("clips", [])),
            "goal14_candidate_exact_video_id_count": len(LINKABLE_HIGHLIGHT_IDS),
            "goal14_candidate_event_page_only_count": len(fan.get("clips", [])) - len(LINKABLE_HIGHLIGHT_IDS),
            "goal14_highlight_links_admitted": len(candidate_sources),
            "counts_notice": "The 20 Goal14 candidate review is separate from the 35 Goal11 internal source records; counts are not added or deduplicated across those independent catalogs.",
        },
        "analysis_compatibility": {
            "review_targets_version": "ptti.review-targets/0.1",
            "review_evidence_pack_version": "ptti.review-evidence-pack/0.1",
            "join_policy": "EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY",
            "automatic_join_by_title_or_player_name": False,
            "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
        },
        "notice": review["notice"] + " Strict-public inclusion authorizes only the stated factual metadata and official outbound link. Match identity links are limited to the two exact official event/video metadata cross-checks plus the previously admitted China Smash final. Event-level highlight sources have no match or athlete association. No visual playback, embed, thumbnail display, local analysis, download, or redistribution is asserted.",
    }
    audit = {
        "contract_version": AUDIT_CONTRACT,
        "view": "INTERNAL_REVIEW",
        "generated_at": generated_at,
        "source_manifest": manifest,
        "candidate_count": len(candidate_audit_rows),
        "decision_counts": {
            "PUBLIC_OFFICIAL_EXTERNAL_LINK_ONLY": sum(row["decision"] == "PUBLIC_OFFICIAL_EXTERNAL_LINK_ONLY" for row in candidate_audit_rows),
            "INTERNAL_ONLY_VIDEO_ID_UNRESOLVED": sum(row["decision"] == "INTERNAL_ONLY_VIDEO_ID_UNRESOLVED" for row in candidate_audit_rows),
        },
        "candidates": candidate_audit_rows,
        "notice": "This is an internal audit of the 20 existing candidate records, not a media license. The 10 admitted rows are official external links only; all candidate playback remains NOT_TESTED, embed and territory remain UNKNOWN, and unlinked items remain internal.",
    }
    return package, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-package", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--internal-index", type=Path, default=DEFAULT_INTERNAL)
    parser.add_argument("--fan-package", type=Path, default=DEFAULT_FAN)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", help="Optional fixed UTC timestamp for repeatable output")
    args = parser.parse_args()
    paths = {"base": args.base_package, "internal": args.internal_index, "fan": args.fan_package, "review": args.review}
    package, audit = build_expansion(
        _load(args.base_package), _load(args.internal_index), _load(args.fan_package), _load(args.review),
        args.generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"), paths,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    package_path = args.output_dir / "match-library-strict-public.json"
    audit_path = args.output_dir / "candidate-review-internal.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"STRICT_PUBLIC: matches={len(package['matches'])} video_sources={len(package['video_sources'])} stars={len(package['stars'])} match_video_links={package['quality_summary']['public_match_video_link_count']} playback_pass=0")
    print(f"CANDIDATES: total={audit['candidate_count']} exact_external_links={audit['decision_counts']['PUBLIC_OFFICIAL_EXTERNAL_LINK_ONLY']} event_page_only_internal={audit['decision_counts']['INTERNAL_ONLY_VIDEO_ID_UNRESOLVED']}")
    print(f"Wrote {package_path}")
    print(f"Wrote {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
