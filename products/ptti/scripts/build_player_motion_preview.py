"""Build a separate local Windows preview for quality-gated player motion."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Vision-v2-Player-Motion-Preview"
TARGET = ROOT / "build" / "player-motion-preview"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    info = {
        "version": "0.2.0-player-motion-preview",
        "commit": commit,
        "source_tree_dirty": dirty,
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db",
        "player_motion_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-rtmpose/runs/jobs",
        "player_tracking_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-sam2/runs/closed-loop/jobs",
        "pose_runtime_external": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-rtmpose",
        "research_dataset": "Extended OpenTTGames",
        "research_license": "CC BY-NC-SA 4.0; research / non-commercial",
        "tracking_gate": "PLAYER_TRACKING_V1_PARTIAL",
        "player_pose_gate": "PLAYER_POSE_V0_1_PARTIAL",
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
        "PTTI Vision v2 · 人体动作研究预览\n\n"
        f"双击 {NAME}.exe。\n"
        "视频分析 → 人物与球台：选择本机已经完成追踪的真实研究片段，查看可信窗口中的 Near/Far 骨架、动作时间线和 2D 估计。\n"
        "低质量、身份冲突、追踪丢失或球员离画的时间窗会显示为复核/无姿态。\n"
        "研究视频、姿态模型和分析输出均留在本机开发目录，不包含在预览文件夹中。\n"
        "数据仅用于 Extended OpenTTGames 许可允许的研究 / 非商业用途；模型权重许可未单独确认，未随预览分发。\n"
        "这是独立开发预览，不覆盖正式 v0.1.2，也不是 v0.2 发布版本。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "bytes": exe.stat().st_size,
                      "sha256": digest, "build": info}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
