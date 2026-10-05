from vision.hardening import collect_errors, combine_metrics
from scripts.download_vision_holdout import make_split


def test_error_dataset_retains_all_failure_types_and_neighbors():
    points=[dict(frame=i,visible=x is not None,pixel_x=x,pixel_y=0 if x is not None else None,confidence=.6) for i,x in enumerate([None,10,900,12])]
    gt={0:dict(visible=True,x=1,y=0),1:dict(visible=False,x=0,y=0),2:dict(visible=True,x=1,y=0)}
    errors=collect_errors('tabletennis/match1/000','video.mp4',points,gt,1000,500)
    assert {x['failure'] for x in errors}=={'MISSED_GT','FALSE_POSITIVE_ON_ANNOTATED_NEGATIVE','HIGH_POSITION_ERROR'}
    assert all(x['classification']=='UNKNOWN' for x in errors)
    assert errors[2]['previous_prediction']==points[1] and errors[2]['next_prediction']==points[3]
    assert errors[2]['model_output']['confidence']==.6


def test_split_is_disjoint_and_does_not_read_gt():
    official=[(f'match{i}',f'{j:03d}') for i in range(5) for j in range(3)]
    dev=[f'tabletennis/match{i}/000' for i in range(5)]
    split=make_split(dev,official)
    assert len(split['holdout'])==5
    assert not set(dev)&set(split['holdout'])
    assert all(x.endswith('/001') for x in split['holdout'])


def test_aggregate_reports_recall_and_conditional_errors_separately():
    metrics={'visible_gt_frames':3,'detected_visible_frames':2,'annotated_negative_frames':1,'false_detections':1}
    data=combine_metrics([{'raw':metrics,'raw_errors':[1,100]}],'raw')
    assert data['recall']==2/3 and data['false_positives']==1
    assert data['mean_error_px']==50.5 and data['co_visible_samples']==2
