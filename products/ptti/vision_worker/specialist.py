"""Model-level A/B/C pilot using unchanged upstream loader/model/loss/metric."""
import argparse,json,sys,time,random,math,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vision.specialist import sha256,validate_split,validate_model,safe_checkpoint_target,OFFICIAL_SHA
from vision.config import RV_COMMIT
from vision.benchmark import compare,read_ground_truth,percentile

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','audit','baseline','train_b','train_c','evaluate_b','evaluate_c']);args=parser.parse_args()
    import cv2,numpy as np,torch
    from torch.utils.data import DataLoader,WeightedRandomSampler
    home=ROOT/'outputs/vision/specialist_v1';home.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((home/'split.json').read_text());validate_split(manifest)
    official=ROOT/'models/balltrack_best.pth';validate_model(official,OFFICIAL_SHA)
    runtime=ROOT/'third_party_runtime/racketvision/source/BallTrack';sys.path.insert(0,str(runtime))
    from inference import BallInferencer,remove_ddp_prefix
    from dataset.uball import UniBallDataset
    from model.tracknet_v3 import TrackNet
    from metrics.ball_metrics import BallMetrics
    import torch.utils.data._utils.collate as collate
    # Filename-only shim: upstream OpenCV imread cannot open Chinese Windows paths.
    cv2.imread=lambda path,flags=cv2.IMREAD_COLOR:cv2.imdecode(np.fromfile(path,dtype=np.uint8),flags)
    config=dict(epochs=3,batch_size=2,learning_rate=1e-5,optimizer='Adam',seed=20261005,
                architecture='unchanged TrackNetV3 d_model64 in15 out4 last_only',resolution=[512,288],
                seq_len=4,sigma=3.5,mixup=True,alpha=.5,loss='unchanged upstream WBCELoss',
                best_metric='DEV official BallMetrics F1',hard_negative_sampling_weight=3,
                hard_negative_minimum_response=.5,hard_negative_distance_model_px=4,
                median='GT-free up to100 evenly sampled frames per rally; original full-match median unavailable',
                scope='bounded tabletennis pilot; NOT full 625-clip training reproduction')
    config_path=home/'training_config.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:raise ValueError('Configuration already frozen')
    write(config_path,config)
    parent=torch.load(official,map_location='cpu',weights_only=False)
    if args.stage=='audit':
        write(home/'upstream_checkpoint_meta.json',parent['meta']);print('Official epoch',parent['meta']['epoch']);return
    data=home/'dataset/tabletennis'
    if args.stage=='prepare':
        from vision.config import VisionConfig
        source=VisionConfig.load().dataset_root
        inputs=[]
        for role in ['train','dev','known_evaluation']:
            entries=[]
            for s in manifest[role]:
                _,m,r=s.split('/');entries.append([m,r]);gtpath=source/f'tabletennis/all/{m}/csv/{r}_ball.csv';gt=read_ground_truth(gtpath)
                if any((not g['visible']) and (g['x']!=0 or g['y']!=0) for g in gt.values()):raise ValueError('Visibility sentinel inconsistency; do not silently change GT')
                target=data/'all'/m;frames=target/'frame'/r;frames.mkdir(parents=True,exist_ok=True)
                csvdir=target/'csv';csvdir.mkdir(exist_ok=True);shutil.copyfile(gtpath,csvdir/f'{r}_ball.csv')
                needed={0}|{max(0,f-i) for f in gt for i in range(4)}
                cap=cv2.VideoCapture(str(source/f'tabletennis/videos/{m}_{r}.mp4'));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                sampled=set(np.linspace(0,count-1,min(count,100),dtype=int));background=[];i=0;w=h=0
                while True:
                    ok,image=cap.read()
                    if not ok:break
                    h,w=image.shape[:2]
                    if i in sampled:background.append(image)
                    if i in needed:
                        ok,encoded=cv2.imencode('.jpg',image);encoded.tofile(frames/f'{i:04d}.jpg')
                    i+=1
                cap.release()
                if max(needed)>=i or i>1800:raise ValueError('Video/GT bounds mismatch')
                # Match-level original median unavailable: same rally proxy for every A/B/C.
                np.savez(frames/'median.npz',median=np.median(np.array(background),axis=0).astype(np.uint8))
                inputs.append(dict(source_id=s,role=role,frames=i,annotated_frames=len(gt),width=w,height=h,
                                   video_sha256=sha256(source/f'tabletennis/videos/{m}_{r}.mp4'),gt_sha256=sha256(gtpath),median_sha256=sha256(frames/'median.npz')))
                print('Prepared',role,s,flush=True)
            write(data/'info'/f'{role}.json',entries)
        write(home/'prepared_inputs.json',inputs);return

    def dataset(role):return UniBallDataset(root_dir=str(data),split=role,seq_len=4,width=512,height=288,sigma=3.5,bg_mode='concat',first_frame='0000')
    def model(path):
        mdl=TrackNet(15,4,mixup=True,alpha=.5,last_only=True)
        state=torch.load(path,map_location='cpu',weights_only=False)['state_dict'];mdl.load_state_dict(remove_ddp_prefix(state));return mdl.cuda()
    def peaks(hm):
        # Ranked real local maxima with greedy radius5 NMS; no calibrated probability.
        local=hm==cv2.dilate(hm.astype(np.float32),np.ones((3,3),np.uint8))
        yy,xx=np.where(local & (hm>1e-7));order=np.argsort(-hm[yy,xx],kind='stable');suppressed=np.zeros(hm.shape,bool);out=[]
        for index in order:
            x,y=int(xx[index]),int(yy[index])
            if suppressed[y,x]:continue
            out.append(dict(x=x,y=y,response=float(hm[y,x])))
            suppressed[max(0,y-5):y+6,max(0,x-5):x+6]=True
        return out

    def evaluate(mdl,role,mine=False):
        ds=dataset(role);loader=DataLoader(ds,batch_size=2,shuffle=False,num_workers=0)
        metric=BallMetrics(height=288,width=512,last_only=True,gt_src='position');mdl.eval();points={};gt_maps={};ranks=[];negatives=[];errors=[];witness=None;index=0;start=time.perf_counter()
        for batch in loader:
            batch=mdl.data_preprocessor(batch,training=False)
            with torch.no_grad(),torch.amp.autocast('cuda'):pred,labels,coordinates=mdl.forward(**batch)
            metric.process(batch,(pred,labels,coordinates));heatmaps=pred.float().cpu().numpy()[:,0]
            for j,hm in enumerate(heatmaps):
                rally_index,frame=map(int,batch['data_idx'][j,-1].cpu().tolist());m,r=json.loads((data/'info'/f'{role}.json').read_text())[rally_index];sid=f'tabletennis/{m}/{r}'
                g=read_ground_truth(data/'all'/m/'csv'/f'{r}_ball.csv')[frame];w,h=ds.img_config['img_shape'][rally_index]
                # Unchanged upstream inference box decoding, inclusive labelled sequence.
                decoder=object.__new__(BallInferencer);decoder.thre=.5;x,y,bw,bh,conf=decoder._predict_location(hm)
                px,py=int((x+bw/2)*w/512),int((y+bh/2)*h/288);visible=px!=0 or py!=0
                p=dict(frame=frame,visible=visible,pixel_x=px if visible else None,pixel_y=py if visible else None,confidence=conf)
                points.setdefault(sid,[]).append(p);gt_maps.setdefault(sid,{})[frame]=g
                heatmap_path=home/'heatmaps'/args.stage/role/f'{m}_{r}_{frame:06d}.npz';heatmap_path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(heatmap_path,heatmap=hm)
                candidates=peaks(hm);gx,gy=g['x']/w*512,g['y']/h*288
                near=[(rank+1,c) for rank,c in enumerate(candidates) if math.hypot(c['x']-gx,c['y']-gy)<=4]
                rank=min((n for n,_ in near),default=None);response=max((c['response'] for _,c in near),default=None)
                if g['visible']:ranks.append(dict(source_id=sid,frame=frame,rank=rank,gt_local_peak_response=response))
                if g['visible'] and visible:errors.append(math.hypot(px-g['x'],py-g['y']))
                if mine:
                    for candidate in candidates:
                        if candidate['response']<.5:break
                        if not g['visible'] or math.hypot(candidate['x']-gx,candidate['y']-gy)>4:
                            record=dict(sample_index=index,source_id=sid,match_id=m,frame=frame,gt=g,false_peak=candidate,category='UNKNOWN',response_semantics='sigmoid heatmap response; not calibrated probability')
                            negatives.append(record)
                            image=cv2.imread(str(data/'all'/m/'frame'/r/f'{frame:04d}.jpg'));cx=round(candidate['x']*w/512);cy=round(candidate['y']*h/288)
                            crop=image[max(0,cy-64):cy+65,max(0,cx-64):cx+65];folder=home/'hard_negative_crops';folder.mkdir(exist_ok=True)
                            if crop.size:
                                path=folder/f'{m}_{r}_{frame}_{len(negatives)}.jpg';ok,encoded=cv2.imencode('.jpg',crop);encoded.tofile(path);record['crop']=str(path)
                if sid=='tabletennis/match10/001' and frame==184:
                    patch=hm[max(0,round(gy)-2):round(gy)+3,max(0,round(gx)-2):round(gx)+3]
                    witness=dict(gt_peak_rank=rank,true_ball_region_response=float(patch.max()),clothing_peak_response=float(hm[122,317]),decoded=p,pixel_error=math.hypot(px-g['x'],py-g['y']) if visible else None,semantics='Response is not calibrated probability; official loader baseline differs from legacy inferencer interpolation')
                    np.savez_compressed(home/f'witness_{args.stage}.npz',heatmap=hm)
                index+=1
        torch.cuda.synchronize();elapsed=time.perf_counter()-start
        metrics=metric.compute_metrics(metric.results);clips=[]
        for sid,ps in points.items():
            rally_index=next(i for i,x in enumerate(json.loads((data/'info'/f'{role}.json').read_text())) if sid=='tabletennis/'+x[0]+'/'+x[1]);w,h=ds.img_config['img_shape'][rally_index]
            clips.append(dict(source_id=sid,metrics=compare(ps,gt_maps[sid],w,h),raw_predictions=ps))
        visible=sum(c['metrics']['visible_gt_frames'] for c in clips);detected=sum(c['metrics']['detected_visible_frames'] for c in clips)
        aggregate=dict(visible=visible,detected=detected,recall=detected/visible if visible else None,false_positives=sum(c['metrics']['false_detections'] or 0 for c in clips),negative=sum(c['metrics']['annotated_negative_frames'] for c in clips),mean=float(np.mean(errors)) if errors else None,median=float(np.median(errors)) if errors else None,p95=percentile(errors,.95),catastrophic={str(t):sum(e>t for e in errors) for t in [20,50,100]})
        rank_metrics={str(k):sum(r['rank'] is not None and r['rank']<=k for r in ranks) for k in [1,4,8,16,32,64]};rank_metrics.update(visible=len(ranks),greater_than64=sum(r['rank'] is not None and r['rank']>64 for r in ranks),no_nearby_peak=sum(r['rank'] is None for r in ranks))
        return dict(role=role,official_style=metrics,tti_style=aggregate,peak_rank=rank_metrics,peak_rank_frames=ranks,clips=clips,witness=witness,seconds=elapsed,sparse_evaluated_frames=index,scope='bounded official loader/metric reproduction with rally-median proxy; NOT official full-test score'),negatives

    if args.stage=='baseline':
        mdl=model(official);all_results={}
        for role in ['train','dev','known_evaluation']:
            result,negatives=evaluate(mdl,role,mine=role in ['train','dev']);all_results[role]=result
            if negatives:write(home/f'hard_negative_{role}.json',negatives)
        write(home/'A_official.json',all_results);return
    strategy='B' if args.stage.endswith('b') else 'C'
    checkpoint=ROOT/'models/tti_tabletennis'/f'tti_balltrack_tt_ft_v1_{strategy}.pth'
    if args.stage.startswith('evaluate'):
        mdl=model(checkpoint);result,_=evaluate(mdl,'known_evaluation');write(home/f'{strategy}_known_evaluation.json',result);return
    safe_checkpoint_target(official,checkpoint)
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed']);torch.cuda.manual_seed_all(config['seed']);torch.backends.cudnn.benchmark=False
    mdl=model(official);ds=dataset('train');weights=torch.ones(len(ds))
    if strategy=='C':
        hard=json.loads((home/'hard_negative_train.json').read_text())
        for r in hard:weights[r['sample_index']]=config['hard_negative_sampling_weight']
        sampler=WeightedRandomSampler(weights,len(ds),replacement=True,generator=torch.Generator().manual_seed(config['seed']))
        loader=DataLoader(ds,batch_size=2,sampler=sampler,num_workers=0)
    else:
        sampler=WeightedRandomSampler(weights,len(ds),replacement=True,generator=torch.Generator().manual_seed(config['seed']))
        loader=DataLoader(ds,batch_size=2,sampler=sampler,num_workers=0)
    optimizer=torch.optim.Adam(mdl.parameters(),lr=config['learning_rate']);scaler=torch.amp.GradScaler('cuda');history=[];best=-1;best_epoch=None;start=time.perf_counter()
    for epoch in range(1,config['epochs']+1):
        mdl.train();losses=[]
        for batch in loader:
            batch=mdl.data_preprocessor(batch,training=True);optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast('cuda'):loss=mdl.forward(**batch,mode='loss')['loss']
            if not torch.isfinite(loss):raise RuntimeError('Non-finite training loss')
            scaler.scale(loss).backward();scaler.step(optimizer);scaler.update();losses.append(float(loss.detach()))
        validation,_=evaluate(mdl,'dev');score=validation['official_style']['f1'];history.append(dict(epoch=epoch,mean_loss=float(np.mean(losses)),dev=validation))
        print(strategy,'epoch',epoch,'loss',np.mean(losses),'DEV F1',score,flush=True)
        if score>best:
            best=score;best_epoch=epoch;checkpoint.parent.mkdir(parents=True,exist_ok=True)
            torch.save(dict(state_dict=mdl.state_dict(),meta=dict(epoch=epoch,parent_sha256=OFFICIAL_SHA,strategy=strategy)),checkpoint)
    provenance=dict(parent_checkpoint_sha256=OFFICIAL_SHA,split_sha256=sha256(home/'split.json'),config_sha256=sha256(config_path),epochs=config['epochs'],optimizer='Adam',learning_rate=config['learning_rate'],seed=config['seed'],best_epoch=best_epoch,validation_metric={'DEV_official_F1':best},checkpoint_sha256=sha256(checkpoint),tti_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),racketvision_commit=RV_COMMIT,worker_sha256=sha256(Path(__file__)),prepared_inputs_sha256=sha256(home/'prepared_inputs.json'),gpu=torch.cuda.get_device_name(),torch=torch.__version__,cuda=torch.version.cuda,train_match_ids=sorted({s.split('/')[1] for s in manifest['train']}),dev_match_ids=sorted({s.split('/')[1] for s in manifest['dev']}),strategy=strategy,training_seconds=time.perf_counter()-start,architecture_changed=False,loss_changed=False,hard_negative_strategy='3x weighted sampler; same epoch sample count, seed, parent, loss and LR' if strategy=='C' else 'none',model_path=str(checkpoint))
    write(checkpoint.with_suffix('.provenance.json'),provenance);write(home/f'{strategy}_training.json',dict(provenance=provenance,history=history))

if __name__=='__main__':main()
