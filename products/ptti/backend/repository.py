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
            db.execute('PRAGMA foreign_keys = ON')
            db.execute('CREATE TABLE IF NOT EXISTS matches (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS professional_sources (source_id TEXT PRIMARY KEY, source_url TEXT, source_type TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS athletes (athlete_id TEXT PRIMARY KEY, canonical_name_en TEXT NOT NULL, canonical_name_zh TEXT, country_or_association TEXT, ittf_id INTEGER, wtt_player_id TEXT, payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_athletes_name_en ON athletes(canonical_name_en COLLATE NOCASE)')
            db.execute('CREATE TABLE IF NOT EXISTS athlete_groups (group_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, description TEXT NOT NULL, user_edited INTEGER NOT NULL DEFAULT 0)')
            group_columns={row[1] for row in db.execute('PRAGMA table_info(athlete_groups)')}
            if 'user_edited' not in group_columns:
                db.execute('ALTER TABLE athlete_groups ADD COLUMN user_edited INTEGER NOT NULL DEFAULT 0')
            db.execute('CREATE TABLE IF NOT EXISTS athlete_group_memberships (athlete_id TEXT NOT NULL REFERENCES athletes(athlete_id), group_code TEXT NOT NULL REFERENCES athlete_groups(group_code), PRIMARY KEY(athlete_id,group_code))')
            db.execute('CREATE TABLE IF NOT EXISTS athlete_ranking_history (athlete_id TEXT NOT NULL REFERENCES athletes(athlete_id), ranking_type TEXT NOT NULL, rank INTEGER NOT NULL, points INTEGER, ranking_year INTEGER NOT NULL, ranking_week INTEGER NOT NULL, ranking_date TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES professional_sources(source_id), payload TEXT NOT NULL, UNIQUE(athlete_id,ranking_type,ranking_year,ranking_week,source_id))')
            db.execute('CREATE INDEX IF NOT EXISTS idx_athlete_rankings_latest ON athlete_ranking_history(athlete_id,ranking_type,ranking_date DESC)')
            db.execute('CREATE TABLE IF NOT EXISTS professional_matches (match_id TEXT PRIMARY KEY, event_name TEXT NOT NULL, event_id TEXT, event_date TEXT, round TEXT, competition_level TEXT, player_a_id TEXT NOT NULL REFERENCES athletes(athlete_id), player_b_id TEXT NOT NULL REFERENCES athletes(athlete_id), winner_id TEXT REFERENCES athletes(athlete_id), payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_professional_matches_event_date ON professional_matches(event_date DESC,event_name)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_professional_matches_players ON professional_matches(player_a_id,player_b_id)')
            db.execute('CREATE TABLE IF NOT EXISTS professional_match_sources (match_id TEXT NOT NULL REFERENCES professional_matches(match_id), source_id TEXT NOT NULL REFERENCES professional_sources(source_id), PRIMARY KEY(match_id,source_id))')
            db.execute('CREATE TABLE IF NOT EXISTS professional_seed_versions (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')

    def seed_professional(self,manifest):
        """Apply each shipped seed version once; later edits survive app restarts."""
        from backend.professional import validate_seed
        import datetime
        validate_seed(manifest)
        version=manifest['schema_version']
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM professional_seed_versions WHERE version=?',(version,)).fetchone():
                return False
            for source in manifest.get('sources',[]):
                db.execute('INSERT OR IGNORE INTO professional_sources VALUES (?,?,?,?,?)',(
                    source['source_id'],source.get('source_url'),source['source_type'],source['retrieved_at'],
                    json.dumps(source,ensure_ascii=False)))
            for group in manifest.get('groups',[]):
                db.execute('INSERT OR IGNORE INTO athlete_groups(group_code,display_name,description) VALUES (?,?,?)',(
                    group['group_code'],group['display_name'],group.get('description','')))
            for athlete in manifest.get('athletes',[]):
                profile={k:v for k,v in athlete.items() if k not in {'current_ranking','group_codes'}}
                values=(
                    athlete['athlete_id'],athlete['canonical_name_en'],athlete.get('canonical_name_zh'),
                    athlete.get('country_or_association'),athlete.get('ittf_id'),athlete.get('wtt_player_id'),
                    json.dumps(profile,ensure_ascii=False))
                db.execute('INSERT OR IGNORE INTO athletes VALUES (?,?,?,?,?,?,?)',values)
                # New manifest versions may add verified provenance to an existing stable identity.
                # Group memberships and ranking snapshots live in separate tables and are not replaced.
                db.execute('UPDATE athletes SET canonical_name_en=?,canonical_name_zh=?,country_or_association=?,ittf_id=?,wtt_player_id=?,payload=? WHERE athlete_id=?',
                    (values[1],values[2],values[3],values[4],values[5],values[6],values[0]))
            for group in manifest.get('groups',[]):
                if db.execute('SELECT user_edited FROM athlete_groups WHERE group_code=?',(group['group_code'],)).fetchone()[0]:
                    continue
                db.execute('DELETE FROM athlete_group_memberships WHERE group_code=?',(group['group_code'],))
                db.executemany('INSERT INTO athlete_group_memberships VALUES (?,?)',[
                    (athlete['athlete_id'],group['group_code']) for athlete in manifest.get('athletes',[])
                    if group['group_code'] in athlete.get('group_codes',[])])
            for athlete in manifest.get('athletes',[]):
                ranking=athlete.get('current_ranking')
                if ranking:
                    snap=manifest['ranking_snapshot'];source=snap['source_id']
                    payload={'athlete_id':athlete['athlete_id'],'ranking_type':snap['ranking_type'],
                        'rank':ranking['rank'],'points':ranking['points'],'ranking_year':snap['ranking_year'],
                        'ranking_week':snap['ranking_week'],'ranking_date':snap['ranking_date'],'source_id':source}
                    key=(athlete['athlete_id'],snap['ranking_type'],snap['ranking_year'],snap['ranking_week'],source)
                    existing=db.execute('SELECT payload FROM athlete_ranking_history WHERE athlete_id=? AND ranking_type=? AND ranking_year=? AND ranking_week=? AND source_id=?',key).fetchone()
                    encoded=json.dumps(payload,ensure_ascii=False)
                    if existing and existing[0]!=encoded:
                        raise ValueError(f'Ranking snapshot is immutable and conflicts with existing data: {key}')
                    db.execute('INSERT OR IGNORE INTO athlete_ranking_history VALUES (?,?,?,?,?,?,?,?,?)',(
                        athlete['athlete_id'],snap['ranking_type'],ranking['rank'],ranking['points'],
                        snap['ranking_year'],snap['ranking_week'],snap['ranking_date'],source,encoded))
            for match in manifest.get('professional_matches',[]):
                encoded=json.dumps(match,ensure_ascii=False)
                existing=db.execute('SELECT payload FROM professional_matches WHERE match_id=?',(match['match_id'],)).fetchone()
                if existing and existing[0]!=encoded:
                    raise ValueError(f'Professional match record is immutable and conflicts with existing data: {match["match_id"]}')
                db.execute('INSERT OR IGNORE INTO professional_matches VALUES (?,?,?,?,?,?,?,?,?,?)',(
                    match['match_id'],match['event_name'],match.get('event_id'),match.get('event_date'),match.get('round'),
                    match.get('competition_level'),match['player_a_id'],match['player_b_id'],match.get('winner_id'),encoded))
                for source in match.get('source_ids',[]):
                    db.execute('INSERT OR IGNORE INTO professional_match_sources VALUES (?,?)',(match['match_id'],source))
            db.execute('INSERT INTO professional_seed_versions(version,applied_at) VALUES (?,?)',(
                version,datetime.datetime.now(datetime.timezone.utc).isoformat()))
        return True

    def list_groups(self):
        with self.connect() as db:
            rows=db.execute('SELECT g.group_code,g.display_name,g.description,COUNT(m.athlete_id) FROM athlete_groups g LEFT JOIN athlete_group_memberships m USING(group_code) GROUP BY g.group_code ORDER BY g.display_name').fetchall()
            return [dict(group_code=r[0],display_name=r[1],description=r[2],athlete_count=r[3]) for r in rows]

    def set_group_members(self,group_code,athlete_ids):
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM athlete_groups WHERE group_code=?',(group_code,)).fetchone(): return None
            unique=list(dict.fromkeys(athlete_ids))
            if unique:
                marks=','.join('?' for _ in unique)
                found={r[0] for r in db.execute(f'SELECT athlete_id FROM athletes WHERE athlete_id IN ({marks})',unique)}
                missing=set(unique)-found
                if missing: raise ValueError('Unknown athlete_id: '+', '.join(sorted(missing)))
            db.execute('DELETE FROM athlete_group_memberships WHERE group_code=?',(group_code,))
            db.executemany('INSERT INTO athlete_group_memberships VALUES (?,?)',[(i,group_code) for i in unique])
            db.execute('UPDATE athlete_groups SET user_edited=1 WHERE group_code=?',(group_code,))
        return self.get_group(group_code)

    def get_group(self,group_code):
        with self.connect() as db:
            group=db.execute('SELECT group_code,display_name,description FROM athlete_groups WHERE group_code=?',(group_code,)).fetchone()
            if not group:return None
            ids=[r[0] for r in db.execute('SELECT athlete_id FROM athlete_group_memberships WHERE group_code=? ORDER BY athlete_id',(group_code,))]
        return dict(group_code=group[0],display_name=group[1],description=group[2],athlete_ids=ids)

    def list_athletes(self,group_code=None,search=None):
        query='SELECT a.athlete_id,a.payload FROM athletes a'
        where=[];params=[]
        if group_code:
            query+=' JOIN athlete_group_memberships gm ON gm.athlete_id=a.athlete_id'
            where.append('gm.group_code=?');params.append(group_code)
        if search:
            where.append('(a.canonical_name_en LIKE ? COLLATE NOCASE OR a.canonical_name_zh LIKE ? COLLATE NOCASE OR a.country_or_association LIKE ? COLLATE NOCASE)')
            params.extend([f'%{search}%']*3)
        if where:query+=' WHERE '+' AND '.join(where)
        query+=' ORDER BY COALESCE((SELECT rank FROM athlete_ranking_history r WHERE r.athlete_id=a.athlete_id ORDER BY ranking_date DESC,ranking_year DESC,ranking_week DESC LIMIT 1),999999), a.canonical_name_en COLLATE NOCASE'
        profiles=[]
        with self.connect() as db:
            rows=db.execute(query,params).fetchall()
            for athlete_id,payload in rows:
                profile=json.loads(payload)
                rankings=db.execute('SELECT athlete_id,ranking_type,rank,points,ranking_year,ranking_week,ranking_date,source_id FROM athlete_ranking_history WHERE athlete_id=? ORDER BY ranking_date DESC,ranking_year DESC,ranking_week DESC',(athlete_id,)).fetchall()
                groups=[r[0] for r in db.execute('SELECT group_code FROM athlete_group_memberships WHERE athlete_id=? ORDER BY group_code',(athlete_id,))]
                profile.update(current_world_rank=rankings[0][2] if rankings else None,
                    ranking_points=rankings[0][3] if rankings else None,
                    ranking_year=rankings[0][4] if rankings else None,
                    ranking_week=rankings[0][5] if rankings else None,
                    ranking_date=rankings[0][6] if rankings else None,
                    ranking_history_count=len(rankings),groups=groups)
                profiles.append(profile)
        return profiles

    def get_athlete(self,athlete_id):
        with self.connect() as db:row=db.execute('SELECT payload FROM athletes WHERE athlete_id=?',(athlete_id,)).fetchone()
        return self._athlete_view(json.loads(row[0])) if row else None

    def _athlete_view(self,profile):
        rankings=self.get_rankings(profile['athlete_id'])
        groups=self.get_athlete_groups(profile['athlete_id'])
        profile.update(current_world_rank=rankings[0]['rank'] if rankings else None,
            ranking_points=rankings[0]['points'] if rankings else None,
            ranking_year=rankings[0]['ranking_year'] if rankings else None,
            ranking_week=rankings[0]['ranking_week'] if rankings else None,
            ranking_date=rankings[0]['ranking_date'] if rankings else None,
            ranking_history_count=len(rankings),groups=groups)
        return profile

    def get_athlete_groups(self,athlete_id):
        with self.connect() as db:return [r[0] for r in db.execute('SELECT group_code FROM athlete_group_memberships WHERE athlete_id=? ORDER BY group_code',(athlete_id,))]

    def get_rankings(self,athlete_id):
        with self.connect() as db:rows=db.execute('SELECT athlete_id,ranking_type,rank,points,ranking_year,ranking_week,ranking_date,source_id FROM athlete_ranking_history WHERE athlete_id=? ORDER BY ranking_date DESC,ranking_year DESC,ranking_week DESC',(athlete_id,)).fetchall()
        return [dict(athlete_id=r[0],ranking_type=r[1],rank=r[2],points=r[3],ranking_year=r[4],ranking_week=r[5],ranking_date=r[6],source_id=r[7]) for r in rows]

    def get_sources(self,source_ids):
        ids=list(dict.fromkeys(source_ids))
        if not ids:return []
        with self.connect() as db:
            marks=','.join('?' for _ in ids);rows=db.execute(f'SELECT payload FROM professional_sources WHERE source_id IN ({marks})',ids).fetchall()
        return [json.loads(r[0]) for r in rows]

    def professional_matches(self,athlete_id=None):
        query='SELECT payload FROM professional_matches';params=[]
        if athlete_id:
            query+=' WHERE player_a_id=? OR player_b_id=?';params=[athlete_id,athlete_id]
        query+=' ORDER BY COALESCE(event_date,\'\') DESC,event_name,match_id'
        with self.connect() as db:rows=db.execute(query,params).fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_professional_match(self,match_id):
        with self.connect() as db:row=db.execute('SELECT payload FROM professional_matches WHERE match_id=?',(match_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_professional_match(self,record):
        with self.connect() as db:
            participants={record['player_a_id'],record['player_b_id']}
            marks=','.join('?' for _ in participants)
            found={r[0] for r in db.execute(f'SELECT athlete_id FROM athletes WHERE athlete_id IN ({marks})',list(participants))}
            if found!=participants:raise ValueError('Both participants must exist in the athlete registry')
            missing=set(record.get('source_ids',[]))-{r[0] for r in db.execute('SELECT source_id FROM professional_sources')}
            if missing:raise ValueError('Unknown source_id: '+', '.join(sorted(missing)))
            encoded=json.dumps(record,ensure_ascii=False)
            db.execute('INSERT INTO professional_matches VALUES (?,?,?,?,?,?,?,?,?,?)',(
                record['match_id'],record['event_name'],record.get('event_id'),record.get('event_date'),record.get('round'),
                record.get('competition_level'),record['player_a_id'],record['player_b_id'],record.get('winner_id'),encoded))
            for source in record.get('source_ids',[]):db.execute('INSERT INTO professional_match_sources VALUES (?,?)',(record['match_id'],source))
        return record
    def settings(self):
        with self.connect() as db: row=db.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}
    def save_settings(self,value):
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO preferences VALUES (1,?)',(json.dumps(value),))
    def connect(self):
        self.guard.validate(self.path)
        connection=sqlite3.connect(self.path,factory=ClosingConnection)
        connection.execute('PRAGMA foreign_keys = ON')
        return connection
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
