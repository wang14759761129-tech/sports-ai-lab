import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('safe_start',Path(__file__).parents[1]/'safe_start.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class SafeStartTests(unittest.TestCase):
    def test_click_resets_idle_and_waits_instead_of_starting(self):
        self.assertEqual(mod.decision(0,0),'WAIT')
    def test_input_resets_wait_even_after_59_seconds(self):
        self.assertEqual(mod.decision(59,59),'WAIT')
        self.assertEqual(mod.decision(0,60),'WAIT')
    def test_exact_60_seconds_is_ready(self):
        self.assertEqual(mod.decision(60,61),'READY')
    def test_cancel_has_priority_over_ready(self):
        self.assertEqual(mod.decision(80,90,True),'CANCELLED')
    def test_timeout_is_bounded_even_when_nearly_idle(self):
        self.assertEqual(mod.decision(59,600),'TIMED_OUT')
    def test_timeout_has_priority_over_ready(self):
        self.assertEqual(mod.decision(70,601),'TIMED_OUT')
    def test_low_ram_fails_closed(self):
        with self.assertRaises(mod.Refused):mod.check_final_gates(2.499,90,True,True)
    def test_unreadable_or_busy_session_fails_closed(self):
        for args in [(3,60,False,True),(3,60,True,False),(3,59,True,True)]:
            with self.subTest(args=args),self.assertRaises(mod.Refused):mod.check_final_gates(*args)
    def test_exact_ram_and_idle_thresholds_remain(self):
        mod.check_final_gates(2.5,60,True,True)
        self.assertEqual((mod.MIN_RAM_GIB,mod.MIN_IDLE_SECONDS,mod.TIMEOUT_SECONDS),(2.5,60,600))
    def test_tampered_exe_or_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'host').mkdir();(root/'host/PTTI-Desktop-Fan.exe').write_bytes(b'wrong')
            (root/'release.json').write_text('{}')
            with self.assertRaises(mod.Refused):mod.verify_candidate(root)
    def test_missing_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(mod.Refused):mod.verify_candidate(Path(temp))

if __name__=='__main__':unittest.main()
