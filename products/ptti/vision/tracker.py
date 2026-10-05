"""Experimental offline beam association; never changes upstream RAW observations."""
from dataclasses import dataclass, asdict
import math
from statistics import median

@dataclass(frozen=True)
class TrackerConfig:
    top_k: int = 16
    minimum_response: float = .01
    nms_radius: int = 5
    beam_width: int = 12
    response_weight: float = .2
    motion_weight: float = 1.0
    acceleration_weight: float = .5
    persistence_weight: float = .4
    missing_cost: float = .9
    speed_scale_diagonals_per_second: float = 3.0
    gap_seconds: float = .1
    interpolation_frames: int = 0

class SceneContext:
    """Optional externally supplied soft priors, never an exclusion mask."""
    def __init__(self, zones=()):
        self.zones = zones
    def penalty(self, x, y):
        return sum(z['penalty'] for z in self.zones if z['x0'] <= x <= z['x1'] and z['y0'] <= y <= z['y1'])

class TTIBallTracker:
    def __init__(self, config=None, scene=None):
        self.config = config or TrackerConfig()
        self.scene = scene or SceneContext()
        if self.config.beam_width < 1 or self.config.top_k < 1 or self.config.interpolation_frames < 0 or self.config.speed_scale_diagonals_per_second <= 0 or any(not math.isfinite(v) or v < 0 for k,v in asdict(self.config).items()) or self.config.minimum_response > 1:
            raise ValueError('Invalid tracker parameters')

    def track(self, raw, observations, width, height, fps):
        if min(width,height,fps) <= 0 or len(raw) != len(observations):
            raise ValueError('Invalid aligned observations')
        cfg = self.config
        diagonal = math.hypot(width,height)
        # Clip-level persistent response map is GT-free and valid for offline use.
        counts = {}
        for obs in observations:
            cells={(round(c['model_x']/10),round(c['model_y']/10)) for c in obs['candidates']}
            for cell in cells:
                counts[cell] = counts.get(cell,0)+1
        # Beam state: cost, linked path, last two actual observations.
        beam = [(0.,None,())]
        for p, obs in zip(raw,observations):
            if p['frame'] != obs['frame']:
                raise ValueError('Frame alignment mismatch')
            mh,mw = obs['heatmap_shape']
            choices = [dict(x=c['model_x']*width/mw,y=c['model_y']*height/mh,
                            response=c['model_response'],origin='peak',cell=(round(c['model_x']/10),round(c['model_y']/10)))
                       for c in obs['candidates']]
            # Keep the exact RAW box center, so correct RAW precision is preserved.
            if p['visible']:
                choices.append(dict(x=p['pixel_x'],y=p['pixel_y'],response=p['confidence'] or .01,origin='raw',
                                    cell=(round(p['pixel_x']/width*mw/10),round(p['pixel_y']/height*mh/10))))
            proposals=[]
            for cost,path,history in beam:
                proposals.append((cost+cfg.missing_cost,(None,path,{}),history))
                for c in choices:
                    response_cost=-math.log(max(c['response'],1e-8))*cfg.response_weight
                    motion=acceleration=0.
                    if history:
                        last=history[-1];dt=(p['frame']-last[0])/fps
                        if dt <= cfg.gap_seconds:
                            speed=math.hypot(c['x']-last[1],c['y']-last[2])/diagonal/dt
                            motion=max(0,speed/cfg.speed_scale_diagonals_per_second-1)
                            if len(history)>1:
                                before=history[-2];prior_dt=(last[0]-before[0])/fps
                                vx=(last[1]-before[1])/prior_dt;vy=(last[2]-before[2])/prior_dt
                                acceleration=math.hypot(c['x']-last[1]-vx*dt,c['y']-last[2]-vy*dt)/diagonal/max(dt,1/fps)/cfg.speed_scale_diagonals_per_second
                                acceleration=min(acceleration,1.) # Bounce/contact can legitimately reverse direction.
                    persistence=counts.get(c['cell'],0)/max(1,len(raw))
                    scene=self.scene.penalty(c['x']/width,c['y']/height)
                    delta=response_cost+cfg.motion_weight*motion+cfg.acceleration_weight*acceleration+cfg.persistence_weight*persistence+scene
                    evidence=dict(model_response=c['response'],response_kind='upstream_bbox_mean' if c['origin']=='raw' else 'heatmap_peak',response_semantics='sigmoid response; not calibrated probability',
                                  motion_cost=motion,acceleration_cost=acceleration,persistent_response_fraction=persistence,
                                  scene_soft_penalty=scene,combined_cost=delta)
                    h=(*history,(p['frame'],c['x'],c['y']))[-2:]
                    proposals.append((cost+delta,(c,path,evidence),h))
            beam=[];seen=set()
            for proposal in sorted(proposals,key=lambda b:b[0]):
                signature=proposal[2]
                if signature not in seen:
                    seen.add(signature);beam.append(proposal)
                if len(beam)==cfg.beam_width:break
        node=min(beam,key=lambda b:b[0])[1]; selected=[]
        while node:
            choice,node,evidence=node
            selected.append((choice,evidence))
        selected.reverse(); rows=[]
        for p,(c,evidence) in zip(raw,selected):
            t=dict(p,visible=bool(c),pixel_x=c['x'] if c else None,pixel_y=c['y'] if c else None,
                   source='detected' if c else 'missing',model_observation=bool(c),confidence=None)
            t['normalized_x']=t['pixel_x']/width if c else None
            t['normalized_y']=t['pixel_y']/height if c else None
            decision='NO_RELIABLE_CANDIDATE' if not c else ('RAW_ACCEPTED' if c['origin']=='raw' else 'ALTERNATIVE_CANDIDATE_SELECTED')
            rows.append(dict(raw_prediction=dict(p),tti_prediction=t,decision=decision,
                             reason='Minimum cumulative beam cost over response, motion, history and soft persistence',evidence=evidence))
        if cfg.interpolation_frames:
            detected=[i for i,r in enumerate(rows) if r['tti_prediction']['visible']]
            for a,b in zip(detected,detected[1:]):
                if 1 < b-a <= cfg.interpolation_frames+1:
                    left,right=rows[a]['tti_prediction'],rows[b]['tti_prediction']
                    if math.hypot(right['pixel_x']-left['pixel_x'],right['pixel_y']-left['pixel_y'])/diagonal/((b-a)/fps) > cfg.speed_scale_diagonals_per_second:
                        continue
                    for i in range(a+1,b):
                        f=(i-a)/(b-a);t=rows[i]['tti_prediction']
                        x=left['pixel_x']*(1-f)+right['pixel_x']*f;y=left['pixel_y']*(1-f)+right['pixel_y']*f
                        t.update(visible=True,pixel_x=x,pixel_y=y,normalized_x=x/width,normalized_y=y/height,source='interpolated',model_observation=False)
                        rows[i].update(decision='INTERPOLATED_SHORT_GAP',reason='Bounded linear gap; excluded from detection recall',evidence={'left_frame':left['frame'],'right_frame':right['frame']})
        return rows
