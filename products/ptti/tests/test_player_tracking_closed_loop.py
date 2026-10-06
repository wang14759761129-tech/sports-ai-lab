import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.player_tracking_closed_loop import (
    append_manual_action,
    atomic_json,
    closed_loop_root,
    create_closed_loop_job,
    _player_tracking_validation_manifest,
    load_job_progress,
    queue_reacquisition,
    seed_detection_dir,
    seed_review_asset,
    list_closed_loop_samples,
)


RIGHTS = "CC BY-NC-SA 4.0 research/non-commercial"


def test_atomic_json_uses_unique_temporary_files_for_concurrent_progress_writes(tmp_path):
    target = tmp_path / "progress.json"
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda index: atomic_json(target, {"writer": index, "payload": [index] * 20}),
                      range(24)))
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["writer"] in range(24)
    assert result["payload"] == [result["writer"]] * 20
    assert list(tmp_path.glob("progress.json.*.tmp")) == []


def fixture_sample(local: Path):
    root = local / "PTTI-Dev" / "vision-v2-sam2"
    dataset = root / "datasets" / "extended-openttgames"
    dataset.mkdir(parents=True)
    clip = dataset / "game_4_t30_10s.mp4"
    clip.write_bytes(b"research-video-fixture")
    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
    manifest = {
        "dataset": "Extended OpenTTGames", "rights": RIGHTS, "commercial_use": False,
        "official_split": "TRAIN_ONLY; official test split not used",
        "videos": [{
            "video_id": "game_4-t30", "match_id": "game_4", "official_split": "TRAIN",
            "clip": {"file": clip.name, "start_seconds": 30,
                     "sha256": digest, "bytes": clip.stat().st_size,
                     "duration_seconds": 10.0, "frames": 300, "sample_fps": 30,
                     "source_fps": 120, "resolution": "1920x1080"},
            "seed_screening": {"status": "SEEDS_READY"},
        }],
    }
    manifest_path = root / "runs" / "multi-match-final" / "cross_match_validation.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return digest


def seed_detections(local: Path, digest: str, *, frame=4):
    detection_set_id = "a" * 64
    folder = seed_detection_dir("game_4-t30", frame, detection_set_id, local)
    folder.mkdir(parents=True)
    detections = [
        {"candidate_id": "player-near", "bbox": [1400, 250, 1780, 1040],
         "detector_score": 0.93, "detector": "RT-DETR R18"},
        {"candidate_id": "player-far", "bbox": [100, 300, 400, 920],
         "detector_score": 0.9, "detector": "RT-DETR R18"},
        {"candidate_id": "referee", "bbox": [840, 100, 1020, 410],
         "detector_score": 0.82, "detector": "RT-DETR R18"},
    ]
    (folder / "detections.json").write_text(json.dumps({
        "detection_set_id": detection_set_id, "sample_id": "game_4-t30",
        "frame_index": frame, "clip_sha256": digest, "detections": detections,
    }), encoding="utf-8")
    (folder / "seed-frame.jpg").write_bytes(b"source")
    (folder / "seed-overlay.jpg").write_bytes(b"overlay")
    return detection_set_id, detections


def test_sample_catalog_is_manifest_backed_and_does_not_expose_paths(tmp_path):
    digest = fixture_sample(tmp_path)
    samples = list_closed_loop_samples(tmp_path)
    assert len(samples) == 1
    assert samples[0]["clip_sha256"] == digest
    assert samples[0]["start_seconds"] == 30
    assert samples[0]["video_path"].is_file()

    public = {key: value for key, value in samples[0].items() if key != "video_path"}
    assert "source_path" not in public
    assert public["commercial_use"] is False


def test_sample_catalog_fails_closed_when_file_changed(tmp_path):
    fixture_sample(tmp_path)
    clip = tmp_path / "PTTI-Dev/vision-v2-sam2/datasets/extended-openttgames/game_4_t30_10s.mp4"
    clip.write_bytes(b"changed")
    assert list_closed_loop_samples(tmp_path) == []


def test_validation_manifest_requires_frozen_config_and_five_nonoverlapping_train_matches(tmp_path, monkeypatch):
    fixture_sample(tmp_path)
    config = tmp_path / "PLAYER_TRACKING_V1_CANDIDATE.json"
    config.write_text('{"locked":true}', encoding="utf-8")
    monkeypatch.setattr("backend.player_tracking_closed_loop._player_tracking_config_path", lambda: config)
    validation_root = (tmp_path / "PTTI-Dev/vision-v2-sam2/runs/player-tracking-v1-validation")
    validation_root.mkdir(parents=True)
    validation_dataset = tmp_path / "PTTI-Dev/vision-v2-sam2/datasets/extended-openttgames"
    validation_dataset.mkdir(parents=True, exist_ok=True)
    videos = []
    for game in range(1, 6):
        start = 60 if game == 4 else 45
        filename = f"game_{game}_t{start}_10s.mp4"
        clip_path = validation_dataset / filename
        clip_path.write_bytes(f"validation clip {game}".encode())
        digest = hashlib.sha256(clip_path.read_bytes()).hexdigest()
        videos.append({"video_id": f"game_{game}-t{start}", "match_id": f"game_{game}",
                       "official_split": "TRAIN", "clip": {"start_seconds": start,
                       "file": filename, "bytes": clip_path.stat().st_size, "sha256": digest,
                       "duration_seconds": 10.0, "frames": 300, "sample_fps": 30,
                       "source_fps": 120, "resolution": "1920x1080"},
                       "seed_screening": {"status": "PENDING_SEED_REVIEW"}})
    expected = hashlib.sha256(config.read_bytes()).hexdigest()
    manifest = {"schema_version": "player-tracking-v1-validation-set-v1",
                "dataset": "Extended OpenTTGames", "rights": RIGHTS,
                "commercial_use": False,
                "official_split": "TRAIN_ONLY; official test split not used",
                "evaluation_role": "FROZEN_VALIDATION", "frozen_config_sha256": expected,
                "videos": videos}
    path = validation_root / "validation_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert len(_player_tracking_validation_manifest(tmp_path)["videos"]) == 5
    catalog = list_closed_loop_samples(tmp_path)
    validation_catalog = [row for row in catalog if row["evaluation_role"] == "FROZEN_VALIDATION"]
    assert len(validation_catalog) == 5
    assert {row["validation_config_sha256"] for row in validation_catalog} == {expected}
    manifest["frozen_config_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="CONFIG_NOT_FROZEN"):
        _player_tracking_validation_manifest(tmp_path)


def test_validation_manifest_rejects_development_overlap(tmp_path, monkeypatch):
    fixture_sample(tmp_path)
    config = tmp_path / "PLAYER_TRACKING_V1_CANDIDATE.json"
    config.write_text("candidate", encoding="utf-8")
    monkeypatch.setattr("backend.player_tracking_closed_loop._player_tracking_config_path", lambda: config)
    validation_root = (tmp_path / "PTTI-Dev/vision-v2-sam2/runs/player-tracking-v1-validation")
    validation_root.mkdir(parents=True)
    videos = [{"video_id": f"game_{game}-t45", "match_id": f"game_{game}",
               "official_split": "TRAIN", "clip": {"start_seconds": 45,
               "duration_seconds": 10.0}, "seed_screening": {"status": "PENDING_SEED_REVIEW"}}
              for game in range(1, 6)]
    videos[3]["clip"]["start_seconds"] = 35
    manifest = {"schema_version": "player-tracking-v1-validation-set-v1",
                "dataset": "Extended OpenTTGames", "rights": RIGHTS,
                "commercial_use": False,
                "official_split": "TRAIN_ONLY; official test split not used",
                "evaluation_role": "FROZEN_VALIDATION",
                "frozen_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
                "videos": videos}
    (validation_root / "validation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="OVERLAPS_DEVELOPMENT"):
        _player_tracking_validation_manifest(tmp_path)


def test_manual_action_id_is_idempotent_and_replay_safe(tmp_path):
    digest = fixture_sample(tmp_path)
    detection_set_id, _ = seed_detections(tmp_path, digest)
    job_id, _, _ = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, localappdata=tmp_path)
    action_id = "a" * 32
    first = append_manual_action(job_id=job_id, action="mask_choice", action_id=action_id,
                                 details={"choice": "REVERSE"}, localappdata=tmp_path)
    second = append_manual_action(job_id=job_id, action="mask_choice", action_id=action_id,
                                  details={"choice": "REVERSE"}, localappdata=tmp_path)
    log = json.loads((closed_loop_root(tmp_path) / "jobs" / job_id / "manual-actions.json").read_text())
    assert first == second
    assert sum(row["action_id"] == action_id for row in log["actions"]) == 1


def test_confirmed_seed_creates_fixed_identity_job_and_preserves_raw(tmp_path):
    digest = fixture_sample(tmp_path)
    detection_set_id, raw = seed_detections(tmp_path, digest)
    original = json.loads(json.dumps(raw))
    job_id, root, seed = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, athlete_mapping={"NEAR_PLAYER": "athlete-1"}, localappdata=tmp_path,
    )
    assert root.is_relative_to(closed_loop_root(tmp_path) / "jobs")
    assert seed["raw_detections"] == original
    assert seed["selected_seeds"][0]["object_id"] == 1
    assert seed["selected_seeds"][1]["object_id"] == 2
    assert seed["timestamp_ms"] == 30133
    assert load_job_progress(job_id, tmp_path)["status"] == "QUEUED"
    assert seed_review_asset("game_4-t30", 4, detection_set_id, "overlay", tmp_path).read_bytes() == b"overlay"


def test_anchor_guided_job_pins_interval_without_changing_fixed_identity(tmp_path):
    digest = fixture_sample(tmp_path)
    detection_set_id, _ = seed_detections(tmp_path, digest)
    job_id, root, seed = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, tracking_architecture="DETECTION_ANCHORED_MASK_TRACKING",
        anchor_interval_seconds=0.5, localappdata=tmp_path,
    )
    assert seed["tracking_architecture"] == "DETECTION_ANCHORED_MASK_TRACKING"
    assert seed["anchor_interval_seconds"] == 0.5
    assert load_job_progress(job_id, tmp_path)["tracking_architecture"] == "DETECTION_ANCHORED_MASK_TRACKING"
    with pytest.raises(ValueError, match="UNSUPPORTED_ANCHOR_INTERVAL"):
        create_closed_loop_job(
            sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
            near_candidate_id="player-near", far_candidate_id="player-far",
            user_confirmed=True, tracking_architecture="DETECTION_ANCHORED_MASK_TRACKING",
            anchor_interval_seconds=0.75, localappdata=tmp_path,
        )


def test_closed_loop_job_rejects_unconfirmed_or_changed_seed_evidence(tmp_path):
    digest = fixture_sample(tmp_path)
    detection_set_id, _ = seed_detections(tmp_path, digest)
    with pytest.raises(ValueError, match="TWO_DISTINCT_USER_CONFIRMED_SEEDS_REQUIRED"):
        create_closed_loop_job(
            sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
            near_candidate_id="player-near", far_candidate_id="player-far",
            user_confirmed=False, localappdata=tmp_path,
        )
    with pytest.raises(FileNotFoundError, match="SEED_DETECTIONS_NOT_READY"):
        from backend.player_tracking_closed_loop import load_seed_detection
        load_seed_detection("game_4-t30", 4, "b" * 64, tmp_path)


def test_reacquisition_requires_waiting_state_and_server_observed_candidate(tmp_path):
    digest = fixture_sample(tmp_path)
    detection_set_id, _ = seed_detections(tmp_path, digest)
    job_id, root, _ = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, localappdata=tmp_path,
    )
    with pytest.raises(ValueError, match="REACQUISITION_NOT_WAITING_FOR_USER"):
        queue_reacquisition(job_id=job_id, role="FAR_PLAYER", candidate_id="referee", localappdata=tmp_path)
    progress = load_job_progress(job_id, tmp_path)
    progress["status"] = "NEEDS_USER_CONFIRMATION"
    (root / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
    (root / "review_candidates.json").write_text(json.dumps({
        "frame_index": 12, "requested_role": "FAR_PLAYER",
        "candidate_ids_by_role": {"NEAR_PLAYER": ["valid-person"], "FAR_PLAYER": ["far-person"]},
        "detections": [{"candidate_id": "valid-person", "bbox": [1, 2, 20, 30]},
                        {"candidate_id": "far-person", "bbox": [40, 2, 60, 30]}]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="REACQUISITION_CANDIDATE_NOT_FOUND"):
        queue_reacquisition(job_id=job_id, role="FAR_PLAYER", candidate_id="referee", localappdata=tmp_path)
    with pytest.raises(ValueError, match="REACQUISITION_CANDIDATE_ROLE_MISMATCH"):
        queue_reacquisition(job_id=job_id, role="FAR_PLAYER", candidate_id="valid-person", localappdata=tmp_path)
    queued = queue_reacquisition(job_id=job_id, role="FAR_PLAYER", candidate_id="far-person", localappdata=tmp_path)
    command = json.loads((root / "reacquisition-command.json").read_text(encoding="utf-8"))
    assert queued["object_id"] == command["object_id"] == 2


def test_closed_loop_desktop_api_keeps_jobs_in_ptti_dev_and_requires_user_seed(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    local = tmp_path / "local"
    digest = fixture_sample(local)
    detection_set_id, detections = seed_detections(local, digest)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PTTI_ENV", "test")
    monkeypatch.setenv("PTTI_DB", str(tmp_path / "test-db" / "matches.db"))

    product_root = Path(__file__).resolve().parents[1]
    script = product_root / "vision_worker" / "player_tracking_closed_loop.py"
    monkeypatch.setattr(vision_api, "closed_loop_worker_paths",
                        lambda: (product_root, script, Path(sys.executable)))

    class FakeProcess:
        def poll(self):
            return None

    launches = []
    monkeypatch.setattr(vision_api, "launch_closed_loop_worker",
                        lambda **kwargs: launches.append(kwargs) or FakeProcess())

    app = create_app(tmp_path / "test-db" / "matches.db")
    with TestClient(app) as client:
        sample_result = client.get("/api/vision/v2/player-tracking/closed-loop/samples")
        assert sample_result.status_code == 200
        assert "video_path" not in sample_result.json()["samples"][0]
        assert sample_result.json()["production_database"] == "NOT_ACCESSED"
        start = client.post("/api/vision/v2/player-tracking/closed-loop/jobs", json={
            "sample_id": "game_4-t30", "frame_index": 4,
            "detection_set_id": detection_set_id,
            "near_candidate_id": "player-near", "far_candidate_id": "player-far",
            "user_confirmed": True,
        })
        assert start.status_code == 200
        job_id = start.json()["job_id"]
        assert start.json()["object_ids"] == {"NEAR_PLAYER": 1, "FAR_PLAYER": 2}
        assert len(launches) == 1
        status = client.get(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["production_database"] == "NOT_ACCESSED"
        assert client.get(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}/assets/..%2F..%2Fmatches.db").status_code == 404

        refused = client.post("/api/vision/v2/player-tracking/closed-loop/jobs", json={
            "sample_id": "game_4-t30", "frame_index": 4,
            "detection_set_id": detection_set_id,
            "near_candidate_id": "player-near", "far_candidate_id": "player-far",
            "user_confirmed": False,
        })
        assert refused.status_code == 422
    assert app.state.database_path == (tmp_path / "test-db" / "matches.db").resolve()


def test_desktop_api_routes_anchor_guided_jobs_to_isolated_worker(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    local = tmp_path / "local"
    digest = fixture_sample(local)
    detection_set_id, _ = seed_detections(local, digest)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PTTI_ENV", "test")
    monkeypatch.setenv("PTTI_DB", str(tmp_path / "test-db" / "matches.db"))
    monkeypatch.setattr(vision_api, "_CLOSED_LOOP_PROCESSES", {})
    product_root = Path(__file__).resolve().parents[1]
    script = product_root / "vision_worker" / "anchor_guided_player_tracker.py"
    monkeypatch.setattr(vision_api, "anchor_guided_worker_paths",
                        lambda: (product_root, script, Path(sys.executable)))

    class FakeProcess:
        def poll(self):
            return None

    launches = []
    monkeypatch.setattr(vision_api, "launch_anchor_guided_worker",
                        lambda **kwargs: launches.append(kwargs) or FakeProcess())
    app = create_app(tmp_path / "test-db" / "matches.db")
    with TestClient(app) as client:
        response = client.post("/api/vision/v2/player-tracking/closed-loop/jobs", json={
            "sample_id": "game_4-t30", "frame_index": 4,
            "detection_set_id": detection_set_id,
            "near_candidate_id": "player-near", "far_candidate_id": "player-far",
            "user_confirmed": True,
            "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING",
            "anchor_interval_seconds": 2.0,
        })
        assert response.status_code == 200
        assert response.json()["tracking_architecture"] == "DETECTION_ANCHORED_MASK_TRACKING"
        assert len(launches) == 1
        assert launches[0]["interval_seconds"] == 2.0
        progress = client.get(f"/api/vision/v2/player-tracking/closed-loop/jobs/{response.json()['job_id']}")
        assert progress.status_code == 200
        assert progress.json()["production_database"] == "NOT_ACCESSED"


def test_mask_conflict_review_api_preserves_evidence_and_queues_local_rerun(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    local = tmp_path / "local"
    digest = fixture_sample(local)
    detection_set_id, _ = seed_detections(local, digest)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PTTI_ENV", "test")
    monkeypatch.setattr(vision_api, "_CLOSED_LOOP_PROCESSES", {})
    product_root = Path(__file__).resolve().parents[1]
    script = product_root / "vision_worker" / "anchor_guided_player_tracker.py"
    monkeypatch.setattr(vision_api, "anchor_guided_worker_paths",
                        lambda: (product_root, script, Path(sys.executable)))

    class FakeProcess:
        def poll(self):
            return 0

    launches = []
    monkeypatch.setattr(vision_api, "launch_anchor_guided_review_worker",
                        lambda **kwargs: launches.append(kwargs) or FakeProcess())
    job_id, root, _ = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, tracking_architecture="DETECTION_ANCHORED_MASK_TRACKING",
        localappdata=local)
    event_id = "MASK_CONFLICT_NEAR_PLAYER_00059_00118"
    review_dir = root / "review-conflicts" / "near_player" / event_id
    review_dir.mkdir(parents=True)
    assets = {}
    for view in ("source", "forward", "reverse"):
        path = review_dir / f"{view}.jpg"
        path.write_bytes(view.encode())
        assets[view] = str(path.relative_to(root))
    atomic_json(root / "tracking.json", {
        "schema_version": "anchor-guided-player-tracking-v1",
        "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING",
        "sample_id": "game_4-t30", "source_sha256": digest,
        "duration_seconds": 10.0, "config": {"sha256": "c" * 64},
        "events": [{"event_id": event_id, "type": "MASK_CONFLICT",
                    "role": "NEAR_PLAYER", "status": "REVIEW_REQUIRED",
                    "frame": 88, "start_frame": 59, "end_frame": 118,
                    "review_assets": assets}],
    })
    progress = load_job_progress(job_id, local)
    progress["status"] = "COMPLETE"
    atomic_json(root / "progress.json", progress)
    app = create_app(tmp_path / "test-db" / "matches.db")
    with TestClient(app) as client:
        asset = client.get(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}/conflicts/{event_id}/forward")
        assert asset.status_code == 200
        neither = client.post(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}/conflicts", json={
            "event_id": event_id, "role": "NEAR_PLAYER", "choice": "NEITHER"})
        assert neither.status_code == 200
        assert neither.json()["status"] == "NEEDS_REBOX"
        rebox = client.post(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}/conflicts", json={
            "event_id": event_id, "role": "NEAR_PLAYER", "choice": "REBOX",
            "bbox": [20, 40, 120, 260]})
        assert rebox.status_code == 200
        assert rebox.json()["status"] == "QUEUED"
        assert launches[0]["event_id"] == event_id
        assert launches[0]["choice"] == "REBOX"
        assert launches[0]["bbox"] == [20.0, 40.0, 120.0, 260.0]
    manifest = json.loads((root / "tracking.json").read_text(encoding="utf-8"))
    assert manifest["events"][0]["status"] == "REVIEW_REQUIRED"
    actions = json.loads((root / "manual-actions.json").read_text(encoding="utf-8"))["actions"]
    assert [row["action"] for row in actions] == ["initial_seed", "mask_choice", "manual_rebox"]


def test_out_of_frame_review_api_can_downgrade_unsupported_classification(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    local = tmp_path / "local"
    digest = fixture_sample(local)
    detection_set_id, _ = seed_detections(local, digest)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("PTTI_ENV", "test")
    job_id, root, _ = create_closed_loop_job(
        sample_id="game_4-t30", frame_index=4, detection_set_id=detection_set_id,
        near_candidate_id="player-near", far_candidate_id="player-far",
        user_confirmed=True, tracking_architecture="DETECTION_ANCHORED_MASK_TRACKING",
        localappdata=local)
    event_id = "OUT_OF_FRAME_FAR_PLAYER_00180"
    atomic_json(root / "tracking.json", {
        "sample_id": "game_4-t30", "duration_seconds": 10,
        "events": [{"event_id": event_id, "type": "OUT_OF_FRAME",
                    "role": "FAR_PLAYER", "classification": "OUT_OF_FRAME",
                    "confidence_level": "HIGH", "status": "CLASSIFIED"}],
    })
    app = create_app(tmp_path / "test-db" / "matches.db")
    with TestClient(app) as client:
        response = client.post(f"/api/vision/v2/player-tracking/closed-loop/jobs/{job_id}/out-of-frame-reviews", json={
            "event_id": event_id, "role": "FAR_PLAYER", "confirm_out_of_frame": False})
        assert response.status_code == 200
        assert response.json()["classification"] == "UNKNOWN"
    manifest = json.loads((root / "tracking.json").read_text(encoding="utf-8"))
    assert manifest["events"][0]["type"] == "IDENTITY_UNCERTAIN"
    assert manifest["events"][0]["status"] == "REVIEW_REQUIRED"


def test_packaged_preview_worker_paths_use_explicit_local_runtime(tmp_path, monkeypatch):
    import backend.vision_api as vision_api

    product_root = tmp_path / "local-runtime"
    workers = product_root / "vision_worker"
    workers.mkdir(parents=True)
    closed_loop = workers / "player_tracking_closed_loop.py"
    anchor_guided = workers / "anchor_guided_player_tracker.py"
    closed_loop.write_text("# worker fixture", encoding="utf-8")
    anchor_guided.write_text("# worker fixture", encoding="utf-8")
    python = tmp_path / "local" / "PTTI-Dev" / "vision-v2-sam2" / "venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"isolated worker fixture")

    monkeypatch.setenv("PTTI_VISION_HOME", str(product_root))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert vision_api.closed_loop_worker_paths() == (product_root, closed_loop, python)
    assert vision_api.anchor_guided_worker_paths() == (product_root, anchor_guided, python)
