#!/usr/bin/env python3
"""Convert a ptti.quick-annotation/0.1 JSON draft into 21-field Protocol v0.3 rows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quick_annotation import QuickAnnotationError, adapt_quick_annotation  # noqa: E402


def _write(path: Path, content: bytes, *, force: bool) -> None:
    if path.exists():
        if path.read_bytes() == content:
            return
        if not force:
            raise FileExistsError(f"refusing to overwrite different file: {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a quick point draft to existing Protocol v0.3 rows.")
    parser.add_argument("--input", type=Path, required=True, help="ptti.quick-annotation/0.1 JSON input")
    parser.add_argument("--output-json", type=Path, required=True, help="review-only draft output JSON")
    parser.add_argument("--output-csv", type=Path, required=True, help="21-field Protocol v0.3-compatible draft CSV")
    parser.add_argument("--force", action="store_true", help="replace explicitly named outputs with different contents")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = adapt_quick_annotation(payload)
        encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        csv_bytes = result["protocol"]["csv_utf8"].encode("utf-8")
        _write(args.output_json, encoded, force=args.force)
        _write(args.output_csv, csv_bytes, force=args.force)
        print(f"draft={result['draft_status']} points={len(result['points'])} formal_report_eligible=false")
        print(f"json={args.output_json}")
        print(f"protocol_csv={args.output_csv}")
        return 0
    except (QuickAnnotationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Quick Annotation rejected input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
