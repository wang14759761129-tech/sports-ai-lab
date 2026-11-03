"""Research-only adapter for Extended OpenTTGames annotations.

The adapter preserves native labels and makes all derived rally intervals
explicitly DERIVED. It never supplies ground-truth annotations to inference.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


SOURCE = "extended_openttgames"
RIGHTS = "CC BY-NC-SA 4.0"
COMMERCIAL_USE = False
ENDINGS = {"winner", "double_bounce", "net", "not_hitting_ball", "out", "miss_on_own_side"}
NATIVE_SIMPLE = {"bounce": "BOUNCE", "net": "NET", "empty_event": "EMPTY_EVENT"}
STROKES = {"serve", "loop", "block", "push", "flick", "lob", "chop", "smash"}
LEAN_LABELS = {"back_heavy", "front_heavy", "right_leaning", "left_leaning", "neutral", "unknown"}
FEET_LABELS = {"both_feet_planted", "both_feet_lifted", "right_foot_lifted", "left_foot_lifted", "unknown"}


@dataclass(frozen=True)
class EventGroundTruthAdapter:
    fps: float | None = None

    def parse(self, annotations: dict[str, Any], *, pts_ms: dict[int, float] | None = None) -> list[dict]:
        if not isinstance(annotations, dict):
            raise ValueError("Native annotation must be a frame-keyed JSON object")
        result = []
        for raw_frame, raw_label in sorted(annotations.items(), key=lambda item: int(item[0])):
            try:
                frame = int(raw_frame)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid annotation frame: {raw_frame!r}") from exc
            if frame < 0 or not isinstance(raw_label, str):
                raise ValueError("Annotation frames must be non-negative and labels must be strings")
            label = raw_label.strip()
            tokens = label.split()
            side = tokens[0].split("_", 1)[0] if tokens and tokens[0].startswith(("left_", "right_")) else None
            native_tail = tokens[0][len(side) + 1:] if side else (tokens[0] if tokens else "")
            event_type = NATIVE_SIMPLE.get(native_tail, "UNKNOWN_NATIVE_EVENT")
            hand = technique = None
            if native_tail in ENDINGS and (native_tail != "net" or side is not None):
                event_type = "RALLY_ENDING"
            else:
                match = re.fullmatch(r"(forehand|backhand)_(.+)", native_tail)
                if match and match.group(2) in STROKES:
                    hand, technique, event_type = match.group(1).upper(), match.group(2).upper(), "STROKE"
                elif native_tail in NATIVE_SIMPLE:
                    pass
                elif native_tail == "empty_event":
                    pass
                elif native_tail:
                    event_type = "UNKNOWN_NATIVE_EVENT"
            timestamp = None
            time_source = "UNAVAILABLE"
            if pts_ms is not None and frame in pts_ms:
                timestamp = float(pts_ms[frame]); time_source = "SOURCE_PTS"
            elif self.fps and self.fps > 0:
                timestamp = frame * 1000.0 / self.fps; time_source = "FRAME_RATE_ESTIMATE"
            result.append({
                "event_id": f"{SOURCE}:{frame}:{len(result)}", "frame": frame,
                "timestamp_ms": timestamp, "timestamp_source": time_source,
                "event_type": event_type, "player_side": side, "hand": hand,
                "technique": technique, "lean": next((x for x in tokens[1:] if x in LEAN_LABELS), None),
                "feet": next((x for x in tokens[1:] if x in FEET_LABELS), None),
                "native_label": label, "native_label_tail": native_tail,
                "native_attributes": tokens[1:], "source": SOURCE, "ground_truth": True,
            })
        return result


class ExtendedOpenTTGamesAdapter(EventGroundTruthAdapter):
    """Named dataset adapter; event parsing is shared with future event datasets."""

    def parse_ball_track(self, annotations: dict[str, Any], *, pts_ms: dict[int, float] | None = None) -> list[dict]:
        if not isinstance(annotations, dict):
            raise ValueError("Ball annotation must be a frame-keyed JSON object")
        rows = []
        for raw_frame, point in sorted(annotations.items(), key=lambda item: int(item[0])):
            frame = int(raw_frame)
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                raise ValueError(f"Invalid ball point at frame {raw_frame}")
            x, y = float(point["x"]), float(point["y"])
            visible = (x, y) != (-1.0, -1.0)
            rows.append({"frame": frame, "x": x if visible else None, "y": y if visible else None,
                         "visible": visible, "timestamp_ms": (float(pts_ms[frame]) if pts_ms and frame in pts_ms
                         else (frame * 1000.0 / self.fps if self.fps else None)),
                         "timestamp_source": "SOURCE_PTS" if pts_ms and frame in pts_ms else
                         ("FRAME_RATE_ESTIMATE" if self.fps else "UNAVAILABLE"),
                         "source": SOURCE, "ground_truth": True})
        return rows


def derive_rally_ground_truth(events: list[dict], *, frame_count: int | None = None) -> dict:
    """Derive conservative serve-to-ending intervals; preserve incomplete cases."""
    ordered = sorted(events, key=lambda event: (event["frame"], event["event_id"]))
    serves = [e for e in ordered if e.get("event_type") == "STROKE" and e.get("technique") == "SERVE"]
    endings = [e for e in ordered if e.get("event_type") == "RALLY_ENDING"]
    relevant = sorted([*serves, *endings], key=lambda e: (e["frame"], e["event_id"]))
    segments, incomplete = [], []
    pending = None
    for event in relevant:
        if event in serves:
            if pending:
                incomplete.append(_incomplete(pending, None, "NEW_SERVE_BEFORE_ENDING"))
            pending = event
        elif not pending:
            incomplete.append(_incomplete(None, event, "ENDING_WITHOUT_SERVE"))
        elif event["frame"] <= pending["frame"]:
            incomplete.append(_incomplete(pending, event, "NON_POSITIVE_INTERVAL")); pending = None
        elif frame_count is not None and (pending["frame"] >= frame_count or event["frame"] >= frame_count):
            incomplete.append(_incomplete(pending, event, "ANNOTATION_OUTSIDE_VIDEO")); pending = None
        else:
            segments.append({
                "segment_id": f"derived:{pending['frame']}:{event['frame']}",
                "start_frame": pending["frame"], "end_frame": event["frame"],
                "start_ms": pending.get("timestamp_ms"), "end_ms": event.get("timestamp_ms"),
                "ground_truth_type": "DERIVED", "status": "DERIVED_RALLY_SEGMENT",
                "start_source": "serve_annotation", "end_source": "rally_ending_annotation",
                "start_event_id": pending["event_id"], "end_event_id": event["event_id"],
                "ending_type": event.get("native_label_tail"), "ending_player_side": event.get("player_side"),
                "source": SOURCE,
            })
            pending = None
    if pending:
        incomplete.append(_incomplete(pending, None, "MISSING_RALLY_ENDING"))
    return {"ground_truth_type": "DERIVED_NOT_NATIVE", "segments": segments,
            "incomplete_ground_truth": incomplete,
            "counts": {"complete_derived_segments": len(segments), "incomplete": len(incomplete),
                       "serve_annotations": len(serves), "rally_ending_annotations": len(endings)}}


def _incomplete(start: dict | None, end: dict | None, reason: str) -> dict:
    event = start or end or {}
    return {"status": "INCOMPLETE_GROUND_TRUTH", "reason": reason,
            "frame": event.get("frame"), "start_event_id": start.get("event_id") if start else None,
            "end_event_id": end.get("event_id") if end else None,
            "native_label": event.get("native_label"), "source": SOURCE}


def match_segments(predictions: list[dict], ground_truth: list[dict], *, min_iou: float = 0.1,
                   max_boundary_delta_ms: float = 500) -> list[tuple[int, int, float]]:
    """Maximum-weight one-to-one assignment (Hungarian), avoiding greedy order matches."""
    if not predictions or not ground_truth:
        return []
    n, m = len(predictions), len(ground_truth)
    size = max(n, m)
    weights = [[0.0] * size for _ in range(size)]
    ious = [[0.0] * m for _ in range(n)]
    eligible = [[False] * m for _ in range(n)]
    for i, pred in enumerate(predictions):
        for j, truth in enumerate(ground_truth):
            ps, pe = float(pred["start_ms"]), float(pred["end_ms"])
            gs, ge = float(truth["start_ms"]), float(truth["end_ms"])
            intersection = max(0.0, min(pe, ge) - max(ps, gs))
            union = max(pe, ge) - min(ps, gs)
            iou = intersection / union if union > 0 else 0.0
            ious[i][j] = iou
            start_delta = abs(ps-gs); end_delta = abs(pe-ge)
            eligible[i][j] = iou >= min_iou or max(start_delta, end_delta) <= max_boundary_delta_ms
            if eligible[i][j]:
                proximity = 1.0 - min(1.0, (start_delta + end_delta) /
                                      max(1.0, 2 * max_boundary_delta_ms))
                weights[i][j] = 1.0 + iou + proximity * 1e-3
    assignment = _hungarian_max(weights)
    return [(i, j, ious[i][j]) for i, j in enumerate(assignment[:n])
            if j < m and eligible[i][j]]


def _hungarian_max(weights: list[list[float]]) -> list[int]:
    """Square maximum assignment implementation; returns column per row."""
    n = len(weights)
    if not n:
        return []
    maximum = max(max(row) for row in weights)
    cost = [[maximum - value for value in row] for row in weights]
    u, v, p, way = [0.0]*(n+1), [0.0]*(n+1), [0]*(n+1), [0]*(n+1)
    for i in range(1, n+1):
        p[0] = i; j0 = 0; minv = [float("inf")]*(n+1); used = [False]*(n+1)
        while True:
            used[j0] = True; i0 = p[j0]; delta = float("inf"); j1 = 0
            for j in range(1, n+1):
                if not used[j]:
                    cur = cost[i0-1][j-1] - u[i0] - v[j]
                    if cur < minv[j]: minv[j] = cur; way[j] = j0
                    if minv[j] < delta: delta = minv[j]; j1 = j
            for j in range(n+1):
                if used[j]: u[p[j]] += delta; v[j] -= delta
                else: minv[j] -= delta
            j0 = j1
            if p[j0] == 0: break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0: break
    result = [-1]*n
    for j in range(1, n+1):
        if p[j]: result[p[j]-1] = j-1
    return result


def evaluate_segments(predictions: list[dict], ground_truth: list[dict], *, min_iou: float = 0.1,
                      max_boundary_delta_ms: float = 500) -> dict:
    matches = match_segments(predictions, ground_truth, min_iou=min_iou,
                             max_boundary_delta_ms=max_boundary_delta_ms)
    matched_pred, matched_gt = {x[0] for x in matches}, {x[1] for x in matches}
    precision = len(matches) / len(predictions) if predictions else (1.0 if not ground_truth else 0.0)
    recall = len(matches) / len(ground_truth) if ground_truth else (1.0 if not predictions else 0.0)
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    start = [float(predictions[i]["start_ms"])-float(ground_truth[j]["start_ms"]) for i,j,_ in matches]
    end = [float(predictions[i]["end_ms"])-float(ground_truth[j]["end_ms"]) for i,j,_ in matches]
    def stats(values):
        values = sorted(abs(value) for value in values)
        if not values: return {"mae_ms": None, "median_abs_error_ms": None}
        mid = len(values)//2
        median = values[mid] if len(values)%2 else (values[mid-1]+values[mid])/2
        return {"mae_ms": sum(values)/len(values), "median_abs_error_ms": median}
    iou_values = sorted(x[2] for x in matches)
    if iou_values:
        middle = len(iou_values)//2
        median_iou = iou_values[middle] if len(iou_values)%2 else (iou_values[middle-1]+iou_values[middle])/2
    else:
        median_iou = None
    return {"gt_rallies": len(ground_truth), "suggested_rallies": len(predictions),
            "matched_rallies": len(matches), "missed_rallies": len(ground_truth)-len(matched_gt),
            "false_rallies": len(predictions)-len(matched_pred), "precision": precision,
            "recall": recall, "f1": f1, "start_error": stats(start), "end_error": stats(end),
            "mean_iou": sum(x[2] for x in matches)/len(matches) if matches else None,
            "median_iou": median_iou,
            "matches": [{"prediction_index": i, "ground_truth_index": j, "iou": score,
                         "start_delta_ms": start[k], "end_delta_ms": end[k],
                         "match_basis": ("IOU" if score >= min_iou else "BOUNDARY_PROXIMITY")}
                        for k,(i,j,score) in enumerate(matches)],
            "unmatched_prediction_indices": sorted(set(range(len(predictions)))-matched_pred),
            "unmatched_ground_truth_indices": sorted(set(range(len(ground_truth)))-matched_gt)}


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
