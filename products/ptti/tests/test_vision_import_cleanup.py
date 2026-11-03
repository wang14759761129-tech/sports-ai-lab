import json

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.mark.parametrize('failure_stage', ['inspect', 'submit'])
def test_rejected_vision_import_removes_only_its_upload(tmp_path, monkeypatch, failure_stage):
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY', '0')
    old = tmp_path/'vision/user_uploads/previous.mp4'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'PREVIOUS_QA_INPUT')
    def fail(*args, **kwargs):
        raise ValueError('QA rejection')
    monkeypatch.setattr('backend.vision_api.VisionService.inspect', lambda *a: {'video': {}, 'quality': {}})
    monkeypatch.setattr('backend.vision_api.VisionService.' + failure_stage, fail)
    source = {'type': 'local', 'rights': 'user_provided'}
    with TestClient(create_app(tmp_path/'qa.db')) as client:
        response = client.post('/api/vision/import', data={'source': json.dumps(source)},
                               files={'file': ('qa.mp4', b'INVALID_QA_ONLY', 'video/mp4')})
    assert response.status_code == 422
    assert list(old.parent.glob('*.mp4')) == [old]
    assert old.read_bytes() == b'PREVIOUS_QA_INPUT'


def test_accepted_vision_import_keeps_worker_input(tmp_path, monkeypatch):
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY', '0')
    monkeypatch.setattr('backend.vision_api.VisionService.inspect', lambda *a: {'video': {}, 'quality': {}})
    monkeypatch.setattr('backend.vision_api.VisionService.submit', lambda *a, **kw: {'id': 'QA_NO_WORKER'})
    with TestClient(create_app(tmp_path/'qa.db')) as client:
        response = client.post('/api/vision/import',
                               data={'source': json.dumps({'type': 'local', 'rights': 'user_provided'})},
                               files={'file': ('qa.mp4', b'QA_WORKER_INPUT', 'video/mp4')})
    assert response.status_code == 200
    uploads = list((tmp_path/'vision/user_uploads').glob('*.mp4'))
    assert len(uploads) == 1
    assert uploads[0].read_bytes() == b'QA_WORKER_INPUT'
