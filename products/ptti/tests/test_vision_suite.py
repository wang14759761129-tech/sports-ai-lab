import pytest

from vision.suite import aggregate, _worst_observations, select_worst_cases


def test_suite_aggregate_weights_visible_frames_and_has_no_fake_pass_threshold():
    clips=[
        {'status':'ANALYZED','annotated_frames':4,'visible_gt_frames':3,'detected_visible_frames':2,
         'processing_seconds':2.0,'decoded_frames':20,'failure_modes':['missed_visible_annotations']},
        {'status':'ANALYZED','annotated_frames':2,'visible_gt_frames':2,'detected_visible_frames':2,
         'processing_seconds':1.0,'decoded_frames':10,'failure_modes':[]},
    ]
    result=aggregate(clips,[1.0,3.0,5.0,7.0])
    assert result['annotated_frames']==6
    assert result['overall_visible_recall']==pytest.approx(4/5)
    assert result['weighted_mean_position_error_px']==pytest.approx(4.0)
    assert result['clips_completed']==2
    assert result['clips_with_failure_modes']==1
    assert result['clips_passed'] is None
    assert result['aggregate_processing_fps']==pytest.approx(10.0)


def test_suite_worst_cases_use_only_annotated_frames():
    video='clip.mp4'
    prediction=[{'frame':0,'visible':True,'pixel_x':10.0,'pixel_y':10.0},
                {'frame':1,'visible':False,'pixel_x':0.0,'pixel_y':0.0},
                {'frame':2,'visible':True,'pixel_x':20.0,'pixel_y':30.0}]
    gt={0:{'visible':True,'x':10.0,'y':12.0},
        1:{'visible':True,'x':5.0,'y':5.0},
        2:{'visible':True,'x':20.0,'y':30.0},
        100:{'visible':True,'x':0.0,'y':0.0}}
    cases=_worst_observations(video,prediction,gt,'tabletennis/match/000')
    assert len(cases)==4
    assert sum(case['failure']=='missed_visible_annotation' for case in cases)==2
    assert all(case['classification']=='unknown' for case in cases)
    assert all(case['frame'] in gt for case in cases)


def test_worst_case_selection_includes_misses_and_large_localization_outliers():
    cases=[{'clip_id':f'clip{i}','frame':i,'failure':'missed_visible_annotation','error_px':None} for i in range(12)]
    cases.extend([{'clip_id':'outlier','frame':20,'failure':None,'error_px':460.0},
                  {'clip_id':'normal','frame':21,'failure':None,'error_px':5.0}])
    selected=select_worst_cases(cases,20)
    assert len(selected)==12
    assert any(item['error_px']==460.0 for item in selected)
    assert sum(item['failure']=='missed_visible_annotation' for item in selected)==10
