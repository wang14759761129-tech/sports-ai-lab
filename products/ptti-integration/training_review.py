"""Local, evidence-limited training-match review from Protocol v0.3 point CSV.

This is a sidecar to ptti.match-intelligence/0.1. It never reads a database,
decodes video, binds free-text timestamps to PTS, or reports Vision results.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from match_intelligence import (
    EDITABLE_ANNOTATIONS, POINT_FIELDS,
    AnalysisValidationError, analyze_bundle, build_synthetic_demo,
    change_point_annotation, import_manual_csv, parse_protocol_v03_csv,
    serialize_protocol_csv, validate_bundle,
)


REVIEW_VERSION = "ptti.training-review/0.1"
SYNTHETIC_DECLARATION_VERSION = "ptti.training-simulated-declaration/0.1"
REAL_BINDING_VERSION = "ptti.training-source-binding/0.1"
GENERATOR_REF = "goal07-24-point-v1"
MIN_DISPLAY_SAMPLE = 5


def _reject(code: str, message: str) -> None:
    raise AnalysisValidationError(code, message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row_sha256(row: dict) -> str:
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def csv_template() -> bytes:
    """An empty, fillable UTF-8 CSV with the exact v0.3 importer header."""
    import csv
    import io
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerow(POINT_FIELDS)
    template = stream.getvalue().encode("utf-8")
    if parse_protocol_v03_csv(template) != []:
        raise AssertionError("Template header no longer matches the importer")
    return template


def synthetic_declaration(csv_bytes: bytes, *, parent_csv_sha256: str | None = None) -> dict:
    return {
        "declaration_version": SYNTHETIC_DECLARATION_VERSION,
        "dataset_class": "SIMULATED_ONLY",
        "generator_ref": GENERATOR_REF,
        "csv_sha256": _sha256(csv_bytes),
        "parent_csv_sha256": parent_csv_sha256,
    }


def import_simulated_csv(csv_bytes: bytes, declaration: dict) -> dict:
    """Accept the committed generator CSV or exactly one derived annotation edit."""
    required = {"declaration_version", "dataset_class", "generator_ref", "csv_sha256", "parent_csv_sha256"}
    if not isinstance(declaration, dict) or set(declaration) != required:
        _reject("INVALID_SYNTHETIC_DECLARATION", "synthetic declaration fields are incomplete or unexpected")
    if (declaration["declaration_version"] != SYNTHETIC_DECLARATION_VERSION
            or declaration["dataset_class"] != "SIMULATED_ONLY"
            or declaration["generator_ref"] != GENERATOR_REF):
        _reject("UNSUPPORTED_SYNTHETIC_DECLARATION", "only the declared original generator is accepted")
    if declaration["csv_sha256"] != _sha256(csv_bytes):
        _reject("ANNOTATION_CSV_HASH_MISMATCH", "synthetic CSV bytes differ from the declaration")
    base = build_synthetic_demo()
    base_csv_sha = _sha256(serialize_protocol_csv(base))
    rows = parse_protocol_v03_csv(csv_bytes)
    if len(rows) != len(base["points"]):
        _reject("SYNTHETIC_ORIGIN_MISMATCH", "demo rows must match the declared 24-point generator")
    changes = [
        (index, field, original[field], incoming[field])
        for index, (original, incoming) in enumerate(zip(base["points"], rows))
        for field in POINT_FIELDS if original[field] != incoming[field]
    ]
    if not changes:
        if declaration["parent_csv_sha256"] is not None or declaration["csv_sha256"] != base_csv_sha:
            _reject("SYNTHETIC_ORIGIN_MISMATCH", "unmodified generator CSV cannot claim a parent edit")
        validate_bundle(base)
        return base
    if len(changes) != 1 or declaration["parent_csv_sha256"] != base_csv_sha:
        _reject("SYNTHETIC_ORIGIN_MISMATCH", "derived demo requires one exact edit and the original parent CSV hash")
    index, field, _before, after = changes[0]
    if field not in EDITABLE_ANNOTATIONS:
        _reject("SYNTHETIC_IDENTITY_EDIT_FORBIDDEN", "demo cannot change match, point, server, or outcome identity")
    original = base["points"][index]
    edited = change_point_annotation(
        base, game_number=original["game_number"], point_number=original["point_number"], field=field, value=after,
    )
    if edited["points"] != rows:
        _reject("SYNTHETIC_ORIGIN_MISMATCH", "imported CSV does not equal the validated derived bundle")
    return edited


def import_human_training_csv(csv_bytes: bytes, manifest: dict, source_file: str, binding: dict) -> dict:
    """Require an exact local source and a separately reviewed, explicit ID link.

    A binding is an auditable human declaration; no hash or declaration proves
    that a video really depicts the claimed match or that its labels are right.
    """
    bundle = import_manual_csv(csv_bytes, manifest, source_file)
    _require_video_stream_metadata(Path(source_file))
    _validate_human_binding(bundle, binding)
    return bundle


def _validate_human_binding(bundle: dict, binding: dict | None) -> None:
    required = {
        "binding_version", "dataset_id", "match_id", "source_id", "local_asset_id",
        "source_sha256", "match_link_status", "local_analysis_permission",
        "rights_basis_ref", "reviewer_ref", "reviewed_at", "analysis_method",
    }
    if not isinstance(binding, dict) or set(binding) != required:
        _reject("UNVERIFIED_MATCH_SOURCE_LINK", "a complete separate match/source review declaration is required")
    if binding["binding_version"] != REAL_BINDING_VERSION:
        _reject("UNSUPPORTED_BINDING_VERSION", "training source binding version is unsupported")
    if binding["analysis_method"] != "HUMAN_MANUAL":
        _reject("VISION_EVIDENCE_FORBIDDEN", "manual annotations cannot claim Vision analysis")
    if binding["match_link_status"] != "HUMAN_REVIEWED_DECLARATION":
        _reject("UNVERIFIED_MATCH_SOURCE_LINK", "match/source relation requires an explicit human review declaration")
    if binding["local_analysis_permission"] != "DECLARED_ALLOWED":
        _reject("LOCAL_ANALYSIS_PERMISSION_NOT_DECLARED", "local analysis permission must be explicitly declared")
    for field in ("dataset_id", "match_id", "source_id", "source_sha256"):
        expected = (bundle["dataset"]["source_binding"].get(field)
                    if field in {"source_id", "source_sha256"} else bundle["dataset"].get(field))
        if binding[field] != expected:
            _reject("MATCH_SOURCE_BINDING_MISMATCH", f"{field} differs from the hash-checked annotation import")
    for field in ("local_asset_id", "rights_basis_ref", "reviewer_ref"):
        if not isinstance(binding[field], str) or not binding[field].strip():
            _reject("UNVERIFIED_MATCH_SOURCE_LINK", f"{field} requires an explicit nonempty reference")
    try:
        reviewed_at = datetime.fromisoformat(binding["reviewed_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        _reject("UNVERIFIED_MATCH_SOURCE_LINK", "reviewed_at must be an ISO timestamp with timezone")
    if reviewed_at.tzinfo is None:
        _reject("UNVERIFIED_MATCH_SOURCE_LINK", "reviewed_at must contain a timezone")


def _require_video_stream_metadata(path: Path) -> None:
    """Check a selected file has video-stream metadata; this does not decode it."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        _reject("MEDIA_PROBE_UNAVAILABLE", "ffprobe is required before labeling a source file as video")
    try:
        process = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type,width,height", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=15, check=False,
        )
        payload = json.loads(process.stdout) if process.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        _reject("SOURCE_NOT_VIDEO", "selected source could not be probed for a video stream")
    streams = payload.get("streams", []) if isinstance(payload, dict) else []
    if not isinstance(streams, list) or not any(
        stream.get("codec_type") == "video"
        and type(stream.get("width")) is int and stream["width"] > 0
        and type(stream.get("height")) is int and stream["height"] > 0
        for stream in streams if isinstance(stream, dict)
    ):
        _reject("SOURCE_NOT_VIDEO", "selected source has no identifiable video stream")


def _metric(key: str, numerator: int | float | dict, denominator: int, sample_count: int,
            rule: str, evidence_status: str, *, extra: dict | None = None) -> dict:
    result = {
        "key": key, "numerator": numerator, "denominator": denominator,
        "sample_count": sample_count, "missing_count": sample_count - denominator,
        "value": round(numerator / denominator, 6) if isinstance(numerator, (int, float)) and denominator else None,
        "computation_rule": rule, "evidence_status": evidence_status,
        "sample_status": "NOT_ESTIMABLE" if not denominator else (
            "INSUFFICIENT_SAMPLE" if denominator < MIN_DISPLAY_SAMPLE else "DESCRIPTIVE_ONLY"
        ),
    }
    if extra:
        result.update(extra)
    return result


def _score_for_roles(row: dict) -> tuple[int, int] | None:
    if row["server"] not in {"player", "opponent"} or row["receiver"] not in {"player", "opponent"}:
        return None
    a, b = row["server_score_before"], row["receiver_score_before"]
    if type(a) is not int or type(b) is not int:
        return None
    return (a, b) if row["server"] == "player" else (b, a)


def build_training_report(bundle: dict, *, csv_sha256: str, generated_at: str,
                          binding: dict | None = None) -> dict:
    if not isinstance(csv_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", csv_sha256):
        _reject("INVALID_ANNOTATION_CSV_HASH", "csv_sha256 must be the lowercase SHA-256 of imported CSV bytes")
    try:
        parsed_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        _reject("INVALID_REPORT_TIME", "generated_at must be a timezone-qualified ISO timestamp")
    if parsed_time.tzinfo is None:
        _reject("INVALID_REPORT_TIME", "generated_at must include a timezone")
    base = analyze_bundle(bundle)
    dataset = bundle["dataset"]
    synthetic = dataset["dataset_class"] == "SIMULATED_ONLY"
    if synthetic and binding is not None:
        _reject("SIMULATED_REAL_BINDING_FORBIDDEN", "synthetic points cannot take a local video binding")
    if not synthetic and binding is None:
        _reject("UNVERIFIED_MATCH_SOURCE_LINK", "manual reports require the reviewed source declaration")
    if not synthetic:
        _validate_human_binding(bundle, binding)
    if csv_sha256 != dataset["provenance"].get("annotation_csv_sha256", csv_sha256) and not synthetic:
        _reject("ANNOTATION_CSV_HASH_MISMATCH", "report CSV hash differs from the imported human annotation")
    status = "SIMULATED_ONLY" if synthetic else "DECLARED_NOT_INDEPENDENTLY_AUDITED"
    points = bundle["points"]
    count = len(points)
    refs = base["point_refs"]
    known_server = [row for row in points if row["server"] in {"player", "opponent"} and row["point_winner"] in {"player", "opponent"}]
    known_receiver = [row for row in points if row["receiver"] in {"player", "opponent"} and row["point_winner"] in {"player", "opponent"}]
    classified_attacks = [row for row in points if row["third_ball_attack"] in {"yes", "no"}]
    attacked = [row for row in points if row["third_ball_attack"] == "yes"]
    known_attack_winner = [row for row in attacked if row["server"] in {"player", "opponent"} and row["point_winner"] in {"player", "opponent"}]
    known_immediate = [row for row in attacked if row["third_ball_outcome"] in {"successful", "unsuccessful"}]
    score_trace = []
    point_records = []
    key_points = []
    watchlist = []
    for record_number, (row, ref) in enumerate(zip(points, refs), 2):
        score = _score_for_roles(row)
        known_winner = row["point_winner"] in {"player", "opponent"}
        before = {"player": score[0], "opponent": score[1]} if score else None
        after = ({"player": score[0] + int(row["point_winner"] == "player"),
                  "opponent": score[1] + int(row["point_winner"] == "opponent")}
                 if score and known_winner else None)
        point_ref = {
            **ref, "csv_record_number": record_number,
            "annotation_row_sha256": _row_sha256(row),
            "video_timestamp_text": row["video_timestamp"],
            "timestamp_binding": "UNBOUND_PROTOCOL_TEXT",
        }
        score_trace.append({"point_id": ref["point_id"], "game_number": row["game_number"],
                            "score_before": before, "score_after": after, "winner": row["point_winner"]})
        point_records.append({"point_id": ref["point_id"], "csv_record_number": record_number,
                              "annotation_row_sha256": point_ref["annotation_row_sha256"],
                              "fields": copy.deepcopy(row)})
        if score and min(score) >= 7 and abs(score[0] - score[1]) <= 1:
            key_points.append({"point_id": ref["point_id"], "score_before": before,
                               "winner": row["point_winner"], "evidence_status": status})
            if row["point_winner"] == "opponent":
                watchlist.append({"point_id": ref["point_id"], "reason": "关键比分下该行记录为失分；请复看原始录像与标注。"})
        if row["third_ball_attack"] == "yes" and row["third_ball_outcome"] == "unsuccessful":
            watchlist.append({"point_id": ref["point_id"], "reason": "该行标注第三板进攻未成功；请复看动作与判定依据。"})
        ref.update(point_ref)
    metric = lambda key, num, denom, rule, extra=None, sample_count=count: _metric(
        key, num, denom, sample_count, rule, status, extra=extra
    )
    distributions = {}
    for field in ("serve_side", "serve_length", "serve_location", "serve_spin", "receive_type", "receive_location"):
        observed = [row[field] for row in points if row[field] not in {"unknown", "unclear", "not_applicable"}]
        categories = {value: observed.count(value) for value in sorted(set(observed))}
        not_applicable = sum(row[field] == "not_applicable" for row in points)
        distributions[field] = metric(field, categories, len(observed),
            f"各{field}类别次数 / 已判定的该字段行数；unknown与unclear记入missing_count，not_applicable单列。",
            {"unknown_count": sum(row[field] == "unknown" for row in points),
             "unclear_count": sum(row[field] == "unclear" for row in points),
             "not_applicable_count": not_applicable}, sample_count=count - not_applicable)
    key_known = [point for point in key_points if point["winner"] in {"player", "opponent"}]
    metrics = {
        "server_point_win_rate": metric("server_point_win_rate", sum(row["server"] == row["point_winner"] for row in known_server),
            len(known_server), "已知发球方赢分数 / 发球方与胜者均已知的逐分数。"),
        "receiver_point_win_rate": metric("receiver_point_win_rate", sum(row["receiver"] == row["point_winner"] for row in known_receiver),
            len(known_receiver), "已知接发球方赢分数 / 接发球方与胜者均已知的逐分数。"),
        "third_ball_attack_rate": metric("third_ball_attack_rate", len(attacked), len(classified_attacks),
            "third_ball_attack=yes / (yes+no)；未判定及不适用不加入分母。",
            {"not_applicable_count": sum(row["third_ball_attack"] == "not_applicable" for row in points)},
            sample_count=count - sum(row["third_ball_attack"] == "not_applicable" for row in points)),
        "third_ball_point_conversion": metric("third_ball_point_conversion",
            sum(row["server"] == row["point_winner"] for row in known_attack_winner), len(known_attack_winner),
            "确认第三板进攻后发球方赢分数 / 已知发球方及胜者的第三板进攻逐分数。", sample_count=len(attacked)),
        "third_ball_immediate_success": metric("third_ball_immediate_success",
            sum(row["third_ball_outcome"] == "successful" for row in known_immediate), len(known_immediate),
            "第三板即时successful数 / successful与unsuccessful数；不等同于本分获胜。", sample_count=len(attacked)),
        "key_point_player_win_rate": metric("key_point_player_win_rate",
            sum(point["winner"] == "player" for point in key_known), len(key_known),
            "双方分前比分均至少7且差距不超过1的已知胜者逐分中，player获胜数 / 已知胜者数。",
            {"key_point_candidates": len(key_points), "unresolved_score_or_identity": count - len(key_points)},
            sample_count=len(key_points)),
        "rally_length_mean": metric("rally_length_mean",
            sum(row["rally_length"] for row in points if type(row["rally_length"]) is int),
            sum(type(row["rally_length"]) is int for row in points),
            "已判定的击球次数总和 / 击球次数为正整数的逐分数；发球计为第一板。"),
    }
    serve_turns = []
    current_turn = None
    for row, ref in zip(points, refs):
        server = row["server"]
        if server == "unknown":
            current_turn = None
            continue
        if (current_turn is None or current_turn["server"] != server
                or current_turn["game_number"] != row["game_number"]):
            current_turn = {"game_number": row["game_number"], "server": server, "point_ids": [],
                            "winner_known_count": 0, "server_wins": 0}
            serve_turns.append(current_turn)
        current_turn["point_ids"].append(ref["point_id"])
        if row["point_winner"] in {"player", "opponent"}:
            current_turn["winner_known_count"] += 1
            current_turn["server_wins"] += int(server == row["point_winner"])
    for turn in serve_turns:
        turn["metric"] = _metric("serve_turn_win_rate", turn["server_wins"], turn["winner_known_count"],
            len(turn["point_ids"]), "本轮发球方赢分数 / 本轮胜者已知的逐分数。", status)
    game_summaries = []
    for game_number in sorted({row["game_number"] for row in points}):
        game_rows = [trace for trace in score_trace if trace["game_number"] == game_number]
        game_summaries.append({
            "game_number": game_number, "point_count": len(game_rows),
            "player_wins_recorded": sum(trace["winner"] == "player" for trace in game_rows),
            "opponent_wins_recorded": sum(trace["winner"] == "opponent" for trace in game_rows),
            "last_observed_score_after": game_rows[-1]["score_after"],
            "score_status": "DERIVED_FROM_KNOWN_ANNOTATIONS" if game_rows[-1]["score_after"] is not None else "UNKNOWN",
        })
    report = {
        "report_version": REVIEW_VERSION,
        "generated_at": generated_at,
        "dataset": {
            "dataset_id": dataset["dataset_id"], "dataset_class": dataset["dataset_class"],
            "match_id": dataset["match_id"], "source_id": None if synthetic else dataset["source_binding"]["source_id"],
            "local_asset_id": None if synthetic else binding["local_asset_id"],
            "annotation_csv_sha256": csv_sha256,
            "annotation_bundle_sha256": base["input_sha256"],
            "source_video_sha256": dataset["source_binding"]["source_sha256"],
            "protocol": copy.deepcopy(dataset["source_protocol"]),
            "annotation_provenance": copy.deepcopy(dataset["provenance"]),
            "match_link_status": "NOT_APPLICABLE_SIMULATED" if synthetic else "HUMAN_REVIEWED_DECLARATION_NOT_AUDITED",
            "local_analysis_permission": "NOT_APPLICABLE_SIMULATED" if synthetic else "DECLARED_ALLOWED_NOT_AUDITED",
            "rights_basis_ref": None if synthetic else binding["rights_basis_ref"],
            "video_timeline": {"status": "UNBOUND", "timeline_id": None, "pts": None, "time_base": None},
            "evidence_status": status, "vision_status": "NOT_TESTED",
            "event": None, "player_identity": None,
        },
        "sample": {"point_count": count, "game_count": len({row["game_number"] for row in points}),
                   "known_score_count": sum(_score_for_roles(row) is not None for row in points),
                   "known_winner_count": sum(row["point_winner"] in {"player", "opponent"} for row in points)},
        "metrics": metrics, "distributions": distributions,
        "serve_turns": serve_turns, "game_summaries": game_summaries,
        "score_trace": score_trace, "key_points": key_points,
        "watchlist": watchlist[:10], "point_refs": refs, "point_records": point_records,
        "limitations": [
            "人工标注仅做结构与来源文件字节校验；战术动作仍需教练复看录像。" if not synthetic else
            "全部逐分数据为原创模拟数据；不得对应真实比赛、运动员或视频。",
            "21字段协议的video_timestamp为自由文本，未验证PTS/time_base，报告不提供精确跳转。",
            "五分门槛仅为展示阈值，不是统计显著性或竞技规律证明。",
            "报告不含Vision识别结果，也未独立核验版权或比赛身份。",
        ],
    }
    report["summary_cn"] = render_chinese_summary(report)
    return report


def render_chinese_summary(report: dict) -> str:
    dataset = report["dataset"]
    metrics = report["metrics"]
    def value(key: str) -> str:
        metric = metrics[key]
        if metric["value"] is None:
            return "无法计算"
        suffix = "，样本不足" if metric["sample_status"] == "INSUFFICIENT_SAMPLE" else ""
        return f"{metric['numerator']}/{metric['denominator']}（{metric['value']:.1%}{suffix}）"
    lines = [
        "# PTTI 训练比赛战术复盘",
        f"数据集：{dataset['dataset_id']}；比赛ID：{dataset['match_id']}；证据：{dataset['evidence_status']}。",
        f"已录入{report['sample']['point_count']}分；发球方赢分率{value('server_point_win_rate')}，接发球方赢分率{value('receiver_point_win_rate')}。",
        f"第三板进攻率{value('third_ball_attack_rate')}，已标注第三板后的发球方赢分率{value('third_ball_point_conversion')}。",
        f"已知关键比分的player赢分率{value('key_point_player_win_rate')}；关键分数{len(report['key_points'])}。",
        "这些是逐分标注的描述性统计。建议按报告中的point_id复看关键比分及第三板未成功的记录；当前视频时间尚未绑定PTS。",
        "低样本与未知字段见JSON中各指标的sample_status、missing_count及limitations。",
    ]
    return "\n\n".join(lines) + "\n"
