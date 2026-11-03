"""Task-aware resource gates for local PTTI QA and high-load operations.

This policy does not change Windows memory management.  It is a conservative
preflight/monitor for PTTI work: light tasks do not inherit the build threshold,
medium tasks require a measured budget and live monitoring, and heavy tasks keep
the 2.5 GiB start budget used by the build workflow.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import sys
import time
from pathlib import Path

GIB = 1024**3
MIB = 1024**2
LIGHT_PHYSICAL_FLOOR = 512 * MIB
COMMIT_HEADROOM_FLOOR = GIB
HEAVY_START_FLOOR = int(2.5 * GIB)
HEAVY_RUNTIME_FLOOR = 2 * GIB


class ResourceLevel(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass(frozen=True)
class ResourceSnapshot:
    total_physical_bytes: int
    available_physical_bytes: int
    commit_used_bytes: int | None = None
    commit_limit_bytes: int | None = None
    pagefile_free_bytes: int | None = None

    @property
    def commit_headroom_bytes(self) -> int | None:
        if self.commit_used_bytes is None or self.commit_limit_bytes is None:
            return None
        return max(0, self.commit_limit_bytes - self.commit_used_bytes)

    @property
    def commit_ratio(self) -> float | None:
        if not self.commit_limit_bytes or self.commit_used_bytes is None:
            return None
        return self.commit_used_bytes / self.commit_limit_bytes


@dataclass(frozen=True)
class ResourceDecision:
    allowed: bool
    level: ResourceLevel
    reason: str
    monitor_required: bool = False
    projected_available_bytes: int | None = None


def evaluate_start(
    level: ResourceLevel,
    snapshot: ResourceSnapshot,
    *,
    estimated_peak_bytes: int | None = None,
) -> ResourceDecision:
    """Decide whether a task may start using its actual workload class."""
    if level is ResourceLevel.LIGHT:
        if _severe_pressure(snapshot):
            return ResourceDecision(False, level, "SEVERE_SYSTEM_MEMORY_PRESSURE")
        return ResourceDecision(True, level, "LIGHT_TASK_WITHIN_SYSTEM_HEADROOM")

    if level is ResourceLevel.MEDIUM:
        if estimated_peak_bytes is None or estimated_peak_bytes <= 0:
            return ResourceDecision(False, level, "MEASURED_PEAK_BUDGET_REQUIRED")
        if snapshot.commit_headroom_bytes is None:
            return ResourceDecision(False, level, "COMMIT_HEADROOM_MEASUREMENT_REQUIRED")
        projected = snapshot.available_physical_bytes - estimated_peak_bytes
        if projected < LIGHT_PHYSICAL_FLOOR:
            return ResourceDecision(
                False,
                level,
                "PROJECTED_PHYSICAL_RESERVE_TOO_LOW",
                monitor_required=True,
                projected_available_bytes=projected,
            )
        if snapshot.commit_headroom_bytes - estimated_peak_bytes < COMMIT_HEADROOM_FLOOR:
            return ResourceDecision(
                False,
                level,
                "PROJECTED_COMMIT_RESERVE_TOO_LOW",
                monitor_required=True,
                projected_available_bytes=projected,
            )
        return ResourceDecision(
            True,
            level,
            "MEASURED_BUDGET_FITS_WITH_RESERVE",
            monitor_required=True,
            projected_available_bytes=projected,
        )

    if level is ResourceLevel.HEAVY:
        if snapshot.available_physical_bytes < HEAVY_START_FLOOR:
            return ResourceDecision(False, level, "HEAVY_START_BUDGET_NOT_MET")
        if _severe_pressure(snapshot):
            return ResourceDecision(False, level, "SEVERE_SYSTEM_MEMORY_PRESSURE")
        return ResourceDecision(True, level, "HEAVY_START_BUDGET_MET", monitor_required=True)

    return ResourceDecision(False, level, "UNKNOWN_RESOURCE_LEVEL")


def evaluate_runtime(
    level: ResourceLevel,
    snapshot: ResourceSnapshot,
    *,
    process_tree_working_set_bytes: int | None = None,
    estimated_peak_bytes: int | None = None,
) -> ResourceDecision:
    """Return whether a task may continue; callers should stop safely on False."""
    if _severe_pressure(snapshot):
        return ResourceDecision(False, level, "SEVERE_SYSTEM_MEMORY_PRESSURE")

    if level is ResourceLevel.MEDIUM:
        if process_tree_working_set_bytes is None or estimated_peak_bytes is None:
            return ResourceDecision(False, level, "RUNTIME_MEASUREMENT_REQUIRED")
        if process_tree_working_set_bytes > estimated_peak_bytes:
            return ResourceDecision(False, level, "OBSERVED_PROCESS_BUDGET_EXCEEDED")
        return ResourceDecision(True, level, "WITHIN_MEASURED_RUNTIME_BUDGET", monitor_required=True)

    if level is ResourceLevel.HEAVY:
        if snapshot.available_physical_bytes < HEAVY_RUNTIME_FLOOR:
            return ResourceDecision(False, level, "HEAVY_RUNTIME_FLOOR_NOT_MET", monitor_required=True)
        return ResourceDecision(True, level, "HEAVY_RUNTIME_FLOOR_MET", monitor_required=True)

    return ResourceDecision(True, ResourceLevel.LIGHT, "LIGHT_TASK_WITHIN_SYSTEM_HEADROOM")


def _severe_pressure(snapshot: ResourceSnapshot) -> bool:
    if snapshot.available_physical_bytes < LIGHT_PHYSICAL_FLOOR:
        return True
    headroom = snapshot.commit_headroom_bytes
    if headroom is not None and headroom < COMMIT_HEADROOM_FLOOR:
        return True
    ratio = snapshot.commit_ratio
    return ratio is not None and ratio >= 0.98


def collect_resource_snapshot() -> ResourceSnapshot:
    """Collect real Windows/Linux resource measurements; never fabricates values."""
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - depends on runtime install
        raise RuntimeError("psutil is required for live resource measurement") from exc

    memory = psutil.virtual_memory()
    commit_used: int | None = None
    commit_limit: int | None = None

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PERFORMANCE_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("CommitTotal", ctypes.c_size_t),
                ("CommitLimit", ctypes.c_size_t),
                ("CommitPeak", ctypes.c_size_t),
                ("PhysicalTotal", ctypes.c_size_t),
                ("PhysicalAvailable", ctypes.c_size_t),
                ("SystemCache", ctypes.c_size_t),
                ("KernelTotal", ctypes.c_size_t),
                ("KernelPaged", ctypes.c_size_t),
                ("KernelNonpaged", ctypes.c_size_t),
                ("PageSize", ctypes.c_size_t),
                ("HandleCount", wintypes.DWORD),
                ("ProcessCount", wintypes.DWORD),
                ("ThreadCount", wintypes.DWORD),
            ]

        info = PERFORMANCE_INFORMATION()
        info.cb = ctypes.sizeof(info)
        if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
            raise OSError("GetPerformanceInfo failed")
        commit_used = int(info.CommitTotal * info.PageSize)
        commit_limit = int(info.CommitLimit * info.PageSize)

    try:
        pagefile_free = int(psutil.swap_memory().free)
    except (AttributeError, OSError):  # pragma: no cover - platform-specific
        pagefile_free = None

    return ResourceSnapshot(
        total_physical_bytes=int(memory.total),
        available_physical_bytes=int(memory.available),
        commit_used_bytes=commit_used,
        commit_limit_bytes=commit_limit,
        pagefile_free_bytes=pagefile_free,
    )


def process_tree_working_set_bytes(pid: int) -> int:
    """Measure the requested process and current descendants, without stopping them."""
    import psutil

    root = psutil.Process(pid)
    processes = [root, *root.children(recursive=True)]
    total = 0
    for process in processes:
        try:
            total += int(process.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total


def _snapshot_dict(snapshot: ResourceSnapshot) -> dict[str, int | float | None]:
    result = asdict(snapshot)
    result["commit_headroom_bytes"] = snapshot.commit_headroom_bytes
    result["commit_ratio"] = snapshot.commit_ratio
    return result


def _decision_dict(decision: ResourceDecision) -> dict[str, object]:
    result = asdict(decision)
    result["level"] = decision.level.value
    return result


def run_monitor(
    *,
    level: ResourceLevel,
    pid: int | None,
    estimated_peak_bytes: int | None,
    duration_seconds: int,
    interval_seconds: int,
    log_path: Path | None = None,
    runtime_only: bool = False,
) -> int:
    """Preflight and/or sample for a bounded duration; never kills the target."""
    if duration_seconds < 1 or duration_seconds > 900:
        raise ValueError("duration must be between 1 and 900 seconds")
    if interval_seconds < 1 or interval_seconds > 30:
        raise ValueError("interval must be between 1 and 30 seconds")
    if level is ResourceLevel.MEDIUM and estimated_peak_bytes is None:
        raise ValueError("medium tasks require --estimate-mib")
    if runtime_only and pid is None:
        raise ValueError("runtime-only monitoring requires --pid")

    log = log_path.open("a", encoding="utf-8", newline="\n") if log_path else None

    def record(snapshot: ResourceSnapshot, decision: ResourceDecision, rss: int | None) -> None:
        entry = {
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "snapshot": _snapshot_dict(snapshot),
            "process_tree_working_set_bytes": rss,
            "decision": _decision_dict(decision),
        }
        line = json.dumps(entry, ensure_ascii=True)
        print(line, flush=True)
        if log:
            log.write(line + "\n")
            log.flush()

    def sample_runtime() -> tuple[bool, bool]:
        snapshot = collect_resource_snapshot()
        try:
            assert pid is not None
            rss = process_tree_working_set_bytes(pid)
        except Exception as exc:
            try:
                import psutil
            except ImportError:
                psutil = None  # type: ignore[assignment]
            if psutil is not None and isinstance(exc, psutil.NoSuchProcess):
                decision = ResourceDecision(True, level, "QA_PROCESS_EXITED")
                record(snapshot, decision, None)
                return True, True
            decision = ResourceDecision(False, level, f"PROCESS_MEASUREMENT_FAILED:{type(exc).__name__}")
            record(snapshot, decision, None)
            return False, False
        decision = evaluate_runtime(
            level,
            snapshot,
            process_tree_working_set_bytes=rss,
            estimated_peak_bytes=estimated_peak_bytes,
        )
        record(snapshot, decision, rss)
        return decision.allowed, False

    try:
        if not runtime_only:
            start = collect_resource_snapshot()
            start_decision = evaluate_start(
                level,
                start,
                estimated_peak_bytes=estimated_peak_bytes,
            )
            record(start, start_decision, None)
            if not start_decision.allowed:
                return 2
            if pid is None:
                return 0
        else:
            allowed, exited = sample_runtime()
            if not allowed:
                return 2
            if exited:
                return 0

        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            time.sleep(min(interval_seconds, max(0.0, deadline - time.monotonic())))
            allowed, exited = sample_runtime()
            if not allowed:
                return 2
            if exited:
                return 0
        print(json.dumps({"decision": {"allowed": True, "reason": "MONITOR_WINDOW_COMPLETE"}}), flush=True)
        return 0
    finally:
        if log:
            log.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=[item.value for item in ResourceLevel], required=True)
    parser.add_argument("--estimate-mib", type=int)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--duration-seconds", type=int, default=180)
    parser.add_argument("--interval-seconds", type=int, default=2)
    parser.add_argument("--log-jsonl", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        level = ResourceLevel(args.level)
        if args.estimate_mib is not None and args.estimate_mib <= 0:
            raise ValueError("estimate must be a positive MiB value")
        estimated_peak_bytes = args.estimate_mib * MIB if args.estimate_mib is not None else None
        if level is ResourceLevel.MEDIUM and estimated_peak_bytes is None:
            raise ValueError("medium tasks require --estimate-mib")
        if level is not ResourceLevel.LIGHT and not args.preflight_only and args.pid is None:
            raise ValueError("medium/heavy monitoring requires --pid unless --preflight-only is used")
        if args.runtime_only and args.pid is None:
            raise ValueError("--runtime-only requires --pid")
        if level is ResourceLevel.HEAVY and args.pid is None and not args.preflight_only:
            raise ValueError("heavy task monitoring requires --pid")
        return run_monitor(
            level=level,
            pid=args.pid,
            estimated_peak_bytes=estimated_peak_bytes,
            duration_seconds=args.duration_seconds,
            interval_seconds=args.interval_seconds,
            log_path=args.log_jsonl,
            runtime_only=args.runtime_only,
        )
    except Exception as exc:
        print(f"resource monitor failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
