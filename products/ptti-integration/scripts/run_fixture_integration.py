"""Run a read-only, sanitized match/media contract demonstration."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import (  # noqa: E402
    UnsupportedContractVersion,
    build_contract,
    require_exact_contract_version,
    to_web_safe_payload,
)


def read_fixture(name: str):
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    print(
        "DEMO_MODE fixture_snapshot=READ_ONLY database=NOT_USED "
        "network=NOT_USED real_media=NOT_OPENED"
    )
    untrusted = read_fixture("untrusted-inputs.json")
    contract = build_contract(
        web_records=read_fixture("web-match-records.json"),
        desktop_sources=[
            read_fixture("desktop-video-source.json"),
            untrusted["desktop_source_without_rights"],
        ],
        local_assets=[read_fixture("desktop-local-asset.json")],
        timeline_mappings=[untrusted["unverified_timeline_mapping"]],
    )
    public = to_web_safe_payload(contract)
    web_only_public = to_web_safe_payload(
        build_contract(web_records=read_fixture("web-match-records.json"))
    )

    schema = json.loads(
        (ROOT / "contracts" / "match-media-v0.2.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(contract)

    # A consumer that only declares v0.1 must stop before interpreting v0.2.
    try:
        require_exact_contract_version(contract, "ptti.match-media/0.1")
    except UnsupportedContractVersion as exc:
        assert exc.code == "UNSUPPORTED_CONTRACT_VERSION"
        assert exc.received_version == "ptti.match-media/0.2"
        print(
            "VERSION_REJECTION_PASS "
            f"expected={exc.expected_version} received={exc.received_version} code={exc.code}"
        )
    else:
        raise AssertionError("A v0.1-only consumer must reject a v0.2 contract.")

    schema_v01 = json.loads(
        (ROOT / "contracts" / "match-media-v0.1.schema.json").read_text(encoding="utf-8")
    )
    v01_errors = list(
        Draft202012Validator(schema_v01, format_checker=FormatChecker()).iter_errors(contract)
    )
    assert any(
        error.validator == "const"
        and list(error.path) == ["contract_version"]
        and error.validator_value == "ptti.match-media/0.1"
        for error in v01_errors
    )
    print("V01_SCHEMA_REJECTION_PASS path=contract_version mode=exact-version-no-fallback")

    assert contract["contract_version"] == "ptti.match-media/0.2"
    assert len(contract["matches"]) == 4
    assert len(contract["video_sources"]) == 6
    assert len(contract["local_video_assets"]) == 1
    external_visual_passes = sum(
        source["evidence"]["external_video_page"]["status"] == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS"
        for source in contract["video_sources"]
    )
    assert all(
        source["evidence"]["desktop_native_playback"]["status"] == "NOT_TESTED"
        for source in contract["video_sources"]
        if source["source_id"].startswith("web-source:")
    )
    assert all(
        source["evidence"]["embed_playback"]["status"] == "NOT_TESTED"
        for source in contract["video_sources"]
        if source["source_id"].startswith("web-source:")
    )
    assert contract["local_video_assets"][0]["rights"]["local_analysis"] == "ALLOWED"
    assert contract["local_video_assets"][0]["rights"]["redistribution"] == "UNKNOWN"
    assert public["local_video_assets"] == []
    assert public["video_sources"] == []
    assert web_only_public["matches"] == []
    assert web_only_public["video_sources"] == []
    assert contract["timeline_mappings"][0]["offset_ms"] is None

    public_source_ids = {source["source_id"] for source in public["video_sources"]}
    web_sources_by_match: dict[str, list[dict]] = {}
    for source in contract["video_sources"]:
        if source["source_id"].startswith("web-source:"):
            if source.get("match_id"):
                web_sources_by_match.setdefault(source["match_id"], []).append(source)
            assert all(
                source["rights"][key] == "UNKNOWN"
                for key in (
                    "metadata_listing", "thumbnail_display", "external_viewing", "embedding",
                    "local_analysis", "model_training", "redistribution",
                )
            )
            assert source["thumbnail_url"] is None
            missing_rights = [
                f"{key}={source['rights'][key]}"
                for key in ("metadata_listing", "external_viewing")
                if source["rights"][key] != "ALLOWED"
            ]
            print(
                "WEB_RIGHTS_AUDIT "
                f"source={source['source_id']} listing={source['rights']['metadata_listing']} "
                f"external={source['rights']['external_viewing']} thumbnail={source['rights']['thumbnail_display']} "
                f"embed={source['rights']['embedding']} local_analysis={source['rights']['local_analysis']} "
                f"training={source['rights']['model_training']} redistribution={source['rights']['redistribution']} "
                f"content_type={source['content_type']} "
                f"public_projection=EXCLUDED reason={','.join(missing_rights)}"
            )
            print(
                "WEB_SAMPLE "
                f"source={source['source_id']} match={source['match_id']} "
                f"route={source['resource_kind']} content_type={source['content_type']} "
                f"match_link={source['match_link_status']} "
                f"external_visual={source['evidence']['external_video_page']['status']} "
                f"embed={source['evidence']['embed_playback']['status']} "
                f"desktop_native={source['evidence']['desktop_native_playback']['status']} "
                f"canonical_url={source['canonical_url']} evidence_origin=FIXTURE_SNAPSHOT"
            )
    assert len(web_sources_by_match) == 4
    assert all(
        len(web_sources_by_match.get(match["match_id"], [])) == 1
        for match in contract["matches"]
    )

    for match in contract["matches"]:
        match_id = match["match_id"]
        sources = web_sources_by_match.get(match_id, [])
        source = sources[0] if sources else None
        if source is None:
            entry_url = "NONE"
            entry_kind = "UNKNOWN"
            projection = "EXCLUDED"
            reasons = ["OFFICIAL_ENTRY_NOT_PRESENT"]
        else:
            entry_url = source["canonical_url"]
            entry_kind = source["resource_kind"]
            projection = "PROJECTED" if source["source_id"] in public_source_ids else "EXCLUDED"
            reasons = [
                f"{key.upper()}={source['rights'][key]}"
                for key in ("metadata_listing", "external_viewing")
                if source["rights"][key] != "ALLOWED"
            ]
            if not reasons and projection == "EXCLUDED":
                reasons = ["REJECTED_BY_PUBLIC_PROJECTION_POLICY"]
        names = match.get("participant_names_unassigned") or []
        matchup = " vs ".join(names) if names else "UNKNOWN"
        print(
            "MATCH_ENTRY "
            f"match={match_id} event={match['event'].get('name') or 'UNKNOWN'} "
            f"discipline={match['discipline']} round={match.get('round') or 'UNKNOWN'} "
            f"participants={matchup} entry_kind={entry_kind} official_entry={entry_url} "
            f"public_projection={projection} "
            f"reason={','.join(reasons) if reasons else 'NONE'}"
        )

    for source in contract["video_sources"]:
        if source["source_id"].startswith("web-source:"):
            native = source["evidence"]["desktop_native_playback"]
            print(
                "WEB_SOURCE_BINDING "
                f"source={source['source_id']} source_sha256=UNKNOWN_NOT_MEASURED "
                "timeline_id=UNKNOWN_NOT_REPRESENTED pts=UNKNOWN_NOT_PROVIDED "
                "time_base=UNKNOWN_NOT_PROVIDED "
                "timeline_mapping=NOT_VERIFIED "
                f"desktop_native={native['status']} "
                "package_sha256=NOT_TESTED source_sha256_binding=NOT_TESTED"
            )

    for asset in contract["local_video_assets"]:
        timeline = asset["timeline"]
        time_base = timeline.get("time_base")
        time_base_label = (
            f"{time_base['numerator']}/{time_base['denominator']}"
            if isinstance(time_base, dict)
            else "UNKNOWN"
        )
        print(
            "LOCAL_ASSET_BINDING fixture=SYNTHETIC "
            f"asset={asset['local_asset_id']} source_sha256={asset['source_sha256']} "
            "actual_file_hash=NOT_TESTED "
            f"timeline_id={timeline['timeline_id']} time_base={time_base_label} "
            "pts_samples=NOT_INCLUDED cross_source_mapping=NOT_VERIFIED "
            f"desktop_native={asset['desktop_playback']['status']} "
            f"vision={asset['vision_result']['status']} "
            f"local_analysis={asset['rights']['local_analysis']} "
            f"training={asset['rights']['model_training']} "
            f"redistribution={asset['rights']['redistribution']} local_path=REDACTED"
        )

    print(
        "FIXTURE_PIPELINE_PASS "
        f"schema={schema['$id']} "
        f"matches={len(contract['matches'])} "
        f"video_sources={len(contract['video_sources'])} "
        f"local_assets={len(contract['local_video_assets'])} "
        f"combined_web_safe_sources={len(public['video_sources'])} "
        "web_only_public_sources=0 synthetic_desktop_public_sources=0 "
        f"external_visual_passes={external_visual_passes} "
        "native_passes=0 embed_passes=0 vision_results=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
