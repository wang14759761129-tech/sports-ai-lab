"""Build a source-backed, internal-only GOAL14 Fan content index.

This module deliberately does not crawl or download media. It transforms the
checked-in observation fixture and a small allowlisted slice of the professional
registry into a typed consumer view. Rights, match identity, and playback stay
fail-closed unless a future, separately reviewed evidence flow changes them.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


CONTRACT_VERSION = "ptti.fan-content-intelligence/0.1"
INPUT_VERSION = "ptti.fan-content-observations/0.1"
OFFICIAL_HOSTS = {"worldtabletennis.com", "www.worldtabletennis.com"}
ALLOWED_OBSERVATION_KEYS = {
    "candidate_id",
    "event_id",
    "title",
    "content_type",
    "video_id",
    "published_at",
    "youtube_evidence_id",
}
ALLOWED_EVENT_KEYS = {
    "event_id",
    "provider",
    "provider_event_id",
    "name",
    "event_year",
    "event_dates",
    "official_event_page_url",
    "event_page_evidence_id",
    "viewing_route_status",
    "viewing_route_kind",
    "notes",
}
ALLOWED_RELATIONSHIP_KEYS = {
    "relationship_id",
    "from_type",
    "from_id",
    "to_type",
    "to_id",
    "relationship_kind",
    "evidence_id",
}
ALLOWED_EVIDENCE_KEYS = {
    "evidence_id",
    "kind",
    "url",
    "observed_at",
    "claims",
    "listed_titles",
    "listed_player_athlete_ids",
    "observed_event_name",
    "event_start",
    "event_end",
    "observed_title",
    "published_at",
    "publisher",
    "limitations",
}
ALLOWED_TOP_LEVEL_KEYS = {
    "contract_version",
    "audience",
    "observed_at",
    "events",
    "star_athlete_ids",
    "relationships",
    "content_candidates",
    "evidence_sources",
}
DIRECT_VIDEO_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class FanContentError(ValueError):
    """Raised when supplied content/evidence violates the conservative contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _official_wtt_url(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FanContentError(f"{field} must be an HTTPS WTT URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise FanContentError(f"{field} must use an official World Table Tennis host")
    return value


def _evidence_map(raw_rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_rows, list):
        raise FanContentError("evidence_sources must be an array")
    result: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict) or set(row) - ALLOWED_EVIDENCE_KEYS:
            raise FanContentError("evidence source has unsupported or malformed fields")
        evidence_id = row.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in result:
            raise FanContentError("evidence_id must be unique and non-empty")
        kind = row.get("kind")
        if kind not in {
            "OFFICIAL_EVENT_PAGE_SEARCH_INDEX",
            "OFFICIAL_WTT_ARTICLE_SEARCH_INDEX",
            "OFFICIAL_YOUTUBE_SEARCH_RESULT",
        }:
            raise FanContentError(f"unsupported evidence kind: {kind!r}")
        if kind == "OFFICIAL_YOUTUBE_SEARCH_RESULT":
            url = row.get("url")
            parsed = urlsplit(url) if isinstance(url, str) else None
            if parsed is None or parsed.scheme != "https" or parsed.hostname not in {"youtube.com", "www.youtube.com"}:
                raise FanContentError("YouTube evidence URL must use the official YouTube watch host")
        else:
            _official_wtt_url(row.get("url"), "evidence url")
        if not isinstance(row.get("observed_at"), str) or not isinstance(row.get("claims"), list):
            raise FanContentError("evidence observed_at and claims are required")
        if not isinstance(row.get("limitations"), str) or not row["limitations"].strip():
            raise FanContentError("every evidence source must state its limitations")
        result[evidence_id] = row
    return result


def _rights(notes: list[str] | None = None) -> dict[str, Any]:
    return {
        "public_listing": "UNKNOWN",
        "external_viewing": "UNKNOWN",
        "embedding": "UNKNOWN",
        "thumbnail_display": "UNKNOWN",
        "local_analysis": "NOT_GRANTED",
        "download": "NOT_GRANTED",
        "redistribution": "NOT_GRANTED",
        "evidence_status": "NO_SCOPED_GRANT_RECORDED",
        "notes": list(notes or []),
    }


def _event_page_event_reference(event: dict[str, Any], evidence: dict[str, Any]) -> None:
    if evidence["url"] != event["official_event_page_url"]:
        raise FanContentError(f"event evidence URL mismatch for {event['event_id']}")
    if evidence["kind"] not in {"OFFICIAL_EVENT_PAGE_SEARCH_INDEX", "OFFICIAL_WTT_ARTICLE_SEARCH_INDEX"}:
        raise FanContentError(f"event identity evidence type invalid for {event['event_id']}")
    if evidence.get("observed_event_name") != event.get("name"):
        raise FanContentError(f"official source event name does not match {event['event_id']}")


def _source_ids_for_athletes(registry: dict[str, Any], athlete_ids: list[str]) -> dict[str, dict[str, Any]]:
    profiles = {
        row.get("athlete_id"): row
        for row in registry.get("athletes", [])
        if isinstance(row, dict) and isinstance(row.get("athlete_id"), str)
    }
    missing = sorted(set(athlete_ids) - set(profiles))
    if missing:
        raise FanContentError(f"unknown athlete IDs in curated star list: {missing}")
    return {athlete_id: profiles[athlete_id] for athlete_id in athlete_ids}


def _build_star(profile: dict[str, Any]) -> dict[str, Any]:
    name = profile.get("canonical_name_en")
    if not isinstance(name, str) or not name:
        raise FanContentError(f"registry profile {profile.get('athlete_id')} has no canonical name")
    profile_url = profile.get("official_profile_url")
    if profile_url is not None:
        parsed = urlsplit(profile_url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            raise FanContentError("athlete profile URL must be an official WTT URL")
    return {
        "athlete_id": profile["athlete_id"],
        "name_en": name,
        "name_zh": profile.get("canonical_name_zh"),
        "association": profile.get("country_or_association"),
        "ittf_id": profile.get("ittf_id"),
        "official_profile_url": profile_url,
        "registry_source_ids": list(profile.get("source_ids") or []),
        "profile_snapshot_verified_at": profile.get("last_verified_at"),
        "current_profile_access": "NOT_TESTED_CURRENT_SESSION",
        "public_listing": "UNKNOWN",
        "display_permissions": {
            "profile_listing": "UNKNOWN",
            "portrait_display": "UNKNOWN",
            "biography_reuse": "UNKNOWN",
            "evidence_status": "NO_SCOPED_GRANT_RECORDED",
        },
        "portrait_url": None,
        "biography_status": "NOT_COLLECTED",
        "equipment_status": "UNKNOWN",
        "coach_observation_status": "NOT_COLLECTED",
        "interviews_status": "NOT_COLLECTED",
        "sponsorship_status": "NOT_COLLECTED",
        "social_feedback_status": "NOT_COLLECTED",
    }


def _build_event(raw: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - ALLOWED_EVENT_KEYS:
        raise FanContentError("event has unsupported or malformed fields")
    event_id = raw.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise FanContentError("event_id must be non-empty")
    event_url = _official_wtt_url(raw.get("official_event_page_url"), "official_event_page_url")
    if raw.get("provider") != "WTT":
        raise FanContentError("this GOAL14 sample currently supports WTT provider records only")
    provider_event_id = raw.get("provider_event_id")
    if provider_event_id is not None:
        query_event_id = parse_qs(urlsplit(event_url).query).get("eventId", [None])[0]
        if str(provider_event_id) != query_event_id or event_id != f"event:wtt:{provider_event_id}":
            raise FanContentError(f"provider event identity does not match URL and stable event_id for {event_id}")
    evidence_id = raw.get("event_page_evidence_id")
    if evidence_id not in evidence:
        raise FanContentError(f"missing event-page evidence for {event_id}")
    _event_page_event_reference(raw, evidence[evidence_id])
    status = raw.get("viewing_route_status")
    if status not in {
        "OFFICIAL_ROUTE_IDENTIFIED",
        "OFFICIAL_PAGE_LISTS_RELATED_VIDEO",
        "OFFICIAL_ARTICLE_STATES_WATCH_OPTIONS",
    }:
        raise FanContentError(f"invalid viewing route status for {event_id}")
    dates = raw.get("event_dates")
    if not isinstance(dates, dict) or set(dates) != {"start", "end", "status"}:
        raise FanContentError(f"event_dates malformed for {event_id}")
    if dates["status"] == "UNKNOWN" and (dates["start"] is not None or dates["end"] is not None):
        raise FanContentError(f"unknown event dates cannot contain inferred dates for {event_id}")
    if dates["status"] == "SOURCE_PAGE_LISTED" and (not dates["start"] or not dates["end"]):
        raise FanContentError(f"source-listed event dates require both endpoints for {event_id}")
    if dates["status"] == "SOURCE_PAGE_LISTED" and (
        evidence[evidence_id].get("event_start") != dates["start"]
        or evidence[evidence_id].get("event_end") != dates["end"]
    ):
        raise FanContentError(f"event dates do not match source evidence for {event_id}")
    if dates["start"] and dates["end"] and dates["start"] > dates["end"]:
        raise FanContentError(f"event start date follows event end date for {event_id}")
    return {
        "event_id": event_id,
        "provider": raw["provider"],
        "provider_event_id": raw.get("provider_event_id"),
        "name": raw["name"],
        "event_year": raw.get("event_year"),
        "event_dates": dates,
        "official_event_page_url": event_url,
        "event_page_evidence_id": evidence_id,
        "source_verified_at": evidence[evidence_id]["observed_at"],
        "official_viewing_route": {
            "kind": raw["viewing_route_kind"],
            "url": event_url,
            "status": status,
            "current_access": "NOT_TESTED_CURRENT_SESSION",
            "territory": "UNKNOWN",
            "login_or_paywall": "NOT_TESTED",
        },
        "rights": _rights(["Official route is recorded as a link only; PTTI reuse, embedding, or territorial access permission is not established."]),
        "public_status": "INTERNAL_ONLY_PENDING_RIGHTS_REVIEW",
        "notes": list(raw.get("notes") or []),
    }


def _build_candidate(raw: dict[str, Any], events: dict[str, dict[str, Any]], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != ALLOWED_OBSERVATION_KEYS:
        raise FanContentError("content candidate has unsupported, inferred, or missing input fields")
    candidate_id = raw["candidate_id"]
    event_id = raw["event_id"]
    title = raw["title"]
    if not isinstance(candidate_id, str) or not candidate_id or not isinstance(title, str) or not title:
        raise FanContentError("candidate_id and title must be non-empty strings")
    if raw["content_type"] not in {"HIGHLIGHTS", "HIGHLIGHTS_SHOW"}:
        raise FanContentError(f"unsupported fan-content type for {candidate_id}")
    event = events.get(event_id)
    if event is None:
        raise FanContentError(f"candidate references unknown event_id: {event_id}")

    video_id = raw["video_id"]
    published_at = raw["published_at"]
    youtube_evidence_id = raw["youtube_evidence_id"]
    if video_id is None:
        if published_at is not None or youtube_evidence_id is not None:
            raise FanContentError("unresolved video ID cannot carry publication date or YouTube metadata evidence")
        event_evidence = evidence[event["event_page_evidence_id"]]
        if title not in event_evidence.get("listed_titles", []):
            raise FanContentError(f"unresolved candidate title is not listed on official event page: {candidate_id}")
        watch_route = {
            "kind": "OFFICIAL_EVENT_PAGE_LISTING",
            "url": event["official_event_page_url"],
            "status": "OFFICIAL_LISTING_ONLY_VIDEO_URL_UNRESOLVED",
        }
        publisher = None
        publisher_status = "EVENT_PAGE_LISTING_ONLY"
        page_observation_status = "OFFICIAL_EVENT_PAGE_RELATED_VIDEO_LISTING"
        evidence_ids = [event["event_page_evidence_id"]]
        published_status = "UNKNOWN"
    else:
        if not isinstance(video_id, str) or not DIRECT_VIDEO_RE.fullmatch(video_id):
            raise FanContentError(f"invalid YouTube video ID: {video_id!r}")
        if youtube_evidence_id not in evidence:
            raise FanContentError(f"missing direct YouTube metadata evidence for {candidate_id}")
        youtube_evidence = evidence[youtube_evidence_id]
        expected_url = f"https://www.youtube.com/watch?v={video_id}"
        if youtube_evidence["kind"] != "OFFICIAL_YOUTUBE_SEARCH_RESULT" or youtube_evidence["url"] != expected_url:
            raise FanContentError(f"YouTube evidence does not bind the supplied video ID for {candidate_id}")
        event_evidence = evidence[event["event_page_evidence_id"]]
        observed_title = youtube_evidence.get("observed_title")
        if observed_title is not None and observed_title != title:
            raise FanContentError(f"YouTube title evidence mismatch for {candidate_id}")
        if title not in event_evidence.get("listed_titles", []) and observed_title != title:
            raise FanContentError(f"video title is not corroborated for {candidate_id}")
        if "publisher_world_table_tennis_verified" not in youtube_evidence["claims"] or youtube_evidence.get("publisher") != "World Table Tennis":
            raise FanContentError(f"publisher identity is not verified for {candidate_id}")
        if published_at != youtube_evidence.get("published_at"):
            raise FanContentError(f"publication date mismatch for {candidate_id}")
        watch_route = {
            "kind": "OFFICIAL_YOUTUBE_VIDEO",
            "url": expected_url,
            "status": "URL_IDENTIFIED_PLAYBACK_NOT_TESTED",
        }
        publisher = "World Table Tennis"
        publisher_status = "WTT_VERIFIED_CHANNEL_SEARCH_RESULT"
        page_observation_status = "YOUTUBE_SEARCH_INDEX_METADATA"
        evidence_ids = [event["event_page_evidence_id"], youtube_evidence_id]
        published_status = "SOURCE_METADATA_DATE" if published_at is not None else "UNKNOWN"

    return {
        "candidate_id": candidate_id,
        "event_id": event_id,
        "title": title,
        "content_type": raw["content_type"],
        "provider": "YOUTUBE" if video_id is not None else "UNKNOWN",
        "video_id": video_id,
        "publisher": publisher,
        "publisher_identity_status": publisher_status,
        "published_at": published_at,
        "publication_date_status": published_status,
        "official_video_url": watch_route["url"] if video_id else None,
        "watch_route": watch_route,
        "source_evidence_ids": evidence_ids,
        "source_verified_at": max(evidence[evidence_id]["observed_at"] for evidence_id in evidence_ids),
        "page_observation_status": page_observation_status,
        "playback_status": "NOT_TESTED",
        "territory": "UNKNOWN",
        "login_or_paywall": "NOT_TESTED",
        "embed_status": "UNKNOWN",
        "thumbnail_url": None,
        "match_id": None,
        "match_link_status": "UNKNOWN",
        "rights": _rights(["No scoped permission for public listing, embed, thumbnail, local analysis, download, or redistribution was supplied."]),
        "public_status": "INTERNAL_ONLY_PENDING_RIGHTS_REVIEW",
    }


def _validate_relationships(rows: Any, stars: dict[str, dict[str, Any]], events: dict[str, dict[str, Any]], candidates: dict[str, dict[str, Any]], evidence: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise FanContentError("relationships must be an array")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != ALLOWED_RELATIONSHIP_KEYS:
            raise FanContentError("relationship has unsupported or missing fields")
        relationship_id = raw["relationship_id"]
        if not isinstance(relationship_id, str) or relationship_id in ids:
            raise FanContentError("relationship IDs must be unique strings")
        ids.add(relationship_id)
        evidence_id = raw["evidence_id"]
        if evidence_id not in evidence:
            raise FanContentError(f"relationship references unknown evidence_id: {evidence_id}")
        from_type, from_id = raw["from_type"], raw["from_id"]
        to_type, to_id = raw["to_type"], raw["to_id"]
        if to_type != "EVENT" or to_id not in events:
            raise FanContentError("relationships must point to a known event")
        kind = raw["relationship_kind"]
        if from_type == "ATHLETE" and kind == "LISTED_ON_EVENT_PLAYER_ROSTER":
            if from_id not in stars or from_id not in evidence[evidence_id].get("listed_player_athlete_ids", []):
                raise FanContentError("athlete/event relation lacks exact roster evidence")
            scope = "EVENT_ROSTER_LISTING_ONLY_NOT_CLIP_APPEARANCE"
        elif from_type == "CONTENT_CANDIDATE" and kind in {"LISTED_AS_EVENT_RELATED_VIDEO", "TITLE_HASHTAG_EVENT_ASSOCIATION"}:
            candidate = candidates.get(from_id)
            if candidate is None or candidate["event_id"] != to_id:
                raise FanContentError("candidate/event relation does not match the candidate event_id")
            if evidence_id not in candidate["source_evidence_ids"]:
                raise FanContentError("candidate/event relation evidence is not attached to the candidate")
            if kind == "LISTED_AS_EVENT_RELATED_VIDEO" and evidence[evidence_id].get("kind") != "OFFICIAL_EVENT_PAGE_SEARCH_INDEX":
                raise FanContentError("event-listed video relationship requires the exact official event page evidence")
            if kind == "TITLE_HASHTAG_EVENT_ASSOCIATION" and evidence[evidence_id].get("kind") != "OFFICIAL_YOUTUBE_SEARCH_RESULT":
                raise FanContentError("title-event relationship requires direct video title evidence")
            scope = "OFFICIAL_VIDEO_TITLE_EVENT_ASSOCIATION_ONLY_NOT_MATCH_LINK" if kind == "TITLE_HASHTAG_EVENT_ASSOCIATION" else "OFFICIAL_EVENT_PAGE_LISTING_ONLY_NOT_MATCH_LINK"
        else:
            raise FanContentError("unsupported relationship direction or kind")
        result.append({**raw, "confidence_scope": scope})
    return result


def build_fan_content(
    registry: dict[str, Any],
    observations: dict[str, Any],
    *,
    generated_at: str,
    source_manifest: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return INTERNAL_REVIEW and deliberately empty STRICT_PUBLIC views."""
    if not isinstance(observations, dict) or set(observations) != ALLOWED_TOP_LEVEL_KEYS:
        raise FanContentError("observation fixture has unsupported or missing top-level fields")
    if observations.get("contract_version") != INPUT_VERSION or observations.get("audience") != "INTERNAL_REVIEW_ONLY":
        raise FanContentError("unsupported observation contract or audience")
    evidence = _evidence_map(observations.get("evidence_sources"))

    raw_events = observations.get("events")
    if not isinstance(raw_events, list):
        raise FanContentError("events must be an array")
    events_list = [_build_event(row, evidence) for row in raw_events]
    if len({row["event_id"] for row in events_list}) != len(events_list):
        raise FanContentError("duplicate event_id")
    events = {row["event_id"]: row for row in events_list}

    athlete_ids = observations.get("star_athlete_ids")
    if not isinstance(athlete_ids, list) or len(athlete_ids) != 3 or len(set(athlete_ids)) != len(athlete_ids):
        raise FanContentError("exactly three unique registry-backed demo athletes are required")
    profiles = _source_ids_for_athletes(registry, athlete_ids)
    stars_list = [_build_star(profiles[athlete_id]) for athlete_id in athlete_ids]
    stars = {row["athlete_id"]: row for row in stars_list}

    raw_candidates = observations.get("content_candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) != 20:
        raise FanContentError("the source review sample must contain exactly 20 unique candidate records")
    candidates_list = [_build_candidate(row, events, evidence) for row in raw_candidates]
    if len({row["candidate_id"] for row in candidates_list}) != len(candidates_list):
        raise FanContentError("duplicate candidate_id")
    resolved_ids = [row["video_id"] for row in candidates_list if row["video_id"] is not None]
    if len(set(resolved_ids)) != len(resolved_ids):
        raise FanContentError("duplicate video_id in candidate list")
    candidates = {row["candidate_id"]: row for row in candidates_list}

    relationships_raw = list(observations.get("relationships") or [])
    for candidate in candidates_list:
        if candidate["video_id"] is None:
            evidence_id = events[candidate["event_id"]]["event_page_evidence_id"]
            relationship_kind = "LISTED_AS_EVENT_RELATED_VIDEO"
        else:
            evidence_id = next(
                evidence_id
                for evidence_id in candidate["source_evidence_ids"]
                if evidence[evidence_id]["kind"] == "OFFICIAL_YOUTUBE_SEARCH_RESULT"
            )
            relationship_kind = "TITLE_HASHTAG_EVENT_ASSOCIATION"
        relationships_raw.append({
            "relationship_id": f"rel:{candidate['candidate_id']}:event",
            "from_type": "CONTENT_CANDIDATE",
            "from_id": candidate["candidate_id"],
            "to_type": "EVENT",
            "to_id": candidate["event_id"],
            "relationship_kind": relationship_kind,
            "evidence_id": evidence_id,
        })
    relationships = _validate_relationships(relationships_raw, stars, events, candidates, evidence)

    # Include only profile source evidence for the three selected athlete IDs.
    registry_sources = {row.get("source_id"): row for row in registry.get("sources", []) if isinstance(row, dict)}
    used_profile_sources: set[str] = set()
    profile_evidence: list[dict[str, Any]] = []
    for star in stars_list:
        preferred = next((source_id for source_id in star["registry_source_ids"] if source_id.startswith("wtt-profile-")), None)
        source = registry_sources.get(preferred)
        if not isinstance(source, dict) or source.get("source_url") != star["official_profile_url"]:
            raise FanContentError(f"official profile source is not bound for {star['athlete_id']}")
        used_profile_sources.add(preferred)
        profile_evidence.append({
            "evidence_id": f"evidence:registry:{preferred}",
            "kind": "PROFESSIONAL_REGISTRY_SOURCE_SNAPSHOT",
            "url": source["source_url"],
            "observed_at": source.get("retrieved_at", "2026-10-05T00:00:00Z")[:10],
            "claims": ["registry_identity_fields_and_official_profile_url"],
            "limitations": "Committed professional registry snapshot only; current page access, profile freshness, portrait permission, and public reuse are not tested or granted.",
        })
    normalized_evidence = []
    for row in evidence.values():
        normalized_evidence.append({
            key: row[key]
            for key in ("evidence_id", "kind", "url", "observed_at", "claims", "limitations")
            if key in row
        } | ({"listed_titles": row["listed_titles"]} if "listed_titles" in row else {})
          | ({"listed_player_athlete_ids": row["listed_player_athlete_ids"]} if "listed_player_athlete_ids" in row else {})
          | ({"observed_event_name": row["observed_event_name"]} if "observed_event_name" in row else {})
          | ({"event_start": row["event_start"]} if "event_start" in row else {})
          | ({"event_end": row["event_end"]} if "event_end" in row else {})
          | ({"observed_event_name": row["observed_event_name"]} if "observed_event_name" in row else {})
          | ({"event_start": row["event_start"]} if "event_start" in row else {})
          | ({"event_end": row["event_end"]} if "event_end" in row else {})
          | ({"observed_title": row["observed_title"]} if "observed_title" in row else {})
          | ({"published_at": row["published_at"]} if "published_at" in row else {})
          | ({"publisher": row["publisher"]} if "publisher" in row else {}))
    normalized_evidence.extend(profile_evidence)

    count = len(candidates_list)
    direct_count = sum(row["video_id"] is not None for row in candidates_list)
    internal = {
        "contract_version": CONTRACT_VERSION,
        "view": "INTERNAL_REVIEW",
        "generated_at": generated_at,
        "source_manifest": source_manifest,
        "evidence_sources": normalized_evidence,
        "events": events_list,
        "stars": stars_list,
        "content_candidates": candidates_list,
        "relationships": relationships,
        "quality_summary": {
            "event_count": len(events_list),
            "star_count": len(stars_list),
            "candidate_count": count,
            "exact_video_url_count": direct_count,
            "event_page_only_count": count - direct_count,
            "playback_pass_count": 0,
            "public_eligible_count": 0,
            "match_video_links": 0,
            "status_counts": {
                "playback_NOT_TESTED": count,
                "rights_UNKNOWN": len(events_list) + len(stars_list) + count,
                "public_INTERNAL_ONLY": len(events_list) + len(stars_list) + count,
            },
        },
        "notice": "Internal source review only. Event-page listing or an identified official URL does not prove current viewing, region access, embed permission, thumbnail rights, match identity, or PTTI public listing permission. No media is hosted here.",
    }
    public = {
        "contract_version": CONTRACT_VERSION,
        "view": "STRICT_PUBLIC",
        "generated_at": generated_at,
        "source_manifest": [],
        "evidence_sources": [],
        "events": [],
        "stars": [],
        "content_candidates": [],
        "relationships": [],
        "quality_summary": {
            "event_count": 0,
            "star_count": 0,
            "candidate_count": 0,
            "exact_video_url_count": 0,
            "event_page_only_count": 0,
            "playback_pass_count": 0,
            "public_eligible_count": 0,
            "match_video_links": 0,
            "status_counts": {"playback_NOT_TESTED": 0, "rights_UNKNOWN": 0, "public_INTERNAL_ONLY": 0},
        },
        "notice": "No records have scoped, evidenced public-listing permission. This view is empty by design and must not fall back to INTERNAL_REVIEW.",
    }
    return internal, public


def build_from_files(repo_root: Path, observations_path: Path, registry_path: Path, generated_at: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    integration_dir = repo_root / "products" / "ptti-integration"
    reference_index = integration_dir / "generated" / "goal11-match-library" / "match-library-internal-review.json"
    if not reference_index.is_file():
        raise FanContentError("the existing read-only Match Library review index is missing")
    for candidate_path in (observations_path, registry_path):
        if not candidate_path.is_file():
            raise FanContentError(f"required input file missing: {candidate_path.name}")
    fixture = json.loads(observations_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    # The 35-record source catalog is deliberately consumed only as a hashed
    # upstream reference. It is never merged into these five events/20 clips.
    manifest = [
        {"logical_name": "goal14-observation-fixture", "sha256": _sha256(observations_path)},
        {"logical_name": "professional-registry-snapshot", "sha256": _sha256(registry_path)},
        {"logical_name": "goal11-match-library-internal-reference", "sha256": _sha256(reference_index)},
    ]
    when = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FanContentError("generated_at must be ISO-8601") from exc
    return build_fan_content(registry, fixture, generated_at=when, source_manifest=manifest)


def write_views(internal: dict[str, Any], public: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    internal_path = output_dir / "fan-content-internal-review.json"
    public_path = output_dir / "fan-content-strict-public.json"
    internal_path.write_text(json.dumps(internal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_path.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return internal_path, public_path
