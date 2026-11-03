"""Build an isolated, byte-pinned GOAL17.3 candidate without touching San dist."""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

SOURCE = Path(__file__).resolve().parent
SAN = Path(r"C:\PTTI-Worktrees\web-goal14-fan-mvp")
WEB = SAN / "products/ptti-web"
PYTHON = Path("<LOCAL_USER_ROOT>/OneDrive/文档/ChatGPT/table tennis intelligent/.venv/Scripts/python.exe")
ROOT = Path(r"<LOCAL_USER_ROOT>\PTTI\Candidates\GOAL17")
VERSION = "0.1.6-fan-bb0a0c2"
COMMIT = "bb0a0c2a5558ff9424e4d89f0eb0724cd77d5284"
PARENT = ROOT / "0.1.5-fan-bb0a0c2"
PARENT_SHA = "b2d38b1ebf1b7bf540f3e70832b2e5cb9581b3c425f17352003a95cb57d9d573"
PORT = 4202
BUILD = ROOT / "build" / VERSION
ARTIFACTS = SOURCE / "artifacts/GOAL17.3"
SELECTOR = Path(r"<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1")
SELECTOR_SHA = "277069c5bd9bc4d95780edc38bf1866978b48deca03b4e0adaa6a84e4c3bf2b1"
LAUNCHER = Path(r"<LOCAL_USER_ROOT>\PTTI\NativeRoot\PTTI-Cinema\launcher.ps1")
LAUNCHER_SHA = "fa426aa15acca4e4308475a437d8f20a5cfcfa55b473296a6f841ff75683b969"
R4 = LAUNCHER.parent / "versions/5cc753886b11-b2623e68/PTTI-Video-First-R4-Preview.exe"
R4_SHA = "fca3bdf09a96e3d95a1f676ea63793909057c6e8a1d95d0a9274d3c3fc6738ab"
PINS = {
    "catalog_sha256": ("public/data/match-library-strict-public.json", "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930"),
    "fan_media_index_sha256": ("src/approved-public-media.json", "998acd8bf033bd2c19dcc042ce8b8f682c493261de513c9c816b54dceb889a10"),
    "main_media_manifest_sha256": ("scripts/fixtures/goal16-media/main-public-media-v0.2.json", "c05491a64f59ac922d2d85d081eccf3b2853f717ece82c8bcfa3d05608f2c004"),
    "goal17_photo_delta_sha256": ("public/data/goal17-athlete-photo-additions.json", "6afb03bcc99cefaca7d8ca26005b728162fe878317e217bd705a9253fd067dc9"),
    "goal17_match_delta_sha256": ("public/data/goal17-official-match-video-additions.json", "6f05d1fc48fb74ffc305abe20fd9152973bd96bb009fe6a183d42c031a31198a"),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def tree(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): digest(p) for p in sorted(path.rglob("*")) if p.is_file()}


def run(args: list[str | Path], cwd: Path = SOURCE) -> str:
    result = subprocess.run([str(x) for x in args], cwd=cwd, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="", flush=True)
    with (ARTIFACTS / "build.log").open("a", encoding="utf-8") as log:
        log.write("\n$ " + " ".join(map(str, args)) + "\n" + result.stdout)
    if result.returncode:
        raise RuntimeError(f"Build step failed ({result.returncode}): {args[0]}")
    return result.stdout.strip()


def memory_guard() -> float:
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]
    status = Memory()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("RAM status unavailable; stopped.")
    available = status.available / 2**30
    if available < 2.5:
        raise RuntimeError(f"RAM_GUARD: {available:.3f} GiB < 2.5 GiB. This guarded step was not started.")
    print(f"RAM_GUARD PASS {available:.3f} GiB", flush=True)
    return available


def ports() -> str:
    code = "ConvertTo-Json -Compress -InputObject @(Get-NetTCPConnection -State Listen -LocalPort 4174,4183,4199,4200,4201,4202 -ErrorAction SilentlyContinue | Sort-Object LocalPort,LocalAddress | Select-Object LocalAddress,LocalPort,OwningProcess)"
    return run(["powershell.exe", "-NoProfile", "-Command", code])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    final = ROOT / VERSION
    if final.exists():
        raise RuntimeError("Candidate already exists; refusing to overwrite or start another instance.")
    require(run(["git", "-C", SAN, "rev-parse", "HEAD"]) == COMMIT, "San HEAD changed")
    require(not run(["git", "-C", SAN, "status", "--porcelain=v1", "--untracked-files=all"]), "San tree is not clean")
    require(digest(PARENT / "release.json") == PARENT_SHA, "Parent release identity changed")
    parent = json.loads((PARENT / "release.json").read_text(encoding="utf-8"))
    require({p: h for p, h in tree(PARENT).items() if p != "release.json"} == parent["files"], "Parent payload changed")
    for path, expected in ((SELECTOR, SELECTOR_SHA), (LAUNCHER, LAUNCHER_SHA), (R4, R4_SHA)):
        require(digest(path) == expected, f"Protected runtime identity changed: {path}")
    for relative, expected in PINS.values():
        require(digest(WEB / relative) == expected, f"Content pin changed: {relative}")
    validation_key = {"san_commit": COMMIT, "host_sha256": digest(SOURCE / "src/desktop_host.py"),
                      "test_sha256": digest(SOURCE / "tests/test_native_qa_profile.py"),
                      "san_dist_sha256": hashlib.sha256(json.dumps(tree(WEB / "dist"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    validation_path = ARTIFACTS / "validation-receipt.json"
    previous_validation = json.loads(validation_path.read_text(encoding="utf-8"))["inputs"] if validation_path.exists() else {}
    static_validated = all(previous_validation.get(k) == validation_key[k] for k in ("san_commit", "san_dist_sha256"))
    desktop_validated = all(previous_validation.get(k) == validation_key[k] for k in ("host_sha256", "test_sha256"))
    before = ports()
    if any(x["LocalPort"] == PORT for x in json.loads(before or "[]")):
        raise RuntimeError("QA port occupied; no process contacted.")
    initial_ram = memory_guard()
    if not static_validated:
        for script in ("check-goal15-public-projection.mjs", "check-goal14-public-isolation.mjs", "check-goal16-media-v02.mjs", "check-goal17-additions.mjs", "check-fan-navigation.mjs", "check-goal15.mjs"):
            run(["node", "scripts/" + script, "--built"], WEB)
    if not desktop_validated:
        run([PYTHON, "-m", "unittest", "discover", "-s", "tests", "-v"])
    validation_path.write_text(json.dumps({"inputs": validation_key, "static_checks": "PASS", "desktop_isolation": "8 PASS"}, indent=2) + "\n", encoding="utf-8")
    print(f"Reused unchanged checks: San static={static_validated}, desktop isolation={desktop_validated}", flush=True)
    # The content is unchanged by the export fix; reuse the verified 0.1.5 Web build.
    webdist = ROOT / "build/0.1.5-fan-bb0a0c2/webdist"
    if webdist.exists():
        require(tree(webdist) == tree(WEB / "dist"), "Existing isolated build differs; refusing to overwrite")
        print("Reusing the existing isolated Web build after exact San dist byte verification.", flush=True)
    else:
        memory_guard()
        run(["node", "node_modules/vite/bin/vite.js", "build", "--outDir", webdist, "--emptyOutDir"], WEB)
    require(tree(webdist) == tree(WEB / "dist"), "Isolated production build differs from San production dist")
    require(run(["git", "-C", SAN, "rev-parse", "HEAD"]) == COMMIT, "San HEAD changed during build")
    require(not run(["git", "-C", SAN, "status", "--porcelain=v1", "--untracked-files=all"]), "San tree changed during build")
    info = run([PYTHON, "-c", "import sys,importlib.metadata as m;print(sys.version.split()[0]+'|'+m.version('pywebview')+'|'+m.version('pyinstaller'))"])
    require(info == "3.12.14|6.2.1|6.22.3", "Build tool identity changed")
    memory_guard()
    run([PYTHON, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--name", "PTTI-Desktop-Fan", "--collect-all", "webview", "--hidden-import", "sqlite3", "--hidden-import", "_sqlite3", "--distpath", BUILD / "dist", "--workpath", BUILD / "pyinstaller", "--specpath", BUILD / "spec", SOURCE / "src/desktop_host.py"])
    package = BUILD / "staging" / uuid.uuid4().hex
    package.mkdir(parents=True)
    shutil.copytree(webdist, package / "fan-universe")
    shutil.copytree(BUILD / "dist/PTTI-Desktop-Fan", package / "host")
    shutil.copy2(SOURCE / "desktop-shell.html", package / "desktop-shell.html")
    (package / "source").mkdir()
    shutil.copy2(SOURCE / "src/desktop_host.py", package / "source/desktop_host.py")
    shutil.copy2(WEB / "src/approved-public-media.json", package / "source/approved-public-media.json")
    files = tree(package)
    web_hash = hashlib.sha256(json.dumps(tree(webdist), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"schema": "ptti.desktop-fan.release.v1", "version": VERSION, "fan_commit": COMMIT,
                **{key: value[1] for key, value in PINS.items()}, "parent_release_manifest_sha256": PARENT_SHA,
                "desktop_host_source_sha256": files["source/desktop_host.py"], "native_selector_sha256": SELECTOR_SHA.upper(),
                "native_launcher_sha256": LAUNCHER_SHA.upper(), "r4_exe_sha256": R4_SHA.upper(),
                "native_qa_database_mode": "sqlite-read-only-backup-v1", "native_bridge_status": "BLOCKED_PENDING_SELECTOR_APPROVAL",
                "profile_mode": "QA_ONLY", "default_port": PORT, "qa_port_profile_policy": "distinct-loopback-port-and-WebView2-profile-per-QA-port-v1",
                "json_download_policy": "webview-native-save-dialog-v1",
                "powershell_policy": "inherit-current-user-policy-v1", "web_engine": "WebView2 via pywebview 6.2.1",
                "signature_status": "UNSIGNED_CANDIDATE", "web_static_build_sha256": web_hash,
                "web_static_hash_algorithm": "sha256(canonical sorted relative-path-to-sha256 JSON)", "files": files}
    (package / "release.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("desktop_host", SOURCE / "src/desktop_host.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    require(module.verify_package(package)["version"] == VERSION, "Staged package verification failed")
    ROOT.mkdir(parents=True, exist_ok=True)
    if final.exists():
        raise RuntimeError("Final candidate appeared; staged output retained without replacement.")
    package.rename(final)
    require(module.verify_package(final)["version"] == VERSION, "Final package verification failed")
    require(digest(SELECTOR) == SELECTOR_SHA, "Formal selector changed during build")
    after = ports()
    receipt = {"version": VERSION, "fan_commit": COMMIT, "package": str(final), "exe": str(final / "host/PTTI-Desktop-Fan.exe"),
               "release_json_sha256": digest(final / "release.json"), "exe_sha256": digest(final / "host/PTTI-Desktop-Fan.exe"),
               "file_count": len(files), "file_hash_verification": "PASS", "web_static_build_sha256": web_hash,
               "san_dist_byte_equality": "PASS", "ports_before": json.loads(before or "[]"), "ports_after": json.loads(after or "[]"),
               "protected_ports_unchanged": before == after, "initial_free_gib": initial_ram, "gui": "NOT_TESTED",
               "native_bridge": "BLOCKED_PENDING_SELECTOR_APPROVAL", "live_database_access": "NONE"}
    record = SOURCE / "releases" / VERSION
    record.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final / "release.json", record / "release.json")
    (record / "build-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
