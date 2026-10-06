"""Pure evidence rules for detection-anchored player-mask tracking.

RT-DETR supplies periodic person observations; this module schedules those
anchors, ranks roles against table-derived play zones, and defines conservative
mask/visibility outcomes. GPU inference and persistence stay in adapters.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from math import hypot
from typing import Any, Iterable, Mapping, Sequence


ROLES = ("NEAR_PLAYER", "FAR_PLAYER")
VISIBILITY = {"VISIBLE", "PARTIAL", "OUT_OF_FRAME", "UNKNOWN"}
DEFAULT_ASSOCIATION = {
    "zone_weight": 0.58,
    "continuity_weight": 0.20,
    "size_weight": 0.08,
    "mask_overlap_weight": 0.14,
    "minimum_confident_score": 0.58,
    "minimum_confident_margin": 0.12,
    "minimum_candidate_score": 0.32,
}


def _nearest_frame(seconds: float, fps: float) -> int:
    """Round a non-negative time to the nearest sampled frame, ties upward."""
    return int(seconds * fps + 0.5)


def schedule_time_anchors(*, frame_count: int, sample_fps: float,
                          interval_seconds: float, seed_frame: int = 0) -> list[dict[str, Any]]:
    """Create timestamp-driven anchors and include the seed and final frame.

    Frame indices are derived from elapsed seconds and the clip's measured
    sample FPS; interval spacing is never expressed as a fixed frame count.
    """
    if frame_count <= 0 or sample_fps <= 0 or interval_seconds <= 0:
        raise ValueError("FRAME_COUNT_FPS_AND_INTERVAL_MUST_BE_POSITIVE")
    if seed_frame < 0 or seed_frame >= frame_count:
        raise ValueError("SEED_FRAME_OUT_OF_RANGE")
    duration = (frame_count - 1) / sample_fps
    seed_time = seed_frame / sample_fps
    anchors = {0, seed_frame, frame_count - 1}
    step = 1
    while seed_time - step * interval_seconds >= -1e-9:
        anchors.add(_nearest_frame(seed_time - step * interval_seconds, sample_fps))
        step += 1
    step = 1
    while seed_time + step * interval_seconds <= duration + 1e-9:
        anchors.add(_nearest_frame(seed_time + step * interval_seconds, sample_fps))
        step += 1
    result = []
    for frame in sorted(anchors):
        result.append({"frame": frame, "timestamp_ms": int(frame * 1000 / sample_fps),
                       "clip_time_seconds": frame / sample_fps})
    return result


def derive_play_zones(*, table_bbox: Sequence[float], image_size: Sequence[int],
                      seed_candidates: Mapping[str, Mapping[str, Any]] | None = None,
                      horizontal_padding_table_widths: float = 0.5) -> dict[str, Any]:
    """Derive soft player zones using table geometry and confirmed seed layout.

    Side-view research footage places the two athletes left/right of the table;
    broadcast/end-view footage separates them in image depth (top/bottom).
    The confirmed seed centers choose the dominant separation axis and role
    orientation. Zones remain soft context and never hard-mask detections.
    """
    if len(table_bbox) != 4 or len(image_size) != 2:
        raise ValueError("TABLE_BBOX_AND_IMAGE_SIZE_REQUIRED")
    x0, y0, x1, y1 = map(float, table_bbox)
    width, height = map(float, image_size)
    if width <= 0 or height <= 0 or x1 <= x0 or y1 <= y0:
        raise ValueError("INVALID_TABLE_OR_FRAME_GEOMETRY")
    if horizontal_padding_table_widths < 0:
        raise ValueError("INVALID_PLAY_ZONE_PADDING")
    center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
    pad = (x1 - x0) * horizontal_padding_table_widths
    court_x0, court_x1 = max(0.0, x0 - pad), min(width, x1 + pad)
    axis = "Y"
    near_first = "LOWER"
    if seed_candidates and set(seed_candidates) == set(ROLES):
        near_center = _center(seed_candidates["NEAR_PLAYER"]["bbox"])
        far_center = _center(seed_candidates["FAR_PLAYER"]["bbox"])
        delta_x, delta_y = near_center[0] - far_center[0], near_center[1] - far_center[1]
        if abs(delta_x) > abs(delta_y) * 1.25:
            axis = "X"
            near_first = "RIGHT" if delta_x > 0 else "LEFT"
        else:
            near_first = "LOWER" if delta_y > 0 else "UPPER"
    if axis == "X":
        if near_first == "RIGHT":
            near_zone = [center_x, 0.0, width, height]
            far_zone = [0.0, 0.0, center_x, height]
        else:
            near_zone = [0.0, 0.0, center_x, height]
            far_zone = [center_x, 0.0, width, height]
    elif near_first == "LOWER":
        near_zone = [0.0, center_y, width, height]
        far_zone = [0.0, 0.0, width, center_y]
    else:
        near_zone = [0.0, 0.0, width, center_y]
        far_zone = [0.0, center_y, width, height]
    return {
        "table_bbox": [x0, y0, x1, y1],
        "image_size": [int(width), int(height)],
        "near": {"role": "NEAR_PLAYER", "bbox": near_zone},
        "far": {"role": "FAR_PLAYER", "bbox": far_zone},
        "separation_axis": axis,
        "near_seed_side": near_first,
        "geometry_source": "TABLE_BBOX_FRAME_SIZE_AND_CONFIRMED_SEED_LAYOUT",
    }


def _area(box: Sequence[float]) -> float:
    return max(0.0, float(box[2]) - float(box[0])) * max(0.0, float(box[3]) - float(box[1]))


def _center(box: Sequence[float]) -> tuple[float, float]:
    return (float(box[0]) + float(box[2])) / 2, (float(box[1]) + float(box[3])) / 2


def _iou(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b:
        return 0.0
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = _area(a) + _area(b) - iw * ih
    return iw * ih / union if union else 0.0


def _zone_overlap(candidate: Sequence[float], zone: Sequence[float]) -> float:
    area = _area(candidate)
    if not area:
        return 0.0
    iw = max(0.0, min(candidate[2], zone[2]) - max(candidate[0], zone[0]))
    ih = max(0.0, min(candidate[3], zone[3]) - max(candidate[1], zone[1]))
    overlap = iw * ih / area
    foot_y = float(candidate[3])
    foot_x = (float(candidate[0]) + float(candidate[2])) / 2
    # A player's footpoint is the stronger depth cue; box overlap preserves
    # ambiguity for tall/cropped people who span the table's projected plane.
    foot_inside = zone[0] <= foot_x <= zone[2] and zone[1] <= foot_y <= zone[3]
    return min(1.0, 0.65 * overlap + 0.35 * float(foot_inside))


def _association_score(role: str, candidate: Mapping[str, Any], zones: Mapping[str, Any],
                       frame_size: Sequence[int], reference: Mapping[str, Any] | None,
                       weights: Mapping[str, float]) -> tuple[float, dict[str, float]]:
    bbox = candidate["bbox"]
    zone = zones["near" if role == "NEAR_PLAYER" else "far"]["bbox"]
    zone_score = _zone_overlap(bbox, zone)
    continuity = 0.5
    size = 0.5
    mask_overlap = 0.5
    if reference and reference.get("bbox"):
        ref_box = reference.get("predicted_bbox") or reference["bbox"]
        width, height = map(float, frame_size)
        diagonal = max(1.0, hypot(width, height))
        cx, cy = _center(bbox)
        rx, ry = _center(ref_box)
        continuity = max(0.0, 1.0 - hypot(cx - rx, cy - ry) / (0.55 * diagonal))
        if reference.get("mask_bbox"):
            mask_overlap = _iou(bbox, reference["mask_bbox"])
        size = min(_area(bbox), _area(ref_box)) / max(1.0, _area(bbox), _area(ref_box))
    score = (weights["zone_weight"] * zone_score
             + weights["continuity_weight"] * continuity
             + weights["size_weight"] * size
             + weights["mask_overlap_weight"] * mask_overlap)
    return score, {"play_zone_overlap": zone_score, "temporal_continuity": continuity,
                   "sam2_mask_bbox_overlap": mask_overlap,
                   "bbox_size_similarity": size}


def associate_players(candidates: Iterable[Mapping[str, Any]], zones: Mapping[str, Any], *,
                      frame_size: Sequence[int], references: Mapping[str, Mapping[str, Any]] | None = None,
                      config: Mapping[str, float] | None = None) -> dict[str, dict[str, Any]]:
    """Rank person detections for fixed Near/Far identities without reusing IDs."""
    weights = {**DEFAULT_ASSOCIATION, **dict(config or {})}
    rows = [dict(item) for item in candidates if item.get("candidate_id") and item.get("bbox")]
    scored: dict[str, list[dict[str, Any]]] = {}
    for role in ROLES:
        reference = (references or {}).get(role)
        values = []
        for row in rows:
            score, evidence = _association_score(role, row, zones, frame_size, reference, weights)
            values.append({**row, "association_score": round(score, 6), "evidence": evidence})
        scored[role] = sorted(values, key=lambda item: item["association_score"], reverse=True)

    # Resolve Near/Far jointly. Independent maxima can assign one person to
    # both roles; enumerate distinct pairs so clear table geometry can still
    # separate them while retaining a fail-closed ambiguous result.
    pairs = []
    for near in scored["NEAR_PLAYER"]:
        for far in scored["FAR_PLAYER"]:
            if near["candidate_id"] != far["candidate_id"]:
                pairs.append({"near": near, "far": far,
                              "pair_score": near["association_score"] + far["association_score"]})
    pairs.sort(key=lambda pair: pair["pair_score"], reverse=True)
    selected_pair = pairs[0] if pairs else None
    pair_margin = (selected_pair["pair_score"] - pairs[1]["pair_score"]
                   if len(pairs) > 1 else (selected_pair["pair_score"] if selected_pair else 0.0))
    shared = selected_pair is None and bool(rows)
    result = {}
    for role in ROLES:
        ranked = scored[role]
        independent_best = ranked[0] if ranked else None
        best = selected_pair["near" if role == "NEAR_PLAYER" else "far"] if selected_pair else independent_best
        alternatives = [row for row in ranked if best and row["candidate_id"] != best["candidate_id"]]
        runner_up = alternatives[0] if alternatives else None
        margin = (best["association_score"] - runner_up["association_score"]
                  if best and runner_up else (best["association_score"] if best else 0.0))
        if best is None or best["association_score"] < weights["minimum_candidate_score"]:
            status, selected = "FAILED", None
        elif (shared or best["association_score"] < weights["minimum_confident_score"]
              or margin < weights["minimum_confident_margin"]):
            status, selected = "AMBIGUOUS", None
        else:
            status, selected = "CONFIDENT", best
        result[role] = {"status": status, "candidate": selected,
                        "best_candidate": best, "independent_best_candidate": independent_best,
                        "ranked": ranked, "score_margin": round(margin, 6),
                        "pair_score_margin": round(pair_margin, 6),
                        "candidate_reused_by_other_role": shared}
    return result


class PlayerIdentityAssociator:
    """Maintain fixed Near/Far identities across timestamped detector anchors."""

    def __init__(self, zones: Mapping[str, Any], *, frame_size: Sequence[int],
                 config: Mapping[str, float] | None = None, direction: int = 1):
        self.zones = dict(zones)
        self.frame_size = tuple(map(int, frame_size))
        if len(self.frame_size) != 2 or min(self.frame_size) <= 0:
            raise ValueError("INVALID_FRAME_SIZE")
        self.config = {**DEFAULT_ASSOCIATION, **dict(config or {})}
        if direction not in {-1, 1}:
            raise ValueError("DIRECTION_MUST_BE_FORWARD_OR_REVERSE")
        self.direction = direction
        self.history: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}

    def confirm(self, role: str, candidate: Mapping[str, Any], *, frame: int,
                timestamp_ms: int, mask_bbox: Sequence[float] | None = None,
                source: str = "USER_CONFIRMED") -> dict[str, Any]:
        if role not in ROLES or not candidate.get("candidate_id") or len(candidate.get("bbox", [])) != 4:
            raise ValueError("INVALID_ROLE_OR_PERSON_CANDIDATE")
        if frame < 0 or timestamp_ms < 0:
            raise ValueError("ANCHOR_TIME_MUST_BE_NON_NEGATIVE")
        candidate_id = str(candidate["candidate_id"])
        other = "FAR_PLAYER" if role == "NEAR_PLAYER" else "NEAR_PLAYER"
        if any(row["candidate_id"] == candidate_id for row in self.history[other][-1:]):
            raise ValueError("CANDIDATE_ALREADY_BOUND_TO_OTHER_ROLE")
        record = {"candidate_id": candidate_id, "bbox": list(map(float, candidate["bbox"])),
                  "frame": frame, "timestamp_ms": timestamp_ms,
                  "mask_bbox": list(map(float, mask_bbox)) if mask_bbox else None,
                  "source": source}
        if (self.history[role]
                and self.direction * (timestamp_ms - self.history[role][-1]["timestamp_ms"]) < 0):
            raise ValueError("ANCHOR_TIME_ORDER_DOES_NOT_MATCH_DIRECTION")
        self.history[role].append(record)
        return deepcopy(record)

    def _predicted_reference(self, role: str, timestamp_ms: int,
                             mask_bbox: Sequence[float] | None = None) -> dict[str, Any] | None:
        rows = self.history[role]
        if not rows:
            return None
        latest = rows[-1]
        predicted = list(latest["bbox"])
        if len(rows) > 1:
            previous = rows[-2]
            dt = latest["timestamp_ms"] - previous["timestamp_ms"]
            future = timestamp_ms - latest["timestamp_ms"]
            if dt and self.direction * future > 0 and future / dt > 0:
                p_cx, p_cy = _center(previous["bbox"])
                l_cx, l_cy = _center(latest["bbox"])
                dx = (l_cx - p_cx) * future / dt
                dy = (l_cy - p_cy) * future / dt
                diagonal = hypot(*self.frame_size)
                magnitude = hypot(dx, dy)
                if magnitude > diagonal * 0.22:
                    scale = diagonal * 0.22 / magnitude
                    dx *= scale
                    dy *= scale
                predicted = [latest["bbox"][0] + dx, latest["bbox"][1] + dy,
                             latest["bbox"][2] + dx, latest["bbox"][3] + dy]
        return {"bbox": list(latest["bbox"]), "predicted_bbox": predicted,
                "mask_bbox": list(mask_bbox) if mask_bbox else latest.get("mask_bbox")}

    def observe(self, candidates: Iterable[Mapping[str, Any]], *, frame: int,
                timestamp_ms: int,
                mask_bboxes: Mapping[str, Sequence[float]] | None = None) -> dict[str, dict[str, Any]]:
        if frame < 0 or timestamp_ms < 0:
            raise ValueError("ANCHOR_TIME_MUST_BE_NON_NEGATIVE")
        references = {role: self._predicted_reference(role, timestamp_ms,
                                                       (mask_bboxes or {}).get(role))
                      for role in ROLES}
        result = associate_players(candidates, self.zones, frame_size=self.frame_size,
                                   references=references, config=self.config)
        for role in ROLES:
            choice = result[role]
            candidate = choice.get("candidate")
            if choice["status"] == "CONFIDENT" and candidate:
                self.confirm(role, candidate, frame=frame, timestamp_ms=timestamp_ms,
                             mask_bbox=(mask_bboxes or {}).get(role), source="RTDETR_CONFIDENT")
        return result


def _copy_mask(mask):
    if mask is None:
        return None
    copier = getattr(mask, "copy", None)
    return copier() if callable(copier) else deepcopy(mask)


def _mask_stats(mask) -> tuple[int, int]:
    if mask is None:
        return 0, 0
    if hasattr(mask, "shape"):
        count = int(mask.astype(bool).sum())
        height, width = mask.shape[:2]
        return count, int(height * width)
    rows = list(mask)
    return sum(bool(value) for row in rows for value in row), sum(len(row) for row in rows)


def fuse_masks(forward, reverse, *, visibility: str, agreement_iou: float = 0.55) -> dict[str, Any]:
    """Select a mask only when evidence and visibility permit it; preserve both raws."""
    if visibility not in VISIBILITY:
        raise ValueError("INVALID_VISIBILITY_STATE")
    f_raw, r_raw = _copy_mask(forward), _copy_mask(reverse)
    f_pixels, f_total = _mask_stats(forward)
    r_pixels, r_total = _mask_stats(reverse)
    if f_total and r_total and f_total != r_total:
        raise ValueError("FORWARD_REVERSE_MASK_SHAPE_MISMATCH")
    if visibility == "OUT_OF_FRAME":
        return {"status": "SUPPRESSED_OUT_OF_FRAME", "decision": "NO_MASK_EXPECTED",
                "source": None, "final_mask": None, "forward_raw": f_raw, "reverse_raw": r_raw,
                "evidence": {"visibility": visibility, "forward_pixels": f_pixels, "reverse_pixels": r_pixels}}
    if visibility == "UNKNOWN":
        return {"status": "REVIEW_REQUIRED", "decision": "VISIBILITY_UNKNOWN",
                "source": None, "final_mask": None, "forward_raw": f_raw, "reverse_raw": r_raw,
                "evidence": {"visibility": visibility, "forward_pixels": f_pixels, "reverse_pixels": r_pixels}}
    if not f_pixels and not r_pixels:
        return {"status": "REVIEW_REQUIRED", "decision": "VISIBLE_WITHOUT_MASK",
                "source": None, "final_mask": None, "forward_raw": f_raw, "reverse_raw": r_raw,
                "evidence": {"visibility": visibility, "forward_pixels": f_pixels, "reverse_pixels": r_pixels}}
    if f_pixels and not r_pixels:
        return {"status": "CANDIDATE", "decision": "FORWARD_ONLY",
                "source": "FORWARD", "final_mask": f_raw, "forward_raw": f_raw, "reverse_raw": r_raw,
                "evidence": {"visibility": visibility, "forward_pixels": f_pixels, "reverse_pixels": r_pixels}}
    if r_pixels and not f_pixels:
        return {"status": "CANDIDATE", "decision": "REVERSE_ONLY",
                "source": "REVERSE", "final_mask": r_raw, "forward_raw": f_raw, "reverse_raw": r_raw,
                "evidence": {"visibility": visibility, "forward_pixels": f_pixels, "reverse_pixels": r_pixels}}
    # Use numpy fast path in the GPU worker; retain a dependency-free path for
    # backend tests and lightweight desktop processes.
    if hasattr(forward, "shape"):
        import numpy as np
        f_bool, r_bool = np.asarray(forward, dtype=bool), np.asarray(reverse, dtype=bool)
        intersection = int(np.logical_and(f_bool, r_bool).sum())
        union = int(np.logical_or(f_bool, r_bool).sum())
    else:
        f_rows, r_rows = list(forward), list(reverse)
        if len(f_rows) != len(r_rows) or any(len(a) != len(b) for a, b in zip(f_rows, r_rows)):
            raise ValueError("FORWARD_REVERSE_MASK_SHAPE_MISMATCH")
        intersection = sum(bool(a) and bool(b) for row_a, row_b in zip(f_rows, r_rows)
                           for a, b in zip(row_a, row_b))
        union = sum(bool(a) or bool(b) for row_a, row_b in zip(f_rows, r_rows)
                    for a, b in zip(row_a, row_b))
    iou = intersection / union if union else 1.0
    evidence = {"visibility": visibility, "forward_pixels": f_pixels,
                "reverse_pixels": r_pixels, "forward_reverse_iou": round(iou, 6)}
    if iou < agreement_iou:
        return {"status": "REVIEW_REQUIRED", "decision": "FORWARD_REVERSE_CONFLICT",
                "source": None, "final_mask": None, "forward_raw": f_raw,
                "reverse_raw": r_raw, "evidence": evidence}
    return {"status": "ACCEPTED", "decision": "FORWARD_REVERSE_AGREE",
            "source": "FORWARD_REVERSE_AGREE", "final_mask": f_raw,
            "forward_raw": f_raw, "reverse_raw": r_raw, "evidence": evidence}


def visibility_coverage(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute mask availability only where human visibility truth permits it."""
    items = list(rows)
    if any(item.get("visibility") not in VISIBILITY for item in items):
        raise ValueError("INVALID_VISIBILITY_STATE")
    eligible = [item for item in items if item["visibility"] in {"VISIBLE", "PARTIAL"}]
    available = sum(bool(item.get("mask_present")) for item in eligible)
    out = sum(item["visibility"] == "OUT_OF_FRAME" for item in items)
    unknown = sum(item["visibility"] == "UNKNOWN" for item in items)
    return {"eligible_frames": len(eligible), "mask_available": available,
            "coverage": available / len(eligible) if eligible else None,
            "out_of_frame": out, "unknown": unknown}


class AnchorGuidedPlayerTracker:
    """Evidence-first RT-DETR anchor orchestration for fixed player identities.

    The class does not run SAM2 or touch files. It produces time anchors,
    candidate associations, and prompt decisions; a worker consumes those
    decisions using stable SAM2 object IDs 1 (Near) and 2 (Far).
    """

    OBJECT_IDS = {"NEAR_PLAYER": 1, "FAR_PLAYER": 2}

    def __init__(self, *, sample_id: str, frame_count: int, sample_fps: float,
                 interval_seconds: float, seed_frame: int,
                 seed_candidates: Mapping[str, Mapping[str, Any]],
                 zones: Mapping[str, Any], frame_size: Sequence[int],
                 config: Mapping[str, float] | None = None):
        if set(seed_candidates) != set(ROLES):
            raise ValueError("BOTH_CONFIRMED_PLAYER_SEEDS_REQUIRED")
        self.sample_id = sample_id
        self.frame_count = frame_count
        self.sample_fps = sample_fps
        self.interval_seconds = interval_seconds
        self.seed_frame = seed_frame
        self.config = {**DEFAULT_ASSOCIATION, **dict(config or {})}
        self.anchors = schedule_time_anchors(frame_count=frame_count, sample_fps=sample_fps,
                                             interval_seconds=interval_seconds,
                                             seed_frame=seed_frame)
        self.associators = {
            1: PlayerIdentityAssociator(zones, frame_size=frame_size, config=self.config, direction=1),
            -1: PlayerIdentityAssociator(zones, frame_size=frame_size, config=self.config, direction=-1),
        }
        self.anchor_results: dict[int, dict[str, Any]] = {}
        seed_time = int(seed_frame * 1000 / sample_fps)
        normalized_seeds = {}
        for role in ROLES:
            candidate = dict(seed_candidates[role])
            if not candidate.get("candidate_id") or len(candidate.get("bbox", [])) != 4:
                raise ValueError("INVALID_CONFIRMED_PLAYER_SEED")
            normalized_seeds[role] = candidate
            for associator in self.associators.values():
                associator.confirm(role, candidate, frame=seed_frame, timestamp_ms=seed_time,
                                   source="USER_CONFIRMED_SEED")
        self.seed_candidates = normalized_seeds

    def observe_anchor(self, frame: int, detections: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        if frame not in {row["frame"] for row in self.anchors}:
            raise ValueError("FRAME_IS_NOT_A_SCHEDULED_ANCHOR")
        if frame in self.anchor_results:
            raise ValueError("ANCHOR_ALREADY_OBSERVED")
        timestamp_ms = int(frame * 1000 / self.sample_fps)
        raw = [dict(row) for row in detections]
        if frame == self.seed_frame:
            decisions = {
                role: {"status": "CONFIDENT", "candidate": dict(self.seed_candidates[role]),
                       "best_candidate": dict(self.seed_candidates[role]),
                       "source": "USER_CONFIRMED_SEED"}
                for role in ROLES
            }
        else:
            direction = 1 if frame > self.seed_frame else -1
            decisions = self.associators[direction].observe(raw, frame=frame,
                                                             timestamp_ms=timestamp_ms)
            for role in ROLES:
                decisions[role]["source"] = ("RTDETR_CONFIDENT" if decisions[role]["status"] == "CONFIDENT"
                                              else "RTDETR_ASSOCIATION_REVIEW")
        result = {"frame": frame, "timestamp_ms": timestamp_ms,
                  "direction_from_seed": 0 if frame == self.seed_frame else (1 if frame > self.seed_frame else -1),
                  "raw_detections": raw, "roles": decisions}
        self.anchor_results[frame] = result
        return deepcopy(result)

    def prompt_plan(self) -> list[dict[str, Any]]:
        """Return only user-confirmed or confident detections as SAM2 prompts."""
        plan = []
        for frame in sorted(self.anchor_results):
            anchor = self.anchor_results[frame]
            for role in ROLES:
                row = anchor["roles"][role]
                candidate = row.get("candidate")
                if row["status"] != "CONFIDENT" or not candidate:
                    continue
                plan.append({"frame": frame, "timestamp_ms": anchor["timestamp_ms"],
                             "object_id": self.OBJECT_IDS[role], "role": role,
                             "bbox": list(map(float, candidate["bbox"])),
                             "candidate_id": candidate.get("candidate_id"),
                             "source": row["source"], "status": row["status"]})
        return plan

    def config_fingerprint(self) -> str:
        payload = {"sample_id": self.sample_id, "frame_count": self.frame_count,
                   "sample_fps": self.sample_fps, "interval_seconds": self.interval_seconds,
                   "seed_frame": self.seed_frame, "association": self.config,
                   "schema": "anchor-guided-player-tracker-v1"}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checkpoint_matches(checkpoint: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    """Fail-closed resume predicate for an anchor-window checkpoint."""
    keys = ("source_sha256", "config_sha256", "sample_id", "role", "start_frame", "end_frame")
    return all(checkpoint.get(key) == expected.get(key) for key in keys)
