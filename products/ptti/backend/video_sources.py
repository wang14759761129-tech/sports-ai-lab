"""Source contracts. Metadata, rights, completeness and playback are independent."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Availability = Literal[
    "CATALOG_ONLY", "OFFICIAL_WATCH_PAGE", "EMBED_CANDIDATE",
    "EMBED_PLAYBACK_VERIFIED", "AUTHORIZED_STREAM_VERIFIED",
    "LOCAL_PLAYBACK_VERIFIED", "UNAVAILABLE", "RIGHTS_REQUIRED",
]


class MatchVideoSource(BaseModel):
    provider: str
    source_id: str
    match_id: str | None = None
    player_ids: list[str] = Field(default_factory=list)
    tournament_id: str | None = None
    source_url: str
    playback_type: Literal["OFFICIAL_PAGE", "OFFICIAL_EMBED", "AUTHORIZED_STREAM", "LOCAL"]
    stream_id: str | None = None
    match_start_seconds: float | None = Field(default=None, ge=0)
    match_end_seconds: float | None = Field(default=None, ge=0)
    duration: float | None = Field(default=None, gt=0)
    is_full_match: bool | None = None
    full_match_verification: str = "NOT_VERIFIED"
    embed_permission: Literal["UNKNOWN", "ALLOWED", "DENIED"] = "UNKNOWN"
    analysis_permission: Literal["UNKNOWN", "ALLOWED", "DENIED"] = "UNKNOWN"
    rights_evidence: list[dict] = Field(default_factory=list)
    availability_status: Availability = "CATALOG_ONLY"
    last_checked_at: str | None = None
    provenance: dict = Field(default_factory=dict)
    playback_verified: bool = False

    @model_validator(mode="after")
    def independent_evidence(self):
        if self.match_end_seconds is not None:
            if self.match_start_seconds is None or self.match_end_seconds <= self.match_start_seconds:
                raise ValueError("A stream match interval needs ordered start/end boundaries")
            if self.duration is not None and self.match_end_seconds > self.duration:
                raise ValueError("Match interval exceeds source duration")
        if self.is_full_match is True and self.full_match_verification not in {
            "CONTENT_REVIEWED", "RIGHTSHOLDER_CONFIRMED",
        }:
            raise ValueError("Publisher title alone does not verify match completeness")
        if self.playback_verified and not self.provenance.get("playback_test"):
            raise ValueError("Playback verification requires an actual test record")
        if self.availability_status.endswith("_VERIFIED") and not self.playback_verified:
            raise ValueError("Verified availability requires playback evidence")
        if self.availability_status == "EMBED_PLAYBACK_VERIFIED" and self.embed_permission != "ALLOWED":
            raise ValueError("Embedding requires permission as well as playback")
        if self.availability_status == "AUTHORIZED_STREAM_VERIFIED" and not self.rights_evidence:
            raise ValueError("Authorized streams require rights evidence")
        return self


def official_source(row: dict) -> dict:
    """Project existing references without converting historical labels to success."""
    tested = row.get("watch_page_test") or {}
    times = tested.get("observed_playing_times", [])
    played = (tested.get("result") == "ACTUAL_PLAYBACK_VERIFIED"
              and len(times) >= 2 and all(isinstance(t, (int, float)) and t >= 0 for t in times)
              and times[1] > times[0] and tested.get("surface") in {"BROWSER_IAB", "NATIVE_WINDOWS"})
    page_exists = played or tested.get("result") == "NOT_PLAYABLE_IN_CURRENT_UNAUTHENTICATED_SESSION"
    blocked = row.get("playback_status") == "EMBED_BLOCKED"
    result = MatchVideoSource(
        provider=row["provider"], source_id=row["video_id"],
        match_id=row.get("match_id"), player_ids=row.get("athlete_ids", []),
        tournament_id=row.get("tournament_id"), source_url=row["source_url"],
        playback_type="OFFICIAL_PAGE", stream_id=row["video_id"],
        duration=row.get("duration_seconds"),
        full_match_verification="TITLE_CLAIM_ONLY" if row.get("full_match") else "NOT_VERIFIED",
        embed_permission="DENIED" if blocked else "UNKNOWN", analysis_permission="DENIED",
        availability_status="OFFICIAL_WATCH_PAGE" if page_exists else "CATALOG_ONLY",
        playback_verified=played,
        last_checked_at=tested.get("checked_at") or row.get("metadata_verified_at"),
        provenance={**row.get("provenance", {}), "publisher_full_match_claim": row.get("full_match"),
                    "watch_page_test": tested, "playback_test": tested if played else None, "native_playback_test": row.get("native_playback_test"),
                    "limitation": "A reference is not a redistribution or analysis licence"},
    )
    return result.model_dump()


def source_counts(rows: list[dict]) -> dict:
    return {
        "catalog_records": len(rows),
        "complete_matches_verified": sum(r["is_full_match"] is True for r in rows),
        "internal_playback_verified": sum(r["playback_verified"] and r["playback_type"] != "OFFICIAL_PAGE" for r in rows),
        "external_playback_verified": sum(r["playback_verified"] and r["playback_type"] == "OFFICIAL_PAGE" for r in rows),
        "embed_denied": sum(r["embed_permission"] == "DENIED" for r in rows),
        "analysis_permitted": sum(r["analysis_permission"] == "ALLOWED" for r in rows),
    }
