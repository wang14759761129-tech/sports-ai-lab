"""Build a small, strict public projection of an already-admitted WTT match report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATCH_LIBRARY_PATH = ROOT / "generated" / "goal15-main-fan-universe-public-v0.2" / "match-library-strict-public.json"
FAN_INSPIRATION_PATH = ROOT / "generated" / "goal22-main-inspiration-v0.1" / "public" / "fan-inspiration-v0.1.json"
SCHEMA_PATH = ROOT / "contracts" / "match-report-evidence-v0.1.schema.json"
OUTPUT_PATH = ROOT / "generated" / "goal24-main-evidence-v0.1" / "public" / "match-reports-v0.1.json"

EXPECTED_MATCH_LIBRARY_SHA256 = "1e038dcab1a39c6c37d7687a066cd391328681a89950ae02e937ab1a0ac65930"
EXPECTED_FAN_INSPIRATION_SHA256 = "702bc12850676ae9eeda39b533ade9cc5f2da0fe8710aa8ebc82f0c2b803c5c9"
MATCH_ID = "pro:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final"
REPORT_EVIDENCE_ID = "goal15-wtt-singapore-smash-2026-ms-final"
VIDEO_SOURCE_ID = "video-source:youtube:cDccQqVlMnc"


class PackageError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_package(*, generated_at: str = "2026-10-21T00:00:00Z") -> dict[str, Any]:
    library_sha = sha256_file(MATCH_LIBRARY_PATH)
    fan_sha = sha256_file(FAN_INSPIRATION_PATH)
    if library_sha != EXPECTED_MATCH_LIBRARY_SHA256:
        raise PackageError("match_library_identity_mismatch")
    if fan_sha != EXPECTED_FAN_INSPIRATION_SHA256:
        raise PackageError("fan_inspiration_identity_mismatch")

    library = read_json(MATCH_LIBRARY_PATH)
    inspiration = read_json(FAN_INSPIRATION_PATH)
    matches = {item.get("match_id"): item for item in library.get("matches", [])}
    match = matches.get(MATCH_ID)
    if not match:
        raise PackageError("pinned_match_missing")

    evidence = {item.get("source_id"): item for item in library.get("evidence_sources", [])}
    source = evidence.get(REPORT_EVIDENCE_ID)
    if not source or source.get("source_type") != "OFFICIAL_WTT_MATCH_REPORT":
        raise PackageError("official_report_evidence_missing_or_wrong_type")
    if source.get("url") != "https://www.worldtabletennis.com/description?artId=5957":
        raise PackageError("official_report_url_mismatch")

    videos = {
        item.get("source_id"): item
        for item in inspiration.get("clips", []) + inspiration.get("match_watch_sources", [])
    }
    video = videos.get(VIDEO_SOURCE_ID)
    if not video or video.get("match_id") != MATCH_ID:
        raise PackageError("linked_video_missing_or_match_mismatch")

    participants = match.get("participants", [])
    result = match.get("recorded_result", {})
    expected_participants = [("athlete:121558", "WANG Chuqin"), ("athlete:121582", "LIN Yun-Ju")]
    actual_participants = [(p.get("athlete_id"), p.get("name_en")) for p in participants]
    if actual_participants != expected_participants:
        raise PackageError("pinned_match_participants_mismatch")
    if result != {"player_a_games": 4, "player_b_games": 0}:
        raise PackageError("pinned_official_result_mismatch")
    if match.get("result_status") != "OFFICIAL_WTT_RESULT_CROSSCHECKED":
        raise PackageError("pinned_result_not_officially_crosschecked")
    if video.get("verification", {}).get("match_link") != "HUMAN_VERIFIED":
        raise PackageError("linked_video_match_link_not_human_verified")

    report = {
        "report_id": f"match-report:wtt:singapore-smash-2026:wang-chuqin-lin-yun-ju-ms-final",
        "match_id": MATCH_ID,
        "event_name": match["event"]["name"],
        "event_year": match["event"]["event_year"],
        "round": match["round"],
        "participants": [{"athlete_id": p["athlete_id"], "name_en": p["name_en"]} for p in participants],
        "recorded_result": {
            "winner_id": match["recorded_winner_id"],
            "winner_name": match["recorded_winner_name"],
            "player_a_games": result["player_a_games"],
            "player_b_games": result["player_b_games"],
            "status": match["result_status"],
        },
        "game_scores": [[11, 3], [11, 8], [11, 8], [11, 9]],
        "editorial_summary_zh": "WTT官方赛报称，王楚钦在新加坡大满贯男单决赛以4比0战胜林昀儒；比赛局分为11比3、11比8、11比8、11比9。报道还记录了比赛走势和王楚钦的赛后感受。",
        "article": {
            "source_id": REPORT_EVIDENCE_ID,
            "publisher": "World Table Tennis",
            "title": "Lion Heart: Wang Chuqin Takes Second Singapore Smash Title",
            "url": source["url"],
            "published_at": None,
            "published_at_status": "NOT_RECORDED_NO_DATE_IN_REVIEWED_SOURCE",
            "content_observation": "OFFICIAL_DOMAIN_SEARCH_EXCERPT_SURFACED",
            "direct_page_status": "COOKIE_CONSENT_SHELL_ONLY",
            "checked_on": "2026-10-21",
        },
        "linked_video": {
            "source_id": VIDEO_SOURCE_ID,
            "url": video["original_url"],
            "match_link": video["verification"]["match_link"],
            "external_system_browser_open": "NOT_TESTED",
            "video_started": "NOT_TESTED",
            "complete_watch": "UNVERIFIED",
        },
        "rights": {
            "article_republication": "NOT_GRANTED",
            "image_reuse": "NOT_GRANTED",
            "summary_and_outbound_link": "FACTUAL_SUMMARY_AND_LINK_ONLY",
            "video_embed": "UNKNOWN_NOT_GRANTED",
        },
    }
    return {
        "contract_version": "ptti.main.match-report-evidence/0.1",
        "generated_at": generated_at,
        "input_identity": {
            "match_library_sha256": library_sha,
            "fan_inspiration_sha256": fan_sha,
        },
        "match_reports": [report],
        "notice": "One official report projection is linked to an existing WTT match and existing official video record. This is factual summary and outbound-link data only; direct browser opening and video playback remain untested.",
    }


def validate_package(package: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("jsonschema_required_for_package_validation") from exc
    errors = sorted(jsonschema.Draft202012Validator(read_json(SCHEMA_PATH)).iter_errors(package), key=lambda e: list(e.path))
    return ["/" + "/".join(str(p) for p in error.path) + ": " + error.message for error in errors]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at", default="2026-10-21T00:00:00Z")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    package = build_package(generated_at=args.generated_at)
    errors = validate_package(package)
    if errors:
        raise PackageError("schema_validation_failed: " + "; ".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "report_count": len(package["match_reports"]), "validation_errors": errors}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
