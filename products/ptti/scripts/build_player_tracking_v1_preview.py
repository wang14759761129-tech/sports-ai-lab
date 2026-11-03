"""Build a local, non-release Preview for Player Tracking v1 QA."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Vision-v2-Player-Tracking-v1-Preview"
TARGET = Path(os.environ.get("PTTI_PLAYER_TRACKING_PREVIEW_BUILD_ROOT", r"C:\ptti-v1-preview"))


def main() -> None:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if status.strip():
        raise RuntimeError("Commit the Preview source before building a verifiable artifact")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    TARGET.mkdir(parents=True, exist_ok=True)
    info = {
        "version": "0.2.0-player-tracking-v1-preview",
        "commit": commit,
        "source_tree_dirty": False,
        "environment": "DEVELOPMENT",
        "database": "%TEMP%/PTTI-PlayerTracking-v1-Preview-QA/matches.db",
        "local_vision_runtime_home": str(ROOT),
        "external_vision_runtime_required": True,
        "player_tracking_config_sha256": "970115a09122ba7350bc62c4d82b69ff16d304740cd6818456d57511c48471e0",
        "release_gate": "HISTORICAL_DB_UNVERIFIED",
        "vision_gate": "PLAYER_TRACKING_V1_PARTIAL_PENDING_VALIDATION",
        "official_release": False,
    }
    info_path = TARGET / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
        "--name", NAME, "--icon", str(ROOT / "assets" / "ptti.ico"),
        "--collect-all", "webview", "--paths", str(ROOT),
        "--distpath", str(TARGET / "dist"), "--workpath", str(TARGET / "work"),
        "--specpath", str(TARGET),
        "--add-data", f"{info_path};.",
        "--add-data", f"{ROOT / 'frontend' / 'dist'};frontend/dist",
        "--add-data", f"{ROOT / 'data' / 'professional'};data/professional",
        "--add-data", f"{ROOT / 'data' / 'samples'};data/samples",
        "--add-data", f"{ROOT / 'configs' / 'vision' / 'PLAYER_TRACKING_V1_CANDIDATE.json'};configs/vision",
    ]
    for tool in ("ffmpeg", "ffprobe"):
        executable = shutil.which(tool)
        if not executable:
            raise RuntimeError(f"{tool} is required for packaged video support")
        command.extend(["--add-binary", f"{executable};."])
    command.append(str(ROOT / "apps" / "desktop.py"))
    subprocess.run(command, cwd=ROOT, check=True)

    folder = TARGET / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    (folder / "START-HERE.txt").write_text(
        "PTTI Vision v2 · Player Tracking v1 QA Preview\n\n"
        f"双击 {NAME}.exe。\n"
        "本预览用于本机研究验证，追踪 worker 与 GPU 环境从同一开发目录隔离调用。\n"
        "研究视频、模型权重和追踪结果不会打包；官方研究数据按 CC BY-NC-SA 4.0 非商业条款使用。\n"
        "这不是正式发布版本，不覆盖 PTTI v0.1.2；不要用于商业用途。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "bytes": exe.stat().st_size, "sha256": digest,
                      "build": info}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
