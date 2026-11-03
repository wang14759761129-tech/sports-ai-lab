import pytest

from apps import external_links
from apps.desktop import DesktopAPI


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=WoqgXTjZNSk",
    "https://www.bilibili.com/video/BV1nb421H7jB/",
])
def test_only_canonical_official_video_pages_are_allowed(url):
    assert external_links.is_supported_official_video_url(url)


def test_youtube_integer_seek_requires_matching_registered_video_identity():
    url = "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=754"
    assert external_links.is_supported_official_video_url(url, expected_video_id="WoqgXTjZNSk")
    assert not external_links.is_supported_official_video_url(url)
    assert not external_links.is_supported_official_video_url(url, expected_video_id="ekfCZiIEYi0")


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=754s",
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=-1",
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=7.5",
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=754&t=755",
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=86400",
    "https://www.youtube.com/watch?v=%57oqgXTjZNSk&t=754",
])
def test_youtube_seek_rejects_non_integer_or_ambiguous_seconds(url):
    assert not external_links.is_supported_official_video_url(url, expected_video_id="WoqgXTjZNSk")


@pytest.mark.parametrize("url", [
    "http://www.youtube.com/watch?v=WoqgXTjZNSk",
    "https://youtube.com/watch?v=WoqgXTjZNSk",
    "https://www.youtube.com.evil.invalid/watch?v=WoqgXTjZNSk",
    "https://redacted@example.invalid/watch?v=WoqgXTjZNSk",
    "https://www.youtube.com/watch?v=WoqgXTjZNSk&redirect=https://evil.invalid",
    "https://www.bilibili.com/video/BV1nb421H7jB/?redirect=evil",
    "https://www.bilibili.com/video/not-a-bvid/",
    "https://www.youtube.com/watch?v=short",
])
def test_rejects_noncanonical_or_untrusted_urls(url):
    assert not external_links.is_supported_official_video_url(url)


def test_desktop_bridge_opens_validated_url_in_system_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(external_links.webbrowser, "open_new_tab", lambda url: opened.append(url) or True)

    assert DesktopAPI().open_official_video("https://www.youtube.com/watch?v=WoqgXTjZNSk") is True
    assert opened == ["https://www.youtube.com/watch?v=WoqgXTjZNSk"]


def test_desktop_bridge_never_passes_untrusted_url_to_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(external_links.webbrowser, "open_new_tab", lambda url: opened.append(url) or True)

    with pytest.raises(ValueError):
        DesktopAPI().open_official_video("https://evil.invalid/")
    assert opened == []


def test_desktop_bridge_passes_only_identity_matched_youtube_integer_seek(monkeypatch):
    opened = []
    monkeypatch.setattr(external_links.webbrowser, "open_new_tab", lambda url: opened.append(url) or True)
    url = "https://www.youtube.com/watch?v=WoqgXTjZNSk&t=754"
    assert DesktopAPI().open_official_video(url, "WoqgXTjZNSk") is True
    assert opened == [url]
    with pytest.raises(ValueError):
        DesktopAPI().open_official_video(url, "ekfCZiIEYi0")
    assert opened == [url]


def test_bilibili_expected_identity_must_match_registered_video():
    url = "https://www.bilibili.com/video/BV1nb421H7jB/"
    assert external_links.is_supported_official_video_url(url, "BV1nb421H7jB")
    assert not external_links.is_supported_official_video_url(url, "BV1xxxxxxxxx")
