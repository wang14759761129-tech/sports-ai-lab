"""Safe handoff of reviewed official video URLs to the operating system browser."""
import re
import webbrowser
from urllib.parse import parse_qs, urlsplit


_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_BILIBILI_ID = re.compile(r"^BV[A-Za-z0-9]{10}$")


def is_supported_official_video_url(value: str) -> bool:
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
        query = parse_qs(parsed.query, keep_blank_values=True)
        return set(query) == {"v"} and len(query["v"]) == 1 and bool(_YOUTUBE_ID.fullmatch(query["v"][0]))
    if parsed.hostname == "www.bilibili.com":
        match = re.fullmatch(r"/video/(BV[A-Za-z0-9]{10})/?", parsed.path)
        return bool(match and _BILIBILI_ID.fullmatch(match.group(1)) and not parsed.query)
    return False


def open_official_video_url(value: str) -> bool:
    if not is_supported_official_video_url(value):
        raise ValueError("Only canonical YouTube or Bilibili video pages can be opened")
    return bool(webbrowser.open_new_tab(value))
