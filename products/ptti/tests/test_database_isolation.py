import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app, create_app, resolve_database_path


def test_guard_rejects_msix_production_alias_and_hardlink(tmp_path):
    from backend.database import ProductionDatabaseGuard
    local=tmp_path/'local';production=local/'PTTI'/'matches.db'
    production.parent.mkdir(parents=True);production.write_bytes(b'protected')
    alias=local/'Packages'/'OpenAI.Codex_test'/'LocalCache'/'Local'/'PTTI'/'matches.db'
    alias.parent.mkdir(parents=True);alias.write_bytes(b'private')
    guard=ProductionDatabaseGuard('development',{'LOCALAPPDATA':str(local)})
    with pytest.raises(RuntimeError,match='PRODUCTION_DATABASE_WRITE_GUARD'):
        guard.validate(alias)
    hardlink=tmp_path/'dev.db';os.link(production,hardlink)
    with pytest.raises(RuntimeError,match='PRODUCTION_DATABASE_WRITE_GUARD'):
        guard.validate(hardlink)
    assert production.read_bytes()==b'protected'


def test_guard_is_rechecked_on_every_connection(tmp_path):
    from backend.database import ProductionDatabaseGuard
    from backend.repository import Repository
    local=tmp_path/'local';production=local/'PTTI'/'matches.db'
    production.parent.mkdir(parents=True);production.write_bytes(b'protected')
    guard=ProductionDatabaseGuard('development',{'LOCALAPPDATA':str(local)})
    repo=Repository(tmp_path/'dev.db',guard=guard)
    repo.path.unlink();os.link(production,repo.path)
    with pytest.raises(RuntimeError,match='PRODUCTION_DATABASE_WRITE_GUARD'):
        repo.connect()
    assert production.read_bytes()==b'protected'


def test_startup_banner_and_runtime_diagnostics_use_isolated_db(tmp_path,capsys):
    isolated=create_app(tmp_path/'diagnostic.db')
    assert isolated.state.database_diagnostics['environment']=='TEST'
    assert isolated.state.database_diagnostics['database_mode']=='READ_WRITE'
    with TestClient(isolated) as client:
        data=client.get('/api/diagnostics/database').json()
        assert data['database']==str((tmp_path/'diagnostic.db').resolve())
    assert 'PTTI Environment: TEST' in capsys.readouterr().out


def test_pytest_cannot_enable_production_even_explicitly(tmp_path):
    from backend.database import ProductionDatabaseGuard
    with pytest.raises(RuntimeError,match='tests cannot enable production'):
        ProductionDatabaseGuard('production',{'LOCALAPPDATA':str(tmp_path)}).validate(tmp_path/'PTTI'/'matches.db')


def test_repository_test_mode_rejects_non_temp_path(monkeypatch,tmp_path):
    from backend.database import ProductionDatabaseGuard
    import backend.database as module
    monkeypatch.setattr(module.tempfile,'gettempdir',lambda:str(tmp_path/'allowed-temp'))
    with pytest.raises(RuntimeError,match='OS temp'):
        ProductionDatabaseGuard('test',{'LOCALAPPDATA':str(tmp_path)}).validate(tmp_path/'outside.db')


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
