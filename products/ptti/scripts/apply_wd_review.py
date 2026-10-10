"""Apply explicit WD playback observations to an isolated QA repository only."""
import json
import uuid
import tempfile
from pathlib import Path

from backend.video_sources import official_source


def apply_review(repo, review):
    path = Path(repo.path).resolve()
    if not path.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('Playback reviews require an isolated temporary QA database')
    changed = 0
    with repo.connect() as db:
        for item in review['entries']:
            key = 'YOUTUBE:' + item['video_id']
            found = db.execute('SELECT payload FROM media_online_sources WHERE source_key=?', (key,)).fetchone()
            if not found:
                raise ValueError('Existing WD source required')
            row = json.loads(found[0])
            if row.get('discipline') != 'WD':
                raise ValueError('WD-only review cannot modify another category')
            evidence = {**item, 'surface': review['surface'], 'checked_at': review['reviewed_at']}
            if row.get('watch_page_test') == evidence:
                continue
            row['watch_page_test'] = evidence
            row['playback_limitation'] = item['limitation']
            row['playback_status'] = 'RESTRICTED' if item['result'] == 'REGION_RESTRICTED' else 'NOT_TESTED'
            row['video_source'] = official_source(row)
            db.execute('UPDATE media_online_sources SET payload=? WHERE source_key=?',
                       (json.dumps(row, ensure_ascii=False), key))
            db.execute('INSERT INTO evidence_audit VALUES (?,?,?,?,?)',
                       (str(uuid.uuid4()), key, 'WD_OFFICIAL_PAGE_REVIEW', review['reviewed_at'],
                        json.dumps({'before': json.loads(found[0]), 'observation': evidence}, ensure_ascii=False)))
            changed += 1
    return changed
