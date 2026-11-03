#!/usr/bin/env python3
"""Generate GOAL14's internal fan-content candidates and empty strict-public view."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTEGRATION_DIR.parents[1]
sys.path.insert(0, str(INTEGRATION_DIR))

from fan_content_intelligence import build_from_files, write_views  # noqa: E402
from fan_content_delivery import build_delivery_package, write_delivery_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=INTEGRATION_DIR / "fixtures" / "goal14-fan-content-observations.json")
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "products" / "ptti" / "data" / "professional" / "registry.json")
    parser.add_argument("--output-dir", type=Path, default=INTEGRATION_DIR / "generated" / "goal14")
    parser.add_argument("--localizations", type=Path, default=INTEGRATION_DIR / "fixtures" / "goal14-fan-localization-v0.1.json")
    parser.add_argument("--generated-at", help="Optional fixed ISO-8601 timestamp for reproducible output")
    args = parser.parse_args()
    internal, public = build_from_files(REPO_ROOT, args.observations, args.registry, args.generated_at)
    internal_path, public_path = write_views(internal, public, args.output_dir)
    delivery = build_delivery_package(
        internal,
        args.localizations,
        base_sha256=hashlib.sha256(internal_path.read_bytes()).hexdigest(),
    )
    delivery_path = write_delivery_package(delivery, args.output_dir / "fan-content-delivery-internal-review.json")
    summary = internal["quality_summary"]
    print(
        f"INTERNAL_REVIEW: {summary['event_count']} events, {summary['star_count']} stars, "
        f"{summary['candidate_count']} candidates; {summary['exact_video_url_count']} exact video URLs, "
        f"{summary['event_page_only_count']} event-page-only; playback PASS {summary['playback_pass_count']}; "
        f"strict-public eligible {summary['public_eligible_count']}"
    )
    print(f"Wrote {internal_path}")
    print(f"Wrote {public_path} ({len(public['content_candidates'])} content candidates)")
    print(f"Wrote {delivery_path} ({delivery['quality_summary']['unique_watch_source_count']} unique watch sources; match links {delivery['quality_summary']['match_video_links']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
