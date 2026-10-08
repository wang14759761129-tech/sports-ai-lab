import csv
import json
import subprocess
import tracemalloc
from pathlib import Path

import pytest

from backend.full_match_pipeline import generate_preview_overlays


def _observations(path, count):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["global_frame", "visible", "x", "y", "raw_model_score"])
        writer.writeheader()
        for frame in range(count):
            writer.writerow({"global_frame": frame, "visible": True, "x": 123, "y": 456,
                             "raw_model_score": .61})


def test_long_csv_preview_memory_is_bounded_by_selected_windows(tmp_path, monkeypatch, record_property):
    source = tmp_path / "observations.csv"
    _observations(source, 60000)
    captured = []

    def run(command, **_kwargs):
        if command[0] != "ffmpeg":
            captured.append(json.loads(Path(command[-2]).read_text(encoding="utf-8")))
        Path(command[-1]).write_bytes(b"QA encoded preview")

    monkeypatch.setattr("backend.full_match_pipeline.subprocess.run", run)
    tracemalloc.start()
    try:
        previews = generate_preview_overlays(tmp_path / "video.mp4", source,
            {"duration": 2000, "fps": 30}, tmp_path, "qa-python")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert [item["frames"] for item in previews] == [900, 900, 900]
    assert all(rows[0]["frame"] == 0 and rows[-1]["frame"] == 899 for rows in captured)
    record_property("python_allocation_peak_bytes", peak)
    assert peak < 8 * 1024 ** 2, f"Preview materialized full CSV: peak={peak}"


@pytest.mark.parametrize("existing_preview", [False, True])
def test_failed_preview_does_not_publish_partial_video_and_cleans_temporary_files(tmp_path, monkeypatch, existing_preview):
    source = tmp_path / "observations.csv"
    _observations(source, 30)
    published = tmp_path / "preview_overlays" / "preview-01.mp4"
    if existing_preview:
        published.parent.mkdir()
        published.write_bytes(b"previous valid preview")

    def fail_encoder(command, **_kwargs):
        Path(command[-1]).write_bytes(b"incomplete")
        if command[0] != "ffmpeg":
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("backend.full_match_pipeline.subprocess.run", fail_encoder)
    with pytest.raises(subprocess.CalledProcessError):
        generate_preview_overlays(tmp_path / "video.mp4", source,
            {"duration": 1, "fps": 30}, tmp_path, "qa-python")
    if existing_preview:
        assert published.read_bytes() == b"previous valid preview"
    else:
        assert not published.exists()
    assert not list((tmp_path / "preview_overlays").glob("*.part.mp4"))
    assert not list((tmp_path / "preview_overlays").glob("*-source.mp4"))
    assert not list((tmp_path / "preview_overlays").glob("*.json"))
