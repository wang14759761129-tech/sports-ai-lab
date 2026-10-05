"""Freeze a rally-disjoint holdout before inspecting any new GT or predictions."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.download_vision_sample import download
from vision.config import VisionConfig, DATA_REVISION


def make_split(development,official_split,count=5):
    excluded=set(development);selected=[];seen=set()
    for match,rally in official_split:
        source=f'tabletennis/{match}/{rally}'
        if source not in excluded and match not in seen:
            selected.append(source);seen.add(match)
        if len(selected)==count: break
    if len(selected)!=count: raise ValueError('Not enough distinct matches for holdout')
    return {'dataset_revision':DATA_REVISION,'development':development,'holdout':selected,
            'selection_policy':'First unseen official test rally per match; no GT or prediction inspected for selection',
            'independence_limit':'Rally-disjoint, not match-disjoint: these test matches also appear in development'}


if __name__=='__main__':
    config=VisionConfig.load();path=config.dataset_root/'balltrack-split-v1.json'
    development=json.loads((config.dataset_root/'benchmark-suite-manifest.json').read_text())['source_ids']
    split=make_split(development,json.loads((config.dataset_root/'tabletennis/info/test.json').read_text()))
    if path.exists() and json.loads(path.read_text())!=split: raise RuntimeError('Refusing to replace a frozen split')
    path.write_text(json.dumps(split,indent=2),encoding='utf-8')
    print(json.dumps(split,indent=2),flush=True)
    for source in split['holdout']:
        _,match,rally=source.split('/')
        for relative in (f'tabletennis/videos/{match}_{rally}.mp4',f'tabletennis/all/{match}/csv/{rally}_ball.csv'):
            download('linfeng302/RacketVision','datasets',DATA_REVISION,relative,config.dataset_root/relative)
