"""Build the separately named, isolated PTTI Next desktop preview from M1A."""

import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version as distribution_version
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import sys

import psutil

import build_dual_source_v061_preview as preview


preview.NAME = "PTTI-Next-Preview"
preview.PRODUCT_NAME = "PTTI Next"
preview.VERSION = "1.0.0-D2"
preview.BUILD_PREFIX = "ptti-next-d2"
preview.DATABASE_SUBDIR = "Next-D2-Preview"
preview.ENTRYPOINT = preview.ROOT / "apps" / "ptti_next_desktop.py"
preview.LOCAL_VISION_RUNTIME_HOME = None
MANIFEST_NAME = "package-manifest.json"
MANIFEST_SCHEMA = "ptti.next.desktop-package/1"
SUPPORTED_PYTHON_VERSIONS = {(3, 12), (3, 13)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"桌面包不能包含符号链接：{path.relative_to(root)}")
        if path.is_file() and path != root / MANIFEST_NAME:
            files[path.relative_to(root).as_posix()] = sha256_file(path)
    return files


def write_package_manifest(root: Path) -> Path:
    info = json.loads((root / "build-info.json").read_text(encoding="utf-8"))
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "product_name": preview.PRODUCT_NAME,
        "version": preview.VERSION,
        "commit": info["commit"],
        "files": package_files(root),
    }
    target = root / MANIFEST_NAME
    target.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


def verify_package(package_path: str | Path) -> dict[str, object]:
    root = Path(package_path).resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("待核验的桌面包路径不是文件夹。")

    try:
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        info = json.loads((root / "build-info.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("桌面包缺少可读取的构建身份或哈希清单。") from error

    if not isinstance(manifest, dict) or not isinstance(info, dict):
        raise RuntimeError("桌面包身份文件格式无效。")
    commit = info.get("commit")
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("product_name") != preview.PRODUCT_NAME
        or manifest.get("version") != preview.VERSION
        or manifest.get("commit") != commit
        or not isinstance(commit, str)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or info.get("product_name") != preview.PRODUCT_NAME
        or info.get("version") != preview.VERSION
        or info.get("channel") != "preview"
        or info.get("environment") != "DEVELOPMENT"
        or info.get("source_tree_dirty") is not False
        or info.get("official_release") is not False
        or info.get("production_database") != "NOT_ACCESSED"
        or info.get("media_included") is not False
    ):
        raise RuntimeError("桌面包身份不符合 PTTI Next 隔离预览要求。")

    expected = manifest.get("files")
    if (not isinstance(expected, dict) or not expected
            or any(not isinstance(name, str) or not isinstance(digest, str)
                   for name, digest in expected.items())):
        raise RuntimeError("桌面包哈希清单为空或格式无效。")
    for relative, digest in expected.items():
        part = PurePosixPath(relative)
        if (part.is_absolute() or ".." in part.parts or "\\" in relative
                or re.match(r"^[A-Za-z]:", relative)
                or not re.fullmatch(r"[0-9a-f]{64}", str(digest))):
            raise RuntimeError(f"桌面包清单包含不安全条目：{relative}")
        candidate = (root.joinpath(*part.parts)).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise RuntimeError(f"桌面包文件路径无效：{relative}")
        if sha256_file(candidate) != digest:
            raise RuntimeError(f"桌面包文件哈希不匹配：{relative}")

    actual = package_files(root)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise RuntimeError(f"桌面包文件集合不匹配；缺少={missing}，额外={unexpected}")

    executable = root / f"{preview.NAME}.exe"
    sidecar = root / f"{executable.name}.sha256"
    if not executable.is_file() or not sidecar.is_file():
        raise RuntimeError("PTTI Next 可执行文件或 SHA-256 旁车缺失。")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or fields[1] != executable.name or fields[0].lower() != sha256_file(executable):
        raise RuntimeError("PTTI Next 可执行文件与 SHA-256 旁车不匹配。")

    return {"status": "PASS", "product_name": preview.PRODUCT_NAME, "version": preview.VERSION,
            "commit": commit, "file_count": len(expected), "package": str(root)}


def preflight() -> tuple[Path, Path]:
    available_ram = psutil.virtual_memory().available
    if available_ram < preview.MIN_START_RAM_BYTES:
        raise RuntimeError(
            f"PTTI Next 打包暂停：可用内存 {available_ram / 1024**3:.2f} GiB，"
            "需要至少 2.50 GiB；没有启动构建子进程。"
        )

    if sys.version_info[:2] not in SUPPORTED_PYTHON_VERSIONS:
        version = ".".join(str(part) for part in sys.version_info[:3])
        raise RuntimeError(f"PTTI Next 打包支持 Python 3.12 或 3.13；当前是 {version}。")

    requirements = preview.ROOT / "requirements.txt"
    pinned: dict[str, str] = {}
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        item = raw.strip()
        if item and not item.startswith("#"):
            name, separator, expected = item.partition("==")
            if separator:
                pinned[name.strip().lower()] = expected.strip()
    required_distributions = (
        "fastapi", "uvicorn", "pydantic", "python-multipart", "pywebview", "pyinstaller", "psutil",
    )
    version_errors = []
    for name in required_distributions:
        expected = pinned.get(name)
        if not expected:
            version_errors.append(f"{name}: requirements.txt 未锁定版本")
            continue
        try:
            actual = distribution_version(name)
        except PackageNotFoundError:
            actual = "未安装"
        if actual != expected:
            version_errors.append(f"{name}: 需要 {expected}，当前 {actual}")
    if version_errors:
        raise RuntimeError("桌面打包依赖与 requirements.txt 不匹配：" + "; ".join(version_errors))

    missing_tools = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing_tools:
        raise RuntimeError("缺少桌面包运行依赖：" + ", ".join(missing_tools))

    node = shutil.which("node.exe") or shutil.which("node")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not node or not npm:
        raise RuntimeError("未找到 Node.js 和 npm，无法构建 PTTI Next 前端。")

    npm_cli = Path(npm).resolve().parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not npm_cli.is_file():
        raise RuntimeError(f"找不到 npm 命令入口：{npm_cli}")

    frontend = preview.ROOT / "frontend"
    for name in ("package.json", "package-lock.json"):
        if not (frontend / name).is_file():
            raise RuntimeError(f"前端构建清单缺失：{frontend / name}")
    return Path(node), npm_cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the isolated PTTI Next desktop preview.")
    parser.add_argument("--verify-only", action="store_true", help="verify a built package without launching it")
    parser.add_argument("package", nargs="?", help="package folder to verify")
    args = parser.parse_args(argv)

    if args.verify_only:
        if not args.package:
            parser.error("--verify-only requires a package folder")
        print(json.dumps(verify_package(args.package), ensure_ascii=False))
        return 0
    if args.package:
        parser.error("package folder is only accepted with --verify-only")

    node, npm_cli = preflight()
    frontend = preview.ROOT / "frontend"
    env = os.environ.copy()
    env["npm_config_offline"] = "true"
    env["npm_config_update_notifier"] = "false"

    subprocess.run([str(node), str(npm_cli), "ci", "--offline"], cwd=frontend, env=env, check=True)
    subprocess.run([str(node), str(npm_cli), "run", "build"], cwd=frontend, env=env, check=True)
    package = preview.main()
    write_package_manifest(package)
    print(json.dumps(verify_package(package), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
