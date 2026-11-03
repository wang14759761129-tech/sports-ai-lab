"""Export local Alpha RC Web views and separate Desktop binding review data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from alpha_bridge import build_bridge, write_bridge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-records", type=Path, default=PACKAGE / "fixtures" / "web-alpha-46f1826d.json")
    parser.add_argument("--native-report", type=Path, default=PACKAGE / "fixtures" / "native-user-acceptance-goal04.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        records = json.loads(args.web_records.read_text(encoding="utf-8"))
        report = json.loads(args.native_report.read_text(encoding="utf-8"))
        bridge = build_bridge(records, report)
        manifest = json.loads((PACKAGE / "fixtures" / "alpha-bridge-inputs.json").read_text(encoding="utf-8"))
        snapshot_hash = hashlib.sha256(args.web_records.read_bytes()).hexdigest()
        pinned = snapshot_hash == manifest["web_snapshot_sha256"]
        bridge["input_provenance"] = {"web_snapshot_sha256": snapshot_hash,
            "web_git_sha": manifest["web_git_sha"] if pinned else None,
            "snapshot_status": "PINNED_PUBLIC_SNAPSHOT" if pinned else "UNPINNED_INPUT",
            "playback_interface_audit_sha": manifest["playback_git_sha"],
            "runtime_playback_checks": "NOT_PERFORMED"}
        summary = {"bridge_version": bridge["bridge_version"], **bridge["counts"],
                   "native_acceptance": bridge["native_acceptance"]["assessment"],
                   "sandbox": bridge["desktop_fixture_sandbox"]["assessment"]}
        if args.output_dir:
            summary["export_sha256"] = write_bridge(args.output_dir, bridge)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"Alpha bridge rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
