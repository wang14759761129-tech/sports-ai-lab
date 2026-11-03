"""Build a source-backed, rights-conservative Match Library index.

This adapter reads only committed professional catalog snapshots. It never
downloads media, infers cross-system Match links from names, or grants rights.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


CONTRACT_VERSION = "ptti.match-library-index/0.1"
REVIEW_TARGETS_VERSION = "ptti.review-targets/0.1"
EVIDENCE_PACK_VERSION = "ptti.review-evidence-pack/0.1"
DISCIPLINES = {"MS", "WS", "MD", "WD", "XD"}
CONTENT_TYPES = {"FULL_MATCH", "HIGHLIGHTS", "SESSION", "CLIP", "UNKNOWN"}
PLAYBACK_STATES = {
    "NOT_TESTED", "RESTRICTED", "UNAVAILABLE", "SOURCE_LINK_ONLY",
    "EMBED_BLOCKED", "EMBED_NOT_TESTED", "UNKNOWN",
}
CATALOG_FILES = (
    "catalog_expansion_r1.json",
    "catalog_expansion_r51_closeout.json",
    "catalog_expansion_20261011.json",
    "official_video_sources.json",
)
REGISTRY_FILE = "registry.json"


class CatalogError(ValueError):
    """Raised when a source snapshot is structurally unsafe to project."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Cannot read catalog input {path.name}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _platform(row: dict[str, Any]) -> str:
    value = row.get("platform")
    if value in {"YOUTUBE", "BILIBILI"}:
        return value
    provider = str(row.get("provider") or "").upper()
    if "BILIBILI" in provider:
        return "BILIBILI"
    if "YOUTUBE" in provider:
        return "YOUTUBE"
    raise CatalogError("Video source has no supported platform")


def _validate_video_url(platform: str, video_id: str, value: Any) -> str:
    if not isinstance(value, str):
        raise CatalogError("Video source URL is missing")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise CatalogError("Video source URL must be a clean HTTPS URL")
    if platform == "YOUTUBE":
        if (parsed.netloc not in {"www.youtube.com", "youtube.com"}
                or parsed.path != "/watch"
                or parse_qs(parsed.query, keep_blank_values=True) != {"v": [video_id]}
                or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id)):
            raise CatalogError("YouTube URL and video ID do not match")
    elif (parsed.netloc not in {"www.bilibili.com", "bilibili.com"}
          or parsed.path.rstrip("/") != f"/video/{video_id}"
          or parsed.query
          or not re.fullmatch(r"BV[A-Za-z0-9]{10}", video_id)):
        raise CatalogError("Bilibili URL and video ID do not match")
    return value


def _source_time(row: dict[str, Any]) -> str | None:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    return _text(row.get("source_verified_at") or row.get("metadata_verified_at")
                 or provenance.get("checked_at"))


def _source_time_key(row: dict[str, Any]) -> float:
    value = _source_time(row)
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _source_permission(row: dict[str, Any], permission: str) -> str:
    """Only a scoped, evidenced permission can become ALLOWED.

    Generic flags such as full_match, local_analysis_allowed, a platform URL,
    or rights_status do not grant public listing or image reuse.
    """
    permissions = row.get("usage_permissions")
    evidence = row.get("permission_evidence")
    decision = permissions.get(permission) if isinstance(permissions, dict) else None
    proof = evidence.get(permission) if isinstance(evidence, dict) else None
    if (decision == "ALLOWED" and isinstance(proof, dict)
            and _text(proof.get("evidence_ref")) and _text(proof.get("verified_at"))
            and _text(proof.get("issuer"))):
        return "ALLOWED"
    if decision in {"DENIED", "NOT_ALLOWED"}:
        return "NOT_ALLOWED"
    return "UNKNOWN"


def _external_observations(row: dict[str, Any], snapshot: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    page_review = provenance.get("page_review")
    if isinstance(page_review, dict):
        observations.append({
            "snapshot": snapshot,
            "surface": _text(page_review.get("surface")) or "UNKNOWN",
            "checked_at": _text(page_review.get("checked_at")),
            "page_accessible": page_review.get("page_accessible") if isinstance(page_review.get("page_accessible"), bool) else None,
            "visual_playback": "VISUAL_PASS_LIMITED" if page_review.get("content_playback_verified") is True else (
                "RESTRICTED_OBSERVED" if "REGION_RESTRICTED" in str(page_review.get("result", "")) else "NOT_VERIFIED"
            ),
            "observed_result": _text(page_review.get("result")) or "UNKNOWN",
            "limitations": _text(page_review.get("limitations")),
        })
    watch_page_test = row.get("watch_page_test")
    if isinstance(watch_page_test, dict):
        result = str(watch_page_test.get("result", ""))
        limitations = _text(watch_page_test.get("limitations"))
        visual = "VISUAL_PASS_LIMITED" if result == "ACTUAL_PLAYBACK_VERIFIED" else (
            "RESTRICTED_OBSERVED" if "RESTRICT" in result or "LIMIT" in result else "NOT_VERIFIED"
        )
        observations.append({
            "snapshot": snapshot,
            "surface": _text(watch_page_test.get("surface")) or "UNKNOWN",
            "checked_at": _text(watch_page_test.get("checked_at")),
            "page_accessible": True if result == "ACTUAL_PLAYBACK_VERIFIED" else None,
            "visual_playback": visual,
            "observed_result": _text(watch_page_test.get("result")) or "UNKNOWN",
            "limitations": limitations,
            "observed_playing_times": watch_page_test.get("observed_playing_times") if isinstance(watch_page_test.get("observed_playing_times"), list) else [],
            "full_content_reviewed": watch_page_test.get("full_content_reviewed") if isinstance(watch_page_test.get("full_content_reviewed"), bool) else None,
        })
    return observations


def _embed_observation(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("playback_status") or "UNKNOWN")
    native_test = row.get("native_playback_test")
    error_class = native_test.get("error_class") if isinstance(native_test, dict) else None
    if status == "EMBED_BLOCKED" or error_class == "EMBEDDING_DISALLOWED":
        technical_status = "BLOCKED_OBSERVED"
    else:
        technical_status = "NOT_TESTED"
    attempt = None
    if isinstance(native_test, dict):
        attempt = {
            "result": _text(native_test.get("result")) or "UNKNOWN",
            "error_code": native_test.get("error_code") if isinstance(native_test.get("error_code"), int) else None,
            "error_class": _text(error_class),
            "verification_label": _text(native_test.get("verification")) or "UNKNOWN",
            "date": _text(native_test.get("date")),
        }
    return {
        "technical_status": technical_status,
        "permission_status": "UNKNOWN",
        "historical_attempt": attempt,
    }


def _explicit_native_pass(row: dict[str, Any]) -> bool:
    test = row.get("desktop_native_playback_evidence")
    if not isinstance(test, dict) or test.get("status") != "DESKTOP_NATIVE_PLAYBACK_PASS":
        return False
    required = ("build_git_sha", "exe_sha256", "media_sha256", "tested_at", "test_record_id")
    if not all(_text(test.get(key)) for key in required):
        return False
    if not re.fullmatch(r"[0-9a-fA-F]{40}", test["build_git_sha"]):
        return False
    return all(re.fullmatch(r"[0-9a-fA-F]{64}", test[key]) for key in ("exe_sha256", "media_sha256"))


def _participants(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("player_a") or row.get("player_b"):
        return {"side_a": _text(row.get("player_a")), "side_b": _text(row.get("player_b")), "unassigned_names": []}
    if row.get("pair_a") or row.get("pair_b"):
        return {"side_a": _text(row.get("pair_a")), "side_b": _text(row.get("pair_b")), "unassigned_names": []}
    raw_names = row.get("athlete_names")
    names = [name.strip() for name in raw_names if isinstance(name, str) and name.strip()] if isinstance(raw_names, list) else []
    return {"side_a": None, "side_b": None, "unassigned_names": names}


def _identity_values(row: dict[str, Any]) -> dict[str, Any]:
    participants = _participants(row)
    return {
        "event": _text(row.get("event") or row.get("event_name")),
        "discipline": row.get("match_type") or row.get("discipline") or "UNKNOWN",
        "round": _text(row.get("round") or row.get("round_label")),
        "side_a": participants["side_a"],
        "side_b": participants["side_b"],
        "unassigned_names": participants["unassigned_names"],
    }


def _deduplicate_sources(rows: list[tuple[str, dict[str, Any]]]) -> tuple[list[dict[str, Any]], int]:
    grouped: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for snapshot, row in rows:
        platform = _platform(row)
        video_id = _text(row.get("video_id"))
        if not video_id:
            raise CatalogError(f"{snapshot}: video_id is missing")
        raw_url = row.get("official_url") or row.get("source_url")
        _validate_video_url(platform, video_id, raw_url)
        grouped[(platform, video_id)].append((snapshot, row))

    result: list[dict[str, Any]] = []
    duplicate_rows = 0
    for (platform, video_id), group in sorted(grouped.items()):
        duplicate_rows += len(group) - 1
        ordered = sorted(group, key=lambda item: (_source_time_key(item[1]), item[0]))
        _, primary = ordered[-1]
        identity_by_snapshot = [(snapshot, _identity_values(row)) for snapshot, row in group]
        identity_conflicts: set[str] = set()
        fields = ("event", "discipline", "round", "side_a", "side_b", "unassigned_names")
        for field in fields:
            values = {json.dumps(identity[field], sort_keys=True, ensure_ascii=False) for _, identity in identity_by_snapshot if identity[field] not in (None, "UNKNOWN", [])}
            if len(values) > 1:
                identity_conflicts.add(field)

        identity = _identity_values(primary)
        for field in identity_conflicts:
            if field in {"side_a", "side_b"}:
                identity[field] = None
            elif field == "unassigned_names":
                identity[field] = []
            else:
                identity[field] = "UNKNOWN"

        title = _text(primary.get("display_title") or primary.get("original_title") or primary.get("title")) or "UNKNOWN"
        original_title = _text(primary.get("original_title") or primary.get("title")) or "UNKNOWN"
        content_type = _text(primary.get("content_type"))
        if content_type not in CONTENT_TYPES or content_type == "UNKNOWN":
            content_type = "FULL_MATCH" if primary.get("full_match") is True else "UNKNOWN"
        publisher = _text(primary.get("source_publisher") or primary.get("channel") or (primary.get("provenance") or {}).get("publisher")) or "UNKNOWN"
        publisher_url = _text((primary.get("provenance") or {}).get("publisher_url") or primary.get("channel_url"))
        latest_status = str(primary.get("playback_status") or "UNKNOWN")
        if latest_status not in PLAYBACK_STATES:
            latest_status = "UNKNOWN"
        provenance_rows = []
        external_observations = []
        embed_observations = []
        native_pass = False
        for snapshot, row in ordered:
            provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
            provenance_rows.append({
                "snapshot": snapshot,
                "recorded_at": _source_time(row),
                "metadata_method": _text(provenance.get("metadata_method")) or "UNKNOWN",
                "publisher_url": _text(provenance.get("publisher_url") or row.get("channel_url")),
                "category_evidence": _text(provenance.get("category_evidence")),
                "event_evidence": _text(provenance.get("event_evidence")),
                "full_match_evidence": _text(provenance.get("full_match_evidence") or row.get("full_match_evidence")),
                "availability_evidence": _text(provenance.get("availability_evidence")),
                "source_notice": _text(provenance.get("notice")),
                "playback_status_recorded": _text(row.get("playback_status")) or "UNKNOWN",
            })
            external_observations.extend(_external_observations(row, snapshot))
            embed = _embed_observation(row)
            if embed["technical_status"] != "NOT_TESTED" or embed["historical_attempt"]:
                embed_observations.append({"snapshot": snapshot, **embed})
            native_pass = native_pass or _explicit_native_pass(row)

        if any(item["visual_playback"] == "VISUAL_PASS_LIMITED" for item in external_observations):
            external_summary = "VISUAL_PASS_LIMITED"
        elif any(item["visual_playback"] == "RESTRICTED_OBSERVED" for item in external_observations):
            external_summary = "RESTRICTED_OBSERVED"
        elif any(item.get("page_accessible") is True for item in external_observations):
            external_summary = "PAGE_ACCESSIBLE_VISUAL_NOT_VERIFIED"
        else:
            external_summary = "NOT_TESTED"

        raw_rights = _text(primary.get("permission_status") or primary.get("rights")) or "REFERENCE_ONLY"
        local_analysis = primary.get("local_analysis_allowed")
        source_id = f"video-source:{platform.lower()}:{video_id}"
        record = {
            "catalog_record_id": f"catalog:{platform.lower()}:{video_id}",
            "source_id": source_id,
            "video_id": video_id,
            "platform": platform,
            "official_url": primary.get("official_url") or primary.get("source_url"),
            "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
            "title": title,
            "original_title": original_title,
            "event": identity["event"] or "UNKNOWN",
            "event_year": primary.get("event_year") if isinstance(primary.get("event_year"), int) else None,
            "match_date": _text(primary.get("match_date")),
            "match_type": identity["discipline"] if identity["discipline"] in DISCIPLINES else "UNKNOWN",
            "round": identity["round"] or "UNKNOWN",
            "participants_claimed": {
                "side_a": identity["side_a"],
                "side_b": identity["side_b"],
                "unassigned_names": identity["unassigned_names"],
                "identity_status": "SOURCE_METADATA_CLAIM" if identity["side_a"] or identity["side_b"] or identity["unassigned_names"] else "UNKNOWN",
            },
            "publisher": publisher,
            "publisher_url": publisher_url,
            "publisher_identity_status": "RECORDED_NOT_REVERIFIED" if publisher_url else "UNKNOWN",
            "source_verified_at": _source_time(primary),
            "source_identity_status": "CONFLICT_REVIEW_REQUIRED" if identity_conflicts else "SOURCE_METADATA_RECORDED_NOT_REVERIFIED",
            "identity_conflicts": sorted(identity_conflicts),
            "canonical_match_id": None,
            "match_link_status": "UNKNOWN",
            "content_type_claim": content_type,
            "completeness_status": "VERIFIED" if any(row.get("completeness_verified") is True for _, row in group) else "UNVERIFIED",
            "permission_status_recorded": raw_rights,
            "rights": {
                "public_listing": _source_permission(primary, "metadata_listing"),
                "external_viewing": _source_permission(primary, "external_viewing"),
                "thumbnail_display": _source_permission(primary, "thumbnail_display"),
                "embedding": _source_permission(primary, "embedding"),
                "local_analysis": "NOT_GRANTED" if local_analysis is False or "REFERENCE_ONLY" in raw_rights else _source_permission(primary, "local_analysis"),
                "redistribution": "NOT_GRANTED" if "REFERENCE_ONLY" in raw_rights else _source_permission(primary, "redistribution"),
                "evidence_status": "NO_SCOPED_PERMISSION_EVIDENCE",
            },
            "thumbnail": {
                "url": None,
                "source_has_thumbnail_url": any(bool(row.get("thumbnail_url")) for _, row in group),
                "display_status": "NOT_DISPLAYED_PERMISSION_UNKNOWN",
            },
            "availability": {
                "official_page_current": "NOT_TESTED",
                "external_video_visual_latest_recorded": external_summary,
                "external_observations": external_observations,
                "platform_embed": {
                    "permission": _source_permission(primary, "embedding"),
                    "latest_recorded_technical_status": _embed_observation(primary)["technical_status"],
                    "historical_attempts": embed_observations,
                },
                "desktop_native_playback": "PASS" if native_pass else "NOT_TESTED",
                "vision_analysis": "NOT_TESTED",
                "current_session_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
                "latest_recorded_playback_status": latest_status,
                "territory_availability": "UNKNOWN",
                "recorded_region_restriction": "RESTRICTED_OBSERVED" if any(item["visual_playback"] == "RESTRICTED_OBSERVED" for item in external_observations) or latest_status == "RESTRICTED" else "UNKNOWN",
            },
            "provenance": provenance_rows,
            "snapshot_count": len(group),
        }
        result.append(record)
    return result, duplicate_rows


def _safe_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return value


def _registry_records(registry: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_sources = registry.get("sources")
    raw_athletes = registry.get("athletes")
    raw_matches = registry.get("professional_matches")
    if not all(isinstance(value, list) for value in (raw_sources, raw_athletes, raw_matches)):
        raise CatalogError("Professional registry must contain sources, athletes and professional_matches arrays")
    sources_by_id = {row.get("source_id"): row for row in raw_sources if isinstance(row, dict) and _text(row.get("source_id"))}
    athletes_by_id = {row.get("athlete_id"): row for row in raw_athletes if isinstance(row, dict) and _text(row.get("athlete_id"))}
    if len(sources_by_id) != len(raw_sources) or len(athletes_by_id) != len(raw_athletes):
        raise CatalogError("Duplicate or invalid source/athlete IDs in professional registry")
    source_records = []
    for source_id, row in sorted(sources_by_id.items()):
        url = _safe_http_url(row.get("source_url"))
        if not url:
            raise CatalogError(f"Invalid evidence source URL: {source_id}")
        source_records.append({
            "source_id": source_id,
            "source_type": _text(row.get("source_type")) or "UNKNOWN",
            "url": url,
            "retrieved_at": _text(row.get("retrieved_at")),
            "description": _text(row.get("description")) or "UNKNOWN",
        })
    stars = []
    for athlete_id, row in sorted(athletes_by_id.items()):
        evidence_ids = row.get("source_ids") if isinstance(row.get("source_ids"), list) else []
        if any(source_id not in sources_by_id for source_id in evidence_ids):
            raise CatalogError(f"Missing athlete provenance source: {athlete_id}")
        profile_url = _safe_http_url(row.get("official_profile_url"))
        stars.append({
            "athlete_id": athlete_id,
            "name_en": _text(row.get("canonical_name_en")),
            "name_zh": _text(row.get("canonical_name_zh")),
            "association": _text(row.get("country_or_association")),
            "official_profile_url": profile_url,
            "profile_last_verified_at": _text(row.get("last_verified_at")),
            "evidence_source_ids": list(evidence_ids),
            "public_listing": _source_permission(row, "metadata_listing"),
            "equipment": {"status": "UNKNOWN", "items": []},
            "coach_observations": {"status": "NOT_COLLECTED", "items": []},
            "interviews": {"status": "NOT_COLLECTED", "items": []},
            "sponsorships": {"status": "NOT_COLLECTED", "items": []},
            "social_feedback": {"status": "NOT_COLLECTED", "items": []},
        })
    matches = []
    seen_matches: set[str] = set()
    for row in raw_matches:
        if not isinstance(row, dict) or not _text(row.get("match_id")):
            raise CatalogError("Invalid professional match record")
        match_id = row["match_id"]
        if match_id in seen_matches:
            raise CatalogError(f"Duplicate match_id: {match_id}")
        seen_matches.add(match_id)
        participant_ids = [row.get("player_a_id"), row.get("player_b_id")]
        if any(participant_id not in athletes_by_id for participant_id in participant_ids):
            raise CatalogError(f"Unknown participant athlete ID: {match_id}")
        source_ids = row.get("source_ids") if isinstance(row.get("source_ids"), list) else []
        if not source_ids or any(source_id not in sources_by_id for source_id in source_ids):
            raise CatalogError(f"Missing match provenance source: {match_id}")
        result = row.get("final_score") if isinstance(row.get("final_score"), dict) else None
        matches.append({
            "match_id": match_id,
            "identity_status": "REGISTERED_WITH_SOURCE_REFERENCES",
            "event": {
                "name": _text(row.get("event_name")) or "UNKNOWN",
                "event_id": _text(row.get("event_id")),
                "date": _text(row.get("event_date")),
                "competition_level": _text(row.get("competition_level")) or "UNKNOWN",
            },
            "match_type": "UNKNOWN",
            "round": _text(row.get("round")) or "UNKNOWN",
            "participants": [
                {"side": "A", "athlete_id": participant_ids[0], "name_en": _text(athletes_by_id[participant_ids[0]].get("canonical_name_en"))},
                {"side": "B", "athlete_id": participant_ids[1], "name_en": _text(athletes_by_id[participant_ids[1]].get("canonical_name_en"))},
            ],
            "recorded_result": result,
            "recorded_winner_id": _text(row.get("winner_id")),
            "result_status": "RECORDED_NOT_REVERIFIED",
            "reference_url": _safe_http_url(row.get("external_reference_url")),
            "evidence_source_ids": list(source_ids),
            "video_source_ids": [],
            "match_video_link_status": "UNKNOWN",
            "rights": {"public_listing": _source_permission(row, "metadata_listing"), "evidence_status": "NO_SCOPED_PERMISSION_EVIDENCE"},
        })
    return matches, stars, source_records


def _make_review_queue(video_sources: list[dict[str, Any]], matches: list[dict[str, Any]], stars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue = []
    for source in video_sources:
        pending = ["public_listing_permission", "external_viewing_terms", "current_page_availability", "territory_availability", "embedding_permission", "exact_match_link"]
        if source["thumbnail"]["source_has_thumbnail_url"]:
            pending.append("thumbnail_display_permission")
        if source["availability"]["desktop_native_playback"] != "PASS":
            pending.append("desktop_native_playback_evidence")
        queue.append({"record_type": "VIDEO_SOURCE", "record_id": source["source_id"], "pending_evidence": pending})
    for match in matches:
        queue.append({"record_type": "MATCH", "record_id": match["match_id"], "pending_evidence": ["public_listing_permission", "source_freshness_review", "match_type_if_required"]})
    for star in stars:
        queue.append({"record_type": "ATHLETE_PROFILE", "record_id": star["athlete_id"], "pending_evidence": ["public_listing_permission", "equipment_source_if_added", "coach_observation_source_if_added"]})
    return queue


def _source_manifest(root: Path, data_root: Path) -> list[dict[str, str]]:
    manifest = []
    for name in (*CATALOG_FILES, REGISTRY_FILE):
        path = data_root / name
        if not path.is_file():
            raise CatalogError(f"Missing source catalog file: {name}")
        manifest.append({"file": path.relative_to(root).as_posix(), "sha256": _sha256(path)})
    return manifest


def _public_permission(record: dict[str, Any]) -> bool:
    rights = record.get("rights")
    return isinstance(rights, dict) and rights.get("public_listing") == "ALLOWED"


def build_indexes(repo_root: Path, generated_at: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    root = repo_root.resolve()
    data_root = root / "products" / "ptti" / "data" / "professional"
    manifest = _source_manifest(root, data_root)
    all_rows: list[tuple[str, dict[str, Any]]] = []
    for filename in CATALOG_FILES:
        payload = _read_json(data_root / filename)
        key = "videos" if filename == "official_video_sources.json" else "entries"
        rows = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise CatalogError(f"{filename} must contain a {key} array")
        if any(not isinstance(row, dict) for row in rows):
            raise CatalogError(f"{filename} contains a non-object entry")
        all_rows.extend((filename, row) for row in rows)
    video_sources, duplicate_rows = _deduplicate_sources(all_rows)
    registry = _read_json(data_root / REGISTRY_FILE)
    matches, stars, evidence_sources = _registry_records(registry)
    now = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    source_counts = Counter(source["platform"] for source in video_sources)
    discipline_counts = Counter(source["match_type"] for source in video_sources)
    playback_counts = Counter(source["availability"]["latest_recorded_playback_status"] for source in video_sources)
    external_visual_pass = sum(source["availability"]["external_video_visual_latest_recorded"] == "VISUAL_PASS_LIMITED" for source in video_sources)
    native_pass = sum(source["availability"]["desktop_native_playback"] == "PASS" for source in video_sources)
    verified_complete = sum(source["completeness_status"] == "VERIFIED" for source in video_sources)
    public_counts = {
        "matches": sum(_public_permission(row) for row in matches),
        "video_sources": sum(source["rights"]["public_listing"] == "ALLOWED" for source in video_sources),
        "stars": sum(star["public_listing"] == "ALLOWED" for star in stars),
    }
    review = {
        "contract_version": CONTRACT_VERSION,
        "view": "INTERNAL_REVIEW",
        "generated_at": now,
        "source_manifest": manifest,
        "quality_summary": {
            "source_snapshot_rows": len(all_rows),
            "unique_video_sources": len(video_sources),
            "duplicate_snapshot_rows_removed": duplicate_rows,
            "registered_match_records": len(matches),
            "athlete_profiles": len(stars),
            "registry_evidence_sources": len(evidence_sources),
            "video_sources_by_platform": dict(sorted(source_counts.items())),
            "video_sources_by_match_type": dict(sorted(discipline_counts.items())),
            "latest_recorded_playback_status": dict(sorted(playback_counts.items())),
            "external_visual_playback_observed_limited": external_visual_pass,
            "desktop_native_playback_pass": native_pass,
            "completeness_verified": verified_complete,
            "catalog_video_match_links": sum(source["canonical_match_id"] is not None for source in video_sources),
            "public_eligible": public_counts,
            "interpretation": "Video source records are not canonical Match records unless an exact evidenced link is present; reference metadata does not grant rights or verify current playback.",
        },
        "matches": matches,
        "video_sources": video_sources,
        "local_video_assets": [],
        "stars": stars,
        "evidence_sources": evidence_sources,
        "rights_review_queue": _make_review_queue(video_sources, matches, stars),
        "analysis_compatibility": {
            "review_targets_version": REVIEW_TARGETS_VERSION,
            "review_evidence_pack_version": EVIDENCE_PACK_VERSION,
            "join_policy": "EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY",
            "automatic_join_by_title_or_player_name": False,
            "catalog_sources_linked_to_review_data": 0,
            "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
        },
        "notice": "Internal review index only. Do not serve this artifact as the public catalog. Source-file hashes identify snapshot bytes only; they do not establish match truth, media rights, current availability, complete-match status, or playback success.",
    }
    public = {
        "contract_version": CONTRACT_VERSION,
        "view": "STRICT_PUBLIC",
        "generated_at": now,
        "source_manifest": [],
        "matches": [row for row in matches if _public_permission(row)],
        "video_sources": [row for row in video_sources if row["rights"]["public_listing"] == "ALLOWED"],
        "local_video_assets": [],
        "stars": [row for row in stars if row["public_listing"] == "ALLOWED"],
        "evidence_sources": [],
        "rights_review_queue": [],
        "quality_summary": {
            "public_match_count": public_counts["matches"],
            "public_video_source_count": public_counts["video_sources"],
            "public_star_count": public_counts["stars"],
            "excluded_reference_only_records": len(video_sources),
            "exclusion_reason": "No scoped, evidenced public metadata-listing permission is present in these snapshots.",
        },
        "analysis_compatibility": {
            "review_targets_version": REVIEW_TARGETS_VERSION,
            "review_evidence_pack_version": EVIDENCE_PACK_VERSION,
            "join_policy": "EXACT_MATCH_ID_AND_SOURCE_ID_WITH_EVIDENCE_ONLY",
            "automatic_join_by_title_or_player_name": False,
            "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
        },
        "notice": "Strict public projection. Unknown rights are excluded; no review fallback is permitted.",
    }
    return review, public


def write_indexes(repo_root: Path, output_dir: Path, generated_at: str | None = None) -> tuple[Path, Path]:
    review, public = build_indexes(repo_root, generated_at=generated_at)
    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "match-library-internal-review.json"
    public_path = output_dir / "match-library-strict-public.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_path.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review_path, public_path
