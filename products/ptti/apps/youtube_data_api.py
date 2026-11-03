"""Server-side YouTube Data API v3 transport; one shared request path.

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
_BATCH_PARTS = "snippet,contentDetails,status"
_BATCH_FIELDS = "items(id,snippet(title,channelId,channelTitle,publishedAt,thumbnails),contentDetails(duration),status(privacyStatus,embeddable))"
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
    """Backward-compatible snippet-only call through the shared transport."""
    return _request_videos_list([video_id], config, "snippet", _FIELDS, opener, timeout)


def fetch_videos_list_batch(
    video_ids: list[str] | tuple[str, ...],
    config: YouTubeDataApiConfig,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    timeout: float = 8,
) -> dict:
    """Batch metadata profile; status/contentDetails never grant media permission."""
    return _request_videos_list(video_ids, config, _BATCH_PARTS, _BATCH_FIELDS, opener, timeout)


def _request_videos_list(video_ids, config, parts, fields, opener, timeout) -> dict:
    if not isinstance(video_ids, (list, tuple)) or not 1 <= len(video_ids) <= 50:
        raise YouTubeDataApiError("invalid batch; expected between 1 and 50 video IDs")
    if any(not isinstance(video_id, str) or not _VIDEO_ID.fullmatch(video_id) for video_id in video_ids):
        raise YouTubeDataApiError("invalid video ID in batch")
    if len(set(video_ids)) != len(video_ids):
        raise YouTubeDataApiError("duplicate video ID in batch")
    if not isinstance(config, YouTubeDataApiConfig) or not config.ready:
        raise YouTubeDataApiError("YouTube Data API client is not configured and reviewed")
    query = urllib.parse.urlencode({
        "part": parts, "id": ",".join(video_ids), "maxResults": str(len(video_ids)),
        "fields": fields, "key": config.api_key,
    })
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
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise YouTubeDataApiError("YouTube Data API response has an invalid shape")
    returned_ids = []
    for item in payload["items"]:
        if not isinstance(item, dict) or item.get("id") not in video_ids:
            raise YouTubeDataApiError("YouTube Data API response contains an unexpected video ID")
        returned_ids.append(item["id"])
    if len(set(returned_ids)) != len(returned_ids):
        raise YouTubeDataApiError("YouTube Data API response contains duplicate video IDs")
    return payload


def configuration_readiness(config: YouTubeDataApiConfig) -> dict:
    """Local preflight only; does not prove key validity, restrictions or authorization."""
    return {
        "api_key_present": bool(config.api_key),
        "client_review": config.client_review,
        "api_scope": config.api_scope,
        "application_restriction": config.application_restriction,
        "configuration_ready": config.ready,
        "credential_validity": "NOT_TESTED",
        "live_request_executed": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Local YouTube client preflight; never sends a request")
    parser.add_argument("--check-config", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(configuration_readiness(YouTubeDataApiConfig.from_environment()), indent=2))
