"""Build the isolated PTTI Dual Source v0.6.1 Windows Preview."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
NAME = "PTTI-Dual-Source-v0.6.1-Preview"
PRODUCT_NAME = "PTTI 双来源比赛观看"
VERSION = "0.6.1"
MIN_START_RAM_BYTES = int(2.5 * 1024**3)
HARD_RAM_FLOOR_BYTES = 2 * 1024**3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stop_process_tree(process: subprocess.Popen) -> None:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.Error:
            pass
    try:
        psutil.wait_procs(children, timeout=5)
    except psutil.Error:
        pass
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        for child in children:
            try:
                child.kill()
            except psutil.Error:
                pass
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def run_packager(command: list[str], log_path: Path) -> None:
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            available = psutil.virtual_memory().available
            if available < HARD_RAM_FLOOR_BYTES:
                log.write(
                    f"\nSAFE STOP: available RAM fell below the 2 GiB hard floor "
                    f"({available / 1024**3:.2f} GiB).\n"
                )
                log.flush()
                stop_process_tree(process)
                raise RuntimeError("Packaging stopped safely after available RAM crossed below 2 GiB")
            time.sleep(1)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)


def main() -> None:
    available_ram = psutil.virtual_memory().available
    if available_ram < MIN_START_RAM_BYTES:
        raise RuntimeError(
            f"Preview packaging paused: {available_ram / 1024**3:.2f} GiB available; "
            "recommended start headroom is 2.50 GiB. The hard runtime floor remains 2.00 GiB."
        )

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit and verify the source tree before packaging")

    frontend_dist = ROOT / "frontend" / "dist"
    if not (frontend_dist / "index.html").is_file():
        raise RuntimeError("Missing frontend production build at frontend/dist/index.html")
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    missing = [name for name, path in tools.items() if not path]
    if missing:
        raise RuntimeError(f"Missing required media tools: {', '.join(missing)}")

    default_build_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PTTI-Builds"
    build_root = Path(os.environ.get("PTTI_PREVIEW_BUILD_ROOT", default_build_root)).resolve()
    build_id = f"{commit[:10]}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    target = build_root / f"dual-source-v061-{build_id}"
    target.mkdir(parents=True, exist_ok=False)
    info = {
        "product_name": PRODUCT_NAME,
        "version": VERSION,
        "build_id": commit[:10],
        "commit": commit,
        "source_tree_dirty": False,
        "environment": "DEVELOPMENT",
        "build_available_ram_bytes": available_ram,
        "startup_ram_recommended_bytes": MIN_START_RAM_BYTES,
        "runtime_ram_hard_floor_bytes": HARD_RAM_FLOOR_BYTES,
        "database": "%LOCALAPPDATA%/PTTI-Dev/DualSource-v061-Preview/matches.db",
        "official_release": False,
        "production_database": "NOT_ACCESSED",
        "media_included": False,
        "models_included": False,
        "research_data_included": False,
        "synthetic_samples_included": True,
        "research_gate": "HIT_EVENT_V0_3_CONFIG_FROZEN",
        "hit_product_gate": "HIT_EVENT_V0_2_PARTIAL",
        "dual_source_product_gate": "DUAL_SOURCE_PRODUCT_PARTIAL",
    }
    info_path = target / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
        "--name", NAME, "--icon", str(ROOT / "assets" / "ptti.ico"),
        "--collect-all", "webview", "--paths", str(ROOT),
        "--distpath", str(target / "dist"), "--workpath", str(target / "work"),
        "--specpath", str(target),
    ]
    data_files = [
        (info_path, "."),
        (frontend_dist, "frontend/dist"),
        (ROOT / "data" / "professional", "data/professional"),
        (ROOT / "data" / "samples", "data/samples"),
        (ROOT / "THIRD_PARTY_NOTICES.md", "."),
    ]
    for source, destination in data_files:
        if not source.exists():
            raise RuntimeError(f"Required Preview input is missing: {source}")
        command.extend(["--add-data", f"{source};{destination}"])
    for path in tools.values():
        command.extend(["--add-binary", f"{path};."])
    command.append(str(ROOT / "apps" / "desktop.py"))

    run_packager(command, target / "build.log")
    folder = target / "dist" / NAME
    if not folder.is_dir() or not (folder / "_internal").is_dir():
        raise RuntimeError("PyInstaller output is incomplete: executable folder or _internal is missing")
    shutil.copy2(info_path, folder / "build-info.json")
    (folder / "START-HERE.txt").write_text(
        f"{PRODUCT_NAME} v{VERSION} Preview · build {commit[:10]}\n\n"
        f"完整解压后双击 {NAME}.exe；请保留旁边的 _internal 文件夹。\n"
        "首页可查看在线来源入口；受平台登录、嵌入或观看权限限制时，请使用官方观看页面。\n"
        "本地专业复盘仅适用于你有权使用的本机录像；不同视频版本的时间轴相互独立。\n"
        "预览数据保存在 %LOCALAPPDATA%\\PTTI-Dev\\DualSource-v061-Preview\\matches.db。\n"
        "本预览不含比赛视频、模型权重或正式个人数据库；内置示例数据为合成样例。\n"
        "无法打开时请确认完整解压，并已安装 Microsoft Edge WebView2 Runtime。\n",
        encoding="utf-8",
    )
    exe = folder / f"{NAME}.exe"
    digest = sha256_file(exe)
    (folder / f"{exe.name}.sha256").write_text(f"{digest}  {exe.name}\n", encoding="ascii")
    folder_bytes = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    print(json.dumps({
        "exe": str(exe),
        "sha256": digest,
        "bytes": exe.stat().st_size,
        "folder_bytes": folder_bytes,
        "build_info": info,
        "output_folder": str(folder),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
