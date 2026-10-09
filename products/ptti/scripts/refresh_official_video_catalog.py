"""Refresh an explicit official-source allowlist via public oEmbed, never media downloads.

Metadata availability does not certify playback, embedding, duration, or regional rights.
Review titles and provenance before committing the resulting manifest.
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("0QgbtsBWZhk", "王楚钦 vs 菲利克斯·勒布伦", ["athlete:121558", "athlete:135977"], ["王楚钦", "菲利克斯·勒布伦"], "China Smash 2025", "MS", "决赛"),
    ("vYsJLPTEIaI", "孙颖莎 vs 王曼昱", [], ["孙颖莎", "王曼昱"], "WTT Singapore 2026", "WS", "决赛"),
    ("aFs7HJ0NX18", "马龙 vs 樊振东", [], ["马龙", "樊振东"], "ITTF Finals 2020", "MS", "决赛"),
    ("JTUWXpB-NVo", "马龙 vs 樊振东", [], ["马龙", "樊振东"], "ITTF Grand Finals 2019", "MS", "决赛"),
    ("H77vNFk3neg", "王楚钦 vs 马龙", ["athlete:121558"], ["王楚钦", "马龙"], "WTT Macao 2023", "MS", "决赛"),
    ("ekfCZiIEYi0", "王楚钦 vs 樊振东", ["athlete:121558"], ["王楚钦", "樊振东"], "WTT Ljubljana 2023", "MS", "决赛"),
    ("DTPNEl3-2b0", "孙颖莎 vs 金娜英", [], ["孙颖莎", "金娜英"], "WTT Macao 2024", "WS", "16强"),
    ("iQhVLkcGCFE", "林昀儒 / 郑怡静 vs 王楚钦 / 孙颖莎", ["athlete:121558"], ["林昀儒", "郑怡静", "王楚钦", "孙颖莎"], "ITTF Worlds 2021", "XD", "半决赛"),
]


def main():
    target = ROOT / "data/professional/official_video_sources.json"
    existing = {v["video_id"]: v for v in json.loads(target.read_text(encoding="utf-8"))["videos"]}
    videos = []
    for identity, title, athletes, names, event, discipline, round_label in SOURCES:
        url = f"https://www.youtube.com/watch?v={identity}"
        with urllib.request.urlopen("https://www.youtube.com/oembed?url=" + url + "&format=json", timeout=10) as response:
            metadata = json.load(response)
        if metadata["author_url"].rstrip("/") != "https://www.youtube.com/@wttglobal" or not metadata["title"].startswith("FULL MATCH"):
            raise ValueError("Publisher or full-match title differs from expected official source")
        old = existing.get(identity, {})
        videos.append({**old, "video_id": identity, "title": metadata["title"], "display_title": title,
            "athlete_ids": athletes, "athlete_names": names, "event_name": event, "discipline": discipline,
            "round_label": round_label, "full_match": True, "full_match_evidence": "OFFICIAL_PUBLISHER_TITLE",
            "provider": "YOUTUBE_OFFICIAL", "channel": metadata["author_name"], "channel_url": metadata["author_url"],
            "source_url": url, "embed_url": f"https://www.youtube.com/embed/{identity}",
            "thumbnail_url": metadata["thumbnail_url"], "duration_seconds": None, "published_at": None,
            "metadata_verified_at": datetime.now(timezone.utc).isoformat(),
            "playback_status": old.get("playback_status", "EMBED_NOT_TESTED"),
            "watch_page_status": old.get("watch_page_status", "NOT_TESTED"),
            "embeddable_api": None, "privacy_status_api": None, "region_restrictions_api": None,
            "rights": "REFERENCE_ONLY_NOT_LICENSE_GRANTED", "local_analysis_allowed": False,
            "provenance": {"metadata_method": "YOUTUBE_OEMBED", "endpoint": "https://www.youtube.com/oembed",
                "limitations": "oEmbed supplies neither duration nor playback restrictions; actual play required",
                "official_channel_reference": "https://www.ittf.com/2025/05/16/everything-you-need-to-know-ittf-world-table-tennis-championships-finals-doha-2025/"}})
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"videos": videos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(f"Verified {len(videos)} unique official metadata records; no video downloaded")


if __name__ == "__main__":
    main()
