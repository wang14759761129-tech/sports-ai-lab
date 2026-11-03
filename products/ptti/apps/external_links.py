"""Safe handoff of reviewed official video URLs to the operating system browser."""
import re
import webbrowser
from urllib.parse import parse_qs, urlsplit


_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_BILIBILI_ID = re.compile(r"^BV[A-Za-z0-9]{10}$")


def is_supported_official_video_url(value: str, expected_video_id: str | None = None) -> bool:
    if not isinstance(value, str) or len(value) > 512:
        return False
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
                or parsed.fragment):
            return False
    except ValueError:
        return False
    if parsed.hostname == "www.youtube.com" and parsed.path == "/watch":
        try:
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            return False
        if set(query) not in ({"v"}, {"v", "t"}) or len(query.get("v", [])) != 1:
            return False
        video_id = query["v"][0]
        if not _YOUTUBE_ID.fullmatch(video_id):
            return False
        if expected_video_id is not None and video_id != expected_video_id:
            return False
        canonical_query = f"v={video_id}"
        if "t" in query:
            if (expected_video_id is None or len(query["t"]) != 1
                    or not re.fullmatch(r"(?:0|[1-9][0-9]{0,4})", query["t"][0])
                    or int(query["t"][0]) >= 86400):
                return False
            canonical_query += f"&t={query['t'][0]}"
        if parsed.query != canonical_query:
            return False
        return True
    if parsed.hostname == "www.bilibili.com":
        match = re.fullmatch(r"/video/(BV[A-Za-z0-9]{10})/?", parsed.path)
        return bool(
            match and _BILIBILI_ID.fullmatch(match.group(1)) and not parsed.query
            and (expected_video_id is None or match.group(1) == expected_video_id)
        )
    return False


def open_official_video_url(value: str, expected_video_id: str | None = None) -> bool:
    if not is_supported_official_video_url(value, expected_video_id=expected_video_id):
        raise ValueError("Only canonical YouTube or Bilibili video pages can be opened")
    return bool(webbrowser.open_new_tab(value))
