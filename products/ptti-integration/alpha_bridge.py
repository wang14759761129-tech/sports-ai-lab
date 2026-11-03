"""Local Alpha RC bridge: real Web catalog, isolated binding sandbox, QA ledger.

No service, database, media, GUI, or network is opened. Sidecars leave the
strict match-media/0.2 schema intact and must be negotiated explicitly.
"""
from __future__ import annotations

import copy
from datetime import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from adapters import build_contract, _is_synthetic, _safe_id
from alpha_demo import read_fixture
from web_consumer import consume_contract, _validate_contract

BRIDGE_VERSION = "ptti.alpha-bridge/0.1"
BINDING_VERSION = "ptti.source-version-binding/0.1"
NATIVE_VERSION = "ptti.native-acceptance/0.1"
OPERATIONS = ("play", "pause", "fast_forward", "rewind", "seek")


def _hash(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def _ratio(value: Any) -> Fraction | None:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        return None
    numerator, denominator = value["numerator"], value["denominator"]
    if any(type(number) is not int or number <= 0 for number in (numerator, denominator)):
        return None
    return Fraction(numerator, denominator)


def inspect_binding(contract: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    """Validate a specific source version -> local bytes -> observed PTS edge.

    Never infer it from a filename, shared Match, FPS, or successful playback.
    A valid synthetic edge is SIMULATED_ONLY, never human/native evidence.
    """
    _validate_contract(contract)
    if not isinstance(binding, dict):
        raise ValueError("Source-version binding must be an object")
    if binding.get("binding_version") != BINDING_VERSION:
        raise ValueError("Unsupported source-version binding version")
    failures: list[str] = []
    source = next((row for row in contract["video_sources"] if row["source_id"] == binding.get("source_id")), None)
    asset = next((row for row in contract["local_video_assets"] if row["local_asset_id"] == binding.get("local_asset_id")), None)
    if source is None or asset is None:
        return {"status": "REJECTED", "failures": ["SOURCE_OR_ASSET_ID_NOT_FOUND"], "time_seconds": None}
    if _is_synthetic(source) != _is_synthetic(asset):
        failures.append("SYNTHETIC_REAL_BOUNDARY")
    if not source["match_id"] or source["match_id"] != asset["match_id"]:
        failures.append("EXPLICIT_MATCH_ID_MISMATCH")
    if not _safe_id(binding.get("source_version_id")):
        failures.append("SOURCE_VERSION_ID_MISSING")
    if binding.get("hash_status") != "VERIFIED" or not _hash(binding.get("source_version_sha256")):
        failures.append("SOURCE_VERSION_HASH_PENDING_OR_INVALID")
    elif binding["source_version_sha256"] != asset["source_sha256"]:
        failures.append("LOCAL_BYTES_HASH_MISMATCH")
    if binding.get("timeline_id") != asset["timeline"]["timeline_id"]:
        failures.append("TIMELINE_ID_MISMATCH")
    ratio = _ratio(binding.get("time_base"))
    if ratio is None or ratio != _ratio(asset["timeline"]["time_base"]):
        failures.append("TIME_BASE_MISSING_OR_MISMATCH")
    pts, origin = binding.get("observation_pts"), binding.get("origin_pts")
    if type(pts) is not int or type(origin) is not int or pts < origin:
        failures.append("PTS_OR_ORIGIN_INVALID")
    if binding.get("time_basis") != "SOURCE_PTS":
        failures.append("TIME_BASIS_UNVERIFIED")
    refs = binding.get("evidence_refs")
    if (binding.get("review_status") != "HUMAN_VERIFIED"
        or not _timestamp(binding.get("reviewed_at"))
        or not isinstance(refs, list) or not refs or not all(_safe_id(ref) for ref in refs)):
        failures.append("BINDING_REVIEW_EVIDENCE_MISSING")
    if failures:
        return {"status": "REJECTED", "failures": failures, "time_seconds": None}
    seconds = (pts - origin) * ratio
    duration = asset["timeline"].get("duration_ms")
    if duration is not None and seconds * 1000 > duration:
        return {"status": "REJECTED", "failures": ["PTS_OUTSIDE_MEDIA"], "time_seconds": None}
    return {"status": "SIMULATED_ONLY" if _is_synthetic(asset) else "BINDING_VERIFIED",
            "failures": [], "time_seconds": float(seconds)}


def inspect_native_acceptance(contract: dict[str, Any], report: dict[str, Any],
                              binding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep a user report observable without upgrading an unbound PASS claim."""
    _validate_contract(contract)
    if not isinstance(report, dict):
        raise ValueError("Native acceptance must be an object")
    if report.get("acceptance_version") != NATIVE_VERSION:
        raise ValueError("Unsupported native acceptance version")
    operations = report.get("operations")
    if not isinstance(operations, dict) or any(value not in {"USER_REPORTED_PASS", "PASS", "FAIL", "NOT_TESTED"} for value in operations.values()):
        raise ValueError("Invalid operation evidence")
    missing = []
    for key, length in (("app_git_sha", 40), ("exe_sha256", 64), ("source_sha256", 64)):
        if not _hash(report.get(key), length):
            missing.append(key)
    if not _timestamp(report.get("tested_at")):
        missing.append("tested_at")
    if not _safe_id(report.get("evidence_ref")):
        missing.append("evidence_ref")
    if not _safe_id(report.get("source_id")):
        missing.append("source_id")
    asset = next((row for row in contract["local_video_assets"] if row["local_asset_id"] == report.get("local_asset_id")), None)
    if asset is None:
        missing.append("local_asset_id")
    elif report.get("source_sha256") != asset["source_sha256"]:
        missing.append("source_sha256_asset_match")
    binding_result = inspect_binding(contract, binding) if binding is not None else None
    if binding_result is None or binding_result["status"] != "BINDING_VERIFIED":
        missing.append("verified_source_version_binding")
    elif (binding.get("source_id") != report.get("source_id")
          or binding.get("local_asset_id") != report.get("local_asset_id")):
        missing.append("acceptance_binding_ids")
    if report.get("environment") != "WINDOWS_NATIVE" or report.get("player") != "Cinema":
        missing.append("windows_native_cinema_context")
    if any(operations.get(key) not in {"PASS", "USER_REPORTED_PASS"} for key in OPERATIONS):
        missing.append("required_operations")
    return {"status": "UNBOUND_REVIEW_REQUIRED" if missing else "NATIVE_OPERATIONS_BOUND",
            "operations": copy.deepcopy(operations), "missing_bindings": missing,
            "vision_analysis": "NOT_TESTED", "full_qa": "NOT_TESTED"}


def binding_sandbox() -> tuple[dict[str, Any], dict[str, Any]]:
    """Explicit synthetic Match/VideoSource/LocalVideoAsset example; no media."""
    match_id = "web-match:synthetic-binding-sandbox"
    contract = build_contract(web_records=[{
        "fixture_only": True, "id": "synthetic-binding-sandbox", "identityStatus": "VERIFIED",
        "event": "PTTI synthetic binding sandbox", "discipline": "UNKNOWN",
        "players": ["Synthetic A", "Synthetic B"], "routeType": "video-page",
        "platformUrl": "https://fixture.example.test/video/sandbox", "platform": "SYNTHETIC",
    }], local_assets=[{
        **read_fixture("desktop-local-asset.json"), "match_id": match_id,
        "match_link_review_status": "VERIFIED", "match_link_evidence_refs": ["synthetic-association-01"],
    }])
    binding = {
        "binding_version": BINDING_VERSION, "source_id": "web-source:synthetic-binding-sandbox",
        "source_version_id": "fixture-version-01", "local_asset_id": "fixture-local-licensed-01",
        "hash_status": "VERIFIED", "source_version_sha256": "a" * 64,
        "timeline_id": "fixture-timeline-01", "time_base": {"numerator": 1, "denominator": 15360},
        "time_basis": "SOURCE_PTS", "observation_pts": 230400, "origin_pts": 0,
        "review_status": "HUMAN_VERIFIED", "reviewed_at": "2026-10-13T00:00:00Z",
        "evidence_refs": ["synthetic-binding-test-only"],
    }
    return contract, binding


def build_bridge(web_records: list[dict[str, Any]], native_report: dict[str, Any]) -> dict[str, Any]:
    contract = build_contract(web_records=web_records)
    _validate_contract(contract)
    if any(_is_synthetic(row) for row in contract["matches"] + contract["video_sources"]):
        raise ValueError("Real catalog rejects synthetic inputs")
    sandbox, binding = binding_sandbox()
    review = consume_contract(contract, view="review")
    public = consume_contract(contract, view="public")
    return {
        "bridge_version": BRIDGE_VERSION,
        "web": {"internal_review": review, "strict_public": public},
        "real_associations": [{"match_id": match["match_id"],
            "source_ids": [source["source_id"] for source in contract["video_sources"] if source["match_id"] == match["match_id"]],
            "local_asset_ids": [], "local_association_status": "NOT_ESTABLISHED"} for match in contract["matches"]],
        "native_acceptance": {"reported": copy.deepcopy(native_report), "assessment": inspect_native_acceptance(contract, native_report)},
        "desktop_fixture_sandbox": {"classification": "SYNTHETIC_ONLY_NOT_REAL_MATCH",
            "contract": sandbox, "binding": binding, "assessment": inspect_binding(sandbox, binding)},
        "counts": {"real_matches": len(review["matches"]), "real_sources": len(review["video_sources"]),
                   "public_sources": len(public["video_sources"]), "real_local_assets": 0},
    }


def write_bridge(output_dir: Path, bridge: dict[str, Any]) -> dict[str, str]:
    """Export separate Web JSON and private review sidecars without overwrites."""
    documents = {
        "web-internal-review.json": bridge["web"]["internal_review"],
        "web-strict-public.json": bridge["web"]["strict_public"],
        "desktop-synthetic-sandbox.json": bridge["desktop_fixture_sandbox"],
        "alpha-bridge-ledger.json": {key: value for key, value in bridge.items() if key not in {"web", "desktop_fixture_sandbox"}},
    }
    encoded = {name: (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8") for name, doc in documents.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in encoded.items():
        path = output_dir / name
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError(f"Refusing to replace differing Alpha export: {path}")
    for name, data in encoded.items():
        path = output_dir / name
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
    return {name: hashlib.sha256(data).hexdigest() for name, data in encoded.items()}
