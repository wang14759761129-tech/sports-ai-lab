import json
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.fullmatch import (TimelineAction, apply_timeline_action, build_chunks,
                               cache_key, map_chunk_observation, merge_chunk_observations,
                               run_resumable_chunks)
from backend.full_match_pipeline import refresh_timeline_summary


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
    assert result["status"] == "BALLTRACK_COMPLETE"


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


def test_timeline_adjust_rejects_non_positive_interval():
    value = {"match_id": "match-1", "revision": 1, "games": [{"game_number": 1, "start_ms": 0,
             "end_ms": None, "points": [{"point_id": "p1", "game_number": 1, "point_number": 1,
             "start_ms": 100, "end_ms": 200, "rallies": []}]}], "scene_segments": []}
    with pytest.raises(ValueError, match="after start"):
        apply_timeline_action(value, TimelineAction(action="adjust", game_number=1,
                                                    point_number=1, start_ms=250, end_ms=200))


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
        assert client.get(f"/api/professional-matches/{match_id}/scoreboard-recognizer").json()["status"] == "EXPERIMENTAL"


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
