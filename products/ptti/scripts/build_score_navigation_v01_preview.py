"""Build the isolated Windows Score Navigation v0.1 Preview (not a release)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Score-Navigation-v0.1-Preview"
PRODUCT_NAME = "PTTI 比分导航"
VERSION = "0.1"
MIN_AVAILABLE_RAM_BYTES = 2 * 1024**3


def main():
    available_ram = psutil.virtual_memory().available
    if available_ram < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError(
            f"Preview packaging paused: {available_ram / 1024**3:.2f} GiB RAM available; "
            "at least 2.00 GiB is required. Close no user applications automatically and retry later."
        )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit and verify the source tree before packaging")
    build_root = Path(os.environ.get("PTTI_PREVIEW_BUILD_ROOT", ROOT / "build")).resolve()
    target = build_root / f"score-navigation-v01-{commit[:10]}"
    target.mkdir(parents=True, exist_ok=False)
    info = {
        "product_name": PRODUCT_NAME, "version": VERSION,
        "build_id": commit[:10], "commit": commit,
        "source_tree_dirty": False, "environment": "DEVELOPMENT",
        "build_available_ram_bytes": available_ram,
        "database": "%LOCALAPPDATA%/PTTI-Dev/ScoreNavigation-v01-Preview/matches.db",
        "official_release": False, "production_database": "NOT_ACCESSED",
        "media_included": False, "models_included": False,
        "research_data_included": False,
        "research_gate": "HIT_EVENT_V0_3_CONFIG_FROZEN",
        "hit_product_gate": "HIT_EVENT_V0_2_PARTIAL",
        "score_navigation_gate": "SCORE_NAVIGATION_V0_1_PARTIAL",
    }
    info_path = target / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
               "--name", NAME, "--icon", str(ROOT / "assets/ptti.ico"),
               "--collect-all", "webview", "--paths", str(ROOT),
               "--distpath", str(target / "dist"), "--workpath", str(target / "work"),
               "--specpath", str(target)]
    for source, destination in [(info_path, "."), (ROOT / "frontend/dist", "frontend/dist"),
                               (ROOT / "data/professional", "data/professional"),
                               (ROOT / "data/samples", "data/samples")]:
        command.extend(["--add-data", f"{source};{destination}"])
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if not path:
            raise RuntimeError(f"Missing required media tool: {tool}")
        command.extend(["--add-binary", f"{path};."])
    command.append(str(ROOT / "apps/desktop.py"))
    with (target / "build.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    folder = target / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    (folder / "START-HERE.txt").write_text(
        f"{PRODUCT_NAME} v{VERSION} Preview · build {commit[:10]}\n\n"
        f"完整解压后双击 {NAME}.exe；请保留旁边的 _internal 文件夹。\n"
        "在比赛录像页面选择你有权使用的本机录像。播放器内可按局、比分和关键分建立人工索引。\n"
        "分前比分由用户填写；比分牌出现时间与这一分开始时间分开记录。未知信息请保留未知。\n"
        "已确认比分支持回到视频预览并使用现有片段播放列表连续复盘。\n"
        "预览数据保存在 %LOCALAPPDATA%\\PTTI-Dev\\ScoreNavigation-v01-Preview\\matches.db。\n"
        "此预览不含视频、模型、个人数据库，也不是正式发布。\n"
        "无法打开时请确认完整解压，并安装 Microsoft Edge WebView2 Runtime。\n",
        encoding="utf-8")
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{exe.name}.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "sha256": digest, "bytes": exe.stat().st_size,
                      "folder_bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()),
                      "build_info": info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
