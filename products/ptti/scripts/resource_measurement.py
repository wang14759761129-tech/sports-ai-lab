"""Bounded Windows/Linux process-tree resource sampling for PTTI QA.

The sampler is observational only. It never starts a worker or stops a process.
Reports intentionally omit executable paths and command lines.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil


MAX_DURATION_SECONDS = 300


def summarize_samples(samples: list[dict]) -> dict:
    """Summarize numeric sample fields while keeping unavailable metrics explicit."""
    if not samples:
        return {"sample_count": 0, "metrics": {}}

    keys = sorted({key for sample in samples for key in sample})
    metrics = {}
    for key in keys:
        values = [
            sample[key]
            for sample in samples
            if isinstance(sample.get(key), (int, float))
            and not isinstance(sample.get(key), bool)
        ]
        if values:
            metrics[key] = {
                "median": statistics.median(values),
                "min": min(values),
                "peak": max(values),
            }
        elif any(key in sample for sample in samples):
            metrics[key] = None
    return {"sample_count": len(samples), **metrics}


def cpu_percent_from_cpu_times(
    previous_cpu_seconds: float | None,
    current_cpu_seconds: float,
    elapsed_seconds: float,
) -> float | None:
    """Return process-tree CPU usage in single-core-equivalent percent."""
    if previous_cpu_seconds is None or elapsed_seconds <= 0:
        return None
    return max(0.0, (current_cpu_seconds - previous_cpu_seconds) / elapsed_seconds * 100)


def _gpu_snapshot(process_ids: set[int]) -> dict:
    executable = "nvidia-smi"
    try:
        gpu_result = subprocess.run(
            [
                executable,
                "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        gpu_rows = list(csv.reader(gpu_result.stdout.strip().splitlines()))
        gpu_rows = [row for row in gpu_rows if len(row) >= 4]
        gpu_total = sum(int(row[0].strip()) for row in gpu_rows) * 1024**2
        gpu_used = sum(int(row[1].strip()) for row in gpu_rows) * 1024**2
        gpu_free = sum(int(row[2].strip()) for row in gpu_rows) * 1024**2
        gpu_util = statistics.mean(int(row[3].strip()) for row in gpu_rows)
    except (OSError, subprocess.SubprocessError, ValueError, csv.Error):
        return {
            "gpu_total_bytes": None,
            "gpu_used_bytes": None,
            "gpu_free_bytes": None,
            "gpu_utilization_percent": None,
            "process_tree_gpu_bytes": None,
        }

    process_gpu_bytes = None
    try:
        app_result = subprocess.run(
            [
                executable,
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        app_rows = list(csv.reader(app_result.stdout.strip().splitlines()))
        matched = []
        for row in app_rows:
            if len(row) < 2 or row[0].strip() in {"", "N/A"}:
                continue
            if int(row[0].strip()) in process_ids and row[1].strip() not in {"", "N/A"}:
                matched.append(int(row[1].strip()) * 1024**2)
        process_gpu_bytes = sum(matched) if matched else 0
    except (OSError, subprocess.SubprocessError, ValueError, csv.Error):
        pass
    return {
        "gpu_total_bytes": gpu_total,
        "gpu_used_bytes": gpu_used,
        "gpu_free_bytes": gpu_free,
        "gpu_utilization_percent": gpu_util,
        "process_tree_gpu_bytes": process_gpu_bytes,
    }


def _tree_snapshot(roots: dict[int, float]) -> tuple[list[dict], list[int]]:
    processes: dict[int, psutil.Process] = {}
    missing_roots = []
    for pid, created_at in roots.items():
        try:
            root = psutil.Process(pid)
            if abs(root.create_time() - created_at) > 0.01:
                missing_roots.append(pid)
                continue
            processes[pid] = root
            for child in root.children(recursive=True):
                processes[child.pid] = child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            missing_roots.append(pid)

    rows = []
    for pid, process in processes.items():
        try:
            memory = process.memory_info()
            try:
                private_bytes = process.memory_full_info().uss
            except (psutil.AccessDenied, AttributeError, NotImplementedError):
                private_bytes = None
            rows.append(
                {
                    "pid": pid,
                    "parent_pid": process.ppid(),
                    "name": process.name(),
                    "rss_bytes": memory.rss,
                    "uss_bytes": private_bytes,
                    "cpu_time_seconds": sum(process.cpu_times()[:2]),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows, sorted(set(missing_roots))


def capture(
    root_pids: list[int], scenario: str, duration_seconds: float, interval_seconds: float
) -> dict:
    if not root_pids or len(root_pids) > 8:
        raise ValueError("Supply between 1 and 8 process root PIDs")
    if duration_seconds < 0 or duration_seconds > MAX_DURATION_SECONDS:
        raise ValueError(f"Duration must be between 0 and {MAX_DURATION_SECONDS} seconds")
    if interval_seconds < 1 or interval_seconds > 30:
        raise ValueError("Interval must be between 1 and 30 seconds")
    if not scenario.strip() or len(scenario) > 100:
        raise ValueError("Scenario must contain 1 to 100 characters")

    roots = {pid: psutil.Process(pid).create_time() for pid in root_pids}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "UNKNOWN"

    started = datetime.now(timezone.utc)
    began = time.monotonic()
    last_sample_elapsed = 0.0
    previous_cpu_seconds = None
    samples = []
    while True:
        rows, missing_roots = _tree_snapshot(roots)
        elapsed = time.monotonic() - began
        cpu_seconds = sum(row["cpu_time_seconds"] for row in rows)
        private_known = all(row["uss_bytes"] is not None for row in rows) and bool(rows)
        metrics = {
            "available_ram_bytes": psutil.virtual_memory().available,
            "process_tree_rss_bytes": sum(row["rss_bytes"] for row in rows),
            "process_tree_uss_bytes": (
                sum(row["uss_bytes"] for row in rows) if private_known else None
            ),
            "process_tree_cpu_percent": cpu_percent_from_cpu_times(
                previous_cpu_seconds, cpu_seconds, elapsed - last_sample_elapsed
            ),
            "process_count": len(rows),
        }
        metrics.update(_gpu_snapshot({row["pid"] for row in rows}))
        samples.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                **metrics,
                "processes": rows,
                "missing_root_pids": missing_roots,
            }
        )
        previous_cpu_seconds = cpu_seconds
        last_sample_elapsed = elapsed
        if missing_roots or elapsed >= duration_seconds:
            break
        time.sleep(min(interval_seconds, max(0, duration_seconds - elapsed)))

    return {
        "schema_version": 1,
        "scenario": scenario,
        "source_git_sha": commit,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "started_at": started.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - began, 3),
        "root_pids": root_pids,
        "summary": summarize_samples(samples),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, action="append", required=True, help="Root PID; repeat to include independent trees")
    parser.add_argument("--scenario", required=True, help="Short user-action label for this capture")
    parser.add_argument("--duration-seconds", type=float, default=30)
    parser.add_argument("--interval-seconds", type=float, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = capture(args.pid, args.scenario, args.duration_seconds, args.interval_seconds)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
