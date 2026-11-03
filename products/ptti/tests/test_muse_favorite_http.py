"""Real frontend persistence helper -> loopback FastAPI -> isolated SQLite.

This is API integration, not browser or Windows GUI acceptance.
"""
import json
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from backend.main import create_app


def test_frontend_helper_real_http_sqlite_and_reload(tmp_path):
    assert shutil.which('node'), 'Node is required; do not silently skip persistence coverage'
    database = tmp_path / 'muse-http-qa.db'
    app = create_app(database)
    assert app.state.database_path.resolve() == database.resolve()
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', lifespan='off'))
    worker = threading.Thread(target=server.run, kwargs={'sockets':[sock]}, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started, 'Isolated HTTP API did not start'
        helper = (Path(__file__).resolve().parents[1] / 'frontend/src/favoritePersistence.mjs').as_uri()
        script = """
const {persistFavoriteKeys}=await import(process.argv[1]);
const {base,keys,saved,initial,dropResponse}=JSON.parse(process.argv[2]);
let writes=0,reads=0;
const result=await persistFavoriteKeys(keys,saved,initial,async(url,options)=>{
  if(options)writes++;else reads++;
  const response=await fetch(new URL(url,base),options);
  if(options&&dropResponse)throw Error('QA response lost after SQLite commit');
  return response;
});
console.log(JSON.stringify({...result,writes,reads}));
"""
        def run(keys, saved, initial, drop=False):
            result = subprocess.run(['node','--input-type=module','-e',script,helper,json.dumps({
                'base':f'http://127.0.0.1:{port}', 'keys':keys,'saved':saved,'initial':initial,'dropResponse':drop,
            })], capture_output=True, text=True, encoding='utf-8', timeout=20)
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout)
        def rows():
            with sqlite3.connect(database) as db:
                return sorted(row[0] for row in db.execute('SELECT source_key FROM media_feed_favorites'))
        match = 'match:pro:wtt:china-smash-2025:wang-chuqin-felix-lebrun'
        legacy = 'official:0QgbtsBWZhk'
        other = 'official:aFs7HJ0NX18'
        # Card save -> Story cancel, then an independent request/reopened DB.
        assert run([match],True,[])['error'] == ''
        assert rows() == [match]
        assert run([match],False,[match])['favorites'] == []
        assert rows() == []
        # Story save -> card cancel. Unrelated source survives.
        saved = run([match,other],True,[])['favorites']
        assert run([match],False,saved)['favorites'] == [other]
        assert rows() == [other]
        # Legacy and canonical exact-match keys; no implicit migration.
        saved = run([match,legacy],True,[other])['favorites']
        assert run([legacy,match,match],False,saved)['favorites'] == [other]
        assert rows() == [other]
        # A lost successful response must read back durable state without retrying DELETE.
        run([match],True,[other])
        result = run([match],False,[match,other],drop=True)
        assert result['favorites'] == [other] and result['error']
        assert (result['writes'],result['reads']) == (1,1)
        assert rows() == [other]
        # SQLite rejects deletion; helper re-reads unchanged state and keeps an error.
        run([match],True,[other])
        with sqlite3.connect(database) as db:
            db.execute("CREATE TRIGGER qa_reject_delete BEFORE DELETE ON media_feed_favorites BEGIN SELECT RAISE(ABORT,'QA only'); END")
        result = run([match],False,[match,other])
        assert sorted(result['favorites']) == sorted([match,other]) and result['error']
        assert (result['writes'],result['reads']) == (1,1)
        assert rows() == sorted([match,other])
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        sock.close()
        assert not worker.is_alive(), 'QA server must exit; no resident process left behind'
