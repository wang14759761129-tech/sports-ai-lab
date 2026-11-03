"""Chinese, noninteractive-by-default RC diagnostics; no database until --launch."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import uuid

try:
    from scripts import alpha_rc_qa_launcher as reviewed
except ModuleNotFoundError:
    import alpha_rc_qa_launcher as reviewed

COMMIT = "994fac25011d44c6e947439c7150bf9cd261f8a2"
EXE_HASH = "8871bca6d226648c5d90d3c53f4028ff0d12e6b1ab85c11685c50add6147fea1"
MANIFEST_HASH = "eccbd13be306e59c903c147ffa311768e141c48396e7e7a6d7a944fa22a20fd8"
BUILD_HASH = "649c62b881d8f587de95d9bf08b0b98032d2df6fe00f9088f493e3cb59edd3aa"
REQUIRED_RAM = int(2.5 * 1024**3)
MESSAGES = {
    "QA_RESOURCE_GATE": "内存不足：保存工作后正常关闭不用的应用，再检查；日常开发不受此门槛限制。",
    "QA_SESSION_IN_USE": "已有候选窗口：请正常关闭后再检查，不会强制结束。",
    "QA_CANDIDATE_IDENTITY_MISMATCH": "候选版本不符：使用本次归档修复版，不要通过旧桌面图标启动。",
    "QA_CANDIDATE_PACKAGE_INVALID": "候选文件缺失或完整性异常：保留现场，重新核对归档。",
    "RC_QA_PACKAGE_MODE_INVALID": "候选不是经过确认的隔离预览模式，拒绝启动。",
    "RC_QA_UNEXPECTED_FILES": "候选目录有额外文件，拒绝启动；不要在包内保存视频或数据库。",
    "QA_RESOURCE_CHECK_UNAVAILABLE": "无法读取实时内存，拒绝启动；保留日志用于排查。",
    "QA_PROCESS_CHECK_UNAVAILABLE": "无法确认候选实例，拒绝启动；保留日志用于排查。",
    "RC_QA_BASE_LAUNCHER_CHANGED": "基础启动器身份改变：需重新审核，不会跳过检查。",
    "QA_CANDIDATE_START_FAILED": "候选未能正常启动，请保留日志，不要反复启动。",
    "DIAGNOSTIC_FAILED": "预检发生异常，拒绝启动；日志仅保存脱敏错误代码。",
    "LOG_WRITE_FAILED": "无法安全保存启动日志，拒绝启动；检查诊断目录权限。",
    "START_OUTCOME_UNKNOWN": "启动结果无法确认：保留现场，先检查实例，不要再次启动。",
}


def safe_code(exc):
    code = getattr(exc, "code", None)
    if code is None and isinstance(exc, RuntimeError) and exc.args == ("RC_QA_BASE_LAUNCHER_CHANGED",):
        code = exc.args[0]
    return code if code in MESSAGES else "DIAGNOSTIC_FAILED"


def pin(base):
    return base.CandidatePin(COMMIT, reviewed.EXE_NAME, EXE_HASH, MANIFEST_HASH, BUILD_HASH)


def empty_report():
    return {"schema": "ptti.launch-diagnostic/1", "time_utc": datetime.now(timezone.utc).isoformat(),
              "target_commit": COMMIT, "exe_sha256": EXE_HASH, "integrity": "UNKNOWN",
              "available_ram_bytes": None, "required_ram_bytes": REQUIRED_RAM,
              "missing_ram_bytes": None, "conflict_count": None, "codes": [],
              "mode": "DIAGNOSE_ONLY", "status": "BLOCKED", "exe_started": False}


def diagnose(base, candidate_dir):
    report = empty_report()
    try:
        artifact = base.validate_candidate(candidate_dir, expected=pin(base))
        info = json.loads((artifact.directory / "build-info.json").read_text(encoding="utf-8-sig"))
        if (info.get("environment") != "DEVELOPMENT" or info.get("source_tree_dirty") is not False
                or info.get("official_release") is not False):
            raise base.QALauncherError("RC_QA_PACKAGE_MODE_INVALID")
        manifest = json.loads((artifact.directory / "manifest.json").read_text(encoding="utf-8-sig"))
        files = {p.relative_to(artifact.directory).as_posix() for p in artifact.directory.rglob("*") if p.is_file()}
        if files != set(manifest["files"]) | {"manifest.json"}:
            raise base.QALauncherError("RC_QA_UNEXPECTED_FILES")
        report["integrity"] = "PASS"
    except Exception as exc:
        report["integrity"] = "FAIL"
        report["codes"].append(safe_code(exc))
    try:
        available = base._available_memory_bytes()
        report.update(available_ram_bytes=available, missing_ram_bytes=max(0, REQUIRED_RAM - available))
        if available < REQUIRED_RAM:
            report["codes"].append("QA_RESOURCE_GATE")
    except Exception as exc:
        report["codes"].append(safe_code(exc))
    try:
        processes = base._running_candidate_processes()
        report["conflict_count"] = sum(name.casefold() == reviewed.EXE_NAME.casefold() for _, name in processes)
        if report["conflict_count"]:
            report["codes"].append("QA_SESSION_IN_USE")
    except Exception as exc:
        report["codes"].append(safe_code(exc))
    if not report["codes"]:
        report["status"] = "READY_REQUIRES_USER_CONFIRMATION"
    return report


def save_report(report, temp_root=None):
    root = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
    folder = root / "PTTI-Launch-Diagnostics"
    folder.mkdir(exist_ok=True)
    if folder.is_symlink() or getattr(folder.lstat(), "st_file_attributes", 0) & 0x400:
        raise RuntimeError("Unsafe log directory")
    if folder.resolve().parent != root:
        raise RuntimeError("Unsafe log directory")
    target = folder / ("launch-" + uuid.uuid4().hex + ".json")
    with target.open("x", encoding="utf8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return target.name


def show(report):
    print("PTTI Cinema 修复版 · 启动诊断（默认不启动）")
    print("目标源码：" + COMMIT)
    print("候选完整性：" + report["integrity"])
    available = report["available_ram_bytes"]
    if available is None:
        print("实时内存：无法读取")
    else:
        print(f"可用内存：{available / 1024**3:.3f} GiB；启动门槛：2.500 GiB；还缺：{report['missing_ram_bytes'] / 1024**3:.3f} GiB")
    print("冲突实例：" + (str(report["conflict_count"]) if report["conflict_count"] is not None else "无法确认"))
    for code in report["codes"]:
        print(code + "：" + MESSAGES[code])
    if not report["codes"]:
        print("预检通过。需要用户确认后才能启动；启动时会再次检查资源。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", default=str(Path.home() / "PTTI-Archives/Playback-Recovery/Run-38410292279-Alpha-RC/candidate"))
    parser.add_argument("--launch", action="store_true", help="仅在获得即时授权后，启动新隔离会话")
    args = parser.parse_args(argv)
    try:
        base = reviewed.load_base()
        report = diagnose(base, args.candidate_dir)
    except Exception as exc:
        report = empty_report()
        report["codes"] = [safe_code(exc)]
    show(report)
    launch_attempted = False
    try:
        name = save_report(report)
        print("诊断日志：%TEMP%\\PTTI-Launch-Diagnostics\\" + name)
    except Exception:
        print(MESSAGES["LOG_WRITE_FAILED"])
        return 2
    if report["codes"]:
        return 2
    if not args.launch:
        return 0
    try:
        plan = base.prepare_new_plan(args.candidate_dir, expected=pin(base))
        base._require_no_running_candidate(plan.candidate)
        # One final live check; low RAM does not prevent diagnostics or development.
        base._require_resource_gate()
        launch_attempted = True
        base._launch(plan)
    except Exception as exc:
        code = safe_code(exc)
        if launch_attempted and code != "QA_CANDIDATE_START_FAILED":
            code = "START_OUTCOME_UNKNOWN"
            report["exe_started"] = None
        report.update(mode="LAUNCH", status="BLOCKED", codes=[code])
        if code == "QA_RESOURCE_GATE":
            try:
                available = base._available_memory_bytes()
                report.update(available_ram_bytes=available, missing_ram_bytes=max(0, REQUIRED_RAM - available))
            except Exception:
                report.update(available_ram_bytes=None, missing_ram_bytes=None)
            show(report)
        print(code + "：" + MESSAGES[code])
        try:
            save_report(report)
        except Exception:
            print(MESSAGES["LOG_WRITE_FAILED"])
        return 2
    report.update(mode="LAUNCH", status="STARTED", exe_started=True)
    try:
        save_report(report)
    except Exception:
        print("候选已启动，但启动后日志更新失败；不要重复启动。")
    print("候选已启动，全新 OS Temp 隔离会话；请完成审核，不会自动登记。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    raise SystemExit(main())
