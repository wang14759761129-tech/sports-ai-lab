#!/usr/bin/env python3
"""Import Protocol v0.3 point CSV and write a local training review sidecar."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from match_intelligence import (  # noqa: E402
    AnalysisValidationError, build_synthetic_demo, change_point_annotation, serialize_protocol_csv,
)
from training_review import (  # noqa: E402
    build_training_report, csv_template, import_human_training_csv, import_simulated_csv,
    render_chinese_summary, synthetic_declaration,
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write(path: Path, data: bytes, *, force: bool) -> None:
    if path.exists() and path.read_bytes() != data and not force:
        raise FileExistsError(f"Existing output differs; refusing to replace {path}. Pass --force for this selected output.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _time_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _demo(output_dir: Path, *, force: bool) -> dict:
    original = build_synthetic_demo()
    original_csv = serialize_protocol_csv(original)
    original_decl = synthetic_declaration(original_csv)
    reimported = import_simulated_csv(original_csv, original_decl)
    original_report = build_training_report(
        reimported, csv_sha256=original_decl["csv_sha256"], generated_at="2026-10-13T00:00:00Z"
    )
    edited = change_point_annotation(reimported, game_number=1, point_number=1, field="rally_length", value=7)
    edited_csv = serialize_protocol_csv(edited)
    edited_decl = synthetic_declaration(edited_csv, parent_csv_sha256=original_decl["csv_sha256"])
    reimported_edited = import_simulated_csv(edited_csv, edited_decl)
    edited_report = build_training_report(
        reimported_edited, csv_sha256=edited_decl["csv_sha256"], generated_at="2026-10-13T00:00:00Z"
    )
    before = original_report["metrics"]["server_point_win_rate"]
    after = edited_report["metrics"]["server_point_win_rate"]
    comparison = {
        "comparison_version": "ptti.training-review-comparison/0.1",
        "changed_point_id": edited_report["point_refs"][0]["point_id"],
        "field": "rally_length", "before": 5, "after": 7,
        "original_csv_sha256": original_decl["csv_sha256"],
        "edited_csv_sha256": edited_decl["csv_sha256"],
        "original_bundle_sha256": original_report["dataset"]["annotation_bundle_sha256"],
        "edited_bundle_sha256": edited_report["dataset"]["annotation_bundle_sha256"],
        "unchanged_server_win_rate": before["value"] == after["value"],
        "original_rally_length_mean": original_report["metrics"]["rally_length_mean"]["value"],
        "edited_rally_length_mean": edited_report["metrics"]["rally_length_mean"]["value"],
    }
    outputs = {
        "simulated-points.csv": original_csv,
        "simulated-declaration.json": _json_bytes(original_decl),
        "simulated-report.json": _json_bytes(original_report),
        "simulated-report.md": render_chinese_summary(original_report).encode("utf-8"),
        "simulated-points-edited.csv": edited_csv,
        "simulated-declaration-edited.json": _json_bytes(edited_decl),
        "simulated-report-edited.json": _json_bytes(edited_report),
        "simulated-report-edited.md": render_chinese_summary(edited_report).encode("utf-8"),
        "comparison.json": _json_bytes(comparison),
    }
    for name, data in outputs.items():
        _write(output_dir / name, data, force=force)
    return comparison


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-template", type=Path, help="write the fillable exact 21-column CSV header")
    parser.add_argument("--demo", action="store_true", help="run original and one-edit synthetic CSV import/report comparison")
    parser.add_argument("--output-dir", type=Path, help="directory for deterministic demo files")
    parser.add_argument("--csv", type=Path, help="local UTF-8 Protocol v0.3 CSV")
    parser.add_argument("--declaration", type=Path, help="SIMULATED_ONLY source declaration JSON")
    parser.add_argument("--manifest", type=Path, help="human annotation manifest JSON")
    parser.add_argument("--source-file", type=Path, help="explicitly selected locally authorized source video")
    parser.add_argument("--binding", type=Path, help="separate human match/source/rights review declaration")
    parser.add_argument("--output-json", type=Path, help="save the structured report")
    parser.add_argument("--output-md", type=Path, help="save the Chinese review summary")
    parser.add_argument("--generated-at", help="timezone-qualified ISO timestamp; default is current UTC")
    parser.add_argument("--force", action="store_true", help="replace explicitly selected output files")
    args = parser.parse_args(argv)
    try:
        if args.write_template:
            _write(args.write_template, csv_template(), force=args.force)
            print(f"Template: {args.write_template}")
            return 0
        if args.demo:
            if not args.output_dir:
                raise ValueError("--demo requires --output-dir")
            comparison = _demo(args.output_dir, force=args.force)
            print(json.dumps(comparison, ensure_ascii=False, indent=2))
            return 0
        if not (args.csv and args.output_json and args.output_md):
            raise ValueError("provide --csv, --output-json and --output-md, or use --demo")
        csv_bytes = args.csv.read_bytes()
        if args.declaration and not any((args.manifest, args.source_file, args.binding)):
            bundle = import_simulated_csv(csv_bytes, json.loads(args.declaration.read_text(encoding="utf-8")))
            binding = None
        elif not args.declaration and all((args.manifest, args.source_file, args.binding)):
            binding = json.loads(args.binding.read_text(encoding="utf-8"))
            bundle = import_human_training_csv(
                csv_bytes, json.loads(args.manifest.read_text(encoding="utf-8")), args.source_file, binding,
            )
        else:
            raise ValueError("choose --declaration for simulated CSV or all of --manifest, --source-file, --binding for human CSV")
        generated_at = args.generated_at or _time_now()
        report = build_training_report(bundle, csv_sha256=hashlib.sha256(csv_bytes).hexdigest(),
                                       generated_at=generated_at, binding=binding)
        _write(args.output_json, _json_bytes(report), force=args.force)
        _write(args.output_md, report["summary_cn"].encode("utf-8"), force=args.force)
        print(f"Report: {args.output_json}; {report['dataset']['evidence_status']}; {report['sample']['point_count']} points")
        return 0
    except (AnalysisValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Training review rejected input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
