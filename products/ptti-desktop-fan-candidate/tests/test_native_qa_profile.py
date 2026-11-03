from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desktop_host import (  # noqa: E402
    Bridge,
    CandidateError,
    native_preflight_block_reason,
    prepare_native_qa_context,
    qa_profile_paths,
    selector_command,
)


class NativeQaProfileTests(unittest.TestCase):
    def test_pending_native_approval_stops_before_selector_and_database(self) -> None:
        bridge = Bridge({"native_bridge_status": "BLOCKED_PENDING_SELECTOR_APPROVAL"}, qa_profile=True)
        with patch("desktop_host.subprocess.run", side_effect=AssertionError("selector must not run")), patch("desktop_host.prepare_native_qa_context", side_effect=AssertionError("database must not be read")):
            result = bridge.launch_native()
        self.assertFalse(result["ok"])
        self.assertIn("审批", result["message"])

    def test_native_preflight_requires_verified_process_identity(self) -> None:
        self.assertIn("could not verify", native_preflight_block_reason({"running": []}))
        self.assertIn(
            "could not be identified safely",
            native_preflight_block_reason(
                {"identityVerified": True, "running": [91], "runningUnverified": [91]}
            ),
        )
        self.assertIn(
            "already running",
            native_preflight_block_reason(
                {"identityVerified": True, "running": [92], "runningUnverified": []}
            ),
        )
        self.assertIsNone(
            native_preflight_block_reason(
                {"identityVerified": True, "running": [], "runningUnverified": []}
            )
        )

    def test_selector_invocation_inherits_power_shell_policy(self) -> None:
        command = selector_command(Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"), Path(r"<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1"))

        self.assertEqual(command[1:], ["-NoProfile", "-File", r"<LOCAL_USER_ROOT>\PTTI\Launcher\Start-PTTI.ps1", "-Choice", "Native"])
        self.assertNotIn("-ExecutionPolicy", command)
        self.assertNotIn("Bypass", command)

    def test_qa_webview_profiles_are_separate_from_each_other_and_production(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            production_profile = temp_root / "user-profile" / "PTTI" / "DesktopFan" / "WebView2"
            qa_root_a, qa_profile_a = qa_profile_paths(temp_root, 4200)
            qa_root_b, qa_profile_b = qa_profile_paths(temp_root, 4201)

            self.assertNotEqual(qa_root_a, qa_root_b)
            self.assertNotEqual(qa_profile_a, qa_profile_b)
            self.assertNotEqual(qa_profile_a, production_profile)
            self.assertEqual(qa_profile_a, qa_root_a / "WebView2")

    def test_qa_webview_cannot_use_production_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(CandidateError):
                qa_profile_paths(Path(temporary), 4199)

    def test_missing_preview_database_stops_native_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local_app_data = root / "user-profile"
            temp_root = root / "temp"
            local_app_data.mkdir()
            temp_root.mkdir()
            with self.assertRaises(CandidateError):
                prepare_native_qa_context(
                    {"LOCALAPPDATA": str(local_app_data)},
                    temp_root=temp_root,
                )

    def test_native_button_is_disabled_outside_qa_profile(self) -> None:
        result = Bridge({}, qa_profile=False).launch_native()
        self.assertFalse(result["ok"])
        self.assertIn("isolated QA profile", result["message"])

    def test_native_qa_database_is_an_independent_writable_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local_app_data = root / "user-profile"
            source = local_app_data / "PTTI-Dev" / "VideoFirst-R4-Preview" / "matches.db"
            source.parent.mkdir(parents=True)
            with closing(sqlite3.connect(source)) as database:
                database.execute("CREATE TABLE isolation_probe (value TEXT NOT NULL)")
                database.execute("INSERT INTO isolation_probe VALUES ('source')")
                database.commit()
            source_digest_before = hashlib.sha256(source.read_bytes()).hexdigest()
            temporary_root = root / "temp"
            temporary_root.mkdir()

            context = prepare_native_qa_context(
                {"LOCALAPPDATA": str(local_app_data)},
                temp_root=temporary_root,
            )

            self.assertTrue(context.database_path.is_file())
            self.assertNotEqual(context.database_path.resolve(), source.resolve())
            self.assertTrue(context.database_path.resolve().is_relative_to((root / "temp").resolve()))
            self.assertEqual(context.environment["PTTI_PREVIEW_QA_DB"], str(context.database_path))
            self.assertEqual(context.environment["PTTI_DB"], str(context.database_path))
            self.assertEqual(context.environment["LOCALAPPDATA"], str(context.profile_root))

            with closing(sqlite3.connect(context.database_path)) as database:
                self.assertEqual(database.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(database.execute("SELECT value FROM isolation_probe").fetchone()[0], "source")
                database.execute("UPDATE isolation_probe SET value='qa-only'")
                database.commit()

            with closing(sqlite3.connect(source)) as database:
                self.assertEqual(database.execute("SELECT value FROM isolation_probe").fetchone()[0], "source")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_digest_before)


if __name__ == "__main__":
    unittest.main()
