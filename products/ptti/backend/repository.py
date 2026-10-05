import json
import sqlite3
import uuid
from pathlib import Path

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

class Repository:
    def __init__(self,path,guard=None):
        from backend.database import ProductionDatabaseGuard
        import os,sys
        mode='test' if 'pytest' in sys.modules else os.environ.get('PTTI_ENV','development')
        self.guard=guard or ProductionDatabaseGuard(mode)
        self.path=self.guard.validate(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS matches (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
    def settings(self):
        with self.connect() as db: row=db.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}
    def save_settings(self,value):
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO preferences VALUES (1,?)',(json.dumps(value),))
    def connect(self):
        self.guard.validate(self.path)
        return sqlite3.connect(self.path,factory=ClosingConnection)
    def save(self,payload):
        payload['id']=str(uuid.uuid4())
        with self.connect() as db: db.execute('INSERT INTO matches VALUES (?,?)',(payload['id'],json.dumps(payload,ensure_ascii=False)))
        return payload
    def list(self):
        with self.connect() as db: return [json.loads(r[0]) for r in db.execute('SELECT payload FROM matches ORDER BY rowid DESC')]
    def get(self,id):
        with self.connect() as db: r=db.execute('SELECT payload FROM matches WHERE id=?',(id,)).fetchone()
        return json.loads(r[0]) if r else None
    def delete(self,id):
        with self.connect() as db: return db.execute('DELETE FROM matches WHERE id=?',(id,)).rowcount>0
