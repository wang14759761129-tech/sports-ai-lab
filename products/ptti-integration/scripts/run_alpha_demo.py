"""Run the local, fixture-only PTTI Alpha Match/Media handoff demo."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from alpha_demo import build_alpha_demo, write_demo_files  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory for a schema-valid contract and its rights/ID audit.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace differing files only in the explicitly supplied demo output directory.",
    )
    args = parser.parse_args(argv)
    if args.replace and args.output_dir is None:
        parser.error("--replace requires --output-dir")

    contract, audit = build_alpha_demo()
    print("PTTI_ALPHA_DEMO mode=SANITIZED_FIXTURES db=NOT_USED network=NOT_USED media=NOT_OPENED")
    print(
        "CONTRACT "
        f"version={contract['contract_version']} schema={audit['schema']['status']} "
        f"integrity={audit['integrity']['status']} matches={len(contract['matches'])} "
        f"video_sources={len(contract['video_sources'])} local_assets={len(contract['local_video_assets'])}"
    )
    print(
        "VERSION_GATE "
        f"v0_1={audit['v0_1_consumer']['status']} "
        f"code={audit['v0_1_consumer']['code']}"
    )
    for row in audit["identity_map"]["match_sources"]:
        match = next(item for item in contract["matches"] if item["match_id"] == row["match_id"])
        source_ids = ",".join(row["video_source_ids"]) or "NONE"
        print(
            "MATCH_LINK "
            f"match={row['match_id']} event={match['event']['name'] or 'UNKNOWN'} "
            f"discipline={match['discipline']} sources={source_ids} "
            f"identity={row['identity_status']} relation={row['link_status']}"
        )
    for source in contract["video_sources"]:
        synthetic = source["provenance"]["method"].startswith("synthetic-fixture:")
        external_status = source["evidence"]["external_video_page"]["status"]
        platform = source["platform"].replace(" · ", " / ")
        print(
            "SOURCE "
            f"id={source['source_id']} match={source.get('match_id') or 'UNLINKED'} "
            f"platform={platform} kind={source['resource_kind']} "
            f"content={source['content_type']} watch={source['canonical_url']} "
            "entry=EXTERNAL_CANDIDATE_NOT_PERMISSION "
            f"page={source['evidence']['page_access']['status']} external_visual={external_status} "
            f"embed_right={source['rights']['embedding']} "
            f"embed_test={source['evidence']['embed_playback']['status']} "
            f"native={source['evidence']['desktop_native_playback']['status']} "
            f"listing={source['rights']['metadata_listing']} external_right={source['rights']['external_viewing']} "
            f"thumbnail_right={source['rights']['thumbnail_display']} thumbnail_url={source['thumbnail_url'] or 'NONE'} "
            "source_sha=NOT_REPRESENTED timeline_id=NOT_REPRESENTED pts_time_base=NOT_REPRESENTED "
            f"territory={source['territory']['status']} "
            f"projection={'SYNTHETIC_EXCLUDED' if synthetic else 'PENDING_RIGHTS'}"
        )
    for relation in audit["identity_map"]["local_assets"]:
        asset = next(
            item for item in contract["local_video_assets"]
            if item["local_asset_id"] == relation["local_asset_id"]
        )
        timeline = asset["timeline"]
        time_base = timeline.get("time_base")
        time_base_text = (
            f"{time_base['numerator']}/{time_base['denominator']}" if time_base else "UNKNOWN"
        )
        print(
            "LOCAL_ASSET "
            f"id={relation['local_asset_id']} match={relation['match_id'] or 'UNLINKED'} "
            f"association={relation['association']} synthetic={relation['synthetic_fixture']} "
            f"sha={relation['actual_file_sha256']} timeline={timeline['timeline_id']} "
            f"time_base={time_base_text} native={asset['desktop_playback']['status']} "
            f"vision={asset['vision_result']['status']} locator=LOCAL_ONLY "
            f"local_analysis={asset['rights']['local_analysis']}_FIXTURE_ONLY "
            f"training={asset['rights']['model_training']} redistribution={asset['rights']['redistribution']}"
        )
    print(
        "WEB_PROJECTION "
        f"status={audit['web_projection']['status']} matches={audit['web_projection']['match_count']} "
        f"sources={audit['web_projection']['source_count']} "
        f"local_assets={audit['web_projection']['local_asset_count']}"
    )
    for item in audit["rights_review_queue"]:
        print(
            "RIGHTS_REVIEW "
            f"source={item['source_id']} field={item['field']} current={item['current']} "
            f"decision={item['decision']} evidence_needed={item['evidence_needed']}"
        )
    for item in audit["local_asset_review_queue"]:
        print(
            "LOCAL_REVIEW "
            f"asset={item['local_asset_id']} field={item['field']} current={item['current']} "
            f"decision={item['decision']} evidence_needed={item['evidence_needed']}"
        )
    for item in audit["rejected_candidates"]:
        print(
            "CANDIDATE_REJECTED "
            f"kind={item['kind']} id={item.get('mapping_id') or item.get('local_asset_id')} "
            f"status={item.get('status', 'UNKNOWN')} reason={item['reason']}"
        )
    print(
        "EVIDENCE_SUMMARY "
        f"stored_external_visual_snapshots={audit['stored_external_visual_pass_snapshot_count']} "
        f"fresh_checks_this_run={audit['fresh_external_checks_this_run']} "
        f"desktop_native_passes={audit['desktop_native_playback_passes']} "
        f"vision_result_passes={audit['vision_result_passes']}"
    )

    if args.output_dir is not None:
        contract_path, audit_path = write_demo_files(args.output_dir, replace=args.replace)
        print(f"OUTPUT contract={contract_path} audit={audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
