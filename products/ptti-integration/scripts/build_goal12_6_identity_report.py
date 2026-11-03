"""Regenerate a private evidence report and compatible Cinema projection, offline."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRATION))
from cinema_source_review import build_source_review  # noqa: E402
from match_library_index import build_indexes  # noqa: E402


def build():
    evidence = json.loads((INTEGRATION / "fixtures/goal12-6-match-identity-evidence.json").read_text(encoding="utf-8"))
    observations = json.loads((INTEGRATION / "fixtures/goal12-3-selected-source-observations.json").read_text(encoding="utf-8"))
    records = {row["source_id"]: row for row in evidence["records"]}
    if len(records) != 3 or len(evidence["records"]) != 3 or set(records) != {row["source_id"] for row in observations["sources"]}:
        raise ValueError("Expected exactly three unique reviewed sources")
    for source in observations["sources"]:
        review = records[source["source_id"]]
        fresh = review["oembed_observation"]
        if fresh["http_status"] != 200 or review["video_id"] != source["source_id"].rsplit(":", 1)[1]:
            raise ValueError("Metadata observation must match the exact selected video")
        for key in ("checked_at", "title", "author_name", "author_url"):
            source["source_metadata"][key] = fresh[key]
        excluded = {item["url"] for item in review["excluded_or_limited_sources"]
                    if item["status"] == "CONFLICTING_DYNAMIC_EVENT_ID_NOT_IDENTITY_EVIDENCE"}
        source["event_match_review"]["evidence_sources"] = [
            item for item in source["event_match_review"]["evidence_sources"] if item["url"] not in excluded
        ]
    index, public = build_indexes(INTEGRATION.parents[1], generated_at=evidence["reviewed_at"])
    if public["video_sources"]:
        raise ValueError("Public catalog must remain empty; no fallback permitted")
    projection = build_source_review(index, observations, evidence["reviewed_at"])
    report = copy.deepcopy(evidence)
    report["cinema_contract_version"] = projection["contract_version"]
    report["public_admission"] = "BLOCKED_NO_SCOPED_PERMISSION_AND_CANONICAL_BINDING"
    report["summary"] = {"reviewed_sources": 3, "fresh_oembed_metadata_http_200": 3,
                         "canonical_match_video_bindings": 0, "strict_public_sources": 0,
                         "external_visual_playback_pass": 0, "desktop_native_playback_pass": 0}
    for record, source in zip(report["records"], projection["featured_sources"]):
        if record["source_id"] != source["source_id"]:
            raise ValueError("Source order/identity mismatch")
        record["canonical_match_id"] = None
        record["watch_url"] = source["original_source_url"]
        record["rights"] = copy.deepcopy(source["rights"])
        record["download_permission"] = "UNKNOWN_NO_SCOPED_LICENSE_EVIDENCE"
        record["playback"] = {"metadata_lookup": "PASS_METADATA_ONLY", "external_visual": "NOT_TESTED",
                              "embedding": "NOT_TESTED", "desktop_native": "NOT_TESTED", "vision": "NOT_TESTED",
                              "region": "UNKNOWN", "completeness": "UNVERIFIED",
                              "historical_embed_status": source["watch_status"]["latest_recorded_embed_technical_status"],
                              "oembed_html_is_not_playback_or_permission": True}
    return report, projection


if __name__ == "__main__":
    report, projection = build()
    output = INTEGRATION / "generated/goal12-6"
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("match-identity-evidence.json", report), ("cinema-source-review-internal.json", projection)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"]))
