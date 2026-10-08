"""Standalone non-release Windows player preview; no models or research media."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Video-Evidence-Preview"


def main():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    target = ROOT / "build" / f"video-evidence-{commit[:10]}"
    target.mkdir(parents=True, exist_ok=True)
    info = {
        "version": "0.1-video-evidence-preview",
        "commit": commit,
        "source_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/VideoEvidencePreview/matches.db",
        "official_release": False,
        "production_database": "NOT_ACCESSED",
        "media_included": False,
        "models_included": False,
        "hit_research_gate": "HIT_EVENT_V0_3_CONFIG_FROZEN",
        "hit_product_gate": "HIT_EVENT_V0_2_PARTIAL",
    }
    info_path = target / "build-info.json"
    info_path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--onedir",
        "--name",
        NAME,
        "--icon",
        str(ROOT / "assets/ptti.ico"),
        "--collect-all",
        "webview",
        "--paths",
        str(ROOT),
        "--distpath",
        str(target / "dist"),
        "--workpath",
        str(target / "work"),
        "--specpath",
        str(target),
    ]
    for source, destination in [
        (info_path, "."),
        (ROOT / "frontend/dist", "frontend/dist"),
        (ROOT / "data/professional", "data/professional"),
        (ROOT / "data/samples", "data/samples"),
    ]:
        command.extend(["--add-data", f"{source};{destination}"])
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if not path:
            raise RuntimeError(f"Missing {tool}")
        command.extend(["--add-binary", f"{path};."])
    command.append(str(ROOT / "apps/desktop.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    folder = target / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    (folder / "START-HERE.txt").write_text(
        "PTTI 视频证据复盘 · 独立开发预览\n\n"
        f"双击 {NAME}.exe → 视频复盘 → 导入本机原视频。\n"
        "确认使用权限后即可播放。原视频不复制；完整性校验在后台进行。\n"
        "标记起止点、添加标签和笔记，保存为关键片段。\n"
        "勾选多个片段建立收藏夹，点击连续播放。\n"
        "原视频移走后，使用重新关联；系统必须确认 SHA256 一致。\n"
        "数据保存在 %LOCALAPPDATA%\\PTTI-Dev\\VideoEvidencePreview\\matches.db。\n"
        "本预览不包含研究视频、AI 模型或正式数据库；没有进行正式发布。\n"
        "逐帧按钮是按源帧率近似移动。非 H.264 MP4 编码可能无法在 WebView2 中播放。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{NAME}.exe.sha256").write_text(
        f"{digest}  {exe.name}\n", encoding="ascii"
    )
    print(
        json.dumps(
            {
                "exe": str(exe),
                "sha256": digest,
                "bytes": exe.stat().st_size,
                "build": info,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
