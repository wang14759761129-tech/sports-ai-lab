"""Denominator audit and conservative product display gates, not scientific validation."""
from collections import Counter
UNCERTAIN={'unknown','unclear','not_applicable'}
MIN_TACTICAL=5
MAX_UNCERTAINTY=.30

def known(value): return bool(value) and value not in UNCERTAIN
def numeric(value): return known(value) and str(value).isdigit() and int(value)>0

def quality(rows,field,conditional=False):
    counts=Counter(r.get(field,'') for r in rows)
    unresolved=sum(r.get('third_ball_attack') in {'unknown','unclear',''} for r in rows) if conditional else 0
    eligible=[r for r in rows if r.get('third_ball_attack')=='yes' and r.get(field)!='not_applicable'] if conditional else [r for r in rows if r.get(field)!='not_applicable']
    absent=sum(not r.get(field) for r in eligible)
    unknown=sum(r.get(field)=='unknown' for r in eligible);unclear=sum(r.get(field)=='unclear' for r in eligible)
    return dict(eligible_rows=len(eligible),unknown=unknown,unclear=unclear,not_applicable=counts['not_applicable'],missing=absent,uncertainty_rate=(unknown+unclear)/len(eligible) if eligible else None,unresolved_eligibility=unresolved,known_rows=sum(known(r.get(field)) for r in eligible),row_label_counts=dict(counts))

def guard(metric,rows,field=None,tactical=False,denominator_source=None):
    q=quality(rows,field) if field else dict(eligible_rows=len(rows),unknown=0,unclear=0,not_applicable=0,missing=0,uncertainty_rate=0 if rows else None,unresolved_eligibility=0,known_rows=len(rows))
    metric.update(q)
    metric['excluded_rows']=len(rows)-metric['denominator']
    metric['minimum_denominator']=MIN_TACTICAL if tactical else 1
    metric['denominator_source']=denominator_source or field or 'validated match-state rows'
    if field and not any(r.get(field) for r in rows): state='NOT_AVAILABLE'
    elif metric['denominator']<metric['minimum_denominator']: state='INSUFFICIENT_EVIDENCE'
    elif tactical and q['eligible_rows'] and (q['unknown']+q['unclear']+q['missing'])/q['eligible_rows']>MAX_UNCERTAINTY: state='INSUFFICIENT_EVIDENCE'
    else: state='AVAILABLE'
    metric['evidence_state']=state
    if state!='AVAILABLE': metric['value']=None;metric['status']='insufficient data'
    return metric

def decorate(players,rows):
    for p,m in players.items():
        serves=[r for r in rows if r['server']==p];receives=[r for r in rows if r['server']!=p]
        for key,subset in [('points_won',rows),('serve_win',serves),('receive_win',receives)]: guard(m[key],subset)
        guard(m['third_ball_attack'],serves,'third_ball_attack',True,'classified yes/no service opportunities')
        guard(m['third_ball_win'],serves,'third_ball_attack',True,'confirmed yes attacks with validated point winner')
        m['third_ball_win']['unresolved_eligibility']=sum(r.get('third_ball_attack') in {'unknown','unclear',''} for r in serves)
        guard(m['average_rally'],rows,'rally_length',True)
        for metric in m['rally_bands'].values(): guard(metric,rows,'rally_length',True)
        for key,field,subset in [('by_serve_placement','serve_placement',serves),('by_serve_type','serve_type',serves),('by_receive_type','receive_type',receives),('by_phase','point_phase',rows)]:
            for metric in m[key].values(): guard(metric,subset,field,True)
        for key in ['by_server','by_receiver']:
            for metric in m[key].values(): guard(metric,rows)
    fields=['serve_placement','serve_type','receive_type','third_ball_attack','rally_length','point_phase','outcome','source_serve_length','source_serve_location','source_third_ball_side','source_third_ball_outcome']
    return {f:quality(rows,f,conditional=f in {'source_third_ball_side','source_third_ball_outcome'}) for f in fields}
