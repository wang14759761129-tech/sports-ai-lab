"""Build and validate a strict, additive Main match/highlight delta for San."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "products" / "ptti-integration" / "generated" / "goal27-match-experience-v0.1"
REVIEW_PATH = PACKAGE_DIR / "internal" / "review-source.json"
PUBLIC_PATH = PACKAGE_DIR / "public" / "match-experience-delta-v0.1.json"
SCHEMA_PATH = ROOT / "products" / "ptti-integration" / "contracts" / "match-experience-delta-v0.1.schema.json"
BASE_PATH = ROOT / "products" / "ptti-integration" / "generated" / "goal15-main-fan-universe-public-v0.2" / "match-library-strict-public.json"
BASE_SHA256 = "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930"
MATCH_ID = "match:ittf-doha-2025:ms:wang-chuqin-wong-chun-ting"
SOURCE_ID = "video-source:youtube:suwultS-Jcc"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_review(review: dict[str, Any]) -> None:
    if review.get("contract_version") != "ptti.main.match-experience-source-review/0.1":
        raise ValueError("unsupported-review-version")
    if review.get("base_catalog_sha256") != BASE_SHA256:
        raise ValueError("review-base-catalog-mismatch")
    event, match, video, rights = (review.get(key) for key in ("event", "match", "video", "rights_review"))
    if not all(isinstance(value, dict) for value in (event, match, video, rights)):
        raise ValueError("missing-review-record")
    if event.get("event_id") != "wtt-event:3108" or event.get("provider_event_id") != "3108":
        raise ValueError("event-identity-mismatch")
    if match.get("match_id") != MATCH_ID or match.get("provider_match_id") is not None:
        raise ValueError("match-identity-mismatch")
    if video.get("source_id") != SOURCE_ID or video.get("video_id") != "suwultS-Jcc":
        raise ValueError("video-identity-mismatch")
    if rights != {
        "public_listing": "ALLOWED", "external_viewing": "ALLOWED", "scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY",
        "embedding": "UNKNOWN", "thumbnail_display": "NOT_ALLOWED", "download": "NOT_GRANTED",
        "local_analysis": "NOT_GRANTED", "redistribution": "NOT_GRANTED", "rationale": rights.get("rationale"),
    }:
        raise ValueError("rights-scope-not-approved")
    if not rights.get("rationale") or "prior approval" not in rights["rationale"]:
        raise ValueError("rights-evidence-missing")
    if video.get("direct_fetch_observation", "").find("NOT_TESTED") < 0:
        raise ValueError("fetch-limitation-not-preserved")


def build_public_delta(review: dict[str, Any], generated_at: str) -> dict[str, Any]:
    """Project only enumerated public fields; internal review detail stays private."""
    _check_review(review)
    event = review["event"]
    match = review["match"]
    video = review["video"]
    rights_review = review["rights_review"]
    evidence = review["evidence"]
    evidence_by_id = {item["source_id"]: item for item in evidence}

    public_evidence = [
        {key: item[key] for key in ("source_id", "source_type", "url", "retrieved_at", "description")}
        for item in evidence
    ]
    public_match = {
        "match_id": match["match_id"],
        "provider_match_id": None,
        "identity_status": "METADATA_CROSSCHECKED_VISUAL_MATCH_NOT_TESTED",
        "event": {
            "name": event["name"],
            "event_id": event["event_id"],
            "date": match["date"],
            "competition_level": "WORLD_CHAMPIONSHIPS",
        },
        "match_type": match["match_type"],
        "round": "UNKNOWN",
        "participants": [
            {"side": person["side"], "athlete_id": person["athlete_id"], "name_en": person["name_en"]}
            for person in match["participants"]
        ],
        "recorded_result": {
            "player_a_games": match["recorded_result"]["player_a_games"],
            "player_b_games": match["recorded_result"]["player_b_games"],
            "game_scores": [[12, 10], [11, 6], [11, 5], [11, 7]],
        },
        "recorded_winner_id": match["recorded_winner_id"],
        "result_status": match["result_status"],
        "reference_url": event["url"],
        "evidence_source_ids": list(match["summary_evidence_source_ids"]),
        "video_source_ids": [video["source_id"]],
        "match_video_link_status": "HUMAN_VERIFIED",
        "rights": {
            "public_listing": "ALLOWED",
            "evidence_status": "FACTUAL_MATCH_METADATA_AND_OFFICIAL_LINK_ONLY",
            "scope": "MATCH_IDENTITY_AND_OFFICIAL_OUTBOUND_LINK_ONLY",
            "evidence_source_ids": list(match["summary_evidence_source_ids"]),
        },
    }
    if match["provider_match_id"] is not None:
        raise ValueError("provider-match-id-must-remain-unknown")

    source_evidence_ids = list(dict.fromkeys([
        video["metadata_evidence_source_id"], *video["match_identity_evidence_source_ids"], "youtube-share-link-help"
    ]))
    if not set(match["summary_evidence_source_ids"]).issubset(evidence_by_id):
        raise ValueError("unresolved-match-evidence")
    available_evidence_ids = set(evidence_by_id) | {"youtube-share-link-help"}
    if not set(source_evidence_ids).issubset(available_evidence_ids):
        raise ValueError("unresolved-source-evidence")

    public_source = {
        "catalog_record_id": "catalog:goal27:wtt-doha-2025-wang-wong-highlights",
        "source_id": video["source_id"],
        "video_id": video["video_id"],
        "platform": "YOUTUBE",
        "official_url": f"https://www.youtube.com/watch?v={video['video_id']}",
        "watch_entry": "OPEN_OFFICIAL_PLATFORM_URL",
        "source_published_at": video["published_at"],
        "title": video["title"],
        "display_title_zh": None,
        "event": event["name"],
        "event_display_zh": None,
        "event_year": event["year"],
        "match_type": match["match_type"],
        "round": "UNKNOWN",
        "round_zh": None,
        "participants_claimed": {"side_a": "Wong Chun Ting", "side_b": "Wang Chuqin"},
        "publisher": video["publisher"],
        "publisher_url": video["publisher_url"],
        "source_verified_at": review["reviewed_at"],
        "source_identity_status": "VERIFIED",
        "publisher_identity_status": "VERIFIED",
        "identity_conflicts": [],
        "canonical_match_id": match["match_id"],
        "match_link_status": "HUMAN_VERIFIED",
        "content_type_claim": video["category"],
        "completeness_status": "UNVERIFIED",
        "rights": {
            "public_listing": rights_review["public_listing"],
            "external_viewing": rights_review["external_viewing"],
            "thumbnail_display": rights_review["thumbnail_display"],
            "embedding": rights_review["embedding"],
            "download": rights_review["download"],
            "local_analysis": rights_review["local_analysis"],
            "redistribution": rights_review["redistribution"],
            "evidence_status": "SCOPED_EXTERNAL_LINK_ONLY_NO_MEDIA_USE_GRANT",
            "scope": rights_review["scope"],
            "evidence_source_ids": source_evidence_ids,
        },
        "thumbnail": {"url": None, "source_has_thumbnail_url": False, "display_status": "NOT_DISPLAYED"},
        "availability": {
            "official_page_current": "NOT_TESTED",
            "external_video_visual_latest_recorded": "NOT_TESTED",
            "external_observations": [{
                "surface": "OFFICIAL_YOUTUBE_METADATA_SEARCH_RESULT",
                "checked_at": review["reviewed_at"],
                "page_accessible": None,
                "visual_playback": "NOT_TESTED",
                "observed_result": "Official search metadata names both players and #ITTFWorlds2025; direct tool fetch was throttled, no frames were viewed.",
                "limitations": "System-browser opening, current territory, login/paywall and playback are not tested; this match highlight is not evidence of a complete match.",
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
        "provenance": [
            {"recorded_at": review["reviewed_at"], "metadata_method": "OFFICIAL_YOUTUBE_VIDEO_METADATA_SEARCH_RESULT", "source_id": video["metadata_evidence_source_id"], "source_rights_scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY", "playback_status_recorded": "NOT_TESTED"},
            {"recorded_at": review["reviewed_at"], "metadata_method": "OFFICIAL_ITTF_MATCH_RECAP_CROSSCHECK", "source_id": "ittf-doha-day4-wang-wong-2025", "source_rights_scope": "OFFICIAL_YOUTUBE_SHARE_URL_ONLY", "playback_status_recorded": "NOT_TESTED"},
        ],
    }
    delta = {
        "contract_version": "ptti.main.match-experience-delta/0.1",
        "view": "STRICT_PUBLIC_EXTERNAL_LINK_DELTA",
        "generated_at": generated_at,
        "base_catalog_contract": "ptti.match-library-index/0.1",
        "base_catalog_sha256": review["base_catalog_sha256"],
        "matches": [public_match],
        "video_sources": [public_source],
        "evidence_sources": public_evidence,
        "notice": "One match-linked WTT highlights external link. The match ID is PTTI-local; no provider match ID is claimed. Official-page access, external playback, completeness, territory, embed, thumbnail, download, local analysis, redistribution, native playback and Vision remain unverified or not granted.",
    }
    validate_public_delta(delta, _load_json(BASE_PATH))
    return delta


def validate_public_delta(delta: dict[str, Any], base: dict[str, Any]) -> None:
    schema = _load_json(SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(delta), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"schema-invalid:{errors[0].message}")
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != delta["base_catalog_sha256"]:
        raise ValueError("base-catalog-sha256-mismatch")
    base_match_ids = {row["match_id"] for row in base["matches"]}
    base_source_ids = {row["source_id"] for row in base["video_sources"]}
    evidence_ids = {row["source_id"] for row in base["evidence_sources"]} | {row["source_id"] for row in delta["evidence_sources"]}
    matches = {row["match_id"]: row for row in delta["matches"]}
    sources = {row["source_id"]: row for row in delta["video_sources"]}
    if len(matches) != len(delta["matches"]) or set(matches) & base_match_ids:
        raise ValueError("duplicate-or-base-match-id")
    if len(sources) != len(delta["video_sources"]) or set(sources) & base_source_ids:
        raise ValueError("duplicate-or-base-source-id")
    if set(matches) != {row["canonical_match_id"] for row in sources.values()}:
        raise ValueError("unmatched-source-reference")
    for match in matches.values():
        if any(source_id not in sources for source_id in match["video_source_ids"]):
            raise ValueError("unresolved-match-source-reference")
        if any(evidence_id not in evidence_ids for evidence_id in match["evidence_source_ids"]):
            raise ValueError("unresolved-match-evidence-reference")
    for source in sources.values():
        if source["source_id"] != f"video-source:{source['platform'].lower()}:{source['video_id']}":
            raise ValueError("source-id-url-mismatch")
        if source["official_url"] != f"https://www.youtube.com/watch?v={source['video_id']}":
            raise ValueError("source-url-video-id-mismatch")
        if any(evidence_id not in evidence_ids for evidence_id in source["rights"]["evidence_source_ids"]):
            raise ValueError("unresolved-rights-evidence-reference")
        if source["match_link_status"] != "HUMAN_VERIFIED" or source["canonical_match_id"] not in matches:
            raise ValueError("unverified-or-orphan-match-link")
        if source["content_type_claim"] != "HIGHLIGHTS" or source["completeness_status"] != "UNVERIFIED":
            raise ValueError("content-type-or-completeness-escalation")
        rights = source["rights"]
        if rights["external_viewing"] != "ALLOWED" or rights["embedding"] != "UNKNOWN" or rights["thumbnail_display"] != "NOT_ALLOWED" or rights["download"] != "NOT_GRANTED":
            raise ValueError("media-rights-escalation")
        if any(rights[key] != "NOT_GRANTED" for key in ("local_analysis", "redistribution")):
            raise ValueError("media-use-grant-escalation")
        availability = source["availability"]
        if any(availability[key] != "NOT_TESTED" for key in ("official_page_current", "external_video_visual_latest_recorded", "desktop_native_playback", "vision_analysis", "latest_recorded_playback_status")):
            raise ValueError("playback-evidence-escalation")
        if availability["territory_availability"] != "UNKNOWN" or availability["current_session_eligibility"] != "NOT_EVALUATED_CURRENT_SESSION":
            raise ValueError("availability-escalation")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Regenerate the public delta from the internal reviewed record")
    parser.add_argument("--validate", action="store_true", help="Validate the checked-in public delta against schema and pinned base")
    parser.add_argument("--generated-at", help="ISO timestamp used to make the package reproducible")
    args = parser.parse_args()
    if args.build:
        generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        delta = build_public_delta(_load_json(REVIEW_PATH), generated_at)
        PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_PATH.write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"BUILT {PUBLIC_PATH}")
        return 0
    delta = _load_json(PUBLIC_PATH)
    validate_public_delta(delta, _load_json(BASE_PATH))
    print(f"PASS {PUBLIC_PATH}: {len(delta['matches'])} match, {len(delta['video_sources'])} source, parent SHA verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
