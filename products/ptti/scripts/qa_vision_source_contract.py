"""Snapshot a previous temporary QA DB; never import or alter registered sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-db', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_db.resolve(strict=True)
    if not source.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise RuntimeError('Only a prior temporary QA database is permitted')
    destination = Path(tempfile.mkdtemp(prefix='ptti-playback-sprint03-')) / 'matches.db'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(destination) as copied:
            original.backup(copied)
    os.environ.update(PTTI_ENV='test', PTTI_DB=str(destination), PTTI_PREVIEW='1',
                      PTTI_MATCH_LIBRARY_PREVIEW='1', PTTI_VIDEO_FEED_PREVIEW='1',
                      PTTI_DUAL_SOURCE_PREVIEW='1')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get('/api/video-evidence/videos')
        assert response.status_code == 200
        rows = response.json()
        library = client.get('/api/video-evidence/library').json()
        fields = ('video_id', 'title', 'rights_status', 'source_sha256', 'hash_status', 'availability_status')
        videos = [{field: row.get(field) for field in fields} for row in rows]
        authorized = [row for row in videos if row['rights_status'] in ('LICENSED_FOR_ANALYSIS', 'RESEARCH_NONCOMMERCIAL')]
        assert any('game_1' in row['title'] for row in authorized)
        assert {row['video_id'] for row in authorized} <= {row['video_id'] for row in library['videos']}
        forwarded = {'Host': '127.0.0.1:53103', 'Origin': 'http://127.0.0.1:53103'}
        assert client.get('/api/video-evidence/videos', headers=forwarded).status_code == 200
        cross = {**forwarded, 'Origin': 'http://127.0.0.1:8773'}
        assert client.get('/api/video-evidence/videos', headers=cross).status_code == 403
        data = dict(qa_database=str(destination), original_qa_database='READ_ONLY_SQLITE_BACKUP',
                    api_status=200, videos=videos, cinema_vision_same_ids=True,
                    preserved_proxy_host_status=200, mismatched_origin_status=403,
                    native_request_failure_root_cause='NOT_CONFIRMED',
                    evidence_scope='IN_PROCESS_HTTP_CONTRACT; NOT_NATIVE_GUI')
    with destination.open('rb') as stream:
        data['snapshot_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(json.dumps(data, ensure_ascii=True))


if __name__ == '__main__':
    main()
