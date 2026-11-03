"""Print a filtered, read-only Web view of a v0.2 interchange JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from web_consumer import consume_contract, load_contract  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path, help="Path to a ptti.match-media/0.2 JSON export")
    parser.add_argument("--view", choices=("review", "public"), default="review")
    parser.add_argument("--match-id")
    parser.add_argument("--discipline", choices=("MS", "WS", "MD", "WD", "XD", "UNKNOWN"))
    parser.add_argument("--search")
    args = parser.parse_args()
    try:
        result = consume_contract(
            load_contract(args.contract),
            view=args.view,
            match_id=args.match_id,
            discipline=args.discipline,
            search=args.search,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"Web export rejected: {exc}\n")
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
