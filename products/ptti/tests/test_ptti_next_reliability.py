from pathlib import Path
from types import ModuleType
import sys

import pytest

from apps import ptti_next_desktop as desktop


def package(tmp_path):
    for name in ("frontend/dist/index.html", "data/professional/registry.json"):
        path = tmp_path / "bundle" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    local = tmp_path / "local"
    local.mkdir()
    return tmp_path / "bundle", local


def test_preflight_does_not_create_database(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop, "webview2_runtime_state", lambda: True)
    bundle, local = package(tmp_path)
    desktop.validate_startup_configuration(bundle, str(local))
    assert list(local.iterdir()) == []


def test_missing_files_and_invalid_local_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop, "webview2_runtime_state", lambda: True)
    bundle, local = package(tmp_path)
    (bundle / "frontend/dist/index.html").unlink()
    with pytest.raises(RuntimeError, match="必要文件"):
        desktop.validate_startup_configuration(bundle, str(local))
    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        desktop.validate_startup_configuration(bundle, "relative")
    assert list(local.iterdir()) == []


def test_database_path_directory_rejected_without_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop, "webview2_runtime_state", lambda: True)
    bundle, local = package(tmp_path)
    database = local / "PTTI-Dev/Next-D2-Preview/matches.db"
    database.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="数据库路径"):
        desktop.validate_startup_configuration(bundle, str(local))
    assert database.is_dir()


def test_missing_webview2_is_reported_before_database_access(tmp_path, monkeypatch):
    bundle, local = package(tmp_path)
    monkeypatch.setattr(desktop, "webview2_runtime_state", lambda: False)
    with pytest.raises(RuntimeError, match="WebView2"):
        desktop.validate_startup_configuration(bundle, str(local))
    assert list(local.iterdir()) == []


@pytest.mark.parametrize("error, text", [
    (PermissionError("denied"), "目录权限"),
    (RuntimeError("Local PTTI server did not start"), "本地 API"),
    (RuntimeError("WebView2 failed"), "WebView2"),
    (RuntimeError("sqlite database is locked"), "数据库"),
])
def test_actionable_error_messages(error, text):
    assert text in desktop.startup_error_message(error)


def test_single_instance_returns_without_launch(monkeypatch):
    monkeypatch.setattr(desktop, "validate_package_identity", lambda: None)
    monkeypatch.setattr(desktop, "require_start_resources", lambda: None)
    monkeypatch.setattr(desktop, "validate_startup_configuration", lambda *args: None)
    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: None)
    messages = []
    monkeypatch.setattr(desktop, "show_message", lambda message, **kwargs: messages.append(message))
    assert desktop.main() == 0
    assert "已在运行" in messages[0]


def test_failure_releases_owned_mutex(monkeypatch):
    monkeypatch.setattr(desktop, "validate_package_identity", lambda: None)
    monkeypatch.setattr(desktop, "require_start_resources", lambda: None)
    monkeypatch.setattr(desktop, "validate_startup_configuration", lambda *args: None)
    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: 123)
    released, messages = [], []
    monkeypatch.setattr(desktop, "release_single_instance", released.append)
    monkeypatch.setattr(desktop, "report_startup_failure", lambda error: None)
    monkeypatch.setattr(desktop, "show_message", lambda message, **kwargs: messages.append(message))
    fake = ModuleType("apps.desktop")
    def fail():
        raise RuntimeError("WebView2 failed")
    fake.main = fail
    monkeypatch.setitem(sys.modules, "apps.desktop", fake)
    assert desktop.main() == 1
    assert released == [123]
    assert "WebView2" in messages[0]
