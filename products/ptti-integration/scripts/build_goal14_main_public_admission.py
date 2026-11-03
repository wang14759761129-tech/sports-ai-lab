#!/usr/bin/env python3
"""Build a minimal San-consumable strict-public package from explicit review."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
DEFAULT_INTERNAL = INTEGRATION_DIR / "generated" / "goal11-match-library" / "match-library-internal-review.json"
DEFAULT_ADMISSION = INTEGRATION_DIR / "fixtures" / "goal14-main-content-admission-v0.1.json"
DEFAULT_OUTPUT_DIR = INTEGRATION_DIR / "generated" / "goal14-main-admission"
CONTRACT = "ptti.match-library-index/0.1"
PERMISSION_VALUES = {"ALLOWED", "NOT_ALLOWED", "UNKNOWN"}


class AdmissionError(ValueError):
    """Raised when a curated public record lacks the explicit evidence scope."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdmissionError(f"{path.name} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise AdmissionError(code)


def _evidence_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_id = row.get("source_id")
        _need(isinstance(source_id, str) and source_id and source_id not in result, "duplicate-or-invalid-evidence-id")
        result[source_id] = row
    return result


def _validate_admission(internal: dict[str, Any], admission: dict[str, Any]) -> list[dict[str, Any]]:
    _need(internal.get("contract_version") == CONTRACT and internal.get("view") == "INTERNAL_REVIEW", "unsupported-internal-index")
    _need(admission.get("contract_version") == "ptti.main-content-admission/0.1", "unsupported-admission-version")
    _need(admission.get("scope") == "ONE_CURATED_PUBLIC_FACTS_AND_OFFICIAL_EXTERNAL_LINK", "unsupported-admission-scope")
    rows = admission.get("admissions")
    _need(isinstance(rows, list) and rows, "missing-admissions")
    evidence = _evidence_map(admission.get("evidence_sources", []))
    matches = {row.get("match_id"): row for row in internal.get("matches", [])}
    sources = {row.get("source_id"): row for row in internal.get("video_sources", [])}
    stars = {row.get("athlete_id"): row for row in internal.get("stars", [])}
    seen: set[tuple[str, str]] = set()

    for row in rows:
        _need(isinstance(row, dict), "invalid-admission-row")
        match_id, source_id = row.get("match_id"), row.get("source_id")
        _need(isinstance(match_id, str) and isinstance(source_id, str), "missing-match-or-source-id")
        _need((match_id, source_id) not in seen, "duplicate-admission-pair")
        seen.add((match_id, source_id))
        _need(match_id in matches and source_id in sources, "unknown-match-or-source-reference")
        match, source = matches[match_id], sources[source_id]
        facts, source_facts = row.get("match_facts"), row.get("source_facts")
        _need(isinstance(facts, dict) and isinstance(source_facts, dict), "missing-crosscheck-facts")
        _need(facts.get("event_name") == match.get("event", {}).get("name"), "event-name-mismatch")
        _need(facts.get("event_id") == match.get("event", {}).get("event_id"), "event-id-mismatch")
        _need(facts.get("round") == match.get("round"), "match-round-mismatch")
        _need(facts.get("recorded_result") == match.get("recorded_result"), "match-result-mismatch")
        expected_participants = {item.get("athlete_id") for item in facts.get("participants", [])}
        actual_participants = {item.get("athlete_id") for item in match.get("participants", [])}
        _need(expected_participants == actual_participants and None not in expected_participants, "match-participant-mismatch")
        athlete_ids = row.get("athlete_ids")
        _need(isinstance(athlete_ids, list) and set(athlete_ids) == expected_participants, "star-match-identity-mismatch")
        _need(all(athlete_id in stars for athlete_id in athlete_ids), "unknown-athlete-reference")

        _need(source_facts.get("video_id") == source.get("video_id"), "video-id-mismatch")
        _need(source_facts.get("official_url") == source.get("official_url"), "video-url-mismatch")
        _need(source_facts.get("original_title") == source.get("original_title"), "official-title-mismatch")
        _need(source_facts.get("event") == facts.get("event_name"), "source-event-mismatch")
        _need(source_facts.get("match_type") == "MS" and facts.get("match_type") == "MS", "match-discipline-mismatch")
        _need(source_facts.get("round") == facts.get("round"), "source-round-mismatch")
        _need(source_facts.get("publisher") == "World Table Tennis", "unexpected-video-publisher")
        _need(source_facts.get("source_identity_status") == "VERIFIED", "source-identity-not-verified")
        _need(source_facts.get("source_identity_evidence_scope") == "OFFICIAL_VIDEO_METADATA_ONLY_NOT_VISUAL_PLAYBACK", "source-identity-scope-missing")
        _need(source_facts.get("publisher_identity_status") == "VERIFIED", "publisher-not-verified")
        _need(source_facts.get("completeness_status") == "UNVERIFIED", "unearned-completeness-upgrade")

        relation_evidence = row.get("relationship_evidence_ids")
        _need(isinstance(relation_evidence, list) and len(relation_evidence) >= 2, "missing-direct-match-link-evidence")
        _need(all(item in evidence for item in relation_evidence), "unknown-match-link-evidence")
        _need(any("EVENT_RESULT" in evidence[item].get("source_type", "") for item in relation_evidence), "missing-official-match-result-source")
        _need(any("YOUTUBE_VIDEO_METADATA" in evidence[item].get("source_type", "") for item in relation_evidence), "missing-exact-video-metadata-source")

        listing = row.get("public_listing_basis")
        external = row.get("external_viewing_basis")
        _need(isinstance(listing, dict) and listing.get("status") == "ALLOWED", "public-listing-not-approved")
        _need(listing.get("scope") == "FACTUAL_NAMES_EVENT_MATCH_SUMMARY_AND_SOURCE_ATTRIBUTION_ONLY", "overbroad-public-listing-scope")
        _need(isinstance(external, dict) and external.get("status") == "ALLOWED", "external-link-not-approved")
        _need(external.get("scope") == "OFFICIAL_YOUTUBE_SHARE_URL_ONLY", "overbroad-external-link-scope")
        for field, block_value in ((listing, "evidence_ids"), (external, "evidence_ids")):
            refs = field.get(block_value)
            _need(isinstance(refs, list) and refs and all(ref in evidence for ref in refs), "missing-permission-basis-evidence")
        listing_types = {evidence[ref].get("source_type", "") for ref in listing["evidence_ids"]}
        _need("OFFICIAL_WTT_EVENT_RESULT" in listing_types, "public-match-facts-not-sourced")
        _need(sum("OFFICIAL_WTT_PLAYER_PROFILE_REFERENCE" in evidence[ref].get("source_type", "") for ref in listing["evidence_ids"]) >= 2, "public-athlete-facts-not-sourced")
        external_types = {evidence[ref].get("source_type", "") for ref in external["evidence_ids"]}
        _need("OFFICIAL_YOUTUBE_VIDEO_METADATA" in external_types, "official-watch-source-not-sourced")
        _need("PLATFORM_LINK_SHARING_GUIDANCE" in external_types, "external-link-sharing-basis-missing")
        rights = row.get("media_rights")
        _need(isinstance(rights, dict), "missing-media-rights")
        _need(rights.get("embedding") in {"UNKNOWN", "NOT_ALLOWED"}, "embedding-needs-explicit-grant")
        _need(rights.get("thumbnail_display") in {"UNKNOWN", "NOT_ALLOWED_WITHOUT_PRIOR_APPROVAL"}, "thumbnail-needs-explicit-grant")
        _need(rights.get("local_analysis") == "NOT_GRANTED", "local-analysis-not-granted")
        _need(rights.get("download") == "NOT_GRANTED" and rights.get("redistribution") == "NOT_GRANTED", "media-reuse-not-granted")
        availability = row.get("availability")
        _need(isinstance(availability, dict), "missing-availability-status")
        _need(availability.get("external_video_visual_latest_recorded") == "NOT_TESTED", "unverified-playback-upgrade")
        _need(availability.get("territory_availability") == "UNKNOWN", "unverified-territory-upgrade")
        _need(availability.get("desktop_native_playback") == "NOT_TESTED" and availability.get("vision_analysis") == "NOT_TESTED", "non-web-evidence-upgrade")

    return rows


def build_public_index(
    internal: dict[str, Any],
    admission: dict[str, Any],
    generated_at: str,
    internal_path: Path = DEFAULT_INTERNAL,
    admission_path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    admissions = _validate_admission(internal, admission)
    internal_matches = {row["match_id"]: row for row in internal["matches"]}
    internal_sources = {row["source_id"]: row for row in internal["video_sources"]}
    internal_stars = {row["athlete_id"]: row for row in internal["stars"]}
    output_matches: list[dict[str, Any]] = []
    output_sources: list[dict[str, Any]] = []
    output_stars: dict[str, dict[str, Any]] = {}

    for item in admissions:
        match = json.loads(json.dumps(internal_matches[item["match_id"]]))
        source = json.loads(json.dumps(internal_sources[item["source_id"]]))
        facts, sf = item["match_facts"], item["source_facts"]
        evidence_ids = sorted(set(item["relationship_evidence_ids"] + item["public_listing_basis"]["evidence_ids"]))

        match["match_type"] = facts["match_type"]
        match["round"] = facts["round"]
        match["recorded_result"] = facts["recorded_result"]
        match["result_status"] = facts["result_status"]
        match["reference_url"] = "https://www.worldtabletennis.com/eventInfo?eventId=3098"
        match["evidence_source_ids"] = sorted(set(match["evidence_source_ids"] + evidence_ids))
        match["video_source_ids"] = [item["source_id"]]
        match["match_video_link_status"] = "HUMAN_VERIFIED"
        match["rights"] = {
            "public_listing": "ALLOWED",
            "evidence_status": "SCOPED_FACTUAL_METADATA_ONLY",
            "scope": item["public_listing_basis"]["scope"],
            "evidence_source_ids": item["public_listing_basis"]["evidence_ids"],
        }

        source.update({
            "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
            "title": sf["display_title"],
            "original_title": sf["original_title"],
            "event": sf["event"],
            "event_year": sf["event_year"],
            "match_type": sf["match_type"],
            "round": sf["round"],
            "participants_claimed": sf["participants_claimed"],
            "publisher": sf["publisher"],
            "publisher_url": sf["publisher_url"],
            "source_verified_at": admission["evaluated_at"],
            "publisher_identity_status": sf["publisher_identity_status"],
            "source_identity_status": sf["source_identity_status"],
            "source_identity_evidence_scope": sf["source_identity_evidence_scope"],
            "canonical_match_id": item["match_id"],
            "match_link_status": "HUMAN_VERIFIED",
            "content_type_claim": sf["content_type_claim"],
            "completeness_status": sf["completeness_status"],
            "permission_status_recorded": "SCOPED_PUBLIC_METADATA_AND_EXTERNAL_LINK_ONLY",
            "rights": {
                "public_listing": "ALLOWED",
                "external_viewing": "ALLOWED",
                "thumbnail_display": "NOT_ALLOWED",
                "embedding": item["media_rights"]["embedding"],
                "local_analysis": "NOT_GRANTED",
                "redistribution": "NOT_GRANTED",
                "evidence_status": "SCOPED_EXTERNAL_LINK_ONLY_NO_MEDIA_USE_GRANT",
                "scope": item["external_viewing_basis"]["scope"],
                "evidence_source_ids": item["external_viewing_basis"]["evidence_ids"],
            },
            "thumbnail": {"url": None, "source_has_thumbnail_url": True, "display_status": "NOT_DISPLAYED_PRIOR_APPROVAL_REQUIRED"},
            "availability": {
                "official_page_current": "NOT_TESTED",
                "external_video_visual_latest_recorded": "NOT_TESTED",
                "external_observations": [{
                    "surface": "OFFICIAL_YOUTUBE_METADATA",
                    "checked_at": admission["evaluated_at"],
                    "page_accessible": None,
                    "visual_playback": "NOT_TESTED",
                    "observed_result": "Exact official metadata observed; no video frames or current playback verified.",
                    "limitations": "Metadata and outbound URL only; current access and territory are unknown.",
                }],
                "platform_embed": {
                    "permission": item["media_rights"]["embedding"],
                    "latest_recorded_technical_status": item["availability"]["platform_embed_technical_status"],
                    "historical_attempts": [{"result": "FAILED", "error_code": 150, "date": "2026-10-09", "status": "HISTORICAL_ONLY"}],
                },
                "desktop_native_playback": "NOT_TESTED",
                "vision_analysis": "NOT_TESTED",
                "current_session_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
                "latest_recorded_playback_status": item["availability"]["latest_recorded_playback_status"],
                "territory_availability": "UNKNOWN",
                "recorded_region_restriction": "UNKNOWN",
            },
            "provenance": [{
                "snapshot": "goal14-main-content-admission-v0.1.json",
                "recorded_at": admission["evaluated_at"],
                "metadata_method": "MANUAL_OFFICIAL_SOURCE_CROSSCHECK",
                "publisher_url": sf["publisher_url"],
                "event_evidence": item["relationship_evidence_ids"][0],
                "match_link_evidence": item["relationship_evidence_ids"],
                "source_rights_scope": item["external_viewing_basis"]["scope"],
                "source_notice": "Official platform link only. No thumbnail, embed, analysis, download, or redistribution grant recorded.",
                "playback_status_recorded": "NOT_TESTED",
            }],
        })
        output_matches.append(match)
        output_sources.append(source)

        for athlete_id in item["athlete_ids"]:
            star = json.loads(json.dumps(internal_stars[athlete_id]))
            star["public_listing"] = "ALLOWED"
            star["public_listing_scope"] = "FACTUAL_NAME_STABLE_ID_AND_OFFICIAL_PROFILE_LINK_ONLY_NO_PORTRAIT_OR_BIOGRAPHY"
            star["evidence_source_ids"] = sorted(set(star["evidence_source_ids"] + item["public_listing_basis"]["evidence_ids"]))
            output_stars[athlete_id] = star

    evidence_ids = set()
    for row in admissions:
        evidence_ids.update(row["relationship_evidence_ids"])
        evidence_ids.update(row["public_listing_basis"]["evidence_ids"])
        evidence_ids.update(row["external_viewing_basis"]["evidence_ids"])
    evidence_sources = [row for row in admission["evidence_sources"] if row["source_id"] in evidence_ids]
    _need({row["source_id"] for row in evidence_sources} == evidence_ids, "missing-projected-evidence-source")

    return {
        "contract_version": CONTRACT,
        "view": "STRICT_PUBLIC",
        "generated_at": generated_at,
        "source_manifest": [
            {"file": internal_path.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(internal_path)},
            {"file": admission_path.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(admission_path)},
        ],
        "matches": output_matches,
        "video_sources": output_sources,
        "local_video_assets": [],
        "stars": list(output_stars.values()),
        "evidence_sources": evidence_sources,
        "rights_review_queue": [],
        "quality_summary": {
            "public_match_count": len(output_matches),
            "public_video_source_count": len(output_sources),
            "public_star_count": len(output_stars),
            "public_match_video_link_count": len(output_sources),
            "current_session_playback_pass_count": 0,
            "official_embed_permission_count": 0,
            "thumbnail_display_permission_count": 0,
            "total_internal_video_sources_reviewed": len(internal["video_sources"]),
            "excluded_reference_only_records": len(internal["video_sources"]) - len(output_sources),
            "excluded_match_records": len(internal["matches"]) - len(output_matches),
            "excluded_athlete_profiles": len(internal["stars"]) - len(output_stars),
            "excluded_reason": "All other internal records lack an equivalent scoped public-facts/external-link review; no rights are inherited between records.",
        },
        "analysis_compatibility": {
            "review_targets_version": "ptti.review-targets/0.1",
            "review_evidence_pack_version": "ptti.review-evidence-pack/0.1",
            "join_policy": "EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY",
            "automatic_join_by_title_or_player_name": False,
            "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
        },
        "notice": admission["notice"] + " The record is a public factual index and official external watch link only. The video is not embedded or redistributed. Current access, region, playback, completeness, Desktop Native playback, and Vision analysis remain unverified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--internal-index", type=Path, default=DEFAULT_INTERNAL)
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--generated-at", help="Optional fixed UTC timestamp for repeatable output")
    args = parser.parse_args()
    internal = _load(args.internal_index)
    admission = _load(args.admission)
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = build_public_index(internal, admission, generated_at, args.internal_index, args.admission)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "match-library-strict-public.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"STRICT_PUBLIC: {len(payload['matches'])} match, {len(payload['video_sources'])} source, {len(payload['stars'])} stars, {payload['quality_summary']['current_session_playback_pass_count']} playback pass")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
