from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
INTEGRATION_DIR = HERE.parents[1]
REPO_ROOT = HERE.parents[3]
sys.path.insert(0, str(INTEGRATION_DIR))
sys.path.insert(0, str(HERE.parents[0]))

from cinema_source_review import SourceReviewError, build_from_paths  # noqa: E402
from match_library_index import build_indexes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a private, evidence-backed Cinema source review JSON.")
    parser.add_argument("--generated-at", help="ISO-8601 timestamp; defaults to current UTC")
    parser.add_argument("--output", type=Path, default=INTEGRATION_DIR / "generated" / "goal12-3" / "cinema-source-review-internal.json")
    args = parser.parse_args()
    try:
        internal_index, strict_public = build_indexes(REPO_ROOT, generated_at=args.generated_at)
        if strict_public["video_sources"]:
            raise SourceReviewError("strict-public projection unexpectedly contains video sources")
        # Use a temporary JSON input only in memory by writing the fresh source index
        # to a short-lived file next to the requested output, then remove it reliably.
        temp_index = args.output.with_suffix(".index.tmp.json")
        temp_observations = INTEGRATION_DIR / "fixtures" / "goal12-3-selected-source-observations.json"
        try:
            temp_index.parent.mkdir(parents=True, exist_ok=True)
            temp_index.write_text(json.dumps(internal_index, ensure_ascii=False), encoding="utf-8")
            result = build_from_paths(temp_index, temp_observations, args.output, args.generated_at)
        finally:
            temp_index.unlink(missing_ok=True)
    except SourceReviewError as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(args.output), "selected": result["summary"]["selected_sources"], "canonical_links": result["summary"]["canonical_match_links"], "public_sources": result["catalog_snapshot"]["strict_public_video_source_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
