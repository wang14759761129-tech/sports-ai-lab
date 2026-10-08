import hashlib
import shutil
import subprocess
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.repository import Repository
from backend.video_evidence import (
    EvidenceInput,
    EvidenceStore,
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
