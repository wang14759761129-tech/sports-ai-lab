import pytest

from apps import external_links
from apps.desktop import DesktopAPI


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=WoqgXTjZNSk",
    "https://www.bilibili.com/video/BV1nb421H7jB/",
])
def test_only_canonical_official_video_pages_are_allowed(url):
    assert external_links.is_supported_official_video_url(url)


@pytest.mark.parametrize("url", [
    "http://www.youtube.com/watch?v=WoqgXTjZNSk",
    "https://youtube.com/watch?v=WoqgXTjZNSk",
    "https://www.youtube.com.evil.invalid/watch?v=WoqgXTjZNSk",
    "https://user@www.youtube.com/watch?v=WoqgXTjZNSk",
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
