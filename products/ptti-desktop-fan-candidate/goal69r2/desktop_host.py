"""Small GOAL23 WebView2 host. It has no Native, database, or production-profile bridge."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import socket
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from goal23_identity import PINS


PROTECTED_PORTS = {4174, 4183, 4199, 4200, 4201, 4202, 4203, 4204, 4205, 4206, 4207}


class CandidateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_manifest(root: Path) -> dict[str, str]:
    root = root.resolve(strict=True)
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CandidateError("Package symlinks are not allowed")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def tree_sha256(root: Path) -> str:
    payload = json.dumps(tree_manifest(root), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def package_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[1]


def verify_package(root: Path) -> dict:
    root = root.resolve(strict=True)
    release_path = root / "release.json"
    manifest = json.loads(release_path.read_text(encoding="utf-8"))
    expected_fields = {
        "schema": "ptti.desktop-fan.release.v1",
        "version": PINS["version"],
        "host_version": PINS["host_version"],
        "san_commit": PINS["san_commit"],
        "main_commit": PINS["main_commit"],
        "main_json_sha256": PINS["main_inspiration_json_sha256"],
        "web_static_build_sha256": PINS["static_artifact_sha256"],
        "default_port": PINS["qa_port"],
        "native_bridge_status": "DISABLED_NO_R4_BRIDGE",
        "profile_mode": "QA_ONLY_TEMP_VERSION_PORT_SCOPED",
    }
    for key in ("public_package_hashes", "source_schema_hashes", "main_schema_hashes"):
        if key in PINS:
            expected_fields[key] = PINS[key]
    for key in ("host_commit", "playback_commit", "playback_source_hashes", "main_content_manifest_sha256",
                "san_candidate_manifest_sha256", "candidate_title", "minimum_idle_seconds", "main_content_reference_commit", "manual_start_policy"):
        if key in PINS:
            expected_fields[key] = PINS[key]
    for key, expected in expected_fields.items():
        if manifest.get(key) != expected:
            raise CandidateError(f"Candidate release identity mismatch: {key}")
    file_map = manifest.get("files")
    if not isinstance(file_map, dict) or "release.json" in file_map:
        raise CandidateError("Candidate release file map is missing or recursive")
    for relative, digest in file_map.items():
        rel = PurePosixPath(relative)
        if rel.is_absolute() or re.match(r"^[A-Za-z]:", relative) or ".." in rel.parts or "\\" in relative or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise CandidateError("Candidate release file map contains an unsafe entry")
    actual = tree_manifest(root)
    actual.pop("release.json", None)
    if actual != file_map:
        raise CandidateError("Candidate package file hash verification failed")
    fan_root = root / "fan-universe"
    if tree_sha256(fan_root) != PINS["static_artifact_sha256"]:
        raise CandidateError("Static Fan artifact identity mismatch")
    main_json = fan_root / "data" / "fan-inspiration-v0.1.json"
    if sha256_file(main_json) != PINS["main_inspiration_json_sha256"]:
        raise CandidateError("Pinned Main inspiration JSON mismatch")
    if sha256_file(root / "host" / "PTTI-Desktop-Fan.exe") != file_map.get("host/PTTI-Desktop-Fan.exe"):
        raise CandidateError("New Host EXE does not match the release manifest")
    return manifest


def qa_profile_path(temp_root: Path, host_version: str, port: int) -> Path:
    if port in PROTECTED_PORTS or port != PINS["qa_port"]:
        raise CandidateError("Only the pinned, isolated GOAL23 QA port is allowed")
    return temp_root.resolve(strict=True) / "PTTI-GOAL23-DesktopFan-QA" / host_version / f"Port-{port}" / "WebView2"


def ensure_port_free(port: int) -> None:
    if port in PROTECTED_PORTS or port != PINS["qa_port"]:
        raise CandidateError("The configured QA port is invalid or protected")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise CandidateError(f"QA port {port} is occupied; no process was stopped or retried") from exc


def available_gib() -> float:
    if os.name != "nt":
        raise CandidateError("Windows RAM status unavailable; WebView2 startup stopped")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise CandidateError("Windows RAM status query failed; WebView2 startup stopped")
    return status.avail_phys / (1024 ** 3)


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        translated = Path(super().translate_path(path))
        if translated.is_file():
            return str(translated)
        if translated.is_dir() and (translated / "index.html").is_file():
            return str(translated / "index.html")
        requested_path = path.split("?", 1)[0].split("#", 1)[0]
        if not Path(requested_path).suffix:
            return str(Path(self.directory) / "index.html")
        return str(translated)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def natural_idle_seconds() -> float:
    class LastInput(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint), ("tick", ctypes.c_uint)]
    status = LastInput(ctypes.sizeof(LastInput), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(status)):
        raise CandidateError("Natural input idle unavailable")
    return ((ctypes.windll.kernel32.GetTickCount() - status.tick) & 0xffffffff) / 1000


def confirm_memory_warning(available: float | None) -> bool:
    detail = "无法读取当前可用内存。" if available is None else f"当前可用内存约 {available:.2f} GiB。"
    message = detail + "\n打开桌面可能增加内存压力，响应可能变慢。是否继续？\n选择否会取消本次启动，不会关闭其他应用。"
    return ctypes.windll.user32.MessageBoxW(None, message, "PTTI · 内存提示", 0x4 | 0x30 | 0x100) == 6


def check_start_policy(automated: bool, memory_reader=available_gib,
                       idle_reader=natural_idle_seconds, confirm=confirm_memory_warning) -> None:
    # This is application policy, not a substitute for computer-control platform rules.
    try:
        available = memory_reader()
    except CandidateError:
        if automated:
            raise
        available = None
    if automated:
        if available < 2.5:
            raise CandidateError("RAM_GUARD: less than 2.5 GiB free; automation stopped")
        if idle_reader() < 60:
            raise CandidateError("Natural input idle below 60 seconds; automation stopped")
    elif available is None or available < 2.5:
        # 2.5 GiB is a conservative advisory level, not a measured minimum footprint.
        if not confirm(available):
            raise CandidateError("User cancelled after memory advisory")


def run_gui(port: int, automated: bool = False) -> int:
    if port != PINS["qa_port"]:
        raise CandidateError("Requested port does not match this release identity")
    check_start_policy(automated)
    ensure_port_free(port)
    root = package_root()
    verify_package(root)
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    profile = qa_profile_path(temp_root, PINS["host_version"], port)
    profile.mkdir(parents=True, exist_ok=True)
    resolved_profile = profile.resolve(strict=True)
    if temp_root not in resolved_profile.parents:
        raise CandidateError("QA WebView2 profile escaped the user temporary root")
    fan_root = root / "fan-universe"
    handler = partial(QuietStaticHandler, directory=str(fan_root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    try:
        import webview
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            PINS.get("candidate_title", "PTTI · Fan Universe") + " · " + PINS["version"],
            url=f"http://127.0.0.1:{port}/",
            width=1440,
            height=920,
            min_size=(390, 620) if "candidate_title" in PINS else (840, 620),
            background_color="#080d18" if "candidate_title" in PINS else "#f4f7fb",
        )
        webview.start(debug=False, gui="edgechromium", http_server=False,
                      private_mode=False, storage_path=str(resolved_profile))
        return 0
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="GOAL23 Desktop Fan QA host; Native and production data bridges are absent")
    parser.add_argument("--port", type=int, default=PINS["qa_port"])
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--package-root", type=Path, default=None)
    parser.add_argument("--automation", action="store_true", help="Retain RAM and natural-idle automation gates")
    args = parser.parse_args()
    if args.verify_only:
        manifest = verify_package(args.package_root or package_root())
        print(json.dumps({"status": "PASS", "version": manifest["version"],
                          "san_commit": manifest["san_commit"], "qa_port": manifest["default_port"],
                          "native_bridge": manifest["native_bridge_status"]}, indent=2))
        return 0
    return run_gui(args.port, automated=args.automation)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CandidateError, OSError, MemoryError, RuntimeError) as exc:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, str(exc), "PTTI · 启动未完成", 0x10)
        print(f"GOAL23 QA host stopped safely: {exc}", file=sys.stderr)
        raise SystemExit(2)
