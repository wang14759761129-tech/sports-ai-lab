from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
MANIFEST_PATH = REPO_ROOT / "products/ptti-integration/generated/goal16-public-media-v0.1/public-media-manifest.json"
SCHEMA_PATH = REPO_ROOT / "products/ptti-integration/contracts/public-media-manifest-v0.1.schema.json"
STRICT_PUBLIC_PACKAGE = REPO_ROOT / "products/ptti-integration/generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json"


class ManifestValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_data(data: dict[str, Any]) -> None:
    schema = load_json(SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors)
        raise ManifestValidationError(details)

    ids = [asset["asset_id"] for asset in data["assets"]]
    if len(ids) != len(set(ids)):
        raise ManifestValidationError("asset_id values must be unique")
    if data["strict_public_projection"]["count"] != len(data["strict_public_projection"]["eligible_asset_ids"]):
        raise ManifestValidationError("strict-public count does not match eligible_asset_ids")
    if data["strict_public_projection"]["count"] != data["coverage"]["strict_public_assets"]:
        raise ManifestValidationError("strict-public count does not match coverage")
    approved = [asset["asset_id"] for asset in data["assets"] if asset["display_permission"] == "ALLOWED"]
    if approved:
        raise ManifestValidationError("this review manifest is not an approval mechanism; assets must not be promoted here")
    if data["strict_public_projection"]["eligible_asset_ids"]:
        raise ManifestValidationError("candidate manifest may not populate the strict public projection")
    if any(asset["match_id"] is not None for asset in data["assets"]):
        raise ManifestValidationError("no Goal15 match-photo link has direct evidence")
    if any(asset["media_sha256"] is not None and asset["media_sha256_status"] != "COMPUTED_FROM_REVIEWED_LOCAL_COPY" for asset in data["assets"]):
        raise ManifestValidationError("media_sha256 may only be populated when computed from a reviewed local copy")
    if any(asset["media_sha256"] is None and asset["media_sha256_status"] != "NOT_COMPUTED_NO_DOWNLOAD" for asset in data["assets"]):
        raise ManifestValidationError("missing media_sha256 must remain explicitly uncomputed")


def validate_files() -> dict[str, int]:
    data = load_json(MANIFEST_PATH)
    validate_data(data)
    strict_public = load_json(STRICT_PUBLIC_PACKAGE)
    if strict_public.get("contract_version") != "ptti.match-library-index/0.1" or strict_public.get("view") != "STRICT_PUBLIC":
        raise ManifestValidationError("existing strict-public package identity changed")
    return {
        "candidate_assets": len(data["assets"]),
        "unresolved_leads": len(data["unresolved_leads"]),
        "strict_public_assets": data["strict_public_projection"]["count"],
        "existing_public_matches": len(strict_public.get("matches", [])),
    }


if __name__ == "__main__":
    summary = validate_files()
    print("PASS public media manifest v0.1")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
