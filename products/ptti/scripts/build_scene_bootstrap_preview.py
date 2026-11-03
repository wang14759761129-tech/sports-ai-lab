"""Build an isolated local preview without replacing any prior preview."""

import hashlib
import json
import shutil
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = os.environ.get("PTTI_PREVIEW_NAME", "PTTI-Vision-Lab-v2-Scene-Preview")
BUILD_DIR = os.environ.get("PTTI_PREVIEW_BUILD_DIR", "vision-lab-v2-scene-preview")
VERSION = os.environ.get("PTTI_PREVIEW_VERSION", "0.2.0-vision-lab-v2-scene-preview")
START_TITLE = os.environ.get("PTTI_PREVIEW_START_TITLE", "PTTI Vision Lab v2 场景识别预览")


def main():
    target = ROOT / "build" / BUILD_DIR
    target.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    info = {
        "version": VERSION,
        "commit": commit,
        "source_tree_dirty": bool(dirty),
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/ProfessionalPreview/matches.db",
        "scene_bootstrap_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2/scene-bootstrap",
        "person_detector_results": "%LOCALAPPDATA%/PTTI-Dev/vision-v2/scene-bootstrap/person_detector_evaluation.json",
        "person_detector_gate": "PERSON_DETECTOR_PARTIAL",
        "research_data_license": "CC BY-NC-SA 4.0; non-commercial",
        "release_gate": "HISTORICAL_DB_UNVERIFIED",
        "vision_gate": "SCENE_BOOTSTRAP_PARTIAL",
        "official_release": False,
    }
    info_path = target / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
               "--name", NAME, "--icon", str(ROOT / "assets/ptti.ico"), "--collect-all", "webview",
               "--paths", str(ROOT), "--distpath", str(target / "dist"),
               "--workpath", str(target / "work"), "--specpath", str(target)]
    for source, dest in [(info_path, "."), (ROOT / "frontend/dist", "frontend/dist"),
                         (ROOT / "data/professional", "data/professional"),
                         (ROOT / "data/samples", "data/samples")]:
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
    folder = target / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    exe = folder / f"{NAME}.exe"
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(f"{sha}  {exe.name}\n", encoding="ascii")
    (folder / "START-HERE.txt").write_text(
        f"{START_TITLE}\n\n双击 {NAME}.exe。\n"
        "视频分析 → 人物与球台：查看真实研究样本，切换新增比赛、只看异常、修正角色、确认本帧。\n"
        "研究中心展示模型与对比证据。结果仅供研究 / 非商业复核，身份需要人工确认。\n"
        "示例视频、抽样帧和权重未包含在此文件夹中；结果从本机 PTTI-Dev 读取。\n"
        "开发预览不会覆盖正式 v0.1.2，也不是正式发布版本。\n", encoding="utf-8")
    print(json.dumps({"exe": str(exe), "bytes": exe.stat().st_size,
                      "sha256": sha, "build": info}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
