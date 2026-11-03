from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image, ImageOps


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
REVIEW_PATH = REPO_ROOT / "products/ptti-integration/generated/goal16-media-clearance-v0.2/rights-review.json"
REVIEW_SCHEMA_PATH = REPO_ROOT / "products/ptti-integration/contracts/media-clearance-review-v0.2.schema.json"
PUBLIC_DIR = REPO_ROOT / "products/ptti-integration/generated/goal16-public-media-v0.2"
PUBLIC_PATH = PUBLIC_DIR / "public-media-manifest.json"
PUBLIC_SCHEMA_PATH = REPO_ROOT / "products/ptti-integration/contracts/public-media-manifest-v0.2.schema.json"
SOURCE_MANIFEST_PATH = REPO_ROOT / "products/ptti-integration/generated/goal16-public-media-v0.1/public-media-manifest.json"
OLD_STRICT_PACKAGE = REPO_ROOT / "products/ptti-integration/generated/goal15-main-fan-universe-public-v0.2/match-library-strict-public.json"
EXPECTED_SOURCE_MANIFEST_SHA = "e533ceeae42138a1bcf45099f0ea53180a29a7f21366e5f59d6ce8bebd837a49"
EXPECTED_APPROVED_IDS = {
    "commons:attc-2017:harimoto-1",
    "commons:jonathan-groth-portrait",
    "commons:acttc-2016:wang-manyu-17",
    "commons:acttc-2016:liang-jingkun-8",
}
PORTRAIT_SIZES = ((400, 500), (800, 1000))
LANDSCAPE_3_2_SIZES = ((480, 320), (960, 640))


class MediaPackageError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_schema(data: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = read_json(schema_path)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data),
        key=lambda error: list(error.path),
    )
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors)
        raise MediaPackageError(f"{label} schema invalid: {detail}")


def _asset_slug(asset_id: str) -> str:
    return asset_id.replace(":", "-")


def _local_original_path(asset: dict[str, Any]) -> Path:
    relative = PurePosixPath(asset["reviewed_original_relpath"])
    if relative.is_absolute() or ".." in relative.parts:
        raise MediaPackageError("reviewed original path must stay inside repository")
    return REPO_ROOT.joinpath(*relative.parts)


def _remove_obsolete_generated_derivatives(approved_assets: list[dict[str, Any]]) -> None:
    """Remove only stale WebP outputs whose allowlisted asset IDs are owned by this builder."""
    assets_dir = PUBLIC_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    known_prefixes = tuple(f"{_asset_slug(asset['asset_id'])}-" for asset in approved_assets)
    if not known_prefixes:
        raise MediaPackageError("refusing to clean generated assets with an empty allowlist")
    for path in assets_dir.glob("*.webp"):
        if path.name.startswith(known_prefixes):
            if path.is_symlink() or not path.is_file():
                raise MediaPackageError(f"refusing to clean a non-regular derivative path: {path.name}")
            path.unlink()
        else:
            raise MediaPackageError(f"unexpected file in generated public asset directory: {path.name}")


def build() -> dict[str, Any]:
    review = read_json(REVIEW_PATH)
    validate_schema(review, REVIEW_SCHEMA_PATH, "clearance review")
    source_manifest_bytes = SOURCE_MANIFEST_PATH.read_bytes()
    source_manifest_sha = sha256_bytes(source_manifest_bytes)
    if source_manifest_sha != EXPECTED_SOURCE_MANIFEST_SHA or review["source_manifest"]["sha256"] != source_manifest_sha:
        raise MediaPackageError("source manifest hash changed; re-review is required before projecting media")
    source_manifest = json.loads(source_manifest_bytes.decode("utf-8"))
    candidates = {asset["asset_id"]: asset for asset in source_manifest["assets"]}
    reviewed = {asset["asset_id"]: asset for asset in review["assets"]}
    if len(reviewed) != 9 or set(reviewed) != set(candidates):
        raise MediaPackageError("review must contain exactly the nine source-manifest candidates")

    approved = [asset for asset in review["assets"] if asset["clearance_status"] == "CLEARED_EDITORIAL_PROFILE_ONLY"]
    if {asset["asset_id"] for asset in approved} != EXPECTED_APPROVED_IDS:
        raise MediaPackageError("approved set differs from the explicitly reviewed editorial allowlist")

    # Validate every source and identity before touching any prior generated output.
    for item in approved:
        candidate = candidates[item["asset_id"]]
        source_path = _local_original_path(item)
        if not source_path.is_file():
            raise MediaPackageError(f"reviewed original missing: {item['asset_id']}")
        source_hash = sha256_file(source_path)
        if source_hash != item["source_sha256"]:
            raise MediaPackageError(f"reviewed original SHA-256 mismatch: {item['asset_id']}")
        if source_hash != candidate["media_sha256"] and candidate["media_sha256"] is not None:
            raise MediaPackageError(f"source manifest already has a conflicting media hash: {item['asset_id']}")
        if not item["athlete_id"] or item["athlete_id"] not in candidate["athlete_ids"]:
            raise MediaPackageError(f"public athlete identity is not bound in source manifest: {item['asset_id']}")
        with Image.open(source_path) as opened:
            opened.load()
            oriented = ImageOps.exif_transpose(opened)
            if oriented.size != (item["source_dimensions"]["width"], item["source_dimensions"]["height"]):
                raise MediaPackageError(f"source dimensions do not match the inspected file page: {item['asset_id']}")
            if item["derivative_policy"]["mode"] == "PRESERVE_SOURCE_3_2" and abs(oriented.width / oriented.height - 1.5) > 0.001:
                raise MediaPackageError(f"full-frame 3:2 policy does not match source aspect ratio: {item['asset_id']}")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    _remove_obsolete_generated_derivatives(approved)
    public_assets: list[dict[str, Any]] = []
    for item in approved:
        candidate = candidates[item["asset_id"]]
        source_path = _local_original_path(item)
        if not source_path.is_file():
            raise MediaPackageError(f"reviewed original missing: {item['asset_id']}")
        source_hash = sha256_file(source_path)
        if source_hash != item["source_sha256"]:
            raise MediaPackageError(f"reviewed original SHA-256 mismatch: {item['asset_id']}")
        if source_hash != candidate["media_sha256"] and candidate["media_sha256"] is not None:
            raise MediaPackageError(f"source manifest already has a conflicting media hash: {item['asset_id']}")
        if not item["athlete_id"] or item["athlete_id"] not in candidate["athlete_ids"]:
            raise MediaPackageError(f"public athlete identity is not bound in source manifest: {item['asset_id']}")

        with Image.open(source_path) as opened:
            opened.load()
            oriented = ImageOps.exif_transpose(opened)
            if oriented.size != (item["source_dimensions"]["width"], item["source_dimensions"]["height"]):
                raise MediaPackageError(f"source dimensions do not match the inspected file page: {item['asset_id']}")
            rgb = oriented.convert("RGB")

        derivative_rows: list[dict[str, Any]] = []
        slug = _asset_slug(item["asset_id"])
        policy = item["derivative_policy"]
        sizes = PORTRAIT_SIZES if policy["mode"] == "CENTER_CROP_4_5" else LANDSCAPE_3_2_SIZES
        if policy["mode"] == "PRESERVE_SOURCE_3_2" and abs(rgb.width / rgb.height - 1.5) > 0.001:
            raise MediaPackageError(f"full-frame 3:2 policy does not match source aspect ratio: {item['asset_id']}")
        change_note = (
            "4:5 center crop; resized; JPEG converted to WebP; EXIF/GPS metadata removed"
            if policy["mode"] == "CENTER_CROP_4_5"
            else "3:2 full-frame resize; JPEG converted to WebP; EXIF/GPS metadata removed"
        )
        for width, height in sizes:
            derivative_path = PUBLIC_DIR / "assets" / f"{slug}-{width}x{height}.webp"
            derivative_path.parent.mkdir(parents=True, exist_ok=True)
            if policy["mode"] == "CENTER_CROP_4_5":
                derivative = ImageOps.fit(rgb, (width, height), method=Image.Resampling.LANCZOS, centering=tuple(policy["centering"]))
            else:
                derivative = rgb.resize((width, height), Image.Resampling.LANCZOS)
            derivative.save(derivative_path, format="WEBP", quality=88, method=6, exif=b"")
            derivative_rows.append({
                "path": derivative_path.relative_to(PUBLIC_DIR).as_posix(),
                "sha256": sha256_file(derivative_path),
                "width": width,
                "height": height,
                "format": "WEBP",
                "license": item["license"],
                "changes_made": change_note,
                "metadata_stripped": True,
            })

        title = unquote(item["source_page_url"].rsplit("File:", 1)[-1]).replace("_", " ")
        credit = item["photographer"]
        source_page = item["source_page_url"]
        license_url = (
            "https://creativecommons.org/licenses/by-sa/2.0/"
            if item["license"] == "CC BY-SA 2.0"
            else "https://creativecommons.org/licenses/by-sa/4.0/"
        )
        public_assets.append({
            "asset_id": item["asset_id"],
            "athlete_id": item["athlete_id"],
            "subject_name": item["subject_name"],
            "match_id": None,
            "match_link_status": "NOT_LINKED_NO_DIRECT_MATCH_PHOTO_EVIDENCE",
            "use_scope": "ATHLETE_PROFILE_EDITORIAL_ONLY",
            "promotion_use": "NOT_CLEARED_NO_ENDORSEMENT_OR_HOMEPAGE_PROMOTION",
            "source_page_url": source_page,
            "source_file_url": item["source_file_url"],
            "source_title": title,
            "photographer": credit,
            "license": item["license"],
            "license_url": license_url,
            "attribution": f"{title} — Photo by {credit}; licensed {item['license']}. Source: {source_page}. License: {license_url}. This use does not imply athlete endorsement.",
            "changes_made": "Original cropped to 4:5, resized to two responsive dimensions, converted to WebP, and stripped of EXIF metadata; derivatives remain under the same CC BY-SA license.",
            "share_alike_required": True,
            "source_sha256": source_hash,
            "source_dimensions": item["source_dimensions"],
            "derivatives": derivative_rows,
        })

    manifest = {
        "contract_version": "ptti.public-media-manifest/0.2",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "view": "STRICT_PUBLIC_MEDIA",
        "clearance_review_sha256": sha256_bytes(REVIEW_PATH.read_bytes()),
        "source_manifest_sha256": source_manifest_sha,
        "license_notice": "These four images are cleared only for factual athlete-profile editorial display with visible credit, source link and license. Do not imply endorsement or use as homepage promotion/advertising. Every derivative is CC BY-SA under the same license as the source; preserve attribution and ShareAlike. No image is linked to a Goal15 match.",
        "assets": public_assets,
    }
    validate_schema(manifest, PUBLIC_SCHEMA_PATH, "strict public media package")
    PUBLIC_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def validate_files() -> dict[str, Any]:
    review = read_json(REVIEW_PATH)
    validate_schema(review, REVIEW_SCHEMA_PATH, "clearance review")
    source_manifest_bytes = SOURCE_MANIFEST_PATH.read_bytes()
    source_manifest_sha = sha256_bytes(source_manifest_bytes)
    if source_manifest_sha != EXPECTED_SOURCE_MANIFEST_SHA or review["source_manifest"]["sha256"] != source_manifest_sha:
        raise MediaPackageError("source manifest hash changed; strict-public projection is stale")
    source_manifest = json.loads(source_manifest_bytes.decode("utf-8"))
    review_by_id = {asset["asset_id"]: asset for asset in review["assets"]}
    if len(review_by_id) != 9 or set(review_by_id) != {asset["asset_id"] for asset in source_manifest["assets"]}:
        raise MediaPackageError("internal clearance review no longer matches the original nine candidates")
    public = read_json(PUBLIC_PATH)
    validate_schema(public, PUBLIC_SCHEMA_PATH, "strict public media package")
    if public["source_manifest_sha256"] != source_manifest_sha:
        raise MediaPackageError("strict-public package is not bound to the reviewed source manifest")
    if public["clearance_review_sha256"] != sha256_bytes(REVIEW_PATH.read_bytes()):
        raise MediaPackageError("strict-public package is stale relative to the clearance review")
    public_by_id = {asset["asset_id"]: asset for asset in public["assets"]}
    approved_ids = {asset_id for asset_id, item in review_by_id.items() if item["clearance_status"] == "CLEARED_EDITORIAL_PROFILE_ONLY"}
    if set(public_by_id) != approved_ids or approved_ids != EXPECTED_APPROVED_IDS:
        raise MediaPackageError("strict-public package must contain exactly the cleared four-asset allowlist")

    source_by_id = {asset["asset_id"]: asset for asset in source_manifest["assets"]}
    referenced_derivatives: set[str] = set()
    for asset_id, asset in public_by_id.items():
        review_item = review_by_id[asset_id]
        source = source_by_id[asset_id]
        if asset["athlete_id"] != review_item["athlete_id"] or asset["athlete_id"] not in source["athlete_ids"]:
            raise MediaPackageError(f"athlete ID does not match reviewed source record: {asset_id}")
        if asset["match_id"] is not None or asset["use_scope"] != "ATHLETE_PROFILE_EDITORIAL_ONLY":
            raise MediaPackageError(f"asset exceeds scoped profile-only approval: {asset_id}")
        if asset["source_sha256"] != review_item["source_sha256"]:
            raise MediaPackageError(f"original image hash differs from rights review: {asset_id}")
        for derivative in asset["derivatives"]:
            relative = PurePosixPath(derivative["path"])
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "assets":
                raise MediaPackageError("public derivative path escapes the media package")
            path = PUBLIC_DIR.joinpath(*relative.parts)
            if not path.is_file() or sha256_file(path) != derivative["sha256"]:
                raise MediaPackageError(f"derivative missing or hash mismatch: {asset_id} / {derivative['path']}")
            referenced_derivatives.add(path.resolve().as_posix())
            with Image.open(path) as image:
                if image.size != (derivative["width"], derivative["height"]):
                    raise MediaPackageError(f"derivative dimensions mismatch: {asset_id} / {derivative['path']}")
                if image.getexif():
                    raise MediaPackageError(f"derivative retains EXIF metadata: {asset_id} / {derivative['path']}")

    actual_derivatives = {path.resolve().as_posix() for path in (PUBLIC_DIR / "assets").glob("*.webp")}
    if actual_derivatives != referenced_derivatives:
        raise MediaPackageError("public asset folder contains missing or unreferenced WebP derivatives")

    if OLD_STRICT_PACKAGE.exists() and len(json.loads(OLD_STRICT_PACKAGE.read_text(encoding="utf-8"))["matches"]) != 5:
        raise MediaPackageError("pre-existing strict match package was unexpectedly changed")
    return {
        "reviewed_candidate_count": len(review["assets"]),
        "editorial_profile_cleared_count": len(approved_ids),
        "not_cleared_count": len(review["assets"]) - len(approved_ids),
        "strict_public_assets": len(public["assets"]),
        "derivatives": sum(len(asset["derivatives"]) for asset in public["assets"]),
        "source_manifest_sha256": source_manifest_sha,
        "review_sha256": sha256_bytes(REVIEW_PATH.read_bytes()),
        "public_package_sha256": sha256_file(PUBLIC_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or validate the GOAL16.2 strict-public editorial photo package.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true", help="verify local licensed source copies and build responsive derivatives")
    group.add_argument("--validate", action="store_true", help="validate review, strict package, file hashes and image metadata")
    args = parser.parse_args()
    if args.build:
        manifest = build()
        print(json.dumps({"status": "BUILT", "assets": len(manifest["assets"]), "package": str(PUBLIC_PATH)}, ensure_ascii=False))
    else:
        print(json.dumps({"status": "PASS", **validate_files()}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
