#!/usr/bin/env python3
"""Build the small GOAL 12 internal-only Cinema shortlist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from cinema_curated_sources import CurationError, write_curated_sources  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INTEGRATION_DIR / "generated" / "goal11-match-library" / "match-library-internal-review.json")
    parser.add_argument("--observations", type=Path, default=INTEGRATION_DIR / "fixtures" / "goal12-cinema-curation-observations.json")
    parser.add_argument("--output", type=Path, default=INTEGRATION_DIR / "generated" / "goal12-cinema-featured" / "featured-sources-internal-review.json")
    parser.add_argument("--generated-at", help="Optional fixed UTC timestamp for reproducible output")
    args = parser.parse_args()
    try:
        result = write_curated_sources(args.index, args.observations, args.output, args.generated_at)
    except CurationError as exc:
        parser.error(str(exc))
    print(f"Internal curated sources: {len(result['featured_sources'])}")
    print(f"Strict-public fallback: {result['strict_public_fallback']}")
    print(f"Canonical Match links: {sum(item['match_link']['status'] == 'HUMAN_VERIFIED' for item in result['featured_sources'])}")
    print(f"Official pages HTTP 200: {sum(item['external_watch']['http_head_status'] == 'HTTP_200' for item in result['featured_sources'])}")
    print("Actual video playback PASS: 0")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
