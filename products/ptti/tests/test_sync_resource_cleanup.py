import pytest

from scripts import build_dual_source_v061_preview as build


def test_monitor_error_stops_only_its_owned_worker(tmp_path, monkeypatch):
    class Worker:
        pid = 12345
        returncode = None

        def poll(self):
            return self.returncode

    worker = Worker()
    stopped = []
    monkeypatch.setattr(build.subprocess, 'Popen', lambda *args, **kwargs: worker)
    monkeypatch.setattr(build, 'stop_process_tree', lambda p: stopped.append(p.pid))
    def failure():
        raise OSError('simulated monitor failure')
    monkeypatch.setattr(build.psutil, 'virtual_memory', failure)
    with pytest.raises(OSError):
        build.run_packager(['QA_ONLY'], tmp_path / 'qa.log')
    assert stopped == [12345]
