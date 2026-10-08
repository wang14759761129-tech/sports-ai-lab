"""Build a standalone Windows AI Evidence Bridge Preview (not a release)."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Match-Library-v0.4-Preview"


def main():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    build_root = Path(os.environ.get("PTTI_PREVIEW_BUILD_ROOT", ROOT / "build")).resolve()
    target = build_root / f"match-library-v04-{commit[:10]}"
    target.mkdir(parents=True, exist_ok=False)
    info = {
        "version": "0.4-match-library-preview",
        "commit": commit,
        "source_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/MatchLibrary-v04-Preview/matches.db",
        "official_release": False,
        "production_database": "NOT_ACCESSED",
        "media_included": False,
        "models_included": False,
        "research_data_included": False,
        "research_gate": "HIT_EVENT_V0_3_CONFIG_FROZEN",
        "product_hit_gate": "HIT_EVENT_V0_2_PARTIAL",
        "dataset_license": "CC BY-NC-SA 4.0; research/non-commercial source references remain in imported evidence",
    }
    info_path = target / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
        "--name", NAME, "--icon", str(ROOT / "assets/ptti.ico"),
        "--collect-all", "webview", "--paths", str(ROOT), "--distpath", str(target / "dist"),
        "--workpath", str(target / "work"), "--specpath", str(target),
    ]
    for source, destination in [(info_path, "."), (ROOT / "frontend/dist", "frontend/dist"), (ROOT / "data/professional", "data/professional"), (ROOT / "data/samples", "data/samples")]:
        command.extend(["--add-data", f"{source};{destination}"])
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if not path:
            raise RuntimeError(f"Missing {tool}")
        command.extend(["--add-binary", f"{path};."])
    command.append(str(ROOT / "apps/desktop.py"))
    with (target / 'build.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    folder = target / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    exe = folder / f"{NAME}.exe"
    (folder / "START-HERE.txt").write_text(
        "PTTI 比赛录像库 v0.4 · 开发预览\n\n"
        f"完整解压后运行 {NAME}.exe；不要单独移动 EXE，须保留 _internal。\n"
        "首页先显示比赛资料和本机可看录像。职业比赛的官方网页不代表视频已授权。\n"
        "选择一次获准使用的视频文件夹，后台索引后确认录像，可立即播放；不需要 AI JSON。\n"
        "文件名关联只是建议，请核对运动员与比赛后确认；原视频不会复制或改写。\n"
        "可保存关键片段、专题和人工复核；AI 候选必须由用户审核。\n"
        "数据位于 %LOCALAPPDATA%\\PTTI-Dev\\MatchLibrary-v04-Preview\\matches.db。\n"
        "研究素材只限获准的非商业使用，不随程序分发。此包不包含视频、模型或用户数据库。\n"
        "比分搜索、Vision 轨迹与真实球速/旋转尚未在本阶段交付。\n"
        "打不开时检查完整解压和 Microsoft Edge WebView2 Runtime。\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{exe.name}.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "sha256": digest, "bytes": exe.stat().st_size, "build": info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
