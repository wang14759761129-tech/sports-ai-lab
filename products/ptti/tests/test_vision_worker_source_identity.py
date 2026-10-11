import sys

import pytest
from fastapi import HTTPException

from backend.vision_api import _worker_product_root


@pytest.mark.parametrize('actual,dirty,status', [('expected','',None),('other','',409),('expected','modified',409)])
def test_frozen_worker_uses_matching_clean_source(tmp_path, monkeypatch, actual, dirty, status):
    (tmp_path/'vision_worker').mkdir()
    monkeypatch.setenv('PTTI_VISION_HOME',str(tmp_path))
    monkeypatch.setenv('PTTI_PREVIEW_COMMIT','expected')
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr('backend.vision_api.subprocess.check_output',lambda args,**kw: actual if args[1]=='rev-parse' else dirty)
    if status:
        with pytest.raises(HTTPException) as error:
            _worker_product_root()
        assert error.value.status_code==status
    else:
        assert _worker_product_root()==tmp_path
