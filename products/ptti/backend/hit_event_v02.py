"""Evidence-first temporal decoding for Hit Event v0.2 experiments.

This layer is intentionally separate from the frozen v0.1 engine. RAW
BallTrack observations and generated candidates are never overwritten. Pose can
only rerank an existing ball-derived candidate and is disabled by default.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


ROLES = {"NEAR_PLAYER", "FAR_PLAYER"}


@dataclass(frozen=True)
class HitEventV02Config:
    schema_version: str
    status: str
    minimum_kinematic_score: float
    max_ball_gap_ms: float
    max_normalized_ball_speed_per_second: float
    minimum_pre_post_observations: int
    cluster_window_ms: float
    interval_floor_ms: float
    sequence_break_ms: float
    decoder_selection_floor: float
    same_side_penalty: float
    alternation_reward: float
    short_interval_penalty: float
    pose_for_hit: bool = False
    pose_rerank_max_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.schema_version != "hit-event-v0.2":
            raise ValueError("UNSUPPORTED_HIT_EVENT_V02_CONFIG")
        if self.status not in {"DRAFT_DEV_ONLY", "CALIBRATED_LOCKED"}:
            raise ValueError("INVALID_HIT_EVENT_V02_CONFIG_STATUS")
        for name in ("minimum_kinematic_score", "decoder_selection_floor"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError("HIT_EVENT_SCORE_THRESHOLD_OUT_OF_RANGE")
        for name in ("max_ball_gap_ms", "max_normalized_ball_speed_per_second",
                     "cluster_window_ms", "interval_floor_ms", "sequence_break_ms"):
            if getattr(self, name) < 0:
                raise ValueError("HIT_EVENT_TIME_OR_SPEED_PARAMETER_INVALID")
        if self.minimum_pre_post_observations < 1:
            raise ValueError("HIT_EVENT_PRE_POST_COUNT_MUST_BE_POSITIVE")
        if any(not 0 <= getattr(self, name) <= 1 for name in
               ("same_side_penalty", "alternation_reward", "short_interval_penalty",
                "pose_rerank_max_delta")):
            raise ValueError("HIT_EVENT_DECODER_WEIGHT_OUT_OF_RANGE")
        if self.pose_for_hit and self.pose_rerank_max_delta <= 0:
            raise ValueError("POSE_RERANK_REQUIRES_BOUNDED_POSITIVE_WEIGHT")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HitEventV02Config":
        return cls(**dict(value))

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def config_sha256(config: HitEventV02Config | Mapping[str, Any]) -> str:
    value = config.as_dict() if isinstance(config, HitEventV02Config) else dict(config)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _point(row: Mapping[str, Any] | None) -> tuple[float, float] | None:
    ball = (row or {}).get("ball") or {}
    if ball.get("visible") is not True or ball.get("x") is None or ball.get("y") is None:
        return None
    return float(ball["x"]), float(ball["y"])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _percentile(values: Sequence[float], p: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


@dataclass(frozen=True)
class StrokeIntervalPrior:
    sample_count: int
    minimum_ms: float
    p1_ms: float
    p5_ms: float
    median_ms: float
    p95_ms: float
    source_split: str = "TRAIN_DEV_ONLY"

    @classmethod
    def from_development_intervals(cls, intervals_ms: Sequence[float]) -> "StrokeIntervalPrior":
        if len(intervals_ms) < 2:
            raise ValueError("INSUFFICIENT_DEV_INTERVALS")
        values = [float(value) for value in intervals_ms]
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("INVALID_DEV_STROKE_INTERVAL")
        return cls(sample_count=len(values), minimum_ms=min(values),
                   p1_ms=float(_percentile(values, .01)), p5_ms=float(_percentile(values, .05)),
                   median_ms=float(_percentile(values, .5)), p95_ms=float(_percentile(values, .95)))

    def as_dict(self) -> dict[str, Any]:
        return {"sample_count": self.sample_count, "minimum_ms": self.minimum_ms,
                "p1_ms": self.p1_ms, "p5_ms": self.p5_ms, "median_ms": self.median_ms,
                "p95_ms": self.p95_ms, "source_split": self.source_split}


def _role_at(frame: Mapping[str, Any], point: tuple[float, float]) -> tuple[str, float, str]:
    options = []
    players = frame.get("players") or {}
    width = max(1.0, float((frame.get("frame_size") or {}).get("width") or 1920))
    height = max(1.0, float((frame.get("frame_size") or {}).get("height") or 1080))
    diagonal = math.hypot(width, height)
    for role in ("NEAR_PLAYER", "FAR_PLAYER"):
        player = players.get(role) or {}
        track = player.get("track") or {}
        bbox = track.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = map(float, bbox)
        dx = max(x0 - point[0], 0.0, point[0] - x1)
        dy = max(y0 - point[1], 0.0, point[1] - y1)
        scale = max(diagonal * .08, math.hypot(x1 - x0, y1 - y0))
        proximity = max(0.0, min(1.0, 1.0 - math.hypot(dx, dy) / scale))
        state = str(track.get("tracking_status", track.get("health", "UNKNOWN")))
        identity = "CONFIDENT" if state in {"ACCEPTED", "HEALTHY", "GOOD"} else "UNCERTAIN"
        options.append((role, proximity, identity))
    if not options:
        return "UNKNOWN", 0.0, "UNCERTAIN"
    options.sort(key=lambda row: row[1], reverse=True)
    if len(options) > 1 and options[0][1] - options[1][1] < .12:
        return "UNKNOWN", options[0][1], "UNCERTAIN"
    return options[0]


class RawHitCandidateGenerator:
    """Generate high-recall ball-kinematic candidates without Pose creation."""

    def __init__(self, config: HitEventV02Config):
        self.config = config

    def generate(self, frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if any(float(b["timestamp_ms"]) <= float(a["timestamp_ms"])
               for a, b in zip(frames, frames[1:])):
            raise ValueError("FRAME_EVIDENCE_TIMELINE_NOT_MONOTONIC")
        if len({row.get("video_sha256") for row in frames if row.get("video_sha256")}) > 1:
            raise ValueError("FRAME_EVIDENCE_SOURCE_MISMATCH")
        visible = []
        for index, frame in enumerate(frames):
            point = _point(frame)
            if point is not None:
                visible.append((index, point))
        output = []
        needed = self.config.minimum_pre_post_observations
        for visible_index in range(needed, len(visible) - needed):
            frame_index, point = visible[visible_index]
            frame = frames[frame_index]
            timestamp = float(frame["timestamp_ms"])
            before = visible[visible_index-needed:visible_index]
            after = visible[visible_index+1:visible_index+1+needed]
            pre_gap = timestamp - float(frames[before[-1][0]]["timestamp_ms"])
            post_gap = float(frames[after[0][0]]["timestamp_ms"]) - timestamp
            neighbor_gaps = [float(frames[b[0]]["timestamp_ms"]) - float(frames[a[0]]["timestamp_ms"])
                             for a, b in zip(before, before[1:])]
            neighbor_gaps += [float(frames[b[0]]["timestamp_ms"]) - float(frames[a[0]]["timestamp_ms"])
                              for a, b in zip(after, after[1:])]
            if max([pre_gap, post_gap, *neighbor_gaps], default=0.0) > self.config.max_ball_gap_ms:
                continue
            width = max(1.0, float((frame.get("frame_size") or {}).get("width") or 1920))
            height = max(1.0, float((frame.get("frame_size") or {}).get("height") or 1080))
            diagonal = math.hypot(width, height)
            prev_pair = before[-2:]
            next_pair = after[:2]
            pre_dt = (float(frames[prev_pair[1][0]]["timestamp_ms"]) -
                      float(frames[prev_pair[0][0]]["timestamp_ms"])) / 1000.0
            post_dt = (float(frames[next_pair[1][0]]["timestamp_ms"]) -
                       float(frames[next_pair[0][0]]["timestamp_ms"])) / 1000.0
            if pre_dt <= 0 or post_dt <= 0:
                continue
            v_pre = ((prev_pair[1][1][0] - prev_pair[0][1][0]) / pre_dt,
                     (prev_pair[1][1][1] - prev_pair[0][1][1]) / pre_dt)
            v_post = ((next_pair[1][1][0] - next_pair[0][1][0]) / post_dt,
                      (next_pair[1][1][1] - next_pair[0][1][1]) / post_dt)
            speed_pre, speed_post = math.hypot(*v_pre), math.hypot(*v_post)
            if speed_pre <= 1e-6 or speed_post <= 1e-6:
                continue
            cosine = max(-1.0, min(1.0, (v_pre[0] * v_post[0] + v_pre[1] * v_post[1]) /
                                  (speed_pre * speed_post)))
            angle = math.degrees(math.acos(cosine))
            direction_score = min(1.0, angle / 180.0)
            speed_change = abs(speed_post - speed_pre) / max(speed_pre, speed_post)
            kinematic_score = .65 * direction_score + .35 * speed_change
            if kinematic_score < self.config.minimum_kinematic_score:
                continue
            norm_pre, norm_post = speed_pre / diagonal, speed_post / diagonal
            jump = max(norm_pre, norm_post) > self.config.max_normalized_ball_speed_per_second
            role, proximity, identity = _role_at(frame, point)
            raw_probability = (frame.get("ball") or {}).get("model_evidence")
            event_id = hashlib.sha256(
                f"{frame.get('video_sha256','')}:{timestamp:.3f}:RAW_KINEMATIC".encode()
            ).hexdigest()[:24]
            output.append({
                "event_id": event_id, "event_type": "HIT_CANDIDATE", "status": "RAW_CANDIDATE",
                "timestamp_ms": timestamp, "source_frame": frame.get("source_frame"),
                "processing_frame": frame.get("processing_frame", frame.get("frame")),
                "candidate_player": role, "identity_status": identity,
                "evidence_score": round(kinematic_score, 6), "confidence": None,
                "pose_used_for_generation": False,
                "ball_quality": "JUMP_SUSPECT" if jump else "SUPPORTED",
                "filter_reason": "BALLTRACK_JUMP" if jump else None,
                "evidence_components": {
                    "trajectory_direction_change_degrees": round(angle, 4),
                    "trajectory_direction_change_score": round(direction_score, 6),
                    "ball_speed_change_ratio": round(speed_change, 6),
                    "incoming_normalized_diagonals_per_second": round(norm_pre, 6),
                    "outgoing_normalized_diagonals_per_second": round(norm_post, 6),
                    "ball_player_proximity": round(proximity, 6),
                    "model_probability": raw_probability,
                    "pre_ball_observations": len(before), "post_ball_observations": len(after),
                    "pre_post_max_gap_ms": max([pre_gap, post_gap, *neighbor_gaps], default=0.0),
                },
                "source_modules": ["RACKETVISION_RAW", "PLAYER_TRACKING"],
            })
        return output


class TemporalCandidateClusterer:
    # Candidate timestamps are serialized to 0.001 ms. This tolerance only
    # absorbs that serialization rounding at an inclusive window boundary.
    TIMESTAMP_ROUNDING_EPSILON_MS = 0.001

    def __init__(self, window_ms: float):
        if window_ms < 0:
            raise ValueError("CLUSTER_WINDOW_MUST_BE_NONNEGATIVE")
        self.window_ms = float(window_ms)

    def cluster(self, candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        rows = sorted((dict(row) for row in candidates), key=lambda row: float(row["timestamp_ms"]))
        groups: list[list[dict[str, Any]]] = []
        for row in rows:
            # Anchor the window to its first member so a chain of individually
            # close peaks cannot collapse multiple contacts into one cluster.
            if (not groups or
                    float(row["timestamp_ms"]) - float(groups[-1][0]["timestamp_ms"]) >
                    self.window_ms + self.TIMESTAMP_ROUNDING_EPSILON_MS):
                groups.append([row])
            else:
                groups[-1].append(row)
        kept, removed = [], []
        for index, group in enumerate(groups, start=1):
            best = max(group, key=lambda row: (float(row.get("evidence_score", 0.0)),
                                                -float(row["timestamp_ms"])))
            selected = dict(best)
            selected["cluster_id"] = f"cluster-{index:06d}"
            selected["cluster_member_count"] = len(group)
            selected["cluster_members"] = [row["event_id"] for row in group]
            kept.append(selected)
            for row in group:
                if row["event_id"] != best["event_id"]:
                    removed.append({**row, "decision": "SUPPRESSED_DUPLICATE_CLUSTER",
                                    "selected_event_id": best["event_id"]})
        return {"kept": kept, "suppressed": removed,
                "raw_count": len(rows), "cluster_count": len(groups),
                "suppressed_count": len(removed), "cluster_window_ms": self.window_ms}


class HitSequenceDecoder:
    """Soft sequence decoder with role alternation only when identity is known."""

    def __init__(self, config: HitEventV02Config, interval_prior: StrokeIntervalPrior):
        self.config = config
        self.interval_prior = interval_prior
        self.interval_floor_ms = (config.interval_floor_ms if config.interval_floor_ms > 0
                                  else interval_prior.p1_ms)

    def _transition(self, prior: Mapping[str, Any], current: Mapping[str, Any],
                    delta_ms: float) -> tuple[float, str, list[str]]:
        transition = 0.0
        reason = "SEQUENCE_CONTINUITY"
        adjustments: list[str] = []
        if delta_ms < self.interval_floor_ms:
            transition -= self.config.short_interval_penalty
            reason = "SHORT_INTER_STROKE_INTERVAL"
            adjustments.append("INTERVAL_PENALTY")
        prior_role = prior.get("candidate_player", "UNKNOWN")
        current_role = current.get("candidate_player", "UNKNOWN")
        identities_confident = (prior.get("identity_status", "UNCERTAIN") ==
                                current.get("identity_status", "UNCERTAIN") == "CONFIDENT")
        if prior_role in ROLES and current_role in ROLES and identities_confident:
            if prior_role == current_role:
                transition -= self.config.same_side_penalty
                reason = "SAME_PLAYER_SEQUENCE_CONFLICT"
                adjustments.append("ALTERNATION_CONFLICT")
            else:
                transition += self.config.alternation_reward
                reason = "ALTERNATING_PLAYER_SEQUENCE"
        return transition, reason, adjustments

    def decode(self, candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        rows = sorted((dict(row) for row in candidates), key=lambda row: float(row["timestamp_ms"]))
        accepted: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        review_candidates: list[dict[str, Any]] = []
        eligible: list[dict[str, Any]] = []
        for row in rows:
            if row.get("ball_quality") == "JUMP_SUSPECT" or row.get("filter_reason") == "BALLTRACK_JUMP":
                removed.append({**row, "decision": "BALLTRACK_QUALITY",
                                "rejection_reasons": ["BALLTRACK_QUALITY"],
                                "decoder_trace": {"ball_quality": row.get("ball_quality"),
                                                  "filter_reason": row.get("filter_reason")}})
            else:
                eligible.append(row)
        # Decode independent temporal blocks; a long gap resets the alternation
        # state. These block boundaries are provisional until DEV calibration.
        blocks: list[list[dict[str, Any]]] = []
        for row in eligible:
            if not blocks or float(row["timestamp_ms"]) - float(blocks[-1][-1]["timestamp_ms"]) > self.config.sequence_break_ms:
                blocks.append([row])
            else:
                blocks[-1].append(row)
        for block in blocks:
            n = len(block)
            node_utility = [float(row.get("evidence_score", 0.0)) -
                            self.config.decoder_selection_floor for row in block]
            best_score = list(node_utility)
            previous = [-1] * n
            edge_reason: list[str | None] = [None] * n
            edge_adjustments: list[list[str]] = [[] for _ in range(n)]
            for j in range(n):
                for i in range(j):
                    delta = float(block[j]["timestamp_ms"]) - float(block[i]["timestamp_ms"])
                    transition, reason, adjustments = self._transition(block[i], block[j], delta)
                    score = best_score[i] + node_utility[j] + transition
                    if score > best_score[j]:
                        best_score[j], previous[j], edge_reason[j] = score, i, reason
                        edge_adjustments[j] = adjustments

            # Best suffix scores let the report measure the best complete path
            # that could include each suppressed candidate, rather than guess
            # a rejection reason from the candidate's raw score alone.
            suffix_score = list(node_utility)
            for i in range(n - 1, -1, -1):
                for j in range(i + 1, n):
                    delta = float(block[j]["timestamp_ms"]) - float(block[i]["timestamp_ms"])
                    transition, _, _ = self._transition(block[i], block[j], delta)
                    score = node_utility[i] + transition + suffix_score[j]
                    if score > suffix_score[i]:
                        suffix_score[i] = score
            # A block's best path provides the selected sequence. Other
            # candidates remain explainable and borderline alternatives enter
            # a separate review queue; they are not promoted to automatic hits.
            end = max(range(n), key=lambda index: best_score[index])
            path = set()
            cursor = end
            while cursor >= 0:
                path.add(cursor)
                cursor = previous[cursor]
            global_best_score = best_score[end]
            selected_event_ids = [block[index]["event_id"] for index in sorted(path)
                                  if best_score[index] >= 0]
            for index, row in enumerate(block):
                through_score = best_score[index] + suffix_score[index] - node_utility[index]
                regret = max(0.0, global_best_score - through_score)
                trace = {
                    "candidate_utility": round(node_utility[index], 6),
                    "best_prefix_utility": round(best_score[index], 6),
                    "best_suffix_utility": round(suffix_score[index], 6),
                    "best_path_utility_through_candidate": round(through_score, 6),
                    "best_block_path_utility": round(global_best_score, 6),
                    "regret_to_best_block_path": round(regret, 6),
                    "best_predecessor_event_id": (block[previous[index]]["event_id"]
                                                   if previous[index] >= 0 else None),
                    "best_predecessor_transition": edge_reason[index],
                    "transition_adjustments": list(edge_adjustments[index]),
                    "selected_block_sequence_event_ids": selected_event_ids,
                }
                if index in path and best_score[index] >= 0:
                    selected = dict(row)
                    selected["decoder_reason"] = edge_reason[index] or "RAW_EVIDENCE_SELECTED"
                    selected["decoder_trace"] = trace
                    selected["sequence_review_required"] = (
                        selected.get("candidate_player") not in ROLES or
                        selected.get("identity_status") != "CONFIDENT")
                    accepted.append(selected)
                else:
                    evidence_below_floor = node_utility[index] < 0
                    rejection_reasons = []
                    if evidence_below_floor:
                        rejection_reasons.append("LOW_BALL_EVIDENCE")
                    rejection_reasons.extend(edge_adjustments[index])
                    if through_score > 0 and regret > 1e-9:
                        rejection_reasons.append("SEQUENCE_GLOBAL_OPTIMUM")
                        reason = "SEQUENCE_GLOBAL_OPTIMUM"
                    elif evidence_below_floor:
                        rejection_reasons.append("LOW_SEQUENCE_UTILITY")
                        reason = "LOW_BALL_EVIDENCE"
                    else:
                        rejection_reasons.append("LOW_SEQUENCE_UTILITY")
                        reason = "LOW_SEQUENCE_UTILITY"
                    trace["rejection_reasons"] = list(dict.fromkeys(rejection_reasons))
                    removed.append({**row, "decision": reason,
                                    "rejection_reasons": trace["rejection_reasons"],
                                    "decoder_trace": trace})

                    identity_uncertain = (row.get("candidate_player") not in ROLES or
                                          row.get("identity_status") != "CONFIDENT")
                    near_optimal_alternative = (through_score > 0 and regret <=
                                                max(self.config.alternation_reward, 0.001))
                    if (not evidence_below_floor and identity_uncertain) or near_optimal_alternative:
                        review_reason = ("IDENTITY_UNCERTAIN" if identity_uncertain and
                                         not evidence_below_floor else "NEAR_OPTIMAL_SEQUENCE")
                        review_candidates.append({**row, "status": "REQUIRES_REVIEW",
                                                  "review_reason": review_reason,
                                                  "rejection_reasons": trace["rejection_reasons"],
                                                  "decoder_trace": trace})
        accepted.sort(key=lambda row: float(row["timestamp_ms"]))
        previous_time = None
        for index, row in enumerate(accepted, start=1):
            row["sequence_index"] = index
            row["interval_from_previous_ms"] = None if previous_time is None else round(
                float(row["timestamp_ms"]) - previous_time, 3)
            previous_time = float(row["timestamp_ms"])
        return {"accepted": accepted, "suppressed": removed,
                "review_candidates": review_candidates,
                "candidate_count": len(rows), "accepted_count": len(accepted),
                "suppressed_count": len(removed),
                "review_candidate_count": len(review_candidates),
                "decoder_parameters": {
                    "interval_floor_ms": self.interval_floor_ms,
                    "selection_floor": self.config.decoder_selection_floor,
                    "alternation_reward": self.config.alternation_reward,
                    "same_side_penalty": self.config.same_side_penalty,
                    "short_interval_penalty": self.config.short_interval_penalty,
                    "sequence_break_ms": self.config.sequence_break_ms,
                }}


def apply_pose_rerank(candidates: Sequence[Mapping[str, Any]], frame_evidence: Sequence[Mapping[str, Any]],
                      config: HitEventV02Config) -> list[dict[str, Any]]:
    """Optionally rerank existing candidates; never creates new events."""
    if not config.pose_for_hit:
        return [{**candidate, "pose_rerank_applied": False} for candidate in candidates]
    by_time = {round(float(row["timestamp_ms"]), 3): row for row in frame_evidence}
    output = []
    for candidate in candidates:
        row = dict(candidate)
        if config.pose_for_hit:
            frame = by_time.get(round(float(row["timestamp_ms"]), 3), {})
            player = (frame.get("players") or {}).get(row.get("candidate_player")) or {}
            pose = player.get("pose") or {}
            ball = frame.get("ball") or {}
            keypoints = pose.get("keypoints") or {}
            if (pose.get("pose_quality") == "GOOD" and ball.get("visible") is True and
                    ball.get("x") is not None and ball.get("y") is not None):
                wrists = []
                for name in ("left_wrist", "right_wrist"):
                    joint = keypoints.get(name) or {}
                    x = joint.get("x_global", joint.get("x"))
                    y = joint.get("y_global", joint.get("y"))
                    if x is None or y is None or float(joint.get("score", 0.0)) < 0.35:
                        continue
                    distance = _distance((float(ball["x"]), float(ball["y"])),
                                         (float(x), float(y)))
                    wrists.append((distance, name))
                if wrists:
                    distance, joint_name = min(wrists)
                    frame_height = float((frame.get("frame_size") or {}).get("height") or 0)
                    bbox = ((player.get("track") or {}).get("bbox") or [])
                    if frame_height <= 0 and len(bbox) == 4:
                        frame_height = max(1.0, float(bbox[3]) - float(bbox[1]))
                    support_radius = max(1.0, 0.38 * (frame_height or 200.0))
                    support = max(0.0, min(1.0, 1.0 - distance / support_radius))
                    delta = min(config.pose_rerank_max_delta,
                                config.pose_rerank_max_delta * support)
                    row["pose_rerank_evidence"] = {
                        "type": "WRIST_PROXIMITY_PROXY",
                        "nearest_joint": joint_name,
                        "distance_px": round(distance, 3),
                        "support_radius_px": round(support_radius, 3),
                        "support_score": round(support, 6),
                    }
                    if delta > 0:
                        row["evidence_score"] = min(1.0, float(row["evidence_score"]) + delta)
                        row["pose_rerank_delta"] = round(delta, 6)
                        row["pose_rerank_applied"] = True
                        row["source_modules"] = sorted(set(row.get("source_modules", [])) | {"RTMPOSE"})
                    else:
                        row["pose_rerank_delta"] = 0.0
                        row["pose_rerank_applied"] = False
                else:
                    row["pose_rerank_applied"] = False
                    row["pose_rerank_reason"] = "NO_VALID_WRIST_KEYPOINT"
            else:
                row["pose_rerank_applied"] = False
                row["pose_rerank_reason"] = "POSE_OR_BALL_EVIDENCE_UNAVAILABLE"
        else:
            row["pose_rerank_applied"] = False
        output.append(row)
    return output


def build_hit_event_pipeline(frames: Sequence[Mapping[str, Any]], config: HitEventV02Config,
                            interval_prior: StrokeIntervalPrior) -> dict[str, Any]:
    raw = RawHitCandidateGenerator(config).generate(frames)
    cluster = TemporalCandidateClusterer(config.cluster_window_ms).cluster(raw)
    reranked = apply_pose_rerank(cluster["kept"], frames, config)
    decoded = HitSequenceDecoder(config, interval_prior).decode(reranked)
    return {"raw_candidates": raw, "clustered_candidates": cluster["kept"],
            "cluster_suppressed": cluster["suppressed"], "filtered_candidates": decoded["accepted"],
            "decoder_suppressed": decoded["suppressed"],
            "decoder_review_candidates": decoded["review_candidates"],
            "counts": {"raw": len(raw), "clustered": len(cluster["kept"]),
                       "cluster_suppressed": len(cluster["suppressed"]),
                       "decoded": len(decoded["accepted"]),
                       "decoder_suppressed": len(decoded["suppressed"]),
                       "decoder_review_candidates": len(decoded["review_candidates"])},
            "config_sha256": config_sha256(config), "config_status": config.status}


def summarize_hard_negative_overlap(candidates: Sequence[Mapping[str, Any]],
                                    events: Sequence[Mapping[str, Any]], *,
                                    window_ms: float = 100.0) -> dict[str, Any]:
    """Development-only diagnostic; native labels never enter inference."""
    negatives = [event for event in events if event.get("event_type") in {"BOUNCE", "NET"}]
    by_type = {}
    for event_type in ("BOUNCE", "NET"):
        relevant = [row for row in negatives if row.get("event_type") == event_type]
        hits = []
        for candidate in candidates:
            matches = [event for event in relevant if event.get("timestamp_ms") is not None and
                       abs(float(candidate["timestamp_ms"]) - float(event["timestamp_ms"])) <= window_ms]
            if matches:
                hits.append({"candidate_id": candidate["event_id"],
                             "event_ids": [row["event_id"] for row in matches]})
        by_type[event_type] = {"ground_truth_events": len(relevant),
                               "candidate_near_event_count": len(hits), "matches": hits}
    return {"scope": "TRAIN_DEV_DIAGNOSTIC_ONLY; NOT_AN_INFERENCE_INPUT",
            "window_ms": window_ms, "by_event_type": by_type}
