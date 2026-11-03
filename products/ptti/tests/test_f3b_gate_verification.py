"""Bounded verification-tool tests; all process calls and memory are mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/verify_f3b_gate.py"
SPEC = importlib.util.spec_from_file_location("f3b_gate_verification", MODULE_PATH)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class VerificationGateTests(unittest.TestCase):
    def invoke(self, phase, available_bytes, result):
        with tempfile.TemporaryDirectory(prefix="ptti-f3b-gate-test-") as temporary:
            output = Path(temporary) / "evidence"
            with patch.object(gate.sys, "argv", ["verify", phase, "--output", str(output)]), \
                 patch.object(gate.shutil, "which", side_effect=lambda executable: executable), \
                 patch.object(gate, "memory", return_value={"available_bytes": available_bytes}), \
                 patch.object(gate.subprocess, "check_output", return_value="SIMULATED_TEST_HEAD\n"), \
                 patch.object(gate.subprocess, "run", return_value=result) as process, \
                 contextlib.redirect_stdout(io.StringIO()):
                code = gate.main()
            report = json.loads((output / f"{phase}.json").read_text())
            return code, report, process.call_count

    def test_below_resource_gate_never_starts_install(self):
        code, report, calls = self.invoke("upgrade", gate.GATE_BYTES - 1, None)
        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(report["commands"][0]["status"], "RESOURCE_BLOCKED")

    def test_unknown_memory_fails_closed(self):
        code, report, calls = self.invoke("upgrade", None, None)
        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(report["commands"][0]["exit_code"], None)

    def test_exact_original_gate_allows_controlled_command(self):
        result = subprocess.CompletedProcess([], 0, "synthetic install output", "")
        code, report, calls = self.invoke("upgrade", gate.GATE_BYTES, result)
        self.assertEqual((code, calls), (0, 1))
        self.assertEqual(report["commands"][0]["argv"][2:4], ["--save-dev", "--save-exact"])

    def test_audit_network_failure_is_not_a_vulnerability_report(self):
        result = subprocess.CompletedProcess([], 1, json.dumps({"error": {"code": "ETIMEDOUT"}}), "")
        code, report, _ = self.invoke("baseline", gate.GATE_BYTES, result)
        self.assertEqual(code, 1)
        self.assertEqual(report["commands"][0]["reason"], "AUDIT_ENDPOINT_NOT_VERIFIED")

    def test_audit_vulnerabilities_are_retained_even_when_baseline_command_completes(self):
        result = subprocess.CompletedProcess([], 1, json.dumps({"auditReportVersion": 2, "metadata": {"vulnerabilities": {"high": 1, "total": 1}}}), "")
        code, report, _ = self.invoke("baseline", gate.GATE_BYTES, result)
        self.assertEqual(code, 0)
        self.assertEqual(report["commands"][0]["audit_vulnerabilities"]["high"], 1)


if __name__ == "__main__":
    unittest.main()
