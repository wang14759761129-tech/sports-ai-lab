import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.main import create_app


def test_lab_import_requires_analysis_permission_before_upload(tmp_path, monkeypatch):
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY', '1')
    monkeypatch.setattr('backend.vision_lab.psutil.virtual_memory',
                        lambda: SimpleNamespace(available=1024**3))
    source = {'type': 'local', 'rights': 'user_provided', 'rights_notes': ''}
    with TestClient(create_app(tmp_path/'qa.db')) as client:
        def submit(confirmed=False):
            return client.post('/api/vision/import',
                               data={'source': json.dumps(source), 'rights_confirmed': str(confirmed).lower()},
                               files={'file': ('permission-qa.mp4', b'NOT_REAL_VIDEO', 'video/mp4')})
        assert submit().status_code == 422
        source['rights_notes'] = 'Synthetic permission test only'
        assert submit().status_code == 422
        source['rights_notes'] = '   '
        assert submit(True).status_code == 422
        source['rights_notes'] = 'Synthetic permission test only'
        response = submit(True)
        assert response.status_code == 503
        assert 'RAM' in response.json()['detail']
    assert not list(tmp_path.rglob('*.mp4'))
