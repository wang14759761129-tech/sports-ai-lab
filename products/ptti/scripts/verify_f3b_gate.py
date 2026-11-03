"""Offline F3B verification with command logs and the existing 2.5 GiB gate.

Does not start the product, import the backend, or access browser/user storage.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "products/ptti/frontend"
GATE_BYTES = int(2.5 * 1024**3)


def mask_machine_paths(value):
    user_profile = os.environ.get("USERPROFILE")
    return value.replace(user_profile, "%USERPROFILE%") if user_profile else value


def memory():
    if os.name != "nt":
        return {"available_bytes": None, "reason": "WINDOWS_MEMORY_SAMPLE_UNAVAILABLE"}

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"available_bytes": None, "reason": "MEMORY_SAMPLE_FAILED"}
    return {"available_bytes": status.available, "available_gib": round(status.available / 1024**3, 4)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baseline", "upgrade", "verify", "audit", "artifact", "tools"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--playback-module", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / f"{args.phase}.json"
    if manifest.exists():
        raise SystemExit(f"Refusing to replace existing evidence: {manifest}")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    node = shutil.which("node")
    if not npm or not node:
        raise SystemExit("Node and npm must already be installed")
    commands = {
        "baseline": [("audit-before", [npm, "audit", "--json"], FRONTEND, False, [0, 1])],
        "audit": [("audit-confirmed", [npm, "audit", "--json"], FRONTEND, False, [0])],
        "artifact": [("built-media-gate", [node, "scripts/check-media-distribution.mjs", "dist"], FRONTEND, False, [0])],
        "tools": [("verification-tools", [sys.executable, "-m", "unittest", "products.ptti.tests.test_f3b_gate_verification", "-v"], ROOT, False, [0])],
        "upgrade": [("vite-patch-lock", [npm, "install", "--save-dev", "--save-exact", "vite@7.3.7", "--package-lock-only", "--ignore-scripts"], FRONTEND, True, [0])],
        "verify": [
            ("npm-ci", [npm, "ci"], FRONTEND, True, [0]),
            ("audit-after", [npm, "audit", "--json"], FRONTEND, False, [0]),
            *[(label, [npm, "run", script], FRONTEND, False, [0]) for label, script in [
                ("foundation", "test:foundation"), ("f3a-adapters", "test:foundation-adapters"),
                ("f3b-projection", "test:foundation-playback"), ("media-distribution", "test:media-distribution"),
                ("feed", "test:feed"), ("story", "test:goal99-story"), ("favorites", "test:favorite-persistence"),
                ("moments", "test:moments"), ("moment-backup", "test:moment-backup"),
                ("pro-lab", "test:pro-lab"), ("arena", "test:fan-arena"),
                ("arena-storage", "test:fan-arena-storage"), ("official-theater", "test:official-theater"),
                ("thumbnail-gate", "test:youtube-thumbnail"), ("cinema-viewing", "test:cinema-viewing"),
            ]],
            ("python-schema", [sys.executable, "-m", "unittest", "products.ptti.tests.test_foundation_contract", "-v"], ROOT, False, [0]),
            ("typescript-full", [node, "node_modules/typescript/bin/tsc", "-b", "--pretty", "false"], FRONTEND, True, [0]),
            ("vite-production", [node, "node_modules/vite/bin/vite.js", "build"], FRONTEND, True, [0]),
            ("diff-check", ["git", "diff", "--check"], ROOT, False, [0]),
        ],
    }[args.phase]
    if args.phase == "verify" and args.playback_module:
        commands.insert(-3, ("playback-source-integration", [node, "scripts/test-playback-foundation-source-integration.mjs", str(args.playback_module.resolve())], FRONTEND, False, [0]))
    report = {"phase": args.phase, "head_before": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "started_at": datetime.now(timezone.utc).isoformat(), "guard_bytes": GATE_BYTES, "commands": []}
    for label, command, cwd, guarded, expected in commands:
        before = memory()
        row = {"label": label, "argv": [mask_machine_paths(arg) for arg in command], "cwd": str(cwd.relative_to(ROOT)) or ".", "memory_before": before}
        if guarded and (before["available_bytes"] is None or before["available_bytes"] < GATE_BYTES):
            row.update(status="RESOURCE_BLOCKED", exit_code=None)
        else:
            start = time.monotonic()
            env = {**os.environ, "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, encoding="utf-8", errors="replace")
            log = output / f"{label}.log"
            if log.exists():
                raise SystemExit(f"Refusing to replace existing evidence: {log}")
            content = result.stdout + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
            raw_log_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            log.write_text(mask_machine_paths(content), encoding="utf-8", newline="\n")
            count = re.search(r"(?:tests (\d+)|Ran (\d+) tests?)", content)
            row.update(status="PASS" if result.returncode in expected else "FAIL", exit_code=result.returncode,
                       seconds=round(time.monotonic() - start, 3), log=log.name,
                       raw_log_sha256=raw_log_sha256,
                       log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                       test_count=int(next(value for value in count.groups() if value)) if count else None,
                       memory_after=memory())
            if label.startswith("audit-"):
                try:
                    audit = json.loads(result.stdout)
                    if audit.get("auditReportVersion") != 2:
                        raise ValueError("not a completed registry advisory report")
                    row["audit_vulnerabilities"] = audit["metadata"]["vulnerabilities"]
                except (ValueError, KeyError):
                    row["status"] = "FAIL"
                    row["reason"] = "AUDIT_ENDPOINT_NOT_VERIFIED"
        report["commands"].append(row)
        manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"{label}: {row['status']} exit={row['exit_code']} memory={before.get('available_gib')}", flush=True)
        if row["status"] != "PASS" and label in {"npm-ci", "vite-patch-lock"}:
            break
    return 0 if all(row["status"] == "PASS" for row in report["commands"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
