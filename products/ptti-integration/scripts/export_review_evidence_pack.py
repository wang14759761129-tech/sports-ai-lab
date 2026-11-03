#!/usr/bin/env python3
"""Export a private Markdown and JSON evidence pack from Quick Annotation input."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quick_annotation import QuickAnnotationError
from review_evidence_pack import build_review_evidence_pack, render_markdown


def _write_new_or_identical(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"output exists with different content; choose a new path: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--generated-at-utc", help="Optional timezone-aware ISO timestamp for reproducible exports.")
    parser.add_argument("--display-caution-threshold", type=int, default=5)
    args = parser.parse_args()
    try:
        paths = [args.input.resolve(), args.json_output.resolve(), args.markdown_output.resolve()]
        if paths[1] == paths[0] or paths[2] == paths[0]:
            raise ValueError("an output path cannot replace the source input")
        if paths[1] == paths[2]:
            raise ValueError("JSON and Markdown output paths must be different")
        raw = args.input.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        pack = build_review_evidence_pack(
            payload, generated_at_utc=args.generated_at_utc, raw_input_bytes=raw,
            input_name=args.input.name, display_caution_threshold=args.display_caution_threshold,
        )
        json_bytes = (json.dumps(pack, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        markdown_bytes = render_markdown(pack).encode("utf-8")
        # Validate both destinations before creating either artifact.
        for path, content in ((args.json_output, json_bytes), (args.markdown_output, markdown_bytes)):
            if path.exists() and path.read_bytes() != content:
                raise ValueError(f"output exists with different content; choose a new path: {path}")
        _write_new_or_identical(args.json_output, json_bytes)
        _write_new_or_identical(args.markdown_output, markdown_bytes)
        print(f"{pack['contract_version']} points={pack['sample']['point_count']} "
              f"candidates={len(pack['review_candidates'])} score={pack['match']['game']['score']['A']}:{pack['match']['game']['score']['B']} "
              f"status={pack['match']['game']['score_status']}")
        return 0
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError, QuickAnnotationError) as exc:
        print(f"Rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
