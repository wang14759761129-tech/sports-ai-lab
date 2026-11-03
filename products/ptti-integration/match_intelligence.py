"""Evidence-aware descriptive analysis for the existing PTTI Protocol v0.3.

This sidecar deliberately stays separate from ptti.match-media/0.2. It reads
point annotations only; it does not read video, a database, or Vision output.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote


ANALYSIS_VERSION = "ptti.match-intelligence/0.1"
PROTOCOL_ID = "serve-third-ball-analytics"
PROTOCOL_VERSION = "0.3"
PROTOCOL_SCHEMA_REVISION = "1b30e8ea0f8a90a745fb6c30105599f0334fdf7c"
MANUAL_MANIFEST_VERSION = "ptti.manual-point-annotation/0.1"
MIN_DISPLAY_SAMPLE = 5  # Product display rule from PTTI DATA-FIELDS.md; not a research threshold.

POINT_FIELDS = (
    "match_id", "game_number", "point_number", "server", "receiver",
    "server_score_before", "receiver_score_before", "serve_side", "serve_length",
    "serve_location", "serve_spin", "receive_type", "receive_location",
    "third_ball_attack", "third_ball_side", "third_ball_outcome", "rally_length",
    "point_winner", "point_outcome", "video_timestamp", "notes",
)
IDENTITY_FIELDS = {"match_id", "game_number", "point_number"}
UNRESOLVED = {"unknown", "unclear"}
NOT_APPLICABLE = "not_applicable"
UNCERTAIN = UNRESOLVED | {NOT_APPLICABLE}
NUMERIC_FIELDS = {"game_number", "point_number", "server_score_before", "receiver_score_before", "rally_length"}
CATEGORIES = {
    "server": {"player", "opponent", "unknown"},
    "receiver": {"player", "opponent", "unknown"},
    "point_winner": {"player", "opponent", "unknown"},
    "point_outcome": {"win", "loss", "unknown"},
    "serve_side": {"forehand", "backhand", "unknown", "unclear", "not_applicable"},
    "serve_length": {"short", "half_long", "long", "unknown", "unclear", "not_applicable"},
    "serve_location": {"forehand", "middle", "backhand", "unknown", "unclear", "not_applicable"},
    "serve_spin": {"backspin", "sidespin", "topspin", "no_spin", "mixed", "unknown", "unclear", "not_applicable"},
    "receive_type": {"push", "flick", "chiquita", "drive", "loop", "long_push", "short_touch", "other", "unknown", "unclear", "not_applicable"},
    "receive_location": {"forehand", "middle", "backhand", "unknown", "unclear", "not_applicable"},
    "third_ball_attack": {"yes", "no", "unknown", "unclear", "not_applicable"},
    "third_ball_side": {"forehand", "backhand", "other", "unknown", "unclear", "not_applicable"},
    "third_ball_outcome": {"successful", "unsuccessful", "unknown", "unclear", "not_applicable"},
}
EDITABLE_ANNOTATIONS = (set(CATEGORIES) - {"server", "receiver", "point_winner", "point_outcome"}) | {
    "rally_length", "video_timestamp", "notes",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AnalysisValidationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _error(code: str, detail: str) -> None:
    raise AnalysisValidationError(code, detail)


def _number(value, field: str, minimum: int) -> int | None:
    if isinstance(value, bool):
        _error("INVALID_NUMBER", f"{field} must be an integer or an explicit uncertainty value")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value in UNCERTAIN:
        return None
    elif isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        result = int(value)
    else:
        _error("INVALID_NUMBER", f"{field} must be an integer or one of {sorted(UNCERTAIN)}")
    if result < minimum:
        _error("INVALID_NUMBER", f"{field} must be >= {minimum}")
    return result


def _counter_summary(values: list[str], *, eligible_count: int | None = None) -> dict:
    counts = Counter(values)
    n_rows = len(values)
    na = counts[NOT_APPLICABLE]
    unknown = counts["unknown"]
    unclear = counts["unclear"]
    observed = n_rows - na - unknown - unclear
    eligible = n_rows - na if eligible_count is None else eligible_count
    unresolved = unknown + unclear
    categories = {key: counts[key] for key in sorted(counts) if key not in UNCERTAIN}
    shares = {key: round(count / observed, 6) for key, count in categories.items()} if observed else {}
    status = "NOT_ESTIMABLE" if observed == 0 else (
        "DESCRIPTIVE_ONLY" if observed >= MIN_DISPLAY_SAMPLE else "INSUFFICIENT_SAMPLE"
    )
    return {
        "row_count": n_rows,
        "eligible_denominator": eligible,
        "observed_denominator": observed,
        "counts": categories,
        "shares_of_observed": shares,
        "unknown_count": unknown,
        "unclear_count": unclear,
        "not_applicable_count": na,
        "uncertainty_rate": round(unresolved / eligible, 6) if eligible else None,
        "status": status,
    }


def _rate(numerator: int, denominator: int) -> dict:
    status = "NOT_ESTIMABLE" if denominator == 0 else (
        "DESCRIPTIVE_ONLY" if denominator >= MIN_DISPLAY_SAMPLE else "INSUFFICIENT_SAMPLE"
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": round(numerator / denominator, 6) if denominator else None,
        "status": status,
    }


def _point_id(match_id: str, game_number: int, point_number: int) -> str:
    return f"{quote(match_id, safe='')}/g{game_number:02d}/p{point_number:03d}"


def _canonical_bundle_sha256(bundle: dict) -> str:
    encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _simulated_edit_dataset_id(parent_sha256: str, field: str, game_number: int, point_number: int, after: str | int) -> str:
    edit_identity = json.dumps(
        {"field": field, "game_number": game_number, "point_number": point_number, "after": after},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    digest = hashlib.sha256((parent_sha256 + edit_identity).encode("utf-8")).hexdigest()[:24]
    return f"SIMULATED_ONLY:edit-{digest}"


def _validate_dataset(dataset: dict) -> None:
    if not isinstance(dataset, dict):
        _error("INVALID_DATASET", "dataset must be an object")
    required = {"dataset_id", "dataset_class", "match_id", "source_protocol", "provenance", "source_binding"}
    if set(dataset) != required:
        _error("INVALID_DATASET_FIELDS", f"dataset fields must be exactly {sorted(required)}")
    for field in ("dataset_id", "match_id"):
        if not isinstance(dataset[field], str) or not dataset[field].strip():
            _error("MISSING_DATASET_IDENTITY", f"{field} must be a non-empty string")
    protocol = dataset["source_protocol"]
    expected_protocol = {"id": PROTOCOL_ID, "version": PROTOCOL_VERSION, "schema_revision": PROTOCOL_SCHEMA_REVISION}
    if protocol != expected_protocol:
        _error("UNSUPPORTED_SOURCE_PROTOCOL", f"expected exact Protocol v0.3 binding {expected_protocol}")
    provenance = dataset["provenance"]
    binding = dataset["source_binding"]
    if not isinstance(provenance, dict) or not isinstance(binding, dict):
        _error("INVALID_PROVENANCE", "provenance and source_binding must be objects")
    dataset_class = dataset["dataset_class"]
    if dataset_class == "SIMULATED_ONLY":
        if not dataset["match_id"].startswith("SIMULATED_ONLY:"):
            _error("SYNTHETIC_ID_NAMESPACE_REQUIRED", "SIMULATED_ONLY rows require a SIMULATED_ONLY: match_id")
        if provenance.get("method") == "DETERMINISTIC_ORIGINAL_GENERATOR":
            if set(provenance) != {"method", "seed", "generated_on"}:
                _error("INVALID_SIMULATION_PROVENANCE", "simulation must identify its deterministic generator, seed, and date")
            if type(provenance.get("seed")) is not int or not isinstance(provenance.get("generated_on"), str):
                _error("INVALID_SIMULATION_PROVENANCE", "simulation seed/date is invalid")
            try:
                date.fromisoformat(provenance["generated_on"])
            except ValueError:
                _error("INVALID_SIMULATION_PROVENANCE", "generated_on must be an ISO date")
        elif provenance.get("method") == "SIMULATED_INTERACTIVE_EDIT":
            required_provenance = {"method", "parent_dataset_id", "parent_input_sha256", "edit"}
            if set(provenance) != required_provenance:
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "interactive edits require exact parent and edit fields")
            if not isinstance(provenance["parent_dataset_id"], str) or not provenance["parent_dataset_id"].startswith("SIMULATED_ONLY:"):
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "parent_dataset_id must stay in the synthetic namespace")
            if not SHA256_RE.fullmatch(str(provenance["parent_input_sha256"])):
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "parent_input_sha256 must be lowercase SHA-256")
            edit = provenance["edit"]
            if not isinstance(edit, dict) or set(edit) != {"point_id", "field", "before", "after"}:
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit must include point_id, field, before, and after")
            if edit["field"] not in EDITABLE_ANNOTATIONS:
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit field is not an editable annotation")
            for version_name in ("before", "after"):
                edit_value = edit[version_name]
                field_name = edit["field"]
                if field_name in CATEGORIES and (not isinstance(edit_value, str) or edit_value not in CATEGORIES[field_name]):
                    _error("INVALID_SIMULATION_EDIT_PROVENANCE", f"{version_name} is invalid for categorical field {field_name}")
                if field_name == "rally_length":
                    try:
                        _number(edit_value, "rally_length", 1)
                    except AnalysisValidationError:
                        _error("INVALID_SIMULATION_EDIT_PROVENANCE", f"{version_name} is invalid for rally_length")
                if field_name in {"video_timestamp", "notes"} and not isinstance(edit_value, str):
                    _error("INVALID_SIMULATION_EDIT_PROVENANCE", f"{version_name} must be text for {field_name}")
            try:
                game, point = int(edit["point_id"].rsplit("/g", 1)[1].split("/p", 1)[0]), int(edit["point_id"].rsplit("/p", 1)[1])
            except (AttributeError, IndexError, ValueError):
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit point_id is malformed")
            if edit["point_id"] != _point_id(dataset["match_id"], game, point):
                _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit point_id must refer to this synthetic match")
        else:
            _error("INVALID_SIMULATION_PROVENANCE", "unsupported synthetic provenance method")
        expected_binding = {
            "status": "NOT_APPLICABLE_SIMULATED", "source_id": None,
            "source_sha256": None, "timeline_id": None, "time_base": None,
        }
        if binding != expected_binding:
            _error("SIMULATION_SOURCE_BINDING_FORBIDDEN", "synthetic points cannot bind to a real source or timeline")
    elif dataset_class == "HUMAN_ANNOTATION":
        if dataset["match_id"].startswith("SIMULATED_ONLY:"):
            _error("SIMULATION_CANNOT_BE_HUMAN", "synthetic IDs cannot be labeled as human-annotated matches")
        expected_provenance = {"method", "annotator_ref", "annotated_at", "evidence_ref", "annotation_csv_sha256", "review_status"}
        if set(provenance) != expected_provenance or provenance.get("method") != "HUMAN_MANUAL":
            _error("INVALID_MANUAL_PROVENANCE", "human annotation provenance fields are incomplete or unsupported")
        if provenance.get("review_status") != "DECLARED_NOT_INDEPENDENTLY_AUDITED":
            _error("MANUAL_EVIDENCE_STATUS_INVALID", "manual declaration cannot claim independent audit")
        for field in ("annotator_ref", "evidence_ref"):
            if not isinstance(provenance.get(field), str) or not provenance[field].strip():
                _error("INVALID_MANUAL_PROVENANCE", f"{field} must be a non-empty opaque reference")
        _parse_iso_datetime(provenance.get("annotated_at"), "annotated_at")
        if not SHA256_RE.fullmatch(str(provenance.get("annotation_csv_sha256", ""))):
            _error("INVALID_MANUAL_PROVENANCE", "annotation_csv_sha256 must be lowercase SHA-256")
        expected_binding = {"status": "SOURCE_BYTES_HASH_MATCHED_AT_IMPORT", "source_id": binding.get("source_id"),
                            "source_sha256": binding.get("source_sha256"), "timeline_id": None,
                            "time_base": None, "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND"}
        if binding != expected_binding or not isinstance(binding.get("source_id"), str) or not binding["source_id"].strip():
            _error("INVALID_MANUAL_SOURCE_BINDING", "manual imports require a hash-checked source ID; v0.3 timestamps stay text-only")
        if not SHA256_RE.fullmatch(str(binding.get("source_sha256", ""))):
            _error("INVALID_MANUAL_SOURCE_BINDING", "source_sha256 must be lowercase SHA-256")
    else:
        _error("UNSUPPORTED_DATASET_CLASS", "accepted dataset_class values are SIMULATED_ONLY and HUMAN_ANNOTATION")


def _parse_iso_datetime(value, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _error("INVALID_MANUAL_PROVENANCE", f"{field} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _error("INVALID_MANUAL_PROVENANCE", f"{field} must be a valid ISO-8601 timestamp")
    if parsed.tzinfo is None:
        _error("INVALID_MANUAL_PROVENANCE", f"{field} must include a timezone")
    return parsed


def validate_bundle(bundle: dict) -> list[dict]:
    if not isinstance(bundle, dict) or set(bundle) != {"contract_version", "dataset", "points"}:
        _error("INVALID_BUNDLE_FIELDS", "bundle must contain only contract_version, dataset, points")
    if bundle.get("contract_version") != ANALYSIS_VERSION:
        _error("UNSUPPORTED_ANALYSIS_VERSION", f"expected exact {ANALYSIS_VERSION}")
    dataset = bundle.get("dataset")
    _validate_dataset(dataset)
    points = bundle.get("points")
    if not isinstance(points, list) or not points:
        _error("EMPTY_POINT_SET", "points must be a non-empty array")
    match_id = bundle["dataset"]["match_id"]
    seen = set()
    groups: dict[int, list[dict]] = defaultdict(list)
    for index, row in enumerate(points, 1):
        if not isinstance(row, dict) or set(row) != set(POINT_FIELDS):
            missing = sorted(set(POINT_FIELDS) - set(row if isinstance(row, dict) else {}))
            extra = sorted(set(row if isinstance(row, dict) else {}) - set(POINT_FIELDS))
            _error("INVALID_POINT_FIELDS", f"row {index}: missing={missing}, extra={extra}")
        if row["match_id"] != match_id:
            _error("MATCH_ASSOCIATION_MISMATCH", f"row {index} match_id differs from dataset; name-based reassociation is forbidden")
        if not isinstance(row["match_id"], str) or not row["match_id"].strip():
            _error("MISSING_MATCH_ID", f"row {index} has no match_id")
        game = _number(row["game_number"], "game_number", 1)
        point = _number(row["point_number"], "point_number", 1)
        if game is None or point is None:
            _error("UNKNOWN_POINT_IDENTITY", f"row {index} must have known game_number and point_number")
        key = (row["match_id"], game, point)
        if key in seen:
            _error("DUPLICATE_POINT_ID", f"duplicate natural point ID {key}")
        seen.add(key)
        for field in ("server_score_before", "receiver_score_before"):
            _number(row[field], field, 0)
        _number(row["rally_length"], "rally_length", 1)
        for field, allowed in CATEGORIES.items():
            value = row[field]
            if not isinstance(value, str) or value not in allowed:
                _error("INVALID_CATEGORY", f"row {index} field {field} has unsupported value {value!r}")
        for field in ("video_timestamp", "notes"):
            if not isinstance(row[field], str):
                _error("INVALID_TEXT_FIELD", f"row {index} field {field} must be text")
        if not row["notes"].strip():
            _error("MISSING_ANNOTATION_NOTE", f"row {index} notes must contain text or an explicit uncertainty note")
        if row["server"] in {"player", "opponent"} and row["receiver"] in {"player", "opponent"} and row["server"] == row["receiver"]:
            _error("SERVER_RECEIVER_CONFLICT", f"row {index} server and receiver must be opposite sides")
        expected_outcome = {"player": "win", "opponent": "loss"}.get(row["point_winner"])
        if expected_outcome and row["point_outcome"] not in {expected_outcome, "unknown"}:
            _error("POINT_OUTCOME_CONFLICT", f"row {index} point_outcome conflicts with point_winner")
        if row["third_ball_attack"] in {"no", NOT_APPLICABLE}:
            for field in ("third_ball_side", "third_ball_outcome"):
                if row[field] != NOT_APPLICABLE:
                    _error("THIRD_BALL_ELIGIBILITY_CONFLICT", f"row {index} {field} must be not_applicable when no attack applies")
        if row["third_ball_attack"] == "yes":
            for field in ("third_ball_side", "third_ball_outcome"):
                if row[field] == NOT_APPLICABLE:
                    _error("THIRD_BALL_ELIGIBILITY_CONFLICT", f"row {index} {field} cannot be not_applicable for a confirmed attack")
        groups[game].append(row)

    if dataset["dataset_class"] == "SIMULATED_ONLY" and dataset["provenance"].get("method") == "SIMULATED_INTERACTIVE_EDIT":
        edit = dataset["provenance"]["edit"]
        try:
            game, point = int(edit["point_id"].rsplit("/g", 1)[1].split("/p", 1)[0]), int(edit["point_id"].rsplit("/p", 1)[1])
        except (AttributeError, IndexError, ValueError):
            _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit point_id is malformed")
        target = next((row for row in points if int(row["game_number"]) == game and int(row["point_number"]) == point), None)
        if target is None or target[edit["field"]] != edit["after"] or edit["before"] == edit["after"]:
            _error("INVALID_SIMULATION_EDIT_PROVENANCE", "edit must identify an existing changed value in this bundle")
        expected_id = _simulated_edit_dataset_id(
            dataset["provenance"]["parent_input_sha256"], edit["field"], game, point, edit["after"]
        )
        if dataset["dataset_id"] != expected_id or dataset["dataset_id"] == dataset["provenance"]["parent_dataset_id"]:
            _error("INVALID_SIMULATION_EDIT_PROVENANCE", "derived dataset_id does not match its edit lineage")

    if sorted(groups) != list(range(1, max(groups) + 1)):
        _error("GAME_SEQUENCE_INVALID", "game_number must begin at 1 and advance without gaps")
    if list(groups) != sorted(groups):
        _error("GAME_ORDER_INVALID", "rows must be ordered by game_number")
    for game_number, game_rows in groups.items():
        numbers = [_number(row["point_number"], "point_number", 1) for row in game_rows]
        if numbers != list(range(1, len(numbers) + 1)):
            _error("POINT_SEQUENCE_INVALID", f"game {game_number} points must be contiguous and input-ordered from 1")
        _validate_service_order(game_rows, game_number)
        _validate_score_progression(game_rows, game_number)
    return points


def _validate_service_order(rows: list[dict], game_number: int) -> None:
    first_server = rows[0]["server"]
    if first_server not in {"player", "opponent"}:
        return  # Protocol permits UNKNOWN; do not infer the opening server.
    other = "opponent" if first_server == "player" else "player"
    for index, row in enumerate(rows):
        server = row["server"]
        if server == "unknown":
            continue
        completed = index
        switches = (completed // 2) % 2 if completed < 20 else (completed - 10) % 2
        expected = other if switches else first_server
        if server != expected:
            _error("SERVICE_ORDER_INVALID", f"game {game_number} point {index + 1}: expected {expected} under the two-point/deuce service rule")


def _validate_score_progression(rows: list[dict], game_number: int) -> None:
    for index, (previous, current) in enumerate(zip(rows, rows[1:]), 1):
        ps = previous["server"]
        pr = previous["receiver"]
        winner = previous["point_winner"]
        try:
            prev_server_score = _number(previous["server_score_before"], "server_score_before", 0)
            prev_receiver_score = _number(previous["receiver_score_before"], "receiver_score_before", 0)
            cur_server_score = _number(current["server_score_before"], "server_score_before", 0)
            cur_receiver_score = _number(current["receiver_score_before"], "receiver_score_before", 0)
        except AnalysisValidationError:
            raise
        if None in {prev_server_score, prev_receiver_score, cur_server_score, cur_receiver_score}:
            continue
        if {ps, pr} != {"player", "opponent"} or winner not in {"player", "opponent"}:
            continue
        if {current["server"], current["receiver"]} != {"player", "opponent"}:
            continue
        previous_scores = {ps: prev_server_score, pr: prev_receiver_score}
        previous_scores[winner] += 1
        if {current["server"]: cur_server_score, current["receiver"]: cur_receiver_score} != previous_scores:
            _error("SCORE_PROGRESSION_INVALID", f"game {game_number} points {index}->{index + 1} do not reconcile")


def _known(value: str) -> bool:
    return value not in UNCERTAIN


def _descriptive_status(denominator: int) -> str:
    if denominator == 0:
        return "NOT_ESTIMABLE"
    return "DESCRIPTIVE_ONLY" if denominator >= MIN_DISPLAY_SAMPLE else "INSUFFICIENT_SAMPLE"


def analyze_bundle(bundle: dict) -> dict:
    points = validate_bundle(bundle)
    input_sha256 = _canonical_bundle_sha256(bundle)
    dataset = bundle["dataset"]
    all_fields = (
        "serve_side", "serve_length", "serve_location", "serve_spin",
        "receive_type", "receive_location",
    )
    serve_distributions = {field: _counter_summary([row[field] for row in points]) for field in all_fields}

    winners = [row["point_winner"] for row in points if _known(row["point_winner"])]
    point_wins = {side: winners.count(side) for side in ("player", "opponent")}
    point_denominator = len(winners)
    point_win_rates = {side: _rate(count, point_denominator) for side, count in point_wins.items()}

    server_rows = [row for row in points if row["server"] in {"player", "opponent"} and row["point_winner"] in {"player", "opponent"}]
    server_wins = sum(row["server"] == row["point_winner"] for row in server_rows)
    server_point_win_rate = _rate(server_wins, len(server_rows))
    server_point_win_rate["excluded_rows"] = len(points) - len(server_rows)

    attacks_classified = [row for row in points if row["third_ball_attack"] in {"yes", "no"}]
    attacks = [row for row in points if row["third_ball_attack"] == "yes"]
    attack_rate = _rate(len(attacks), len(attacks_classified))
    attack_rate.update({
        "unresolved_eligibility": sum(row["third_ball_attack"] in UNRESOLVED for row in points),
        "not_applicable": sum(row["third_ball_attack"] == NOT_APPLICABLE for row in points),
        "unknown": sum(row["third_ball_attack"] == "unknown" for row in points),
        "unclear": sum(row["third_ball_attack"] == "unclear" for row in points),
    })
    attack_side_stats = _counter_summary([row["third_ball_side"] for row in attacks], eligible_count=len(attacks))
    attack_outcome_stats = _counter_summary([row["third_ball_outcome"] for row in attacks], eligible_count=len(attacks))

    conversion_rows = [row for row in attacks if row["server"] in {"player", "opponent"} and row["point_winner"] in {"player", "opponent"}]
    server_point_wins_after_attack = sum(row["server"] == row["point_winner"] for row in conversion_rows)
    third_ball_conversion = _rate(server_point_wins_after_attack, len(conversion_rows))
    third_ball_conversion["excluded_confirmed_attack_rows"] = len(attacks) - len(conversion_rows)

    immediate_outcomes = [row["third_ball_outcome"] for row in attacks if row["third_ball_outcome"] in {"successful", "unsuccessful"}]
    immediate_successes = immediate_outcomes.count("successful")
    immediate_outcome_rate = _rate(immediate_successes, len(immediate_outcomes))
    immediate_outcome_rate["unknown"] = sum(row["third_ball_outcome"] == "unknown" for row in attacks)
    immediate_outcome_rate["unclear"] = sum(row["third_ball_outcome"] == "unclear" for row in attacks)

    rally_values = [_number(row["rally_length"], "rally_length", 1) for row in points]
    numeric_rallies = [value for value in rally_values if value is not None]
    rally_summary = {
        "numerator_sum": sum(numeric_rallies),
        "denominator": len(numeric_rallies),
        "mean": round(sum(numeric_rallies) / len(numeric_rallies), 6) if numeric_rallies else None,
        "unknown_count": sum(row["rally_length"] == "unknown" for row in points),
        "unclear_count": sum(row["rally_length"] == "unclear" for row in points),
        "not_applicable_count": sum(row["rally_length"] == NOT_APPLICABLE for row in points),
        "status": _descriptive_status(len(numeric_rallies)),
    }

    by_game = {}
    for row in points:
        game = str(row["game_number"])
        by_game[game] = by_game.get(game, 0) + 1
    provenance = copy.deepcopy(dataset["provenance"])
    return {
        "analysis_version": ANALYSIS_VERSION,
        "input_sha256": input_sha256,
        "source_protocol": copy.deepcopy(dataset["source_protocol"]),
        "dataset": {
            "dataset_id": dataset["dataset_id"],
            "dataset_class": dataset["dataset_class"],
            "match_id": dataset["match_id"],
            "source_binding": copy.deepcopy(dataset["source_binding"]),
            "provenance": provenance,
            "human_review_status": provenance.get("review_status", "SIMULATED_ONLY"),
        },
        "summary": {
            "point_count": len(points),
            "by_game": by_game,
            "point_wins": {"counts": point_wins, "denominator": point_denominator, "rates": point_win_rates,
                           "status": _descriptive_status(point_denominator)},
            "server_point_win_rate": server_point_win_rate,
            "serve_distributions": serve_distributions,
            "third_ball_attack_rate": attack_rate,
            "third_ball_attack_side": attack_side_stats,
            "third_ball_immediate_outcome": {
                "definition": "third_ball_outcome successful / (successful + unsuccessful), among third_ball_attack=yes",
                "rate": immediate_outcome_rate,
                "distribution": attack_outcome_stats,
            },
            "third_ball_point_conversion": {
                "definition": "server won the point / confirmed third_ball_attack=yes with known server and point_winner",
                **third_ball_conversion,
            },
            "rally_length": rally_summary,
            "display_sample_threshold": {
                "n": MIN_DISPLAY_SAMPLE,
                "meaning": "product display rule only; not a research reliability threshold",
            },
        },
        "limitations": [
            "Descriptive summaries only; no confidence intervals, significance tests, causal claims, or machine learning.",
            "Third-ball immediate outcome is not point winner; point conversion is computed separately from server and point_winner.",
            "Protocol v0.3 video_timestamp is preserved as free text; no PTS, time_base, or source timeline mapping is inferred.",
            "SIMULATED_ONLY data is isolated from real match, athlete, VideoSource, and ptti.match-media records.",
        ],
        "point_refs": [
            {"point_id": _point_id(row["match_id"], int(row["game_number"]), int(row["point_number"])),
             "game_number": int(row["game_number"]), "point_number": int(row["point_number"])}
            for row in points
        ],
    }


def change_point_annotation(bundle: dict, *, game_number: int, point_number: int, field: str, value: str | int) -> dict:
    if field not in EDITABLE_ANNOTATIONS:
        _error("FIELD_NOT_EDITABLE", f"{field} is not an editable tactical annotation")
    validate_bundle(bundle)
    dataset = bundle["dataset"]
    if dataset["dataset_class"] != "SIMULATED_ONLY":
        _error("MANUAL_ANNOTATIONS_REQUIRE_REIMPORT", "re-import the edited CSV so its declared annotation hash remains accurate")
    updated = copy.deepcopy(bundle)
    matches = [row for row in updated.get("points", [])
               if str(row.get("game_number")) == str(game_number) and str(row.get("point_number")) == str(point_number)]
    if len(matches) != 1:
        _error("POINT_NOT_FOUND", f"expected exactly one row for game {game_number}, point {point_number}")
    before_value = matches[0][field]
    if field == "rally_length":
        parsed = _number(value, field, 1)
        value = parsed if parsed is not None else value
    elif field in CATEGORIES and (not isinstance(value, str) or value not in CATEGORIES[field]):
        _error("INVALID_CATEGORY", f"field {field} has unsupported value {value!r}")
    elif field in {"video_timestamp", "notes"} and not isinstance(value, str):
        _error("INVALID_TEXT_FIELD", f"field {field} must be text")
    matches[0][field] = value
    parent_sha256 = _canonical_bundle_sha256(bundle)
    parent_dataset_id = dataset["dataset_id"]
    updated["dataset"]["dataset_id"] = _simulated_edit_dataset_id(parent_sha256, field, game_number, point_number, value)
    updated["dataset"]["provenance"] = {
        "method": "SIMULATED_INTERACTIVE_EDIT",
        "parent_dataset_id": parent_dataset_id,
        "parent_input_sha256": parent_sha256,
        "edit": {
            "point_id": _point_id(dataset["match_id"], game_number, point_number),
            "field": field,
            "before": before_value,
            "after": value,
        },
    }
    validate_bundle(updated)
    return updated


def build_synthetic_demo() -> dict:
    """Return 24 deterministic points in an isolated synthetic namespace."""
    seed = 20261013
    match_id = "SIMULATED_ONLY:goal07-match-001"
    dataset = {
        "dataset_id": "SIMULATED_ONLY:goal07-dataset-v1",
        "dataset_class": "SIMULATED_ONLY",
        "match_id": match_id,
        "source_protocol": {"id": PROTOCOL_ID, "version": PROTOCOL_VERSION, "schema_revision": PROTOCOL_SCHEMA_REVISION},
        "provenance": {"method": "DETERMINISTIC_ORIGINAL_GENERATOR", "seed": seed, "generated_on": "2026-10-13"},
        "source_binding": {"status": "NOT_APPLICABLE_SIMULATED", "source_id": None, "source_sha256": None,
                           "timeline_id": None, "time_base": None},
    }
    winners = ["player", "opponent"] * 10 + ["player", "opponent", "player", "player"]
    rows = []
    score = {"player": 0, "opponent": 0}
    for point_number, winner in enumerate(winners, 1):
        completed = point_number - 1
        switches = (completed // 2) % 2 if completed < 20 else (completed - 10) % 2
        server = "opponent" if switches else "player"
        receiver = "player" if server == "opponent" else "opponent"
        server_score_before = score[server]
        receiver_score_before = score[receiver]
        attack_pattern = point_number % 4
        if attack_pattern in {1, 3}:
            third_attack = "yes"
            third_side = "forehand" if point_number % 8 == 1 else "backhand"
            third_outcome = "successful" if point_number % 8 == 1 else "unsuccessful"
        elif attack_pattern == 2:
            third_attack, third_side, third_outcome = "no", NOT_APPLICABLE, NOT_APPLICABLE
        elif point_number == 4:
            third_attack, third_side, third_outcome = "unclear", "unknown", "unknown"
        elif point_number == 8:
            third_attack, third_side, third_outcome = "unknown", "unknown", "unknown"
        else:
            third_attack, third_side, third_outcome = NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE
        rally_length = 5 if point_number == 1 else (
            "unknown" if point_number in {4, 18} else 3 + ((point_number * 3 + seed) % 8)
        )
        rows.append({
            "match_id": match_id,
            "game_number": 1,
            "point_number": point_number,
            "server": server,
            "receiver": receiver,
            "server_score_before": server_score_before,
            "receiver_score_before": receiver_score_before,
            "serve_side": ("forehand", "backhand", "unknown", "unclear")[(point_number + seed) % 4],
            "serve_length": ("short", "long", "half_long", "unknown", "unclear", "not_applicable")[(point_number + seed) % 6],
            "serve_location": ("forehand", "middle", "backhand", "unknown", "unclear", "not_applicable")[(point_number + seed) % 6],
            "serve_spin": ("backspin", "topspin", "sidespin", "no_spin", "mixed", "unknown")[(point_number + seed) % 6],
            "receive_type": ("push", "flick", "drive", "unknown", "unclear", "not_applicable")[(point_number + seed) % 6],
            "receive_location": ("forehand", "middle", "backhand", "unknown", "unclear", "not_applicable")[(point_number + seed) % 6],
            "third_ball_attack": third_attack,
            "third_ball_side": third_side,
            "third_ball_outcome": third_outcome,
            "rally_length": rally_length,
            "point_winner": winner,
            "point_outcome": "win" if winner == "player" else "loss",
            "video_timestamp": "unknown",
            "notes": "SIMULATED_ONLY; deterministic generated row; no video or athlete evidence.",
        })
        score[winner] += 1
    bundle = {"contract_version": ANALYSIS_VERSION, "dataset": dataset, "points": rows}
    validate_bundle(bundle)
    return bundle


def serialize_protocol_csv(bundle: dict) -> bytes:
    points = validate_bundle(bundle)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=POINT_FIELDS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in points:
        writer.writerow({field: row[field] for field in POINT_FIELDS})
    return stream.getvalue().encode("utf-8")


def parse_protocol_v03_csv(csv_bytes: bytes) -> list[dict]:
    """Parse a strict 21-column Protocol v0.3 CSV without assigning provenance."""
    if not isinstance(csv_bytes, (bytes, bytearray)):
        _error("INVALID_CSV_BYTES", "CSV input must be bytes")
    try:
        text = bytes(csv_bytes).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or set(headers) != set(POINT_FIELDS) or len(headers) != len(POINT_FIELDS):
            _error("PROTOCOL_FIELDS_MISMATCH", "CSV must contain the exact 21 Protocol v0.3 fields once each")
        raw_rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        _error("INVALID_CSV", f"CSV must be valid UTF-8 with consistent rows ({type(exc).__name__})")
    rows = []
    for index, raw in enumerate(raw_rows, 2):
        if None in raw or any(value is None for value in raw.values()):
            _error("CSV_ROW_WIDTH_MISMATCH", f"CSV row {index} does not match the header width")
        if any(value == "" for value in raw.values()):
            _error("BLANK_FIELD_REQUIRES_EXPLICIT_UNCERTAINTY", f"CSV row {index} contains a blank; use unknown/unclear/not_applicable or an explicit note")
        row = dict(raw)
        for field in NUMERIC_FIELDS:
            if row[field] not in UNCERTAIN:
                if not re.fullmatch(r"0|[1-9][0-9]*", row[field]):
                    _error("INVALID_NUMBER", f"CSV row {index} {field} must be an integer")
                row[field] = int(row[field])
        if row["game_number"] == "unknown" or row["point_number"] == "unknown":
            _error("UNKNOWN_POINT_IDENTITY", f"CSV row {index} must identify game and point")
        rows.append(row)
    return rows


def import_manual_csv(csv_bytes: bytes, manifest: dict, source_file: str | Path) -> dict:
    """Import exact v0.3 rows after checking the selected source file's SHA-256.

    The imported status proves structural validity and byte identity only; it
    does not independently verify the annotator's visual judgments.
    """
    if not isinstance(manifest, dict) or set(manifest) != {
        "manifest_version", "dataset_id", "match_id", "source_id", "source_sha256",
        "annotator_ref", "annotated_at", "evidence_ref", "timestamp_semantics",
    }:
        _error("INVALID_MANUAL_MANIFEST", "manifest fields do not exactly match ptti.manual-point-annotation/0.1")
    if manifest.get("manifest_version") != MANUAL_MANIFEST_VERSION:
        _error("UNSUPPORTED_MANUAL_MANIFEST", f"expected exact {MANUAL_MANIFEST_VERSION}")
    if manifest.get("timestamp_semantics") != "PROTOCOL_TEXT_ONLY_UNBOUND":
        _error("PTS_BINDING_UNSUPPORTED_BY_PROTOCOL", "v0.3 video_timestamp is free text; PTS/time_base binding belongs in a separate evidence package")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"].strip():
        _error("INVALID_MANUAL_MANIFEST", "dataset_id is required")
    if not isinstance(manifest.get("match_id"), str) or not manifest["match_id"].strip() or manifest["match_id"].startswith("SIMULATED_ONLY:"):
        _error("INVALID_MANUAL_MANIFEST", "manual match_id must be explicit and outside SIMULATED_ONLY namespace")
    for field in ("source_id", "annotator_ref", "evidence_ref"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            _error("INVALID_MANUAL_MANIFEST", f"{field} is required")
    _parse_iso_datetime(manifest.get("annotated_at"), "annotated_at")
    declared_sha = manifest.get("source_sha256")
    if not isinstance(declared_sha, str) or not SHA256_RE.fullmatch(declared_sha):
        _error("INVALID_MANUAL_MANIFEST", "source_sha256 must be lowercase SHA-256")
    path = Path(source_file)
    if not path.is_file():
        _error("SOURCE_FILE_NOT_FOUND", "the explicitly selected source file does not exist")
    actual_sha, _size = _sha256_file(path)
    if actual_sha != declared_sha:
        _error("SOURCE_HASH_MISMATCH", "selected source file does not match the manifest SHA-256")
    rows = parse_protocol_v03_csv(bytes(csv_bytes))
    csv_sha = hashlib.sha256(bytes(csv_bytes)).hexdigest()
    bundle = {
        "contract_version": ANALYSIS_VERSION,
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "dataset_class": "HUMAN_ANNOTATION",
            "match_id": manifest["match_id"],
            "source_protocol": {"id": PROTOCOL_ID, "version": PROTOCOL_VERSION, "schema_revision": PROTOCOL_SCHEMA_REVISION},
            "provenance": {
                "method": "HUMAN_MANUAL", "annotator_ref": manifest["annotator_ref"],
                "annotated_at": manifest["annotated_at"], "evidence_ref": manifest["evidence_ref"],
                "annotation_csv_sha256": csv_sha, "review_status": "DECLARED_NOT_INDEPENDENTLY_AUDITED",
            },
            "source_binding": {
                "status": "SOURCE_BYTES_HASH_MATCHED_AT_IMPORT", "source_id": manifest["source_id"],
                "source_sha256": actual_sha, "timeline_id": None, "time_base": None,
                "timestamp_semantics": "PROTOCOL_TEXT_ONLY_UNBOUND",
            },
        },
        "points": rows,
    }
    validate_bundle(bundle)
    return bundle


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def guard_match_media_linkage(bundle: dict) -> None:
    """Block implicit sidecar export; no cross-contract linkage is implemented."""
    validate_bundle(bundle)
    if bundle["dataset"]["dataset_class"] == "SIMULATED_ONLY":
        _error("SIMULATED_ONLY_NOT_EXPORTABLE", "synthetic analysis cannot be linked to real Match/VideoSource/LocalVideoAsset data")
    _error("MATCH_MEDIA_LINKAGE_NOT_IMPLEMENTED", "linking analysis to match-media requires a separate explicit, reviewed mapping")


def demo_with_mutation(bundle: dict | None = None) -> dict:
    source = copy.deepcopy(bundle or build_synthetic_demo())
    before = analyze_bundle(source)
    updated = change_point_annotation(source, game_number=1, point_number=1, field="rally_length", value=7)
    after = analyze_bundle(updated)
    old = before["summary"]["rally_length"]
    new = after["summary"]["rally_length"]
    return {
        "demo_version": "ptti.match-intelligence-demo/0.1",
        "evidence_class": "SIMULATED_ONLY",
        "change": {"point_id": _point_id(source["dataset"]["match_id"], 1, 1),
                   "field": "rally_length", "from": 5, "to": 7,
                   "expected_mean_delta": round(2 / old["denominator"], 6),
                   "actual_mean_delta": round(new["mean"] - old["mean"], 6)},
        "before": before,
        "after": after,
    }
