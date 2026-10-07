import hashlib
import json
from pathlib import Path

import pytest

import scripts.run_full_dev_game as runner


def _manifest(root, status="VERIFIED"):
    video = root / "videos" / "train" / "game_1.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    payload = b"authorized train fixture"
    video.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    value = {
        "dataset": "Extended OpenTTGames",
        "dataset_revision": "36471a76b969a0340df59258a813bf8214e68e7c",
        "games": [{"game": "game_1", "split_role": "DEV", "status": status,
                   "current_bytes": len(payload), "expected_bytes": len(payload),
                   "video_path": str(video.resolve()), "sha256": digest}],
    }
    manifest = root / "DEV_VIDEO_DOWNLOAD_MANIFEST.json"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    return video, manifest, payload


def test_full_dev_runner_accepts_only_verified_hash_matched_video(tmp_path, monkeypatch):
    video, manifest, payload = _manifest(tmp_path)
    monkeypatch.setitem(runner.EXPECTED_BYTES, "game_1", len(payload))

    resolved, identity = runner.resolve_verified_dev_video(1, tmp_path, manifest)

    assert resolved == video.resolve()
    assert identity["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("status", ["PAUSED", "COMPLETE_UNVERIFIED", "DOWNLOADING"])
def test_full_dev_runner_rejects_partial_or_unverified_video(tmp_path, monkeypatch, status):
    _video, manifest, payload = _manifest(tmp_path, status=status)
    monkeypatch.setitem(runner.EXPECTED_BYTES, "game_1", len(payload))

    with pytest.raises(ValueError, match="DEV_VIDEO_NOT_VERIFIED"):
        runner.resolve_verified_dev_video(1, tmp_path, manifest)


def test_full_dev_runner_never_accepts_calibration_or_holdout(tmp_path):
    with pytest.raises(ValueError, match="ONLY_DEV_GAMES_1_TO_3"):
        runner.resolve_verified_dev_video(4, tmp_path)


def test_full_dev_runner_rejects_changed_source_hash(tmp_path, monkeypatch):
    video, manifest, payload = _manifest(tmp_path)
    monkeypatch.setitem(runner.EXPECTED_BYTES, "game_1", len(payload))
    changed = b"X" * len(payload)
    video.write_bytes(changed)

    with pytest.raises(ValueError, match="SHA256_MISMATCH"):
        runner.resolve_verified_dev_video(1, tmp_path, manifest)
