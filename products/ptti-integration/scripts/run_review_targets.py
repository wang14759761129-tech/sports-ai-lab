#!/usr/bin/env python3
"""Generate a local review-targets view without modifying the input."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quick_annotation import QuickAnnotationError
from review_targets import build_review_targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--display-caution-threshold", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("output must not replace input")
        result = build_review_targets(json.loads(args.input.read_text(encoding="utf-8")),
                                      display_caution_threshold=args.display_caution_threshold)
        data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output.exists() and args.output.read_text(encoding="utf-8") != data:
            raise ValueError("output exists with different content; choose a new output path")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
        print(f"{result['contract_version']} points={result['sample']['point_count']} targets={len(result['review_targets'])} evidence={result['evidence_status']}")
        return 0
    except (ValueError, OSError, QuickAnnotationError) as exc:
        print(f"Rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
