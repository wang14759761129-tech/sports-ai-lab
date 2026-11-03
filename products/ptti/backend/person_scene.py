"""Read-only raw scene artifacts with separately persisted human review."""
from __future__ import annotations
import copy
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from backend.person_detector import (R18_MODEL,R18_REVISION,R18_FILES,FROZEN_MANIFEST_SHA,
                                     file_sha,person_frame_review)

_REVIEW_LOCK=threading.RLock()
ROLES={'NEAR_PLAYER','FAR_PLAYER','REFEREE','OTHER','UNKNOWN'}


def scene_snapshot(root: Path, *, reviews_path:Path|None=None):
    report_path=root/'person_detector_evaluation.json'
    if not report_path.is_file():
        return {'status':'NOT_RUN','frames':[],'message':'人物识别尚未运行；已有球台研究结果仍可查看。'}
    report=json.loads(report_path.read_text(encoding='utf-8'))
    config_path=root/'person_detector_config.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))
    if (report.get('config_sha256')!=file_sha(config_path) or config.get('model')!=R18_MODEL
        or config.get('revision')!=R18_REVISION or config.get('artifact_sha256')!=R18_FILES
        or report.get('manifest_sha256')!=FROZEN_MANIFEST_SHA):
        raise ValueError('PERSON_RESULT_CONFIG_IDENTITY_MISMATCH')
    reviews_path=reviews_path or root/'person_detector_reviews.json'
    reviews=json.loads(reviews_path.read_text(encoding='utf-8')) if reviews_path.is_file() else []
    frames=[]
    for source,records in [('development',report.get('frames',[]))]:
        for raw in records:
            frames.append({**copy.deepcopy(raw),'frame_id':f"dev-{raw['game']}-s{raw['slot']}",
                           'sample_set':source,'image_asset':f"dev-{raw['game']}-s{raw['slot']:02d}.jpg"})
    validation_path=root/'person-validation/person_detector_validation_results.json'
    validation=None;validation_metrics=None
    if validation_path.is_file():
        validation=json.loads(validation_path.read_text(encoding='utf-8'))
        if validation.get('config_sha256')!=report['config_sha256']:
            raise ValueError('VALIDATION_CONFIG_MISMATCH')
        for raw in validation.get('frames',[]):
            frames.append({**copy.deepcopy(raw),'frame_id':f"val-{raw['game']}-s{raw['slot']}",
                           'sample_set':'validation','image_asset':f"val-{raw['game']}-s{raw['slot']:02d}.jpg"})
        metrics_path=root/'person-validation/person_detector_validation_metrics.json'
        if metrics_path.is_file():
            validation_metrics=json.loads(metrics_path.read_text(encoding='utf-8'))
            if validation_metrics.get('config_sha256')!=report['config_sha256']:
                raise ValueError('VALIDATION_METRICS_CONFIG_MISMATCH')
    for frame in frames:
        verified=False
        for event in reviews:
            if (event.get('frame_id')!=frame['frame_id'] or event.get('config_sha256')!=report['config_sha256']
                or event.get('frame_sha256')!=frame.get('frame_sha256')):continue
            if event['action']=='ACCEPT_FRAME':verified=True;continue
            candidate=next((p for p in frame['detections'] if p['candidate_id']==event.get('candidate_id')),None)
            if candidate:
                verified=False
                candidate['user_correction']={'action':event['action'],'role':event.get('role'),
                                              'status':'REJECTED' if event['action']=='REJECT' else 'CORRECTED'}
        effective=[]
        for p in frame['detections']:
            c=p.get('user_correction') or {}
            p['effective_role']=c.get('role') if c.get('status')=='CORRECTED' else p.get('role_candidate','UNKNOWN')
            if c.get('status')!='REJECTED':effective.append({**p,'role_candidate':p['effective_role']})
        frame['review']=person_frame_review(effective,table_present=bool(frame.get('table_bbox')))
        if verified:frame['review']={**frame['review'],'priority':'LOW','status':'USER_VERIFIED'}
    return {'status':'REAL_RESEARCH_PREVIEW','model':report['model'],'person_gate':'PERSON_DETECTOR_PARTIAL',
            'scene_gate':'SCENE_BOOTSTRAP_PARTIAL','independent_human_verified':False,
            'development':{k:report.get(k) for k in ('r18','grounding_dino_remeasured','per_game','threshold_protocol','gt_status')},
            'validation':{k:validation.get(k) for k in ('status','summary','per_match','independent_human_gt')} if validation else None,
            'validation_metrics':validation_metrics,'runtime':report['runtime'],'provenance':report['provenance'],
            'config_sha256':report['config_sha256'],'frames':frames,'reviews_count':len(reviews),
            'review_required':sum(f['review']['priority']=='HIGH' for f in frames),
            'user_verified':sum(f['review']['status']=='USER_VERIFIED' for f in frames),
            'limitations':['研究帧结果；逐帧标注为视觉复核草稿，尚未经独立人工确认。',
                           '近远端是画面位置候选，复杂背景与正面机位仍需人工指定。',
                           '样本未随软件分发；记分牌尚未实现。']}


def record_review(root:Path, *, frame_id,action,candidate_id=None,role=None,reviews_path:Path|None=None,source='USER_UI'):
    if action not in {'ACCEPT_FRAME','SET_ROLE','REJECT'} or (action=='SET_ROLE' and role not in ROLES):
        raise ValueError('INVALID_REVIEW_ACTION')
    with _REVIEW_LOCK:
        snapshot=scene_snapshot(root,reviews_path=reviews_path)
        frame=next((f for f in snapshot['frames'] if f['frame_id']==frame_id),None)
        if not frame:raise KeyError('FRAME_NOT_FOUND')
        if action!='ACCEPT_FRAME' and not any(p['candidate_id']==candidate_id for p in frame['detections']):
            raise KeyError('DETECTION_NOT_FOUND')
        event={'review_id':str(uuid.uuid4()),'frame_id':frame_id,'candidate_id':candidate_id,
               'action':action,'role':role,'config_sha256':snapshot['config_sha256'],
               'frame_sha256':frame['frame_sha256'],'recorded_at':datetime.now(timezone.utc).isoformat(),
               'source':source}
        path=reviews_path or root/'person_detector_reviews.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        events=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        events.append(event)
        temporary=path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
        return {'status':'SAVED','raw_preserved':True,'review':event}


def scene_asset(root:Path,name:str):
    dev=re.fullmatch(r'dev-(game_[1-5])-s(0[1-4])\.jpg',name)
    val=re.fullmatch(r'val-(match\d+)-s(0[1-4])\.jpg',name)
    if dev:return root/'multi-match-frames'/dev[1]/f'sample-{dev[2]}.jpg'
    if val:return root/'person-validation'/f'{val[1]}-s{val[2]}.jpg'
    raise ValueError('INVALID_ASSET_NAME')
