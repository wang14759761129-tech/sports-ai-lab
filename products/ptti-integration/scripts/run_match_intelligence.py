#!/usr/bin/env python3
"""Run the local Protocol v0.3 Match Intelligence sidecar.

Examples:
  python products/ptti-integration/scripts/run_match_intelligence.py --demo-mutation
  python products/ptti-integration/scripts/run_match_intelligence.py --input products/ptti-integration/fixtures/goal07-simulated-points.json
  python products/ptti-integration/scripts/run_match_intelligence.py --csv points.csv --manifest annotation-manifest.json --source-file match.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from match_intelligence import (  # noqa: E402
    AnalysisValidationError,
    analyze_bundle,
    build_synthetic_demo,
    demo_with_mutation,
    import_manual_csv,
)


DEFAULT_FIXTURE = ROOT / "fixtures" / "goal07-simulated-points.json"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _write_output(path: Path, data: bytes, *, allow_create: bool = True, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == data:
            return
        if not replace:
            raise FileExistsError(f"Refusing to overwrite different existing file: {path}; pass --force to replace it")
    if not allow_create:
        raise FileNotFoundError(path)
    path.write_bytes(data)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze protocol v0.3 point annotations without accessing video or databases.")
    parser.add_argument("--input", type=Path, help="versioned match-intelligence JSON input; defaults to the committed simulated fixture")
    parser.add_argument("--csv", type=Path, help="exact 21-field Protocol v0.3 UTF-8 CSV for manual annotation import")
    parser.add_argument("--manifest", type=Path, help="ptti.manual-point-annotation/0.1 metadata JSON")
    parser.add_argument("--source-file", type=Path, help="selected local source file; its bytes are hashed and compared with the manifest")
    parser.add_argument("--demo-mutation", action="store_true", help="show analysis before and after changing one simulated rally_length")
    parser.add_argument("--write-demo-fixture", type=Path, help="write the deterministic 24-point synthetic input; refuses to overwrite different content")
    parser.add_argument("--output", type=Path, help="write JSON output; refuses to replace different existing content")
    parser.add_argument("--force", action="store_true", help="replace the explicitly selected --output or --write-demo-fixture file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_demo_fixture:
            fixture = build_synthetic_demo()
            _write_output(args.write_demo_fixture, _json_bytes(fixture), replace=args.force)
            print(f"Wrote deterministic SIMULATED_ONLY fixture: {args.write_demo_fixture}")
            return 0

        csv_mode = any((args.csv, args.manifest, args.source_file))
        if csv_mode:
            if not all((args.csv, args.manifest, args.source_file)):
                raise ValueError("--csv, --manifest and --source-file must be supplied together")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            bundle = import_manual_csv(args.csv.read_bytes(), manifest, args.source_file)
        else:
            input_path = args.input or DEFAULT_FIXTURE
            bundle = json.loads(input_path.read_text(encoding="utf-8"))
        result = demo_with_mutation(bundle) if args.demo_mutation else analyze_bundle(bundle)
        encoded = _json_bytes(result)
        if args.output:
            _write_output(args.output, encoded, replace=args.force)
            print(f"Wrote {result.get('evidence_class', result.get('dataset', {}).get('dataset_class'))} result: {args.output}")
        else:
            sys.stdout.buffer.write(encoded)
        return 0
    except (AnalysisValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Match Intelligence rejected input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
