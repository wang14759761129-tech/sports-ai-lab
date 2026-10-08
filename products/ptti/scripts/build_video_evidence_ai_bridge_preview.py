"""Build a standalone Windows AI Evidence Bridge Preview (not a release)."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Video-Evidence-AI-Bridge-Preview"


def main():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    build_root = Path(os.environ.get("PTTI_PREVIEW_BUILD_ROOT", ROOT / "build")).resolve()
    target = build_root / f"video-evidence-ai-bridge-{commit[:10]}"
    target.mkdir(parents=True, exist_ok=True)
    info = {
        "version": "0.2-video-evidence-ai-bridge-preview",
        "commit": commit,
        "source_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "environment": "DEVELOPMENT",
        "database": "%LOCALAPPDATA%/PTTI-Dev/VideoEvidencePreview/matches.db",
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
    subprocess.run(command, cwd=ROOT, check=True)
    folder = target / "dist" / NAME
    shutil.copy2(info_path, folder / "build-info.json")
    exe = folder / f"{NAME}.exe"
    (folder / "START-HERE.txt").write_text(
        "PTTI Video Evidence v0.2 · AI Evidence Bridge · 开发预览\n\n"
        f"运行本目录中的 {NAME}.exe。\n"
        "可登记本机比赛视频，导入与该视频 SHA256 严格匹配的冻结 Hit Event v0.3 D JSONL 结果包。\n"
        "所有导入结果均为 AI 建议，必须由用户确认或否决。UNKNOWN 击球方不会被猜测。\n"
        "AI 证据评分是规则评分，不是校准概率；GAME_4、GAME_5 与官方 TEST 在此预览中锁定。\n"
        "Extended OpenTTGames 来源为 CC BY-NC-SA 4.0，仅研究和非商业使用。素材不包含在本程序中。\n"
        "本地数据保存在 %LOCALAPPDATA%\\PTTI-Dev\\VideoEvidencePreview\\matches.db。\n"
        "此 Preview 不包含正式用户数据库、研究视频、权重或正式 Release。\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (folder / f"{exe.name}.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    print(json.dumps({"exe": str(exe), "sha256": digest, "bytes": exe.stat().st_size, "build": info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
