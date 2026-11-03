import hashlib
import json
import shutil
import subprocess
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.repository import Repository
from backend import video_evidence as video_evidence_module
from backend.video_evidence import (
    AIReviewInput,
    EvidenceInput,
    EvidenceStore,
    PointInput,
    VideoInput,
    evidence_router,
)


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.video_evidence.video_metadata",
        lambda path: {
            "duration": 1200.0,
            "fps": 120.0,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
        },
    )
    source = tmp_path / "中文 空格 比赛.mp4"
    source.write_bytes(bytes(range(256)) * 1000)
    repo = Repository(tmp_path / "qa.db")
    store = EvidenceStore(repo)
    value = VideoInput(
        path=str(source),
        title="训练赛",
        rights_status="USER_OWNED",
        rights_confirmed=True,
        source_note="本人拍摄",
    )
    video = store.register(value)
    for _ in range(100):
        video = store.get("evidence_videos", "video_id", video["video_id"])
        if video["hash_status"] == "VERIFIED":
            break
        time.sleep(0.01)
    assert video["hash_status"] == "VERIFIED"
    yield store, repo, video, source
    store.hasher.shutdown(wait=True)
    store.importer.shutdown(wait=True)


def test_registration_references_original_and_preserves_existing_tables(library):
    _store, repo, video, source = library
    assert video["original_path"] == str(source.resolve())
    assert video["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert video["duration_ms"] == 1200000
    assert len(list(source.parent.glob("*.mp4"))) == 1
    assert repo.list() == []


def test_reopen_preserves_ten_clips_three_tags_notes_and_collection(library):
    store, repo, video, _ = library
    clips = [
        store.evidence(
            EvidenceInput(
                video_id=video["video_id"],
                start_ms=i * 1000,
                end_ms=i * 1000 + 500,
                tags=[["发球", "接发球", "精彩回合"][i % 3]],
                notes=f"复盘笔记 {i}",
            )
        )
        for i in range(10)
    ]
    store.save(
        "evidence_collections",
        "collection_id",
        {
            "collection_id": "playlist",
            "name": "我的关键球",
            "evidence_ids": [c["evidence_id"] for c in reversed(clips)],
        },
        "SAVE_PLAYLIST",
    )
    reopened = EvidenceStore(Repository(repo.path))
    try:
        assert len(reopened.list("video_evidence")) == 10
        assert all(c["notes"] for c in reopened.list("video_evidence"))
        assert (
            reopened.list("evidence_collections")[0]["evidence_ids"][0]
            == clips[-1]["evidence_id"]
        )
    finally:
        reopened.hasher.shutdown(wait=True)


@pytest.mark.parametrize(
    "start,end,representative",
    [(100, 100, None), (-1, 100, None), (0, 1200001, None), (10, 20, 25)],
)
def test_invalid_time_ranges_rejected(library, start, end, representative):
    store, _, video, _ = library
    with pytest.raises(ValueError):
        store.evidence(
            EvidenceInput(
                video_id=video["video_id"],
                start_ms=start,
                end_ms=end,
                representative_ms=representative,
            )
        )


def test_missing_file_relink_checks_content_not_filename(library, tmp_path):
    store, _, video, source = library
    moved = tmp_path / "移动后的录像.mp4"
    source.rename(moved)
    assert store.availability(video)["availability_status"] == "MISSING_FILE"
    wrong = tmp_path / source.name
    wrong.write_bytes(b"x" * video["file_size"])
    with pytest.raises(ValueError, match="身份不一致"):
        store.relink(video["video_id"], wrong)
    linked = store.relink(video["video_id"], moved)
    assert linked["source_sha256"] == video["source_sha256"]
    assert store.availability(linked)["availability_status"] == "AVAILABLE"


def test_source_change_detected_without_reading_full_video(library):
    store, _, video, source = library
    source.write_bytes(b"changed")
    assert store.availability(video)["availability_status"] == "SOURCE_CHANGED"


def test_ai_review_keeps_raw_and_never_becomes_manual(library):
    store, _, video, _ = library
    raw = {
        "event_id": "hit-1",
        "video_sha256": video["source_sha256"],
        "timestamp_ms": 5000,
        "evidence_score": 0.6,
        "status": "SUGGESTED",
    }
    ai = store.import_ai_candidate(video["video_id"], raw)
    assert ai["source"] == "AI_SUGGESTED"
    edited = store.evidence(
        EvidenceInput(
            video_id=video["video_id"],
            start_ms=4500,
            end_ms=5501,
            notes="人工调整",
            review_status="CONFIRMED",
        ),
        ai["evidence_id"],
    )
    assert edited["source"] == "AI_REVIEWED"
    assert edited["raw_candidate"] == raw
    with pytest.raises(ValueError, match="source does not match"):
        store.import_ai_candidate(video["video_id"], {**raw, "video_sha256": "wrong"})


def test_media_range_head_unregistered_path_and_cross_site_denied(library):
    _, repo, video, source = library
    app = FastAPI()
    app.include_router(evidence_router(repo, "test"))
    with TestClient(app) as client:
        url = f"/api/video-evidence/videos/{video['video_id']}/media"
        partial = client.get(url, headers={"Range": "bytes=1024-2047"})
        assert partial.status_code == 206
        assert partial.content == source.read_bytes()[1024:2048]
        assert (
            partial.headers["content-range"] == f"bytes 1024-2047/{video['file_size']}"
        )
        head = client.head(url)
        assert head.status_code == 200 and head.content == b""
        assert int(head.headers["content-length"]) == video["file_size"]
        suffix = client.get(url, headers={"Range": "bytes=-10"})
        assert suffix.status_code == 206 and suffix.content == source.read_bytes()[-10:]
        ranged_head = client.head(url, headers={"Range": "bytes=0-9"})
        assert ranged_head.status_code == 206 and ranged_head.content == b""
        assert ranged_head.headers["content-length"] == "10"
        assert client.get(url, headers={"Range": "bytes=0-1,4-5"}).status_code == 416
        assert client.get(url, headers={"Range": "bytes=999999999-"}).status_code == 416
        assert (
            client.get("/api/video-evidence/videos/unregistered/media").status_code
            == 404
        )
        assert (
            client.get(url, headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
        assert client.get(url, headers={"Host": "evil.example"}).status_code == 403
        source.unlink()
        missing = client.get(url)
        assert (
            missing.status_code == 409
            and missing.json()["detail"]["status"] == "MISSING_FILE"
        )


def test_api_collection_order_and_audit_survive_deletion(library):
    _, repo, video, _ = library
    app = FastAPI()
    app.include_router(evidence_router(repo, "test"))
    with TestClient(app) as client:
        clips = [
            client.post(
                "/api/video-evidence/evidence",
                json={
                    "video_id": video["video_id"],
                    "start_ms": i * 1000,
                    "end_ms": i * 1000 + 500,
                    "tags": ["关键分"],
                    "notes": "人工笔记",
                },
            ).json()
            for i in range(2)
        ]
        created = client.post(
            "/api/video-evidence/collections",
            json={
                "name": "收藏",
                "evidence_ids": [c["evidence_id"] for c in reversed(clips)],
            },
        )
        assert created.status_code == 200
        assert created.json()["evidence_ids"][0] == clips[1]["evidence_id"]
        assert (
            client.post(
                "/api/video-evidence/collections",
                json={"name": "错误", "evidence_ids": ["not-found"]},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                "/api/video-evidence/evidence/" + clips[0]["evidence_id"]
            ).status_code
            == 200
        )
        with repo.connect() as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM evidence_audit WHERE action=?",
                    ("DELETE_EVIDENCE",),
                ).fetchone()[0]
                == 1
            )


def test_production_store_denied_before_any_connection():
    class Repo:
        class Guard:
            mode = "production"

        guard = Guard()

        def connect(self):
            raise AssertionError("Must never connect")

    with pytest.raises(RuntimeError, match="isolated"):
        EvidenceStore(Repo())


def _write_ai_package(path, source_sha, candidate, *, match="game_1", counts=None):
    manifest = {
        "schema": "ptti-ai-evidence-package-v1",
        "dataset": "Extended OpenTTGames",
        "dataset_license": "CC BY-NC-SA 4.0",
        "commercial_use": False,
        "split": "train",
        "match_reference": f"Extended OpenTTGames TRAIN {match}",
        "source_video_sha256": source_sha,
        "result_sha256": video_evidence_module.TRAIN_RESULT_SHA["1"],
        "hit_event_version": "v0.3",
        "variant": "D",
        "model_version": "Hit Event v0.3 Frozen D",
        "frozen_config_sha256": "7b3715807699180b1559d28df5a456046c870035c3d3e9e728e6981185f8ef98",
        "frozen_config_file_sha256": "fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3",
        "timestamp_mapping": {"kind": "CANONICAL_SOURCE_TIMESTAMP_MS", "source_fps": 120.0, "timebase": "1/120", "frame_field": "source_frame", "timestamp_field": "timestamp_ms"},
        "counts": counts or {"total": 1},
    }
    path.write_text(
        json.dumps({"kind": "manifest", "manifest": manifest}) + "\n"
        + json.dumps({"kind": "candidate", "disposition": "ACCEPTED", "candidate": candidate}) + "\n",
        encoding="utf-8",
    )


def _allow_local_video_for_package_test(monkeypatch, video):
    monkeypatch.setitem(video_evidence_module.TRAIN_VIDEO_SHA, "1", video["source_sha256"])


def _wait_batch(store, batch_id):
    for _ in range(200):
        batch = store.import_batch(batch_id)
        if batch["status"] != "RUNNING":
            return batch
        time.sleep(0.01)
    raise AssertionError("AI package import did not finish")


def test_frozen_ai_package_import_checks_sha_timebase_and_preserves_unknown(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "frozen-hit-1", "event_type": "HIT_CANDIDATE", "ablation": "D", "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN", "evidence_score": 0.61, "ball_quality": "SUPPORTED", "evidence_components": {"pre_ball_observations": 2}}
    package = tmp_path / "hits.jsonl"
    _write_ai_package(package, video["source_sha256"], candidate)
    batch = store.start_ai_import(video["video_id"], str(package))
    complete = _wait_batch(store, batch["batch_id"])
    assert complete["status"] == "COMPLETED" and complete["imported_count"] == 1
    suggestion = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)["items"][0]
    assert suggestion["source"] == "AI_SUGGESTION"
    assert suggestion["review_status"] == "UNVERIFIED"
    assert suggestion["suggested_side"] == "UNKNOWN"
    assert suggestion["ai_provenance"]["source_video_sha256"] == video["source_sha256"]
    assert suggestion["ai_provenance"]["frozen_config_sha256"].startswith("7b371580")
    assert suggestion["raw_candidate"]["evidence_score"] == 0.61
    repeated = store.start_ai_import(video["video_id"], str(package))
    assert repeated["batch_id"] == batch["batch_id"]
    assert store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)["total"] == 1


def test_frozen_ai_package_rejects_video_sha_and_bad_frame_mapping(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "bad-hit", "event_type": "HIT_CANDIDATE", "ablation": "D", "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN"}
    wrong_sha = tmp_path / "wrong-sha.jsonl"
    _write_ai_package(wrong_sha, "0" * 64, candidate)
    with pytest.raises(ValueError, match="SHA256"):
        store.start_ai_import(video["video_id"], str(wrong_sha))
    locked = tmp_path / "game-4.jsonl"
    _write_ai_package(locked, video["source_sha256"], candidate, match="game_4")
    with pytest.raises(ValueError, match="GAME_4"):
        store.start_ai_import(video["video_id"], str(locked))
    bad_time = tmp_path / "bad-time.jsonl"
    _write_ai_package(bad_time, video["source_sha256"], {**candidate, "timestamp_ms": 5400.0})
    batch = store.start_ai_import(video["video_id"], str(bad_time))
    failed = _wait_batch(store, batch["batch_id"])
    assert failed["status"] == "FAILED" and "canonical timestamp" in failed["message"]


def test_ai_review_is_append_only_and_point_can_attach_confirmed_evidence(library, tmp_path, monkeypatch):
    store, repo, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "review-hit", "event_type": "HIT_CANDIDATE", "ablation": "D", "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN", "evidence_score": 0.61}
    package = tmp_path / "review.jsonl"
    _write_ai_package(package, video["source_sha256"], candidate)
    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])
    suggestion = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)["items"][0]
    edited = store.review_ai(suggestion["evidence_id"], AIReviewInput(decision="CONFIRMED", representative_ms=5012, start_ms=4512, end_ms=5513, reviewer_side="UNKNOWN", tags=["关键分"], notes="人工确认"))
    assert edited["source"] == "AI_SUGGESTION"
    assert edited["review_status"] == "CONFIRMED"
    assert edited["raw_candidate"]["timestamp_ms"] == 5000.0
    assert edited["representative_ms"] == 5012 and len(edited["review_history"]) == 1
    point = store.save_point(PointInput(video_id=video["video_id"], game_number=1, score_a=9, score_b=9, start_ms=4000, end_ms=6000, tags=["关键分"], evidence_ids=[edited["evidence_id"]]))
    assert point["source"] == "MANUAL_CONFIRMED" and point["evidence_ids"] == [edited["evidence_id"]]
    assert store.points(video["video_id"])[0]["score_a"] == 9
    with repo.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM evidence_audit WHERE entity_id=? AND action='AI_HUMAN_REVIEW'", (edited["evidence_id"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM evidence_audit WHERE action='MANUAL_POINT_SAVE'").fetchone()[0] == 1


def test_filtered_candidates_remain_queryable_and_collection_keeps_order(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "filtered-hit", "event_type": "HIT_CANDIDATE", "ablation": "D", "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN"}
    package = tmp_path / "filtered.jsonl"
    manifest_counts = {"total": 1}
    manifest = {"schema": "ptti-ai-evidence-package-v1", "dataset": "Extended OpenTTGames", "dataset_license": "CC BY-NC-SA 4.0", "commercial_use": False, "split": "train", "match_reference": "Extended OpenTTGames TRAIN game_1", "source_video_sha256": video["source_sha256"], "result_sha256": video_evidence_module.TRAIN_RESULT_SHA["1"], "hit_event_version": "v0.3", "variant": "D", "model_version": "Frozen D", "frozen_config_sha256": "7b3715807699180b1559d28df5a456046c870035c3d3e9e728e6981185f8ef98", "frozen_config_file_sha256": "fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3", "timestamp_mapping": {"kind": "CANONICAL_SOURCE_TIMESTAMP_MS", "source_fps": 120.0, "frame_field": "source_frame", "timestamp_field": "timestamp_ms"}, "counts": manifest_counts}
    package.write_text(json.dumps({"kind": "manifest", "manifest": manifest}) + "\n" + json.dumps({"kind": "candidate", "disposition": "FILTERED", "candidate": candidate}) + "\n", encoding="utf-8")
    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])
    assert batch["filtered_count"] == 1
    result = store.ai_suggestions(video["video_id"], "FILTERED", 0, 10)
    assert result["counts"]["FILTERED"] == 1 and result["items"][0]["disposition"] == "FILTERED"


def test_ai_suggestion_attention_filter_prioritizes_only_explicit_review_evidence(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    base = {"event_type": "HIT_CANDIDATE", "ablation": "D", "candidate_player": "NEAR",
            "ball_quality": "SUPPORTED", "identity_status": "CONFIDENT"}
    rows = [
        ("ordinary", 1000, "ACCEPTED", {**base, "event_id": "ordinary-hit"}),
        ("review", 2000, "REVIEW", {**base, "event_id": "review-hit", "sequence_review_required": True}),
        ("gap", 3000, "ACCEPTED", {**base, "event_id": "gap-hit", "ball_quality": "JUMP_SUSPECT"}),
        ("filtered", 4000, "FILTERED", {**base, "event_id": "filtered-hit"}),
    ]
    package = tmp_path / "attention.jsonl"
    manifest = {"schema": "ptti-ai-evidence-package-v1", "dataset": "Extended OpenTTGames",
                "dataset_license": "CC BY-NC-SA 4.0", "commercial_use": False, "split": "train",
                "match_reference": "Extended OpenTTGames TRAIN game_1",
                "source_video_sha256": video["source_sha256"],
                "result_sha256": video_evidence_module.TRAIN_RESULT_SHA["1"],
                "hit_event_version": "v0.3", "variant": "D", "model_version": "Frozen D",
                "frozen_config_sha256": "7b3715807699180b1559d28df5a456046c870035c3d3e9e728e6981185f8ef98",
                "frozen_config_file_sha256": "fb42c70ab44bb4b919242e6c14de493507fb5aa17ac4a203c6a9e870a1c047f3",
                "timestamp_mapping": {"kind": "CANONICAL_SOURCE_TIMESTAMP_MS", "source_fps": 120.0,
                                      "timebase": "1/120", "frame_field": "source_frame",
                                      "timestamp_field": "timestamp_ms"},
                "counts": {"total": len(rows), "accepted": 2, "review": 1, "filtered": 1}}
    lines = [json.dumps({"kind": "manifest", "manifest": manifest})]
    for _name, timestamp, disposition, candidate in rows:
        candidate = {**candidate, "timestamp_ms": timestamp, "source_frame": int(timestamp * .12)}
        lines.append(json.dumps({"kind": "candidate", "disposition": disposition,
                                 "candidate": candidate}))
    package.write_text("\n".join(lines) + "\n", encoding="utf-8")
    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])
    assert batch["status"] == "COMPLETED"
    all_rows = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 20)
    assert all_rows["counts"]["FILTERED"] == 1
    needs_review = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 20,
                                        attention="NEEDS_REVIEW")
    assert [row["raw_candidate"]["event_id"] for row in needs_review["items"]] == ["review-hit", "gap-hit"]
    evidence_gaps = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 20,
                                         attention="EVIDENCE_GAP")
    assert [row["raw_candidate"]["event_id"] for row in evidence_gaps["items"]] == ["gap-hit"]


def test_video_evidence_exports_keep_ai_review_history_and_filtered_state_separate(library, tmp_path, monkeypatch):
    store, repo, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "export-hit", "event_type": "HIT_CANDIDATE", "ablation": "D",
                 "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN",
                 "evidence_score": 0.61, "ball_quality": "SUPPORTED"}
    package = tmp_path / "export.jsonl"
    _write_ai_package(package, video["source_sha256"], candidate,
                      counts={"accepted": 1, "review": 0, "filtered": 1, "total": 2})
    rows = package.read_text(encoding="utf-8").splitlines()
    filtered = {**candidate, "event_id": "export-filtered", "timestamp_ms": 6000.0,
                "source_frame": 720, "candidate_player": "NEAR"}
    rows.append(json.dumps({"kind": "candidate", "disposition": "FILTERED", "candidate": filtered}))
    package.write_text("\n".join(rows) + "\n", encoding="utf-8")
    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])
    assert batch["status"] == "COMPLETED"
    suggestion = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)["items"][0]
    store.review_ai(suggestion["evidence_id"], AIReviewInput(
        decision="CONFIRMED", representative_ms=5010, start_ms=4510, end_ms=5510,
        reviewer_side="UNKNOWN", tags=["关键分"], notes="确认用于复盘"))
    app = FastAPI()
    app.include_router(evidence_router(repo, "test"))
    with TestClient(app) as client:
        json_response = client.get(f"/api/video-evidence/videos/{video['video_id']}/export?format=json")
        csv_response = client.get(f"/api/video-evidence/videos/{video['video_id']}/export?format=csv")
        html_response = client.get(f"/api/video-evidence/videos/{video['video_id']}/export?format=html")
    assert json_response.status_code == csv_response.status_code == html_response.status_code == 200
    payload = json_response.json()
    statuses = {row["raw_candidate"]["event_id"]: row["review_status"] for row in payload["events"]}
    assert statuses == {"export-hit": "CONFIRMED", "export-filtered": "FILTERED"}
    confirmed = next(row for row in payload["events"] if row["raw_candidate"]["event_id"] == "export-hit")
    assert confirmed["raw_candidate"]["timestamp_ms"] == 5000.0
    assert confirmed["review_history"][-1]["after"]["representative_ms"] == 5010
    assert confirmed["review_status"] != "MANUAL_CONFIRMED"
    assert "FILTERED" in csv_response.text and "CONFIRMED" in csv_response.text
    assert "算法已过滤" in html_response.text and "人工已确认" in html_response.text
    with repo.connect() as db:
        actions = [row[0] for row in db.execute(
            "SELECT action FROM evidence_audit WHERE entity_id=? ORDER BY recorded_at",
            (suggestion["evidence_id"],)).fetchall()]
    assert actions[-1] == "AI_HUMAN_REVIEW"


def test_ai_import_skips_review_candidate_shadowed_by_filtered_raw_row(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {
        "event_id": "shared-hit-id", "event_type": "HIT_CANDIDATE", "ablation": "D",
        "status": "REQUIRES_REVIEW", "timestamp_ms": 5000.0, "source_frame": 600,
        "candidate_player": "UNKNOWN", "evidence_score": 0.61,
    }
    package = tmp_path / "shadowed-hit.jsonl"
    _write_ai_package(
        package, video["source_sha256"], candidate,
        counts={"accepted": 0, "review": 1, "filtered": 1, "total": 2},
    )
    rows = package.read_text(encoding="utf-8").splitlines()
    rows[1] = json.dumps({"kind": "candidate", "disposition": "REVIEW", "candidate": candidate})
    shadow = {**candidate, "status": "RAW_CANDIDATE", "decision": "SUPPRESSED", "review_reason": "DUPLICATE"}
    rows.append(json.dumps({"kind": "candidate", "disposition": "FILTERED", "candidate": shadow}))
    package.write_text("\n".join(rows) + "\n", encoding="utf-8")

    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])

    assert batch["status"] == "COMPLETED"
    assert batch["processed_count"] == 2
    assert batch["imported_count"] == 1
    assert batch["duplicate_count"] == 1
    assert batch["filtered_count"] == 0
    suggestions = store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)
    assert suggestions["total"] == 1
    assert suggestions["items"][0]["disposition"] == "REVIEW"
    assert store.ai_suggestions(video["video_id"], "FILTERED", 0, 10)["total"] == 0


def test_ai_import_rejects_conflicting_duplicate_event_id(library, tmp_path, monkeypatch):
    store, _, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {
        "event_id": "conflicting-hit-id", "event_type": "HIT_CANDIDATE", "ablation": "D",
        "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN",
    }
    package = tmp_path / "conflicting-hit.jsonl"
    _write_ai_package(package, video["source_sha256"], candidate, counts={"accepted": 2, "review": 0, "filtered": 0, "total": 2})
    with package.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"kind": "candidate", "disposition": "ACCEPTED", "candidate": {**candidate, "timestamp_ms": 5100.0, "source_frame": 612}}) + "\n")

    batch = _wait_batch(store, store.start_ai_import(video["video_id"], str(package))["batch_id"])

    assert batch["status"] == "FAILED"
    assert "event_id 内容冲突" in batch["message"]
    assert batch["processed_count"] == 1
    assert store.ai_suggestions(video["video_id"], "UNVERIFIED", 0, 10)["total"] == 1


def test_ai_bridge_api_import_review_and_manual_point(library, tmp_path, monkeypatch):
    _, repo, video, _ = library
    _allow_local_video_for_package_test(monkeypatch, video)
    candidate = {"event_id": "api-hit", "event_type": "HIT_CANDIDATE", "ablation": "D", "timestamp_ms": 5000.0, "source_frame": 600, "candidate_player": "UNKNOWN"}
    package = tmp_path / "api.jsonl"
    _write_ai_package(package, video["source_sha256"], candidate)
    app = FastAPI()
    app.include_router(evidence_router(repo, "test"))
    with TestClient(app) as client:
        started = client.post("/api/video-evidence/imports", json={"video_id": video["video_id"], "path": str(package)})
        assert started.status_code == 200
        batch_id = started.json()["batch_id"]
        for _ in range(200):
            state = client.get(f"/api/video-evidence/imports/{batch_id}").json()
            if state["status"] != "RUNNING":
                break
            time.sleep(0.01)
        assert state["status"] == "COMPLETED"
        result = client.get(f"/api/video-evidence/ai-suggestions?video_id={video['video_id']}&status=UNVERIFIED")
        assert result.status_code == 200 and result.json()["total"] == 1
        suggestion = result.json()["items"][0]
        assert client.get("/api/video-evidence/evidence").json() == []
        reviewed = client.post(f"/api/video-evidence/evidence/{suggestion['evidence_id']}/review", json={"decision": "CONFIRMED", "representative_ms": 5012, "start_ms": 4512, "end_ms": 5513, "reviewer_side": "UNKNOWN", "tags": ["关键分"], "notes": "人工判断"})
        assert reviewed.status_code == 200 and reviewed.json()["review_status"] == "CONFIRMED"
        assert client.get("/api/video-evidence/evidence").json()[0]["evidence_id"] == suggestion["evidence_id"]
        point = client.post("/api/video-evidence/points", json={"video_id": video["video_id"], "game_number": 1, "score_a": 9, "score_b": 9, "start_ms": 4000, "end_ms": 6000, "tags": ["关键分"], "evidence_ids": [suggestion["evidence_id"]], "notes": "人工记录"})
        assert point.status_code == 200 and point.json()["evidence_ids"] == [suggestion["evidence_id"]]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg unavailable")
def test_real_probe_supports_chinese_path(tmp_path):
    from vision.quality import video_metadata

    path = tmp_path / "中文 带空格.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=64x64:rate=30",
            "-t",
            "1",
            "-c:v",
            "libx264",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    metadata = video_metadata(path)
    assert metadata["width"] == 64 and metadata["height"] == 64
    assert metadata["fps"] == 30


def test_evidence_preview_starts_in_manual_review_workspace(tmp_path, monkeypatch):
    from backend.main import create_app

    monkeypatch.setenv("PTTI_EVIDENCE_PREVIEW", "1")
    with TestClient(create_app(tmp_path / "preview.db")) as client:
        health = client.get("/api/health").json()
        assert health["start_page"] == "videoEvidence"
        assert health["version"] == "0.1-video-evidence-preview"
        assert client.get("/api/video-evidence/videos").json() == []
