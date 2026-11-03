#!/usr/bin/env python3
"""Create a minimal GOAL15 public package using recursive field allowlists.

The source package and internal review artifacts are read-only. This projection
retains the existing match-library-index/0.1 consumer contract while emitting a
new, versioned public delivery artifact.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
SOURCE_PATH = INTEGRATION_DIR / "generated" / "goal15-main-fan-universe-v0.1" / "match-library-strict-public.json"
OUTPUT_DIR = INTEGRATION_DIR / "generated" / "goal15-main-fan-universe-public-v0.2"
OUTPUT_PATH = OUTPUT_DIR / "match-library-strict-public.json"
HANDOFF_PATH = OUTPUT_DIR / "README-san-handoff.md"
SCHEMA_PATH = INTEGRATION_DIR / "contracts" / "match-library-index-v0.1.schema.json"

CONTRACT = "ptti.match-library-index/0.1"

# Per-object allowlists are intentionally explicit. New fields are excluded by
# default until reviewed for public purpose, provenance and rights implications.
ROOT_FIELDS = {
    "contract_version", "view", "generated_at", "source_manifest", "matches", "video_sources",
    "local_video_assets", "stars", "evidence_sources", "quality_summary",
    "rights_review_queue", "analysis_compatibility", "notice",
}
MATCH_FIELDS = {
    "match_id", "identity_status", "event", "match_type", "round", "round_zh",
    "display_title_zh", "participants", "recorded_result", "recorded_winner_id",
    "recorded_winner_name", "result_status", "reference_url", "provider_match_id",
    "evidence_source_ids", "video_source_ids", "match_video_link_status", "rights",
}
EVENT_FIELDS = {"name", "name_zh", "event_id", "event_year", "event_start", "event_end", "date", "competition_level"}
PARTICIPANT_FIELDS = {"side", "athlete_id", "name_en", "name_zh"}
RESULT_FIELDS = {"player_a_games", "player_b_games"}
MATCH_RIGHTS_FIELDS = {"public_listing", "evidence_status", "scope", "evidence_source_ids"}
VIDEO_SOURCE_FIELDS = {
    "catalog_record_id", "source_id", "video_id", "platform", "official_url", "watch_entry",
    "title", "original_title", "display_title_zh", "published_at", "event", "event_display_zh",
    "event_id", "event_year", "match_date", "match_type", "round", "round_zh",
    "participants_claimed", "publisher", "publisher_url", "publisher_identity_status",
    "source_verified_at", "source_identity_status", "identity_conflicts", "canonical_match_id",
    "match_link_status", "content_type_claim", "completeness_status", "permission_status_recorded",
    "rights", "thumbnail", "availability", "provenance",
}
CLAIMED_PARTICIPANTS_FIELDS = {"side_a", "side_b", "unassigned_names"}
VIDEO_RIGHTS_FIELDS = {
    "public_listing", "external_viewing", "thumbnail_display", "embedding", "local_analysis",
    "download", "redistribution", "evidence_status", "scope", "evidence_source_ids",
}
THUMBNAIL_FIELDS = {"url", "source_has_thumbnail_url", "display_status"}
AVAILABILITY_FIELDS = {
    "official_page_current", "external_video_visual_latest_recorded", "external_observations",
    "platform_embed", "desktop_native_playback", "vision_analysis", "current_session_eligibility",
    "latest_recorded_playback_status", "territory_availability", "recorded_region_restriction", "login_or_paywall",
}
OBSERVATION_FIELDS = {"surface", "checked_at", "page_accessible", "visual_playback", "observed_result", "limitations"}
EMBED_FIELDS = {"permission", "latest_recorded_technical_status", "historical_attempts"}
EMBED_ATTEMPT_FIELDS = {"result", "error_code", "date", "status"}
# Snapshot paths are deliberately excluded. Public provenance is represented by
# stable evidence IDs/URLs in evidence_sources and source-level evidence IDs.
PROVENANCE_FIELDS = {
    "recorded_at", "metadata_method", "source_id", "publisher_url", "event_evidence",
    "match_link_evidence", "source_rights_scope", "source_notice", "playback_status_recorded",
}
STAR_FIELDS = {
    "athlete_id", "name_en", "name_zh", "association", "official_profile_url",
    "profile_last_verified_at", "evidence_source_ids", "public_listing", "public_listing_scope",
    "equipment", "coach_observations", "interviews", "sponsorships", "social_feedback",
}
STATUS_ITEMS_FIELDS = {"status", "items"}
EVIDENCE_FIELDS = {"source_id", "source_type", "url", "retrieved_at", "description"}
ANALYSIS_FIELDS = {
    "review_targets_version", "review_evidence_pack_version", "join_policy",
    "automatic_join_by_title_or_player_name", "playback_eligibility",
}
CONTENT_TYPE_COUNT_FIELDS = ("FULL_MATCH", "HIGHLIGHTS", "SHORTS", "UNKNOWN")

_INTERNAL_VALUE_PATTERNS = (
    re.compile(r"(?i)products[\\/]ptti-integration[\\/]"),
    re.compile(r"(?i)[a-z]:\\(?:users|ptti|worktrees|temp|windows)\\"),
    re.compile(r"(?i)(?:goal\d+[-_][\w.-]*(?:fixture|admission|internal|review|candidate|snapshot)|candidate-review-internal)"),
)


class ProjectionError(ValueError):
    """Raised when an input cannot be safely projected for public consumption."""


def _copy_allowed(source: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key in allowed}


def _object_rows(source: dict[str, Any], field: str) -> list[dict[str, Any]]:
    rows = source.get(field)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ProjectionError(f"invalid-source-array:{field}")
    return rows


def _string_rows(source: dict[str, Any], field: str) -> list[str]:
    rows = source.get(field)
    if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
        raise ProjectionError(f"invalid-string-array:{field}")
    return rows


def _validate_public_urls(package: dict[str, Any]) -> None:
    for path, value in _walk_strings(package):
        final_key = path.rsplit(".", 1)[-1].split("[", 1)[0]
        if final_key in {"url", "official_url", "publisher_url", "reference_url", "official_profile_url"}:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ProjectionError(f"non-public-url-in-output:{path}")


def _validate_identity_edges(matches: list[dict[str, Any]], sources: list[dict[str, Any]], stars: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> None:
    def unique(rows: list[dict[str, Any]], key: str, error: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = row.get(key)
            if not isinstance(value, str) or not value or value in out:
                raise ProjectionError(error)
            out[value] = row
        return out

    matches_by_id = unique(matches, "match_id", "duplicate-or-missing-match-id")
    sources_by_id = unique(sources, "source_id", "duplicate-or-missing-source-id")
    unique(stars, "athlete_id", "duplicate-or-missing-athlete-id")
    evidence_by_id = unique(evidence, "source_id", "duplicate-or-missing-evidence-id")
    edge_count = 0
    for match in matches:
        for evidence_id in match.get("evidence_source_ids", []):
            if evidence_id not in evidence_by_id:
                raise ProjectionError("match-evidence-reference-missing")
        for evidence_id in match.get("rights", {}).get("evidence_source_ids", []):
            if evidence_id not in evidence_by_id:
                raise ProjectionError("match-rights-evidence-reference-missing")
        for source_id in match.get("video_source_ids", []):
            source = sources_by_id.get(source_id)
            if source is None or source.get("canonical_match_id") != match["match_id"] or source.get("match_link_status") != "HUMAN_VERIFIED":
                raise ProjectionError("match-video-edge-inconsistent")
            edge_count += 1
    for source in sources:
        match_id = source.get("canonical_match_id")
        if match_id is not None:
            match = matches_by_id.get(match_id)
            if match is None or source["source_id"] not in match.get("video_source_ids", []):
                raise ProjectionError("source-match-edge-inconsistent")
        for evidence_id in source.get("rights", {}).get("evidence_source_ids", []):
            if evidence_id not in evidence_by_id:
                raise ProjectionError("source-rights-evidence-reference-missing")
    for star in stars:
        if any(evidence_id not in evidence_by_id for evidence_id in star.get("evidence_source_ids", [])):
            raise ProjectionError("star-evidence-reference-missing")
    if edge_count != 5:
        raise ProjectionError("unexpected-exact-match-video-edge-count")


def _project_rights(rights: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return _copy_allowed(rights, allowed)


def _project_match(row: dict[str, Any]) -> dict[str, Any]:
    out = _copy_allowed(row, MATCH_FIELDS)
    if isinstance(row.get("event"), dict):
        out["event"] = _copy_allowed(row["event"], EVENT_FIELDS)
    if isinstance(row.get("participants"), list):
        if any(not isinstance(x, dict) for x in row["participants"]):
            raise ProjectionError("invalid-match-participants")
        out["participants"] = [_copy_allowed(x, PARTICIPANT_FIELDS) for x in row["participants"]]
    if isinstance(row.get("recorded_result"), dict):
        out["recorded_result"] = _copy_allowed(row["recorded_result"], RESULT_FIELDS)
    if isinstance(row.get("rights"), dict):
        out["rights"] = _project_rights(row["rights"], MATCH_RIGHTS_FIELDS)
        if "evidence_source_ids" in out["rights"]:
            out["rights"]["evidence_source_ids"] = _string_rows(out["rights"], "evidence_source_ids")
    for field in ("evidence_source_ids", "video_source_ids"):
        if field in out:
            out[field] = _string_rows(out, field)
    return out


def _project_source(row: dict[str, Any]) -> dict[str, Any]:
    out = _copy_allowed(row, VIDEO_SOURCE_FIELDS)
    if isinstance(row.get("participants_claimed"), dict):
        out["participants_claimed"] = _copy_allowed(row["participants_claimed"], CLAIMED_PARTICIPANTS_FIELDS)
        if "unassigned_names" in out["participants_claimed"]:
            out["participants_claimed"]["unassigned_names"] = _string_rows(out["participants_claimed"], "unassigned_names")
    if isinstance(row.get("rights"), dict):
        out["rights"] = _project_rights(row["rights"], VIDEO_RIGHTS_FIELDS)
        if "evidence_source_ids" in out["rights"]:
            out["rights"]["evidence_source_ids"] = _string_rows(out["rights"], "evidence_source_ids")
    if "identity_conflicts" in out:
        out["identity_conflicts"] = _string_rows(out, "identity_conflicts")
    if isinstance(row.get("thumbnail"), dict):
        out["thumbnail"] = _copy_allowed(row["thumbnail"], THUMBNAIL_FIELDS)
    availability = row.get("availability")
    if isinstance(availability, dict):
        projected = _copy_allowed(availability, AVAILABILITY_FIELDS)
        if isinstance(availability.get("external_observations"), list):
            projected["external_observations"] = [
                _copy_allowed(item, OBSERVATION_FIELDS) for item in _object_rows(availability, "external_observations")
            ]
        elif "external_observations" in availability:
            raise ProjectionError("invalid-source-array:external_observations")
        embed = availability.get("platform_embed")
        if isinstance(embed, dict):
            projected_embed = _copy_allowed(embed, EMBED_FIELDS)
            if isinstance(embed.get("historical_attempts"), list):
                projected_embed["historical_attempts"] = [
                    _copy_allowed(item, EMBED_ATTEMPT_FIELDS) for item in _object_rows(embed, "historical_attempts")
                ]
            projected["platform_embed"] = projected_embed
        out["availability"] = projected
    if isinstance(row.get("provenance"), list):
        out["provenance"] = [_copy_allowed(item, PROVENANCE_FIELDS) for item in _object_rows(row, "provenance")]
    elif "provenance" in row:
        raise ProjectionError("invalid-source-array:provenance")
    return out


def _project_star(row: dict[str, Any]) -> dict[str, Any]:
    out = _copy_allowed(row, STAR_FIELDS)
    if "evidence_source_ids" in out:
        out["evidence_source_ids"] = _string_rows(out, "evidence_source_ids")
    for key in ("equipment", "coach_observations", "interviews", "sponsorships", "social_feedback"):
        value = row.get(key)
        if isinstance(value, dict):
            out[key] = _copy_allowed(value, STATUS_ITEMS_FIELDS)
            if "items" in out[key] and out[key]["items"] != []:
                raise ProjectionError(f"unreviewed-public-star-items:{key}")
    return out


def _public_summary(matches: list[dict[str, Any]], sources: list[dict[str, Any]], stars: list[dict[str, Any]]) -> dict[str, Any]:
    match_ids = {row.get("match_id") for row in matches}
    exact_edges = sum(
        1 for source in sources
        if source.get("canonical_match_id") in match_ids
        and source.get("source_id") in next(
            (match.get("video_source_ids", []) for match in matches if match.get("match_id") == source.get("canonical_match_id")), []
        )
        and source.get("match_link_status") == "HUMAN_VERIFIED"
    )
    claims = {kind: sum(row.get("content_type_claim") == kind for row in sources) for kind in CONTENT_TYPE_COUNT_FIELDS}
    return {
        "public_match_count": len(matches),
        "public_video_source_count": len(sources),
        "public_star_count": len(stars),
        "public_match_video_link_count": exact_edges,
        "event_level_highlight_source_count": sum(
            row.get("content_type_claim") == "HIGHLIGHTS"
            and row.get("canonical_match_id") is None
            and row.get("match_link_status") == "UNKNOWN"
            for row in sources
        ),
        "current_session_playback_pass_count": sum(
            row.get("availability", {}).get("current_session_eligibility") == "PASS" for row in sources
        ),
        "official_embed_permission_count": sum(row.get("rights", {}).get("embedding") == "ALLOWED" for row in sources),
        "thumbnail_display_permission_count": sum(row.get("rights", {}).get("thumbnail_display") == "ALLOWED" for row in sources),
        "counts_notice": "Counts are calculated from this strict-public projection. Content-type labels are source claims, not verified completeness or playback. Official outbound links do not grant embed, thumbnail, local-analysis, download, or redistribution rights.",
        "content_type_claim_counts": claims,
        "full_match_completeness_verified_count": sum(
            row.get("content_type_claim") == "FULL_MATCH" and row.get("completeness_status") == "VERIFIED"
            for row in sources
        ),
        "shorts_source_count": claims["SHORTS"],
        "desktop_native_playback_pass_count": sum(
            row.get("availability", {}).get("desktop_native_playback") == "PASS" for row in sources
        ),
        "vision_analysis_pass_count": sum(
            row.get("availability", {}).get("vision_analysis") == "PASS" for row in sources
        ),
    }


def _walk_strings(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _assert_no_internal_paths_or_build_metadata(package: dict[str, Any]) -> None:
    forbidden_keys = {
        "goal11_internal_video_source_count", "goal14_highlight_candidate_review_count",
        "goal14_candidate_exact_video_id_count", "goal14_candidate_event_page_only_count",
        "goal14_highlight_links_admitted", "goal15_new_match_count", "goal15_new_source_count",
        "goal15_new_star_count", "snapshot", "snapshot_count",
    }
    def scan(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            leaked = forbidden_keys.intersection(value)
            if leaked:
                raise ProjectionError(f"internal-key-in-public-output:{path}")
            for key, child in value.items():
                scan(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f"{path}[{index}]")
    scan(package)
    for path, text in _walk_strings(package):
        if any(pattern.search(text) for pattern in _INTERNAL_VALUE_PATTERNS):
            raise ProjectionError(f"internal-path-or-build-reference-in-public-value:{path}")
    if package.get("source_manifest") != []:
        raise ProjectionError("public-source-manifest-must-be-empty")


def project_public_package(source: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if source.get("contract_version") != CONTRACT or source.get("view") != "STRICT_PUBLIC":
        raise ProjectionError("unsupported-source-contract-or-view")
    matches = [_project_match(row) for row in _object_rows(source, "matches")]
    video_sources = [_project_source(row) for row in _object_rows(source, "video_sources")]
    stars = [_project_star(row) for row in _object_rows(source, "stars")]
    evidence_sources = [
        _copy_allowed(row, EVIDENCE_FIELDS) for row in _object_rows(source, "evidence_sources")
    ]
    analysis = _copy_allowed(source.get("analysis_compatibility", {}), ANALYSIS_FIELDS)
    for field, value in analysis.items():
        if field == "automatic_join_by_title_or_player_name":
            if not isinstance(value, bool):
                raise ProjectionError("invalid-analysis-compatibility-boolean")
        elif not isinstance(value, str):
            raise ProjectionError("invalid-analysis-compatibility-scalar")
    package = {
        "contract_version": CONTRACT,
        "view": "STRICT_PUBLIC",
        "generated_at": generated_at,
        # v0.1 requires this field. Repository-local build/input manifests are
        # intentionally not published; source URLs and evidence IDs remain below.
        "source_manifest": [],
        "matches": matches,
        "video_sources": video_sources,
        "local_video_assets": [],
        "stars": stars,
        "evidence_sources": evidence_sources,
        "rights_review_queue": [],
        "quality_summary": _public_summary(matches, video_sources, stars),
        "analysis_compatibility": analysis,
        "notice": "This package contains only reviewed factual metadata and official outbound links. Media embedding, thumbnails, downloads, local analysis, redistribution, current access, and native playback remain ungranted, unknown, or untested unless an individual record states otherwise. No repository-local source files or internal review statistics are included.",
    }
    if set(package) - ROOT_FIELDS:
        raise ProjectionError("unexpected-root-field")
    _validate_identity_edges(matches, video_sources, stars, evidence_sources)
    _validate_public_urls(package)
    _assert_no_internal_paths_or_build_metadata(package)
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        raise ProjectionError("jsonschema-required-for-public-build") from exc
    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(package)
    return package


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ProjectionError("source-package-not-object")
    return value


def build(generated_at: str | None = None, source_path: Path = SOURCE_PATH) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return project_public_package(_load_json(source_path), timestamp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--generated-at", help="Override generated_at for reproducible output")
    args = parser.parse_args()
    package = build(args.generated_at, args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Write explicit UTF-8/LF bytes so the checked-in artifact SHA is stable on
    # Windows and Unix regardless of the caller's text-mode newline defaults.
    args.output.write_bytes((json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"public_package={args.output}")
    print(f"matches={len(package['matches'])} video_sources={len(package['video_sources'])} stars={len(package['stars'])}")
    print(f"source_manifest_entries={len(package['source_manifest'])} public_match_video_links={package['quality_summary']['public_match_video_link_count']}")
    print(f"highlights={package['quality_summary']['content_type_claim_counts']['HIGHLIGHTS']} unknown={package['quality_summary']['content_type_claim_counts']['UNKNOWN']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
