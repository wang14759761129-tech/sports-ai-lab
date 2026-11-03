"""Server-side, one-video YouTube Data API v3 transport foundation.

This module is deliberately not imported by the frontend. It makes no request
unless explicitly called with a reviewed client configuration and an API key.
Responses are returned in memory without persistence or thumbnail URL rewriting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
from typing import Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_API_URL = "https://www.googleapis.com/youtube/v3/videos"
_API_KEY_ENV = "PTTI_YOUTUBE_DATA_API_KEY"
_FIELDS = "items(id,snippet(title,channelId,channelTitle,publishedAt,thumbnails))"
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class YouTubeDataApiError(RuntimeError):
    """Sanitized request/configuration error; never includes request URLs or keys."""


@dataclass(frozen=True)
class YouTubeDataApiConfig:
    api_key: str | None = field(repr=False)
    client_review: str = "NOT_STARTED"
    api_scope: str = "UNRESTRICTED"
    application_restriction: str = "UNRESTRICTED"

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        client_review: str = "NOT_STARTED",
        api_scope: str = "UNRESTRICTED",
        application_restriction: str = "UNRESTRICTED",
    ) -> "YouTubeDataApiConfig":
        """Read only the server process environment; never read frontend config."""
        values = os.environ if environ is None else environ
        api_key = values.get(_API_KEY_ENV, "").strip() or None
        return cls(
            api_key=api_key,
            client_review=client_review,
            api_scope=api_scope,
            application_restriction=application_restriction,
        )

    @property
    def ready(self) -> bool:
        return bool(
            self.api_key
            and self.client_review == "APPROVED"
            and self.api_scope == "YOUTUBE_DATA_API_V3"
            and self.application_restriction == "SERVER_RESTRICTED"
        )


def fetch_videos_list(
    video_id: str,
    config: YouTubeDataApiConfig,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    timeout: float = 8,
) -> dict:
    """Fetch snippet for exactly one video after explicit client-review gating.

    Caller owns the approved server-side configuration. This function performs
    no retries, logging, caching, persistence, thumbnail rewriting, or embed
    permission promotion. Tests inject an in-memory opener and make no network
    requests.
    """
    if not isinstance(video_id, str) or not _VIDEO_ID.fullmatch(video_id):
        raise YouTubeDataApiError("invalid video ID; expected one exact 11-character ID")
    if not isinstance(config, YouTubeDataApiConfig) or not config.ready:
        raise YouTubeDataApiError("YouTube Data API client is not configured and reviewed")

    query = urllib.parse.urlencode(
        {
            "part": "snippet",
            "id": video_id,
            "maxResults": "1",
            "fields": _FIELDS,
            "key": config.api_key,
        }
    )
    request = urllib.request.Request(
        f"{_API_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "PTTI-Metadata-Adapter/0.1"},
        method="GET",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read(_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise YouTubeDataApiError(f"YouTube Data API request failed (HTTP {error.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise YouTubeDataApiError("YouTube Data API request failed (network error)") from None

    if len(body) > _MAX_RESPONSE_BYTES:
        raise YouTubeDataApiError("YouTube Data API response exceeded the size limit")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise YouTubeDataApiError("YouTube Data API returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
        raise YouTubeDataApiError("YouTube Data API response has an invalid shape")
    return payload
