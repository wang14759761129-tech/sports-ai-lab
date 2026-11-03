#!/usr/bin/env python3
"""Generate the GOAL 11 internal review and strict public match-library views."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from match_library_index import write_indexes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=INTEGRATION_DIR / "generated" / "goal11-match-library")
    parser.add_argument("--generated-at", help="Optional fixed UTC timestamp for reproducible checks")
    args = parser.parse_args()
    review_path, public_path = write_indexes(REPO_ROOT, args.output_dir, args.generated_at)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    public = json.loads(public_path.read_text(encoding="utf-8"))
    summary = review["quality_summary"]
    print(f"Internal review: {summary['unique_video_sources']} unique VideoSource records, {summary['registered_match_records']} registered Match records, {summary['athlete_profiles']} athlete profiles")
    print(f"Video source duplicates removed: {summary['duplicate_snapshot_rows_removed']}")
    print(f"Playback evidence: {summary['external_visual_playback_observed_limited']} limited external visual observation(s); {summary['desktop_native_playback_pass']} Desktop Native PASS")
    print(f"Strict public: {len(public['matches'])} matches, {len(public['video_sources'])} video sources, {len(public['stars'])} athlete profiles")
    print(f"Wrote {review_path}")
    print(f"Wrote {public_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
