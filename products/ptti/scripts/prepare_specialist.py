"""Bounded specialist pilot data; no database access or final-test inspection."""
import json,sys,urllib.request,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vision.config import VisionConfig,DATA_REVISION
from vision.specialist import validate_split,sha256
from scripts.download_vision_sample import download,tree_entry
ROOT=Path(__file__).resolve().parents[1];HOME=ROOT/'outputs/vision/specialist_v1'
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2),encoding='utf-8')
def main():
    cfg=VisionConfig.load();roles={}
    for split in ['train','val']:
        path=cfg.dataset_root/f'tabletennis/info/{split}.json'
        download('linfeng302/RacketVision','datasets',DATA_REVISION,f'tabletennis/info/{split}.json',path)
        roles[split]=json.loads(path.read_text())
    manifest=dict(dataset_revision=DATA_REVISION,train=[],dev=[],known_evaluation=[],final_test=[],final_test_status='NOT_SELECTED_UNTIL_ACCEPTED_CANDIDATE_FREEZE',
                  scope='BOUNDED_PILOT: first two official training rallies in eight matches; first available validation rallies in four disjoint matches',
                  original_model_exposure='Official parent has trained/validated on these official matches; no claim of model-unseen generalization')
    for role,split,ids in [('train','train',range(20,28)),('dev','val',range(28,32))]:
        for m in ids:
            manifest[role]+=['tabletennis/'+match+'/'+r for match,r in roles[split] if match==f'match{m}'][:2]
    prior=json.loads((ROOT/'configs/balltrack-tracker-v2/dataset_manifest.json').read_text())
    manifest['known_evaluation']=prior['development']+prior['internal_holdout']+prior['cross_match_holdout']
    manifest['parent_exposed_match_ids']=sorted({m for split in roles.values() for m,r in split}|{m for m,r in json.loads((cfg.dataset_root/'tabletennis/info/test.json').read_text())})
    validate_split(manifest)
    path=HOME/'split.json'
    if path.exists() and json.loads(path.read_text())!=manifest:raise ValueError('Existing split frozen')
    write(path,manifest)
    from concurrent.futures import ThreadPoolExecutor
    def fetch(source):
        records=[]
        _,m,r=source.split('/')
        for rel in [f'tabletennis/videos/{m}_{r}.mp4',f'tabletennis/all/{m}/csv/{r}_ball.csv']:
            destination=cfg.dataset_root/rel;download('linfeng302/RacketVision','datasets',DATA_REVISION,rel,destination)
            entry=tree_entry('linfeng302/RacketVision','datasets',DATA_REVISION,rel);data=destination.read_bytes()
            if not entry.get('lfs') and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=entry['oid']:raise ValueError('Official blob mismatch')
            records.append(dict(path=rel,sha256=sha256(destination),size=len(data)))
        return records
    with ThreadPoolExecutor(max_workers=4) as pool:
        inputs=[record for result in pool.map(fetch,manifest['train']+manifest['dev']) for record in result]
    write(HOME/'input_manifest.json',inputs)
    print('Frozen pilot:',len(manifest['train']),'train clips /',len(manifest['dev']),'dev clips; final test untouched/unselected',flush=True)
if __name__=='__main__':main()
