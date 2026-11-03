"""Evidence-first hit candidates on a canonical, timestamp-aligned video timeline.

This module combines observations only. It does not infer stroke technique,
serve quality, spin, tactical intent, or a calibrated hit probability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import os
from typing import Any, Mapping, Sequence


ROLES = ("NEAR_PLAYER", "FAR_PLAYER")
_ALLOWED_WEIGHTS = {
    "ball_player_proximity", "wrist_proximity_proxy", "trajectory_direction_change",
    "ball_speed_change", "wrist_speed_peak", "pose_quality", "track_health",
}


@dataclass(frozen=True)
class CanonicalVideoTimeline:
    """Map sampled processing frames to source frames and absolute video time.

    ``processing_pts_ms`` are probed from the actual processed clip. The clip's
    registered origin binds those PTS to the full match. If source PTS were
    retained, they take precedence for the canonical timestamp.
    """

    video_sha256: str
    source_fps: float
    processing_fps: float
    source_frame_start: int
    clip_start_timestamp_ms: float
    processing_pts_ms: Sequence[float]
    source_pts_ms: Mapping[int, float] | None = None
    clip_duration_ms: float | None = None

    def __post_init__(self):
        if len(self.video_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.video_sha256.lower()):
            raise ValueError("INVALID_VIDEO_SHA256")
        if self.source_fps <= 0 or self.processing_fps <= 0 or self.source_frame_start < 0:
            raise ValueError("INVALID_TIMELINE_RATE_OR_ORIGIN")
        pts = tuple(float(value) for value in self.processing_pts_ms)
        if not pts or any(not math.isfinite(value) or value < 0 for value in pts):
            raise ValueError("INVALID_PROCESSING_PTS")
        if any(right <= left for left, right in zip(pts, pts[1:])):
            raise ValueError("PROCESSING_PTS_NOT_MONOTONIC")
        if not math.isfinite(self.clip_start_timestamp_ms) or self.clip_start_timestamp_ms < 0:
            raise ValueError("INVALID_CLIP_ORIGIN")
        duration = (float(self.clip_duration_ms) if self.clip_duration_ms is not None else
                    pts[-1] + 1000.0 / self.processing_fps)
        if not math.isfinite(duration) or duration <= pts[-1]:
            raise ValueError("INVALID_CLIP_DURATION")
        object.__setattr__(self, "clip_duration_ms", duration)
        if self.source_pts_ms:
            values = [float(value) for _, value in sorted(self.source_pts_ms.items())]
            if any(not math.isfinite(value) or value < 0 for value in values):
                raise ValueError("INVALID_SOURCE_PTS")
            if any(right <= left for left, right in zip(values, values[1:])):
                raise ValueError("SOURCE_PTS_NOT_MONOTONIC")
        object.__setattr__(self, "processing_pts_ms", pts)

    def map_processing_frame(self, processing_frame: int) -> dict[str, Any]:
        if not isinstance(processing_frame, int) or not 0 <= processing_frame < len(self.processing_pts_ms):
            raise ValueError("PROCESSING_FRAME_OUT_OF_RANGE")
        clip_pts = float(self.processing_pts_ms[processing_frame])
        source_frame = self.source_frame_start + round(clip_pts * self.source_fps / 1000.0)
        timestamp_ms = float(self.clip_start_timestamp_ms + clip_pts)
        timestamp_source = "PROCESSING_PTS_PLUS_REGISTERED_ORIGIN"
        alignment_delta_ms = None
        if self.source_pts_ms is not None and source_frame in self.source_pts_ms:
            exact_source_time = float(self.source_pts_ms[source_frame])
            alignment_delta_ms = exact_source_time - timestamp_ms
            timestamp_ms = exact_source_time
            timestamp_source = "SOURCE_PTS"
        return {
            "video_sha256": self.video_sha256,
            "source_frame": source_frame,
            "source_timestamp_ms": timestamp_ms,
            "processing_frame": processing_frame,
            "processing_fps": self.processing_fps,
            "timestamp_ms": timestamp_ms,
            "timestamp_source": timestamp_source,
            "alignment_delta_ms": alignment_delta_ms,
        }

    def map_source_frame(self, source_frame: int) -> dict[str, Any]:
        if not isinstance(source_frame, int) or source_frame < 0:
            raise ValueError("INVALID_SOURCE_FRAME")
        if self.source_pts_ms is not None and source_frame in self.source_pts_ms:
            timestamp = float(self.source_pts_ms[source_frame])
            source = "SOURCE_PTS"
        else:
            timestamp = self.clip_start_timestamp_ms + (
                (source_frame - self.source_frame_start) * 1000.0 / self.source_fps
            )
            source = "SOURCE_FRAME_RATE_ESTIMATE"
        return {"video_sha256": self.video_sha256, "source_frame": source_frame,
                "source_timestamp_ms": timestamp, "timestamp_ms": timestamp,
                "timestamp_source": source}

    @property
    def source_frame_end_exclusive(self) -> int:
        return self.source_frame_start + round(float(self.clip_duration_ms) * self.source_fps / 1000.0)

    def audit(self) -> dict[str, Any]:
        mapped = [self.map_processing_frame(frame) for frame in range(len(self.processing_pts_ms))]
        times = [row["timestamp_ms"] for row in mapped]
        source_frames = [row["source_frame"] for row in mapped]
        expected_step = 1000.0 / self.processing_fps
        step_errors = [abs((b - a) - expected_step) for a, b in zip(times, times[1:])]
        return {
            "video_sha256": self.video_sha256,
            "source_fps": self.source_fps,
            "processing_fps": self.processing_fps,
            "processing_frames": len(mapped),
            "source_frame_start": source_frames[0],
            "source_frame_end": source_frames[-1],
            "first_timestamp_ms": times[0],
            "last_timestamp_ms": times[-1],
            "timestamps_monotonic": all(b > a for a, b in zip(times, times[1:])),
            "maximum_processing_interval_error_ms": max(step_errors, default=0.0),
            "timestamp_sources": sorted({row["timestamp_source"] for row in mapped}),
            "status": "ALIGNED" if all(b > a for a, b in zip(times, times[1:])) else "MISALIGNED",
        }


@dataclass(frozen=True)
class DatasetSideMapping:
    match_id: str
    dataset_side_to_role: Mapping[str, str]
    source: str
    evidence: str
    review_status: str

    def __post_init__(self):
        if self.review_status not in {"UNREVIEWED", "HUMAN_REVIEWED"}:
            raise ValueError("INVALID_SIDE_MAPPING_REVIEW_STATUS")
        mapping = {str(k).lower(): str(v) for k, v in self.dataset_side_to_role.items()}
        if set(mapping) != {"left", "right"} or set(mapping.values()) != set(ROLES):
            raise ValueError("INVALID_DATASET_SIDE_MAPPING")
        if self.review_status == "HUMAN_REVIEWED" and (not self.source.strip() or not self.evidence.strip()):
            raise ValueError("REVIEWED_SIDE_MAPPING_REQUIRES_EVIDENCE")
        object.__setattr__(self, "dataset_side_to_role", mapping)

    def map_side(self, side: str | None) -> str:
        if self.review_status != "HUMAN_REVIEWED" or side is None:
            return "UNKNOWN"
        return self.dataset_side_to_role.get(str(side).lower(), "UNKNOWN")

    def as_dict(self) -> dict[str, Any]:
        return {"match_id": self.match_id, "dataset_side_to_role": dict(self.dataset_side_to_role),
                "source": self.source, "evidence": self.evidence, "review_status": self.review_status}


@dataclass(frozen=True)
class EvidenceFusionConfig:
    weights: Mapping[str, float]
    candidate_threshold: float
    local_peak_radius_frames: int
    minimum_separation_ms: float
    trajectory_window_ms: float
    side_tie_margin: float = 0.06
    minimum_dynamic_evidence_score: float = 0.15

    def __post_init__(self):
        weights = {str(k): float(v) for k, v in self.weights.items()}
        if not weights or set(weights) - _ALLOWED_WEIGHTS:
            raise ValueError("UNKNOWN_HIT_EVIDENCE_WEIGHT")
        if any(not math.isfinite(value) or value < 0 for value in weights.values()):
            raise ValueError("INVALID_HIT_EVIDENCE_WEIGHT")
        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-6):
            raise ValueError("HIT_EVIDENCE_WEIGHTS_MUST_SUM_TO_ONE")
        if not 0 <= self.candidate_threshold <= 1:
            raise ValueError("INVALID_HIT_CANDIDATE_THRESHOLD")
        if self.local_peak_radius_frames < 1 or self.minimum_separation_ms < 0 or self.trajectory_window_ms <= 0:
            raise ValueError("INVALID_HIT_TEMPORAL_CONFIG")
        if not 0 <= self.minimum_dynamic_evidence_score <= 1:
            raise ValueError("INVALID_MINIMUM_DYNAMIC_EVIDENCE")
        object.__setattr__(self, "weights", weights)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceFusionConfig":
        if value.get("schema_version") != "hit-event-v0.1":
            raise ValueError("UNSUPPORTED_HIT_CONFIG_VERSION")
        return cls(weights=value["weights"], candidate_threshold=float(value["candidate_threshold"]),
                   local_peak_radius_frames=int(value["local_peak_radius_frames"]),
                   minimum_separation_ms=float(value["minimum_separation_ms"]),
                   trajectory_window_ms=float(value["trajectory_window_ms"]),
                   side_tie_margin=float(value.get("side_tie_margin", 0.06)),
                   minimum_dynamic_evidence_score=float(value.get("minimum_dynamic_evidence_score", 0.15)))

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": "hit-event-v0.1", "weights": dict(sorted(self.weights.items())),
                "candidate_threshold": self.candidate_threshold,
                "local_peak_radius_frames": self.local_peak_radius_frames,
                "minimum_separation_ms": self.minimum_separation_ms,
                "trajectory_window_ms": self.trajectory_window_ms,
                "side_tie_margin": self.side_tie_margin,
                "minimum_dynamic_evidence_score": self.minimum_dynamic_evidence_score}


def configuration_sha256(value: Mapping[str, Any] | EvidenceFusionConfig) -> str:
    payload = value.as_dict() if isinstance(value, EvidenceFusionConfig) else dict(value)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _nearest_rows(rows: Sequence[Mapping[str, Any]], timestamp_ms: float,
                  tolerance_ms: float) -> list[dict[str, Any]]:
    if not rows:
        return []
    deltas = [(abs(float(row["timestamp_ms"]) - timestamp_ms), index, row)
              for index, row in enumerate(rows) if row.get("timestamp_ms") is not None]
    if not deltas:
        return []
    minimum = min(item[0] for item in deltas)
    if minimum > tolerance_ms:
        return []
    return [dict(row) for delta, _, row in deltas if abs(delta - minimum) < 1e-7]


def _ball_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    visible = row.get("visible") is True
    return {"visible": visible,
            "x": row.get("pixel_x", row.get("x")) if visible else None,
            "y": row.get("pixel_y", row.get("y")) if visible else None,
            "model_evidence": row.get("confidence", row.get("model_evidence")) if visible else None,
            "source": row.get("model", row.get("source", "RACKETVISION_RAW"))}


def _player_map(rows: Sequence[Mapping[str, Any]], role_key: str) -> dict[str, dict[str, Any]]:
    result = {role: {"track": None, "pose": None} for role in ROLES}
    for row in rows:
        role = row.get(role_key)
        if role not in result:
            continue
        if role_key == "role":
            result[role]["track"] = dict(row)
        else:
            result[role]["pose"] = dict(row)
    return result


def build_frame_evidence(timeline: CanonicalVideoTimeline, ball_rows: Sequence[Mapping[str, Any]],
                         tracking_rows: Sequence[Mapping[str, Any]], pose_rows: Sequence[Mapping[str, Any]], *,
                         source_sha256s: Mapping[str, str], max_join_delta_ms: float = 3.0) -> list[dict[str, Any]]:
    """Join modules by canonical time and source identity, never by local frame ID."""
    mismatched = {name: digest for name, digest in source_sha256s.items()
                   if digest and digest.lower() != timeline.video_sha256.lower()}
    if mismatched:
        raise ValueError("SOURCE_SHA_MISMATCH")
    if max_join_delta_ms < 0:
        raise ValueError("INVALID_ALIGNMENT_TOLERANCE")
    frames = []
    for ball_row in sorted(ball_rows, key=lambda row: int(row["frame"])):
        mapping = timeline.map_processing_frame(int(ball_row["frame"]))
        expected_clip_pts = float(timeline.processing_pts_ms[int(ball_row["frame"])])
        if ball_row.get("timestamp_ms") is not None:
            drift = abs(float(ball_row["timestamp_ms"]) - expected_clip_pts)
            if drift > max_join_delta_ms:
                raise ValueError("BALLTRACK_TIMELINE_ALIGNMENT_FAILED")
        timestamp = float(mapping["timestamp_ms"])
        tracks = []
        for role in ROLES:
            tracks.extend(_nearest_rows([row for row in tracking_rows if row.get("role") == role],
                                        timestamp, max_join_delta_ms))
        poses = []
        for role in ROLES:
            poses.extend(_nearest_rows([row for row in pose_rows if row.get("player_role") == role],
                                       timestamp, max_join_delta_ms))
        players = _player_map(tracks, "role")
        for role, item in _player_map(poses, "player_role").items():
            players[role]["pose"] = item["pose"]
        for player in players.values():
            for module in ("track", "pose"):
                row = player[module]
                if row is not None:
                    row["canonical_alignment_delta_ms"] = float(row["timestamp_ms"]) - timestamp
        ball = _ball_observation(ball_row)
        has_track = any(item["track"] is not None for item in players.values())
        has_good_pose = any(item["pose"] and item["pose"].get("pose_quality") in {"GOOD", "PARTIAL"}
                            for item in players.values())
        evidence_level = ("FULL_EVIDENCE" if ball["visible"] and has_track and has_good_pose else
                          "PARTIAL_EVIDENCE" if ball["visible"] and has_track else
                          "BALL_ONLY" if ball["visible"] else "INSUFFICIENT")
        frames.append({**mapping, "frame": int(ball_row["frame"]),
                       "frame_size": {"width": ball_row.get("width"),
                                                  "height": ball_row.get("height")},
                       "ball": ball, "players": players, "evidence_level": evidence_level})
    return frames


def _box_distance(point: tuple[float, float], bbox: Sequence[float]) -> float:
    x, y = point
    x0, y0, x1, y1 = map(float, bbox)
    return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))


def _valid_ball(frame: Mapping[str, Any]) -> tuple[float, float] | None:
    ball = frame.get("ball") or {}
    if ball.get("visible") is not True or ball.get("x") is None or ball.get("y") is None:
        return None
    return float(ball["x"]), float(ball["y"])


def _track_quality(player: Mapping[str, Any]) -> float | None:
    track = player.get("track")
    if not track:
        return None
    state = track.get("tracking_status", track.get("health", ""))
    if state in {"ACCEPTED", "HEALTHY", "GOOD"}:
        return 1.0
    if state in {"SUSPECT", "REVIEW_REQUIRED"}:
        return 0.35
    return 0.0


def _pose_quality(player: Mapping[str, Any]) -> float | None:
    pose = player.get("pose")
    if not pose:
        return None
    return {"GOOD": 1.0, "PARTIAL": 0.55}.get(str(pose.get("pose_quality")), 0.0)


def _nearest_wrist(player: Mapping[str, Any], point: tuple[float, float]) -> tuple[float, str] | None:
    pose = player.get("pose") or {}
    if pose.get("pose_quality") not in {"GOOD", "PARTIAL"}:
        return None
    keypoints = pose.get("keypoints") or {}
    candidates = []
    for name in ("left_wrist", "right_wrist"):
        joint = keypoints.get(name)
        if not joint or float(joint.get("score", 0.0)) < 0.35:
            continue
        x = joint.get("x_global", joint.get("x"))
        y = joint.get("y_global", joint.get("y"))
        if x is None or y is None:
            continue
        candidates.append((math.hypot(float(x) - point[0], float(y) - point[1]), name))
    return min(candidates) if candidates else None


def _track_bbox(player: Mapping[str, Any]) -> Sequence[float] | None:
    track = player.get("track") or {}
    bbox = track.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    return bbox


def _trajectory_features(frames: Sequence[Mapping[str, Any]], index: int,
                         window_ms: float) -> tuple[float | None, float | None]:
    current = _valid_ball(frames[index])
    if current is None:
        return None, None
    now = float(frames[index]["timestamp_ms"])
    before_candidates = [(now - float(frame["timestamp_ms"]), _valid_ball(frame), frame)
                         for frame in frames[:index]
                         if 0 < now - float(frame["timestamp_ms"]) <= max(window_ms * 2.5, 80)]
    after_candidates = [(float(frame["timestamp_ms"]) - now, _valid_ball(frame), frame)
                        for frame in frames[index + 1:]
                        if 0 < float(frame["timestamp_ms"]) - now <= max(window_ms * 2.5, 80)]
    before = min((row for row in before_candidates if row[1] is not None), default=None, key=lambda row: row[0])
    after = min((row for row in after_candidates if row[1] is not None), default=None, key=lambda row: row[0])
    if before is None or after is None:
        return None, None
    p0, p1 = before[1], current
    p2 = after[1]
    t0, t1, t2 = float(before[2]["timestamp_ms"]), now, float(after[2]["timestamp_ms"])
    v1 = ((p1[0] - p0[0]) / max(1e-6, t1 - t0), (p1[1] - p0[1]) / max(1e-6, t1 - t0))
    v2 = ((p2[0] - p1[0]) / max(1e-6, t2 - t1), (p2[1] - p1[1]) / max(1e-6, t2 - t1))
    mag1, mag2 = math.hypot(*v1), math.hypot(*v2)
    if mag1 <= 1e-8 or mag2 <= 1e-8:
        return None, None
    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)))
    angle = math.degrees(math.acos(cosine))
    direction_change = min(1.0, max(0.0, (angle - 35.0) / 125.0))
    speed_change = abs(mag2 - mag1) / max(mag1, mag2)
    return direction_change, min(1.0, speed_change)


def _wrist_speed_peak(frames: Sequence[Mapping[str, Any]], index: int,
                      role: str, window_ms: float) -> float | None:
    player = frames[index]["players"].get(role) or {}
    bbox = _track_bbox(player)
    scale = max(1.0, float(bbox[3]) - float(bbox[1])) if bbox else 200.0
    max_gap_ms = max(window_ms * 2.5, 80)
    scores = []
    for name in ("left_wrist", "right_wrist"):
        samples = []
        for row_index in range(max(0, index - 2), min(len(frames), index + 3)):
            row = frames[row_index]
            pose = ((row.get("players", {}).get(role) or {}).get("pose") or {})
            joint = (pose.get("keypoints") or {}).get(name)
            if pose.get("pose_quality") not in {"GOOD", "PARTIAL"} or not joint or float(joint.get("score", 0.0)) < 0.35:
                continue
            x = joint.get("x_global", joint.get("x")); y = joint.get("y_global", joint.get("y"))
            if x is None or y is None:
                continue
            samples.append((row_index, float(row["timestamp_ms"]), float(x), float(y)))
        segments = []
        for left, right in zip(samples, samples[1:]):
            delta_ms = right[1] - left[1]
            if delta_ms <= 0 or delta_ms > max_gap_ms:
                continue
            speed = math.hypot(right[2] - left[2], right[3] - left[3]) * 1000.0 / delta_ms
            midpoint = (left[0] + right[0]) / 2
            segments.append((midpoint, speed))
        center = [speed for midpoint, speed in segments if abs(midpoint - index) <= 0.75]
        neighbors = [speed for midpoint, speed in segments if 0.75 < abs(midpoint - index) <= 2.0]
        if not center:
            continue
        center_speed = max(center)
        absolute = min(1.0, center_speed / (3.0 * scale))
        if neighbors:
            relative = min(1.0, max(0.0,
                            (center_speed / max(max(neighbors), 1.0) - 1.0) / 1.5))
        else:
            relative = absolute
        scores.append(0.5 * absolute + 0.5 * relative)
    return max(scores) if scores else None


class HitCandidateEngine:
    """Small, explainable rule-based candidate generator; score is not probability."""

    def __init__(self, config: EvidenceFusionConfig):
        self.config = config

    def _player_score(self, frames: Sequence[Mapping[str, Any]], index: int, role: str) -> dict[str, Any] | None:
        frame = frames[index]
        point = _valid_ball(frame)
        player = frame.get("players", {}).get(role) or {}
        bbox = _track_bbox(player)
        track = _track_quality(player)
        if point is None or bbox is None or track is None or track <= 0:
            return None
        height = max(1.0, float(bbox[3]) - float(bbox[1]))
        bbox_distance = _box_distance(point, bbox)
        player_proximity = max(0.0, min(1.0, 1.0 - bbox_distance / (0.55 * height)))
        wrist = _nearest_wrist(player, point)
        wrist_proximity = (max(0.0, min(1.0, 1.0 - wrist[0] / (0.38 * height))) if wrist else None)
        direction, speed_change = _trajectory_features(frames, index, self.config.trajectory_window_ms)
        wrist_speed = _wrist_speed_peak(frames, index, role, self.config.trajectory_window_ms)
        pose_quality = _pose_quality(player)
        dynamic_score = max((value for value in (direction, speed_change, wrist_speed) if value is not None),
                            default=0.0)
        if dynamic_score < self.config.minimum_dynamic_evidence_score:
            return None
        raw = {
            "ball_player_proximity": player_proximity,
            "wrist_proximity_proxy": wrist_proximity,
            "trajectory_direction_change": direction,
            "ball_speed_change": speed_change,
            "wrist_speed_peak": wrist_speed,
            "pose_quality": pose_quality,
            "track_health": track,
        }
        available = {key: value for key, value in raw.items() if key in self.config.weights and value is not None}
        denominator = sum(self.config.weights[key] for key in available)
        if denominator <= 0:
            return None
        score = sum(self.config.weights[key] * float(value) for key, value in available.items()) / denominator
        components = {key: {"value": round(float(value), 4),
                            "weight": self.config.weights[key],
                            "evidence": "racket-side proxy" if key == "wrist_proximity_proxy" else key}
                     for key, value in available.items()}
        if wrist:
            components["wrist_proximity_proxy"]["nearest_joint"] = wrist[1]
            components["wrist_proximity_proxy"]["distance_px"] = round(wrist[0], 3)
        components["ball_player_proximity"]["bbox_distance_px"] = round(bbox_distance, 3)
        return {"candidate_player": role, "score": score, "components": components,
                "evidence_level": frame.get("evidence_level", "INSUFFICIENT")}

    def suggest(self, frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if any(float(right["timestamp_ms"]) <= float(left["timestamp_ms"])
               for left, right in zip(frames, frames[1:])):
            raise ValueError("FRAME_EVIDENCE_TIMELINE_NOT_MONOTONIC")
        if len({row.get("video_sha256") for row in frames if row.get("video_sha256")}) > 1:
            raise ValueError("FRAME_EVIDENCE_SOURCE_MISMATCH")
        scored: list[dict[str, Any]] = []
        for index, frame in enumerate(frames):
            options = [row for role in ROLES if (row := self._player_score(frames, index, role))]
            if not options:
                continue
            options.sort(key=lambda row: row["score"], reverse=True)
            top = options[0]
            if top["score"] < self.config.candidate_threshold:
                continue
            if (len(options) > 1 and top["score"] - options[1]["score"] < self.config.side_tie_margin):
                player = "UNKNOWN"
                components = {"NEAR_PLAYER": top["components"], "FAR_PLAYER": options[1]["components"]}
            else:
                player = top["candidate_player"]
                components = top["components"]
            scored.append({"index": index, "player": player, "score": top["score"],
                           "components": components, "evidence_level": top["evidence_level"]})
        candidates = []
        radius = self.config.local_peak_radius_frames
        for item in scored:
            neighbors = [row for row in scored if abs(row["index"] - item["index"]) <= radius]
            if item["score"] + 1e-9 < max(row["score"] for row in neighbors):
                continue
            frame = frames[item["index"]]
            digest = hashlib.sha256(
                f"{frame.get('video_sha256','')}:{float(frame['timestamp_ms']):.3f}:{item['player']}".encode()
            ).hexdigest()[:24]
            sources = ["RACKETVISION_RAW", "PLAYER_TRACKING"]
            if any(key in item["components"] for key in ("wrist_proximity_proxy", "wrist_speed_peak")):
                sources.append("RTMPOSE")
            candidates.append({
                "event_id": digest,
                "event_type": "HIT",
                "status": "SUGGESTED",
                "frame": int(frame["processing_frame"]),
                "timestamp_ms": float(frame["timestamp_ms"]),
                "source_frame": frame.get("source_frame"),
                "processing_frame": frame.get("processing_frame"),
                "processing_fps": frame.get("processing_fps"),
                "candidate_player": item["player"],
                "evidence_score": round(item["score"], 5),
                "confidence": None,
                "evidence_level": item["evidence_level"],
                "evidence_components": item["components"],
                "source_modules": sources,
            })
        kept = []
        for candidate in sorted(candidates, key=lambda row: (-row["evidence_score"], row["timestamp_ms"])):
            if all(abs(candidate["timestamp_ms"] - row["timestamp_ms"]) >= self.config.minimum_separation_ms
                   for row in kept):
                kept.append(candidate)
        result = sorted(kept, key=lambda row: row["timestamp_ms"])
        previous_timestamp = None
        for sequence_index, event in enumerate(result, start=1):
            event["sequence_index"] = sequence_index
            event["interval_from_previous_ms"] = (
                None if previous_timestamp is None else round(event["timestamp_ms"] - previous_timestamp, 3)
            )
            event["sequence_review_required"] = event["candidate_player"] == "UNKNOWN"
            previous_timestamp = event["timestamp_ms"]
        return result


def adapt_training_strokes(annotations: Mapping[str, Any], timeline: CanonicalVideoTimeline,
                           *, fps: float, side_mapping: DatasetSideMapping | None = None) -> list[dict[str, Any]]:
    """Adapt only native stroke labels, preserving labels and explicit time provenance."""
    from backend.extended_openttgames import ExtendedOpenTTGamesAdapter
    parsed = ExtendedOpenTTGamesAdapter(fps=fps).parse(dict(annotations))
    events = []
    first = timeline.source_frame_start
    for event in parsed:
        if event["event_type"] != "STROKE":
            continue
        frame = int(event["frame"])
        if not first <= frame < timeline.source_frame_end_exclusive:
            continue
        mapped = timeline.map_source_frame(frame)
        role = side_mapping.map_side(event.get("player_side")) if side_mapping else "UNKNOWN"
        events.append({"event_id": event["event_id"], "event_type": "STROKE_GROUND_TRUTH",
                       "timestamp_ms": mapped["timestamp_ms"], "source_frame": frame,
                       "source_timestamp_source": mapped["timestamp_source"],
                       "player_side": event.get("player_side"), "player_role": role,
                       "hand": event.get("hand"), "technique": event.get("technique"),
                       "native_label": event.get("native_label"), "source": event.get("source"),
                       "ground_truth": True})
    return events


def _one_to_one_matches(predicted: Sequence[Mapping[str, Any]], truth: Sequence[Mapping[str, Any]],
                        tolerance_ms: float,
                        timestamp_rounding_epsilon_ms: float = 0.001) -> list[tuple[int, int, float]]:
    ordered_pred = sorted(enumerate(predicted), key=lambda row: (float(row[1]["timestamp_ms"]), row[0]))
    ordered_truth = sorted(enumerate(truth), key=lambda row: (float(row[1]["timestamp_ms"]), row[0]))
    # Dynamic programming first maximizes match count, then minimizes absolute
    # timing error. This avoids order-greedy mistakes when tolerance windows overlap.
    rows, columns = len(ordered_pred), len(ordered_truth)
    best: list[list[tuple[int, float, tuple[tuple[int, int, float], ...]]]] = [
        [(0, 0.0, ()) for _ in range(columns + 1)] for _ in range(rows + 1)
    ]
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            options = [best[i - 1][j], best[i][j - 1]]
            pi, pred = ordered_pred[i - 1]
            gi, target = ordered_truth[j - 1]
            delta = float(pred["timestamp_ms"]) - float(target["timestamp_ms"])
            if abs(delta) <= tolerance_ms + timestamp_rounding_epsilon_ms:
                count, cost, pairs = best[i - 1][j - 1]
                options.append((count + 1, cost + abs(delta), pairs + ((pi, gi, delta),)))
            best[i][j] = min(options, key=lambda item: (-item[0], item[1]))
    return list(best[rows][columns][2])


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    low = math.floor(index); high = math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def evaluate_hit_events(predicted: Sequence[Mapping[str, Any]], truth: Sequence[Mapping[str, Any]], *,
                        tolerances_ms: Mapping[str, float],
                        side_mapping: DatasetSideMapping | None = None,
                        timestamp_rounding_epsilon_ms: float = 0.001) -> dict[str, Any]:
    if not math.isfinite(timestamp_rounding_epsilon_ms) or timestamp_rounding_epsilon_ms < 0:
        raise ValueError("INVALID_TIMESTAMP_ROUNDING_EPSILON")
    result = {}
    for label, tolerance in tolerances_ms.items():
        matches = _one_to_one_matches(predicted, truth, float(tolerance),
                                      timestamp_rounding_epsilon_ms)
        fp, fn = len(predicted) - len(matches), len(truth) - len(matches)
        precision = len(matches) / len(predicted) if predicted else (1.0 if not truth else 0.0)
        recall = len(matches) / len(truth) if truth else (1.0 if not predicted else 0.0)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        errors = [abs(delta) for _, _, delta in matches]
        side_rows = []
        side_results_by_pair = {}
        for pi, gi, _ in matches:
            native_side = truth[gi].get("player_side")
            predicted_role = predicted[pi].get("candidate_player")
            mapped_role = truth[gi].get("player_role")
            if mapped_role in ROLES and predicted_role in ROLES:
                correct = predicted_role == mapped_role
                side_rows.append(correct)
                side_results_by_pair[(pi, gi)] = correct
            elif side_mapping and native_side and predicted_role in ROLES:
                expected_role = side_mapping.map_side(str(native_side))
                if expected_role in ROLES:
                    correct = predicted_role == expected_role
                    side_rows.append(correct)
                    side_results_by_pair[(pi, gi)] = correct
        result[label] = {
            "tolerance_ms": float(tolerance), "predicted": len(predicted), "ground_truth": len(truth),
            "timestamp_rounding_epsilon_ms": timestamp_rounding_epsilon_ms,
            "matched": len(matches), "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall, "f1": f1,
            "median_absolute_timing_error_ms": _percentile(errors, 0.5),
            "p90_absolute_timing_error_ms": _percentile(errors, 0.9),
            "player_side_accuracy": sum(side_rows) / len(side_rows) if side_rows else None,
            "player_side_evaluable_matches": len(side_rows),
            "matches": [{"prediction_index": pi, "ground_truth_index": gi,
                         "signed_timing_error_ms": delta,
                         "player_side_correct": side_results_by_pair.get((pi, gi))}
                        for pi, gi, delta in matches],
            "unmatched_prediction_ids": [str(predicted[index].get("event_id", index))
                                          for index in range(len(predicted))
                                          if index not in {pi for pi, _, _ in matches}],
            "unmatched_ground_truth_ids": [str(truth[index].get("event_id", index))
                                           for index in range(len(truth))
                                           if index not in {gi for _, gi, _ in matches}],
        }
    return {"by_tolerance": result}


def aggregate_hit_evaluations(evaluations: Sequence[tuple[str, Mapping[str, Any]]]) -> dict[str, Any]:
    """Aggregate clip-level metrics without ever matching events across videos."""
    if not evaluations:
        return {"by_tolerance": {}}
    labels = tuple(evaluations[0][1].get("by_tolerance", {}).keys())
    aggregate = {}
    for label in labels:
        rows = [(clip_id, value.get("by_tolerance", {}).get(label, {}))
                for clip_id, value in evaluations]
        predicted = sum(int(row.get("predicted", 0)) for _, row in rows)
        ground_truth = sum(int(row.get("ground_truth", 0)) for _, row in rows)
        matched = sum(int(row.get("matched", 0)) for _, row in rows)
        false_positives = sum(int(row.get("false_positives", 0)) for _, row in rows)
        false_negatives = sum(int(row.get("false_negatives", 0)) for _, row in rows)
        precision = matched / predicted if predicted else (1.0 if not ground_truth else 0.0)
        recall = matched / ground_truth if ground_truth else (1.0 if not predicted else 0.0)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        timing_errors = []
        side_results = []
        matches = []
        unmatched_predictions = []
        unmatched_truth = []
        for clip_id, row in rows:
            unmatched_predictions.extend(f"{clip_id}:{event_id}"
                                         for event_id in row.get("unmatched_prediction_ids", []))
            unmatched_truth.extend(f"{clip_id}:{event_id}"
                                   for event_id in row.get("unmatched_ground_truth_ids", []))
            for item in row.get("matches", []):
                timing_errors.append(abs(float(item["signed_timing_error_ms"])))
                if item.get("player_side_correct") is not None:
                    side_results.append(bool(item["player_side_correct"]))
                matches.append({"clip_id": clip_id, **item})
        aggregate[label] = {
            "tolerance_ms": float(rows[0][1].get("tolerance_ms", 0.0)),
            "predicted": predicted, "ground_truth": ground_truth, "matched": matched,
            "false_positives": false_positives, "false_negatives": false_negatives,
            "precision": precision, "recall": recall, "f1": f1,
            "median_absolute_timing_error_ms": _percentile(timing_errors, .5),
            "p90_absolute_timing_error_ms": _percentile(timing_errors, .9),
            "player_side_accuracy": sum(side_results) / len(side_results) if side_results else None,
            "player_side_evaluable_matches": len(side_results), "matches": matches,
            "unmatched_prediction_ids": unmatched_predictions,
            "unmatched_ground_truth_ids": unmatched_truth,
        }
    return {"by_tolerance": aggregate}


def record_review_correction(path: str | Path, *, video_sha256: str, action: str,
                             event_id: str, timestamp_ms: float, player: str) -> dict[str, Any]:
    if action not in {"CONFIRM", "REJECT", "ADJUST", "ADD"}:
        raise ValueError("INVALID_REVIEW_ACTION")
    if len(video_sha256) != 64 or player not in {*ROLES, "UNKNOWN"}:
        raise ValueError("INVALID_REVIEW_CORRECTION")
    if not event_id or not math.isfinite(float(timestamp_ms)) or timestamp_ms < 0:
        raise ValueError("INVALID_REVIEW_CORRECTION")
    row = {"review_id": hashlib.sha256(
               f"{video_sha256}:{event_id}:{action}:{timestamp_ms}:{datetime.now(timezone.utc).isoformat()}".encode()
           ).hexdigest()[:24],
           "video_sha256": video_sha256, "event_id": event_id, "action": action,
           "timestamp_ms": float(timestamp_ms), "player": player, "source": "USER_CORRECTION",
           "created_at": datetime.now(timezone.utc).isoformat()}
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush(); os.fsync(stream.fileno())
    return row


def load_review_corrections(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        return []
    rows = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if value.get("source") != "USER_CORRECTION":
                raise ValueError("INVALID_REVIEW_CORRECTION_LOG")
            rows.append(value)
    return rows
