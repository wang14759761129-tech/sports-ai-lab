from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
from contextlib import closing
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

PRODUCTION_PORT = 4199
DEFAULT_PORT = 4202
SELECTOR = Path(r"<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1")
NATIVE_LAUNCHER = Path(r"<LOCAL_USER_ROOT>\PTTI\NativeRoot\PTTI-Cinema\launcher.ps1")
NATIVE_LAUNCHER_SHA256 = "FA426AA15ACCA4E4308475A437D8F20A5CFCFA55B473296A6F841FF75683B969"
R4_EXE_SHA256 = "FCA3BDF09A96E3D95A1F676EA63793909057C6E8A1D95D0A9274D3C3FC6738AB"
MANIFEST = "release.json"
SHELL = "desktop-shell.html"
FAN = "fan-universe"
R4_DB_RELATIVE = Path("PTTI-Dev") / "VideoFirst-R4-Preview" / "matches.db"
EXPECTED_FAN_COMMIT = "bb0a0c2a5558ff9424e4d89f0eb0724cd77d5284"
EXPECTED_CATALOG_SHA256 = "1E038DCAB1A39C6C37D7687A066CD391328681A89950AE02E937AB1A0AC65930"
EXPECTED_MEDIA_INDEX_SHA256 = "998ACD8BF033BD2C19DCC042CE8B8F682C493261DE513C9C816B54DCEB889A10"
EXPECTED_MAIN_MEDIA_MANIFEST_SHA256 = "C05491A64F59AC922D2D85D081ECCF3B2853F717ECE82C8BCFA3D05608F2C004"
EXPECTED_PHOTO_DELTA_SHA256 = "6AFB03BCC99CEFACA7D8CA26005B728162FE878317E217BD705A9253FD067DC9"
EXPECTED_MATCH_DELTA_SHA256 = "6F05D1FC48FB74FFC305ABE20FD9152973BD96BB009FE6A183D42C031A31198A"


class CandidateError(RuntimeError):
    pass


def selector_command(powershell: Path, selector: Path) -> list[str]:
    """Build the selector invocation while preserving the user's PowerShell policy."""
    return [str(powershell), "-NoProfile", "-File", str(selector), "-Choice", "Native"]


@dataclass(frozen=True)
class NativeQaContext:
    session_root: Path
    profile_root: Path
    database_path: Path
    environment: dict[str, str]


def prepare_native_qa_context(
    base_environment: Mapping[str, str],
    temp_root: Path | None = None,
) -> NativeQaContext:
    """Make a read-only SQLite snapshot and route R4 to its isolated copy."""
    local_app_data = base_environment.get("LOCALAPPDATA")
    if not local_app_data:
        raise CandidateError("The Windows user data root is unavailable; Native QA was stopped.")

    source_db = Path(local_app_data) / R4_DB_RELATIVE
    if source_db.is_symlink() or not source_db.is_file():
        raise CandidateError("The current R4 preview database is unavailable; Native QA was stopped.")
    try:
        source_db = source_db.resolve(strict=True)
    except OSError as exc:
        raise CandidateError("The current R4 preview database could not be resolved; Native QA was stopped.") from exc

    try:
        system_temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
        if not system_temp.is_dir():
            raise CandidateError("The system temporary folder is unavailable; Native QA was stopped.")
        qa_parent = system_temp / "PTTI-GOAL16-R4-QA"
        qa_parent.mkdir(parents=True, exist_ok=True)
        qa_parent = qa_parent.resolve(strict=True)
        if qa_parent == system_temp or system_temp not in qa_parent.parents:
            raise CandidateError("The Native QA folder is outside the system temporary area.")
        session_root = qa_parent / uuid.uuid4().hex
        session_root.mkdir()
        session_root = session_root.resolve(strict=True)
        if qa_parent not in session_root.parents:
            raise CandidateError("The Native QA session folder is outside its temporary root.")
    except OSError as exc:
        raise CandidateError("A private temporary Native QA folder could not be created.") from exc

    profile_root = session_root / "Profile"
    database_path = profile_root / R4_DB_RELATIVE
    try:
        database_path.parent.mkdir(parents=True)
        resolved_database = database_path.resolve()
        if system_temp not in resolved_database.parents or resolved_database == source_db:
            raise CandidateError("The Native QA database target is not isolated from the current database.")

        source_uri = source_db.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=10)) as source:
            source.execute("PRAGMA query_only=ON")
            with closing(sqlite3.connect(database_path, timeout=10)) as clone:
                deadline = time.monotonic() + 30

                def check_deadline(status: int, remaining: int, total: int) -> None:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Native QA database snapshot exceeded its time limit.")

                source.backup(clone, pages=128, progress=check_deadline, sleep=0.05)
                integrity = clone.execute("PRAGMA quick_check").fetchall()
                if integrity != [("ok",)]:
                    raise CandidateError("The Native QA database copy failed its integrity check.")
                clone.commit()
    except CandidateError:
        raise
    except (OSError, sqlite3.Error, TimeoutError) as exc:
        raise CandidateError("The Native QA database copy could not be verified; Native was not started.") from exc

    if not database_path.is_file() or database_path.is_symlink():
        raise CandidateError("The verified Native QA database copy is missing or unsafe.")

    receipt = {
        "schema": "ptti.native-qa-db-receipt.v1",
        "status": "VERIFIED_ISOLATED_COPY",
        "source_mode": "sqlite-read-only-backup",
        "integrity": "PRAGMA quick_check = ok",
        "database_relative_path": R4_DB_RELATIVE.as_posix(),
        "snapshot_sha256": sha256(database_path),
    }
    try:
        receipt_path = session_root / "qa-db-receipt.json"
        temporary_receipt = session_root / "qa-db-receipt.tmp"
        temporary_receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        temporary_receipt.replace(receipt_path)
    except OSError as exc:
        raise CandidateError("The Native QA verification receipt could not be saved; Native was not started.") from exc

    child_environment = dict(base_environment)
    child_environment["LOCALAPPDATA"] = str(profile_root)
    child_environment["PTTI_PREVIEW_QA_DB"] = str(database_path)
    child_environment["PTTI_DB"] = str(database_path)
    child_environment["PTTI_ENV"] = "test"
    return NativeQaContext(session_root, profile_root, database_path, child_environment)


def package_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def checked_file(root: Path, relative: str) -> Path:
    part = PurePosixPath(relative.replace("\\", "/"))
    if part.is_absolute() or any(item in ("", ".", "..") for item in part.parts):
        raise CandidateError("Unsafe path in candidate manifest.")
    path = root.joinpath(*part.parts)
    resolved = path.resolve()
    if not path.is_file() or path.is_symlink() or root.resolve() not in resolved.parents:
        raise CandidateError("Missing or unsafe candidate file: " + relative)
    return path


def verify_package(root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateError("Candidate release manifest is missing or unreadable.") from exc
    if manifest.get("schema") != "ptti.desktop-fan.release.v1":
        raise CandidateError("Candidate manifest schema is unsupported.")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise CandidateError("Candidate manifest has no file hashes.")
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != root / MANIFEST
    }
    if actual != set(files):
        raise CandidateError("Candidate package contents do not match its manifest.")
    for relative, expected in files.items():
        if sha256(checked_file(root, relative)) != str(expected).upper():
            raise CandidateError("Candidate package hash mismatch: " + relative)
    if str(manifest.get("desktop_host_source_sha256", "")).upper() != str(files.get("source/desktop_host.py", "")).upper():
        raise CandidateError("Desktop host source identity is unexpected.")
    if not {SHELL, FAN + "/index.html"}.issubset(files):
        raise CandidateError("Candidate shell or Fan entry page is missing.")
    if manifest.get("fan_commit") != EXPECTED_FAN_COMMIT:
        raise CandidateError("Fan source commit identity is unexpected.")
    if str(manifest.get("catalog_sha256", "")).upper() != EXPECTED_CATALOG_SHA256:
        raise CandidateError("Public catalog identity is unexpected.")
    if str(manifest.get("fan_media_index_sha256", "")).upper() != EXPECTED_MEDIA_INDEX_SHA256:
        raise CandidateError("GOAL16 public media index identity is unexpected.")
    if str(files.get("source/approved-public-media.json", "")).upper() != EXPECTED_MEDIA_INDEX_SHA256:
        raise CandidateError("The bundled public media index is missing or unexpected.")
    if str(manifest.get("main_media_manifest_sha256", "")).upper() != EXPECTED_MAIN_MEDIA_MANIFEST_SHA256:
        raise CandidateError("Main public media manifest identity is unexpected.")
    if manifest.get("native_qa_database_mode") != "sqlite-read-only-backup-v1":
        raise CandidateError("Native QA database isolation is not enabled in this candidate.")
    for field, relative, expected in (
        ("goal17_photo_delta_sha256", FAN + "/data/goal17-athlete-photo-additions.json", EXPECTED_PHOTO_DELTA_SHA256),
        ("goal17_match_delta_sha256", FAN + "/data/goal17-official-match-video-additions.json", EXPECTED_MATCH_DELTA_SHA256),
    ):
        if str(manifest.get(field, "")).upper() != expected or str(files.get(relative, "")).upper() != expected:
            raise CandidateError("GOAL17 content identity is unexpected: " + field)
    if manifest.get("profile_mode") != "QA_ONLY" or manifest.get("native_bridge_status") != "BLOCKED_PENDING_SELECTOR_APPROVAL":
        raise CandidateError("This candidate requires isolated QA storage and the pending Native approval gate.")
    return manifest


def qa_profile_paths(temp_root: Path, port: int) -> tuple[Path, Path]:
    if port < 1024 or port > 65535 or port == PRODUCTION_PORT:
        raise CandidateError("QA mode requires a separate, valid local port.")
    qa_root = temp_root / "PTTI-GOAL16-DesktopFan-QA" / f"Port-{port}"
    return qa_root, qa_root / "WebView2"


def log_event(message: str) -> None:
    if os.environ.get("PTTI_GOAL16_QA_PROFILE") == "1":
        qa_root = os.environ.get("PTTI_GOAL16_QA_ROOT")
        if qa_root:
            base = Path(qa_root)
        else:
            base = Path(os.environ.get("TEMP", str(Path.home() / "AppData/Local/Temp"))) / "PTTI-GOAL16-DesktopFan-QA"
    else:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "PTTI" / "DesktopFan"
    try:
        logs = base / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "desktop-host.log").open("a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + message + "\n")
    except OSError:
        pass


def show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "PTTI Desktop Fan Candidate", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def native_preflight_block_reason(receipt: dict[str, Any]) -> str | None:
    if receipt.get("identityVerified") is not True:
        return "The selector could not verify the reviewed R4 executable identity. No app was started."
    if receipt.get("runningUnverified"):
        return "A possible R4 process could not be identified safely. No app was started."
    if receipt.get("running"):
        return "R4 is already running. The candidate did not open a second instance."
    return None


class Bridge:
    def __init__(self, manifest: dict[str, Any], qa_profile: bool = False) -> None:
        self.manifest = manifest
        self.qa_profile = qa_profile
        self.qa_context: NativeQaContext | None = None
        self.qa_context_lock = threading.Lock()

    def version_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "version": self.manifest["version"],
            "fanCommit": self.manifest["fan_commit"],
            "catalogSha256": self.manifest["catalog_sha256"],
            "integrityChecked": True,
            "update": "This candidate checks only its local package; it does not download or activate updates.",
        }

    def open_external(self, url: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {"ok": False, "message": "Only HTTP and HTTPS links can be opened externally."}
        try:
            webbrowser.open_new_tab(url)
            log_event("external_link_opened scheme=" + parsed.scheme)
            return {"ok": True, "message": "Opened in the system browser."}
        except Exception:
            return {"ok": False, "message": "The system browser could not open the link."}

    def launch_native(self) -> dict[str, Any]:
        if self.manifest.get("native_bridge_status") == "BLOCKED_PENDING_SELECTOR_APPROVAL":
            return {"ok": False, "message": "R4 联动等待正式选择器审批；当前未启动程序或访问数据库。"}
        if not self.qa_profile:
            return {"ok": False, "message": "Native QA launch is available only from the isolated QA profile."}
        if not SELECTOR.is_file() or not NATIVE_LAUNCHER.is_file():
            return {"ok": False, "message": "The current Native selector or verified R4 launcher is unavailable."}
        selector_sha256 = str(self.manifest.get("native_selector_sha256", "")).upper()
        if not selector_sha256 or sha256(SELECTOR) != selector_sha256:
            return {"ok": False, "message": "The Native selector changed after review. No app was started."}
        if sha256(NATIVE_LAUNCHER) != NATIVE_LAUNCHER_SHA256:
            return {"ok": False, "message": "The R4 launcher changed after review. No app was started."}
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        common = selector_command(powershell, SELECTOR)
        log_event("native_selector_preflight_requested")
        try:
            preflight = subprocess.run(
                common + ["-CheckOnly"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            log_event("native_selector_preflight_timeout")
            return {"ok": False, "message": "The guarded Native preflight timed out. It was not retried."}
        if preflight.returncode:
            detail = (preflight.stderr or preflight.stdout or "").strip()
            log_event("native_selector_preflight_failed")
            return {"ok": False, "message": detail[:1200] or "The Native selector refused its preflight."}
        try:
            receipt = json.loads(preflight.stdout.strip())
        except json.JSONDecodeError:
            log_event("native_selector_preflight_invalid")
            return {"ok": False, "message": "The Native selector returned an invalid verification receipt. No app was started."}
        process_block = native_preflight_block_reason(receipt)
        if process_block:
            return {"ok": False, "message": process_block}
        exe = Path(str(receipt.get("exe", "")))
        versions_root = Path(r"<LOCAL_USER_ROOT>\PTTI\NativeRoot\PTTI-Cinema\versions")
        if (
            receipt.get("choice") != "Native"
            or receipt.get("status") != "VERIFIED_ONLY"
            or not exe.is_file()
            or versions_root.resolve() not in exe.resolve().parents
            or "r4" not in exe.name.lower()
            or str(receipt.get("sha256", "")).upper() != R4_EXE_SHA256
            or sha256(exe) != R4_EXE_SHA256
        ):
            log_event("native_selector_preflight_identity_failed")
            return {"ok": False, "message": "The Native selector did not confirm the reviewed R4 package identity. No app was started."}
        if float(receipt.get("freeGiB", 0)) < 2.5:
            return {"ok": False, "message": "Available memory is below the existing 2.5 GiB guard. R4 was not started."}

        native_profile_db = Path(r"<LOCAL_USER_ROOT>\PTTI\NativeRoot") / R4_DB_RELATIVE
        if native_profile_db.exists():
            log_event("native_qa_fallback_profile_present")
            return {"ok": False, "message": "A second R4 profile was detected. Native QA stopped without launching."}
        with self.qa_context_lock:
            if self.qa_context is None:
                try:
                    self.qa_context = prepare_native_qa_context(os.environ)
                except CandidateError as exc:
                    log_event("native_qa_database_snapshot_failed")
                    return {"ok": False, "message": str(exc)}
                log_event("native_qa_database_snapshot_verified")
            elif not self.qa_context.database_path.is_file():
                self.qa_context = None
                log_event("native_qa_database_snapshot_missing")
                return {"ok": False, "message": "The isolated R4 QA database copy is missing. No app was started."}
            qa_context = self.qa_context

        log_event("native_selector_launch_requested")
        try:
            result = subprocess.run(
                common,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=qa_context.environment,
            )
        except subprocess.TimeoutExpired:
            log_event("native_selector_launch_timeout")
            return {"ok": False, "message": "The guarded Native launch timed out. It was not retried."}
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()
            log_event("native_selector_launch_failed")
            return {"ok": False, "message": detail[:1200] or "The Native selector refused to launch R4."}
        log_event("native_selector_launch_accepted")
        log_event("native_qa_profile_routed")
        return {"ok": True, "message": "R4 opened with an isolated QA database copy. Keep Fan Universe open and switch back to it to return."}

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def handler_for(root: Path, manifest: dict[str, Any]) -> type[SimpleHTTPRequestHandler]:
    fan_root = root / FAN
    shell_path = root / SHELL

    class Handler(SimpleHTTPRequestHandler):
        server_version = "PTTI-Desktop-Fan/0.1"
        sys_version = ""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(fan_root), **kwargs)

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            super().end_headers()

        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/__ptti/desktop":
                self.send_response(302)
                self.send_header("Location", "/__ptti/desktop/")
                self.end_headers()
                return
            if path == "/__ptti/desktop/":
                try:
                    page = shell_path.read_text(encoding="utf-8")
                except OSError:
                    self.send_error(500, "Desktop shell unavailable")
                    return
                page = page.replace("__VERSION__", str(manifest["version"]))
                page = page.replace("__COMMIT__", str(manifest["fan_commit"])[:12])
                payload = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if path.startswith("/__ptti/"):
                self.send_error(404)
                return
            super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:
            log_event("http_request")

    return Handler


def acquire_mutex(port: int) -> Any:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, False, rf"Local\PTTI-GOAL16-Desktop-Fan-Candidate-{port}")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create single-instance mutex")
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(handle)
        raise CandidateError("PTTI Desktop Fan Candidate is already running.")
    return handle


def main() -> int:
    parser = argparse.ArgumentParser(description="PTTI GOAL16 isolated Desktop Fan candidate")
    parser.add_argument("--qa-profile", action="store_true", default=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    root = package_root()
    mutex = None
    server = None
    try:
        if args.port < 1024 or args.port > 65535:
            raise CandidateError("The local candidate port must be between 1024 and 65535.")
        if args.qa_profile and args.port == PRODUCTION_PORT:
            raise CandidateError("QA mode must use a separate port; the production port is protected.")
        manifest = verify_package(root)
        if args.qa_profile:
            os.environ["PTTI_GOAL16_QA_PROFILE"] = "1"
            qa_root, profile = qa_profile_paths(
                Path(os.environ.get("TEMP", str(Path.home() / "AppData/Local/Temp"))),
                args.port,
            )
            os.environ["PTTI_GOAL16_QA_ROOT"] = str(qa_root)
        else:
            profile = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "PTTI/DesktopFan/WebView2"
        profile.mkdir(parents=True, exist_ok=True)
        mutex = acquire_mutex(args.port)
        server = LocalServer(("127.0.0.1", args.port), handler_for(root, manifest))
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        import webview
        # Fan's JSON backup uses a Blob download; let WebView2 show its native save dialog.
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            "PTTI · Fan Universe · " + str(manifest["version"]),
            url=f"http://127.0.0.1:{args.port}/__ptti/desktop/",
            js_api=Bridge(manifest, qa_profile=args.qa_profile),
            width=1440,
            height=920,
            min_size=(1040, 680),
            background_color="#f4f7fb",
        )
        log_event("desktop_window_opened version=" + str(manifest["version"]))
        webview.start(debug=False, gui="edgechromium", http_server=False, private_mode=False, storage_path=str(profile))
        log_event("desktop_window_closed")
        return 0
    except OSError as exc:
        show_error(f"PTTI Desktop Fan could not start its local-only window. It will not change a process that owns port {args.port}.\n\n" + str(exc))
        log_event("startup_failed kind=bind_or_storage")
        return 2
    except Exception as exc:
        show_error("PTTI Desktop Fan candidate failed its startup check.\n\n" + str(exc))
        log_event("startup_failed kind=package_or_webview")
        return 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    raise SystemExit(main())
