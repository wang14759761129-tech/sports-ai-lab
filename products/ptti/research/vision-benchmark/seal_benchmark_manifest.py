"""Seal derived input hashes as a new manifest revision. Original assets/reports are never overwritten."""
import csv
import json
from pathlib import Path

from ptti_benchmark.core import file_sha256, verify_manifest, write_report


def main():
    foundation = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation"
    root = foundation/"benchmark-v0"
    original = root/"PTTI_VISION_BENCHMARK_V0_MANIFEST.json"
    target = root/"PTTI_VISION_BENCHMARK_V0_MANIFEST_R1.json"
    if target.exists():
        raise FileExistsError("SEALED_MANIFEST_ALREADY_EXISTS")
    manifest = json.loads(original.read_text(encoding="utf-8"))
    original_sha = file_sha256(original)
    for clip in manifest["clips"]:
        native = {}
        with Path(clip["annotation"]["path"]).open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                native[int(row["Frame"])] = row
        labels = json.loads(Path(clip["canonical_labels"]).read_text(encoding="utf-8"))
        for label in labels:
            row = native[label["source_frame"]]
            if label["visible"] != bool(int(row["Visibility"])) or (label["visible"] and
                    (label["x"] != float(row["X"]) or label["y"] != float(row["Y"]))):
                raise ValueError("DERIVED_LABELS_DO_NOT_MATCH_PINNED_NATIVE_GT")
        for field in ("canonical_labels", "racketvision_raw"):
            clip[field+"_sha256"] = file_sha256(Path(clip[field]))
    manifest["revision"] = "R1_DERIVED_ASSET_HASH_SEAL"
    manifest["supersedes_manifest_sha256"] = original_sha
    verify_manifest(manifest)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    target.with_suffix(".sha256").write_text(file_sha256(target) + "  " + target.name + "\n")
    # Replay canonical scoring from saved RAW observations, no inference/training/tuning.
    original_report = foundation/"rf-detr-comparison.json"
    if original_report.exists():
        report = json.loads(original_report.read_text(encoding="utf-8"))
        if report["manifest_sha256"] != original_sha:
            raise ValueError("ORIGINAL_RUN_MANIFEST_MISMATCH")
        report["original_report_sha256"] = file_sha256(original_report)
        report["original_manifest_sha256"] = original_sha
        report["manifest_sha256"] = file_sha256(target)
        report["integrity_revalidation"] = "DERIVED_LABELS_MATCH_NATIVE_PINNED_GT; ALL_DERIVED_INPUTS_HASHED; NO_NEW_INFERENCE"
        write_report(foundation/"rf-detr-comparison-revalidated.json", report)
    print(json.dumps({"manifest": str(target), "sha256": file_sha256(target), "original_preserved": original_sha}))


if __name__ == "__main__":
    main()
