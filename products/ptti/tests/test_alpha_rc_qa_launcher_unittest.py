"""Lightweight RC launcher regressions. No EXE is ever executed."""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import alpha_rc_qa_launcher as rc


class RCLauncherTests(unittest.TestCase):
    def setUp(self):
        self.base = rc.load_base()

    def test_default_preflight_never_launches(self):
        with patch.object(rc, "load_base", return_value=self.base), patch.object(rc, "prepare"), \
                patch.object(self.base, "_launch") as launch, redirect_stdout(io.StringIO()):
            self.assertEqual(rc.main(["--candidate-dir", "unused"]), 0)
            launch.assert_not_called()

    def test_old_resume_argument_rejected(self):
        with patch.object(rc, "load_base") as load, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                rc.main(["--candidate-dir", "unused", "--resume-session", "old"])
            self.assertEqual(error.exception.code, 2)
            load.assert_not_called()

    def test_preflight_failure_cannot_launch(self):
        with patch.object(rc, "load_base", return_value=self.base), \
                patch.object(rc, "prepare", side_effect=self.base.QALauncherError("QA_RESOURCE_GATE")), \
                patch.object(self.base, "_launch") as launch, redirect_stderr(io.StringIO()):
            self.assertEqual(rc.main(["--candidate-dir", "unused", "--launch"]), 2)
            launch.assert_not_called()

    def test_launch_rechecks_resource_gate_before_spawn(self):
        plan = SimpleNamespace(candidate=Mock())
        with patch.object(rc, "load_base", return_value=self.base), patch.object(rc, "prepare", return_value=plan), \
                patch.object(self.base, "_require_no_running_candidate"), \
                patch.object(self.base, "_require_resource_gate", side_effect=self.base.QALauncherError("QA_RESOURCE_GATE")), \
                patch.object(self.base, "_launch") as launch, redirect_stderr(io.StringIO()):
            self.assertEqual(rc.main(["--candidate-dir", "unused", "--launch"]), 2)
            launch.assert_not_called()

    def test_low_memory_refused(self):
        with self.assertRaises(self.base.QALauncherError):
            self.base._require_resource_gate(2 * 1024**3)

    def test_environment_uses_only_new_database(self):
        database = Path("fresh-session") / "matches.db"
        result = self.base.build_qa_environment(database, {
            "PTTI_DB": "production", "PTTI_ENV": "PRODUCTION",
            "PTTI_PREVIEW_QA_DB": "old-session", "PTTI_VISION_HOME": "private",
            "PTTI_DESKTOP_DEPLOY_ROOT": "old-desktop"})
        self.assertEqual(result["PTTI_PREVIEW_QA_DB"], str(database))
        self.assertEqual(result["PTTI_PLAYBACK_DIAGNOSTICS"], "1")
        for key in ("PTTI_DB", "PTTI_ENV", "PTTI_VISION_HOME", "PTTI_DESKTOP_DEPLOY_ROOT"):
            self.assertNotIn(key, result)

    def test_modified_base_refused(self):
        with patch.object(Path, "read_bytes", return_value=b"unexpected"):
            with self.assertRaisesRegex(RuntimeError, "BASE_LAUNCHER_CHANGED"):
                rc.load_base()

    def test_checkout_line_endings_do_not_change_base_identity(self):
        source = Path(rc.__file__).with_name("candidate_qa_launcher.py").read_bytes()
        with patch.object(Path, "read_bytes", return_value=source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")):
            self.assertEqual(rc.load_base().PINNED_CANDIDATE.exe_name, rc.EXE_NAME)


if __name__ == "__main__":
    unittest.main()
