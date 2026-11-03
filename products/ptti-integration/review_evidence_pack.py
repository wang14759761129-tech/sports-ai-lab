"""Readable evidence export layered over the existing Review Targets view."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from quick_annotation import adapt_quick_annotation
from review_targets import STAGES, VERSION as REVIEW_TARGETS_VERSION, build_review_targets

VERSION = "ptti.review-evidence-pack/0.1"


def _generated_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("generated_at_utc must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _game_progress(payload: dict, review: dict, draft: dict) -> dict:
    if review["sample"]["game_count"] != 1:
        raise ValueError("review evidence pack currently accepts exactly one game")
    contexts = payload.get("rules_context", {}).get("games", [])
    if len(contexts) != 1:
        raise ValueError("review evidence pack currently accepts exactly one declared game")
    context = contexts[0]
    game_number = context.get("game_number", draft["points"][0]["protocol_fields"]["game_number"])
    rows = [p for p in draft["points"] if p["protocol_fields"]["game_number"] == game_number]
    numbers = [p["protocol_fields"]["point_number"] for p in rows]
    stats = review["sample"]["game_counts"].get(str(game_number), {})
    score = {"A": stats.get("player_wins", 0), "B": stats.get("opponent_wins", 0)}
    all_known = stats.get("known_winner_count", 0) == stats.get("point_count", -1)
    complete_sequence = (review["sample"]["protocol_sequence_valid"] and bool(numbers)
                         and numbers[0] == 1 and numbers == list(range(1, len(numbers) + 1)))
    complete_coverage = context.get("coverage") == "COMPLETE_FROM_GAME_START"
    terminal = max(score.values()) >= 11 and abs(score["A"] - score["B"]) >= 2
    if not (complete_sequence and complete_coverage and all_known):
        status = "INDETERMINATE"
    else:
        status = "ENDED_BY_RULE_SCORE" if terminal else "IN_PROGRESS"
    return {
        "game_number": game_number, "point_count": len(rows), "score": score, "score_status": status,
        "completion_rule": "At least 11 points and a lead of 2; ordered sequence complete from 0:0 and all winners known.",
        "coverage_declaration": context.get("coverage", "UNKNOWN"),
        "sequence_valid": complete_sequence,
        "known_winner_count": stats.get("known_winner_count", 0),
        "unknown_winner_count": len(rows) - stats.get("known_winner_count", 0),
        "point_ids": [p["point_id"] for p in rows],
    }


def build_review_evidence_pack(
    payload: dict, *, generated_at_utc: str | None = None,
    raw_input_bytes: bytes | None = None, input_name: str | None = None,
    display_caution_threshold: int = 5,
) -> dict:
    """Reuse Review Targets counts and add concise provenance/report structure."""
    review = build_review_targets(payload, display_caution_threshold=display_caution_threshold)
    draft = adapt_quick_annotation(payload)
    if review["contract_version"] != REVIEW_TARGETS_VERSION:
        raise ValueError("unsupported Review Targets output version")
    raw_points = {p["point_id"]: p for p in payload["points"]}
    adapted = {p["point_id"]: p for p in draft["points"]}
    if raw_points.keys() != adapted.keys():
        raise ValueError("input point IDs do not match adapted point IDs")

    ids = [p["point_id"] for p in draft["points"]]
    known_winner_ids = [pid for pid in ids if adapted[pid]["protocol_fields"]["point_winner"] in {"player", "opponent"}]
    unknown_winner_ids = [pid for pid in ids if adapted[pid]["protocol_fields"]["point_winner"] == "unknown"]
    unknown_stage_ids = [pid for pid in ids if adapted[pid].get("observed_rally_stage", "UNKNOWN") == "UNKNOWN"]
    raw_unknown_server_ids = [pid for pid in ids if raw_points[pid]["server"] == "unknown"]
    ranged_ids = [pid for pid in known_winner_ids
                  if adapted[pid]["timestamp"]["range_status"] == "CHECKED_AGAINST_USER_REPORTED_DURATION"
                  and adapted[pid]["timestamp"]["start_ms"] is not None
                  and adapted[pid]["timestamp"]["end_ms"] is not None]
    ranged_set = set(ranged_ids)
    missing_range_ids = [pid for pid in known_winner_ids if pid not in ranged_set]

    athletes = {a["role"]: a for a in review["athletes"]}
    roles = {"A": ("player", "INPUT_ROLE_ONLY"), "B": ("opponent", "INPUT_ROLE_ONLY")}
    score_by_role, service_by_role, observed_stages = {}, {}, {}
    for label, (role, identity_status) in roles.items():
        score_by_role[label] = {"review_role": role, "identity_status": identity_status, **athletes[role]["score"]}
        service_by_role[label] = {"review_role": role, "identity_status": identity_status, **athletes[role]["service"]}
    for stage in STAGES:
        observed_stages[stage] = {
            label: {"review_role": role, "identity_status": identity_status,
                    **athletes[role]["observed_stages"][stage]}
            for label, (role, identity_status) in roles.items()
        }

    contexts = payload.get("rules_context", {}).get("games", [])
    context = contexts[0] if len(contexts) == 1 else {}
    first_server = context.get("first_server", "unknown")
    if context.get("coverage") == "COMPLETE_FROM_GAME_START" and first_server in {"player", "opponent"}:
        service_basis = "RULE_DERIVED_FROM_DECLARED_GAME_START_AND_FIRST_SERVER"
    elif any(adapted[pid]["protocol_fields"]["server"] != "unknown" for pid in ids):
        service_basis = "EXPLICIT_OR_ADAPTER_VALIDATED_SERVER_INPUT"
    else:
        service_basis = "UNKNOWN"

    point_index = []
    for p in draft["points"]:
        protocol, timestamp = p["protocol_fields"], p["timestamp"]
        point_index.append({
            "point_id": p["point_id"], "winner": protocol["point_winner"],
            "server": protocol["server"], "server_derivation": p["field_derivation"]["server"],
            "score_before_A_B": p["score_before_player_opponent"],
            "observed_rally_stage": p.get("observed_rally_stage", "UNKNOWN"),
            "time_range": {"start_ms": timestamp["start_ms"], "end_ms": timestamp["end_ms"],
                           "range_status": timestamp["range_status"],
                           "timeline_binding": timestamp["timeline_binding"],
                           "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION"},
            "key_point_status": p["key_point_status"],
        })
    targets = {t["target_id"]: t for t in review["review_targets"]}
    candidates = [{**targets[o["target_id"]], "text_zh": o["text_zh"]}
                  for o in review["observations"][:2]]

    safe_input_name = input_name.replace("\\", "/").rsplit("/", 1)[-1] if input_name else None
    return {
        "contract_version": VERSION,
        "generated_at_utc": _generated_at(generated_at_utc),
        "input": {
            "input_name": safe_input_name,
            "input_contract_version": review["input_contract_version"],
            "statistics_contract_version": review["statistics_contract_version"],
            "review_targets_contract_version": review["contract_version"],
            "canonical_input_sha256": review["canonical_input_sha256"],
            "canonical_hash_semantics": "SHA-256 over parsed UTF-8 JSON with sorted keys, compact separators and preserved Unicode; formatting-only changes do not alter it.",
            "raw_input_sha256": hashlib.sha256(raw_input_bytes).hexdigest() if raw_input_bytes is not None else None,
            "raw_hash_semantics": "Exact input file byte identity when supplied by the CLI; not proof of truth, rights, or media identity.",
        },
        "match": {
            "match_id": review["dataset"]["match_id"], "dataset_id": review["dataset"]["dataset_id"],
            "dataset_class": review["dataset"]["dataset_class"],
            "identity_status": review["dataset"]["match_link_status"],
            "game": _game_progress(payload, review, draft),
        },
        "source_and_rights": {
            "source_status": review["evidence_status"], "source_id": review["dataset"]["source_id"],
            "source_link_status": review["dataset"]["source_link_status"],
            "rights_status": review["dataset"]["rights_status"],
            "source_video_sha256": review["dataset"]["source_video_sha256"],
            "timeline_id": review["dataset"]["timeline_id"], "pts": review["dataset"]["pts"],
            "time_base": review["dataset"]["time_base"], "vision_status": review["dataset"]["vision_status"],
            "playback_eligibility": "NOT_EVALUATED_CURRENT_SESSION",
        },
        "sample": {
            "point_count": len(ids), "point_ids": ids,
            "score_by_role": score_by_role, "service_by_role": service_by_role,
            "service_basis": service_basis, "raw_unknown_server_point_ids": raw_unknown_server_ids,
            "observed_rally_stages": observed_stages,
            "unknown_stage": {"count": len(unknown_stage_ids), "point_ids": unknown_stage_ids,
                              "scope": "All supplied point rows, regardless of winner."},
            "unknown_winner": {"count": len(unknown_winner_ids), "point_ids": unknown_winner_ids,
                               "scope": "winner=unknown rows; excluded from known score denominators."},
            "time_range_coverage": {
                **review["time_range_coverage"], "range_checked_point_ids": ranged_ids,
                "missing_range_point_ids": missing_range_ids,
                "scope": "Known-winner rows; duration range checked only, timestamps remain unbound to a source timeline.",
            },
            "display_caution_threshold": review["display_caution_threshold"],
            "threshold_is_significance_test": False, "point_evidence_index": point_index,
        },
        "review_candidates": candidates,
        "limitations": [
            "This projection reuses ptti.review-targets/0.1; it adds no statistical inference.",
            "A/B are input roles, not verified athlete identities. SIMULATED_ONLY is not real-match evidence.",
            "A terminal score is derived only from the complete ordered known-winner sequence and is not external match verification.",
            "Coarse observed stages do not establish exact contacts, third-ball tactics, spin, placement, or error cause.",
            "Point IDs are traceable records, not proof of current-session media availability or playback.",
            "The export includes no video bytes or local media/database paths; it grants no rights, timeline binding, native playback, or Vision result.",
            "The configurable sample threshold is a display caution, not a significance test; one game does not establish a stable tendency.",
        ],
    }


def render_markdown(pack: dict) -> str:
    sample, game = pack["sample"], pack["match"]["game"]
    status = {"ENDED_BY_RULE_SCORE": "按逐分序列达到规则终局",
              "IN_PROGRESS": "当前序列尚未达到规则终局",
              "INDETERMINATE": "无法确认局状态"}[game["score_status"]]
    a, b = sample["score_by_role"]["A"], sample["score_by_role"]["B"]
    sa, sb = sample["service_by_role"]["A"], sample["service_by_role"]["B"]
    time = sample["time_range_coverage"]
    lines = [
        "# PTTI 单局复盘证据摘要", "",
        f"> **来源状态：{pack['source_and_rights']['source_status']}。** 本报告使用模拟逐分数据，仅用于验证报告流程。", "",
        f"- 比赛 ID：`{pack['match']['match_id']}`",
        f"- 数据集 ID：`{pack['match']['dataset_id']}`",
        f"- 局号：{game['game_number']}；录入点数：{game['point_count']}；A:B = {game['score']['A']}:{game['score']['B']}（{status}）",
        f"- 输入版本：`{pack['input']['input_contract_version']}`；统计版本：`{pack['input']['statistics_contract_version']}`；Review Targets：`{pack['input']['review_targets_contract_version']}`",
        f"- 生成时间（UTC）：`{pack['generated_at_utc']}`",
        f"- Canonical SHA-256：`{pack['input']['canonical_input_sha256']}`",
        f"- 原始输入字节 SHA-256：`{pack['input']['raw_input_sha256'] or '未提供'}`（仅证明字节身份）", "",
        "## 得分与发球", "",
        "已知得分统计包含没有视频时间的记录；N 为胜者已知的记录数。", "",
        "| 输入角色 | 得分 | N | 未知胜者 |", "|---|---:|---:|---:|",
        f"| A（player） | {a['won_count']} 胜 / {a['lost_count']} 负 | {a['denominator']} | {a['unknown_count']} |",
        f"| B（opponent） | {b['won_count']} 胜 / {b['lost_count']} 负 | {b['denominator']} | {b['unknown_count']} |", "",
        f"发球侧依据：`{sample['service_basis']}`。显式 UNKNOWN 发球方有 {len(sample['raw_unknown_server_point_ids'])}/{sample['point_count']} 条；在完整开局声明和首发球方已知时由既有规则适配器推导轮换。", "",
        "| 发球角色 | 得分 / 失分 | 有效发球分母 N | 未知 / 排除 |", "|---|---:|---:|---:|",
        f"| A（player） | {sa['won_count']} / {sa['lost_count']} | {sa['denominator']} | {sa['unknown_count']} / {sa['excluded_count']} |",
        f"| B（opponent） | {sb['won_count']} / {sb['lost_count']} | {sb['denominator']} | {sb['unknown_count']} / {sb['excluded_count']} |", "",
        "发球分母仅含该角色发球且胜者已知的逐分；发球结果不是对发球技术的独立视频观察。", "",
        "## 人工观察的回合阶段", "",
        "N 为该阶段中胜者已知的记录数。UNKNOWN 阶段不并入已观察阶段。", "",
        "| 阶段 | A 胜/负/N | B 胜/负/N | 该组 UNKNOWN |", "|---|---:|---:|---:|",
    ]
    for stage, label in (("END_AFTER_1_2_CONTACTS", "1–2板"),
                         ("END_AFTER_3_4_CONTACTS", "3–4板"),
                         ("END_AFTER_5_PLUS_CONTACTS", "5板及以上")):
        ma, mb = sample["observed_rally_stages"][stage]["A"], sample["observed_rally_stages"][stage]["B"]
        lines.append(f"| {label} | {ma['won_count']}/{ma['lost_count']}/{ma['denominator']} | {mb['won_count']}/{mb['lost_count']}/{mb['denominator']} | {ma['unknown_count']} |")
    lines.extend(["", "每个表格指标的 `valid/won/lost/unknown/excluded` 完整 point_id 分区见机器报告 `sample.score_by_role`、`sample.service_by_role` 与 `sample.observed_rally_stages`。", "",
                  f"UNKNOWN 阶段：{sample['unknown_stage']['count']} 条（{', '.join(sample['unknown_stage']['point_ids'])}），范围为全部输入记录。各阶段的 unknown_count 不可跨组相加。", "", "## 值得人工回看的记录", ""])
    if not pack["review_candidates"]:
        lines.append("当前没有包含已知失分的非空阶段分组。")
    for candidate in pack["review_candidates"]:
        who = "A（player）" if candidate["subject_role"] == "player" else "B（opponent）"
        stage = {"END_AFTER_1_2_CONTACTS": "1–2板", "END_AFTER_3_4_CONTACTS": "3–4板",
                 "END_AFTER_5_PLUS_CONTACTS": "5板及以上"}[candidate["observed_rally_stage"]]
        caution = (f"样本不足（N<{sample['display_caution_threshold']}），不能据此判断长期倾向。"
                   if candidate["sample_status"] == "INSUFFICIENT_SAMPLE" else "这是单局描述，不能代表长期倾向。")
        lines.extend([f"### {who}｜{stage}", "",
                      f"已观察到 {candidate['lost_count']} 次失分；该组已知胜负分母 N={candidate['denominator']}。{caution}", "",
                      "完整逐分 ID：", "", *[f"- `{pid}`" for pid in candidate["point_ids"]], "",
                      f"证据：`{candidate['evidence_status']}`；播放资格：`{candidate['playback_eligibility']}`。这些 ID 是待核对记录，尚未确认对应片段可播放。",
                      "", "建议对照对应回合；本报告不推断具体技术、失误原因或训练处方。", ""])
    lines.extend(["## 时间与证据边界", "",
                  f"双方时间边界通过用户报告时长范围检查：{time['numerator']}/{time['denominator']}；缺少边界：{time['missing_count']}/{time['denominator']}。这些时间仍是 UNBOUND。",
                  "有范围检查记录的完整 point IDs：", "",
                  *[f"- `{pid}`" for pid in time["range_checked_point_ids"]], "",
                  "缺少时间边界的完整 point IDs：", "",
                  *[f"- `{pid}`" for pid in time["missing_range_point_ids"]], "",
        f"来源 ID：`{pack['source_and_rights']['source_id'] or '未绑定（null）'}`；版权：`{pack['source_and_rights']['rights_status']}`；时间轴：`{pack['source_and_rights']['timeline_id'] or '未绑定（null）'}`；Vision：`{pack['source_and_rights']['vision_status']}`；播放资格：`{pack['source_and_rights']['playback_eligibility']}`。", "",
                  f"小样本提示阈值为 N<{sample['display_caution_threshold']}，是可配置展示提醒，不是统计显著性检验。", "",
                  "报告不包含视频字节或本机路径。A/B 是输入角色，不是已核实运动员身份；SIMULATED_ONLY 不代表真实比赛分析。", ""])
    return "\n".join(lines)
