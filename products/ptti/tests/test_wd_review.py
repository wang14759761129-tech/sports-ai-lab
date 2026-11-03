import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from scripts.apply_wd_review import apply_review


def test_wd_review_is_audited_idempotent_and_not_embed_or_complete(tmp_path):
    with TestClient(create_app(tmp_path / 'qa.db')) as client:
        manifest = json.loads(Path('data/professional/catalog_expansion_r1.json').read_text(encoding='utf8'))
        assert client.post('/api/video-evidence/library/catalog/import', json=manifest).status_code == 200
        before = client.get('/api/video-evidence/library').json()['official_videos']
        review = json.loads(Path('data/professional/wd_playback_review_r4.json').read_text(encoding='utf8'))
        repo = client.app.state.repository
        assert apply_review(repo, review) == 3
        assert apply_review(repo, review) == 0
        after = client.get('/api/video-evidence/library').json()['official_videos']
        assert [r for r in before if r.get('discipline') != 'WD'] == [r for r in after if r.get('discipline') != 'WD']
        wd = [r for r in after if r.get('discipline') == 'WD']
        assert len(wd) == 3
        assert sum(r['video_source']['playback_verified'] for r in wd) == 2
        assert all(r['video_source']['playback_type'] == 'OFFICIAL_PAGE' for r in wd)
        assert all(r['video_source']['is_full_match'] is not True for r in wd)
        assert all(r['video_source']['analysis_permission'] == 'DENIED' for r in wd)
        with repo.connect() as db:
            assert db.execute("SELECT count(*) FROM evidence_audit WHERE action='WD_OFFICIAL_PAGE_REVIEW'").fetchone()[0] == 3
