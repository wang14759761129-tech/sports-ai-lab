import json
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.fullmatch import (TimelineAction, apply_timeline_action, build_chunks,
                               cache_key, map_chunk_observation, merge_chunk_observations,
                               run_resumable_chunks, source_identity, extract_source_frame_timestamps,
                               system_resource_snapshot, ResourceGuardStop, ResourceTrendGuard)
from backend.full_match_pipeline import refresh_manifest_artifact, refresh_timeline_summary


def test_chunk_boundaries_cover_long_video_without_gaps_or_overlap():
    total = 47 * 60 * 50
    chunks = build_chunks(total, 50, 60)
    assert len(chunks) == 47
    assert chunks[0]["source_frame_start"] == 0
    assert chunks[0]["source_frame_end"] == 2999
    assert chunks[1]["source_frame_start"] == 3000
    assert chunks[-1]["end_frame_exclusive"] == total
    assert all(a["end_frame_exclusive"] == b["start_frame_inclusive"] for a, b in zip(chunks, chunks[1:]))


def test_chunk_frame_and_timestamp_mapping_uses_global_timeline():
    chunks = build_chunks(8, 2, 2, [0, 490, 1010, 1510, 2010, 2490, 3010, 3520])
    assert map_chunk_observation(chunks[1], 1, 2, [0, 490, 1010, 1510, 2010, 2490, 3010, 3520]) == {
        "global_frame": 5, "source_frame": 5, "processed_frame": 5, "timestamp_ms": 2490}
    with pytest.raises(ValueError, match="outside"):
        map_chunk_observation(chunks[1], 4, 2)


def test_merge_keeps_raw_observations_and_rejects_duplicate_global_frames():
    chunks = [{"chunk_index": 1, "status": "COMPLETE", "observations": [{"global_frame": 2, "x": 3}]},
              {"chunk_index": 0, "status": "COMPLETE", "observations": [{"global_frame": 1, "x": 4}]}]
    assert [row["global_frame"] for row in merge_chunk_observations(chunks)] == [1, 2]
    chunks[0]["observations"].append({"global_frame": 1, "x": 99})
    with pytest.raises(ValueError, match="Duplicate global frame"):
        merge_chunk_observations(chunks)


def test_cache_key_binds_all_reproducibility_inputs():
    key = cache_key("video", "checkpoint", "config", "v1")
    assert key != cache_key("video2", "checkpoint", "config", "v1")
    assert key != cache_key("video", "checkpoint2", "config", "v1")
    assert key != cache_key("video", "checkpoint", "config2", "v1")
    assert key != cache_key("video", "checkpoint", "config", "v2")


def test_failed_chunk_resumes_at_first_incomplete_chunk(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "QUEUED", "chunks": [
        {"chunk_index": i, "status": "PENDING"} for i in range(3)]}), encoding="utf-8")
    calls = []

    def fail_second(chunk):
        calls.append(chunk["chunk_index"])
        if chunk["chunk_index"] == 1:
            raise RuntimeError("synthetic interruption")
        return {"observations": []}

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        run_resumable_chunks(path, fail_second)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [chunk["status"] for chunk in saved["chunks"]] == ["COMPLETE", "FAILED", "PENDING"]
    resumed_calls = []
    result = run_resumable_chunks(path, lambda chunk: resumed_calls.append(chunk["chunk_index"]) or {"observations": []})
    assert calls == [0, 1]
    assert resumed_calls == [1, 2]
    assert result["status"] == "CHUNKS_COMPLETE"
    assert result["resume_count"] == 1
    assert result["chunks"][1]["attempt_count"] == 2


def test_resource_guard_uses_machine_relative_start_pause_and_trend_thresholds():
    gib = 1024 ** 3
    snapshot = {"total_ram_bytes": 16 * gib, "available_ram_bytes": 5 * gib}
    guard = ResourceTrendGuard(snapshot)
    assert guard.start_bytes == 4 * gib
    assert ResourceTrendGuard(snapshot, minimum_start_gib=2).start_bytes == 4 * gib
    assert guard.start_check({**snapshot, "available_ram_bytes": int(3.9 * gib)})["allowed"] is False
    assert guard.start_check(snapshot)["allowed"] is True

    base_time = time.monotonic() + 1
    first = guard.observe({**snapshot, "available_ram_bytes": 5 * gib}, now=base_time)
    trend = guard.observe({**snapshot, "available_ram_bytes": int(3.6 * gib)}, now=base_time + 10)
    assert first["pause"] is False
    assert trend["pause"] is True
    assert trend["reason"] == "RESOURCE_GUARD_DECLINING_RAM_TREND"
    low = guard.observe({**snapshot, "available_ram_bytes": int(2.3 * gib)}, now=base_time + 11)
    assert low["reason"] == "RESOURCE_GUARD_LOW_AVAILABLE_RAM"


def test_resource_interruption_checkpoints_incomplete_chunk_and_resumes_it(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "QUEUED", "cache_key": "cache-a", "video_sha256": "v" * 64,
                                "checkpoint_sha256": "c" * 64, "config_sha256": "f" * 64,
                                "chunks": [{"chunk_index": 0, "status": "PENDING"}]}), encoding="utf-8")

    def stop_for_resources(_chunk):
        raise ResourceGuardStop("RESOURCE_GUARD_LOW_AVAILABLE_RAM", {"available_ram_bytes": 100})

    paused = run_resumable_chunks(path, stop_for_resources)
    assert paused["status"] == "PAUSED"
    assert paused["pause_reason"] == "RESOURCE_GUARD_LOW_AVAILABLE_RAM"
    assert paused["chunks"][0]["status"] == "INTERRUPTED"
    assert paused["chunks"][0]["failure_class"] == "RESOURCE_GUARD"
    assert paused["chunks"][0]["cache_binding"]["video_sha256"] == "v" * 64

    completed = run_resumable_chunks(path, lambda _chunk: {"observations": []})
    assert completed["status"] == "CHUNKS_COMPLETE"
    assert completed["chunks"][0]["status"] == "COMPLETE"
    assert completed["chunks"][0]["attempt_count"] == 2


def test_chunk_batch_limit_checkpoints_and_resumes_without_reprocessing(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "QUEUED", "chunks": [
        {"chunk_index": i, "status": "PENDING"} for i in range(3)]}), encoding="utf-8")
    first_calls = []
    first = run_resumable_chunks(path,
        lambda chunk: first_calls.append(chunk["chunk_index"]) or {"observations": []},
        max_new_chunks=1)

    assert first_calls == [0]
    assert first["status"] == "PAUSED"
    assert first["pause_reason"] == "BATCH_LIMIT_REACHED"
    assert [chunk["status"] for chunk in first["chunks"]] == ["COMPLETE", "PENDING", "PENDING"]

    second_calls = []
    second = run_resumable_chunks(path,
        lambda chunk: second_calls.append(chunk["chunk_index"]) or {"observations": []},
        max_new_chunks=1)
    assert second_calls == [1]
    assert [chunk["status"] for chunk in second["chunks"]] == ["COMPLETE", "COMPLETE", "PENDING"]

    third_calls = []
    final = run_resumable_chunks(path,
        lambda chunk: third_calls.append(chunk["chunk_index"]) or {"observations": []})
    assert third_calls == [2]
    assert final["status"] == "CHUNKS_COMPLETE"
    # Each resume records the completed chunks it reused: one on resume 2,
    # then two on resume 3.
    assert final["cache_hits"] == 3


def test_resource_guard_pauses_before_marking_or_running_chunk(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "QUEUED", "chunks": [
        {"chunk_index": 0, "status": "PENDING"}]}), encoding="utf-8")
    execution_calls = []
    result = run_resumable_chunks(path,
        lambda chunk: execution_calls.append(chunk["chunk_index"]) or {},
        before_chunk=lambda _chunk: {"allowed": False, "reason": "RESOURCE_GUARD_BEFORE_CHUNK",
                                     "snapshot": {"available_ram_bytes": 512}})

    assert execution_calls == []
    assert result["status"] == "PAUSED"
    assert result["pause_reason"] == "RESOURCE_GUARD_BEFORE_CHUNK"
    assert result["chunks"][0]["status"] == "PENDING"
    assert result["resource_guard_snapshot"]["available_ram_bytes"] == 512


def test_resource_snapshot_uses_windows_ram_fallback_without_psutil(monkeypatch):
    import backend.fullmatch as fullmatch

    def unavailable_nvidia_smi(*_args, **_kwargs):
        raise FileNotFoundError("nvidia-smi unavailable")

    monkeypatch.setitem(sys.modules, "psutil", None)
    monkeypatch.setattr(fullmatch, "_windows_available_ram_bytes", lambda: 3 * 1024 ** 3)
    monkeypatch.setattr(fullmatch.subprocess, "run", unavailable_nvidia_smi)

    snapshot = system_resource_snapshot()

    assert snapshot["available_ram_bytes"] == 3 * 1024 ** 3
    assert snapshot["gpu_memory_free_mib"] is None


def test_validation_records_final_manifest_hash(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"status":"BALLTRACK_COMPLETE"}', encoding="utf-8")
    validation = {"artifacts": {"manifest.json": {"sha256": "stale"}}}

    refresh_manifest_artifact(validation, manifest_path)

    assert validation["artifacts"]["manifest.json"]["exists"] is True
    assert validation["artifacts"]["manifest.json"]["size_bytes"] == manifest_path.stat().st_size
    assert validation["artifacts"]["manifest.json"]["sha256"] == source_identity(manifest_path)["sha256"]


def test_complete_checkpoint_artifact_corruption_fails_closed(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text("[]", encoding="utf-8")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"status": "PAUSED", "chunks": [{"chunk_index": 0,
        "status": "COMPLETE", "raw_prediction_path": str(raw), "raw_prediction_sha256": "wrong"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="CORRUPT_CHECKPOINT"):
        run_resumable_chunks(path, lambda chunk: {})


def test_legacy_complete_chunk_without_resource_log_remains_resumable(tmp_path):
    import hashlib

    artifacts = {}
    for key in ("raw_prediction", "observations", "runtime"):
        file_path = tmp_path / f"{key}.json"
        file_path.write_text("{}", encoding="utf-8")
        artifacts[f"{key}_path"] = str(file_path)
        artifacts[f"{key}_sha256"] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    chunk = {"chunk_index": 0, "status": "COMPLETE", **artifacts}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"status": "PAUSED", "chunks": [chunk]}), encoding="utf-8")

    result = run_resumable_chunks(manifest_path, lambda _chunk: pytest.fail("complete chunk reran"))

    assert result["chunks"][0]["status"] == "COMPLETE"


def test_source_identity_detects_mutation_and_move(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"authorized qa input")
    identity = source_identity(source)
    source.write_bytes(b"changed authorized qa input")
    changed = source_identity(source)
    assert changed["sha256"] != identity["sha256"]
    moved = tmp_path / "moved.mp4"
    source.rename(moved)
    with pytest.raises(FileNotFoundError):
        source_identity(source)


def test_vfr_fixture_uses_source_presentation_timestamps(tmp_path):
    source = tmp_path / "variable-rate.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=320x240:rate=10:duration=2", "-vf",
        "setpts=if(lt(N\\,10)\\,N\\,10+2*(N-10))", "-fps_mode", "vfr", "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-y", str(source)], check=True)
    from vision.quality import video_metadata
    metadata = video_metadata(source)
    timestamps = extract_source_frame_timestamps(source, metadata["frame_count"])
    assert metadata["rate_variable"] is True
    assert len(timestamps) == metadata["frame_count"] == 20
    assert timestamps[-1] > 1000 / metadata["fps"] * (len(timestamps) - 1)
    chunks = build_chunks(len(timestamps), metadata["fps"], 1, timestamps)
    mapped = [map_chunk_observation(chunk, local, metadata["fps"], timestamps)
              for chunk in chunks for local in range(chunk["expected_processed_frames"])]
    assert all(a["global_frame"] < b["global_frame"] for a, b in zip(mapped, mapped[1:]))


def test_manual_timeline_accept_adjust_split_merge_and_scene_labels():
    value = {"match_id": "match-1", "revision": 1, "games": [], "scene_segments": []}
    value = apply_timeline_action(value, TimelineAction(action="add_game", game_number=1, game_start_ms=0))
    value = apply_timeline_action(value, TimelineAction(action="add_point", game_number=1,
                                                        start_ms=1000, end_ms=4000))
    value = apply_timeline_action(value, TimelineAction(action="accept", game_number=1, point_number=1))
    assert value["games"][0]["points"][0]["review_status"] == "ACCEPTED"
    value = apply_timeline_action(value, TimelineAction(action="split", game_number=1,
                                                        point_number=1, split_at_ms=2500))
    assert [(p["start_ms"], p["end_ms"]) for p in value["games"][0]["points"]] == [(1000, 2500), (2500, 4000)]
    value = apply_timeline_action(value, TimelineAction(action="merge", game_number=1,
                                                        point_number=1, next_point_number=2))
    assert len(value["games"][0]["points"]) == 1
    value = apply_timeline_action(value, TimelineAction(action="add_scene", start_ms=0, end_ms=5000))
    scene_id = value["scene_segments"][0]["scene_id"]
    assert value["scene_segments"][0]["scene_type"] == "UNKNOWN"
    value = apply_timeline_action(value, TimelineAction(action="label_scene", scene_id=scene_id,
                                                        scene_type="PLAY_VIEW", note="Human reviewed"))
    assert value["scene_segments"][0]["scene_type"] == "PLAY_VIEW"
    assert value["games"][0]["points"][0]["scorer_id"] is None
    value = apply_timeline_action(value, TimelineAction(action="delete_point", game_number=1, point_number=1))
    assert value["games"][0]["points"] == []


def test_manual_timeline_can_delete_game_and_accept_scene_taxonomy():
    value = {"match_id": "m", "revision": 0, "games": [], "scene_segments": []}
    value = apply_timeline_action(value, TimelineAction(action="add_game", game_number=1, game_start_ms=0))
    value = apply_timeline_action(value, TimelineAction(action="delete_game", game_number=1))
    assert value["games"] == []
    value = apply_timeline_action(value, TimelineAction(action="add_scene", start_ms=0, end_ms=1000))
    scene_id = value["scene_segments"][0]["scene_id"]
    value = apply_timeline_action(value, TimelineAction(action="label_scene", scene_id=scene_id,
                                                        scene_type="REPLAY"))
    assert value["scene_segments"][0]["scene_type"] == "REPLAY"


def test_timeline_adjust_rejects_non_positive_interval():
    value = {"match_id": "match-1", "revision": 1, "games": [{"game_number": 1, "start_ms": 0,
             "end_ms": None, "points": [{"point_id": "p1", "game_number": 1, "point_number": 1,
             "start_ms": 100, "end_ms": 200, "rallies": []}]}], "scene_segments": []}
    with pytest.raises(ValueError, match="after start"):
        apply_timeline_action(value, TimelineAction(action="adjust", game_number=1,
                                                    point_number=1, start_ms=250, end_ms=200))


def test_timeline_split_rejects_cutting_through_manual_rally():
    value = {"match_id": "m", "revision": 0, "games": [], "scene_segments": []}
    value = apply_timeline_action(value, TimelineAction(action="add_game", game_number=1, game_start_ms=0))
    value = apply_timeline_action(value, TimelineAction(action="add_point", game_number=1,
                                                        start_ms=1000, end_ms=5000))
    value = apply_timeline_action(value, TimelineAction(action="add_rally", game_number=1,
        point_number=1, rally_start_ms=1200, rally_end_ms=4800))
    with pytest.raises(ValueError, match="Adjust rally boundaries"):
        apply_timeline_action(value, TimelineAction(action="split", game_number=1,
            point_number=1, split_at_ms=2500))


def _video(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=size=320x240:rate=25:duration=1", "-c:v", "libx264", "-y", str(path)], check=True)
    return path


def test_wtt_inbox_inspects_only_its_folder_and_imports_with_rights_metadata(tmp_path):
    db = tmp_path / "db" / "matches.sqlite"
    app = create_app(db)
    with TestClient(app) as client:
        inbox = Path(client.get("/api/professional-matches/inbox").json()["inbox_directory"])
        inbox_video = _video(inbox / "WANG-Chuqin-vs-Matsushima.mp4")
        outside = _video(tmp_path / "outside" / "not-in-inbox.mp4")
        listing = client.get("/api/professional-matches/inbox").json()
        assert len(listing["items"]) == 1
        item = listing["items"][0]
        assert item["match_status"] == "REVIEW_REQUIRED"
        assert set(item["candidate_athlete_ids"]) == {"athlete:121558", "athlete:135996"}
        assert item["video"]["frame_count"] == 25

        metadata = {"event_name": "Licensed WTT Match", "player_a_id": "athlete:121558",
                    "player_b_id": "athlete:135996", "external_reference_url": "https://www.worldtabletennis.com/eventInfo?eventId=3379",
                    "wtt_asset_id": "WTT-TEST-001", "licence_reference": "LIC-TEST-001"}
        result = client.post("/api/professional-matches/inbox/import", data={
            "inbox_id": item["inbox_id"], "metadata": json.dumps(metadata),
            "rights_confirmed": "true", "video_source_note": "授权文件；许可仅用于本机研究"})
        assert result.status_code == 201, result.text
        record = result.json()
        assert record["video_source_type"] == "LICENSED_WTT_LOCAL"
        assert record["rights_status"] == "LICENSED_FOR_ANALYSIS"
        assert record["video_metadata"]["sha256"] == item["sha256"]
        assert Path(record["video_local_path"]) == inbox_video.resolve()
        quality = client.get(f"/api/vision/professional-matches/{record['match_id']}/full-match/quality?device=cpu")
        assert quality.status_code == 200, quality.text
        assert quality.json()["estimated_frames"] == 25
        assert quality.json()["estimated_chunk_count"] == 1
        assert outside.exists()  # The inbox endpoint did not inspect or move an outside file.
        duplicate = client.post("/api/professional-matches/inbox/import", data={
            "inbox_id": item["inbox_id"], "metadata": json.dumps(metadata),
            "rights_confirmed": "true", "video_source_note": "duplicate"})
        assert duplicate.status_code == 409


def test_wtt_file_picker_import_copies_selected_download_into_inbox(tmp_path):
    source = _video(tmp_path / "Downloads" / "licensed-final.mp4")
    metadata = {"event_name": "Selected WTT video", "player_a_id": "athlete:121558",
                "player_b_id": "athlete:123980", "external_reference_url": "https://www.worldtabletennis.com/eventInfo?eventId=1",
                "wtt_asset_id": "WTT-ASSET", "licence_reference": "LICENSE-ID"}
    with TestClient(create_app(tmp_path / "db" / "matches.sqlite")) as client:
        response = client.post("/api/professional-matches/inbox/import", data={
            "metadata": json.dumps(metadata), "rights_confirmed": "true",
            "video_source_note": "Officially licensed local copy"},
            files={"file": (source.name, source.read_bytes(), "video/mp4")})
        assert response.status_code == 201, response.text
        imported = Path(response.json()["video_local_path"])
        assert imported.parent.name == "wtt"
        assert imported.read_bytes() == source.read_bytes()
        assert source.exists()


def test_wtt_file_picker_stage_returns_metadata_before_match_registration(tmp_path):
    source = _video(tmp_path / "Downloads" / "licensed-final.mp4")
    with TestClient(create_app(tmp_path / "db" / "matches.sqlite")) as client:
        before = len(client.get("/api/professional-matches").json())
        response = client.post("/api/professional-matches/inbox/stage", data={
            "rights_confirmed": "true", "video_source_note": "WTT official license"},
            files={"file": (source.name, source.read_bytes(), "video/mp4")})
        assert response.status_code == 200, response.text
        item = response.json()
        assert item["sha256"]
        assert item["video"]["duration"] > 0
        assert item["video"]["width"] == 320
        assert item["match_status"] == "REVIEW_REQUIRED"
        assert len(client.get("/api/professional-matches").json()) == before
        assert source.exists()


def test_persistent_timeline_actions_and_revision_conflict(tmp_path):
    with TestClient(create_app(tmp_path / "db" / "matches.sqlite")) as client:
        match = client.post("/api/professional-matches", json={
            "event_name": "Timeline test", "player_a_id": "athlete:121558", "player_b_id": "athlete:123980"})
        assert match.status_code == 201
        match_id = match.json()["match_id"]
        base = f"/api/professional-matches/{match_id}/timeline"
        assert client.get(base).json()["revision"] == 0
        game = client.post(base + "/actions?expected_revision=0", json={
            "action": "add_game", "game_number": 1, "game_start_ms": 0})
        assert game.status_code == 200 and game.json()["revision"] == 1
        point = client.post(base + "/actions?expected_revision=1", json={
            "action": "add_point", "game_number": 1, "start_ms": 1000, "end_ms": 5000})
        assert point.status_code == 200
        score = client.post(base + "/actions?expected_revision=2", json={
            "action": "set_score", "game_number": 1, "point_number": 1,
            "score_after": {"player_a": 1, "player_b": 0}, "note": "Observed on scoreboard"})
        assert score.status_code == 200
        rally = client.post(base + "/actions?expected_revision=3", json={
            "action": "add_rally", "game_number": 1, "point_number": 1,
            "rally_start_ms": 1100, "rally_end_ms": 4800})
        assert rally.status_code == 200
        stale = client.post(base + "/actions?expected_revision=3", json={
            "action": "accept", "game_number": 1, "point_number": 1})
        assert stale.status_code == 409
        timeline = client.get(base).json()
        assert timeline["games"][0]["points"][0]["score_after"] == {"player_a": 1, "player_b": 0}
        assert timeline["games"][0]["points"][0]["rallies"][0]["evidence"]["source"] == "MANUAL"
        assert client.get(f"/api/professional-matches/{match_id}/scoreboard-recognizer").json()["status"] == "DISABLED_EXPERIMENTAL"


def test_manual_timeline_updates_full_match_summary_artifacts(tmp_path):
    with TestClient(create_app(tmp_path / "db" / "matches.sqlite")) as client:
        match = client.post("/api/professional-matches", json={
            "event_name": "Timeline test", "player_a_id": "athlete:121558", "player_b_id": "athlete:123980"}).json()
        match_id = match["match_id"]
        output = tmp_path / "outputs" / "safe-match-id"
        output.mkdir(parents=True)
        summary_path = output / "full_match_summary.json"
        summary_path.write_text(json.dumps({"match_id": match_id, "games": 0, "points": 0, "rallies": 0,
            "analysis_completeness": {"full_match_balltrack": True}}), encoding="utf-8")
        client.app.state.repository.save_full_match_job(match_id, {"status": "BALLTRACK_COMPLETE", "output_dir": str(output)})
        timeline = {"match_id": match_id, "revision": 0, "games": [], "scene_segments": []}
        updated = apply_timeline_action(timeline, TimelineAction(action="add_game", game_number=1, game_start_ms=0))
        updated = apply_timeline_action(updated, TimelineAction(action="add_point", game_number=1, start_ms=100, end_ms=400))
        refresh_timeline_summary(client.app.state.repository, match_id, updated)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert (summary["games"], summary["points"], summary["rallies"]) == (1, 1, 0)
        assert (output / "match_timeline.json").is_file()
        assert "1" in (output / "full_match_report.html").read_text(encoding="utf-8")
