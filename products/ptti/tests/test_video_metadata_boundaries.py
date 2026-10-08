import json
from types import SimpleNamespace

import pytest

from vision.quality import video_metadata


@pytest.mark.parametrize("field,value", [
    ("duration", "0"), ("duration", "-1"), ("duration", "NaN"), ("duration", "Infinity"),
    ("duration", "N/A"), ("avg_frame_rate", "30/0"), ("avg_frame_rate", "0/0"),
    ("avg_frame_rate", "0/1"), ("width", 0), ("height", -1),
])
def test_probe_rejects_invalid_timeline_dimensions_with_clear_value_error(tmp_path, monkeypatch, field, value):
    video = tmp_path / "中文 空格.mp4"
    video.write_bytes(b"ENGINEERING_QA_ONLY")
    stream = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
              "duration": "10", "avg_frame_rate": "120/1", "r_frame_rate": "120/1"}
    stream[field] = value
    monkeypatch.setattr("vision.quality.subprocess.run", lambda *_args, **_kwargs:
        SimpleNamespace(stdout=json.dumps({"streams": [stream], "format": {}})))
    with pytest.raises(ValueError, match="有效"):
        video_metadata(video)


def test_valid_fractional_fps_and_duration_are_preserved(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"ENGINEERING_QA_ONLY")
    stream = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
              "duration": "1.001", "avg_frame_rate": "30000/1001", "r_frame_rate": "30000/1001"}
    monkeypatch.setattr("vision.quality.subprocess.run", lambda *_args, **_kwargs:
        SimpleNamespace(stdout=json.dumps({"streams": [stream], "format": {}})))
    metadata = video_metadata(video)
    assert metadata["fps"] == 30000 / 1001
    assert metadata["duration"] == 1.001


def test_unavailable_stream_duration_uses_probed_container_duration(tmp_path, monkeypatch):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"ENGINEERING_QA_ONLY")
    stream = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
              "duration": "N/A", "avg_frame_rate": "120/1", "r_frame_rate": "120/1"}
    monkeypatch.setattr("vision.quality.subprocess.run", lambda *_args, **_kwargs:
        SimpleNamespace(stdout=json.dumps({"streams": [stream],
                                           "format": {"duration": "3.25", "bit_rate": "N/A"}})))
    metadata = video_metadata(video)
    assert metadata["duration"] == 3.25
    assert metadata["bitrate"] is None
