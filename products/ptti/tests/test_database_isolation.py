import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app, create_app, resolve_database_path


def production_db(local_app_data=None):
    root = Path(local_app_data or os.environ.get('LOCALAPPDATA', Path.home()))
    return root / 'PTTI' / 'matches.db'


def test_tests_never_use_production_db():
    production = production_db().resolve(strict=False)
    selected = app.state.database_path.resolve(strict=False)
    assert selected != production
    assert Path(tempfile.gettempdir()).resolve(strict=False) in selected.parents


def test_dev_never_defaults_to_production_db(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path)}
    selected = resolve_database_path(environ=env, testing=False)
    assert selected == (tmp_path / 'PTTI-Dev' / 'matches.db').resolve(strict=False)
    assert selected != (tmp_path / 'PTTI' / 'matches.db').resolve(strict=False)


def test_database_path_isolation(tmp_path):
    production = tmp_path / 'PTTI' / 'matches.db'
    with pytest.raises(RuntimeError, match='PRODUCTION_DATABASE_WRITE_GUARD'):
        resolve_database_path(production, environ={'LOCALAPPDATA': str(tmp_path), 'PTTI_ENV': 'development'}, testing=False)
    with pytest.raises(RuntimeError, match='PRODUCTION_DATABASE_WRITE_GUARD'):
        resolve_database_path(production, environ={'LOCALAPPDATA': str(tmp_path), 'PTTI_ENV': 'test'}, testing=True)


def test_test_db_created_in_temp(tmp_path):
    db = tmp_path / 'isolated-test.db'
    with TestClient(create_app(db)) as client:
        assert client.get('/api/health').status_code == 200
    assert db.exists()
    assert db.resolve().parent == tmp_path.resolve()


def test_production_db_guard(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PTTI_ENV': 'test', 'PTTI_DB': str(tmp_path / 'PTTI' / 'matches.db')}
    with pytest.raises(RuntimeError, match='PRODUCTION_DATABASE_WRITE_GUARD'):
        resolve_database_path(environ=env, testing=True)


def test_missing_test_config_and_changed_cwd_fail_closed(tmp_path):
    product = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop('PTTI_DB', None)
    env['PTTI_ENV'] = 'test'
    env['LOCALAPPDATA'] = str(tmp_path / 'local')
    env['PYTHONPATH'] = str(product)
    result = subprocess.run(
        [sys.executable, '-c', 'import backend.main'],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert 'PRODUCTION_DATABASE_WRITE_GUARD' in result.stderr
    assert not (tmp_path / 'local' / 'PTTI' / 'matches.db').exists()
