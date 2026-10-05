from copy import deepcopy
from vision.postprocess import TTIBallTrackPostProcessor, PostProcessorConfig


def track(xs,scale=1,fps=30):
    return [dict(frame=i,timestamp_ms=i*1000/fps,visible=x is not None,
                 pixel_x=x*scale if x is not None else None,pixel_y=100*scale if x is not None else None,
                 confidence=.6) for i,x in enumerate(xs)]


def test_isolated_spike_is_annotated_preserving_raw():
    points=track([100,105,110,900,120,125,130]);original=deepcopy(points)
    result=TTIBallTrackPostProcessor().process(points,1000,500,30)
    assert result[3]['filter_reason']=='TEMPORAL_OUTLIER'
    assert result[3]['filtered_prediction']['visible']
    assert result[3]['raw_prediction']==original[3]
    assert points==original


def test_rejection_is_explicit_and_never_interpolates_missing_ball():
    result=TTIBallTrackPostProcessor(PostProcessorConfig(reject_suspects=True)).process(track([100,105,110,900,120,125,130]),1000,500,30)
    assert result[3]['filtered_prediction']['visible'] is False
    assert result[3]['filtered_prediction']['pixel_x'] is None
    missing=TTIBallTrackPostProcessor().process(track([100,None,110]),1000,500,30)
    assert missing[1]['filtered_prediction']['visible'] is False


def test_real_fast_continuous_motion_and_return_turn_are_retained():
    processor=TTIBallTrackPostProcessor(PostProcessorConfig(reject_suspects=True))
    for xs in ([100,200,300,400,500,600,700],[100,130,160,190,160,130,100]):
        result=processor.process(track(xs),1000,500,30)
        assert all(p['filter_reason'] is None for p in result)


def test_decisions_scale_with_resolution_and_time():
    processor=TTIBallTrackPostProcessor()
    a=processor.process(track([100,105,110,900,120,125,130]),1000,500,30)
    b=processor.process(track([100,105,110,900,120,125,130],scale=2),2000,1000,30)
    assert [p['filter_reason'] for p in a]==[p['filter_reason'] for p in b]


def test_static_prior_only_marks_suspect_by_default():
    points=track([100]*30)
    result=TTIBallTrackPostProcessor().process(points,1000,500,30)
    assert any(p['filter_reason']=='STATIC_PERSISTENCE' for p in result)
    assert all(p['filtered_prediction']['visible'] for p in result)
