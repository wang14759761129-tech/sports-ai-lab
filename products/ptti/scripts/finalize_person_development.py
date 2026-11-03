"""Limited development threshold comparison; lock before unseen-source run."""
import json
import os
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.person_detector import (FROZEN_MANIFEST_SHA, R18_MODEL, R18_REVISION, R18_FILES,
    deduplicate_people, evaluate_people, TablePersonRoleResolver, person_frame_review, file_sha, box_iou)


def summarize(rows):
    all_iou=[v for r in rows for v in r['evaluation']['matched_ious']]
    visible=sum(r['evaluation']['gt_players'] for r in rows)
    both=sum(r['evaluation']['both_visible'] for r in rows)
    matched=sum(r['evaluation']['matched_players'] for r in rows)
    pairs=sum(r['evaluation']['both_matched'] for r in rows)
    proposed=0;correct=0;ref_confused=0
    for row in rows:
        for i,p in enumerate(row['detections']):
            if p.get('role_candidate') in {'NEAR_PLAYER','FAR_PLAYER'}:
                proposed+=1
                correct+=i in row['evaluation']['matched_prediction_indexes']
                ref_confused+=any(box_iou(p['bbox'],b)>=.3
                                 for b in row['annotation'].get('referees',[]))
    return {'sampled_frames':len(rows),'gt_visible_players':visible,'matched_players':matched,
            'visible_player_recall_percent':round(100*matched/visible,2) if visible else None,
            'gt_both_visible_frames':both,'both_matched_frames':pairs,
            'both_visible_recall_percent':round(100*pairs/both,2) if both else None,
            'all_frame_both_coverage_percent':round(100*pairs/len(rows),2),
            'mean_matched_iou':mean(all_iou) if all_iou else None,
            'non_player_person_candidates':sum(r['evaluation']['non_player_detections'] for r in rows),
            'referee_person_detections':sum(r['evaluation']['referee_detections'] for r in rows),
            'player_role_proposals':proposed,'player_role_precision_proxy':correct/proposed if proposed else None,
            'referee_as_player_proposals':ref_confused,
            'review_required_frames':sum(r['review']['priority']=='HIGH' for r in rows),
            'near_far_recall':None,'near_far_note':'physical depth not established; image-footpoint roles are unverified proxies'}


def main():
    root=Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev/vision-v2/scene-bootstrap'
    raw=json.loads((root/'person_detector_r18_raw.json').read_text())
    gt=json.loads((root/'person_detector_dev_gt.json').read_text())
    manifest=json.loads((root/'scene_bootstrap_eval_manifest.json').read_text())
    if file_sha(root/'scene_bootstrap_eval_manifest.json')!=FROZEN_MANIFEST_SHA:
        raise RuntimeError('FROZEN_MANIFEST_CHANGED')
    if raw['manifest_sha256']!=FROZEN_MANIFEST_SHA or gt['manifest_sha256']!=FROZEN_MANIFEST_SHA:
        raise RuntimeError('INPUT_MANIFEST_MISMATCH')
    annotations={(r['game'],r['slot']):r for r in gt['frames']}
    baseline={(r['game'],r['slot']):r for r in manifest['frame_results'] if r['prompt_id']=='official_bootstrap_a'}
    protocol=[];chosen=[];baseline_rows=[]
    for threshold in (.25,.4,.55):
        rows=[]
        for f in raw['frames']:
            key=(f['game'],f['slot']);b=baseline[key];g=annotations[key]
            if f['frame_sha256']!=g['frame_sha256']:
                raise RuntimeError('ANNOTATION_FRAME_MISMATCH')
            ps=deduplicate_people([p for p in f['raw_person_detections'] if p['detector_score']>=threshold])
            ps=TablePersonRoleResolver().resolve(b['selected_table_bbox'],ps,image_size=(f['width'],f['height']))
            rows.append({**f,'detections':ps,'table_bbox':b['selected_table_bbox'],
                         'annotation':g,'evaluation':evaluate_people(ps,g),
                         'review':person_frame_review(ps,table_present=b['table_found'])})
        protocol.append({'threshold':threshold,**summarize(rows)})
        if threshold==.4:chosen=rows
    for b in baseline.values():
        ps=deduplicate_people([p for p in b['detections'] if any(t in p['label'].lower() for t in ('person','player','athlete'))])
        ps=TablePersonRoleResolver().resolve(b['selected_table_bbox'],ps,image_size=(b['width'],b['height']))
        g=annotations[b['game'],b['slot']]
        baseline_rows.append({'detections':ps,'annotation':g,'evaluation':evaluate_people(ps,g),
                              'review':person_frame_review(ps,table_present=b['table_found'])})
    config={'model':R18_MODEL,'revision':R18_REVISION,'artifact_sha256':R18_FILES,'threshold':.4,
            'duplicate_iou':.7,'role_resolver':'table-side-footpoint-v1','role_score_margin':.15,
            'role_min_footpoint_gap_fraction':.02,'primary_eval_iou':.3,'secondary_eval_iou':.5,
            'development_manifest_sha256':FROZEN_MANIFEST_SHA,'threshold_search':[.25,.4,.55],
            'selection_reason':'0.4 preserves 30/30 approximate visible-player matches with fewer non-player candidates than 0.25; 0.55 loses clipped player',
            'validation_tuning':'FORBIDDEN','human_gt_status':'ASSISTANT_VISUAL_DRAFT_NOT_INDEPENDENT_HUMAN_GT'}
    config_path=root/'person_detector_config.json'
    if config_path.exists():raise RuntimeError('FROZEN_CONFIG_ALREADY_EXISTS')
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    report={'status':'REAL_DEV_EVALUATED','model':R18_MODEL,'person_gate':'PERSON_DETECTOR_PARTIAL',
            'scene_gate':'SCENE_BOOTSTRAP_PARTIAL','runtime':raw['runtime'],'provenance':raw['provenance'],
            'manifest_sha256':FROZEN_MANIFEST_SHA,'config_sha256':file_sha(config_path),
            'gt_sha256':file_sha(root/'person_detector_dev_gt.json'),'gt_status':gt['status'],
            'independent_human_verified':False,'threshold_protocol':protocol,
            'grounding_dino_remeasured':summarize(baseline_rows),'r18':summarize(chosen),
            'per_game':{},
            'validation':{'status':'NOT_RUN','required':'5 independent training-match sources; do not reuse these frames or test split'},
            'frames':chosen,'notes':['No claim of independent human GT or physical near/far accuracy',
                    'Referee detections are real people, not detector false positives; only referee-as-player is a role error',
                    'R18 is a preview research candidate, not a generalization-validated product default']}
    report['per_game']={game:summarize([r for r in chosen if r['game']==game]) for game in sorted({r['game'] for r in chosen})}
    report['secondary_iou_05']=summarize([{**r,'evaluation':evaluate_people(r['detections'],r['annotation'],iou_threshold=.5)} for r in chosen])
    (root/'person_detector_evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('grounding_dino_remeasured','r18','per_game','config_sha256')},indent=2))


if __name__=='__main__':main()
