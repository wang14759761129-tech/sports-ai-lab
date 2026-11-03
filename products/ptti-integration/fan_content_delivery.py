"""Create a San-ready, internal-only GOAL14 delivery projection.

The existing ptti.fan-content-intelligence/0.1 dataset remains unchanged.
This view adds editorial Chinese labels and explicit typed route edges while
keeping match identity, playback, territory, and reuse rights fail-closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "ptti.fan-content-delivery/0.1"
LOCALIZATION_VERSION = "ptti.fan-content-localization/0.1"
BASE_VERSION = "ptti.fan-content-intelligence/0.1"


class DeliveryError(ValueError):
    """Raised when a delivery projection would infer or misbind content."""


def _sha256_json(value: Any) -> str:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _unique_map(rows: Any, key: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise DeliveryError(f"{label} must be an array")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            raise DeliveryError(f"{label} has a row without {key}")
        if row[key] in out:
            raise DeliveryError(f"duplicate {key}: {row[key]}")
        out[row[key]] = row
    return out


def _load_localizations(path: Path, base: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], str]:
    localization = json.loads(path.read_text(encoding="utf-8"))
    if localization.get("contract_version") != LOCALIZATION_VERSION:
        raise DeliveryError("unsupported localization contract version")
    if localization.get("locale") != "zh-CN":
        raise DeliveryError("localization locale must be zh-CN")
    if localization.get("translation_origin") != "PTTI_EDITORIAL_TRANSLATION":
        raise DeliveryError("translation origin must remain an editorial PTTI translation")
    if localization.get("official_translation_status") != "UNKNOWN":
        raise DeliveryError("editorial translations cannot claim official localization")
    if localization.get("review_status") != "NOT_INDEPENDENTLY_REVIEWED":
        raise DeliveryError("unreviewed translations cannot be upgraded")
    observation_sha = next(
        (item.get("sha256") for item in base.get("source_manifest", []) if item.get("logical_name") == "goal14-observation-fixture"),
        None,
    )
    if localization.get("source_observations_sha256") != observation_sha:
        raise DeliveryError("localization is not bound to the exact source-observation fixture")
    events = _unique_map(base.get("events"), "event_id", "base events")
    candidates = _unique_map(base.get("content_candidates"), "candidate_id", "base candidates")
    event_titles = _unique_map(localization.get("events"), "event_id", "event localizations")
    candidate_titles = _unique_map(localization.get("content_candidates"), "candidate_id", "candidate localizations")
    if set(event_titles) != set(events):
        raise DeliveryError("event localization IDs must exactly match the internal dataset")
    if set(candidate_titles) != set(candidates):
        raise DeliveryError("candidate localization IDs must exactly match the internal dataset")
    for event_id, row in event_titles.items():
        if not isinstance(row.get("title_zh"), str) or not row["title_zh"].strip():
            raise DeliveryError(f"event localization is empty: {event_id}")
    for candidate_id, row in candidate_titles.items():
        if not isinstance(row.get("title_zh"), str) or not row["title_zh"].strip():
            raise DeliveryError(f"candidate localization is empty: {candidate_id}")
    return (
        {key: row["title_zh"] for key, row in event_titles.items()},
        {key: row["title_zh"] for key, row in candidate_titles.items()},
        _sha256_json(localization),
    )


def _watch_source(candidate: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    route = candidate.get("watch_route")
    if not isinstance(route, dict) or not isinstance(route.get("url"), str):
        raise DeliveryError(f"candidate lacks an explicit watch route: {candidate.get('candidate_id')}")
    if candidate.get("video_id"):
        expected_url = f"https://www.youtube.com/watch?v={candidate['video_id']}"
        if route.get("kind") != "OFFICIAL_YOUTUBE_VIDEO" or route.get("url") != expected_url:
            raise DeliveryError("video ID and official watch URL do not match")
        watch_source_id = f"watch:youtube:{candidate['video_id']}"
        evidence_ids = list(candidate.get("source_evidence_ids") or [])
        route_status = "URL_IDENTIFIED_PLAYBACK_NOT_TESTED"
        provider = "YOUTUBE"
    else:
        if route.get("kind") != "OFFICIAL_EVENT_PAGE_LISTING":
            raise DeliveryError("unresolved video must route only to its official event listing")
        if route.get("url") != event.get("official_event_page_url"):
            raise DeliveryError("event-page fallback must match the candidate event")
        provider_event_key = event["event_id"].removeprefix("event:")
        watch_source_id = f"watch:event-page:{provider_event_key}"
        evidence_ids = [event["event_page_evidence_id"]]
        route_status = "OFFICIAL_LISTING_ONLY_VIDEO_URL_UNRESOLVED"
        provider = event.get("provider")
    return {
        "watch_source_id": watch_source_id,
        "provider": provider,
        "route_kind": route["kind"],
        "url": route["url"],
        "route_status": route_status,
        "evidence_ids": sorted(set(evidence_ids)),
        "current_access": "NOT_TESTED_CURRENT_SESSION",
        "playback_status": "NOT_TESTED",
        "territory": "UNKNOWN",
        "login_or_paywall": "NOT_TESTED",
        "embed_status": "UNKNOWN",
        "rights": candidate["rights"],
    }


def build_delivery_package(
    base: dict[str, Any],
    localization_path: Path,
    base_sha256: str | None = None,
) -> dict[str, Any]:
    if base.get("contract_version") != BASE_VERSION or base.get("view") != "INTERNAL_REVIEW":
        raise DeliveryError("delivery requires the exact internal-review v0.1 source dataset")
    if base.get("quality_summary", {}).get("public_eligible_count") != 0:
        raise DeliveryError("GOAL14 public projection is not authorized by this delivery builder")

    events = _unique_map(base.get("events"), "event_id", "base events")
    candidates = _unique_map(base.get("content_candidates"), "candidate_id", "base candidates")
    stars = _unique_map(base.get("stars"), "athlete_id", "base stars")
    event_titles, candidate_titles, localization_sha256 = _load_localizations(localization_path, base)

    for row in [*events.values(), *candidates.values()]:
        rights = row.get("rights")
        if not isinstance(rights, dict) or any(rights.get(key) != expected for key, expected in {
            "public_listing": "UNKNOWN",
            "external_viewing": "UNKNOWN",
            "embedding": "UNKNOWN",
            "thumbnail_display": "UNKNOWN",
            "local_analysis": "NOT_GRANTED",
            "download": "NOT_GRANTED",
            "redistribution": "NOT_GRANTED",
            "evidence_status": "NO_SCOPED_GRANT_RECORDED",
        }.items()):
            raise DeliveryError("rights state cannot be escalated in the delivery projection")
        if row.get("public_status") != "INTERNAL_ONLY_PENDING_RIGHTS_REVIEW":
            raise DeliveryError("only the internal-review projection is permitted")
    for candidate in candidates.values():
        if candidate.get("playback_status") != "NOT_TESTED":
            raise DeliveryError("candidate playback cannot be promoted by this delivery projection")
        if candidate.get("match_id") is not None or candidate.get("match_link_status") != "UNKNOWN":
            raise DeliveryError("match identity cannot be inferred by this delivery projection")

    watch_sources: dict[str, dict[str, Any]] = {}
    clips: list[dict[str, Any]] = []
    edges = [dict(row) | {"evidence_ids": [row["evidence_id"]], "edge_status": "SOURCE_LISTING_OBSERVED"}
             for row in base.get("relationships", [])]
    for candidate in candidates.values():
        event = events.get(candidate.get("event_id"))
        if event is None:
            raise DeliveryError(f"orphan event_id for candidate {candidate['candidate_id']}")
        watch = _watch_source(candidate, event)
        previous = watch_sources.get(watch["watch_source_id"])
        if previous is not None and previous != watch:
            raise DeliveryError(f"watch source identity collision: {watch['watch_source_id']}")
        watch_sources[watch["watch_source_id"]] = watch
        clips.append({
            "clip_id": candidate["candidate_id"],
            "event_id": candidate["event_id"],
            "match_id": candidate.get("match_id"),
            "match_link_status": candidate.get("match_link_status", "UNKNOWN"),
            "title_original": candidate["title"],
            "title_zh": candidate_titles[candidate["candidate_id"]],
            "translation_origin": "PTTI_EDITORIAL_TRANSLATION",
            "official_translation_status": "UNKNOWN",
            "content_type": candidate["content_type"],
            "provider": candidate["provider"],
            "video_id": candidate["video_id"],
            "official_video_url": candidate["official_video_url"],
            "publisher": candidate["publisher"],
            "publisher_identity_status": candidate["publisher_identity_status"],
            "published_at": candidate["published_at"],
            "publication_date_status": candidate["publication_date_status"],
            "page_observation_status": candidate["page_observation_status"],
            "watch_source_id": watch["watch_source_id"],
            "source_evidence_ids": list(candidate["source_evidence_ids"]),
            "source_verified_at": candidate["source_verified_at"],
            "playback_status": candidate["playback_status"],
            "territory": candidate["territory"],
            "login_or_paywall": candidate["login_or_paywall"],
            "embed_status": candidate["embed_status"],
            "thumbnail_url": candidate["thumbnail_url"],
            "public_status": candidate["public_status"],
            "rights": candidate["rights"],
        })
        edges.append({
            "relationship_id": f"rel:{candidate['candidate_id']}:watch-source",
            "from_type": "CLIP_CANDIDATE",
            "from_id": candidate["candidate_id"],
            "to_type": "WATCH_SOURCE",
            "to_id": watch["watch_source_id"],
            "relationship_kind": "HAS_OFFICIAL_WATCH_ROUTE",
            "evidence_ids": watch["evidence_ids"],
            "edge_status": "ROUTE_LISTED_NOT_PLAYBACK_VERIFIED",
        })

    event_rows = []
    for event in events.values():
        event_rows.append(dict(event) | {
            "title_original": event["name"],
            "title_zh": event_titles[event["event_id"]],
            "translation_origin": "PTTI_EDITORIAL_TRANSLATION",
            "official_translation_status": "UNKNOWN",
        })

    match_clip_links = [edge for edge in edges if edge.get("from_type") in {"MATCH", "MATCH_CANDIDATE"} or edge.get("to_type") in {"MATCH", "MATCH_CANDIDATE"}]
    if match_clip_links or any(clip["match_id"] is not None or clip["match_link_status"] != "UNKNOWN" for clip in clips):
        raise DeliveryError("this dataset has no verified individual match-to-clip identity")

    source_index = [dict(row) for row in base.get("evidence_sources", [])]
    evidence_ids = {row["evidence_id"] for row in source_index}
    for edge in edges:
        if not set(edge.get("evidence_ids", [])) <= evidence_ids:
            raise DeliveryError("relationship edge refers to missing source evidence")
    return {
        "contract_version": CONTRACT_VERSION,
        "view": "INTERNAL_REVIEW",
        "base_contract_version": BASE_VERSION,
        "generated_at": base["generated_at"],
        "source_manifest": {
            "base_dataset_sha256": base_sha256 or _sha256_json(base),
            "localization_sha256": localization_sha256,
        },
        "stars": [dict(row) for row in stars.values()],
        "events": event_rows,
        "matches": [],
        "clips": clips,
        "watch_sources": sorted(watch_sources.values(), key=lambda row: row["watch_source_id"]),
        "relationships": edges,
        "relationship_gaps": [
            {
                "path": "STAR_TO_MATCH",
                "status": "NOT_ESTABLISHED",
                "reason": "No direct evidence links a listed athlete to a specific match record in this package.",
            },
            {
                "path": "MATCH_TO_CLIP",
                "status": "NOT_ESTABLISHED",
                "reason": "Candidates are event-level highlights or event-page listings; no match-specific clip appearance was verified.",
            },
        ],
        "source_index": source_index,
        "quality_summary": {
            "star_count": len(stars),
            "event_count": len(event_rows),
            "verified_match_count": 0,
            "clip_candidate_count": len(clips),
            "unique_watch_source_count": len(watch_sources),
            "exact_video_url_count": sum(row["video_id"] is not None for row in candidates.values()),
            "event_page_only_count": sum(row["video_id"] is None for row in candidates.values()),
            "playback_pass_count": 0,
            "public_eligible_count": 0,
            "match_video_links": 0,
        },
        "notice": "Internal review only. Localized titles are PTTI editorial translations, not official translations. External routes are not playback proof. No individual match-to-clip identity or public media rights are established.",
    }


def write_delivery_package(package: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path
