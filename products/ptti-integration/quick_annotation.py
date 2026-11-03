"""Versioned adapter from compact Web point input to Protocol v0.3 rows.

This module emits a review-only draft. It does not create a training report,
verify identities or rights, bind PTS/time_base, or claim Vision evidence.
"""
from __future__ import annotations

import copy
import csv
import io
import re
from urllib.parse import quote, unquote

from match_intelligence import (
    CATEGORIES,
    POINT_FIELDS,
    PROTOCOL_ID,
    PROTOCOL_SCHEMA_REVISION,
    PROTOCOL_VERSION,
    AnalysisValidationError,
    parse_protocol_v03_csv,
)


QUICK_ANNOTATION_VERSION = "ptti.quick-annotation/0.1"
TACTICAL_FIELDS = (
    "serve_side", "serve_length", "serve_location", "serve_spin",
    "receive_type", "receive_location", "third_ball_attack",
    "third_ball_side", "third_ball_outcome", "rally_length",
)
TACTICAL_FIELD_SET = set(TACTICAL_FIELDS)
POINT_ID_RE = re.compile(r"^(?P<match>.+)/g(?P<game>[0-9]{2,})/p(?P<point>[0-9]{3,})$")
UNRESOLVED = {"unknown", "unclear"}


class QuickAnnotationError(ValueError):
    """A fail-closed error in the versioned quick annotation input."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> None:
    raise QuickAnnotationError(code, detail)


def _exact_keys(value: object, expected: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        _fail("INVALID_FIELDS", f"{name} must contain exactly {sorted(expected)}")
    return value


def _nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip().lower() in UNRESOLVED:
        _fail("IDENTITY_UNRESOLVED", f"{name} must be an explicit non-UNKNOWN identifier")
    return value


def _positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        _fail("INVALID_INTEGER", f"{name} must be an integer >= {minimum}")
    return value


def _parse_point_id(value: object, match_id: str) -> tuple[int, int]:
    if not isinstance(value, str):
        _fail("INVALID_POINT_ID", "point_id must be a canonical Protocol point reference")
    found = POINT_ID_RE.fullmatch(value)
    if not found:
        _fail("INVALID_POINT_ID", "expected encoded-match-id/gNN/pNNN")
    game, point = int(found.group("game")), int(found.group("point"))
    canonical = f"{quote(match_id, safe='')}/g{game:02d}/p{point:03d}"
    if unquote(found.group("match")) != match_id or value != canonical:
        _fail("POINT_ID_MATCH_MISMATCH", "point_id must exactly encode the selected match_id and canonical game/point numbers")
    return game, point


def _opposite(side: str) -> str:
    return {"player": "opponent", "opponent": "player"}.get(side, "unknown")


def _service_for_point(first_server: str, point_number: int) -> str:
    completed = point_number - 1
    switches = (completed // 2) % 2 if completed < 20 else (completed - 10) % 2
    return first_server if switches == 0 else _opposite(first_server)


def _score_text(start_ms: int | None, end_ms: int | None) -> str:
    if start_ms is None:
        return "unknown"
    return f"start_ms={start_ms};end_ms={end_ms};binding=UNBOUND"


def _validate_game_context(value: object) -> dict[int, dict]:
    if not isinstance(value, list):
        _fail("INVALID_GAME_CONTEXT", "rules_context.games must be an array")
    result: dict[int, dict] = {}
    for index, raw in enumerate(value):
        game = _exact_keys(raw, {"game_number", "coverage", "first_server"}, f"rules_context.games[{index}]")
        number = _positive_int(game["game_number"], f"rules_context.games[{index}].game_number")
        if number in result:
            _fail("DUPLICATE_GAME_CONTEXT", f"game {number} has duplicate context")
        if not isinstance(game["coverage"], str) or game["coverage"] not in {"COMPLETE_FROM_GAME_START", "PARTIAL_OR_UNKNOWN"}:
            _fail("INVALID_GAME_CONTEXT", f"game {number} coverage is unsupported")
        if not isinstance(game["first_server"], str) or game["first_server"] not in {"player", "opponent", "unknown"}:
            _fail("INVALID_GAME_CONTEXT", f"game {number} first_server is unsupported")
        result[number] = game
    return result


def adapt_quick_annotation(payload: dict) -> dict:
    """Convert strict compact input to review-only draft plus 21-field rows.

    Only score/server rule derivations are made, and only when a game's input
    explicitly says it is complete from the game start. Tactical labels are
    copied literally; omitted values remain ``unknown``.
    """
    root = _exact_keys(payload, {
        "contract_version", "dataset_id", "dataset_class", "match_id",
        "video_context", "rules_context", "points",
    }, "input")
    if not isinstance(root["contract_version"], str) or root["contract_version"] != QUICK_ANNOTATION_VERSION:
        _fail("UNSUPPORTED_VERSION", f"expected {QUICK_ANNOTATION_VERSION}")
    dataset_id = _nonempty(root["dataset_id"], "dataset_id")
    dataset_class = root["dataset_class"]
    if not isinstance(dataset_class, str) or dataset_class not in {"HUMAN_QUICK_DRAFT", "SIMULATED_ONLY"}:
        _fail("INVALID_DATASET_CLASS", "dataset_class must be HUMAN_QUICK_DRAFT or SIMULATED_ONLY")
    match_id = _nonempty(root["match_id"], "match_id")
    if dataset_class == "SIMULATED_ONLY" and not match_id.startswith("SIMULATED_ONLY:"):
        _fail("SIMULATED_NAMESPACE_REQUIRED", "SIMULATED_ONLY input must use its reserved match namespace")
    if dataset_class == "SIMULATED_ONLY" and not dataset_id.startswith("SIMULATED_ONLY:"):
        _fail("SIMULATED_NAMESPACE_REQUIRED", "SIMULATED_ONLY input must use its reserved dataset namespace")
    if dataset_class == "HUMAN_QUICK_DRAFT" and match_id.startswith("SIMULATED_ONLY:"):
        _fail("SIMULATED_CANNOT_BE_HUMAN", "synthetic match IDs cannot be declared as human quick input")

    video = _exact_keys(root["video_context"], {"source_id", "duration_ms", "duration_status"}, "video_context")
    source_id = video["source_id"]
    if source_id is not None:
        source_id = _nonempty(source_id, "video_context.source_id")
    duration = video["duration_ms"]
    duration_status = video["duration_status"]
    if not isinstance(duration_status, str) or duration_status not in {"PLAYER_METADATA_REPORTED", "UNKNOWN"}:
        _fail("INVALID_DURATION_STATUS", "duration_status must be PLAYER_METADATA_REPORTED or UNKNOWN")
    if duration_status == "PLAYER_METADATA_REPORTED":
        duration = _positive_int(duration, "video_context.duration_ms")
    elif duration is not None:
        _fail("UNVERIFIED_DURATION_VALUE", "duration_ms must remain null when duration_status is UNKNOWN")

    game_context = _validate_game_context(root["rules_context"].get("games") if isinstance(root["rules_context"], dict)
                                          and set(root["rules_context"]) == {"games"} else None)
    raw_points = root["points"]
    if not isinstance(raw_points, list) or not raw_points:
        _fail("EMPTY_POINT_SET", "points must contain at least one point draft")

    parsed: list[dict] = []
    seen: set[str] = set()
    last_key = (0, 0)
    for index, raw in enumerate(raw_points):
        item = _exact_keys(raw, {
            "point_id", "server", "winner", "observed_tactics", "rally_start_ms", "rally_end_ms",
        }, f"points[{index}]")
        game_number, point_number = _parse_point_id(item["point_id"], match_id)
        if item["point_id"] in seen:
            _fail("DUPLICATE_POINT_ID", f"duplicate point_id {item['point_id']}")
        seen.add(item["point_id"])
        if (game_number, point_number) <= last_key:
            _fail("POINT_ORDER_INVALID", "points must be ordered by increasing game_number and point_number")
        last_key = game_number, point_number
        if not isinstance(item["server"], str) or item["server"] not in {"player", "opponent", "unknown"}:
            _fail("INVALID_SERVER", f"points[{index}].server is unsupported")
        if not isinstance(item["winner"], str) or item["winner"] not in {"player", "opponent", "unknown"}:
            _fail("INVALID_WINNER", f"points[{index}].winner is unsupported")
        tactics = item["observed_tactics"]
        if not isinstance(tactics, dict) or set(tactics) - TACTICAL_FIELD_SET:
            _fail("INVALID_TACTICAL_FIELDS", f"points[{index}].observed_tactics contains unsupported fields")
        normalized_tactics = {field: "unknown" for field in TACTICAL_FIELDS}
        for field, value in tactics.items():
            if field == "rally_length":
                if value != "unknown":
                    normalized_tactics[field] = _positive_int(value, f"points[{index}].observed_tactics.rally_length")
            elif not isinstance(value, str) or value not in CATEGORIES[field]:
                _fail("INVALID_TACTICAL_VALUE", f"points[{index}].observed_tactics.{field} is not an accepted observed label")
            else:
                normalized_tactics[field] = value
        if normalized_tactics["third_ball_attack"] in {"no", "not_applicable"}:
            for field in ("third_ball_side", "third_ball_outcome"):
                if field in tactics and normalized_tactics[field] not in {"unknown", "not_applicable"}:
                    _fail("THIRD_BALL_CONFLICT", f"{field} cannot be known when third-ball attack is {normalized_tactics['third_ball_attack']}")
                normalized_tactics[field] = "not_applicable"

        start, end = item["rally_start_ms"], item["rally_end_ms"]
        if start is None and end is None:
            pass
        elif type(start) is not int or type(end) is not int:
            _fail("INCOMPLETE_TIME_RANGE", "rally_start_ms and rally_end_ms must both be integers or both be null")
        elif duration_status != "PLAYER_METADATA_REPORTED" or duration is None:
            _fail("VIDEO_DURATION_REQUIRED", "time ranges require an explicitly reported video duration")
        elif start < 0 or start >= end or end > duration:
            _fail("TIME_RANGE_OUT_OF_BOUNDS", "time range must satisfy 0 <= start < end <= reported duration")
        parsed.append({
            "point_id": item["point_id"], "game_number": game_number, "point_number": point_number,
            "server_input": item["server"], "winner": item["winner"], "tactics": normalized_tactics,
            "rally_start_ms": start, "rally_end_ms": end,
        })

    # Resolve first-server evidence and validate explicitly observed service sides.
    by_game: dict[int, list[dict]] = {}
    for item in parsed:
        by_game.setdefault(item["game_number"], []).append(item)
    game_numbers = sorted(by_game)
    protocol_sequence_valid = game_numbers == list(range(1, max(game_numbers) + 1))
    for game_number, rows in by_game.items():
        point_numbers = [row["point_number"] for row in rows]
        if point_numbers != list(range(1, max(point_numbers) + 1)):
            protocol_sequence_valid = False
    derived_server: dict[str, str] = {}
    derivation: dict[str, dict] = {}
    score_before: dict[str, tuple[int, int] | None] = {}
    for game_number, rows in by_game.items():
        context = game_context.get(game_number, {"coverage": "PARTIAL_OR_UNKNOWN", "first_server": "unknown"})
        complete = context["coverage"] == "COMPLETE_FROM_GAME_START"
        first_row = next((row for row in rows if row["point_number"] == 1), None)
        first_server = context["first_server"]
        if first_server == "unknown" and first_row and first_row["server_input"] != "unknown":
            first_server = first_row["server_input"]
        can_derive_rules = complete and first_server in {"player", "opponent"}
        if can_derive_rules and first_row and first_row["server_input"] not in {"unknown", first_server}:
            _fail("FIRST_SERVER_CONFLICT", f"game {game_number} point 1 conflicts with declared first_server")
        if can_derive_rules:
            for row in rows:
                expected_server = _service_for_point(first_server, row["point_number"])
                observed_server = row["server_input"]
                if observed_server != "unknown" and observed_server != expected_server:
                    _fail("SERVICE_ROTATION_CONFLICT", f"{row['point_id']} observed server conflicts with rule-derived service side")
                derived_server[row["point_id"]] = expected_server
                derivation[row["point_id"]] = {"server": "OBSERVED_MATCHES_RULE" if observed_server != "unknown"
                                                else "RULE_DERIVED_FROM_GAME_START_FIRST_SERVER"}
        else:
            for row in rows:
                derived_server[row["point_id"]] = row["server_input"]
                derivation[row["point_id"]] = {"server": "OBSERVED" if row["server_input"] != "unknown" else "UNKNOWN"}

        # Scores start at 0:0 only under an explicit complete-from-game-start declaration.
        state: tuple[int, int] | None = (0, 0) if complete and first_row and first_row["point_number"] == 1 else None
        expected_point = 1
        for row in rows:
            if row["point_number"] != expected_point:
                state = None
            score_before[row["point_id"]] = state
            expected_point = row["point_number"] + 1
            if state is None or row["winner"] == "unknown":
                state = None
            elif row["winner"] == "player":
                state = (state[0] + 1, state[1])
            else:
                state = (state[0], state[1] + 1)

    protocol_rows = []
    point_review = []
    for item in parsed:
        server = derived_server[item["point_id"]]
        receiver = _opposite(server)
        global_score = score_before[item["point_id"]]
        if global_score is None or server == "unknown":
            server_score = receiver_score = "unknown"
            score_status = "UNKNOWN_INSUFFICIENT_PREVIOUS_POINTS"
            key_status = "UNKNOWN_SCORE"
        else:
            side_scores = {"player": global_score[0], "opponent": global_score[1]}
            server_score, receiver_score = side_scores[server], side_scores[receiver]
            score_status = "RULE_DERIVED_FROM_COMPLETE_DECLARED_GAME_AND_KNOWN_WINNERS"
            key_status = ("RULE_DERIVED_CANDIDATE" if min(global_score) >= 7 and abs(global_score[0] - global_score[1]) <= 1
                          else "NOT_KEY_SCORE")
        winner = item["winner"]
        point_outcome = "unknown" if winner == "unknown" else ("win" if winner == "player" else "loss")
        timestamp = _score_text(item["rally_start_ms"], item["rally_end_ms"])
        row = {
            "match_id": match_id, "game_number": item["game_number"], "point_number": item["point_number"],
            "server": server, "receiver": receiver,
            "server_score_before": server_score, "receiver_score_before": receiver_score,
            **item["tactics"], "point_winner": winner, "point_outcome": point_outcome,
            "video_timestamp": timestamp,
            "notes": "Quick annotation draft; review required.",
        }
        if set(row) != set(POINT_FIELDS):
            _fail("INTERNAL_PROTOCOL_MAPPING_ERROR", "adapter mapping does not produce exactly the existing 21 fields")
        protocol_rows.append(row)
        point_review.append({
            "point_id": item["point_id"],
            "timestamp": {"start_ms": item["rally_start_ms"], "end_ms": item["rally_end_ms"],
                          "range_status": "CHECKED_AGAINST_USER_REPORTED_DURATION" if item["rally_start_ms"] is not None else "UNKNOWN",
                          "timeline_binding": "UNBOUND"},
            "field_derivation": {**derivation[item["point_id"]], "receiver": "DERIVED_OPPOSITE_SIDE" if server != "unknown" else "UNKNOWN",
                                 "score": score_status, "point_outcome": "DERIVED_FROM_EXPLICIT_WINNER" if winner != "unknown" else "UNKNOWN",
                                 "tactical_labels": "COPIED_ONLY_FROM_OBSERVED_TACTICS"},
            "score_before_player_opponent": None if global_score is None else {"player": global_score[0], "opponent": global_score[1]},
            "key_point_status": key_status,
            "review_status": "REVIEW_REQUIRED",
        })

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=POINT_FIELDS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(protocol_rows)
    csv_bytes = output.getvalue().encode("utf-8")
    # This checks exact headers, row width and primitive types only. The result
    # is deliberately not a formal Match Intelligence bundle/report.
    parsed_csv = parse_protocol_v03_csv(csv_bytes)
    if parsed_csv != protocol_rows:
        _fail("INTERNAL_PROTOCOL_MAPPING_ERROR", "serialized rows did not round-trip through Protocol v0.3 parser")

    missing = sorted({field for row in protocol_rows for field in POINT_FIELDS
                      if isinstance(row[field], str) and row[field] in {"unknown", "unclear"}})
    review_items = []
    for row, point in zip(protocol_rows, point_review):
        uncertain = [field for field in POINT_FIELDS if isinstance(row[field], str) and row[field] in {"unknown", "unclear"}]
        if uncertain:
            review_items.append({"point_id": point["point_id"], "code": "QUICK_DRAFT_UNCERTAINTY", "fields": uncertain})
        if point["timestamp"]["start_ms"] is not None:
            review_items.append({"point_id": point["point_id"], "code": "TIMESTAMP_UNBOUND", "fields": ["video_timestamp"]})
    blockers = [
        "formal annotation manifest and annotator/evidence declarations are absent",
        "source file bytes, source identity, and rights have not been independently checked",
        "quick timestamps remain free text and are not bound to timeline_id, PTS, or time_base",
        "quality review has not completed; quick input cannot become a training report automatically",
    ]
    if not protocol_sequence_valid:
        blockers.append("point rows do not form contiguous Protocol v0.3 sequences starting at game 1, point 1")
    if source_id is None:
        blockers.append("no VideoSource was selected")
    return {
        "contract_version": QUICK_ANNOTATION_VERSION,
        "draft_status": "SIMULATED_ONLY" if dataset_class == "SIMULATED_ONLY" else "LIGHT_ANNOTATION_DRAFT",
        "evidence_status": "SIMULATED_ONLY" if dataset_class == "SIMULATED_ONLY" else "REVIEW_REQUIRED",
        "dataset": {"dataset_id": dataset_id, "dataset_class": dataset_class, "match_id": match_id,
                    "match_link_status": "NOT_APPLICABLE_SIMULATED" if dataset_class == "SIMULATED_ONLY" else "USER_SELECTED_UNVERIFIED",
                    "source_id": source_id, "source_link_status": "UNBOUND" if source_id is None else "USER_SELECTED_UNVERIFIED",
                    "rights_status": "UNKNOWN", "local_analysis_permission": "UNKNOWN",
                    "embed_permission": "UNKNOWN", "source_video_sha256": None,
                    "video_duration_ms": duration, "duration_evidence_status": "USER_REPORTED_UNVERIFIED" if duration is not None else "UNKNOWN",
                    "timeline_id": None, "pts": None, "time_base": None, "vision_status": "NOT_TESTED"},
        "protocol": {"id": PROTOCOL_ID, "version": PROTOCOL_VERSION, "schema_revision": PROTOCOL_SCHEMA_REVISION,
                     "fields": list(POINT_FIELDS), "csv_utf8": csv_bytes.decode("utf-8"),
                     "rows_parseable": True, "sequence_valid": protocol_sequence_valid,
                     "formal_bundle_validated": False},
        "points": [{"point_id": record["point_id"], "protocol_fields": copy.deepcopy(row), **record}
                   for row, record in zip(protocol_rows, point_review)],
        "review_queue": {"status": "QUICK_DRAFT_REQUIRES_EXISTING_FORMAL_IMPORT_AND_AUDIT",
                         "unknown_or_unclear_fields": missing, "items": review_items,
                         "existing_training_quality_audit": "NOT_RUN", "automatic_promotion": False},
        "formal_report_eligibility": {"eligible": False, "blockers": blockers},
    }
