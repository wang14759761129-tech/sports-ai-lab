"""Independent, deterministic point analysis. No network or storage dependencies."""
import csv
import io
from collections import Counter

SCHEMA_VERSION = '1.0.0-new'
ANALYTICS_VERSION = '0.1.0'
REQUIRED = ['game', 'point', 'server', 'winner', 'score_a', 'score_b']
CATEGORIES = {'server': {'A', 'B'}, 'winner': {'A', 'B'}, 'serve_placement': {'short_fh', 'short_bh', 'short_middle', 'long_fh', 'long_bh', 'long_middle'}, 'serve_type': {'backspin', 'topspin', 'sidespin', 'no_spin', 'mixed'}, 'receive_type': {'push', 'flick', 'attack', 'block', 'other'}, 'third_ball_attack': {'yes', 'no'}, 'point_phase': {'serve', 'receive', 'third_ball', 'rally'}, 'outcome': {'winner', 'error'}}

def ingest(raw: bytes):
    issues = []
    def issue(level, row, field, message):
        issues.append(dict(level=level, row=row, field=field, message=message))
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
        headers = reader.fieldnames or []
        for field in REQUIRED:
            if field not in headers: issue('error', 1, field, 'Required column is missing.')
        if len(headers) != len(set(headers)): issue('error', 1, 'header', 'Duplicate column names.')
        rows = list(reader)
    except (UnicodeError, csv.Error):
        return [], {'valid': False, 'issues': [dict(level='error', row=1, field='csv', message='Use a valid UTF-8 CSV.')], 'row_count': 0}
    if not rows: issue('error', 1, 'csv', 'Match has no points.')
    prev_game, prev_point, a, b, first_server = 0, 0, 0, 0, None
    for n, r in enumerate(rows, 2):
        if None in r or any(v is None for v in r.values()): issue('error', n, 'csv', 'Row width differs from header.')
        for f in REQUIRED:
            if not r.get(f): issue('error', n, f, 'Required value is missing.')
        for f, allowed in CATEGORIES.items():
            if r.get(f) and r[f] not in allowed: issue('error', n, f, 'Unknown category: ' + r[f])
        integers = {}
        for f in ['game', 'point', 'score_a', 'score_b', 'rally_length']:
            if r.get(f):
                try:
                    integers[f] = int(r[f])
                    if integers[f] < (1 if f in ['game', 'point', 'rally_length'] else 0): raise ValueError()
                except ValueError: issue('error', n, f, 'Expected a nonnegative integer (game, point and rally length start at 1).')
        if not all(f in integers for f in ['game', 'point', 'score_a', 'score_b']): continue
        g, p = integers['game'], integers['point']
        ended = max(a, b) >= 11 and abs(a-b) >= 2
        if g != prev_game:
            if g != prev_game + 1 or p != 1: issue('error', n, 'game', 'Games must start at 1 and advance by one; each game starts at point 1.')
            if prev_game and not ended: issue('error', n, 'game', 'Previous game ended before 11 points and a two-point lead.')
            a, b, prev_point, first_server = 0, 0, 0, r.get('server')
        elif ended: issue('error', n, 'game', 'Point recorded after this game was won.')
        if p != prev_point + 1: issue('error', n, 'point', 'Points must be contiguous and ordered within each game.')
        total = a+b
        switch = (total//2) % 2 if total < 20 else (10 + total-20) % 2
        expected = first_server if not switch else ('B' if first_server == 'A' else 'A')
        if r.get('server') != expected: issue('error', n, 'server', 'Service order must alternate every two points, then every point at deuce.')
        a += r.get('winner') == 'A'; b += r.get('winner') == 'B'
        if (integers['score_a'], integers['score_b']) != (a,b): issue('error', n, 'score_a/score_b', 'Post-point score does not follow the recorded winner.')
        prev_game, prev_point = g,p
    if rows and not (max(a,b)>=11 and abs(a-b)>=2): issue('warning', len(rows)+1, 'game', 'Final game is incomplete; analysis describes recorded points only.')
    for f in ['rally_length', 'third_ball_attack', 'serve_placement', 'serve_type', 'receive_type', 'point_phase', 'outcome']:
        missing = sum(not r.get(f) for r in rows)
        if missing: issue('warning', None, f, f'{missing} points lack this optional field; associated metrics use annotated points only.')
    return rows, dict(valid=not any(i['level']=='error' for i in issues), issues=issues, row_count=len(rows))

def rate(rows, predicate):
    n = len(rows)
    return dict(value=round(100*sum(predicate(r) for r in rows)/n,2) if n else None, numerator=sum(predicate(r) for r in rows), denominator=n, status='ok' if n else 'insufficient data')

def groups(rows, field, player):
    return {v: rate([r for r in rows if r.get(field)==v], lambda r:r['winner']==player) for v in sorted({r[field] for r in rows if r.get(field)})}

def analyze(rows):
    players = {}
    for player in ['A','B']:
        serves = [r for r in rows if r['server']==player]
        receives = [r for r in rows if r['server']!=player]
        annotated = [r for r in serves if r.get('third_ball_attack') in {'yes','no'}]
        attacks = [r for r in annotated if r['third_ball_attack']=='yes']
        lengths = [int(r['rally_length']) for r in rows if r.get('rally_length')]
        players[player] = dict(points_won=rate(rows,lambda r:r['winner']==player), serve_win=rate(serves,lambda r:r['winner']==player), receive_win=rate(receives,lambda r:r['winner']==player), third_ball_attack=rate(annotated,lambda r:r['third_ball_attack']=='yes'), third_ball_win=rate(attacks,lambda r:r['winner']==player), average_rally=dict(value=round(sum(lengths)/len(lengths),2) if lengths else None, denominator=len(lengths), status='ok' if lengths else 'insufficient data'), rally_bands={label: rate([r for r in rows if r.get('rally_length')],lambda r,lo=lo,hi=hi:lo<=int(r['rally_length'])<=hi) for label,lo,hi in [('short',1,4),('medium',5,8),('long',9,1000000)]}, by_serve_placement=groups(serves,'serve_placement',player), by_serve_type=groups(serves,'serve_type',player), by_receive_type=groups(receives,'receive_type',player), by_phase=groups(rows,'point_phase',player), by_server=groups(rows,'server',player), by_receiver={p:rate([r for r in rows if r['server']!=p],lambda r:r['winner']==player) for p in ['A','B']}, outcomes=dict(Counter(r.get('outcome') for r in rows if r['winner']==player and r.get('outcome'))))
    runs=[]
    for index,r in enumerate(rows):
        if runs and runs[-1]['player']==r['winner'] and runs[-1]['game']==r['game']:
            runs[-1]['length']+=1; runs[-1]['end']=index+1
        else: runs.append(dict(player=r['winner'],game=r['game'],length=1,start=index+1,end=index+1))
    insights=[]
    for p,m in players.items():
        for metric in ['serve_win','receive_win','third_ball_win']:
            s=m[metric]
            if s['denominator']:
                insights.append(dict(player=p,kind='FACT',statement=f'{metric.replace("_"," ").capitalize()}: {s["value"]}%', evidence=f'{s["numerator"]}/{s["denominator"]} recorded opportunities',metric=metric,reliability='descriptive only' if s['denominator']>=20 else 'small sample',interpretation=None))
        if m['third_ball_attack']['denominator']>=10 and m['third_ball_attack']['value']>=60 and m['third_ball_win']['value'] is not None and m['third_ball_win']['value']<50:
            insights.append(dict(player=p,kind='INTERPRETATION',statement='Frequent third-ball attacks had fewer than half their points won.',evidence=f'Attack rate {m["third_ball_attack"]["value"]}%; point conversion {m["third_ball_win"]["numerator"]}/{m["third_ball_win"]["denominator"]}.',metric='third_ball_win',reliability='exploratory; no causal claim',interpretation='Review these annotated points with your teammate.'))
    return dict(analytics_version=ANALYTICS_VERSION,schema_version=SCHEMA_VERSION,point_count=len(rows),players=players,progression=[dict(index=i+1,game=r['game'],a=int(r['score_a']),b=int(r['score_b']),winner=r['winner']) for i,r in enumerate(rows)],runs=runs,insights=insights)
