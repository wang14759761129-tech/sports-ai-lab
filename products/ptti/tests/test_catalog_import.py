"""Synthetic schema/transaction QA, never real match evidence."""
from datetime import datetime, timezone, timedelta
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app


def entry(code="WD", identity="abcdefghijk"):
    return dict(video_id=identity,platform="YOUTUBE",official_url="https://www.youtube.com/watch?v="+identity,
                original_title="QA ONLY",display_title="QA ONLY",match_type=code,source_publisher="QA publisher",
                source_verified_at=datetime.now(timezone.utc).isoformat(),
                provenance={"metadata_method":"SYNTHETIC_TEST_ONLY","category_evidence":"QA_ONLY"})


def test_batch_import_idempotent_and_not_match_or_playback_evidence(tmp_path):
    with TestClient(create_app(tmp_path/"qa.db")) as client:
        body={"entries":[entry(),entry("MD","lmnopqrstuv")]}
        first=client.post("/api/video-evidence/library/catalog/import",json=body)
        assert first.status_code == 200, first.text
        assert first.json()["inserted"] == 2
        repeated=client.post("/api/video-evidence/library/catalog/import",json=body)
        assert repeated.json()["inserted"] == 0
        assert repeated.json()["duplicates"] == 2
        rows=client.get("/api/video-evidence/library").json()["official_videos"]
        row=next(r for r in rows if r["video_id"]=="abcdefghijk")
        assert row["match_id"] is None
        assert row["video_source"]["is_full_match"] is None
        assert not row["video_source"]["playback_verified"]
        assert row["video_source"]["analysis_permission"] == "DENIED"
        assert row["video_source"]["timeline_id"] != next(r for r in rows if r["video_id"]=="lmnopqrstuv")["video_source"]["timeline_id"]


@pytest.mark.parametrize("change",[
    {"official_url":"https://evil.example/watch?v=abcdefghijk"},
    {"official_url":"https://www.youtube.com/watch?v=other"},
    {"official_url":"https://www.youtube.com/watch?v=abcdefghijk#secret"},
    {"completeness_verified":True}, {"playback_status":"VERIFIED"},
    {"source_verified_at":(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()},
    {"source_verified_at":"2030-01-01T00:00:00Z"}, {"provenance":{}},
])
def test_invalid_batch_never_partially_imports(tmp_path,change):
    with TestClient(create_app(tmp_path/"qa.db")) as client:
        bad=deepcopy(entry());bad.update(change)
        r=client.post("/api/video-evidence/library/catalog/import",json={"entries":[entry("MS","lmnopqrstuv"),bad]})
        assert r.status_code == 422
        assert not any(row["video_id"]=="lmnopqrstuv" for row in client.get("/api/video-evidence/library").json()["official_videos"])


def test_conflicting_repeat_does_not_overwrite_category(tmp_path):
    with TestClient(create_app(tmp_path/"qa.db")) as client:
        client.post("/api/video-evidence/library/catalog/import",json={"entries":[entry()]})
        result=client.post("/api/video-evidence/library/catalog/import",json={"entries":[entry("MS")]})
        assert result.json()["conflicts"] == ["YOUTUBE:abcdefghijk"]
        row=next(r for r in client.get("/api/video-evidence/library").json()["official_videos"] if r["video_id"]=="abcdefghijk")
        assert row["discipline"] == "WD"


def test_interrupted_sql_batch_rolls_back_and_resume_is_idempotent(tmp_path):
    from backend.catalog_import import CatalogEntry, import_entries
    import sqlite3
    app=create_app(tmp_path/"qa.db")
    repo=app.state.repository
    with repo.connect() as db:
        db.execute("CREATE TRIGGER qa_fail BEFORE INSERT ON media_online_sources WHEN NEW.source_key='YOUTUBE:lmnopqrstuv' BEGIN SELECT RAISE(ABORT,'QA interruption'); END")
    entries=[CatalogEntry(**entry()),CatalogEntry(**entry("MD","lmnopqrstuv"))]
    with pytest.raises(sqlite3.IntegrityError):
        import_entries(repo,entries)
    with repo.connect() as db:
        assert db.execute("SELECT count(*) FROM media_online_sources").fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM evidence_audit WHERE action='REVIEWED_CATALOG_IMPORT'").fetchone()[0]==0
        db.execute("DROP TRIGGER qa_fail")
    assert import_entries(repo,entries)["inserted"]==2
    assert import_entries(repo,entries)["duplicates"]==2


def test_import_rejects_production_mode_without_writing(tmp_path,monkeypatch):
    app=create_app(tmp_path/"qa.db")
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.repository.guard,"mode","production")
        response=client.post("/api/video-evidence/library/catalog/import",json={"entries":[entry()]})
        assert response.status_code==403
