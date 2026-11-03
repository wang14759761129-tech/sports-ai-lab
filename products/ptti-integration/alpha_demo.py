"""Build a repeatable, fixture-only PTTI Alpha data flow.

No database, network, local media, or user configuration is opened here.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from adapters import (
    CONTRACT_VERSION,
    UnsupportedContractVersion,
    adapt_local_video_asset,
    adapt_timeline_mapping,
    build_contract,
    require_exact_contract_version,
    to_web_safe_payload,
    validate_contract_integrity,
)


PACKAGE = Path(__file__).resolve().parent
FIXTURES = PACKAGE / "fixtures"
CONTRACT_SCHEMA = PACKAGE / "contracts" / "match-media-v0.2.schema.json"


def read_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _permissions_to_review(source: dict[str, Any]) -> list[dict[str, str]]:
    rights = source["rights"]
    details = {
        "metadata_listing": "Evidence that PTTI may index this source's match metadata.",
        "external_viewing": "Confirm the official destination and permitted link-out use.",
        "thumbnail_display": "An explicit image/display grant or applicable platform policy.",
        "embedding": "An explicit embed grant and a separate successful embed playback test.",
        "local_analysis": "Rights-holder evidence covering local analysis of this media.",
        "model_training": "A separate explicit grant for model training; do not infer from analysis rights.",
        "redistribution": "A separate explicit grant for copying or redistribution.",
    }
    pending = [
        {
            "source_id": source["source_id"],
            "field": field,
            "current": rights.get(field, "UNKNOWN"),
            "decision": "PENDING_REVIEW",
            "evidence_needed": details[field],
        }
        for field in details
        if rights.get(field) != "ALLOWED"
    ]
    territory = source.get("territory", {}).get("status", "UNKNOWN")
    if territory not in {"ALLOWED"}:
        pending.append(
            {
                "source_id": source["source_id"],
                "field": "territory",
                "current": territory,
                "decision": "PENDING_REVIEW",
                "evidence_needed": "A dated, territory-specific availability check; UNKNOWN is not global access.",
            }
        )
    evidence = source.get("evidence", {})
    embed_status = evidence.get("embed_playback", {}).get("status", "NOT_TESTED")
    if embed_status != "EMBED_PLAYBACK_PASS":
        pending.append(
            {
                "source_id": source["source_id"],
                "field": "embed_playback",
                "current": embed_status,
                "decision": "NOT_TESTED",
                "evidence_needed": "A successful, rights-permitted test in the intended Web player.",
            }
        )
    external = evidence.get("external_video_page", {})
    if external.get("status") == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS" and not external.get("evidence_ref"):
        pending.append(
            {
                "source_id": source["source_id"],
                "field": "external_evidence_reference",
                "current": "FIXTURE_SNAPSHOT_WITHOUT_EVIDENCE_REFERENCE",
                "decision": "REVIEW_REQUIRED",
                "evidence_needed": "A reviewable evidence reference and a fresh check before using this as current proof.",
            }
        )
    return pending


def build_alpha_demo() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a schema-valid v0.2 contract and a local-only audit sidecar."""
    web_records = read_fixture("web-match-records.json")
    desktop_source = read_fixture("desktop-video-source.json")
    untrusted = read_fixture("untrusted-inputs.json")
    local_raw = read_fixture("desktop-local-asset.json")

    # Keep deliberately dangling/unverified mapping candidates in the audit,
    # not as live edges in the contract.
    contract = build_contract(
        web_records=web_records,
        desktop_sources=[desktop_source, untrusted["desktop_source_without_rights"]],
        local_assets=[local_raw],
        timeline_mappings=[],
    )
    counts = validate_contract_integrity(contract)
    schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contract)
    )
    if errors:
        first = errors[0]
        raise ValueError(f"Contract schema validation failed at {list(first.path)}: {first.message}")

    # A v0.1 consumer must fail closed; the Alpha bundle never rewrites the
    # version or drops v0.2 fields to make an old consumer appear compatible.
    try:
        require_exact_contract_version(contract, "ptti.match-media/0.1")
    except UnsupportedContractVersion as exc:
        version_gate = {
            "status": "REJECTED_AS_REQUIRED",
            "expected": exc.expected_version,
            "received": exc.received_version,
            "code": exc.code,
        }
    else:  # pragma: no cover - defensive: contract version is a module constant
        raise AssertionError("v0.1 compatibility must reject the v0.2 payload")

    matches = {match["match_id"]: match for match in contract["matches"]}
    sources_by_match: dict[str, list[str]] = {}
    for source in contract["video_sources"]:
        if source.get("match_id"):
            sources_by_match.setdefault(source["match_id"], []).append(source["source_id"])

    real_sources = [
        source for source in contract["video_sources"]
        if not source["provenance"]["method"].startswith("synthetic-fixture:")
    ]
    public_projection = to_web_safe_payload(contract)
    identity_map = {
        "policy": {
            "match_id": "Stable only within the originating record namespace; cross-system identity needs an explicit reviewed crosswalk.",
            "video_source_id": "Source-scoped ID; do not merge sources by title, player names, or shared host.",
            "local_asset_id": "Local-only ID; never a public/Web identity and never exported as a path.",
            "timeline": "No cross-source time conversion without an explicit HUMAN_VERIFIED mapping and evidence.",
        },
        "match_sources": [
            {
                "match_id": match_id,
                "video_source_ids": sorted(source_ids),
                "link_status": "EXPLICIT_SOURCE_RECORD_ID",
                "identity_status": matches[match_id]["identity_status"],
            }
            for match_id, source_ids in sorted(sources_by_match.items())
        ],
        "local_assets": [
            {
                "local_asset_id": asset["local_asset_id"],
                "match_id": asset.get("match_id"),
                "association": (
                    "UNLINKED_REVIEW_REQUIRED"
                    if not asset.get("match_id")
                    else "HUMAN_VERIFIED_MATCH_ASSOCIATION"
                    if asset["provenance"]["review_status"] == "VERIFIED"
                    and asset["provenance"]["evidence_refs"]
                    else "EXPLICIT_ID_REVIEW_REQUIRED"
                ),
                "video_source_ids_for_match": sorted(
                    source["source_id"]
                    for source in contract["video_sources"]
                    if asset.get("match_id") and source.get("match_id") == asset["match_id"]
                ),
                "synthetic_fixture": asset["provenance"]["method"].startswith("synthetic-fixture:"),
                "actual_file_sha256": "NOT_TESTED_FIXTURE_DIGEST_ONLY",
                "local_video_source_edge": "MATCH_GROUP_ONLY_V0_2_HAS_NO_DIRECT_SOURCE_VERSION_ID",
            }
            for asset in contract["local_video_assets"]
        ],
    }

    rights_queue: list[dict[str, str]] = []
    for source in real_sources:
        rights_queue.extend(_permissions_to_review(source))
        if source.get("content_type") == "UNKNOWN":
            rights_queue.append(
                {
                    "source_id": source["source_id"],
                    "field": "content_type",
                    "current": "UNKNOWN",
                    "decision": "PENDING_REVIEW",
                    "evidence_needed": "Confirm whether the page is one complete match, highlights, a session, or an article.",
                }
            )

    local_asset_reviews = [
        {
            "local_asset_id": asset["local_asset_id"],
            "field": "actual_file_identity_and_rights",
            "current": "SYNTHETIC_FIXTURE_ONLY",
            "decision": "NOT_TESTED",
            "evidence_needed": "Select an authorized file, hash the actual bytes, record rights basis and review status; this demo did not read media.",
        }
        for asset in contract["local_video_assets"]
    ]

    mapping_raw = adapt_timeline_mapping(untrusted["unverified_timeline_mapping"])
    source_ids = {source["source_id"] for source in contract["video_sources"]}
    rejected_candidates = []
    if mapping_raw["from_source_id"] not in source_ids or mapping_raw["to_source_id"] not in source_ids:
        rejected_candidates.append(
            {
                "kind": "timeline_mapping",
                "mapping_id": mapping_raw["mapping_id"],
                "status": mapping_raw["status"],
                "decision": "REJECTED_NOT_A_CONTRACT_EDGE",
                "reason": "SOURCE_ENDPOINTS_NOT_PRESENT_IN_DEMO",
                "offset_ms": mapping_raw["offset_ms"],
                "required": "Exact source IDs, shared reviewed Match identity, and human evidence before any mapping can be added.",
            }
        )

    pending_hash_raw = copy.deepcopy(local_raw)
    pending_hash_raw["hash_status"] = "PENDING"
    try:
        adapt_local_video_asset(pending_hash_raw)
    except ValueError as exc:
        rejected_candidates.append(
            {
                "kind": "local_asset_hash",
                "local_asset_id": pending_hash_raw["local_asset_id"],
                "status": "PENDING",
                "decision": "REJECTED",
                "reason": "LOCAL_SOURCE_SHA256_NOT_VERIFIED",
                "detail": str(exc),
            }
        )
    else:  # pragma: no cover - the adapter must retain this safety guard
        raise AssertionError("Pending local SHA-256 was accepted")

    audit = {
        "audit_version": "ptti.alpha-demo-audit/0.1",
        "data_origin": "CHECKED_IN_SANITIZED_FIXTURE_SNAPSHOT",
        "runtime_access": {"database": "NOT_USED", "network": "NOT_USED", "local_media": "NOT_OPENED"},
        "schema": {"id": schema["$id"], "status": "PASS"},
        "integrity": {"status": "PASS", **counts},
        "v0_1_consumer": version_gate,
        "identity_map": identity_map,
        "web_projection": {
            "status": "SAFE_EMPTY" if not public_projection["video_sources"] else "SAFE_NONEMPTY",
            "match_count": len(public_projection["matches"]),
            "source_count": len(public_projection["video_sources"]),
            "local_asset_count": len(public_projection["local_video_assets"]),
            "reason": "Every real Web source has UNKNOWN listing or external-view permission; synthetic fixtures are excluded.",
        },
        "rights_review_queue": rights_queue,
        "local_asset_review_queue": local_asset_reviews,
        "rejected_candidates": rejected_candidates,
        "stored_external_visual_pass_snapshot_count": sum(
            source["evidence"]["external_video_page"]["status"] == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS"
            for source in real_sources
        ),
        "fresh_external_checks_this_run": 0,
        "desktop_native_playback_passes": 0,
        "vision_result_passes": 0,
    }
    return contract, audit


def contract_bytes(contract: dict[str, Any]) -> bytes:
    return (json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def audit_bytes(contract: dict[str, Any], audit: dict[str, Any]) -> bytes:
    result = copy.deepcopy(audit)
    result["contract_sha256"] = hashlib.sha256(contract_bytes(contract)).hexdigest()
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_demo_files(output_dir: Path, *, replace: bool = False) -> tuple[Path, Path]:
    """Write the v0.2 contract and review audit without silent overwrites."""
    contract, audit = build_alpha_demo()
    outputs = (
        (output_dir / "alpha-demo-ptti.match-media-0.2.json", contract_bytes(contract)),
        (output_dir / "alpha-demo-review-0.1.json", audit_bytes(contract, audit)),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, content in outputs:
        if path.exists():
            if path.read_bytes() == content:
                continue
            if not replace:
                raise FileExistsError(f"Refusing to overwrite different demo output: {path}; use --replace")
    for path, content in outputs:
        if path.exists() and path.read_bytes() == content:
            continue
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
    return outputs[0][0], outputs[1][0]
