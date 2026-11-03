import json

import pytest
from fastapi import HTTPException

from backend import player_motion_api as pose


@pytest.mark.parametrize('match,allowed',[('game_1',True),('game_3',True),('game_5',False),('UNKNOWN',False)])
def test_lab_pose_checks_match_before_loading_source(tmp_path,monkeypatch,match,allowed):
    path=tmp_path/'qa-tracking.json'
    path.write_text(json.dumps({'match_id':match}))
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY','1')
    monkeypatch.setattr(pose,'tracking_job_path',lambda *a:path)
    if allowed:
        pose._guard_lab_job('a'*32)
    else:
        with pytest.raises(HTTPException) as error:
            pose._guard_lab_job('a'*32)
        assert error.value.status_code==403


def test_bad_lab_job_id_is_rejected_before_metadata(monkeypatch):
    monkeypatch.setenv('PTTI_VISION_LAB_DEV_ONLY','1')
    def forbidden(*args):
        raise AssertionError('Invalid job must not resolve any file')
    monkeypatch.setattr(pose,'tracking_job_path',forbidden)
    with pytest.raises(HTTPException) as error:
        pose._guard_lab_job('../invalid')
    assert error.value.status_code==422
