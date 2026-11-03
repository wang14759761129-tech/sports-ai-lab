"""Project a tiny, explicitly reviewed internal Cinema shortlist.

This adapter consumes the committed internal Match Library index only. It does
not join videos to matches, grant rights, fetch metadata, or create a public
fallback. Live observations are supplied as a small auditable input fixture.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONTRACT_VERSION = "ptti.cinema-curated-sources/0.1"
INPUT_VERSION = "ptti.cinema-curation-observations/0.1"
INDEX_VERSION = "ptti.match-library-index/0.1"


class CurationError(ValueError):
    """Raised when the curation source or observation input is unsafe."""


def _event_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CurationError("event_identity_evidence must be an object")
    if set(value) - {"status", "reference_url", "note"}:
        raise CurationError("event_identity_evidence contains unsupported claims")
    status = value.get("status")
    allowed = {
        "REGISTERED_EVENT_AND_PAIR_CANDIDATE_NOT_LINKED_TO_VIDEO_ID",
        "OFFICIAL_EVENT_REPORT_CORROBORATES_EVENT_AND_PAIR_NOT_VIDEO_ID",
        "SOURCE_METADATA_CLAIM_ONLY",
    }
    if status not in allowed:
        raise CurationError("event_identity_evidence status is unsupported")
    reference_url = value.get("reference_url")
    if reference_url is not None:
        if not isinstance(reference_url, str):
            raise CurationError("event_identity_evidence reference_url must be HTTPS or null")
        parsed = urlsplit(reference_url)
        if parsed.scheme != "https" or parsed.hostname not in {"worldtabletennis.com", "www.worldtabletennis.com", "ittf.com", "www.ittf.com"}:
            raise CurationError("event_identity_evidence reference_url must use an official WTT/ITTF host")
    note = value.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 600):
        raise CurationError("event_identity_evidence note must be a short string")
    return {"status": status, "reference_url": reference_url, **({"note": note} if note is not None else {})}


def _parse_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CurationError(f"{field} must be an ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurationError(f"{field} must be an ISO-8601 timestamp") from exc
    return value


def build_curated_sources(
    index: dict[str, Any],
    observations: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build an internal-only list; rights and match links are copied fail-closed."""
    if index.get("contract_version") != INDEX_VERSION:
        raise CurationError("Unsupported match-library index version")
    if index.get("view") != "INTERNAL_REVIEW":
        raise CurationError("Only INTERNAL_REVIEW may feed this private shortlist")
    if observations.get("contract_version") != INPUT_VERSION:
        raise CurationError("Unsupported curation observation version")
    if observations.get("audience") != "INTERNAL_REVIEW_ONLY":
        raise CurationError("Curation observations must be internal-review-only")

    selected = observations.get("selected_sources")
    if not isinstance(selected, list) or not selected:
        raise CurationError("selected_sources must be a non-empty list")
    source_ids = [row.get("source_id") if isinstance(row, dict) else None for row in selected]
    if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
        raise CurationError("Each selection must identify a source_id")
    if len(source_ids) != len(set(source_ids)):
        raise CurationError("Duplicate source_id in curation selection")
    if len(selected) > 3:
        raise CurationError("The Cinema featured shortlist is limited to three sources")

    indexed = {row.get("source_id"): row for row in index.get("video_sources", [])}
    out: list[dict[str, Any]] = []
    for selection in selected:
        source_id = selection["source_id"]
        source = indexed.get(source_id)
        if source is None:
            raise CurationError(f"Unknown source_id: {source_id}")

        # Deliberately ignore no supplied rights or link claims: reject them.
        forbidden = {"rights", "canonical_match_id", "match_id", "match_link_status", "thumbnail_url"}
        if forbidden.intersection(selection):
            raise CurationError(f"Selection cannot override protected fields for {source_id}")

        check = selection.get("publisher_check", {})
        if not isinstance(check, dict):
            raise CurationError(f"publisher_check must be an object for {source_id}")
        observed_at = _parse_timestamp(selection.get("checked_at"), f"{source_id}.checked_at")
        page_status = selection.get("official_page_http_status")
        if not isinstance(page_status, int) or not 100 <= page_status <= 599:
            raise CurationError(f"official_page_http_status must be an HTTP status for {source_id}")

        if (check.get("method") == "YOUTUBE_OEMBED_SINGLE_LOOKUP"
                and check.get("result") == "METADATA_MATCHED_RECORDED_PUBLISHER"
                and check.get("author_name") == source.get("publisher")
                and check.get("author_url") == source.get("publisher_url")):
            publisher_status = "METADATA_MATCHED_RECORDED_PUBLISHER_AFFILIATION_NOT_INDEPENDENTLY_VERIFIED"
        elif check.get("method") == "YOUTUBE_OEMBED_SINGLE_LOOKUP":
            publisher_status = "PUBLISHER_METADATA_MISMATCH_REVIEW_REQUIRED"
        else:
            publisher_status = "NOT_TESTED"

        current_page = "HTTP_200" if page_status == 200 else "HTTP_NON_200_REVIEW_REQUIRED"
        historical_embed = source.get("availability", {}).get("platform_embed", {})
        event_evidence = _event_evidence(selection.get("event_identity_evidence", {
            "status": "SOURCE_METADATA_CLAIM_ONLY",
            "reference_url": None,
        }))
        out.append({
            "source_id": source_id,
            "catalog_record_id": source["catalog_record_id"],
            "platform": source["platform"],
            "video_id": source["video_id"],
            "official_url": source["official_url"],
            "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
            "title": source["title"],
            "original_title_claim": source.get("original_title"),
            "event_claim": source.get("event"),
            "event_year_claim": source.get("event_year"),
            "discipline_claim": source.get("match_type", "UNKNOWN"),
            "round_claim": source.get("round", "UNKNOWN"),
            "participants_claimed": source.get("participants_claimed"),
            "source_identity_status": source.get("source_identity_status", "UNKNOWN"),
            "publisher_check": {
                "status": publisher_status,
                "method": check.get("method", "NOT_TESTED"),
                "checked_at": observed_at,
                "affiliation_status": "NOT_INDEPENDENTLY_VERIFIED",
            },
            "event_identity_evidence": event_evidence,
            "match_link": {
                "canonical_match_id": source.get("canonical_match_id"),
                "status": source.get("match_link_status", "UNKNOWN"),
                "policy": "NO_JOIN_BY_TITLE_EVENT_OR_PLAYER_NAME",
            },
            "external_watch": {
                "action": "OPEN_OFFICIAL_PLATFORM_URL",
                "http_head_status": current_page,
                "checked_at": observed_at,
                "actual_video_playback": "NOT_TESTED",
                "viewing_rights": source.get("rights", {}).get("external_viewing", "UNKNOWN"),
                "territory": source.get("availability", {}).get("territory_availability", "UNKNOWN"),
            },
            "content_claim": source.get("content_type_claim", "UNKNOWN"),
            "completeness": source.get("completeness_status", "UNVERIFIED"),
            "rights": source.get("rights", {}),
            "thumbnail": {
                "url": None,
                "display_permission": source.get("rights", {}).get("thumbnail_display", "UNKNOWN"),
                "presentation": "PTTI_BRAND_PLACEHOLDER_ONLY",
            },
            "availability": {
                "current_official_page": current_page,
                "current_external_visual_playback": "NOT_TESTED",
                "embedding_permission": source.get("rights", {}).get("embedding", "UNKNOWN"),
                "latest_recorded_embed_technical_status": historical_embed.get("latest_recorded_technical_status", "NOT_TESTED"),
                "desktop_native_playback": source.get("availability", {}).get("desktop_native_playback", "NOT_TESTED"),
                "vision_analysis": source.get("availability", {}).get("vision_analysis", "NOT_TESTED"),
                "current_session_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
            },
            "audience_status": "INTERNAL_REFERENCE_ONLY",
            "public_listing": source.get("rights", {}).get("public_listing", "UNKNOWN"),
        })

    timestamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _parse_timestamp(timestamp, "generated_at")
    return {
        "contract_version": CONTRACT_VERSION,
        "source_contract_version": INDEX_VERSION,
        "audience": "INTERNAL_REVIEW_ONLY",
        "generated_at": timestamp,
        "selection_method": "EXPLICIT_SOURCE_ID_ALLOWLIST",
        "strict_public_fallback": False,
        "notice": (
            "Reference-only review data. A reachable URL is not playback, a rights grant, "
            "a verified complete match, or a canonical Match link. Strict-public remains separate."
        ),
        "featured_sources": out,
    }


def write_curated_sources(
    index_path: Path,
    observations_path: Path,
    output_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    try:
        index = json.loads(index_path.read_text(encoding="utf-8-sig"))
        observations = json.loads(observations_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurationError(f"Cannot read input JSON: {exc}") from exc
    result = build_curated_sources(index, observations, generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
