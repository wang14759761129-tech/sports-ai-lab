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
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY', '0')
    monkeypatch.setattr('backend.vision_lab.shutil.which', lambda name: None)
    app = create_app(tmp_path/'qa.db')
    with TestClient(app) as client:
        assert client.get('/api/vision/lab').json()['debug_enabled'] is False
        assert client.post('/api/vision/lab/debug', json={'enabled': True}).json()['debug_enabled']
        assert client.post('/api/vision/benchmark', json={'device':'cuda'}).status_code == 403
        assert client.post('/api/vision/lab/debug', json={'enabled': 'true'}).status_code == 422
        app.state.repository.guard.mode = 'production'
        assert client.post('/api/vision/lab/debug', json={'enabled': True}).status_code == 403


def test_inventory_gpu_errors_stay_errors(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.vision_lab.shutil.which', lambda name: 'QA_PROBE')
    monkeypatch.setattr('backend.vision_lab.subprocess.run', lambda *a, **kw: SimpleNamespace(stdout='', returncode=1))
    config = SimpleNamespace(worker_python=tmp_path/'missing', model_root=tmp_path/'models')
    assert inventory(config, tmp_path, tmp_path, 'test')['gpu']['state'] == 'ERROR'


def test_lab_excludes_game5_before_hashing(tmp_path, monkeypatch):
    from backend import player_tracking_closed_loop as loop
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY', '1')
    monkeypatch.setattr(loop, '_research_root', lambda *args: tmp_path)
    monkeypatch.setattr(loop, '_manifest', lambda *args: {'videos':[{'video_id':'game_5-t60','match_id':'game_5',
        'official_split':'TRAIN','seed_screening':{'status':'SEEDS_READY'},
        'clip':{'file':'qa-locked.mp4','sha256':'0'*64,'bytes':9}}]})
    monkeypatch.setattr(loop, '_player_tracking_validation_manifest', lambda *args: None)
    def forbidden(*args):
        raise AssertionError('Locked footage must not be hashed')
    monkeypatch.setattr(loop, '_sha', forbidden)
    folder=tmp_path/'datasets/extended-openttgames'
    folder.mkdir(parents=True)
    (folder/'qa-locked.mp4').write_bytes(b'QA_ONLY__')
    assert loop.list_closed_loop_samples()==[]


def test_debug_execution_guard_blocks_before_start(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from backend.vision_lab import guard_debug_inference
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY','1')
    monkeypatch.setattr('backend.vision_lab.psutil.virtual_memory',lambda:SimpleNamespace(available=1024**3))
    with pytest.raises(HTTPException) as error:
        guard_debug_inference()
    assert error.value.status_code==503
