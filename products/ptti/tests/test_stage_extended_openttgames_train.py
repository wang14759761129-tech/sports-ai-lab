from pathlib import Path
import hashlib
import re

import pytest

import scripts.stage_extended_openttgames_train as stager
from scripts.stage_extended_openttgames_train import (
    EXPECTED_BYTES,
    _stream_train_video,
    stage,
)


def test_staging_allowlist_contains_only_the_five_train_videos():
    assert set(EXPECTED_BYTES) == {f"game_{number}" for number in range(1, 6)}


def test_stager_refuses_test_split_names_before_network_or_file_creation(tmp_path):
    destination = tmp_path / "test_1.mp4"

    with pytest.raises(ValueError, match="ONLY_ALLOWLISTED_TRAIN_GAMES"):
        _stream_train_video("test_1", destination)

    assert not destination.exists()


def test_stager_refuses_paths_outside_ptti_dev(tmp_path):
    with pytest.raises(ValueError, match="MUST_BE_PTTI_DEV_DATASET_ROOT"):
        stage(["game_1"], root=tmp_path)


def test_existing_wrong_sized_video_is_never_overwritten(tmp_path):
    destination = tmp_path / "game_1.mp4"
    destination.write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="REFUSING_OVERWRITE"):
        _stream_train_video("game_1", destination)

    assert destination.read_bytes() == b"existing"


def test_range_downloader_resumes_partial_and_verifies_exact_bytes(tmp_path, monkeypatch):
    payload = bytes((index % 251 for index in range(2048)))
    monkeypatch.setitem(stager.EXPECTED_BYTES, "game_1", len(payload))
    destination = tmp_path / "game_1.mp4"
    partial = destination.with_suffix(".mp4.partial")
    partial.write_bytes(payload[:700])
    requested_ranges = []

    class Response:
        status = 206

        def __init__(self, first, last):
            self.headers = {"Content-Range": f"bytes {first}-{last}/{len(payload)}"}
            self.body = payload[first:last + 1]
            self.offset = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if size < 0:
                size = len(self.body) - self.offset
            part = self.body[self.offset:self.offset + size]
            self.offset += len(part)
            return part

    def fake_urlopen(request, timeout):
        assert timeout == 60
        first, last = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", request.get_header("Range")).groups())
        requested_ranges.append((first, last))
        return Response(first, last)

    monkeypatch.setattr(stager, "urlopen", fake_urlopen)

    result = _stream_train_video("game_1", destination)

    assert requested_ranges == [(700, len(payload) - 1)]
    assert destination.read_bytes() == payload
    assert not partial.exists()
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["status"] == "STAGED"
