from copy import deepcopy
import pytest
from pydantic import ValidationError
from backend.video_sources import MatchVideoSource, official_source, source_counts


def source(**changes):
    return MatchVideoSource(provider="QA_ONLY", source_id="qa", source_url="https://example.com/qa", playback_type="OFFICIAL_PAGE", **changes)


def test_title_is_not_full_match_verification():
    with pytest.raises(ValidationError):
        source(is_full_match=True, full_match_verification="TITLE_CLAIM_ONLY")
    assert source().is_full_match is None


def test_verified_availability_needs_real_playback_record():
    with pytest.raises(ValidationError):
        source(availability_status="EMBED_PLAYBACK_VERIFIED")
    with pytest.raises(ValidationError):
        source(playback_verified=True)


def test_embedding_and_cloud_need_separate_permissions():
    with pytest.raises(ValidationError):
        source(availability_status="EMBED_PLAYBACK_VERIFIED", playback_verified=True, provenance={"playback_test": {"result": "QA_ONLY"}})
    with pytest.raises(ValidationError):
        source(availability_status="AUTHORIZED_STREAM_VERIFIED", playback_verified=True, provenance={"playback_test": {"result": "QA_ONLY"}})


@pytest.mark.parametrize("start,end,duration", [(None,10,None),(10,10,None),(11,10,None),(0,20,15)])
def test_long_stream_interval_is_not_invented(start,end,duration):
    with pytest.raises(ValidationError):
        source(match_start_seconds=start,match_end_seconds=end,duration=duration)


def test_multiple_matches_can_share_stream_with_distinct_intervals():
    a=source(match_start_seconds=0,match_end_seconds=10).model_dump()
    b=source(match_start_seconds=10,match_end_seconds=20).model_dump()
    assert a["source_id"] == b["source_id"]
    assert a["match_end_seconds"] == b["match_start_seconds"]


def test_login_and_legacy_embed_labels_do_not_prove_playback():
    row={"provider":"YOUTUBE_OFFICIAL","video_id":"qa","source_url":"https://www.youtube.com/watch?v=qa","full_match":True,"playback_status":"EMBED_VERIFIED", "watch_page_test":{"result":"NOT_PLAYABLE_IN_CURRENT_UNAUTHENTICATED_SESSION"}}
    original=deepcopy(row)
    projected=official_source(row)
    assert row == original
    assert projected["availability_status"] == "OFFICIAL_WATCH_PAGE"
    assert projected["is_full_match"] is None
    assert not projected["playback_verified"]
    assert source_counts([projected])["external_playback_verified"] == 0


def test_actual_external_play_is_separate_from_complete_and_internal():
    row={"provider":"YOUTUBE_OFFICIAL","video_id":"qa","source_url":"https://www.youtube.com/watch?v=qa","full_match":True,"watch_page_test":{"result":"ACTUAL_PLAYBACK_VERIFIED","surface":"BROWSER_IAB","observed_playing_times":[1,2]}}
    projected=official_source(row)
    counts=source_counts([projected])
    assert counts["external_playback_verified"] == 1
    assert counts["internal_playback_verified"] == 0
    assert counts["complete_matches_verified"] == 0
    row["watch_page_test"]["observed_playing_times"]=[2,2]
    assert official_source(row)["playback_verified"] is False
