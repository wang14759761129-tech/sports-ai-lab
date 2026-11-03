"""Build the strict, link-only GOAL22 fan inspiration data package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated" / "goal22-main-inspiration-v0.1"
BASE_PATH = ROOT / "generated" / "goal15-main-fan-universe-public-v0.2" / "match-library-strict-public.json"
DELTA_PATH = ROOT / "generated" / "goal17-1-real-content-v0.1" / "public" / "official-match-video-additions.json"
SUPPLEMENT_PATH = ROOT / "fixtures" / "goal22-public-additions-v0.1.json"
SCHEMA_PATH = ROOT / "contracts" / "fan-inspiration-v0.1.schema.json"
INTERNAL_PATH = GENERATED / "internal" / "review-register.json"
OUTPUT_PATH = GENERATED / "public" / "fan-inspiration-v0.1.json"

EXPECTED_BASE_SHA256 = "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930"
EXPECTED_DELTA_SHA256 = "6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@wttglobal"
GEAR_CATEGORIES = ("JERSEY", "SHOES", "BLADE", "RUBBER")


class PackageError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _publish_date(description: str) -> str | None:
    match = re.search(r"published[_ ](\d{4})[-_](\d{2})[-_](\d{2})", description, re.IGNORECASE)
    if not match:
        return None
    return "-".join(match.groups())


def _event_id_from_sources(source: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str | None:
    referenced = set(source.get("rights", {}).get("evidence_source_ids", []))
    for item in source.get("provenance", []):
        if item.get("event_evidence"):
            referenced.add(item["event_evidence"])
        referenced.update(item.get("match_link_evidence", []))
    for evidence_id in referenced:
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            continue
        url = str(evidence.get("url", ""))
        found = re.search(r"[?&]eventId=(\d+)", url)
        if found:
            return found.group(1)
        found = re.search(r"evidence:wtt-event:(\d+)$", evidence_id)
        if found:
            return found.group(1)
    return None


def _verification(
    *,
    publisher_status: str,
    source_status: str,
    match_status: str,
    metadata_status: str,
    checked_at: str | None,
    page_status: str,
) -> dict[str, Any]:
    return {
        "publisher_identity": "VERIFIED" if "VERIFIED" in publisher_status else "UNKNOWN",
        "source_identity": "VERIFIED" if ("VERIFIED" in source_status or "OFFICIAL_TITLE_METADATA_FOUND" in source_status) else "UNKNOWN",
        "match_link": match_status,
        "metadata_status": metadata_status,
        "metadata_checked_at": checked_at,
        "official_page_open": page_status,
        "external_system_browser_open": "NOT_TESTED",
        "video_started": "NOT_TESTED",
        "complete_watch": "UNVERIFIED",
        "desktop_native_playback": "NOT_TESTED",
        "vision_analysis": "NOT_TESTED",
        "territory": "UNKNOWN",
    }


def _category(claim: str, title: str, has_match: bool) -> str:
    upper = f"{claim} {title}".upper()
    if "SEASON_HIGHLIGHTS" in upper or "WTT 2025 WRAPPED" in upper:
        return "SEASON_HIGHLIGHTS_TITLE_CLAIM"
    if claim in {"FULL_MATCH", "FULL_MATCH_TITLE_CLAIM"} or "FULL MATCH" in title.upper():
        return "FULL_MATCH_TITLE_CLAIM"
    if claim in {"HIGHLIGHTS", "EVENT_HIGHLIGHTS_TITLE_CLAIM"} or "HIGHLIGHT" in title.upper() or "TOP POINT" in title.upper():
        return "EVENT_HIGHLIGHTS_TITLE_CLAIM"
    return "MATCH_SPECIFIC_TYPE_UNKNOWN" if has_match else "EVENT_LEVEL_TYPE_UNKNOWN"


def _public_rights(rights: dict[str, Any]) -> dict[str, str]:
    public_listing = rights.get("public_listing")
    external = rights.get("external_viewing")
    if public_listing != "ALLOWED" and public_listing != "ALLOWED_EXTERNAL_LINK_ONLY":
        raise PackageError("source_not_admitted_for_public_listing")
    if external not in {"ALLOWED", "ALLOWED_WITHIN_PLATFORM_LINK_SHARING_SCOPE"}:
        raise PackageError("source_not_admitted_for_external_link")
    embed = rights.get("embedding", rights.get("embed"))
    if embed not in {None, "UNKNOWN", "UNKNOWN_NOT_GRANTED"}:
        raise PackageError("unsupported_embed_permission_in_strict_link_only_package")
    thumbnail = rights.get("thumbnail_display")
    if thumbnail not in {None, "NOT_ALLOWED", "NOT_GRANTED_PENDING_WRITTEN_APPROVAL", "NOT_GRANTED_PENDING_APPROVAL"}:
        raise PackageError("unsupported_thumbnail_permission_in_strict_link_only_package")
    for field in ("download", "local_analysis", "redistribution"):
        if rights.get(field) not in {None, "NOT_GRANTED"}:
            raise PackageError(f"unsupported_{field}_permission_in_strict_link_only_package")
    return {
        "public_listing": "ALLOWED" if public_listing == "ALLOWED" else "ALLOWED_EXTERNAL_LINK_ONLY",
        "external_viewing": external,
        "embed": "UNKNOWN_NOT_GRANTED",
        "thumbnail_display": "NOT_ALLOWED" if thumbnail == "NOT_ALLOWED" else "NOT_GRANTED_PENDING_APPROVAL",
        "download": "NOT_GRANTED",
        "local_analysis": "NOT_GRANTED",
        "redistribution": "NOT_GRANTED",
    }


def _rights_from_goal17_delta(source: dict[str, Any]) -> dict[str, Any]:
    """Translate only the already-admitted Goal 17.1 official-link scope."""
    if source.get("publisher_status") != "OFFICIAL_VERIFIED_CHANNEL":
        raise PackageError("goal17_source_not_officially_verified")
    if source.get("watch_route") != "OFFICIAL_EXTERNAL_LINK_ONLY":
        raise PackageError("goal17_source_route_not_external_link_only")
    if source.get("embed_permission") != "UNKNOWN_NOT_GRANTED":
        raise PackageError("goal17_embed_permission_not_unknown_not_granted")
    if source.get("thumbnail_display_permission") not in {"NOT_GRANTED_PENDING_WRITTEN_APPROVAL", "NOT_ALLOWED"}:
        raise PackageError("goal17_thumbnail_permission_not_denied_or_pending")
    for key in ("download_permission", "local_analysis_permission", "redistribution_permission"):
        if source.get(key) != "NOT_GRANTED":
            raise PackageError(f"goal17_{key}_not_denied")
    if source.get("playback_status") != "NOT_TESTED" or source.get("territory_status") != "UNKNOWN":
        raise PackageError("goal17_playback_or_territory_state_changed_requires_review")
    return {
        "public_listing": "ALLOWED_EXTERNAL_LINK_ONLY",
        "external_viewing": "ALLOWED_WITHIN_PLATFORM_LINK_SHARING_SCOPE",
        "embedding": "UNKNOWN_NOT_GRANTED",
        "thumbnail_display": source["thumbnail_display_permission"],
        "download": source["download_permission"],
        "local_analysis": source["local_analysis_permission"],
        "redistribution": source["redistribution_permission"],
    }


def _base_item(
    source: dict[str, Any],
    *,
    match_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    rights_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_id = source["source_id"]
    video_id = source.get("video_id") or source.get("provider_video_id")
    url = source.get("official_url") or source.get("watch_url")
    if not video_id or not url:
        raise PackageError("source_missing_explicit_video_id_or_original_url")
    if url != f"https://www.youtube.com/watch?v={video_id}":
        raise PackageError("source_video_id_original_url_mismatch")
    if not source_id.endswith(video_id):
        raise PackageError("source_id_video_id_mismatch")
    rights = rights_override if rights_override is not None else source.get("rights", {})
    match_id = source.get("canonical_match_id") or source.get("match_id")
    match = match_by_id.get(match_id)
    participants: list[dict[str, Any]] = []
    if match:
        participants = match.get("participants", [])
    elif source.get("participants"):
        participants = source["participants"]
    athlete_ids = [p.get("athlete_id") for p in participants if p.get("athlete_id")]
    athlete_names = [p.get("name_en") or p.get("display_name") for p in participants if p.get("name_en") or p.get("display_name")]

    evidence_ids = set(rights.get("evidence_source_ids", []))
    for item in source.get("provenance", []):
        evidence_ids.update(item.get("match_link_evidence", []))
        if item.get("event_evidence"):
            evidence_ids.add(item["event_evidence"])
    published_at = source.get("source_published_at") or source.get("published_at")
    if not published_at:
        for evidence_id in evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence:
                published_at = _publish_date(evidence.get("description", ""))
                if published_at:
                    break
    event = match.get("event", {}) if match else {}
    event_id = event.get("event_id")
    if event_id is None:
        event_id = source.get("event_id")
    if event_id is None:
        event_id = _event_id_from_sources(source, evidence_by_id)
    if event_id is not None:
        event_id = str(event_id)
    event_name = event.get("name") or source.get("event_name") or source.get("event")
    event_year = event.get("event_year") or source.get("event_year")
    if not event_year and isinstance(event_name, str):
        year = re.search(r"20\d{2}", event_name)
        event_year = int(year.group(0)) if year else None
    claim = source.get("content_type_claim") or source.get("video_type_claim") or ""
    title = source.get("original_title") or source.get("title", "")
    category = _category(claim, title, bool(match_id))
    match_link = source.get("match_link_status")
    if not match_link:
        if match_id:
            match_link = "TITLE_ASSOCIATION_VISUAL_NOT_TESTED"
        else:
            match_link = "UNKNOWN"
    if match_link.startswith("OFFICIAL_VIDEO_TITLE_MATCH_ASSOCIATION"):
        match_link = "TITLE_ASSOCIATION_VISUAL_NOT_TESTED"
    source_checked_at = source.get("source_verified_at") or source.get("source_recorded_at")
    page_state = source.get("availability", {}).get("official_page_current")
    if page_state not in {"PARTIAL_METADATA_ONLY", "NOT_TESTED"}:
        page_state = "NOT_TESTED"
    return {
        "source_id": source_id,
        "platform": source.get("platform") or source.get("provider") or "YOUTUBE",
        "original_url": url,
        "original_title": title,
        "published_at": published_at,
        "publisher": source.get("publisher") or "World Table Tennis",
        "publisher_url": source.get("publisher_url") or YOUTUBE_CHANNEL_URL,
        "athlete_ids": athlete_ids,
        "athlete_names": athlete_names,
        "athlete_association_status": "MATCH_LINKED" if match_id and athlete_ids else ("UNMAPPED_TITLE_NAMES" if participants else "UNASSIGNED_EVENT_LEVEL"),
        "event_id": f"wtt-event:{event_id}" if event_id and not str(event_id).startswith("wtt-event:") else event_id,
        "event_name": event_name,
        "event_year": event_year,
        "match_id": match_id,
        "video_category": category,
        "full_match_completeness": "UNVERIFIED",
        "verification": _verification(
            publisher_status=source.get("publisher_identity_status") or source.get("publisher_status") or "UNKNOWN",
            source_status=source.get("source_identity_status") or source.get("source_page_status") or "UNKNOWN",
            match_status=match_link,
            metadata_status="VERIFIED_METADATA_BASELINE" if source_checked_at else "NOT_TESTED",
            checked_at=source_checked_at,
            page_status="PARTIAL_METADATA_ONLY" if page_state == "PARTIAL_METADATA_ONLY" else "NOT_TESTED",
        ),
        "rights": _public_rights(rights),
    }


def _normalise_supplement_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["source_id"],
        "platform": item["platform"],
        "original_url": item["original_url"],
        "original_title": item["original_title"],
        "published_at": item.get("published_at"),
        "publisher": item["publisher"],
        "publisher_url": item["publisher_url"],
        "athlete_ids": item["athlete_ids"],
        "athlete_names": item["athlete_names"],
        "athlete_association_status": item["athlete_association_status"],
        "event_id": item.get("event_id"),
        "event_name": item.get("event_name"),
        "event_year": item.get("event_year"),
        "match_id": item.get("match_id"),
        "video_category": item["video_category"],
        "full_match_completeness": "UNVERIFIED",
        "verification": item["verification"],
        "rights": _public_rights(item["rights"]),
    }


def _gear_dossier(match: dict[str, Any]) -> dict[str, Any]:
    participants = []
    for participant in match.get("participants", []):
        name = participant.get("name_en") or participant.get("display_name") or "UNKNOWN"
        participants.append({
            "athlete_id": participant.get("athlete_id"),
            "athlete_name": name,
            "match_specific_status": "NOT_VERIFIED",
            "items": [{"category": category, "brand": None, "model": None, "status": "UNKNOWN"} for category in GEAR_CATEGORIES],
        })
    return {
        "match_id": match["match_id"],
        "participants": participants,
        "evidence_status": "NOT_VERIFIED_FOR_SPECIFIC_MATCH",
        "public_note": "本场球衣、球鞋、底板和胶皮均没有足以绑定到该场比赛的核验记录；不依据品牌产品页或未核实画面推断。",
    }


def _watch_routes(all_source_ids: list[str], replay_source_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "mode": "OFFICIAL_EMBED", "priority": 1,
            "state": "BLOCKED_NO_EXPLICIT_EMBED_PERMISSION", "source_ids": [], "playback_evidence": "NOT_TESTED",
            "fallback_behavior": "不创建iframe；embed permission未知或未授予时，显示官方外链选项（如果该来源单独满足外链条件）。",
        },
        {
            "mode": "OFFICIAL_PAGE", "priority": 2,
            "state": "OUTBOUND_LINKS_REGISTERED_PLAYBACK_NOT_TESTED", "source_ids": all_source_ids, "playback_evidence": "NOT_TESTED",
            "fallback_behavior": "由用户选择打开原始官方平台页；外部浏览器打开、画面播放、地区可用性仍分别未测试。",
        },
        {
            "mode": "AUTHORIZED_SOURCE", "priority": 3,
            "state": "NO_AUTHORIZED_SOURCE_REGISTERED", "source_ids": [], "playback_evidence": "NOT_TESTED",
            "fallback_behavior": "没有独立授权转播方记录时不显示该选项，也不从官方外链推导授权。",
        },
        {
            "mode": "REPLAY", "priority": 4,
            "state": "OFFICIAL_REPLAY_LINKS_NOT_PLAYBACK_VERIFIED", "source_ids": replay_source_ids, "playback_evidence": "NOT_TESTED",
            "fallback_behavior": "保留原站链接并显示标题类型；高光不替代整场，FULL_MATCH标题不等于完整性或可播放验证。",
        },
        {
            "mode": "LIVE_SCORE", "priority": 5,
            "state": "NO_LIVE_SCORE_VERIFIED", "source_ids": [], "playback_evidence": "NOT_TESTED",
            "fallback_behavior": "没有当前LIVE_VERIFIED比分源时隐藏实时比分状态；不得将赛事页或历史赛果标成直播。",
        },
    ]


def build_package(*, generated_at: str | None = None) -> dict[str, Any]:
    base_bytes = BASE_PATH.read_bytes()
    delta_bytes = DELTA_PATH.read_bytes()
    supplement_bytes = SUPPLEMENT_PATH.read_bytes()
    base_sha = hashlib.sha256(base_bytes).hexdigest()
    delta_sha = hashlib.sha256(delta_bytes).hexdigest()
    if base_sha != EXPECTED_BASE_SHA256:
        raise PackageError("base_public_package_sha_changed_requires_review")
    if delta_sha != EXPECTED_DELTA_SHA256:
        raise PackageError("goal17_public_delta_sha_changed_requires_review")
    base = json.loads(base_bytes.decode("utf-8-sig"))
    delta = json.loads(delta_bytes.decode("utf-8-sig"))
    supplement = json.loads(supplement_bytes.decode("utf-8-sig"))
    if base.get("view") != "STRICT_PUBLIC" or delta.get("view") != "STRICT_PUBLIC_EXTERNAL_LINK_DELTA":
        raise PackageError("input_view_not_strict_public")
    if supplement.get("contract_version") != "ptti.goal22-public-additions/0.1":
        raise PackageError("unknown_goal22_supplement_contract")
    allowed_supplement_keys = {"contract_version", "video_content", "international_reactions", "gear_match_ids"}
    if set(supplement) != allowed_supplement_keys:
        raise PackageError("goal22_supplement_has_unapproved_fields")
    if len(base.get("matches", [])) != 5 or len(delta.get("matches", [])) != 2 or len(base.get("stars", [])) != 8:
        raise PackageError("baseline_content_counts_changed_requires_review")
    if len(base.get("video_sources", [])) != 15 or len(delta.get("video_sources", [])) != 2:
        raise PackageError("baseline_source_counts_changed_requires_review")

    base_matches = {m["match_id"]: m for m in base["matches"]}
    delta_matches = {m["match_id"]: m for m in delta["matches"]}
    match_by_id = {**base_matches, **delta_matches}
    evidence_by_id = {e["source_id"]: e for e in base.get("evidence_sources", [])}
    evidence_by_id.update({e["source_id"]: e for e in delta.get("evidence_sources", [])})

    base_items = [_base_item(s, match_by_id=base_matches, evidence_by_id=evidence_by_id) for s in base["video_sources"]]
    delta_items = [
        _base_item(
            s,
            match_by_id=delta_matches,
            evidence_by_id=evidence_by_id,
            rights_override=_rights_from_goal17_delta(s),
        )
        for s in delta["video_sources"]
    ]
    supplement_items = list(supplement.get("video_content", []))
    for item in supplement_items:
        if set(item) != {
            "source_id", "platform", "video_id", "original_url", "original_title", "published_at", "publisher", "publisher_url",
            "athlete_ids", "athlete_names", "athlete_association_status", "event_id", "event_name", "event_year", "match_id",
            "video_category", "full_match_completeness", "verification", "rights",
        }:
            raise PackageError("supplement_video_has_unapproved_fields")
        if item["platform"] != "YOUTUBE" or item["original_url"] != f"https://www.youtube.com/watch?v={item['video_id']}":
            raise PackageError("supplement_video_url_identity_mismatch")
    supplement_items = [_normalise_supplement_item(item) for item in supplement_items]

    all_items = base_items + delta_items + supplement_items
    source_ids = [item["source_id"] for item in all_items]
    urls = [item["original_url"] for item in all_items]
    if len(source_ids) != len(set(source_ids)) or len(urls) != len(set(urls)):
        raise PackageError("duplicate_video_source_id_or_url")
    if len(all_items) != 18:
        raise PackageError("expected_17_existing_plus_1_new_video_source")

    clips = [item for item in all_items if item["video_category"] in {"EVENT_HIGHLIGHTS_TITLE_CLAIM", "SEASON_HIGHLIGHTS_TITLE_CLAIM"}]
    match_watch_sources = [item for item in all_items if item not in clips]
    for item in clips:
        if item["match_id"] is not None and item["video_category"] == "EVENT_HIGHLIGHTS_TITLE_CLAIM":
            raise PackageError("event_highlight_must_not_be_match_bound")
    if len(clips) != 11 or len(match_watch_sources) != 7:
        raise PackageError("unexpected_clips_or_watch_source_partition")

    reactions = supplement.get("international_reactions", [])
    for reaction in reactions:
        if reaction["credibility"]["audience_representativeness"] != "NOT_CLAIMED":
            raise PackageError("reaction_audience_representativeness_must_not_be_claimed")
    gear_match_ids = supplement.get("gear_match_ids", [])
    if len(gear_match_ids) != 3 or len(set(gear_match_ids)) != 3:
        raise PackageError("gear_dossiers_must_cover_three_distinct_matches")
    missing_gear_matches = [match_id for match_id in gear_match_ids if match_id not in match_by_id]
    if missing_gear_matches:
        raise PackageError("gear_dossier_match_not_in_strict_public_inputs")
    gear_dossiers = [_gear_dossier(match_by_id[mid]) for mid in gear_match_ids]
    replay_ids = [item["source_id"] for item in all_items if item["video_category"] == "FULL_MATCH_TITLE_CLAIM"]
    if len(replay_ids) != 5:
        raise PackageError("full_match_title_claim_count_mismatch")

    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    package = {
        "contract_version": "ptti.fan-inspiration/0.1",
        "generated_at": timestamp,
        "view": "STRICT_PUBLIC_METADATA_LINKS_ONLY",
        "input_identity": {
            "base_contract": "ptti.match-library-index/0.1",
            "base_sha256": base_sha,
            "goal17_delta_contract": "ptti.goal17.1-match-video-additions/0.1",
            "goal17_delta_sha256": delta_sha,
            "goal22_supplement_sha256": hashlib.sha256(supplement_bytes).hexdigest(),
        },
        "clips": clips,
        "match_watch_sources": match_watch_sources,
        "international_reactions": reactions,
        "gear_dossiers": gear_dossiers,
        "watch_routes": _watch_routes(source_ids, replay_ids),
        "notice": "Metadata and official outbound links only. No embed, thumbnail, download, local analysis, article reproduction, media redistribution, playback, or complete-watch permission is granted by this package.",
    }
    return package


def validate_package(package: dict[str, Any]) -> list[str]:
    import jsonschema

    schema = read_json(SCHEMA_PATH)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(package), key=lambda error: list(error.path))
    if errors:
        return [f"schema:{'/'.join(map(str, error.path))}:{error.message}" for error in errors]
    forbidden_keys = {"internal_path", "database_path", "local_video_path", "source_manifest", "review_queue", "build_log"}
    def visit(value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    found.append(f"forbidden_key:{key}")
                found.extend(visit(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(visit(child))
        return found
    failures = visit(package)
    if failures:
        return failures
    sources = package["clips"] + package["match_watch_sources"]
    if len({item["source_id"] for item in sources}) != 18 or len({item["original_url"] for item in sources}) != 18:
        return ["video_source_identity_not_unique"]
    if any(item["verification"]["video_started"] != "NOT_TESTED" for item in sources):
        return ["video_playback_evidence_escalated"]
    if any(item["verification"]["complete_watch"] != "UNVERIFIED" for item in sources):
        return ["completeness_evidence_escalated"]
    if any(
        item["video_category"] in {"EVENT_HIGHLIGHTS_TITLE_CLAIM", "SEASON_HIGHLIGHTS_TITLE_CLAIM"}
        and item["match_id"] is not None
        for item in sources
    ):
        return ["event_highlight_match_binding_escalated"]
    if any(item["rights"]["embed"] != "UNKNOWN_NOT_GRANTED" for item in sources):
        return ["embed_permission_escalated"]
    if any(item["rights"]["thumbnail_display"] not in {"NOT_ALLOWED", "NOT_GRANTED_PENDING_APPROVAL"} for item in sources):
        return ["thumbnail_permission_escalated"]
    if any(item["rights"][field] != "NOT_GRANTED" for item in sources for field in ("download", "local_analysis", "redistribution")):
        return ["media_use_permission_escalated"]
    if any(dossier["evidence_status"] != "NOT_VERIFIED_FOR_SPECIFIC_MATCH" for dossier in package["gear_dossiers"]):
        return ["gear_evidence_escalated"]
    if any(reaction["credibility"]["audience_representativeness"] != "NOT_CLAIMED" for reaction in package["international_reactions"]):
        return ["reaction_representativeness_escalated"]
    if len(package["watch_routes"]) != 5:
        return ["watch_route_coverage_mismatch"]
    return []


def write_internal_register() -> Path:
    package = {
        "record_version": "ptti.goal22-main-review-register/0.1",
        "as_of": "2026-10-20",
        "not_public": True,
        "review_notes": [
            {
                "topic": "clip-source-check",
                "source_url": "https://www.youtube.com/watch?v=-rlqmtZyP5E",
                "observation": "Read-only web search surfaced the exact WTT title, verified World Table Tennis publisher, 2026-01-03 publication date and WTT copyright notice; direct page open returned a web-tool internal error, so system-browser open and playback remain NOT_TESTED.",
                "decision": "ADMIT_METADATA_AND_OFFICIAL_OUTBOUND_LINK_ONLY",
                "source_evidence": "https://www.youtube.com/watch?v=-rlqmtZyP5E",
            },
            {
                "topic": "international-reaction",
                "source_url": "https://www.lemonde.fr/sport/article/2025/10/05/felix-lebrun-battu-avec-les-honneurs-en-finale-du-grand-smash-de-pekin_6644541_3242.html",
                "observation": "Read-only page fetch exposed the French article and publication date 2025-10-05. Only an original concise Chinese summary and outbound link are admitted; article text and imagery are not reproduced.",
                "decision": "ADMIT_SINGLE_ARTICLE_SUMMARY_AND_LINK; NOT_A_FAN_POLL",
                "source_evidence": "https://www.lemonde.fr/sport/article/2025/10/05/felix-lebrun-battu-avec-les-honneurs-en-finale-du-grand-smash-de-pekin_6644541_3242.html",
            },
            {
                "topic": "international-reaction-blocked-candidate",
                "source_url": "https://www.lequipe.fr/Tennis-de-table/Actualites/Felix-lebrun-apres-sa-defaite-en-finale-du-grand-smash-de-pekin-face-a-wang-chuqin-il-etait-au-dessus-pendant-l-ensemble-du-match/1599242",
                "observation": "Search result metadata surfaced, but direct read-only fetch returned HTTP 403. No alternate access method used and no content admitted to the public package.",
                "decision": "INTERNAL_ONLY_BLOCKED_403",
                "source_evidence": "https://www.lequipe.fr/Tennis-de-table/Actualites/Felix-lebrun-apres-sa-defaite-en-finale-du-grand-smash-de-pekin-face-a-wang-chuqin-il-etait-au-dessus-pendant-l-ensemble-du-match/1599242",
            },
            {
                "topic": "gear-match-specific-review",
                "observation": "Three dossiers cover China Smash 2025 men's singles final, China Smash 2025 women's singles final, and Singapore Smash 2026 men's singles final. No jersey, footwear, blade, or rubber entry was promoted to a match-specific fact. Official DHS product pages and a Butterfly Lin Yun-Ju equipment/sponsorship page are athlete/product-level references, not evidence that a particular model was used in the selected match. No visual inference was made.",
                "indirect_sources_reviewed": [
                    "https://dhssportsusa.com/products/dhs-sun-yingsha-classic-series-table-tennis-racket",
                    "https://dhssportsusa.com/products/dhs-wang-cq-national-edition-table-tennis-rubber",
                    "https://www.butterfly-global.com/en/sponsoring/detail/lin-yunju.html",
                    "https://butterflyonline.com/lin-yun-ju-x-zyre-03-interview/"
                ],
                "decision": "KEEP_ALL_SELECTED_MATCH_GEAR_UNKNOWN_UNTIL_MATCH_SPECIFIC_SOURCE",
            },
            {
                "topic": "source-boundaries",
                "observation": "The 17 inherited source rows preserve their existing baseline verification and rights states. Current web research updated no source playback status. New WTT season compilation is not match-bound. No cover image, thumbnail, media bytes, or article text is included in the strict public package.",
                "decision": "STRICT_PUBLIC_LINK_ONLY; PLAYBACK_NOT_TESTED",
            }
        ],
    }
    INTERNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    INTERNAL_PATH.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return INTERNAL_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-at", help="Override generated_at for a reproducible build")
    args = parser.parse_args()
    package = build_package(generated_at=args.generated_at)
    errors = validate_package(package)
    if errors:
        raise PackageError(";".join(errors))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_internal_register()
    print(json.dumps({
        "status": "PASS",
        "contract_version": package["contract_version"],
        "clips": len(package["clips"]),
        "match_watch_sources": len(package["match_watch_sources"]),
        "video_sources_total": len(package["clips"]) + len(package["match_watch_sources"]),
        "international_reactions": len(package["international_reactions"]),
        "gear_match_dossiers": len(package["gear_dossiers"]),
        "output": str(OUTPUT_PATH),
        "errors": errors,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
