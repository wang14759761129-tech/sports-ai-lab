"""Evidence-first match-structure suggestions, separate from BallTrack inference.

This baseline intentionally suggests rally boundaries only. It never converts a
missing observation into a point result, and it never edits the human timeline.
"""
from __future__ import annotations

from dataclasses import dataclass
import bisect
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


EVENT_TYPES = {
    "RALLY_START_CANDIDATE", "RALLY_END_CANDIDATE", "SERVE_START_CANDIDATE",
    "BALL_CONTACT_CANDIDATE", "TABLE_BOUNCE_CANDIDATE", "NET_CROSSING_CANDIDATE",
    "SCENE_CHANGE", "REPLAY_START_CANDIDATE", "REPLAY_END_CANDIDATE",
    "POINT_START_CANDIDATE", "POINT_END_CANDIDATE",
}
NOT_IMPLEMENTED_TYPES = EVENT_TYPES - {"RALLY_START_CANDIDATE", "RALLY_END_CANDIDATE", "SCENE_CHANGE"}


@dataclass(frozen=True)
class RallyActivitySignal:
    timestamp_ms: float
    state: str
    evidence: tuple[dict[str, Any], ...]


class MatchStructureEngine:
    """Generate conservative rally-boundary suggestions from unified RAW rows."""

    def __init__(self, *, minimum_gap_ms: int = 700, context_window_ms: int = 1200,
                 minimum_context_observations: int = 2):
        if minimum_gap_ms < 1 or context_window_ms < 1 or minimum_context_observations < 1:
            raise ValueError("Match-structure windows must be positive")
        self.minimum_gap_ms = minimum_gap_ms
        self.context_window_ms = context_window_ms
        self.minimum_context_observations = minimum_context_observations

    @staticmethod
    def activity(row: dict, previous: dict | None = None) -> RallyActivitySignal:
        timestamp = float(row.get("timestamp_ms", 0))
        if row.get("scene_transition"):
            return RallyActivitySignal(timestamp, "SCENE_TRANSITION", ({"type": "SCENE_TRANSITION"},))
        if row.get("visible") is True and row.get("x") is not None and row.get("y") is not None:
            state="UNKNOWN"
            evidence_type="RAW_BALL_OBSERVATION"
            if previous and previous.get("visible") is True and previous.get("x") is not None and previous.get("y") is not None:
                state=("ACTIVE_BALL_MOVEMENT" if (row["x"],row["y"])!=(previous["x"],previous["y"])
                       else "LOW_ACTIVITY")
                evidence_type="RAW_BALL_DISPLACEMENT"
            return RallyActivitySignal(timestamp, state, ({
                "type": evidence_type, "global_frame": row.get("global_frame"), "activity_state":state,
                "model_probability": row.get("raw_model_score"),
            },))
        if row.get("visible") is False:
            return RallyActivitySignal(timestamp, "BALL_NOT_VISIBLE", ({
                "type": "BALL_TRACK_LOST", "global_frame": row.get("global_frame"),
            },))
        return RallyActivitySignal(timestamp, "UNKNOWN", ({"type": "BALL_ACTIVITY_UNKNOWN"},))

    def suggest(self, observations: list[dict], *, match_id: str,
                video_sha256: str, manual_timeline: dict | None = None,
                source_module: str = "RACKETVISION_RAW") -> dict:
        rows = sorted((dict(item) for item in observations),
                      key=lambda item: (float(item.get("timestamp_ms", 0)), int(item.get("global_frame", -1))))
        timestamps=[float(row.get("timestamp_ms",0)) for row in rows]
        if any(float(row.get("timestamp_ms", 0)) < 0 for row in rows):
            raise ValueError("Observation timestamps must be non-negative")
        if any(float(a.get("timestamp_ms", 0)) > float(b.get("timestamp_ms", 0))
               for a, b in zip(rows, rows[1:])):
            raise ValueError("Observation timeline must be monotonic")
        events: list[dict] = []
        rallies: list[dict] = []
        conflicts: list[dict] = []
        boundaries: list[tuple[dict, dict]] = []
        # Find consecutive missing-observation runs on the one unified timeline.
        index = 0
        while index < len(rows):
            if rows[index].get("visible") is not False:
                index += 1
                continue
            gap_start = index
            while index + 1 < len(rows) and rows[index + 1].get("visible") is False:
                index += 1
            gap_end = index
            index += 1
            if gap_start == 0 or gap_end == len(rows) - 1:
                continue
            before, after = rows[gap_start - 1], rows[gap_end + 1]
            start_gap = float(rows[gap_start].get("timestamp_ms", 0))
            end_gap = float(rows[gap_end].get("timestamp_ms", start_gap))
            duration = max(0.0, end_gap - start_gap)
            if duration < self.minimum_gap_ms:
                continue
            left_start=bisect.bisect_left(timestamps,start_gap-self.context_window_ms,0,gap_start)
            right_end=bisect.bisect_right(timestamps,end_gap+self.context_window_ms,gap_end+1)
            left = [row for row in rows[left_start:gap_start] if row.get("visible") is True]
            right = [row for row in rows[gap_end+1:right_end] if row.get("visible") is True]
            if min(len(left), len(right)) < self.minimum_context_observations:
                continue
            left_motion=sum((a.get("x"),a.get("y"))!=(b.get("x"),b.get("y"))
                            for a,b in zip(left,left[1:]) if None not in (a.get("x"),a.get("y"),b.get("x"),b.get("y")))
            right_motion=sum((a.get("x"),a.get("y"))!=(b.get("x"),b.get("y"))
                             for a,b in zip(right,right[1:]) if None not in (a.get("x"),a.get("y"),b.get("x"),b.get("y")))
            if min(left_motion,right_motion)<1:
                continue
            gap_rows = rows[gap_start:gap_end + 1]
            if any(row.get("scene_transition") for row in gap_rows):
                continue
            non_play=[segment for segment in (manual_timeline or {}).get("scene_segments",[])
                      if segment.get("scene_type") in {"REPLAY","CROWD","TIMEOUT","BREAK","NON_PLAY_VIEW"}
                      and float(segment.get("start_ms",0)) < end_gap
                      and float(segment.get("end_ms",0)) > start_gap]
            if non_play:
                continue
            end_ms = float(before.get("timestamp_ms", 0))
            start_ms = float(after.get("timestamp_ms", end_ms))
            shared_evidence = [
                {"type": "BALL_TRACK_LOST", "duration_ms": round(duration, 3),
                 "first_missing_frame": rows[gap_start].get("global_frame"),
                 "last_missing_frame": rows[gap_end].get("global_frame")},
                {"type": "BALL_ACTIVITY_BEFORE_AND_AFTER", "context_window_ms": self.context_window_ms,
                 "visible_observations_before": len(left), "visible_observations_after": len(right),
                 "coordinate_changes_before": left_motion, "coordinate_changes_after": right_motion},
                {"type": "UNIFIED_TIMELINE", "chunk_boundary_crossed":
                 before.get("chunk_index") != after.get("chunk_index")},
            ]
            end_event = self._event("RALLY_END_CANDIDATE", end_ms, before, shared_evidence,
                                    match_id, video_sha256, source_module)
            start_event = self._event("RALLY_START_CANDIDATE", start_ms, after, shared_evidence,
                                      match_id, video_sha256, source_module)
            events.extend((end_event, start_event))
            boundaries.append((end_event, start_event))
        # A candidate rally is the visible activity interval between two
        # independently supported missing-ball boundaries. Clip edges remain unknown.
        for previous_gap, next_gap in zip(boundaries, boundaries[1:]):
            start_event, end_event = previous_gap[1], next_gap[0]
            start_ms, end_ms = start_event["timestamp_ms"], end_event["timestamp_ms"]
            if start_ms >= end_ms:
                continue
            if any(segment.get("review_status") == "ACCEPTED"
                   and segment.get("scene_type") in {"REPLAY","CROWD","TIMEOUT","BREAK","NON_PLAY_VIEW"}
                   and float(segment.get("start_ms",0)) < end_ms
                   and float(segment.get("end_ms",0)) > start_ms
                   for segment in (manual_timeline or {}).get("scene_segments",[])):
                continue
            rally_evidence = [
                {"type": "RALLY_START_BOUNDARY", "event_id": start_event["event_id"],
                 "timestamp_ms": start_ms},
                {"type": "RALLY_END_BOUNDARY", "event_id": end_event["event_id"],
                 "timestamp_ms": end_ms},
                {"type": "ACTIVE_BALL_OBSERVATIONS", "count": sum(
                    row.get("visible") is True for row in rows[
                        bisect.bisect_left(timestamps,start_ms):bisect.bisect_right(timestamps,end_ms)])},
            ]
            rally = {"segment_id": str(uuid4()), "start_ms": round(start_ms),
                     "end_ms": round(end_ms), "status": "SUGGESTED",
                     "start_event_id": start_event["event_id"], "end_event_id": end_event["event_id"],
                     "evidence": rally_evidence, "source_modules": [source_module], "confidence": None}
            rallies.append(rally)
            for manual in _manual_rallies(manual_timeline or {}):
                if start_ms < manual["end_ms"] and end_ms > manual["start_ms"]:
                    conflicts.append({"suggestion_id": rally["segment_id"], "manual_rally_id": manual["rally_id"],
                                      "type": "MANUAL_RALLY_OVERLAP", "status": "REVIEW_REQUIRED"})
        return {
            "schema_version": "ptti-match-structure-0.1",
            "match_id": match_id, "video_sha256": video_sha256,
            "status": "BASELINE_ENGINEERING_QA", "events": events, "rallies": rallies,
            "points": [], "games": [], "candidate_events": events, "confirmed_events": [],
            "conflicts": conflicts,
            "capabilities": {"rally_boundaries": "EXPERIMENTAL", "scene_change": "EXPERIMENTAL",
                             "replay": "DISABLED_EXPERIMENTAL", "scoreboard": "DISABLED_EXPERIMENTAL",
                             "contact": "NOT_IMPLEMENTED", "bounce": "NOT_IMPLEMENTED",
                             "point_boundaries": "NOT_IMPLEMENTED"},
            "limitations": ["Engineering QA baseline only; no annotated real-match accuracy evaluation is available.",
                            "A missing BallTrack interval is combined with visible activity on both sides; it is not treated as a point end.",
                            "No suggestion in this output is a confirmed match fact."],
        }

    @staticmethod
    def _event(event_type: str, timestamp: float, row: dict, evidence: list[dict],
               match_id: str, video_sha256: str, source_module: str) -> dict:
        return {"event_id": str(uuid4()), "event_type": event_type,
                "timestamp_ms": round(timestamp, 3), "frame": row.get("global_frame"),
                "status": "SUGGESTED", "confidence": None, "evidence": evidence,
                "source_modules": [source_module], "match_id": match_id,
                "video_sha256": video_sha256}


def _manual_rallies(timeline: dict) -> list[dict]:
    return [rally for game in timeline.get("games", []) for point in game.get("points", [])
            for rally in point.get("rallies", [])]


class ScoreboardRecognizer:
    """Interface only. OCR is explicitly disabled and never returns inferred facts."""
    status = "DISABLED_EXPERIMENTAL"

    def recognize(self, frame) -> None:
        return None


class SceneBoundaryDetector:
    """Small, inspectable histogram-distance baseline; emits suggestions only."""
    status = "EXPERIMENTAL"

    @staticmethod
    def compare_histograms(previous: list[float], current: list[float], *, threshold: float = 0.55) -> dict:
        if len(previous) != len(current) or not previous:
            raise ValueError("Comparable non-empty histograms are required")
        p_sum, c_sum = sum(previous), sum(current)
        if p_sum <= 0 or c_sum <= 0:
            raise ValueError("Histogram bins must have positive mass")
        distance = 0.5 * sum(abs(a / p_sum - b / c_sum) for a, b in zip(previous, current))
        return {"status": "SUGGESTED" if distance >= threshold else "NO_BOUNDARY_SUGGESTION",
                "event_type": "SCENE_CHANGE" if distance >= threshold else None,
                "confidence": None, "evidence": [{"type": "NORMALIZED_HISTOGRAM_L1", "distance": distance,
                                                    "threshold": threshold}]}


def table_homography(corners: list[list[float]]) -> list[list[float]]:
    """Map ordered image corners TL,TR,BR,BL to X/Y in [0,1]."""
    if len(corners) != 4 or any(len(point) != 2 for point in corners):
        raise ValueError("Exactly four [x,y] table corners are required")
    (x0,y0),(x1,y1),(x2,y2),(x3,y3) = [[float(v) for v in point] for point in corners]
    edges=[(x1-x0,y1-y0),(x2-x1,y2-y1),(x3-x2,y3-y2),(x0-x3,y0-y3)]
    turns=[edges[i][0]*edges[(i+1)%4][1]-edges[i][1]*edges[(i+1)%4][0] for i in range(4)]
    if not (all(v>1e-8 for v in turns) or all(v < -1e-8 for v in turns)):
        raise ValueError("Table calibration corners must form a convex, consistently ordered quadrilateral with non-zero area")
    area = abs(sum(corners[i][0] * corners[(i+1)%4][1] - corners[(i+1)%4][0] * corners[i][1] for i in range(4))) / 2
    if area <= 1:
        raise ValueError("Table calibration corners must enclose a non-zero area")
    source = [(x0,y0,0,0),(x1,y1,1,0),(x2,y2,1,1),(x3,y3,0,1)]
    matrix, target = [], []
    for x,y,u,v in source:
        matrix.append([x,y,1,0,0,0,-u*x,-u*y]); target.append(u)
        matrix.append([0,0,0,x,y,1,-v*x,-v*y]); target.append(v)
    coeff = _solve(matrix, target)
    return [coeff[0:3], coeff[3:6], [coeff[6], coeff[7], 1.0]]


def _solve(matrix: list[list[float]], target: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row,value in zip(matrix,target)]
    n = len(target)
    for col in range(n):
        pivot = max(range(col,n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-10:
            raise ValueError("Table calibration corners are degenerate")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        augmented[col] = [v/scale for v in augmented[col]]
        for row in range(n):
            if row == col: continue
            scale = augmented[row][col]
            augmented[row] = [a-scale*b for a,b in zip(augmented[row],augmented[col])]
    return [augmented[i][-1] for i in range(n)]


def normalize_table_point(homography: list[list[float]], x: float, y: float) -> dict:
    denominator = homography[2][0]*x + homography[2][1]*y + homography[2][2]
    if abs(denominator) < 1e-10:
        raise ValueError("Point maps to an invalid projective coordinate")
    return {"x": (homography[0][0]*x + homography[0][1]*y + homography[0][2])/denominator,
            "y": (homography[1][0]*x + homography[1][1]*y + homography[1][2])/denominator,
            "coordinate_system": {"x": "left-to-right as viewed in frame", "y": "near-endline to far-endline"}}


def configuration_sha256(config: dict) -> str:
    return sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def review_queue(structure: dict) -> list[dict]:
    conflicted = {item["suggestion_id"] for item in structure.get("conflicts", [])}
    return [dict(item, has_manual_conflict=item["segment_id"] in conflicted)
            for item in structure.get("rallies", []) if item.get("status") == "SUGGESTED"]


def review_rally(structure: dict, segment_id: str, action: str, *, start_ms: int | None = None,
                 end_ms: int | None = None, split_at_ms: int | None = None,
                 target_segment_id: str | None = None, actor: str = "HUMAN") -> dict:
    """Explicit human decision with immutable suggestion/evidence and append-only audit."""
    from copy import deepcopy
    from datetime import datetime, timezone
    from uuid import uuid4

    result = deepcopy(structure)
    item = next((r for r in result.get("rallies", []) if r["segment_id"] == segment_id), None)
    if item is None:
        raise ValueError("Rally suggestion does not exist")
    if item.get("status") != "SUGGESTED":
        raise ValueError("Only a suggested rally can be reviewed")
    previous = {key: item.get(key) for key in ("status", "start_ms", "end_ms")}
    now = datetime.now(timezone.utc).isoformat()
    audit = result.setdefault("audit_trail", [])
    if action == "accept":
        item["status"] = "CONFIRMED"
        item["confirmed_by"] = actor
        accepted_ids={item.get("start_event_id"),item.get("end_event_id")}
        for event in result.get("events",[]):
            if event["event_id"] in accepted_ids:
                event["status"]="CONFIRMED"
                event["confirmed_by"]=actor
        result.setdefault("confirmed_events", []).extend(
            dict(event, status="CONFIRMED", confirmed_by=actor)
            for event in result.get("events", [])
            if event["event_id"] in accepted_ids)
    elif action == "reject":
        item["status"] = "REJECTED"
        item["rejected_by"] = actor
    elif action == "adjust":
        new_start = item["start_ms"] if start_ms is None else start_ms
        new_end = item["end_ms"] if end_ms is None else end_ms
        if new_start < 0 or new_end <= new_start:
            raise ValueError("Adjusted rally needs a positive interval")
        item.update(start_ms=new_start, end_ms=new_end, status="CONFIRMED", review_action="ADJUSTED",
                    confirmed_by=actor)
    elif action == "split":
        if split_at_ms is None or not item["start_ms"] < split_at_ms < item["end_ms"]:
            raise ValueError("Split time must be inside the suggested rally")
        item["status"] = "REJECTED"
        item["review_action"] = "SPLIT_INTO_CONFIRMED_SEGMENTS"
        result["rallies"].extend([
            {**deepcopy(item), "segment_id": str(uuid4()), "start_ms": previous["start_ms"],
             "end_ms": split_at_ms, "status": "CONFIRMED", "confirmed_by": actor,
             "review_action": "SPLIT_LEFT", "suggestion_origin_id": segment_id},
            {**deepcopy(item), "segment_id": str(uuid4()), "start_ms": split_at_ms,
             "end_ms": previous["end_ms"], "status": "CONFIRMED", "confirmed_by": actor,
             "review_action": "SPLIT_RIGHT", "suggestion_origin_id": segment_id},
        ])
    elif action == "merge":
        other = next((r for r in result["rallies"] if r["segment_id"] == target_segment_id), None)
        if not other or other is item or other.get("status") != "SUGGESTED":
            raise ValueError("Merge target must be another suggested rally")
        if max(item["start_ms"], other["start_ms"]) > min(item["end_ms"], other["end_ms"]):
            raise ValueError("Only overlapping or adjacent rallies can be merged")
        item.update(start_ms=min(item["start_ms"], other["start_ms"]),
                    end_ms=max(item["end_ms"], other["end_ms"]), status="CONFIRMED",
                    review_action="MERGED", confirmed_by=actor,
                    merged_segment_ids=[segment_id, target_segment_id],
                    evidence=item.get("evidence",[])+other.get("evidence",[]),
                    source_modules=sorted(set(item.get("source_modules",[])+other.get("source_modules",[]))))
        other["status"] = "REJECTED"
        other["review_action"] = "MERGED_INTO:" + segment_id
    else:
        raise ValueError("Review action must be accept, reject, adjust, split, or merge")
    audit.append({"audit_id": str(uuid4()), "timestamp": now, "actor": actor,
                  "entity_id": segment_id, "action": action, "before": previous,
                  "after": {key: item.get(key) for key in ("status", "start_ms", "end_ms")},
                  "related_entity_id": target_segment_id if action=="merge" else None,
                  "related_before": ({key: other.get(key) for key in ("status","start_ms","end_ms")}
                                     if action=="merge" else None),
                  "evidence_preserved": True})
    return result


def calibration_status(calibration: dict, video_sha256: str, camera_segment_id: str) -> str:
    return "VALID" if (calibration.get("video_sha256") == video_sha256 and
                        calibration.get("camera_segment_id") == camera_segment_id) else "STALE"


def write_match_structure_outputs(output_dir: Path, run_id: str, structure: dict) -> None:
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/"match_structure.json").write_text(
        json.dumps({"run_id":run_id,**structure},ensure_ascii=False,indent=2),encoding="utf-8")
    confirmed=''.join(f'<li>{escape(str(item.get("event_type")))} · {item.get("timestamp_ms")} ms</li>'
                      for item in structure.get("confirmed_events",[])) or '<li>暂无人工确认事件</li>'
    suggested=''.join(f'<li>{escape(str(item.get("event_type")))} · {item.get("timestamp_ms")} ms · SUGGESTED</li>'
                      for item in structure.get("events",[]) if item.get("status")=="SUGGESTED") or '<li>暂无建议</li>'
    unknown='<p>点、局、接触、触台与回放等未实现或证据不足的内容保持未知，不生成比赛事实。</p>'
    (output_dir/"match_structure.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Match Structure</title>'
        '<h1>Match Structure · 工程基线</h1><h2>Confirmed</h2><ul>'+confirmed+
        '</ul><h2>Suggested</h2><ul>'+suggested+'</ul><h2>Unknown</h2>'+unknown,encoding="utf-8")

