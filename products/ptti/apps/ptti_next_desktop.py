"""Guarded Windows entry point for the isolated PTTI Next M1A desktop preview."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import traceback

import psutil


MIN_START_RAM_BYTES = int(2.5 * 1024**3)
MUTEX_NAME = r"Local\PTTI.Next.M1A.Desktop"
ERROR_ALREADY_EXISTS = 183
EXECUTABLE_NAME = "ptti-next-preview"
VERSION = "1.0.0-D2"


class ResourceGateError(RuntimeError):
    pass


def webview2_runtime_state() -> bool | None:
    """Check the Evergreen registration; unknown registry access is not treated as absence."""
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        unknown = False
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key:
                        value, _ = winreg.QueryValueEx(key, "pv")
                        if value and value != "0.0.0.0":
                            return True
                except FileNotFoundError:
                    continue
                except OSError:
                    unknown = True
        return None if unknown else False
    except (ImportError, AttributeError):
        return None


def validate_startup_configuration(bundle: Path, local_app_data: str | None) -> None:
    """Check prerequisites without creating, opening, or modifying a database."""
    if not local_app_data or not Path(local_app_data).is_absolute():
        raise RuntimeError("无法确定 Windows 本地数据目录（LOCALAPPDATA）。请检查当前 Windows 账户配置。")
    local = Path(local_app_data)
    if not local.is_dir():
        raise RuntimeError("Windows 本地数据目录不存在或无法访问。请检查账户和目录权限。")
    required = (bundle / "frontend" / "dist" / "index.html",
                bundle / "data" / "professional" / "registry.json")
    missing = [str(path.relative_to(bundle)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("桌面包缺少必要文件：" + "、".join(missing) + "。请重新完整解压独立预览包。")
    if webview2_runtime_state() is False:
        raise RuntimeError("未检测到 Microsoft Edge WebView2 Runtime。请先安装或修复该组件，再打开预览。")
    database = local / "PTTI-Dev" / "Next-D2-Preview" / "matches.db"
    if database.exists() and not database.is_file():
        raise RuntimeError("预览数据库路径不是文件。请检查预览目录，原有数据未被删除。")


def startup_error_message(error: Exception) -> str:
    """Give actionable guidance while keeping the original exception in the log."""
    message = str(error)
    lowered = message.casefold()
    if isinstance(error, PermissionError):
        return "无法访问预览数据或软件包文件，请检查当前账户的目录权限。"
    if isinstance(error, OSError) and getattr(error, "winerror", None) in (10013, 10048, 10055):
        return "无法预留本机回环端口，请检查系统网络限制或端口占用后重试。"
    if "database" in lowered or "sqlite" in lowered:
        return "预览数据库无法打开或路径不正确。请检查预览目录权限，不要删除或替换已有数据库。"
    if "local ptti server did not start" in lowered or "embedded service identity" in lowered:
        return "本地 API 未能启动或身份不匹配，请查看诊断日志；未连接其他已有服务。"
    if "webview" in lowered or "edgechromium" in lowered:
        return "窗口组件启动失败，请检查 Microsoft Edge WebView2 Runtime 是否已安装且可用。"
    return "启动过程中发生错误，请查看诊断日志。"


def require_start_resources() -> None:
    available = psutil.virtual_memory().available
    if available < MIN_START_RAM_BYTES:
        raise ResourceGateError(
            f"当前可用内存为 {available / 1024**3:.2f} GiB，PTTI Next 至少需要 2.50 GiB。\n"
            "请稍后再打开；本次启动尚未打开数据库或媒体。"
        )


def validate_package_identity() -> None:
    if Path(sys.executable).stem.casefold() != EXECUTABLE_NAME:
        raise RuntimeError("PTTI Next 只能从独立桌面预览包启动。")
    bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    info_path = bundle / "build-info.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("桌面软件包缺少有效的构建身份文件。") from error
    commit = info.get("commit") if isinstance(info, dict) else None
    if (
        not isinstance(commit, str)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or info.get("product_name") != "PTTI Next"
        or info.get("version") != VERSION
        or info.get("channel") != "preview"
        or info.get("environment") != "DEVELOPMENT"
        or info.get("source_tree_dirty") is not False
        or info.get("official_release") is not False
        or info.get("production_database") != "NOT_ACCESSED"
        or info.get("media_included") is not False
    ):
        raise RuntimeError("桌面软件包身份不符合 PTTI Next 隔离预览要求。")


def acquire_single_instance():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE

    ctypes.set_last_error(0)
    handle = create_mutex(None, False, MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        release_single_instance(handle)
        return None
    return handle


def release_single_instance(handle) -> None:
    if not handle:
        return
    close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    close_handle(handle)


def show_message(message: str, *, warning: bool = False) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    message_box = user32.MessageBoxW
    message_box.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    message_box.restype = ctypes.c_int
    message_box(None, message, "PTTI Next · 桌面预览", 0x30 if warning else 0x10)


def report_startup_failure(error: Exception) -> Path | None:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    log_root = local / "PTTI-Dev" / "Next-D2-Preview" / "logs"
    try:
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / "startup-error.log"
        log_path.write_text(
            f"{datetime.now().astimezone().isoformat()}\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    except OSError:
        return None
    return log_path


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("PTTI Next 桌面预览仅支持 Windows。")

    try:
        validate_package_identity()
        require_start_resources()
        bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        validate_startup_configuration(bundle, os.environ.get("LOCALAPPDATA"))
    except ResourceGateError as error:
        show_message(str(error), warning=True)
        return 2
    except Exception as error:
        show_message(f"PTTI Next 启动前检查未通过：{error}")
        return 1

    mutex = None
    try:
        mutex = acquire_single_instance()
        if mutex is None:
            show_message("PTTI Next 已在运行，请返回已打开的窗口继续使用。", warning=True)
            return 0

        for name in tuple(os.environ):
            if name == "PTTI_NATIVE_QA" or name.startswith("PTTI_NATIVE_QA_"):
                os.environ.pop(name, None)
        for name in (
            "PTTI_PREVIEW_QA_DB",
            "PTTI_FOUNDER_QA_API",
            "PTTI_DESKTOP_DEPLOY_ROOT",
            "PTTI_PREVIEW_COMMIT",
            "PTTI_PREVIEW_VERSION",
            "PTTI_PREVIEW_BUILD_ID",
            "PTTI_PREVIEW_BUILT_AT",
            "PTTI_PREVIEW_PRODUCT_NAME",
        ):
            os.environ.pop(name, None)

        from apps.desktop import main as run_desktop

        run_desktop()
        return 0
    except Exception as error:
        log_path = report_startup_failure(error)
        detail = f"PTTI Next 未能启动：{startup_error_message(error)}"
        if log_path:
            detail += f"\n\n诊断日志：{log_path}"
        show_message(detail)
        return 1
    finally:
        release_single_instance(mutex)


if __name__ == "__main__":
    raise SystemExit(main())
