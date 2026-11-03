import csv
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.video_evidence import evidence_router
from test_video_evidence import library, _audit_candidate  # noqa: F401


@pytest.mark.parametrize("formula", ["=HYPERLINK(\"https://example.invalid\")", "+CMD", "-CMD", "@SUM(1)", " \t=1+1", "\ttext"])
def test_csv_export_neutralizes_formulas_and_is_repeatable(library, tmp_path, monkeypatch, formula):
    store, repo, video, _ = library
    candidate = _audit_candidate(library, tmp_path, monkeypatch)
    row = store.get("video_evidence", "evidence_id", candidate["evidence_id"])
    row["raw_candidate"]["source_modules"] = [formula]
    store.save("video_evidence", "evidence_id", row, "QA_SOURCE_FIELD")
    app = FastAPI()
    app.include_router(evidence_router(repo, "test"))
    with TestClient(app) as client:
        url = f"/api/video-evidence/videos/{video['video_id']}/export?format=csv"
        first = client.get(url)
        repeated = client.get(url)
    assert first.content == repeated.content
    parsed = next(csv.DictReader(io.StringIO(first.text.lstrip("\ufeff"))))
    assert parsed["evidence_sources"] == "'" + formula
    assert json.loads(parsed["raw_candidate_json"])["source_modules"] == [formula]
