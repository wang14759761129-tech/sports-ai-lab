"""Build a private, evidence-backed review of selected Cinema video sources.

The output is a companion review view. It never changes the stable match-library,
Review Targets, or Evidence Pack contracts, and never grants rights or binds a
VideoSource to a Match automatically.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


OUTPUT_VERSION = "ptti.cinema-source-review/0.1"
INPUT_VERSION = "ptti.cinema-source-review-input/0.1"
INDEX_VERSION = "ptti.match-library-index/0.1"
OFFICIAL_HOSTS = {
    "worldtabletennis.com", "www.worldtabletennis.com",
    "china-smash.com", "www.china-smash.com",
    "ittf.com", "www.ittf.com",
    "singaporesmash.com", "www.singaporesmash.com",
}
SECONDARY_HOSTS = {"mewatch.sg", "www.mewatch.sg"}
RIGHTS_FIELDS = (
    "public_listing", "external_viewing", "thumbnail_display", "embedding",
    "local_analysis", "redistribution",
)


class SourceReviewError(ValueError):
    """Raised when a source review cannot be safely projected."""


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceReviewError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceReviewError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise SourceReviewError(f"{field} must include a timezone")
    return value


def _https_reference(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != {"role", "url", "claims"}:
        raise SourceReviewError(f"evidence_sources[{index}] has unsupported shape")
    role, url, claims = row["role"], row["url"], row["claims"]
    if not isinstance(url, str):
        raise SourceReviewError(f"evidence_sources[{index}].url must be HTTPS")
    parsed = urlsplit(url)
    allowed_hosts = OFFICIAL_HOSTS if role in {"OFFICIAL_MATCH_RESULT", "OFFICIAL_EVENT_INFO"} else SECONDARY_HOSTS if role == "SECONDARY_STREAMING_CATALOG" else set()
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise SourceReviewError(f"evidence_sources[{index}] host is not allowed for its evidence role")
    if not isinstance(claims, list) or not claims or any(not isinstance(item, str) for item in claims):
        raise SourceReviewError(f"evidence_sources[{index}].claims must be a non-empty string list")
    return {"role": role, "url": url, "claims": claims}


def _normalize_match_date(date_review: Any, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(date_review, dict) or set(date_review) != {"value", "status", "local_start_time"}:
        raise SourceReviewError("match_date must contain value, status, and local_start_time")
    value, status, local_time = date_review["value"], date_review["status"], date_review["local_start_time"]
    allowed = {"OFFICIAL_REPORT_DATE", "SECONDARY_CATALOG_ONLY", "UNKNOWN"}
    if status not in allowed:
        raise SourceReviewError("match_date status is unsupported")
    if value is not None:
        if not isinstance(value, str):
            raise SourceReviewError("match_date.value must be an ISO date or null")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise SourceReviewError("match_date.value must be an ISO date or null") from exc
    if local_time is not None:
        raise SourceReviewError("exact local start times are not verified in this review; keep null")
    if (status == "UNKNOWN") != (value is None):
        raise SourceReviewError("UNKNOWN match date must be null; evidenced dates require a date")
    roles = {row["role"] for row in evidence}
    if status == "OFFICIAL_REPORT_DATE" and "OFFICIAL_MATCH_RESULT" not in roles:
        raise SourceReviewError("official match date requires an official match result reference")
    if status == "SECONDARY_CATALOG_ONLY" and "SECONDARY_STREAMING_CATALOG" not in roles:
        raise SourceReviewError("secondary match date requires a secondary catalog reference")
    return {"value": value, "status": status, "local_start_time": None}


def build_source_review(index: dict[str, Any], observations: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    if index.get("contract_version") != INDEX_VERSION or index.get("view") != "INTERNAL_REVIEW":
        raise SourceReviewError("Only ptti.match-library-index/0.1 INTERNAL_REVIEW input is accepted")
    if observations.get("contract_version") != INPUT_VERSION or observations.get("audience") != "INTERNAL_REVIEW_ONLY":
        raise SourceReviewError("Unsupported or non-private source-review input")
    selections = observations.get("sources")
    if not isinstance(selections, list) or not 1 <= len(selections) <= 3:
        raise SourceReviewError("sources must contain between 1 and 3 reviewed records")
    ids = [row.get("source_id") if isinstance(row, dict) else None for row in selections]
    if any(not isinstance(value, str) or not value for value in ids):
        raise SourceReviewError("each reviewed record must have a source_id")
    if len(ids) != len(set(ids)):
        raise SourceReviewError("duplicate source_id")

    indexed = {row.get("source_id"): row for row in index.get("video_sources", [])}
    match_ids = {row.get("match_id") for row in index.get("matches", [])}
    output_sources: list[dict[str, Any]] = []
    for i, row in enumerate(selections):
        source_id = row["source_id"]
        source = indexed.get(source_id)
        if source is None:
            raise SourceReviewError(f"unknown source_id: {source_id}")
        forbidden = {"rights", "canonical_match_id", "match_id", "thumbnail_url", "playback_pass", "vision_pass"}
        if forbidden.intersection(row):
            raise SourceReviewError(f"source review cannot override rights, links, or playback evidence for {source_id}")
        if source.get("platform") != "YOUTUBE":
            raise SourceReviewError(f"this review adapter only accepts the selected YouTube records: {source_id}")
        video_id = source.get("video_id")
        expected_url = f"https://www.youtube.com/watch?v={video_id}"
        if source.get("official_url") != expected_url:
            raise SourceReviewError(f"source URL does not match video_id: {source_id}")

        metadata = row.get("source_metadata")
        if not isinstance(metadata, dict) or set(metadata) != {"method", "checked_at", "title", "author_name", "author_url"}:
            raise SourceReviewError(f"source_metadata[{source_id}] has unsupported shape")
        _timestamp(metadata.get("checked_at"), f"{source_id}.source_metadata.checked_at")
        if metadata.get("method") != "YOUTUBE_OEMBED_SINGLE_LOOKUP":
            raise SourceReviewError("source publisher metadata must come from a single official oEmbed lookup")
        if metadata.get("title") != source.get("original_title"):
            raise SourceReviewError(f"fresh publisher title does not exactly match stored title for {source_id}")
        if metadata.get("author_name") != source.get("publisher") or metadata.get("author_url") != source.get("publisher_url"):
            raise SourceReviewError(f"fresh publisher identity does not match stored metadata for {source_id}")
        if metadata.get("author_url") != "https://www.youtube.com/@wttglobal":
            raise SourceReviewError("unexpected publisher URL")

        page_probe = row.get("page_probe")
        if not isinstance(page_probe, dict) or set(page_probe) != {"method", "checked_at", "http_status"}:
            raise SourceReviewError(f"page_probe[{source_id}] has unsupported shape")
        _timestamp(page_probe.get("checked_at"), f"{source_id}.page_probe.checked_at")
        if (page_probe.get("method") != "HTTP_HEAD" or not isinstance(page_probe.get("http_status"), int)
                or not 100 <= page_probe["http_status"] <= 599):
            raise SourceReviewError(f"page_probe[{source_id}] must record a numeric HTTP_HEAD result")

        event = row.get("event_match_review")
        required_event = {"event_name", "event_year", "discipline", "round", "participants", "status", "match_date", "event_window", "evidence_sources", "video_id_explicitly_referenced"}
        if not isinstance(event, dict) or set(event) != required_event:
            raise SourceReviewError(f"event_match_review[{source_id}] has unsupported shape")
        if not isinstance(event["event_name"], str) or not event["event_name"]:
            raise SourceReviewError("event_name must be a non-empty evidenced claim")
        if not isinstance(event["event_year"], int) or not 1900 <= event["event_year"] <= 2100:
            raise SourceReviewError("event_year must be a reviewed year")
        if event["discipline"] not in {"MS", "WS", "MD", "WD", "XD"}:
            raise SourceReviewError("discipline must be a known match type")
        if not isinstance(event["round"], str) or not event["round"].strip() or not isinstance(event["participants"], list) or len(event["participants"]) not in {2, 4}:
            raise SourceReviewError("round and participant claims are incomplete")
        if not isinstance(event["status"], str) or not event["status"].strip():
            raise SourceReviewError("event claim status must be explicit")
        if any(not isinstance(name, str) or not name for name in event["participants"]):
            raise SourceReviewError("participants must be explicit non-empty names")
        if event["video_id_explicitly_referenced"] is not False:
            raise SourceReviewError("no reviewed official event record explicitly references this video_id")
        evidence = event["evidence_sources"]
        if not isinstance(evidence, list) or not evidence:
            raise SourceReviewError("each match claim requires supporting evidence")
        evidence = [_https_reference(item, j) for j, item in enumerate(evidence)]
        match_date = _normalize_match_date(event["match_date"], evidence)
        if match_date["value"] and int(match_date["value"][:4]) != event["event_year"]:
            raise SourceReviewError("match date year does not match the reviewed event year")
        event_window = event["event_window"]
        if event_window is not None:
            if not isinstance(event_window, dict) or set(event_window) != {"start", "end", "status"}:
                raise SourceReviewError("event_window has unsupported shape")
            if event_window["status"] != "OFFICIAL_EVENT_INFO":
                raise SourceReviewError("event_window must preserve evidence source status")
            try:
                window_start = datetime.strptime(event_window["start"], "%Y-%m-%d").date()
                window_end = datetime.strptime(event_window["end"], "%Y-%m-%d").date()
            except (TypeError, ValueError) as exc:
                raise SourceReviewError("event_window dates must be ISO dates") from exc
            if window_start > window_end:
                raise SourceReviewError("event_window start must not follow end")
            if match_date["value"]:
                match_day = datetime.strptime(match_date["value"], "%Y-%m-%d").date()
                if not window_start <= match_day <= window_end:
                    raise SourceReviewError("match date must fall within the evidenced event window")
            roles = {item["role"] for item in evidence}
            if "OFFICIAL_EVENT_INFO" not in roles:
                raise SourceReviewError("official event window requires official event information")

        candidate = row.get("unlinked_match_review_candidate")
        if candidate is not None and candidate not in match_ids:
            raise SourceReviewError(f"unknown internal Match review candidate: {candidate}")
        rights_in = source.get("rights", {})
        rights = {key: rights_in.get(key, "UNKNOWN") for key in RIGHTS_FIELDS}
        if any(value not in {"ALLOWED", "NOT_ALLOWED", "NOT_GRANTED", "UNKNOWN"} for value in rights.values()):
            raise SourceReviewError(f"invalid rights value in source snapshot: {source_id}")
        if rights["public_listing"] == "ALLOWED":
            raise SourceReviewError("selected source snapshot unexpectedly grants public listing; review policy before projection")

        historical_embed = source.get("availability", {}).get("platform_embed", {}).get("latest_recorded_technical_status", "NOT_TESTED")
        if page_probe["http_status"] == 200:
            page_status = "HTTP_200_PAGE_ONLY"
        else:
            page_status = "HTTP_NON_200_REVIEW_REQUIRED"
        output_sources.append({
            "source_id": source_id,
            "catalog_record_id": source["catalog_record_id"],
            "video_id": video_id,
            "platform": "YOUTUBE",
            "original_source_url": expected_url,
            "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
            "publisher_metadata": {
                "method": metadata["method"],
                "checked_at": metadata["checked_at"],
                "title": metadata["title"],
                "author_name": metadata["author_name"],
                "author_url": metadata["author_url"],
                "status": "MATCHES_SNAPSHOT_METADATA_AFFILIATION_AND_RIGHTS_SCOPE_NOT_PROVEN",
            },
            "match_claim": {
                "event_name": event["event_name"],
                "event_year": event["event_year"],
                "discipline": event["discipline"],
                "round": event["round"],
                "participants": event["participants"],
                "status": event["status"],
                "match_date": match_date,
                "event_window": event_window,
                "evidence_sources": evidence,
                "official_source_references_video_id": False,
            },
            "match_link": {
                "canonical_match_id": None,
                "status": "UNKNOWN",
                "unlinked_review_candidate_match_id": candidate,
                "reason": "No official match source directly references this exact video_id and no visual watch-session verified the video content.",
                "join_policy": "EXACT_EVIDENCE_REQUIRED_NO_AUTOMATIC_JOIN_BY_TITLE_EVENT_OR_PLAYER_NAME",
            },
            "watch_status": {
                "official_page_request": page_status,
                "page_checked_at": page_probe["checked_at"],
                "external_visual_video_playback": "NOT_TESTED",
                "external_viewing_rights": rights["external_viewing"],
                "territory_status": source.get("availability", {}).get("territory_availability", "UNKNOWN"),
                "login_or_region_check": "NOT_TESTED",
                "in_app_embedding_permission": rights["embedding"],
                "latest_recorded_embed_technical_status": historical_embed,
                "in_app_entry": "EXTERNAL_ONLY_PERMISSION_UNVERIFIED",
                "unavailability_or_limit_reason": (
                    "Historical embed attempt returned error 150; current external visual playback and embed status were not tested."
                    if historical_embed == "BLOCKED_OBSERVED"
                    else "No embed permission evidence and no current visual playback test; keep the direct official link as an external-only action."
                ),
            },
            "content_claim": {
                "publisher_title_claim": source.get("content_type_claim", "UNKNOWN"),
                "completeness": source.get("completeness_status", "UNVERIFIED"),
                "completeness_status": "UNVERIFIED_TITLE_IS_NOT_COMPLETENESS_EVIDENCE",
            },
            "rights": rights,
            "thumbnail": {"url": None, "display_permission": rights["thumbnail_display"], "presentation": "PTTI_BRAND_PLACEHOLDER_ONLY"},
            "audience": "INTERNAL_REVIEW_ONLY",
            "next_evidence_needed": [
                "DIRECT_OFFICIAL_VIDEO_ID_TO_MATCH_REFERENCE",
                "HUMAN_WATCH_SESSION_VISUAL_CONTENT_CHECK",
                "SCOPED_RIGHTS_EVIDENCE_FOR_EACH_USE",
                "TERRITORY_AND_LOGIN_CHECK",
                "FULL_MATCH_COMPLETENESS_CHECK",
            ],
        })

    gen = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _timestamp(gen, "generated_at")
    quality = index.get("quality_summary", {})
    if quality.get("public_eligible", {}).get("video_sources") != 0:
        raise SourceReviewError("strict-public projection must remain empty for this review")
    return {
        "contract_version": OUTPUT_VERSION,
        "source_contract_version": INDEX_VERSION,
        "input_contract_version": INPUT_VERSION,
        "audience": "INTERNAL_REVIEW_ONLY",
        "generated_at": gen,
        "catalog_snapshot": {
            "unique_video_sources": quality.get("unique_video_sources"),
            "registered_match_records": quality.get("registered_match_records"),
            "canonical_video_match_links": quality.get("catalog_video_match_links"),
            "strict_public_video_source_count": quality.get("public_eligible", {}).get("video_sources"),
        },
        "summary": {
            "selected_sources": len(output_sources),
            "official_pages_http_200": sum(item["watch_status"]["official_page_request"] == "HTTP_200_PAGE_ONLY" for item in output_sources),
            "external_visual_playback_pass": 0,
            "canonical_match_links": 0,
            "public_projection_fallback": False,
        },
        "featured_sources": output_sources,
        "notice": "Internal evidence review only. Page HTTP success is not video playback; publisher metadata is not a rights grant; unknown rights and links remain unknown.",
    }


def build_from_paths(index_path: Path, observations_path: Path, output_path: Path, generated_at: str | None = None) -> dict[str, Any]:
    try:
        index = json.loads(index_path.read_text(encoding="utf-8-sig"))
        observations = json.loads(observations_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceReviewError(f"cannot load input JSON: {exc}") from exc
    result = build_source_review(index, observations, generated_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
