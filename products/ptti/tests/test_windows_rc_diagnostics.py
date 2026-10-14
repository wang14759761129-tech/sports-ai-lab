"""Diagnostic behavior tests: no real EXE, user database or system changes."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import windows_rc_diagnostics as diag


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ptti-diagnostic-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "build-info.json").write_text(json.dumps({
            "environment": "DEVELOPMENT", "source_tree_dirty": False, "official_release": False}))
        (self.root / "manifest.json").write_text(json.dumps({"files": {"build-info.json": "fixture"}}))
        self.base = Mock()
        self.base.validate_candidate.return_value = SimpleNamespace(directory=self.root)
        self.base._available_memory_bytes.return_value = 3 * 1024**3
        self.base._running_candidate_processes.return_value = []
        self.base.QALauncherError = diag.reviewed.load_base().QALauncherError

    def test_low_ram_does_not_stop_diagnostics_or_launch(self):
        self.base._available_memory_bytes.return_value = 2 * 1024**3
        report = diag.diagnose(self.base, self.root)
        self.assertEqual(report["integrity"], "PASS")
        self.assertEqual(report["missing_ram_bytes"], 512 * 1024**2)
        self.assertIn("QA_RESOURCE_GATE", report["codes"])
        self.base._launch.assert_not_called()

    def test_conflict_blocks(self):
        self.base._running_candidate_processes.return_value = [(123, diag.reviewed.EXE_NAME)]
        report = diag.diagnose(self.base, self.root)
        self.assertEqual(report["conflict_count"], 1)
        self.assertIn("QA_SESSION_IN_USE", report["codes"])

    def test_bad_package_still_reports_ram_and_safe_error(self):
        self.base.validate_candidate.side_effect = RuntimeError("private-video C:/Users/private token SECRET")
        report = diag.diagnose(self.base, self.root)
        self.assertEqual(report["available_ram_bytes"], 3 * 1024**3)
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertEqual(report["integrity"], "FAIL")

    def test_extra_files_refused(self):
        (self.root / "extra.txt").write_text("fixture")
        self.assertIn("RC_QA_UNEXPECTED_FILES", diag.diagnose(self.base, self.root)["codes"])

    def test_ram_query_failure_refused(self):
        self.base._available_memory_bytes.side_effect = self.base.QALauncherError("QA_RESOURCE_CHECK_UNAVAILABLE")
        self.assertIn("QA_RESOURCE_CHECK_UNAVAILABLE", diag.diagnose(self.base, self.root)["codes"])

    def test_default_never_creates_qa_or_launches(self):
        with patch.object(diag.reviewed, "load_base", return_value=self.base), patch.object(diag, "save_report", return_value="safe.json"), redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(["--candidate-dir", str(self.root)]), 0)
        self.base.prepare_new_plan.assert_not_called()
        self.base._launch.assert_not_called()

    def test_log_failure_blocks_launch(self):
        with patch.object(diag.reviewed, "load_base", return_value=self.base), patch.object(diag, "save_report", side_effect=PermissionError()), redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(["--candidate-dir", str(self.root), "--launch"]), 2)
        self.base._launch.assert_not_called()

    def test_start_time_ram_drop_blocks_and_reports_new_shortfall(self):
        self.base.prepare_new_plan.return_value = SimpleNamespace(candidate=Mock())
        self.base._available_memory_bytes.side_effect = [3 * 1024**3, 2 * 1024**3]
        self.base._require_resource_gate.side_effect = self.base.QALauncherError("QA_RESOURCE_GATE")
        output = io.StringIO()
        with patch.object(diag.reviewed, "load_base", return_value=self.base), patch.object(diag, "save_report", return_value="safe.json"), redirect_stdout(output):
            self.assertEqual(diag.main(["--candidate-dir", str(self.root), "--launch"]), 2)
        self.assertIn("还缺：0.500 GiB", output.getvalue())
        self.base._launch.assert_not_called()

    def test_unknown_spawn_outcome_warns_no_repeat(self):
        self.base.prepare_new_plan.return_value = SimpleNamespace(candidate=Mock())
        self.base._launch.side_effect = OSError("private path")
        writes = []
        with patch.object(diag.reviewed, "load_base", return_value=self.base), patch.object(diag, "save_report", side_effect=lambda r: writes.append(dict(r)) or "safe.json"), redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(["--candidate-dir", str(self.root), "--launch"]), 2)
        self.assertEqual(writes[-1]["codes"], ["START_OUTCOME_UNKNOWN"])
        self.assertIsNone(writes[-1]["exe_started"])
        self.base._launch.assert_called_once()

    def test_log_has_no_paths_or_media(self):
        report = diag.diagnose(self.base, self.root)
        name = diag.save_report(report, self.root)
        payload = (self.root / "PTTI-Launch-Diagnostics" / name).read_text(encoding="utf8")
        self.assertNotIn(str(self.root), payload)
        self.assertNotIn("candidate-dir", payload)
        self.assertEqual(json.loads(payload)["target_commit"], diag.COMMIT)

    def test_base_failure_is_logged_without_exception_text(self):
        writes = []
        with patch.object(diag.reviewed, "load_base", side_effect=RuntimeError("secret path")), patch.object(diag, "save_report", side_effect=lambda r: writes.append(dict(r)) or "safe.json"), redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main([]), 2)
        self.assertNotIn("secret", json.dumps(writes))
        self.assertEqual(writes[0]["codes"], ["DIAGNOSTIC_FAILED"])

    @unittest.skipUnless(os.name == "nt", "Windows batch entry")
    def test_real_windows_entry_reports_failure_and_keeps_result_prompt(self):
        entry = Path(diag.__file__).with_name("PTTI-RC-Diagnostics.cmd")
        env = dict(os.environ, PTTI_QA_DIAGNOSTIC_PYTHON=sys.executable)
        command = f'cmd.exe /d /c call "{entry}" --candidate-dir "{self.root / "missing-package"}"'
        result = subprocess.run(command, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        output = result.stdout.decode("utf8", errors="replace")
        errors = result.stderr.decode("utf8", errors="replace")
        self.assertEqual(result.returncode, 2, output + errors)
        self.assertIn("候选完整性：FAIL", output)
        self.assertIn("按任意键关闭", output)
        self.assertNotIn("Traceback", errors)


if __name__ == "__main__":
    unittest.main()
