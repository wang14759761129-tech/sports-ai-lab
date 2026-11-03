"""Optional, evidence-preserving, offline trajectory plausibility checks.

No GT, guessed ball positions, player labels or hard table ROI enter decisions.
The default annotates suspects only. Rejection requires an explicit experiment.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict
import math
import statistics


@dataclass(frozen=True)
class PostProcessorConfig:
    version: str = 'tti-balltrack-postprocess-1'
    reject_suspects: bool = False
    neighbor_gap_seconds: float = .10
    history_seconds: float = .50
    velocity_floor_diagonals_per_second: float = .50
    velocity_multiplier: float = 6.0
    static_duration_seconds: float = .60
    static_radius_diagonals: float = .006
    static_visible_fraction: float = .90

    def __post_init__(self):
        for key,value in asdict(self).items():
            if isinstance(value,(float,int)) and not isinstance(value,bool) and (not math.isfinite(value) or value<=0):
                raise ValueError(f'Invalid postprocessor option: {key}')
        if self.static_visible_fraction>1: raise ValueError('Invalid visible fraction')


class TTIBallTrackPostProcessor:
    def __init__(self,config=None):
        self.config=config or PostProcessorConfig()

    def process(self,points,width,height,fps):
        if min(width,height,fps)<=0: raise ValueError('Invalid video geometry')
        if any(b['frame']<=a['frame'] for a,b in zip(points,points[1:])): raise ValueError('Frames must be strictly ordered')
        diagonal=math.hypot(width,height);cfg=self.config
        def distance(a,b): return math.hypot(a['pixel_x']-b['pixel_x'],a['pixel_y']-b['pixel_y'])/diagonal
        result=[]
        for i,p in enumerate(points):
            reason=None;details={}
            if p['visible']:
                previous=next((a for a in reversed(points[:i]) if a['visible']),None)
                following=next((a for a in points[i+1:] if a['visible']),None)
                if previous and following:
                    dt1=(p['frame']-previous['frame'])/fps;dt2=(following['frame']-p['frame'])/fps
                    if max(dt1,dt2)<=cfg.neighbor_gap_seconds:
                        nearby=[a for a in points if a['visible'] and 0<abs(a['frame']-p['frame'])/fps<=cfg.history_seconds]
                        speeds=[distance(a,b)/((b['frame']-a['frame'])/fps) for a,b in zip(nearby,nearby[1:])
                                if 0<(b['frame']-a['frame'])/fps<=cfg.neighbor_gap_seconds]
                        median_speed=statistics.median(speeds) if speeds else 0
                        limit=max(cfg.velocity_floor_diagonals_per_second,median_speed*cfg.velocity_multiplier)
                        # Both jumps must be implausible, while neighbors still form a plausible bridge.
                        before=distance(previous,p)/dt1;after=distance(p,following)/dt2
                        bridge=distance(previous,following)/(dt1+dt2)
                        details={'velocity_before':before,'velocity_after':after,'bridge_velocity':bridge,'velocity_limit':limit,
                                 'units':'frame diagonals per second','history_median_velocity':median_speed}
                        if min(before,after)>limit and bridge<=limit: reason='TEMPORAL_OUTLIER'
                half=cfg.static_duration_seconds/2
                window=[a for a in points if abs(a['frame']-p['frame'])/fps<=half]
                visible=[a for a in window if a['visible']]
                span=(window[-1]['frame']-window[0]['frame'])/fps if window else 0
                if reason is None and span>=cfg.static_duration_seconds-1/fps and len(visible)/len(window)>=cfg.static_visible_fraction:
                    center={'pixel_x':statistics.median(a['pixel_x'] for a in visible),'pixel_y':statistics.median(a['pixel_y'] for a in visible)}
                    radius=max(distance(center,a) for a in visible)
                    if radius<=cfg.static_radius_diagonals:
                        reason='STATIC_PERSISTENCE';details={'radius_diagonals':radius,'duration_seconds':span,'caution':'A real slow ball can also be stationary; annotation is not proof of a distractor.'}
            raw=deepcopy(p);filtered=deepcopy(p)
            rejected=bool(reason and cfg.reject_suspects)
            if rejected:
                filtered.update(visible=False,pixel_x=None,pixel_y=None,normalized_x=None,normalized_y=None)
            result.append({'frame':p['frame'],'raw_prediction':raw,'filtered_prediction':filtered,
                           'suspect':reason is not None,'rejected':rejected,'filter_reason':reason,'filter_details':details})
        return result
