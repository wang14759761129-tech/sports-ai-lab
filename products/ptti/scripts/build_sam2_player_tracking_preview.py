"""Build an isolated, non-release desktop preview for the SAM 2 tracking evidence."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Vision-v2-Player-Tracking-Preview"
TARGET = ROOT / "build" / "sam2-player-tracking-preview"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    info = {
        "version": "0.2.0-sam2-player-tracking-preview",
        "commit": commit,
        "source_tree_dirty": dirty,
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db",
        "player_tracking_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2-sam2/runs/multi-match-final",
        "tracker_config_sha256": "9f2cc04ed25e935b6edb53fa296203a5091dabe9ff7ae349d77ce538dbb914bd",
        "release_gate": "HISTORICAL_DB_UNVERIFIED",
        "vision_gate": "SAM2_PLAYER_TRACKING_PARTIAL",
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
    for source, dest in [
        (info_path, "."),
        (ROOT / "frontend/dist", "frontend/dist"),
        (ROOT / "data/professional", "data/professional"),
        (ROOT / "data/samples", "data/samples"),
    ]:
        command.extend(["--add-data", f"{source};{dest}"])
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
        "PTTI Vision v2 · 球员持续追踪开发预览\n\n"
        f"双击 {NAME}.exe。\n"
        "视频分析 → 人物与球台：查看本机已完成的真实研究片段、Near/Far mask 和逐帧抽查。\n"
        "本轮官方训练集 5 场片段中，3 场完成 SAM 2 传播，2 场因缺少有效双球员种子而停止；远端轨迹仍有丢失。\n"
        "角色种子尚未接入桌面端的运行前确认；这是研究预览，不是正式产品或发布版本。\n"
        "研究视频、SAM 2 权重和追踪输出未打包；仅从本机 PTTI-Dev 目录读取。\n"
        "数据使用范围：Extended OpenTTGames，CC BY-NC-SA 4.0，研究 / 非商业。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "bytes": exe.stat().st_size, "sha256": digest, "build": info},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
