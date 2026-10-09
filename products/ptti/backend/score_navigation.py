"""Manual score index over existing points and evidence playlists; no inference/GT."""
import csv
import html
import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.video_evidence import utc_now


class ScoreTimestampEvidenceInput(BaseModel):
    source: Literal['USER_MARKED_PLAYHEAD', 'USER_ENTERED_TIME', 'USER_CONFIRMED_EXISTING_VALUE']
    verification_status: Literal['REVIEW_REQUIRED', 'CONFIRMED']


class ScoreMomentInput(BaseModel):
    video_asset_id: str
    game_number: int = Field(ge=1, le=20)
    point_number: int = Field(ge=1)
    score_a_before: int | None = Field(default=None, ge=0, le=200)
    score_b_before: int | None = Field(default=None, ge=0, le=200)
    point_start_ms: int | None = Field(default=None, ge=0)
    point_end_ms: int | None = Field(default=None, gt=0)
    score_display_ms: int | None = Field(default=None, ge=0)
    field_evidence: dict[str, "ScoreTimestampEvidenceInput"] = Field(default_factory=dict)
    player_a_id: str = 'UNKNOWN'
    player_b_id: str = 'UNKNOWN'
    games_a_before: int | None = Field(default=None, ge=0, le=7)
    games_b_before: int | None = Field(default=None, ge=0, le=7)
    match_best_of: int | None = Field(default=None, ge=1, le=9)
    server_id: Literal['A', 'B', 'UNKNOWN'] = 'UNKNOWN'
    point_winner_id: Literal['A', 'B', 'UNKNOWN'] = 'UNKNOWN'
    verification_status: Literal['REVIEW_REQUIRED', 'CONFIRMED', 'REJECTED'] = 'REVIEW_REQUIRED'
    notes: str = Field(default='', max_length=10000)
    # Client generates once per draft; repeated submissions cannot duplicate a point.
    request_id: str = Field(min_length=1, max_length=100)
    expected_updated_at: str | None = None


def score_flags(a, b, games_a=None, games_b=None, best_of=None):
    def wins(x, y):
        return x >= 11 and x - y >= 2
    game_a = not wins(a, b) and not wins(b, a) and wins(a + 1, b)
    game_b = not wins(a, b) and not wins(b, a) and wins(b + 1, a)
    match_a = None if games_a is None or games_b is None or best_of is None else game_a and games_a + 1 >= best_of // 2 + 1 and games_b < best_of // 2 + 1
    match_b = None if games_a is None or games_b is None or best_of is None else game_b and games_b + 1 >= best_of // 2 + 1 and games_a < best_of // 2 + 1
    return {'game_point_a': game_a,
            'game_point_b': game_b,
            'deuce': a >= 10 and b >= 10 and a == b,
            'game_already_over': wins(a, b) or wins(b, a),
            'match_point_a': match_a, 'match_point_b': match_b,
            'match_point': 'UNKNOWN' if match_a is None else bool(match_a or match_b)}


def score_router(store):
    router = APIRouter(prefix='/scores')

    def rows():
        return [r for r in store.points() if r.get('schema') == 'SCORE_MOMENT_V1']

    @router.get('')
    def query(video_id: str | None = None, athlete_id: str | None = None,
              match_id: str | None = None, game: int | None = None,
              score_a: int | None = None, score_b: int | None = None,
              event: str | None = None, year: int | None = None,
              critical: Literal['GAME_POINT', 'DEUCE', 'MATCH_POINT'] | None = None,
              status: Literal['CONFIRMED', 'REVIEW_REQUIRED', 'REJECTED'] | None = None):
        result = []
        for row in rows():
            if video_id and row['video_id'] != video_id: continue
            if match_id and row['match_id'] != match_id: continue
            if athlete_id and athlete_id not in [row['player_a_id'], row['player_b_id']]: continue
            match = store.repo.get_professional_match(row['match_id']) if row.get('match_id') else None
            if event and (not match or event.casefold() not in match.get('event_name', '').casefold()): continue
            if year is not None and (not match or not str(match.get('event_date') or '').startswith(str(year))): continue
            if game is not None and row['game_number'] != game: continue
            if score_a is not None and row['score_a_before'] != score_a: continue
            if score_b is not None and row['score_b_before'] != score_b: continue
            if status and row['verification_status'] != status: continue
            flags = score_flags(row['score_a_before'], row['score_b_before'], row.get('games_a_before'),
                                row.get('games_b_before'), row.get('match_best_of')) if row['score_a_before'] is not None and row['score_b_before'] is not None else None
            if critical == 'GAME_POINT' and (not flags or not (flags['game_point_a'] or flags['game_point_b'])): continue
            if critical == 'DEUCE' and (not flags or not flags['deuce']): continue
            if critical == 'MATCH_POINT' and (not flags or flags['match_point'] != True): continue
            video = store.get('evidence_videos', 'video_id', row['video_id'])
            result.append({**row, 'flags': flags, 'video_title': video['title'],
                           'availability_status': store.availability(video)['availability_status']})
        return sorted(result, key=lambda r: (
            r['video_id'], r['game_number'],
            r['point_start_ms'] is None, r['point_start_ms'] or 0,
        ))

    def persist(value, identity=None):
        video = store.get('evidence_videos', 'video_id', value.video_asset_id)
        if not video.get('source_sha256') or video.get('hash_status') != 'VERIFIED':
            raise HTTPException(400, '请等待视频完整 SHA256 校验完成后建立比分索引')
        if store.availability(video)['availability_status'] != 'AVAILABLE':
            raise HTTPException(400, '原视频不可用，请先重新关联')
        has_bounds = value.point_start_ms is not None and value.point_end_ms is not None
        if value.verification_status == 'CONFIRMED' and (not has_bounds or value.score_a_before is None or value.score_b_before is None):
            raise HTTPException(400, '确认前请填写比分并标记本分完整起止范围')
        timestamp_values = {
            'point_start_ms': value.point_start_ms,
            'point_end_ms': value.point_end_ms,
            'score_display_ms': value.score_display_ms,
        }
        if any(timestamp is not None and timestamp > video['duration_ms']
               for timestamp in timestamp_values.values()):
            raise HTTPException(400, '时间标记必须位于视频范围内')
        if has_bounds and not value.point_start_ms < value.point_end_ms:
            raise HTTPException(400, '本分起止时间必须位于视频内')
        allowed_time_fields = set(timestamp_values)
        if set(value.field_evidence) - allowed_time_fields:
            raise HTTPException(400, '只有视频时间字段可以保存独立时间证据')
        if any(timestamp_values[field] is None for field in value.field_evidence):
            raise HTTPException(400, '已清空的时间字段不能保留确认状态')
        if value.match_best_of is not None and value.match_best_of % 2 == 0:
            raise HTTPException(400, '比赛局制必须是奇数局')
        if (value.games_a_before is None) != (value.games_b_before is None):
            raise HTTPException(400, '赛前局分必须同时填写，或都保留未知')
        if value.score_a_before is not None and value.score_b_before is not None and score_flags(value.score_a_before, value.score_b_before)['game_already_over']:
            raise HTTPException(400, '这个分前比分已经结束本局，请核对局数与比分')
        allowed = set(video.get('athlete_ids') or []) | {'UNKNOWN'}
        if value.player_a_id not in allowed or value.player_b_id not in allowed:
            raise HTTPException(400, '球员必须来自已确认的视频比赛关联；未知请保留 UNKNOWN')
        body = value.model_dump(exclude={'expected_updated_at'})
        with store.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            all_rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM evidence_points')]
            for r in all_rows:
                if r.get('request_id') == value.request_id:
                    if r.get('submitted_body') != body:
                        raise HTTPException(409, '请求编号已使用，请重新打开记录后修改')
                    return r
            old = next((r for r in all_rows if r['point_id'] == identity), None) if identity else None
            if identity and (not old or old.get('schema') != 'SCORE_MOMENT_V1'):
                raise HTTPException(404, '比分索引不存在')
            if old and (old['video_id'] != value.video_asset_id or old['updated_at'] != value.expected_updated_at):
                raise HTTPException(409, '记录已被更新或视频身份改变，请重新加载')
            if any(r.get('schema') == 'SCORE_MOMENT_V1' and r.get('video_id') == video['video_id']
                   and r.get('game_number') == value.game_number and r.get('point_number') == value.point_number
                   and r.get('point_id') != identity for r in all_rows):
                raise HTTPException(409, '本局这个分序号已存在，请打开原记录修改')
            if value.point_number > 1:
                previous = [r for r in all_rows if r.get('schema') == 'SCORE_MOMENT_V1'
                            and r.get('video_id') == video['video_id'] and r.get('game_number') == value.game_number
                            and r.get('point_number') == value.point_number - 1 and r.get('verification_status') == 'CONFIRMED']
                if previous and value.point_winner_id == 'UNKNOWN' and value.score_a_before is not None:
                    prev = previous[0]
                    if prev.get('point_winner_id') in {'A', 'B'} and prev.get('score_a_before') is not None and prev.get('score_b_before') is not None:
                        proposed = (prev['score_a_before'] + (prev['point_winner_id'] == 'A'),
                                    prev['score_b_before'] + (prev['point_winner_id'] == 'B'))
                        if proposed != (value.score_a_before, value.score_b_before):
                            raise HTTPException(409, '上一分的人工确认得分方与本分比分不一致，请核对或保留未知')
            now = utc_now()
            field_evidence = {}
            previous_evidence = (old or {}).get('field_evidence') or {}
            submitted_evidence = body.get('field_evidence') or {}
            for field, timestamp in timestamp_values.items():
                if timestamp is None:
                    continue
                incoming = submitted_evidence.get(field)
                previous = previous_evidence.get(field)
                same_value = old is not None and old.get(field) == timestamp
                if incoming is None and same_value and previous:
                    # Keep an existing field review intact when editing an unrelated field.
                    field_evidence[field] = previous
                    continue
                source = incoming['source'] if incoming else 'USER_ENTERED_TIME'
                status = incoming['verification_status'] if incoming else 'REVIEW_REQUIRED'
                if value.verification_status == 'CONFIRMED' and field in {'point_start_ms', 'point_end_ms'}:
                    # The explicit whole-point confirmation also confirms the two required boundaries.
                    status = 'CONFIRMED'
                if old is not None and not same_value and status == 'CONFIRMED':
                    # A moved timestamp needs fresh review even if a stale client submits a confirmed flag.
                    status = ('CONFIRMED' if value.verification_status == 'CONFIRMED'
                              else 'REVIEW_REQUIRED')
                if same_value and previous and incoming == {
                        'source': previous.get('source'),
                        'verification_status': previous.get('verification_status')}:
                    field_evidence[field] = previous
                    continue
                field_evidence[field] = {
                    'source': source,
                    'verification_status': status,
                    'value_ms': timestamp,
                    'source_video_sha256': video['source_sha256'],
                    'recorded_at': now,
                }
            body['field_evidence'] = submitted_evidence
            row = {**body, 'schema': 'SCORE_MOMENT_V1', 'point_id': identity or str(uuid.uuid4()),
                   'video_id': video['video_id'], 'video_sha256': video['source_sha256'],
                   'match_id': video.get('match_id'), 'start_ms': value.point_start_ms,
                   'end_ms': value.point_end_ms, 'score_a': value.score_a_before,
                   'score_b': value.score_b_before, 'tags': [], 'evidence_ids': [],
                   'source': 'MANUAL_SCORE_INDEX', 'created_at': old['created_at'] if old else now,
                   'updated_at': now, 'submitted_body': body,
                   'field_evidence': field_evidence,
                   'correction_history': [*(old or {}).get('correction_history', []),
                                          {'recorded_at': now, 'action': 'CREATE' if old is None else 'EDIT',
                                           'before': old, 'after': body}],
            'provenance': {'timestamp_basis': 'USER_MARKED_VIDEO_TIME',
                                  'score_semantics': 'BEFORE_POINT', 'automatically_verified': False}}
            db.execute('INSERT INTO evidence_points VALUES (?,?) ON CONFLICT(point_id) DO UPDATE SET payload=excluded.payload',
                       (row['point_id'], json.dumps(row, ensure_ascii=False)))
            db.execute('INSERT INTO evidence_audit VALUES (?,?,?,?,?)',
                       (str(uuid.uuid4()), row['point_id'], 'SCORE_MOMENT_SAVE', now,
                        json.dumps({'before': old, 'after': row}, ensure_ascii=False)))
        return row

    @router.post('')
    def create(value: ScoreMomentInput):
        row = persist(value)
        flags = score_flags(row['score_a_before'], row['score_b_before'], row.get('games_a_before'),
                            row.get('games_b_before'), row.get('match_best_of')) if row['score_a_before'] is not None and row['score_b_before'] is not None else None
        return {**row, 'flags': flags}

    @router.put('/{identity}')
    def edit(identity: str, value: ScoreMomentInput):
        row = persist(value, identity)
        flags = score_flags(row['score_a_before'], row['score_b_before'], row.get('games_a_before'),
                            row.get('games_b_before'), row.get('match_best_of')) if row['score_a_before'] is not None and row['score_b_before'] is not None else None
        return {**row, 'flags': flags}

    @router.delete('/{identity}')
    def delete_draft(identity: str):
        with store.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            found = db.execute('SELECT payload FROM evidence_points WHERE point_id=?', (identity,)).fetchone()
            if not found:
                raise HTTPException(404, '比分索引不存在')
            row = json.loads(found[0])
            if row.get('schema') != 'SCORE_MOMENT_V1' or row.get('verification_status') != 'REVIEW_REQUIRED':
                raise HTTPException(409, '只有待确认草稿可以删除；已确认记录请保留并更正')
            now = utc_now()
            db.execute('DELETE FROM evidence_points WHERE point_id=?', (identity,))
            db.execute('INSERT INTO evidence_audit VALUES (?,?,?,?,?)',
                       (str(uuid.uuid4()), identity, 'DELETE_SCORE_DRAFT', now,
                        json.dumps({'before': row, 'after': None}, ensure_ascii=False)))
        return {'deleted': True}

    @router.get('/{identity}/history')
    def history(identity: str):
        store.get('evidence_points', 'point_id', identity)
        with store.repo.connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM evidence_audit WHERE entity_id=? ORDER BY rowid', (identity,))]

    @router.post('/{identity}/undo')
    def undo(identity: str):
        old = store.get('evidence_points', 'point_id', identity)
        history = old.get('correction_history') or []
        if old.get('schema') != 'SCORE_MOMENT_V1' or len(history) < 2:
            raise HTTPException(409, '没有可撤销的比分修改')
        prior = history[-2].get('after')
        if not prior:
            raise HTTPException(409, '找不到上一版比分记录')
        value = ScoreMomentInput(**{**prior, 'request_id': str(uuid.uuid4()),
                                    'expected_updated_at': old['updated_at']})
        value.verification_status = old['verification_status']
        restored = persist(value, identity)
        # Keep a distinct undo audit entry while preserving append-only history.
        with store.repo.connect() as db:
            db.execute('INSERT INTO evidence_audit VALUES (?,?,?,?,?)',
                       (str(uuid.uuid4()), identity, 'SCORE_MOMENT_UNDO', utc_now(),
                        json.dumps({'restored_from': history[-2], 'current': old}, ensure_ascii=False)))
        return restored

    @router.get('/export')
    def export(format: Literal['json', 'html', 'csv'] = 'json', video_id: str | None = None,
               athlete_id: str | None = None, match_id: str | None = None,
               game: int | None = None, score_a: int | None = None,
               score_b: int | None = None, event: str | None = None, year: int | None = None,
               status: Literal['CONFIRMED', 'REVIEW_REQUIRED', 'REJECTED'] | None = None):
        data = query(video_id, athlete_id, match_id, game, score_a, score_b, event, year, None, status)
        if format == 'json':
            content = json.dumps({'schema': 'PTTI_SCORE_MOMENTS_V1', 'items': data}, ensure_ascii=False, indent=2)
            return Response(content, media_type='application/json; charset=utf-8')
        fields = ['video_title', 'game_number', 'point_number', 'score_a_before', 'score_b_before',
                  'point_start_ms', 'score_display_ms', 'point_end_ms', 'point_winner_id',
                  'verification_status', 'video_sha256', 'source']
        if format == 'csv':
            from backend.video_evidence import _spreadsheet_text
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            for item in data:
                writer.writerow({k: _spreadsheet_text(item.get(k)) for k in fields})
            return Response('\ufeff' + buffer.getvalue(), media_type='text/csv; charset=utf-8')
        esc = lambda value: html.escape('' if value is None else str(value))
        body = ''.join('<tr>' + ''.join(f'<td>{esc(row.get(k))}</td>' for k in fields) + '</tr>' for row in data)
        labels = ''.join(f'<th>{esc(k)}</th>' for k in fields)
        return Response(f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>PTTI 比分复盘索引</title>"
                        f"<h1>比分复盘索引</h1><p>所有记录均保留来源与确认状态；赛点需要赛制与局分。</p>"
                        f"<table><thead><tr>{labels}</tr></thead><tbody>{body}</tbody></table></html>",
                        media_type='text/html; charset=utf-8')

    @router.post('/playlist')
    def playlist(identities: list[str]):
        selected = [store.get('evidence_points', 'point_id', x) for x in dict.fromkeys(identities)]
        if not selected or len(selected) > 500:
            raise HTTPException(400, '请选择 1–500 个比分片段')
        for row in selected:
            if row.get('schema') != 'SCORE_MOMENT_V1' or row.get('verification_status') != 'CONFIRMED':
                raise HTTPException(400, '连续复盘仅使用人工已确认的比分索引')
            if row.get('point_start_ms') is None or row.get('point_end_ms') is None:
                raise HTTPException(400, '该记录缺少已确认的视频片段边界')
            video = store.get('evidence_videos', 'video_id', row['video_id'])
            if video.get('source_sha256') != row.get('video_sha256') or store.availability(video)['availability_status'] != 'AVAILABLE':
                raise HTTPException(409, '原视频身份不匹配或当前不可用')
        ids = []
        for row in selected:
            # Stable reference: index edits do not generate duplicate playlist clips.
            key = 'score:' + row['point_id']
            clip = {'evidence_id': key, 'video_id': row['video_id'], 'start_ms': row['point_start_ms'],
                    'end_ms': row['point_end_ms'], 'representative_ms': row['point_start_ms'],
                    'tags': ['比分复盘'], 'notes': f"第{row['game_number']}局 {row['score_a_before']}:{row['score_b_before']}",
                    'event_type': 'MANUAL_SCORE_SEGMENT', 'source': 'MANUAL_CONFIRMED',
                    'review_status': 'CONFIRMED', 'score_moment_id': row['point_id'],
                    'video_sha256': row['video_sha256']}
            try:
                store.get('video_evidence', 'evidence_id', key)
            except HTTPException:
                store.save('video_evidence', 'evidence_id', clip, 'SCORE_PLAYLIST_REFERENCE')
            ids.append(key)
        return {'evidence_ids': ids}

    return router
