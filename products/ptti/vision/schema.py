from typing import Literal
from pydantic import BaseModel, Field, model_validator
from urllib.parse import urlparse

class Source(BaseModel):
    type: Literal['local', 'racketvision', 'wtt_licensed', 'external_reference']
    provider: str = ''
    source_id: str | None = None
    original_url: str | None = None
    rights: Literal['licensed', 'internal', 'user_provided', 'research']
    licence_reference: str | None = None
    rights_notes: str = ''
    title: str = ''
    event: str = ''
    players: str = ''
    round: str = ''

    @model_validator(mode='after')
    def rights_check(self):
        if self.type == 'wtt_licensed' and self.rights != 'licensed':
            raise ValueError('WTT imports require licensed rights metadata')
        if self.type == 'wtt_licensed' and not self.licence_reference:
            raise ValueError('WTT imports require a licence reference')
        if self.type == 'external_reference':
            parsed=urlparse(self.original_url or '')
            if parsed.scheme not in {'http','https'} or not parsed.netloc:
                raise ValueError('External references require an http(s) URL')
        return self

class BallPoint(BaseModel):
    frame: int = Field(ge=0)
    timestamp_ms: float = Field(ge=0)
    visible: bool
    pixel_x: float | None = None
    pixel_y: float | None = None
    normalized_x: float | None = Field(default=None, ge=0, le=1)
    normalized_y: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    model: str = 'RacketVision/BallTrack'

    @model_validator(mode='after')
    def coordinates(self):
        values = (self.pixel_x, self.pixel_y, self.normalized_x, self.normalized_y)
        if self.visible and any(v is None for v in values):
            raise ValueError('Visible observations require coordinates')
        if not self.visible and any(v is not None for v in values):
            raise ValueError('Invisible observations must not fabricate coordinates')
        return self

class VisionEvent(BaseModel):
    # Future inference layer: observations do not automatically become tactical events.
    kind: Literal['ball_position', 'racket_contact_candidate', 'table_bounce_candidate',
                  'net_crossing_candidate', 'rally_start_candidate', 'rally_end_candidate']
    frame: int = Field(ge=0)
    timestamp_ms: float = Field(ge=0)
    layer: Literal['observation', 'inference', 'interpretation']
    source: str
    confidence: float | None = None
    evidence: dict
