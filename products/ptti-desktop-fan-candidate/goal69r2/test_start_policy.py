import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.modules['goal23_identity'] = types.SimpleNamespace(PINS={})
spec=importlib.util.spec_from_file_location('direct_host',Path(__file__).with_name('desktop_host.py'))
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
class StartPolicyTests(unittest.TestCase):
    def test_manual_never_reads_idle(self):
        idle=Mock(side_effect=AssertionError('manual must not query idle'))
        host.check_start_policy(False,lambda:3.0,idle)
        idle.assert_not_called()
    def test_low_memory_can_continue(self):
        ask=Mock(return_value=True)
        host.check_start_policy(False,lambda:0.8,Mock(),ask)
        ask.assert_called_once_with(0.8)
    def test_low_memory_can_cancel(self):
        with self.assertRaises(host.CandidateError):host.check_start_policy(False,lambda:1.0,Mock(),lambda _:False)
    def test_unknown_memory_warns(self):
        ask=Mock(return_value=True)
        def unknown():raise host.CandidateError('unavailable')
        host.check_start_policy(False,unknown,Mock(),ask);ask.assert_called_once_with(None)
    def test_automation_low_memory_fails(self):
        with self.assertRaises(host.CandidateError):host.check_start_policy(True,lambda:2.49,lambda:100)
    def test_automation_input_fails(self):
        with self.assertRaises(host.CandidateError):host.check_start_policy(True,lambda:3.0,lambda:0)
    def test_automation_exact_threshold_passes(self):host.check_start_policy(True,lambda:2.5,lambda:60)
    def test_bad_port_before_policy(self):
        host.PINS['qa_port']=4213
        with self.assertRaises(host.CandidateError):host.run_gui(4174)
if __name__=='__main__':unittest.main()
