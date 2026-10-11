from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.vision_lab import inventory


def test_light_inventory_does_not_load_models_or_labels(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.vision_lab.shutil.which', lambda name: None)
    config = SimpleNamespace(worker_python=tmp_path/'worker.exe', model_root=tmp_path/'models')
    config.model_root.mkdir()
    (config.model_root/'balltrack_best.pth').write_bytes(b'QA_FILE_ONLY_NOT_A_MODEL')
    result = inventory(config, tmp_path, tmp_path, 'test', True)
    assert result['debug_enabled']
    assert result['gpu']['state'] == 'UNAVAILABLE'
    ball = next(m for m in result['modules'] if m['id'] == 'ball')
    assert ball['model'] == 'FILE_PRESENT_NOT_LOADED'
    assert ball['smoke_test'] == 'NOT_RUN_THIS_SESSION'
    assert result['policy']['weights_loaded'] is False
    assert result['policy']['dataset_labels_read'] is False
    assert inventory(config, tmp_path, tmp_path, 'production', True)['debug_enabled'] is False


def test_debug_opt_in_and_production_rejection(tmp_path, monkeypatch):
    monkeypatch.delenv('VISION_DEBUG_MODE', raising=False)
    monkeypatch.setattr('backend.vision_lab.shutil.which', lambda name: None)
    app = create_app(tmp_path/'qa.db')
    with TestClient(app) as client:
        assert client.get('/api/vision/lab').json()['debug_enabled'] is False
        assert client.post('/api/vision/lab/debug', json={'enabled': True}).json()['debug_enabled']
        assert client.post('/api/vision/lab/debug', json={'enabled': 'true'}).status_code == 422
        app.state.repository.guard.mode = 'production'
        assert client.post('/api/vision/lab/debug', json={'enabled': True}).status_code == 403


def test_inventory_gpu_errors_stay_errors(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.vision_lab.shutil.which', lambda name: 'QA_PROBE')
    monkeypatch.setattr('backend.vision_lab.subprocess.run', lambda *a, **kw: SimpleNamespace(stdout='', returncode=1))
    config = SimpleNamespace(worker_python=tmp_path/'missing', model_root=tmp_path/'models')
    assert inventory(config, tmp_path, tmp_path, 'test')['gpu']['state'] == 'ERROR'
