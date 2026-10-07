"""Build a separate local Evidence Fusion preview without bundling research media."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Evidence-Fusion-Preview"
TARGET = ROOT / "build" / "evidence-fusion-preview"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    info = {
        "version": "0.2.0-evidence-fusion-preview",
        "commit": commit,
        "source_tree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db",
        "player_motion_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-rtmpose/runs/jobs",
        "player_tracking_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-sam2/runs/closed-loop/jobs",
        "hit_event_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-evidence-fusion/evaluation",
        "research_dataset": "Extended OpenTTGames official TRAIN only",
        "research_license": "CC BY-NC-SA 4.0; research / non-commercial",
        "hit_event_gate": "HIT_EVENT_V0_1_PARTIAL",
        "official_test_split": "NOT_ACCESSED",
        "production_database": "NOT_ACCESSED",
        "release_gate": "HISTORICAL_DB_UNVERIFIED",
        "official_release": False,
        "local_vision_runtime_home": str(ROOT),
    }
    info_path = TARGET / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
        "--name", NAME, "--icon", str(ROOT / "assets/ptti.ico"), "--collect-all", "webview",
        "--paths", str(ROOT), "--distpath", str(TARGET / "dist"),
        "--workpath", str(TARGET / "work"), "--specpath", str(TARGET),
    ]
    for source, destination in [
        (info_path, "."),
        (ROOT / "frontend/dist", "frontend/dist"),
        (ROOT / "data/professional", "data/professional"),
        (ROOT / "data/samples", "data/samples"),
    ]:
        command.extend(["--add-data", f"{source};{destination}"])
    for script in ("balltrack.py", "background.py", "overlay.py", "candidates.py"):
        command.extend(["--add-data", f"{ROOT / 'vision_worker' / script};vision_worker"])
    for tool in ("ffmpeg", "ffprobe"):
        executable = shutil.which(tool)
        if not executable:
            raise RuntimeError(f"{tool} is required to package working video import")
        command.extend(["--add-binary", f"{executable};."])
    command.append(str(ROOT / "apps/desktop.py"))
    subprocess.run(command, cwd=ROOT, check=True)

    folder = TARGET / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    (folder / "START-HERE.txt").write_text(
        "PTTI Evidence Fusion · 本机研究预览\n\n"
        f"双击 {NAME}.exe。\n"
        "视频分析 → 人物与球台 → 选择已完成追踪和姿态分析的 TRAIN 研究片段。\n"
        "时间轴显示击球候选；点选可查看证据、跳转视频，并确认、标记误报、修正时间或补充遗漏事件。\n"
        "候选不是确认击球，也不是校准概率；没有稳定球拍检测，手腕距离只作为手腕代理证据。\n"
        "研究视频、模型权重和分析输出保留在本机 PTTI-Dev 目录，不包含在此预览包中。\n"
        "仅用于 Extended OpenTTGames 许可允许的研究 / 非商业用途；不是正式发行版。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "bytes": exe.stat().st_size,
                      "sha256": digest, "build": info}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
