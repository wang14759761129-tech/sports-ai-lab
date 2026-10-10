"""Reviewed source-list import; no crawling, stream access or match inference."""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, parse_qs

from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.video_sources import official_source


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_id: str
    platform: Literal["YOUTUBE", "BILIBILI"]
    official_url: str
    original_title: str = Field(min_length=1, max_length=500)
    display_title: str = Field(min_length=1, max_length=500)
    event: str = "UNKNOWN"
    event_year: int | None = Field(default=None, ge=1900, le=2100)
    match_date: str | None = None
    match_type: Literal["MS", "WS", "MD", "WD", "XD", "UNKNOWN"]
    round: str = "UNKNOWN"
    player_a: str | None = None
    player_b: str | None = None
    pair_a: str | None = None
    pair_b: str | None = None
    source_publisher: str
    content_type: Literal["FULL_MATCH", "HIGHLIGHTS", "SESSION", "CLIP", "UNKNOWN"] = "UNKNOWN"
    completeness_verified: Literal[False] = False
    permission_status: Literal["REFERENCE_ONLY"] = "REFERENCE_ONLY"
    playback_status: Literal["NOT_TESTED", "RESTRICTED", "UNAVAILABLE"] = "NOT_TESTED"
    playback_limitation: str | None = Field(default=None, max_length=500)
    source_verified_at: datetime
    provenance: dict

    @model_validator(mode="after")
    def safe_source(self):
        u = urlsplit(self.official_url)
        if u.scheme != "https" or u.username or u.password or u.port:
            raise ValueError("Official HTTPS source only")
        if self.platform == "YOUTUBE":
            if u.netloc != "www.youtube.com" or u.path != "/watch" or parse_qs(u.query) != {"v": [self.video_id]} or not re.fullmatch(r"[A-Za-z0-9_-]{11}", self.video_id):
                raise ValueError("YouTube source ID and URL must agree")
        elif u.netloc != "www.bilibili.com" or u.path.rstrip("/") != "/video/" + self.video_id or u.query or not re.fullmatch(r"BV[A-Za-z0-9]{10}", self.video_id):
            raise ValueError("Bilibili source ID and URL must agree")
        if u.fragment or self.source_verified_at.tzinfo is None:
            raise ValueError("No fragment; verification timestamp must include timezone")
        age = datetime.now(timezone.utc) - self.source_verified_at
        if not 0 <= age.total_seconds() <= 30 * 86400:
            raise ValueError("Source metadata must be refreshed within 30 days")
        if not self.provenance.get("metadata_method") or not self.provenance.get("category_evidence"):
            raise ValueError("Metadata and category evidence required")
        return self

    def legacy_row(self):
        raw = self.model_dump(mode="json")
        row = {**raw, "source_key": self.platform + ":" + self.video_id,
               "provider": self.platform + ("_OFFICIAL" if self.platform == "YOUTUBE" else ""),
               "title": self.original_title, "source_url": self.official_url,
               "event_name": self.event, "discipline": self.match_type, "round_label": self.round,
               "athlete_ids": [], "athlete_names": [v for v in [self.player_a,self.player_b,self.pair_a,self.pair_b] if v],
               "thumbnail_url": "", "duration_seconds": None, "full_match": self.content_type == "FULL_MATCH",
               "metadata_verified_at": self.source_verified_at.isoformat(), "match_id": None,
               "local_analysis_allowed": False, "watch_page_status": "NOT_TESTED"}
        row["video_source"] = official_source(row)
        return row


class CatalogBatch(BaseModel):
    entries: list[CatalogEntry] = Field(max_length=500)


def import_entries(repo, entries):
    report = {"received": len(entries), "inserted": 0, "duplicates": 0, "conflicts": [], "per_type": {}}
    # One atomic batch: interrupted imports commit all or none; re-execution is safe.
    with repo.connect() as db:
        for entry in entries:
            row = entry.legacy_row()
            key = row["source_key"]
            previous = db.execute("SELECT payload FROM media_online_sources WHERE source_key=?", (key,)).fetchone()
            if previous:
                report["duplicates"] += 1
                old = json.loads(previous[0])
                if old.get("discipline") != row["discipline"]:
                    report["conflicts"].append(key)
                continue  # Never overwrite human match mapping or playback evidence.
            db.execute("INSERT INTO media_online_sources VALUES (?,?)", (key, json.dumps(row, ensure_ascii=False)))
            db.execute("INSERT INTO evidence_audit VALUES (?,?,?,?,?)", (str(uuid.uuid4()),key,"REVIEWED_CATALOG_IMPORT",datetime.now(timezone.utc).isoformat(),json.dumps(row,ensure_ascii=False)))
            report["inserted"] += 1
            report["per_type"][entry.match_type] = report["per_type"].get(entry.match_type,0) + 1
    return report
