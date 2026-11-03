"""Offline fail-closed checks: no sockets, browser or user data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HOST = Path(__file__).resolve().parents[1] / 'apps' / 'founder_preview_host.py'
spec = importlib.util.spec_from_file_location('founder_preview_host_test', HOST)
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

class StartupChecks(unittest.TestCase):
    def test_missing_frontend_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frontend = root / 'frontend'
            qa = root / 'qa'
            frontend.mkdir()
            qa.mkdir()
            with self.assertRaisesRegex(RuntimeError, '缺少统一模式前端'):
                host.start_services(frontend, qa)
            self.assertEqual(list(qa.iterdir()), [])

    def test_missing_qa_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                host.start_services(root, root / 'missing')

if __name__ == '__main__':
    unittest.main()
