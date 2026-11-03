"""Build an isolated GOAL23 Desktop Fan QA package from byte-pinned inputs."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "goal23-build.json"
HOST_TEMPLATE = HERE / "desktop_host.py"
PROCESS_IDENTITY = HERE / "Goal23.ProcessIdentity.ps1"
PROTECTED_PORTS = {4174, 4183, 4199, 4200, 4201, 4202, 4203, 4204, 4205, 4206, 4207}
FORBIDDEN_HOST_TOKENS = ("matches.db", "PTTI-Dev", "LOCALAPPDATA", "Start-PTTI", "NativeRoot", "sqlite3")
CANONICAL_LF_TEXT_PATHS = {
    "src/internal-review/goal19-watchability-evidence-v0.1.json",
    "scripts/contracts/goal19-1-watchability-evidence-v0.1.schema.json",
    "scripts/contracts/user-watch-feedback-v0.1.schema.json",
    "src/internal-review/goal19.3-user-playback-reports-v0.1.json",
    "scripts/contracts/user-watch-playback-reports-v0.1.schema.json",
}
GOAL30_SCHEMA = "ptti.desktop-fan.goal30-build.v1"
GOAL30_PUBLIC_PACKAGES = {
    "data/fan-inspiration-v0.1.json", "data/match-reports-v0.1.json",
    "data/match-library-strict-public.json", "data/goal17-official-match-video-additions.json",
    "data/goal17-athlete-photo-additions.json", "data/goal14-fan-content-strict-public.json",
    "data/pro-demo-match-intelligence.json", "data/web-strict-public.json",
}
GOAL30_SCHEMAS = {"src/contracts/fan-inspiration-v0.1.schema.json"}
GOAL30_MAIN_SCHEMAS = {
    "products/ptti-integration/contracts/fan-inspiration-v0.1.schema.json",
    "products/ptti-integration/contracts/match-report-evidence-v0.1.schema.json",
}


class BuildError(RuntimeError):
    pass


class BuildBlocked(BuildError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_allowlisted_utf8_text(raw: bytes, entry: dict[str, Any]) -> tuple[dict[str, str], bytes]:
    """Accept only pinned LF/CRLF byte forms and return raw plus canonical-LF identities."""
    if entry.get("encoding") != "utf-8":
        raise BuildError("Allowlisted line-ending normalization requires explicit UTF-8 encoding")
    raw_sha = hashlib.sha256(raw).hexdigest()
    allowed_raw = entry.get("allowed_raw_sha256")
    if not isinstance(allowed_raw, list) or raw_sha not in {str(x).lower() for x in allowed_raw}:
        raise BuildError("Allowlisted text raw SHA-256 is not an approved line-ending variant")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise BuildError("Allowlisted text is not valid UTF-8") from exc
    if text.startswith("\ufeff") or "\x00" in text:
        raise BuildError("Allowlisted text contains a BOM or binary NUL")
    if "\r" in text.replace("\r\n", ""):
        raise BuildError("Allowlisted text contains a bare CR line ending")
    if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in text) or "\x7f" in text:
        raise BuildError("Allowlisted text contains a binary control character")
    canonical = text.replace("\r\n", "\n").encode("utf-8")
    canonical_sha = hashlib.sha256(canonical).hexdigest()
    if canonical_sha != str(entry.get("canonical_lf_sha256", "")).lower():
        raise BuildError("Allowlisted text canonical-LF SHA-256 mismatch")
    if raw == canonical:
        line_endings = "LF"
    elif raw == canonical.replace(b"\n", b"\r\n"):
        line_endings = "CRLF"
    else:
        raise BuildError("Allowlisted text is not an exact LF or CRLF serialization")
    return {
        "raw_sha256": raw_sha,
        "canonical_lf_sha256": canonical_sha,
        "line_endings": line_endings,
    }, canonical


def verify_allowlisted_utf8_text(raw: bytes, entry: dict[str, Any]) -> dict[str, str]:
    return normalize_allowlisted_utf8_text(raw, entry)[0]


def verify_allowlisted_text_inputs(web_root: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    root = web_root.resolve(strict=True)
    entries = config.get("canonical_lf_text_inputs")
    if not isinstance(entries, list) or {entry.get("path") for entry in entries if isinstance(entry, dict)} != CANONICAL_LF_TEXT_PATHS:
        raise BuildError("Canonical-LF normalization allowlist must match the reviewed GOAL23 text input")
    results: list[dict[str, str]] = []
    for entry in entries:
        relative = str(entry.get("path", ""))
        part = PurePosixPath(relative)
        if part.is_absolute() or ".." in part.parts or "\\" in relative or re.match(r"^[A-Za-z]:", relative):
            raise BuildError(f"Unsafe canonical-LF allowlist path: {relative}")
        candidate = root.joinpath(*part.parts)
        cursor = root
        for item in part.parts:
            cursor = cursor / item
            if cursor.is_symlink():
                raise BuildError(f"Symlink is forbidden for canonical-LF input: {relative}")
        try:
            candidate.resolve(strict=True).relative_to(root)
            raw = candidate.read_bytes()
        except FileNotFoundError as exc:
            raise BuildError(f"Canonical-LF input is missing: {relative}") from exc
        except ValueError as exc:
            raise BuildError(f"Canonical-LF input escapes San worktree: {relative}") from exc
        if not candidate.is_file():
            raise BuildError(f"Canonical-LF input is not a regular file: {relative}")
        meta = verify_allowlisted_utf8_text(raw, entry)
        results.append({"path": relative, **meta})
    return results


def tree_manifest(root: Path) -> dict[str, str]:
    root = root.resolve(strict=True)
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BuildError(f"Symlink is forbidden in build input: {path.relative_to(root)}")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = sha256_file(path)
    return files


def canonical_tree_sha256(root: Path) -> str:
    payload = json.dumps(tree_manifest(root), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema") not in {"ptti.desktop-fan.goal23-build.v1", GOAL30_SCHEMA}:
        raise BuildError("Unsupported GOAL23 build config schema")
    for field in ("san_commit", "main_commit"):
        value = str(config.get(field, ""))
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise BuildError(f"Invalid pinned commit: {field}")
    for field in ("main_inspiration_json_sha256", "static_artifact_sha256", "parent_release_manifest_sha256"):
        value = str(config.get(field, ""))
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise BuildError(f"Invalid pinned SHA-256: {field}")
    text_entries = config.get("canonical_lf_text_inputs")
    if not isinstance(text_entries, list) or len(text_entries) != len(CANONICAL_LF_TEXT_PATHS):
        raise BuildError("GOAL23 must explicitly pin every reviewed canonical-LF text input")
    configured_paths = {entry.get("path") for entry in text_entries if isinstance(entry, dict)}
    if configured_paths != CANONICAL_LF_TEXT_PATHS:
        raise BuildError("GOAL23 canonical-LF input paths do not match the reviewed allowlist")
    for text_entry in text_entries:
        if text_entry.get("encoding") != "utf-8":
            raise BuildError("GOAL23 canonical-LF input must declare UTF-8")
        canonical_sha = str(text_entry.get("canonical_lf_sha256", ""))
        raw_hashes = text_entry.get("allowed_raw_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", canonical_sha):
            raise BuildError("GOAL23 canonical-LF input SHA-256 is invalid")
        if (not isinstance(raw_hashes, list) or len(raw_hashes) != 2
                or any(not isinstance(value, str) for value in raw_hashes)
                or len(set(raw_hashes)) != 2):
            raise BuildError("GOAL23 must pin the exact LF and CRLF raw SHA-256 variants")
        if any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in raw_hashes):
            raise BuildError("GOAL23 allowlisted raw SHA-256 variant is invalid")
        if canonical_sha not in raw_hashes:
            raise BuildError("GOAL23 LF raw SHA-256 must equal its canonical-LF SHA-256")
    version = str(config.get("version", ""))
    goal30 = config.get("schema") == GOAL30_SCHEMA
    if goal30:
        expected = {
            "version": "0.1.9-fan-03df597", "host_version": "0.1.9-goal30",
            "san_commit": "03df597c1b872c4875e684c9e4f8a1cc54e7e297",
            "main_commit": "8036a37ff6af5ae5c7924b5c26d3290e640bf607", "qa_port": 4209,
        }
        for key, pinned in expected.items():
            if config.get(key) != pinned:
                raise BuildError(f"GOAL30 fixed release identity mismatch: {key}")
        for key, paths in (("public_package_hashes", GOAL30_PUBLIC_PACKAGES),
                           ("source_schema_hashes", GOAL30_SCHEMAS),
                           ("main_schema_hashes", GOAL30_MAIN_SCHEMAS)):
            values = config.get(key)
            if not isinstance(values, dict) or set(values) != paths:
                raise BuildError(f"GOAL30 requires the complete reviewed file set: {key}")
            safe_file_map(values)
        versions = config.get("public_package_contract_versions")
        if (not isinstance(versions, dict) or set(versions) != GOAL30_PUBLIC_PACKAGES
                or any(not isinstance(v, str) or not v for v in versions.values())):
            raise BuildError("GOAL30 must record every public package contract version")
    elif not re.fullmatch(r"0\.1\.8-fan-[0-9a-f]{7}", version):
        raise BuildError("GOAL23 candidate version must be 0.1.8-fan-<7 hex commit prefix>")
    if not goal30 and config.get("host_version") != "0.1.8-goal23":
        raise BuildError("Unexpected GOAL23 Host version")
    port = config.get("qa_port")
    if not isinstance(port, int) or port < 1024 or port > 65535 or port in PROTECTED_PORTS:
        raise BuildError("QA port is invalid or protected")
    if config.get("minimum_available_gib") != 2.5:
        raise BuildError("The established 2.5 GiB resource gate cannot be changed")
    if config.get("native_bridge_status") != "DISABLED_NO_R4_BRIDGE":
        raise BuildError("GOAL23 QA candidate must keep the Native bridge disabled")
    if config.get("profile_mode") != "QA_ONLY_TEMP_VERSION_PORT_SCOPED":
        raise BuildError("GOAL23 must use its independent temporary WebView2 profile")


def exact_identity(config: dict[str, Any], *, san_commit: str, main_commit: str,
                   main_json_sha256: str, static_sha256: str) -> None:
    expected = {
        "San commit": (san_commit, config["san_commit"]),
        "Main commit": (main_commit, config["main_commit"]),
        "Main JSON SHA-256": (main_json_sha256.lower(), config["main_inspiration_json_sha256"].lower()),
        "Static artifact SHA-256": (static_sha256.lower(), config["static_artifact_sha256"].lower()),
    }
    for label, (actual, pinned) in expected.items():
        if actual != pinned:
            raise BuildError(f"{label} mismatch: expected {pinned}, found {actual}")


def git_head(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                            capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip().lower()


def require_clean_san(root: Path) -> None:
    result = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    if result.stdout.strip():
        raise BuildError("San worktree is not clean; refusing to package a moving source tree")


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def qa_profile_path(temp_root: Path, host_version: str, port: int) -> Path:
    if port in PROTECTED_PORTS or port < 1024 or port > 65535:
        raise BuildError("Refusing protected or invalid QA port")
    return temp_root / "PTTI-GOAL23-DesktopFan-QA" / host_version / f"Port-{port}" / "WebView2"


def safe_file_map(files: dict[str, str]) -> dict[str, str]:
    for relative, digest in files.items():
        part = PurePosixPath(relative)
        if part.is_absolute() or re.match(r"^[A-Za-z]:", relative) or ".." in part.parts or "\\" in relative:
            raise BuildError(f"Unsafe package path: {relative}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise BuildError(f"Invalid file digest: {relative}")
    return files


def verify_parent_release(parent: Path, expected_manifest_sha256: str) -> None:
    manifest_path = parent / "release.json"
    if sha256_file(manifest_path) != expected_manifest_sha256:
        raise BuildError("Rollback parent release manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = safe_file_map(manifest.get("files", {}))
    actual = {k: v for k, v in tree_manifest(parent).items() if k != "release.json"}
    if actual != expected:
        raise BuildError("Rollback parent payload differs from its complete file hash inventory")


def verify_raw_pins(root: Path, pins: dict[str, str]) -> None:
    root = root.resolve(strict=True)
    for relative, digest in safe_file_map(pins).items():
        cursor = root
        for part in PurePosixPath(relative).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise BuildError(f"Pinned file symlink is forbidden: {relative}")
        if not cursor.is_file() or sha256_file(cursor) != digest:
            raise BuildError(f"Pinned file missing or raw SHA-256 mismatch: {relative}")


def verify_goal30_inputs(config: dict[str, Any], web_root: Path, main_root: Path, static_root: Path) -> None:
    if config["schema"] != GOAL30_SCHEMA:
        return
    verify_raw_pins(web_root / "public", config["public_package_hashes"])
    verify_raw_pins(static_root, config["public_package_hashes"])
    verify_raw_pins(web_root, config["source_schema_hashes"])
    verify_raw_pins(main_root, config["main_schema_hashes"])
    for relative, version in config["public_package_contract_versions"].items():
        if json.loads((static_root / relative).read_text(encoding="utf-8")).get("contract_version") != version:
            raise BuildError(f"GOAL30 public contract version mismatch: {relative}")
    assets = static_root / "assets"
    scripts = [p.read_text(encoding="utf-8", errors="strict") for p in assets.glob("*.js")]
    if not any("collector-lounge" in s and "data-collector-source-id" in s for s in scripts):
        raise BuildError("GOAL30 static artifact lacks the Collector's Lounge implementation")
    if not any(".collector-card" in p.read_text(encoding="utf-8", errors="strict") for p in assets.glob("*.css")):
        raise BuildError("GOAL30 static artifact lacks Collector's Lounge styles")


def verify_inputs(config: dict[str, Any], san_root: Path, main_root: Path, static_root: Path,
                  main_json: Path, parent_release: Path, output_root: Path) -> dict[str, Any]:
    validate_config(config)
    san_root = san_root.resolve(strict=True)
    main_root = main_root.resolve(strict=True)
    static_root = static_root.resolve(strict=True)
    main_json = main_json.resolve(strict=True)
    if san_root not in static_root.parents:
        raise BuildError("Static artifact must come from the pinned San worktree")
    if main_root not in main_json.parents:
        raise BuildError("Main JSON must come from the pinned Main worktree")
    verify_goal30_inputs(config, san_root / "products" / "ptti-web", main_root, static_root)
    san_text_hashes = verify_allowlisted_text_inputs(san_root / "products" / "ptti-web", config)
    san_commit = git_head(san_root)
    main_commit = git_head(main_root)
    require_clean_san(san_root)
    main_sha = sha256_file(main_json)
    static_sha = canonical_tree_sha256(static_root)
    exact_identity(config, san_commit=san_commit, main_commit=main_commit,
                   main_json_sha256=main_sha, static_sha256=static_sha)
    bundled_main = static_root / "data" / "fan-inspiration-v0.1.json"
    if sha256_file(bundled_main) != config["main_inspiration_json_sha256"]:
        raise BuildError("Static package does not carry the pinned Main JSON")
    parent_release = parent_release.resolve(strict=True)
    verify_parent_release(parent_release, config["parent_release_manifest_sha256"])
    if not port_is_free(config["qa_port"]):
        raise BuildError(f"QA port {config['qa_port']} is already occupied; no process was contacted")
    output_root = output_root.resolve(strict=False)
    final = output_root / config["version"]
    receipt = output_root / f"{config['version']}.build-receipt.json"
    if final.exists() or receipt.exists():
        raise BuildError("GOAL23 output already exists; refusing to overwrite it")
    if final == parent_release or final.is_relative_to(parent_release) or parent_release.is_relative_to(final):
        raise BuildError("Candidate output must remain separate from its rollback parent")
    source_text = HOST_TEMPLATE.read_text(encoding="utf-8")
    for token in FORBIDDEN_HOST_TOKENS:
        if token.casefold() in source_text.casefold():
            raise BuildError(f"Host template references forbidden production data or selector token: {token}")
    return {"san_commit": san_commit, "main_commit": main_commit,
            "main_json_sha256": main_sha, "static_artifact_sha256": static_sha,
            "san_canonical_lf_text_inputs": san_text_hashes}


def available_gib() -> float:
    if os.name != "nt":
        raise BuildError("Windows memory status is unavailable; build stopped")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise BuildError("Windows memory status query failed; build stopped")
    return status.avail_phys / (1024 ** 3)


def require_ram_guard(available: float, required: float = 2.5) -> None:
    if available < required:
        raise BuildBlocked(f"BUILD BLOCKED: {available:.3f} GiB available < {required:.1f} GiB; Host compilation was not started")


def run_checked(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    if completed.returncode:
        raise BuildError(f"Command failed ({completed.returncode}): {command[0]}\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout + completed.stderr


def host_verification_command(python: str, host_script: Path, package: Path) -> list[str]:
    """Verify the staged package without creating bytecode inside its hashed tree."""
    return [python, "-B", str(host_script), "--verify-only", "--package-root", str(package)]


def run_static_checks(node: str, web_root: Path, config: dict[str, Any]) -> None:
    checks = (
        ("scripts/check-goal22.mjs",),
        ("scripts/check-goal22-integration.mjs", "--built"),
        ("scripts/check-goal17-additions.mjs", "--built"),
        ("scripts/check-goal19-watchability.mjs", "--built"),
    )
    if config["schema"] == GOAL30_SCHEMA:
        checks += (("scripts/check-collector-lounge.mjs",),
                   ("scripts/check-match-reports.mjs", "--built"),
                   ("scripts/check-evidence-projection.mjs",))
    with tempfile.TemporaryDirectory(prefix="ptti-goal23-canonical-check-") as temp:
        check_root = Path(temp) / "ptti-web"
        shutil.copytree(web_root, check_root, ignore=shutil.ignore_patterns("node_modules", ".venv"))
        for entry in config["canonical_lf_text_inputs"]:
            source = web_root.joinpath(*PurePosixPath(entry["path"]).parts)
            meta, canonical = normalize_allowlisted_utf8_text(source.read_bytes(), entry)
            target = check_root.joinpath(*PurePosixPath(entry["path"]).parts)
            target.write_bytes(canonical)
            if hashlib.sha256(target.read_bytes()).hexdigest() != meta["canonical_lf_sha256"]:
                raise BuildError("Canonical-LF static-check overlay failed its pinned hash")
        for args in checks:
            run_checked([node, *args], cwd=check_root)


def package_files(root: Path) -> dict[str, str]:
    return safe_file_map(tree_manifest(root))


def write_build_config(source_dir: Path, config: dict[str, Any]) -> None:
    # The selected config, not CONFIG_PATH's legacy default, belongs in the new package.
    (source_dir / "goal23-build.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def build_candidate(args: argparse.Namespace, config: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    available = available_gib()
    require_ram_guard(available, config["minimum_available_gib"])
    if not args.python or not Path(args.python).is_file():
        raise BuildError("A verified Python environment path is required")
    python = str(Path(args.python).resolve(strict=True))
    info = run_checked([python, "-c", "import sys,importlib.metadata as m;print(sys.version.split()[0]+'|'+m.version('pywebview')+'|'+m.version('pyinstaller'))"], cwd=HERE)
    expected = f"{config['python_version']}|{config['pywebview_version']}|{config['pyinstaller_version']}"
    if info.strip() != expected:
        raise BuildError(f"Build tool identity mismatch: expected {expected}, found {info.strip()}")
    node = shutil.which("node")
    if not node:
        raise BuildError("Node.js is required for pinned San built checks")
    web_root = args.san_root.resolve(strict=True) / "products" / "ptti-web"
    run_static_checks(node, web_root, config)
    compile_ram = available_gib()
    require_ram_guard(compile_ram, config["minimum_available_gib"])
    output_root = args.output_root.resolve(strict=False)
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / config["version"]
    if final.exists():
        raise BuildError("Final candidate appeared before staging; refusing to overwrite")
    stage = Path(tempfile.mkdtemp(prefix=f".{config['version']}.stage-", dir=output_root))
    try:
        package = stage / "package"
        package.mkdir()
        source_dir = stage / "source"
        source_dir.mkdir()
        shutil.copy2(HOST_TEMPLATE, source_dir / "desktop_host.py")
        shutil.copy2(PROCESS_IDENTITY, source_dir / "Goal23.ProcessIdentity.ps1")
        write_build_config(source_dir, config)
        pins = {
            "version": config["version"], "host_version": config["host_version"],
            "san_commit": config["san_commit"], "main_commit": config["main_commit"],
            "main_inspiration_json_sha256": config["main_inspiration_json_sha256"],
            "static_artifact_sha256": config["static_artifact_sha256"], "qa_port": config["qa_port"],
            "san_canonical_lf_text_inputs": identity["san_canonical_lf_text_inputs"],
        }
        if config["schema"] == GOAL30_SCHEMA:
            for key in ("public_package_hashes", "source_schema_hashes", "main_schema_hashes"):
                pins[key] = config[key]
        (source_dir / "goal23_identity.py").write_text("PINS = " + repr(pins) + "\n", encoding="utf-8")
        build_root = stage / "pyinstaller"
        dist_root = build_root / "dist"
        run_checked([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
                     "--name", "PTTI-Desktop-Fan", "--collect-all", "webview", "--paths", str(source_dir),
                     "--distpath", str(dist_root), "--workpath", str(build_root / "work"),
                     "--specpath", str(build_root / "spec"), str(source_dir / "desktop_host.py")], cwd=stage)
        shutil.copytree(web_root / "dist", package / "fan-universe")
        shutil.copytree(dist_root / "PTTI-Desktop-Fan", package / "host")
        shutil.copytree(source_dir, package / "source")
        manifest_files = package_files(package)
        release = {
            "schema": "ptti.desktop-fan.release.v1", **pins,
            "source_identity": "fixed-commit-and-byte-pinned-static-artifact",
            "main_json_sha256": config["main_inspiration_json_sha256"],
            "web_static_build_sha256": config["static_artifact_sha256"],
            "san_canonical_lf_text_inputs": identity["san_canonical_lf_text_inputs"],
            "default_port": config["qa_port"],
            "web_static_hash_algorithm": config["static_hash_algorithm"],
            "native_bridge_status": config["native_bridge_status"],
            "profile_mode": config["profile_mode"], "signature_status": "UNSIGNED_QA_CANDIDATE",
            "web_engine": f"WebView2 via pywebview {config['pywebview_version']}",
            "files": manifest_files,
        }
        (package / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        verify_command = host_verification_command(python, package / "source" / "desktop_host.py", package)
        run_checked(verify_command, cwd=package)
        after_identity = verify_inputs(config, args.san_root, args.main_root, args.static_root,
                                       args.main_json, args.parent_release, args.output_root)
        if after_identity != identity:
            raise BuildError("Pinned input identity changed during Host compilation")
        if final.exists():
            raise BuildError("Final candidate appeared during build; staged package retained")
        package.rename(final)
        exe = final / "host" / "PTTI-Desktop-Fan.exe"
        receipt = {
            "schema": "ptti.desktop-fan.goal23-build-receipt.v1", "status": "CANDIDATE_BUILT",
            "version": config["version"], "host_version": config["host_version"],
            "san_commit": identity["san_commit"], "main_commit": identity["main_commit"],
            "main_json_sha256": identity["main_json_sha256"], "static_artifact_sha256": identity["static_artifact_sha256"],
            "san_canonical_lf_text_inputs": identity["san_canonical_lf_text_inputs"],
            "release_manifest_sha256": sha256_file(final / "release.json"),
            "host_exe_sha256": sha256_file(exe), "package_file_count": len(manifest_files) + 1,
            "qa_port": config["qa_port"], "qa_profile_policy": config["profile_mode"],
            "native_bridge_status": config["native_bridge_status"], "live_database_access": "NONE",
            "formal_selector_modified": False, "gui_status": "NOT_TESTED",
            "available_ram_before_host_compile_gib": round(compile_ram, 3),
        }
        receipt_path = output_root / f"{config['version']}.build-receipt.json"
        temp_receipt = receipt_path.with_suffix(receipt_path.suffix + ".tmp")
        temp_receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_receipt, receipt_path)
        return receipt
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify the isolated GOAL23 Desktop Fan QA candidate")
    parser.add_argument("command", choices=("preflight", "build"))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--san-root", type=Path, required=True)
    parser.add_argument("--main-root", type=Path, required=True)
    parser.add_argument("--static-root", type=Path, required=True)
    parser.add_argument("--main-json", type=Path, required=True)
    parser.add_argument("--parent-release", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--python", default="")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    identity = verify_inputs(config, args.san_root, args.main_root, args.static_root,
                             args.main_json, args.parent_release, args.output_root)
    report = {"status": "PREFLIGHT_PASS", **identity, "version": config["version"],
              "host_version": config["host_version"], "qa_port": config["qa_port"],
              "qa_profile_mode": config["profile_mode"], "native_bridge": config["native_bridge_status"],
              "old_candidate_reused_as_host": False}
    if args.command == "preflight":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        result = build_candidate(args, config, identity)
    except BuildBlocked as exc:
        print(str(exc))
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"BUILD FAILED CLOSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
