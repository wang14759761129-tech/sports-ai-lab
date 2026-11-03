import json

from scripts import resource_policy_v2 as policy
from scripts.resource_policy_v2 import (
    GIB,
    MIB,
    ResourceLevel,
    ResourceSnapshot,
    evaluate_runtime,
    evaluate_start,
)


def healthy_snapshot(available_gib=4, commit_headroom_gib=8):
    total = 16 * GIB
    limit = 32 * GIB
    return ResourceSnapshot(
        total_physical_bytes=total,
        available_physical_bytes=int(available_gib * GIB),
        commit_used_bytes=limit - int(commit_headroom_gib * GIB),
        commit_limit_bytes=limit,
        pagefile_free_bytes=15 * GIB,
    )


def test_lightweight_task_is_not_blocked_by_the_old_2_5_gib_rule():
    snapshot = healthy_snapshot(available_gib=1.75, commit_headroom_gib=19)

    decision = evaluate_start(ResourceLevel.LIGHT, snapshot)

    assert decision.allowed is True
    assert decision.level is ResourceLevel.LIGHT


def test_lightweight_task_stops_under_severe_physical_pressure():
    decision = evaluate_start(ResourceLevel.LIGHT, healthy_snapshot(0.4, 10))
    assert decision.allowed is False
    assert decision.reason == "SEVERE_SYSTEM_MEMORY_PRESSURE"


def test_medium_task_requires_measured_budget_and_monitoring():
    decision = evaluate_start(
        ResourceLevel.MEDIUM,
        healthy_snapshot(available_gib=2.25, commit_headroom_gib=8),
        estimated_peak_bytes=1024 * MIB,
    )
    assert decision.allowed is True
    assert decision.monitor_required is True
    assert decision.projected_available_bytes == int(1.25 * GIB)


def test_medium_task_blocks_when_projected_reserve_is_insufficient():
    decision = evaluate_start(
        ResourceLevel.MEDIUM,
        healthy_snapshot(available_gib=1.25, commit_headroom_gib=8),
        estimated_peak_bytes=1024 * MIB,
    )
    assert decision.allowed is False
    assert decision.reason == "PROJECTED_PHYSICAL_RESERVE_TOO_LOW"


def test_medium_task_fails_closed_without_an_estimate_or_commit_measurement():
    assert not evaluate_start(ResourceLevel.MEDIUM, healthy_snapshot()).allowed
    missing_commit = ResourceSnapshot(16 * GIB, 4 * GIB)
    assert not evaluate_start(
        ResourceLevel.MEDIUM,
        missing_commit,
        estimated_peak_bytes=512 * MIB,
    ).allowed


def test_medium_task_blocks_when_projected_commit_reserve_is_insufficient():
    decision = evaluate_start(
        ResourceLevel.MEDIUM,
        healthy_snapshot(available_gib=4, commit_headroom_gib=1.5),
        estimated_peak_bytes=1024 * MIB,
    )
    assert not decision.allowed
    assert decision.reason == "PROJECTED_COMMIT_RESERVE_TOO_LOW"


def test_heavy_start_keeps_the_2_5_gib_budget():
    below = evaluate_start(ResourceLevel.HEAVY, healthy_snapshot(2.49, 8))
    above = evaluate_start(ResourceLevel.HEAVY, healthy_snapshot(2.5, 8))
    assert not below.allowed
    assert above.allowed


def test_medium_runtime_stops_on_pressure_or_measured_budget_overrun():
    under_pressure = evaluate_runtime(
        ResourceLevel.MEDIUM,
        healthy_snapshot(available_gib=0.45, commit_headroom_gib=10),
        process_tree_working_set_bytes=200 * MIB,
        estimated_peak_bytes=1024 * MIB,
    )
    over_budget = evaluate_runtime(
        ResourceLevel.MEDIUM,
        healthy_snapshot(),
        process_tree_working_set_bytes=1100 * MIB,
        estimated_peak_bytes=1024 * MIB,
    )
    assert not under_pressure.allowed
    assert under_pressure.reason == "SEVERE_SYSTEM_MEMORY_PRESSURE"
    assert not over_budget.allowed
    assert over_budget.reason == "OBSERVED_PROCESS_BUDGET_EXCEEDED"


def test_heavy_runtime_retains_its_2_gib_floor():
    decision = evaluate_runtime(
        ResourceLevel.HEAVY,
        healthy_snapshot(available_gib=1.99, commit_headroom_gib=8),
    )
    assert not decision.allowed
    assert decision.reason == "HEAVY_RUNTIME_FLOOR_NOT_MET"


def test_light_cli_is_a_supported_one_shot_without_pid_or_budget(monkeypatch, capsys):
    monkeypatch.setattr(policy, "collect_resource_snapshot", lambda: healthy_snapshot(1.75, 10))

    result = policy.main(["--level", "light"])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["decision"]["allowed"] is True
    assert output["decision"]["reason"] == "LIGHT_TASK_WITHIN_SYSTEM_HEADROOM"


def test_medium_preflight_cli_uses_v2_without_starting_a_process(monkeypatch, capsys):
    monkeypatch.setattr(policy, "collect_resource_snapshot", lambda: healthy_snapshot(2.25, 8))

    result = policy.main(["--level", "medium", "--estimate-mib", "1024", "--preflight-only"])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["decision"]["allowed"] is True
    assert output["decision"]["projected_available_bytes"] == int(1.25 * GIB)


def test_runtime_monitor_exits_cleanly_when_the_qa_process_is_closed(monkeypatch, capsys):
    import psutil

    monkeypatch.setattr(policy, "collect_resource_snapshot", lambda: healthy_snapshot())
    monkeypatch.setattr(
        policy,
        "process_tree_working_set_bytes",
        lambda _pid: (_ for _ in ()).throw(psutil.NoSuchProcess(999)),
    )

    result = policy.run_monitor(
        level=ResourceLevel.MEDIUM,
        pid=999,
        estimated_peak_bytes=1024 * MIB,
        duration_seconds=1,
        interval_seconds=1,
        runtime_only=True,
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["decision"]["reason"] == "QA_PROCESS_EXITED"


def test_log_creates_runtime_visible_parent_and_reports_actual_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(policy, "collect_resource_snapshot", lambda: healthy_snapshot(1.75, 10))
    log_path = tmp_path / "not-created-by-python" / "monitor.jsonl"
    result = policy.main(["--level", "light", "--preflight-only", "--log-jsonl", str(log_path)])
    assert result == 0
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output[0]["monitor_log"] == {"requested": str(log_path), "actual": str(log_path.resolve())}
    assert json.loads(log_path.read_text(encoding="utf-8"))["decision"]["allowed"] is True


def test_unwritable_log_parent_is_a_visible_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(policy, "collect_resource_snapshot", lambda: healthy_snapshot())
    occupied = tmp_path / "occupied"
    occupied.write_text("synthetic fixture", encoding="utf-8")
    result = policy.main(["--level", "light", "--preflight-only", "--log-jsonl", str(occupied / "monitor.jsonl")])
    assert result == 2
    captured = capsys.readouterr()
    assert "resource monitor failed" in captured.err
    assert '"allowed": true' not in captured.out
