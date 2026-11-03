"""Prepare a match-disjoint, diversified final BallTrack tuning set.

All source assets are pinned to the official RacketVision dataset revision and
verified against Hugging Face's LFS SHA256 or Git blob identity before use.
Outputs are isolated under outputs/vision/balltrack_final and ignored datasets.
"""
import hashlib, json, re, sys, time, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vision.config import VisionConfig, DATA_REVISION
from vision.specialist import validate_split,sha256

OUT=ROOT/'outputs/vision/balltrack_final'
SOURCE='linfeng302/RacketVision'

def get_json(url):
    with urllib.request.urlopen(url,timeout=30) as r:return json.load(r),r.headers.get('Link','')

def main():
    cfg=VisionConfig.load(); root=cfg.dataset_root; catalog_dir=OUT/'catalogs';catalog_dir.mkdir(parents=True,exist_ok=True)
    info={}
    for role in ['train','val','test']:
        p=root/f'tabletennis/info/{role}.json'
        if not p.exists():raise FileNotFoundError(p)
        info[role]=json.loads(p.read_text(encoding='utf-8'))
    # New match groups expand scene coverage; only one clip per added match.
    train_matches=[f'match{i}' for i in range(32,40)]
    dev_matches=[f'match{i}' for i in range(40,45)]
    manifest={'dataset_revision':DATA_REVISION,'train':[],'dev':[],'known_evaluation':json.loads((ROOT/'outputs/vision/specialist_v1/split.json').read_text(encoding='utf-8'))['known_evaluation'],'final_test':[],'final_test_status':'NOT_SELECTED: existing candidates failed; final data remains untouched','selection':'old train/dev pilot retained; add first official train rally per train match32–39, one official val rally per dev match40–47; match-disjoint','train_added_matches':train_matches,'dev_added_matches':dev_matches}
    old=json.loads((ROOT/'outputs/vision/specialist_v1/split.json').read_text(encoding='utf-8'))
    manifest['train']=old['train'][:];manifest['dev']=old['dev'][:]
    for m in train_matches:
        matches=[r for mid,r in info['train'] if mid==m]
        if not matches:raise ValueError(f'No train clip for {m}')
        manifest['train'].append(f'tabletennis/{m}/{matches[0]}')
    for m in dev_matches:
        matches=[r for mid,r in info['val'] if mid==m]
        if not matches:raise ValueError(f'No disjoint DEV clip for {m}')
        manifest['dev'].append(f'tabletennis/{m}/{matches[0]}')
    exposed={m for role in ['train','val','test'] for m,_ in info[role]}
    manifest['parent_exposed_match_ids']=sorted(exposed)
    validate_split(manifest)
    split_path=OUT/'split.json'
    if split_path.exists() and json.loads(split_path.read_text(encoding='utf-8'))!=manifest:
        if (OUT/'prepared_inputs.json').exists() or (OUT/'training_config.json').exists() or (ROOT/'models/tti_tabletennis/tti_balltrack_final_v1_D.pth').exists():
            raise FileExistsError('Split already used by a run; use new experiment ID')
        attempt=OUT/'split_download_attempt.json'
        if not attempt.exists():attempt.write_bytes(split_path.read_bytes())
    split_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')

    def catalog(directory):
        path=catalog_dir/(directory.replace('/','_')+'.json')
        if path.exists():return {e['path']:e for e in json.loads(path.read_text(encoding='utf-8'))['entries']}
        url=f'https://huggingface.co/api/datasets/{SOURCE}/tree/{DATA_REVISION}/{directory}?limit=1000';entries=[];visited=set()
        while url and url not in visited:
            visited.add(url)
            for attempt in range(3):
                try:
                    block,link=get_json(url);entries+=block;break
                except (OSError,TimeoutError):
                    if attempt==2:raise
                    time.sleep(2*(attempt+1))
            match=re.search(r'<([^>]+)>;\s*rel="next"',link);url=match.group(1) if match else None
        path.write_text(json.dumps({'revision':DATA_REVISION,'entries':entries},indent=2),encoding='utf-8')
        return {e['path']:e for e in entries}
    lock=__import__('threading').Lock();cache={}
    def entry(relative):
        folder=relative.rsplit('/',1)[0]
        with lock:
            if folder not in cache:cache[folder]=catalog(folder)
            return cache[folder][relative]
    def fetch(source):
        _,m,r=source.split('/');items=[]
        for rel in [f'tabletennis/videos/{m}_{r}.mp4',f'tabletennis/all/{m}/csv/{r}_ball.csv']:
            meta=entry(rel);dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            def valid(p):
                if not p.exists() or p.stat().st_size!=meta['size']:return False
                data=p.read_bytes()
                return hashlib.sha256(data).hexdigest()==meta['lfs']['oid'] if meta.get('lfs') else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==meta['oid']
            if dest.exists() and not valid(dest):raise ValueError(f'Existing asset hash mismatch: {dest}')
            if not dest.exists():
                url=f'https://huggingface.co/datasets/{SOURCE}/resolve/{DATA_REVISION}/{rel}'
                for attempt in range(4):
                    temp=dest.with_suffix(dest.suffix+'.'+uuid.uuid4().hex+'.partial')
                    try:
                        with urllib.request.urlopen(url,timeout=180) as response,temp.open('wb') as out:
                            while chunk:=response.read(1024*1024):out.write(chunk)
                        if not valid(temp):raise ValueError(f'Download hash mismatch: {rel}')
                        temp.replace(dest);break
                    except (OSError,TimeoutError):
                        # Unique partial is retained; only the verified full asset
                        # gets the canonical path. Resume with another bounded try.
                        if attempt==3:raise
                        time.sleep(2*(attempt+1))
            items.append({'path':rel,'size':meta['size'],'sha256':sha256(dest),'identity':meta.get('lfs',{}).get('oid',meta.get('oid'))})
        return items
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets=[x for result in pool.map(fetch,manifest['train'][-8:]+manifest['dev'][-8:]) for x in result]
    (OUT/'additional_asset_manifest.json').write_text(json.dumps(assets,indent=2)+'\n',encoding='utf-8')
    print(f"TRAIN {len(manifest['train'])} clips / {len({s.split('/')[1] for s in manifest['train']})} matches; DEV {len(manifest['dev'])} clips / {len({s.split('/')[1] for s in manifest['dev']})} matches; added and SHA-verified {len(assets)//2} videos",flush=True)

if __name__=='__main__':main()
