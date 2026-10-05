"""Preserve the first manifest and rebuild its source inventory from frozen inputs."""
import json,sys,shutil
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vision.config import VisionConfig
from vision.specialist import sha256
from vision.benchmark import read_ground_truth

def main():
    home=ROOT/'outputs/vision/balltrack_final';manifest=json.loads((home/'split.json').read_text(encoding='utf-8'));source=VisionConfig.load().dataset_root;old=home/'prepared_inputs.json';archive=home/'prepared_inputs_before_manifest_repair.json'
    if not old.exists():raise FileNotFoundError(old)
    if not archive.exists():shutil.copyfile(old,archive)
    records=[]
    for role in ['train','dev','known_evaluation']:
        for sid in manifest[role]:
            _,match,rally=sid.split('/');video=source/f'tabletennis/videos/{match}_{rally}.mp4';gtfile=source/f'tabletennis/all/{match}/csv/{rally}_ball.csv';frames=home/f'dataset/tabletennis/all/{match}/frame/{rally}';median=home/f'dataset/tabletennis/all/{match}/median.npz'
            if not all(p.is_file() for p in [video,gtfile,frames/'0000.jpg',median]):raise FileNotFoundError(f'Prepared input missing: {sid}')
            gt=read_ground_truth(gtfile);needed={0}|{max(0,f-i) for f in gt for i in range(4)}
            if any(not (frames/f'{i:04d}.jpg').is_file() for i in needed):raise FileNotFoundError(f'Required sample frame missing: {sid}')
            cap=cv2.VideoCapture(str(video));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=float(cap.get(cv2.CAP_PROP_FPS));cap.release()
            if count<=max(needed) or width<=0 or height<=0:raise ValueError(f'Invalid source video: {sid}')
            records.append(dict(source_id=sid,role=role,frames=count,annotated_frames=len(gt),resolution=[width,height],fps=fps,video_sha256=sha256(video),gt_sha256=sha256(gtfile),match_median_sha256=sha256(median)))
    expected=[s for role in ['train','dev','known_evaluation'] for s in manifest[role]]
    if len(records)!=len(expected) or {r['source_id'] for r in records}!=set(expected):raise ValueError('Manifest source identities do not exactly match split')
    old.write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8');prepared_sha=sha256(old)
    checkpoint=ROOT/'models/tti_tabletennis/tti_balltrack_final_v1_D.pth';provenance_path=checkpoint.with_suffix('.provenance.json');provenance=json.loads(provenance_path.read_text(encoding='utf-8'));provenance['prepared_inputs_sha256']=prepared_sha;provenance_path.write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    training=home/'D_training.json';record=json.loads(training.read_text(encoding='utf-8'));record['provenance']=provenance;training.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(f'Preserved erroneous inventory at {archive.name}; rebuilt {len(records)} distinct source records, SHA256 {prepared_sha}')

if __name__=='__main__':main()
