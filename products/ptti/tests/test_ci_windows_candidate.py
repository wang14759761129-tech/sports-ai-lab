import pytest
from scripts import ci_windows_candidate as candidate


def source(monkeypatch, *, sha='abc', dirty='', files='apps/desktop.py\n', frozen=None):
    def command(args, **kwargs):
        if args[1:3] == ['rev-parse', 'HEAD']:
            return sha
        if args[1] == 'status':
            return dirty
        return files
    monkeypatch.setattr(candidate.subprocess, 'check_output', command)
    monkeypatch.setattr(candidate, 'digest', lambda p: frozen or
                        'fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3')


def test_exact_clean_source(monkeypatch):
    source(monkeypatch)
    assert candidate.validate_source('abc') == 'abc'


@pytest.mark.parametrize('changes', [
    {'sha': 'different'}, {'dirty': ' M backend/main.py'},
    {'files': 'private/matches.sqlite3\n'}, {'files': 'datasets/video.mp4\n'},
    {'frozen': 'changed'},
])
def test_unsafe_sources_rejected(monkeypatch, changes):
    source(monkeypatch, **changes)
    with pytest.raises(RuntimeError):
        candidate.validate_source('abc')


def test_local_machine_cannot_run_ci_command(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    with pytest.raises(RuntimeError, match='isolated Windows Actions'):
        candidate.main()


def test_import_regression_runs_before_frontend_build(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(candidate, 'run_packager', lambda command, log: calls.append(command[-1]))
    candidate.run_frontend_checks('npm', tmp_path)
    assert 'test:folder-scan-status' in calls
    assert calls[-1] == 'build'
    assert len(calls) == len(set(calls))


def test_failed_import_regression_stops_build(monkeypatch, tmp_path):
    calls = []
    def run(command, log):
        calls.append(command[-1])
        if command[-1] == 'test:folder-scan-status':
            raise RuntimeError('import regression failed')
    monkeypatch.setattr(candidate, 'run_packager', run)
    with pytest.raises(RuntimeError, match='import regression failed'):
        candidate.run_frontend_checks('npm', tmp_path)
    assert 'build' not in calls
