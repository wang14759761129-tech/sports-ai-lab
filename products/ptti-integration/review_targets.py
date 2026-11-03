"""Traceable descriptive view over validated Quick Annotation drafts; no media authority."""
from __future__ import annotations

import hashlib
import json

from quick_annotation import (
    OBSERVED_RALLY_STAGES, QUICK_STATS_MIN_DISPLAY_SAMPLE,
    adapt_quick_annotation, summarize_quick_annotation,
)

VERSION = "ptti.review-targets/0.1"
STAGES = sorted(OBSERVED_RALLY_STAGES - {"UNKNOWN"})


def build_review_targets(payload: dict, *, display_caution_threshold: int = QUICK_STATS_MIN_DISPLAY_SAMPLE) -> dict:
    """Validate raw input through existing adapter/stats, then attach point-ID membership.

    player/opponent are input roles, never inferred real athlete identities.
    Unknown group membership is counted separately from known excluded rows.
    """
    draft = adapt_quick_annotation(payload)
    stats = summarize_quick_annotation(draft, display_caution_threshold=display_caution_threshold)
    points = draft["points"]
    evidence = stats["evidence_status"]

    def metric(side, group, rule):
        ids = {key: [] for key in ("valid", "won", "lost", "unknown", "excluded")}
        for point in points:
            pid = point["point_id"]
            membership = group(point)
            winner = point["protocol_fields"]["point_winner"]
            if membership is False:
                ids["excluded"].append(pid)
            elif membership is None or winner == "unknown":
                ids["unknown"].append(pid)
            else:
                ids["valid"].append(pid)
                ids["won" if winner == side else "lost"].append(pid)
        n = len(ids["valid"])
        return {
            "won_count": len(ids["won"]), "lost_count": len(ids["lost"]),
            "denominator": n, "sample_count": len(points),
            "unknown_count": len(ids["unknown"]), "excluded_count": len(ids["excluded"]),
            "point_ids": ids, "computation_rule": rule, "evidence_status": evidence,
            "sample_status": "NOT_ESTIMABLE" if n == 0 else (
                "INSUFFICIENT_SAMPLE" if n < display_caution_threshold else "DESCRIPTIVE_ONLY"),
        }

    athletes = []
    targets = []
    for side in ("player", "opponent"):
        score = metric(side, lambda p: True,
                       "Explicit known winners across all supplied rows, including rows without video times.")
        service = metric(side, lambda p: None if p["protocol_fields"]["server"] == "unknown"
                         else p["protocol_fields"]["server"] == side,
                         "Known winners when this input role serves; unknown server or eligible unknown winner is unknown; known other server is excluded.")
        stages = {}
        for stage in STAGES:
            result = metric(side, lambda p, stage=stage: None if p.get("observed_rally_stage", "UNKNOWN") == "UNKNOWN"
                            else p["observed_rally_stage"] == stage,
                            "Known winners within this explicitly observed coarse stage; unknown stage or eligible unknown winner is unknown; known other stage is excluded.")
            stages[stage] = result
            if result["lost_count"]:
                targets.append({
                    "target_id": f"{draft['dataset']['dataset_id']}/{side}/{stage}",
                    "subject_role": side, "observed_rally_stage": stage,
                    "lost_count": result["lost_count"], "denominator": result["denominator"],
                    "unknown_count": result["unknown_count"], "point_ids": result["point_ids"]["lost"],
                    "evidence_status": evidence, "sample_status": result["sample_status"],
                    "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
                })
        athletes.append({"role": side, "identity_status": "INPUT_ROLE_ONLY",
                         "score": score, "service": service, "observed_stages": stages})
    # At most two descriptions; never diagnose technique or prescribe training.
    observations = []
    for target in sorted(targets, key=lambda t: (-t["lost_count"], t["target_id"]))[:2]:
        caution = ("样本不足，不能据此判断长期倾向。" if target["sample_status"] == "INSUFFICIENT_SAMPLE"
                   else "单局描述不能代表长期倾向。")
        observations.append({
            "target_id": target["target_id"], "point_ids": list(target["point_ids"]),
            "text_zh": f"输入角色 {target['subject_role']} 在人工观察的 {target['observed_rally_stage']} 分组中失分 {target['lost_count']} 次，已知胜负样本 N={target['denominator']}。{caution}可核对这些逐分记录；尚不能判断具体技术或失误原因。",
        })
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "contract_version": VERSION, "input_contract_version": payload["contract_version"],
        "statistics_contract_version": stats["contract_version"],
        "canonical_input_sha256": hashlib.sha256(canonical).hexdigest(),
        "dataset": stats["dataset"], "evidence_status": evidence,
        "display_caution_threshold": display_caution_threshold,
        "threshold_is_significance_test": False,
        "sample": stats["sample"], "time_range_coverage": stats["metrics"]["time_range_coverage"],
        "unknown_stage_count": sum(p.get("observed_rally_stage", "UNKNOWN") == "UNKNOWN" for p in points),
        "unknown_server_count": sum(p["protocol_fields"]["server"] == "unknown" for p in points),
        "athletes": athletes, "review_targets": targets, "observations": observations,
        "limitations": [
            "Input roles are not verified athlete identities. Counts retain known winners without video boundaries.",
            "For each metric: denominator + unknown_count + excluded_count = sample_count. Unknown grouping rows recur across groups and must not be summed across groups.",
            "point_ids are traceable record candidates, not verified media or playable segments. San must independently check the current session, source and confirmed boundaries.",
            "Coarse observed stages do not establish exact contact count, third-ball attack, spin, placement or error cause.",
            "Small-sample warnings are configurable display cautions, not significance tests. One game does not establish long-term tendencies.",
            "No formal-report, rights, timeline, native-playback or Vision promotion is performed.",
        ],
    }
