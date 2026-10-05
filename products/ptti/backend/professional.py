"""Professional athlete and match domain validation; names are never identities."""
from datetime import date
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse
import uuid

from pydantic import BaseModel, Field, model_validator


class VideoSourceType(StrEnum):
    NO_VIDEO = "NO_VIDEO"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    ARCHIVE_PREVIEW = "ARCHIVE_PREVIEW"
    LOCAL_USER_VIDEO = "LOCAL_USER_VIDEO"
    LICENSED_WTT_LOCAL = "LICENSED_WTT_LOCAL"
    RESEARCH_DATASET = "RESEARCH_DATASET"


class RightsStatus(StrEnum):
    NO_VIDEO = "NO_VIDEO"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    USER_AUTHORIZED = "USER_AUTHORIZED"
    LICENSED_FOR_ANALYSIS = "LICENSED_FOR_ANALYSIS"
    RESEARCH_DATASET_AUTHORIZED = "RESEARCH_DATASET_AUTHORIZED"


class AnalysisStatus(StrEnum):
    NOT_ANALYZED = "NOT_ANALYZED"
    VIDEO_READY = "VIDEO_READY"
    VIDEO_VALIDATED = "VIDEO_VALIDATED"
    POINT_SEGMENTATION_PENDING = "POINT_SEGMENTATION_PENDING"
    POINTS_DETECTED = "POINTS_DETECTED"
    BALLTRACK_COMPLETE = "BALLTRACK_COMPLETE"
    TACTICAL_ANALYSIS_PENDING = "TACTICAL_ANALYSIS_PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class GroupMembershipUpdate(BaseModel):
    athlete_ids: list[str] = Field(default_factory=list, max_length=500)


class ProfessionalMatchInput(BaseModel):
    event_name: str = Field(min_length=1, max_length=300)
    event_id: str | None = Field(default=None, max_length=100)
    event_date: date | None = None
    round: str | None = Field(default=None, max_length=150)
    competition_level: str | None = Field(default=None, max_length=100)
    player_a_id: str
    player_b_id: str
    final_score: dict[str, int] | None = None
    winner_id: str | None = None
    video_source_type: VideoSourceType = VideoSourceType.NO_VIDEO
    video_local_path: str | None = None
    external_reference_url: str | None = Field(default=None, max_length=2000)
    wtt_asset_id: str | None = Field(default=None, max_length=200)
    rights_status: RightsStatus = RightsStatus.NO_VIDEO
    licence_reference: str | None = Field(default=None, max_length=500)
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_match(self):
        if self.player_a_id == self.player_b_id:
            raise ValueError("A professional match must have two distinct athletes")
        if self.winner_id is not None and self.winner_id not in {self.player_a_id, self.player_b_id}:
            raise ValueError("winner_id must identify one of the match participants")
        if self.final_score is not None:
            if set(self.final_score) != {"player_a_games", "player_b_games"}:
                raise ValueError("final_score must contain player_a_games and player_b_games")
            if min(self.final_score.values()) < 0:
                raise ValueError("final scores cannot be negative")
        if self.external_reference_url:
            parsed = urlparse(self.external_reference_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("External references must use an http(s) URL")
        local_types = {VideoSourceType.LOCAL_USER_VIDEO, VideoSourceType.LICENSED_WTT_LOCAL, VideoSourceType.RESEARCH_DATASET}
        if self.video_source_type in {VideoSourceType.NO_VIDEO, VideoSourceType.REFERENCE_ONLY, VideoSourceType.ARCHIVE_PREVIEW}:
            if self.video_local_path is not None:
                raise ValueError("Reference and preview records cannot enter the local video pipeline")
        if self.video_source_type == VideoSourceType.NO_VIDEO:
            if self.rights_status != RightsStatus.NO_VIDEO or self.external_reference_url or self.wtt_asset_id:
                raise ValueError("NO_VIDEO records cannot carry a video reference or asset")
        elif self.video_source_type in {VideoSourceType.REFERENCE_ONLY, VideoSourceType.ARCHIVE_PREVIEW}:
            if self.rights_status != RightsStatus.REFERENCE_ONLY or not self.external_reference_url:
                raise ValueError("Reference-only records require an external URL and reference-only rights")
        elif self.video_source_type == VideoSourceType.LOCAL_USER_VIDEO:
            if self.rights_status != RightsStatus.USER_AUTHORIZED:
                raise ValueError("Local user video requires USER_AUTHORIZED rights")
        elif self.video_source_type == VideoSourceType.LICENSED_WTT_LOCAL:
            if self.rights_status != RightsStatus.LICENSED_FOR_ANALYSIS or not self.licence_reference:
                raise ValueError("Licensed WTT video requires a licence reference")
        elif self.video_source_type == VideoSourceType.RESEARCH_DATASET:
            if self.rights_status != RightsStatus.RESEARCH_DATASET_AUTHORIZED or not self.licence_reference:
                raise ValueError("Research video requires its dataset authorization reference")
        if self.video_source_type in local_types:
            if not self.video_local_path:
                raise ValueError("Authorized local video requires a local file path")
            path = Path(self.video_local_path).expanduser()
            if not path.is_file():
                raise ValueError("Authorized local video path must identify an existing file")
            if path.suffix.casefold() not in {".mp4", ".mov", ".mkv", ".avi"}:
                raise ValueError("Video file extension is not supported")
        if self.wtt_asset_id and self.video_source_type != VideoSourceType.LICENSED_WTT_LOCAL:
            raise ValueError("A WTT asset ID is only valid for licensed local media")
        return self

    def to_record(self):
        record = self.model_dump(mode="json")
        record["match_id"] = "pro:" + str(uuid.uuid4())
        record["winner_id"] = self.winner_id
        record["analysis_status"] = (
            AnalysisStatus.VIDEO_READY.value if self.video_source_type in {
                VideoSourceType.LOCAL_USER_VIDEO, VideoSourceType.LICENSED_WTT_LOCAL, VideoSourceType.RESEARCH_DATASET
            } else AnalysisStatus.NOT_ANALYZED.value
        )
        return record


def validate_seed(manifest):
    athletes = manifest.get("athletes", [])
    ids = [a["athlete_id"] for a in athletes]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate athlete_id in professional registry seed")
    if not all(a.get("canonical_name_en") for a in athletes):
        raise ValueError("Every athlete seed needs a canonical English name")
    id_set = set(ids)
    for match in manifest.get("professional_matches", []):
        if match["player_a_id"] not in id_set or match["player_b_id"] not in id_set:
            raise ValueError(f"Seed match participants must exist: {match['match_id']}")
        if match.get("winner_id") not in {None, match["player_a_id"], match["player_b_id"]}:
            raise ValueError(f"Seed match winner must be a participant: {match['match_id']}")
    source_ids = {s["source_id"] for s in manifest.get("sources", [])}
    for athlete in athletes:
        if not set(athlete.get("source_ids", [])).issubset(source_ids):
            raise ValueError(f"Missing athlete provenance source: {athlete['athlete_id']}")
    for match in manifest.get("professional_matches", []):
        if not set(match.get("source_ids", [])).issubset(source_ids):
            raise ValueError(f"Missing match provenance source: {match['match_id']}")
    return manifest
