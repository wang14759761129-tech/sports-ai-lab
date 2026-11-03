"""Single bounded final BallTrack tuning experiment; never edits upstream."""
import argparse,json,sys,time,random,math,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vision.specialist import sha256,validate_split,immutable_coordinate_sample,validate_model,validate_provenance,safe_checkpoint_target,OFFICIAL_SHA
from vision.config import RV_COMMIT
from vision.benchmark import compare,read_ground_truth,percentile

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['baseline','train_d','evaluate_d']);args=parser.parse_args()
    import cv2,numpy as np,torch
    from torch.utils.data import DataLoader
    home=ROOT/'outputs/vision/balltrack_final';home.mkdir(parents=True,exist_ok=True)
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
    config=dict(epochs=15,early_stopping_patience=4,batch_size=2,learning_rate=1e-5,optimizer='Adam',seed=20261005,
                architecture='unchanged TrackNetV3 d_model64 in15 out4 last_only',resolution=[512,288],
                seq_len=4,sigma=3.5,mixup=True,alpha=.5,loss='unchanged upstream WBCELoss',
                best_metric='DEV official BallMetrics F1; early stop after 4 non-improving epochs',
                median='pixelwise uint8 median over up to100 globally evenly sampled frames across all selected rallies for each match; not complete-match official input',
                scope='bounded diversified final tuning; official all-frame match medians and complete match video remain unavailable')
    config_path=home/'training_config.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:raise ValueError('Configuration already frozen')
    write(config_path,config)
    parent=torch.load(official,map_location='cpu',weights_only=False)
    data=home/'dataset/tabletennis'
    class StableUniBallDataset(UniBallDataset):
        def __getitem__(self,index):
            return immutable_coordinate_sample(self.data_dict,index,lambda i:super(StableUniBallDataset,self).__getitem__(i))
    def dataset(role):return StableUniBallDataset(root_dir=str(data),split=role,seq_len=4,width=512,height=288,sigma=3.5,bg_mode='concat',first_frame='0000')
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

    def evaluate(mdl,role):
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
                threshold=.5;decoder_kind='upstream_contour_bbox';refinement='none'
                if args.stage=='evaluate_d':
                    dc=json.loads((home/'decoder_config.json').read_text(encoding='utf-8'))
                    threshold=dc['threshold'];decoder_kind=dc['decoder'];refinement=dc['refinement']
                mask=hm>threshold
                if not mask.any():x=y=0.;conf=0.;visible=False
                elif decoder_kind=='upstream_contour_bbox':
                    contours,_=cv2.findContours(mask.astype('uint8')*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                    if not contours:x=y=0.;conf=0.;visible=False
                    else:
                        xx,yy,ww,hh=cv2.boundingRect(max(contours,key=lambda c:cv2.boundingRect(c)[2]*cv2.boundingRect(c)[3]))
                        x,y=xx+ww/2,yy+hh/2;conf=float(np.mean(hm[yy:yy+hh,xx:xx+ww]));visible=True
                else:
                    yy,xx=np.unravel_index(int(np.argmax(hm)),hm.shape);x,y=float(xx),float(yy);conf=float(hm[yy,xx]);visible=True
                if visible and refinement!='none':
                    radius=2;cx,cy=round(x),round(y);patch=hm[max(0,cy-radius):cy+radius+1,max(0,cx-radius):cx+radius+1].astype('float64')
                    weights=np.maximum(patch-float(patch.min()),0)
                    if refinement=='softargmax':
                        logits=np.exp((patch-patch.max())/.05);weights=logits
                    if weights.sum()>0:
                        gy,gx=np.mgrid[max(0,cy-radius):cy+radius+1,max(0,cx-radius):cx+radius+1];x=float((gx*weights).sum()/weights.sum());y=float((gy*weights).sum()/weights.sum())
                px,py=round(x*w/512),round(y*h/288);visible=visible and not (px==0 and py==0)
                p=dict(frame=frame,visible=visible,pixel_x=px if visible else None,pixel_y=py if visible else None,confidence=conf)
                points.setdefault(sid,[]).append(p);gt_maps.setdefault(sid,{})[frame]=g
                heatmap_path=home/'heatmaps'/args.stage/role/f'{m}_{r}_{frame:06d}.npz';heatmap_path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(heatmap_path,heatmap=hm)
                candidates=peaks(hm);gx,gy=g['x']/w*512,g['y']/h*288
                near=[(rank+1,c) for rank,c in enumerate(candidates) if math.hypot(c['x']-gx,c['y']-gy)<=4]
                rank=min((n for n,_ in near),default=None);response=max((c['response'] for _,c in near),default=None)
                if g['visible']:ranks.append(dict(source_id=sid,frame=frame,rank=rank,gt_local_peak_response=response))
                if g['visible'] and visible:errors.append(math.hypot(px-g['x'],py-g['y']))
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
        return dict(role=role,official_style=metrics,tti_style=aggregate,peak_rank=rank_metrics,peak_rank_frames=ranks,clips=clips,witness=witness,seconds=elapsed,sparse_evaluated_frames=index,scope='bounded official loader reproduction; official complete-match background and complete-match video unavailable'),negatives

    if args.stage=='baseline':
        if (home/'A_official.json').exists():raise FileExistsError('Baseline evidence is frozen; use a new experiment ID')
        mdl=model(official);all_results={}
        for role in ['train','dev','known_evaluation']:all_results[role]=evaluate(mdl,role)[0]
        write(home/'A_official.json',all_results);return
    strategy='D';checkpoint=ROOT/'models/tti_tabletennis/tti_balltrack_final_v1_D.pth'
    if args.stage=='evaluate_d':
        if (home/'D_known_evaluation.json').exists():raise FileExistsError('Known evaluation is frozen; use a new experiment ID')
        provenance=json.loads(checkpoint.with_suffix('.provenance.json').read_text(encoding='utf-8'));validate_provenance(provenance,checkpoint)
        if provenance['split_sha256']!=sha256(home/'split.json') or provenance['config_sha256']!=sha256(config_path) or provenance['decoder_sha256']!=sha256(home/'decoder_config.json'):raise ValueError('Evaluation configuration drift')
        mdl=model(checkpoint);result,_=evaluate(mdl,'known_evaluation');write(home/'D_known_evaluation.json',result);return
    safe_checkpoint_target(official,checkpoint)
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed']);torch.cuda.manual_seed_all(config['seed']);torch.backends.cudnn.benchmark=False
    random.seed(config['seed']);np.random.seed(config['seed']);torch.manual_seed(config['seed']);torch.cuda.manual_seed_all(config['seed']);torch.backends.cudnn.benchmark=False
    mdl=model(official);ds=dataset('train');loader=DataLoader(ds,batch_size=2,shuffle=True,generator=torch.Generator().manual_seed(config['seed']),num_workers=0)
    optimizer=torch.optim.Adam(mdl.parameters(),lr=config['learning_rate']);scaler=torch.amp.GradScaler('cuda');history=[];best=-1;best_epoch=None;patience=0;start=time.perf_counter()
    for epoch in range(1,config['epochs']+1):
        mdl.train();losses=[]
        for batch in loader:
            batch=mdl.data_preprocessor(batch,training=True);optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast('cuda'):loss=mdl.forward(**batch,mode='loss')['loss']
            if not torch.isfinite(loss):raise RuntimeError('Non-finite training loss')
            scaler.scale(loss).backward();scaler.step(optimizer);scaler.update();losses.append(float(loss.detach()))
        validation,_=evaluate(mdl,'dev');score=validation['official_style']['f1'];history.append(dict(epoch=epoch,mean_loss=float(np.mean(losses)),dev_f1=score,dev_recall=validation['official_style']['recall'],dev_p95=validation['tti_style']['p95'],dev_catastrophic=validation['tti_style']['catastrophic'],dev=validation))
        print(strategy,'epoch',epoch,'loss',np.mean(losses),'DEV F1',score,'recall',validation['official_style']['recall'],'P95',validation['tti_style']['p95'],'catastrophic',validation['tti_style']['catastrophic'],flush=True)
        if score>best:
            best=score;best_epoch=epoch;patience=0;checkpoint.parent.mkdir(parents=True,exist_ok=True)
            torch.save(dict(state_dict=mdl.state_dict(),meta=dict(epoch=epoch,parent_sha256=OFFICIAL_SHA,strategy=strategy)),checkpoint)
        else:
            patience+=1
            if patience>=config['early_stopping_patience']:break
    # Evaluate the best checkpoint on DEV once, preserving its actual heatmaps for
    # the decoder-only development study. KNOWN remains sealed until config freeze.
    mdl=model(checkpoint);best_dev,_=evaluate(mdl,'dev')
    provenance=dict(parent_checkpoint_sha256=OFFICIAL_SHA,split_sha256=sha256(home/'split.json'),config_sha256=sha256(config_path),decoder_sha256=sha256(home/'decoder_config.json') if (home/'decoder_config.json').exists() else None,epochs=epoch,optimizer='Adam',learning_rate=config['learning_rate'],seed=config['seed'],best_epoch=best_epoch,validation_metric={'DEV_official_F1':best},best_dev_metrics={'recall':best_dev['official_style']['recall'],'p95':best_dev['tti_style']['p95'],'catastrophic':best_dev['tti_style']['catastrophic']},checkpoint_sha256=sha256(checkpoint),tti_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),racketvision_commit=RV_COMMIT,worker_sha256=sha256(Path(__file__)),prepared_inputs_sha256=sha256(home/'prepared_inputs.json'),gpu=torch.cuda.get_device_name(),torch=torch.__version__,cuda=torch.version.cuda,train_match_ids=sorted({s.split('/')[1] for s in manifest['train']}),dev_match_ids=sorted({s.split('/')[1] for s in manifest['dev']}),strategy=strategy,training_seconds=time.perf_counter()-start,architecture_changed=False,loss_changed=False,model_path=str(checkpoint))
    write(checkpoint.with_suffix('.provenance.json'),provenance);write(home/f'{strategy}_training.json',dict(provenance=provenance,history=history))

if __name__=='__main__':main()
