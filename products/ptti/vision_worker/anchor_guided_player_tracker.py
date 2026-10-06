"""Isolated RT-DETR + SAM 2 short-window runner for anchor-guided tracking."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from statistics import median

import player_tracking_closed_loop as closed_loop_worker

PRODUCT_ROOT = closed_loop_worker.PRODUCT_ROOT
LOCAL = closed_loop_worker.LOCAL
RUNTIME_ROOT = closed_loop_worker.RUNTIME_ROOT

sys.path.insert(0, str(PRODUCT_ROOT))

from backend.anchor_guided_tracker import (  # noqa: E402
    AnchorGuidedPlayerTracker,
    MASK_CONFLICT_AGREEMENT_IOU,
    OUT_OF_FRAME_EDGE_MARGIN_RATIO,
    checkpoint_matches,
    classify_out_of_frame,
    derive_play_zones,
    fuse_masks,
    group_mask_conflicts,
    summarize_manual_actions,
    tracking_state,
    visibility_coverage,
)
from backend.player_tracking_closed_loop import (  # noqa: E402
    append_manual_action,
    atomic_json,
    closed_loop_root,
    load_job_progress,
    resolve_sample,
    save_job_progress,
)


VISIBILITY_PATH = RUNTIME_ROOT / "runs" / "anchor-guided" / "visibility_truth_v1.json"
TABLE_MANIFEST_PATH = LOCAL / "PTTI-Dev" / "vision-v2" / "scene-bootstrap" / "scene_bootstrap_eval_manifest.json"
CONFIG_PATH = RUNTIME_ROOT / "runs" / "anchor-guided" / "anchor_tracker_config.json"
DEFAULT_INTERVALS = (0.5, 1.0, 2.0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def table_context_for_sample(sample: dict) -> dict:
    """Use the frozen same-match scene bootstrap geometry as soft context."""
    if not TABLE_MANIFEST_PATH.is_file():
        raise RuntimeError("MATCH_TABLE_CONTEXT_NOT_AVAILABLE")
    manifest = json.loads(TABLE_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (manifest.get("dataset") != "Extended OpenTTGames"
            or manifest.get("license") != "CC BY-NC-SA 4.0"
            or manifest.get("commercial_use") is not False):
        raise RuntimeError("TABLE_CONTEXT_PROVENANCE_INVALID")
    game = str(sample["match_id"])
    rows = [row for row in manifest.get("frame_results", [])
            if row.get("game") == game and row.get("table_found") is True
            and row.get("selected_table_bbox")]
    if not rows:
        raise RuntimeError("MATCH_TABLE_CONTEXT_NOT_AVAILABLE")
    components = list(zip(*(list(map(float, row["selected_table_bbox"])) for row in rows)))
    bbox = [median(values) for values in components]
    if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise RuntimeError("MATCH_TABLE_CONTEXT_INVALID")
    return {"bbox": bbox, "source": "FROZEN_SCENE_BOOTSTRAP_EVAL_MANIFEST",
            "dataset": manifest["dataset"], "license": manifest["license"],
            "game": game, "source_frame_count": len(rows),
            "source_frame_hashes": sorted({row.get("frame_sha256") for row in rows if row.get("frame_sha256")}),
            "method": "component-wise median of selected same-match table boxes; soft role context only"}


def load_visibility_windows(sample: dict) -> tuple[list[dict], str]:
    """Load human-reviewed coarse visibility labels; absent/invalid labels fail closed."""
    if not VISIBILITY_PATH.is_file():
        return [], "NOT_AVAILABLE"
    value = json.loads(VISIBILITY_PATH.read_text(encoding="utf-8"))
    if (value.get("schema_version") != "ptti-player-visibility-truth-v1"
            or value.get("dataset") != "Extended OpenTTGames"
            or value.get("license") != "CC BY-NC-SA 4.0"
            or value.get("review_method") != "HUMAN_REVIEWED_0_5_SECOND_WINDOWS"):
        return [], "INVALID_MANIFEST"
    rows = value.get("samples", {}).get(sample["sample_id"], {})
    if rows.get("source_sha256") != sample["clip_sha256"]:
        return [], "SOURCE_SHA_MISMATCH"
    windows = rows.get("windows", [])
    cursor = 0
    for row in windows:
        if row.get("start_frame") != cursor or row.get("end_frame", -1) < cursor:
            return [], "WINDOW_COVERAGE_GAP"
        if not row.get("start_frame") <= row.get("review_frame", -1) <= row.get("end_frame"):
            return [], "REVIEW_FRAME_OUTSIDE_WINDOW"
        if any(row.get(role) not in {"VISIBLE", "PARTIAL", "OUT_OF_FRAME", "UNKNOWN"}
               for role in ("NEAR_PLAYER", "FAR_PLAYER")):
            return [], "INVALID_VISIBILITY_LABEL"
        cursor = row["end_frame"] + 1
    if cursor != sample["frames"]:
        return [], "WINDOW_COVERAGE_INCOMPLETE"
    return windows, "HUMAN_REVIEWED"


def visibility_at(windows: list[dict], role: str, frame: int) -> str:
    for row in windows:
        if row["start_frame"] <= frame <= row["end_frame"]:
            return row[role]
    return "UNKNOWN"


def _mask_path(job: Path, direction: str, role: str, frame: int, config_sha: str) -> Path:
    return (job / "anchor-runs" / config_sha[:12] / "raw" / direction.lower()
            / role.lower() / f"{frame:05d}.png")


def _read_mask(path: Path, frame_size: tuple[int, int]):
    import numpy as np
    from PIL import Image
    if not path.is_file():
        return np.zeros((frame_size[1], frame_size[0]), dtype=bool)
    return np.asarray(Image.open(path).convert("L")) > 0


def _window_checkpoint(job: Path, left: int, right: int) -> Path:
    return job / "checkpoints" / f"window-{left:05d}-{right:05d}.json"


def _load_window(job: Path, checkpoint_path: Path, expected: dict, frame_size: tuple[int, int]):
    import numpy as np
    if not checkpoint_path.is_file():
        return None
    try:
        metadata = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if not checkpoint_matches(metadata, expected):
            return None
        masks = {"forward": {role: {} for role in ("NEAR_PLAYER", "FAR_PLAYER")},
                 "reverse": {role: {} for role in ("NEAR_PLAYER", "FAR_PLAYER")}}
        for item in metadata.get("outputs", []):
            path = (job / item["path"]).resolve()
            if not path.is_relative_to(job.resolve()) or not path.is_file() or sha256_file(path) != item["sha256"]:
                return None
            # Store paths are normalized as anchor-raw/<direction>/<role>/<frame>.png.
            parts = Path(item["path"]).parts
            direction = parts[-3]
            role = item["role"]
            frame = int(item["frame"])
            masks[direction][role][frame] = _read_mask(path, frame_size)
        if metadata.get("complete") is not True:
            return None
        return masks
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save_window(job: Path, checkpoint_path: Path, expected: dict, masks: dict) -> None:
    outputs = []
    for direction, role_map in masks.items():
        for role, frames in role_map.items():
            for frame, mask in frames.items():
                path = _mask_path(job, direction, role, frame, expected["config_sha256"])
                closed_loop_worker.atomic_mask(mask, path)
                outputs.append({"path": str(path.relative_to(job)), "role": role,
                                "frame": int(frame), "sha256": sha256_file(path)})
    atomic_json(checkpoint_path, {**expected, "outputs": outputs, "complete": True,
                                  "completed_at": closed_loop_worker.now()})


def _collect_masks(predictor, state, start: int, limit: int, reverse: bool,
                   object_roles: dict[int, str], shape: tuple[int, int], torch,
                   frame_offset: int = 0) -> dict[str, dict[int, object]]:
    output = {role: {} for role in object_roles.values()}
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        for frame_idx, object_ids, masks in predictor.propagate_in_video(
                state, start_frame_idx=start, max_frame_num_to_track=limit, reverse=reverse):
            array = masks.detach().float().cpu().numpy()
            for position, object_id in enumerate(map(int, object_ids)):
                role = object_roles.get(object_id)
                if role:
                    output[role][int(frame_idx) + frame_offset] = closed_loop_worker.mask_from_output(
                        torch.from_numpy(array[position]), shape)
    return output


def _materialize_window_frames(source_folder: Path, job: Path, left: int, right: int) -> Path:
    """Expose only this short window to SAM2, with local contiguous frame IDs."""
    window = job / "window-input" / f"{left:05d}-{right:05d}"
    if window.exists():
        shutil.rmtree(window)
    window.mkdir(parents=True)
    for local_frame, source_frame in enumerate(range(left, right + 1)):
        source = source_folder / f"{source_frame:05d}.jpg"
        target = window / f"{local_frame:05d}.jpg"
        if not source.is_file():
            raise RuntimeError(f"ANCHOR_WINDOW_FRAME_MISSING:{source_frame}")
        try:
            os.link(source, target)
        except OSError:
            shutil.copyfile(source, target)
    return window


def _run_window(predictor, frame_folder: Path, left: int, right: int,
                left_prompts: dict[str, dict], right_prompts: dict[str, dict], torch,
                image_size: tuple[int, int]) -> dict:
    state = predictor.init_state(str(frame_folder), offload_video_to_cpu=True,
                                 offload_state_to_cpu=True, async_loading_frames=False)
    roles_to_ids = {"NEAR_PLAYER": 1, "FAR_PLAYER": 2}
    width, height = image_size
    output = {"forward": {role: {} for role in roles_to_ids},
              "reverse": {role: {} for role in roles_to_ids}}
    try:
        if left_prompts:
            for role, prompt in left_prompts.items():
                predictor.add_new_points_or_box(state, frame_idx=0,
                                                obj_id=roles_to_ids[role], box=prompt["bbox"])
            output["forward"] = _collect_masks(predictor, state, 0, right - left,
                                               False, {value: key for key, value in roles_to_ids.items()},
                                               (height, width), torch, frame_offset=left)
        predictor.reset_state(state)
        if right_prompts:
            for role, prompt in right_prompts.items():
                predictor.add_new_points_or_box(state, frame_idx=right - left,
                                                obj_id=roles_to_ids[role], box=prompt["bbox"])
            output["reverse"] = _collect_masks(predictor, state, right - left, right - left,
                                               True, {value: key for key, value in roles_to_ids.items()},
                                               (height, width), torch, frame_offset=left)
        return output
    finally:
        try:
            predictor.reset_state(state)
        except Exception:
            pass


def _load_player_seed(seed: dict) -> dict[str, dict]:
    selected = {row["role"]: row for row in seed.get("selected_seeds", [])}
    if set(selected) != {"NEAR_PLAYER", "FAR_PLAYER"}:
        raise RuntimeError("BOTH_CONFIRMED_PLAYER_SEEDS_REQUIRED")
    return {role: {"candidate_id": row["candidate_id"], "bbox": row["bbox"],
                   "detector_score": row.get("detector_score"), "source": "USER_CONFIRMED_SEED"}
            for role, row in selected.items()}


def command_track(job_id: str, interval_seconds: float):
    import numpy as np
    import torch
    from PIL import Image, ImageDraw
    from sam2.build_sam import build_sam2_video_predictor

    job = (closed_loop_root() / "jobs" / job_id).resolve()
    if not job.is_dir():
        raise FileNotFoundError("CLOSED_LOOP_JOB_NOT_FOUND")
    seed = json.loads((job / "seed.json").read_text(encoding="utf-8"))
    sample = resolve_sample(seed["sample_id"])
    source = Path(sample["video_path"])
    if closed_loop_worker.file_sha(source) != seed["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")
    if interval_seconds not in DEFAULT_INTERVALS:
        raise ValueError("UNSUPPORTED_ANCHOR_INTERVAL")
    decoded = closed_loop_worker.ensure_decoded_frames(sample)
    frame_folder = decoded
    table_context = table_context_for_sample(sample)
    seed_candidates = _load_player_seed(seed)
    zones = derive_play_zones(table_bbox=table_context["bbox"],
                              image_size=(sample["width"], sample["height"]),
                              seed_candidates=seed_candidates)
    orchestrator = AnchorGuidedPlayerTracker(
        sample_id=sample["sample_id"], frame_count=sample["frames"],
        sample_fps=sample["sample_fps"], interval_seconds=interval_seconds,
        seed_frame=seed["seed_frame"], seed_candidates=seed_candidates,
        zones=zones, frame_size=(sample["width"], sample["height"]))
    visibility_windows, visibility_status = load_visibility_windows(sample)

    torch, sam2_commit = closed_loop_worker.runtime_metadata()
    torch.cuda.reset_peak_memory_stats()
    model_started = time.perf_counter()
    predictor = build_sam2_video_predictor(
        str(closed_loop_worker.SAM2_CONFIG), str(closed_loop_worker.SAM2_CHECKPOINT),
        device="cuda", mode="eval", apply_postprocessing=False, vos_optimized=False)
    processor, detector, rtdetr_provenance = closed_loop_worker.load_rtdetr(torch)
    model_load_seconds = time.perf_counter() - model_started

    progress_events = load_job_progress(job_id).get("events", [])
    # Automatic events are regenerated for a rerun; only retain user-originated
    # events so a retry cannot inflate counts with duplicated detections.
    events = [event for event in progress_events
              if event.get("type") == "INITIAL_SEED" or event.get("source") == "USER_UI"]
    raw_anchor_results = []
    prompts_by_frame: dict[int, dict[str, dict]] = {}
    detector_seconds = 0.0
    detector_calls = 0
    anchor_frames = [row["frame"] for row in orchestrator.anchors]
    started = time.perf_counter()
    update = closed_loop_worker.update_progress
    total_steps = len(anchor_frames) + max(0, len(anchor_frames) - 1) + sample["frames"]
    update(job_id, status="RUNNING", stage="准备按时间建立 RT-DETR 追踪锚点",
           processed=0, total_steps=total_steps, error="")

    # Two independent histories walk away from the fixed user-confirmed seed.
    detect_order = ([seed["seed_frame"]]
                    + sorted(frame for frame in anchor_frames if frame > seed["seed_frame"])
                    + sorted((frame for frame in anchor_frames if frame < seed["seed_frame"]), reverse=True))
    for index, frame in enumerate(detect_order, start=1):
        if frame == seed["seed_frame"]:
            raw_detections = seed.get("raw_detections", [])
        else:
            image = Image.open(frame_folder / f"{frame:05d}.jpg").convert("RGB")
            detect_started = time.perf_counter()
            raw_detections = closed_loop_worker.detect_people(
                image, frame_index=frame,
                timestamp_ms=round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000),
                torch=torch, processor=processor, model=detector)
            torch.cuda.synchronize()
            detector_seconds += time.perf_counter() - detect_started
            detector_calls += 1
            image.close()
        anchor = orchestrator.observe_anchor(frame, raw_detections)
        anchor["clip_time_ms"] = anchor["timestamp_ms"]
        anchor["timestamp_ms"] = round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000)
        for role, result in anchor["roles"].items():
            annotation = visibility_at(visibility_windows, role, frame)
            classification = classify_out_of_frame(
                frame_size=(sample["width"], sample["height"]),
                human_annotation=annotation,
                edge_margin_ratio=OUT_OF_FRAME_EDGE_MARGIN_RATIO)
            result["tracking_state"] = (
                "IDENTITY_UNCERTAIN" if result["status"] == "AMBIGUOUS"
                and classification["classification"] != "OUT_OF_FRAME"
                else classification["classification"])
            result["visibility_classification"] = classification
        raw_anchor_results.append(anchor)
        prompt_map = {}
        for role, result in anchor["roles"].items():
            candidate = result.get("candidate")
            if result["status"] == "CONFIDENT" and candidate:
                prompt_map[role] = {"bbox": list(map(float, candidate["bbox"])),
                                    "candidate_id": candidate.get("candidate_id"),
                                    "source": result["source"]}
                if frame != seed["seed_frame"]:
                    event = {"type": "AUTO_ANCHOR", "frame": frame,
                             "timestamp_ms": round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000),
                             "role": role, "object_id": AnchorGuidedPlayerTracker.OBJECT_IDS[role],
                             "candidate_id": candidate.get("candidate_id"),
                             "bbox": candidate["bbox"], "source": "RTDETR_R18",
                             "association": result.get("best_candidate", {}).get("evidence", {})}
                    events.append(event)
                    update(job_id, status="RUNNING", stage="已确认新锚点，固定球员身份并更新 SAM2 提示", event=event)
            elif result["status"] == "AMBIGUOUS":
                classification = result.get("visibility_classification", {})
                out_of_frame = classification.get("classification") == "OUT_OF_FRAME"
                event = {"type": "OUT_OF_FRAME" if out_of_frame else "IDENTITY_UNCERTAIN",
                         "event_id": f"{('OUT_OF_FRAME' if out_of_frame else 'IDENTITY_UNCERTAIN')}_{role}_{frame:05d}",
                         "classification": classification.get("classification", "UNKNOWN"),
                         "confidence_level": classification.get("confidence_level", "LOW"),
                         "frame": frame,
                         "timestamp_ms": round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000),
                         "role": role, "object_id": AnchorGuidedPlayerTracker.OBJECT_IDS[role],
                         "candidate_id": result.get("best_candidate", {}).get("candidate_id"),
                         "source": classification.get("source", "RTDETR_ASSOCIATION"),
                         "status": "REVIEW_REQUIRED" if not out_of_frame else "CLASSIFIED",
                         "evidence": classification.get("evidence") or
                                    result.get("best_candidate", {}).get("evidence", [])}
                events.append(event)
        prompts_by_frame[frame] = prompt_map
        update(job_id, status="RUNNING", stage=f"RT-DETR 锚点检测 · {index}/{len(anchor_frames)}",
               processed=index)

    raw_anchor_results.sort(key=lambda row: row["frame"])
    events.sort(key=lambda row: row.get("timestamp_ms", 0))
    anchor_manifest = {
        "schema_version": "anchor-guided-detections-v1", "sample_id": sample["sample_id"],
        "source_sha256": sample["clip_sha256"], "interval_seconds": interval_seconds,
        "anchors": raw_anchor_results,
        "prompt_plan": orchestrator.prompt_plan(),
        "table_context": table_context, "zones": zones,
        "created_at": closed_loop_worker.now(),
    }
    atomic_json(job / "anchors.json", anchor_manifest)
    config_payload = {"schema_version": "anchor-guided-sam2-window-v1",
                      "frame_window_input": "CROPPED_TO_ANCHOR_WINDOW_V1",
                      "tracker_implementation": "ANCHOR_GUIDED_ROLE_ZONES_V2",
                      "interval_seconds": interval_seconds, "sample_id": sample["sample_id"],
                      "source_sha256": sample["clip_sha256"], "seed_frame": seed["seed_frame"],
                      "seed_candidates": seed_candidates, "table_context": table_context,
                      "play_zones": zones,
                      "association": orchestrator.config,
                      "mask_conflict_agreement_iou": MASK_CONFLICT_AGREEMENT_IOU,
                      "out_of_frame_edge_margin_ratio": OUT_OF_FRAME_EDGE_MARGIN_RATIO,
                      "out_of_frame_rule": "HUMAN_LABEL_OR_EDGE_PLUS_NO_MATCH_AND_MASK_ABSENCE",
                      "sam2_checkpoint_sha256": closed_loop_worker.EXPECTED_SAM2_SHA,
                      "rtdetr_revision": rtdetr_provenance.get("revision")}
    config_sha = sha256_json(config_payload)
    atomic_json(CONFIG_PATH, {**config_payload, "sha256": config_sha})

    visibility_by_frame = {
        role: [visibility_at(visibility_windows, role, frame) for frame in range(sample["frames"])]
        for role in ("NEAR_PLAYER", "FAR_PLAYER")
    }
    frame_size = (sample["width"], sample["height"])
    window_rows = []
    inference_started = time.perf_counter()
    windows = list(zip(anchor_frames, anchor_frames[1:]))
    window_cache_hits = 0
    window_cache_misses = 0
    job.mkdir(exist_ok=True)
    (job / "checkpoints").mkdir(exist_ok=True)

    for window_index, (left, right) in enumerate(windows, start=1):
        expected = {"source_sha256": sample["clip_sha256"], "config_sha256": config_sha,
                    "sample_id": sample["sample_id"], "role": "BOTH_PLAYERS",
                    "start_frame": left, "end_frame": right}
        checkpoint_path = _window_checkpoint(job, left, right)
        saved = _load_window(job, checkpoint_path, expected, frame_size)
        cache_hit = saved is not None
        if saved is None:
            window_cache_misses += 1
            window_frame_folder = _materialize_window_frames(frame_folder, job, left, right)
            try:
                saved = _run_window(
                    predictor, window_frame_folder, left, right,
                    prompts_by_frame.get(left, {}), prompts_by_frame.get(right, {}),
                    torch, frame_size)
            finally:
                shutil.rmtree(window_frame_folder, ignore_errors=True)
            _save_window(job, checkpoint_path, expected, saved)
        else:
            window_cache_hits += 1
        window_rows.append({"start_frame": left, "end_frame": right,
                            "start_timestamp_ms": round(left * 1000 / sample["sample_fps"]),
                            "end_timestamp_ms": round(right * 1000 / sample["sample_fps"]),
                            "cache": "HIT" if cache_hit else "MISS",
                            "left_prompt_roles": sorted(prompts_by_frame.get(left, {})),
                            "right_prompt_roles": sorted(prompts_by_frame.get(right, {}))})
        update(job_id, status="RUNNING", stage=f"SAM2 双向短窗传播 · {window_index}/{len(windows)}",
               processed=len(anchor_frames) + window_index)

    torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - inference_started
    if closed_loop_worker.file_sha(source) != seed["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")

    records = []
    fused_masks = {role: {} for role in ("NEAR_PLAYER", "FAR_PLAYER")}
    raw_stats = {role: {"forward": 0, "reverse": 0, "both": 0} for role in fused_masks}
    run_dir = job / "anchor-runs" / config_sha[:12]
    final_mask_dir = run_dir / "final"
    overlay_dir = job / "anchor-overlay-frames"
    final_mask_dir.mkdir(exist_ok=True)
    overlay_dir.mkdir(exist_ok=True)
    update(job_id, status="RUNNING", stage="正在合成前后向掩码与逐帧预览", processed=len(anchor_frames) + len(windows))
    for frame in range(sample["frames"]):
        image = Image.open(frame_folder / f"{frame:05d}.jpg").convert("RGB")
        frame_display = {}
        for role in ("NEAR_PLAYER", "FAR_PLAYER"):
            forward_path = _mask_path(job, "forward", role, frame, config_sha)
            reverse_path = _mask_path(job, "reverse", role, frame, config_sha)
            forward = _read_mask(forward_path, frame_size) if forward_path.is_file() else None
            reverse = _read_mask(reverse_path, frame_size) if reverse_path.is_file() else None
            raw_stats[role]["forward"] += int(forward is not None and bool(forward.any()))
            raw_stats[role]["reverse"] += int(reverse is not None and bool(reverse.any()))
            raw_stats[role]["both"] += int(forward is not None and reverse is not None
                                               and bool(forward.any()) and bool(reverse.any()))
            visibility = visibility_by_frame[role][frame]
            fusion = fuse_masks(forward, reverse, visibility=visibility,
                                agreement_iou=MASK_CONFLICT_AGREEMENT_IOU)
            final = fusion["final_mask"]
            if final is not None and bool(final.any()):
                fused_masks[role][frame] = final
                closed_loop_worker.atomic_mask(final, final_mask_dir / role.lower() / f"{frame:05d}.png")
                frame_display[role] = final
            elif visibility in {"VISIBLE", "PARTIAL"}:
                # Keep a diagnostic-only mask visible in the QA overlay; the
                # record continues to mark it as unselected/review-required.
                diagnostic = forward if forward is not None and bool(forward.any()) else reverse
                if diagnostic is not None and bool(diagnostic.any()):
                    frame_display[role] = diagnostic
            mask_area = int(final.sum()) if final is not None else 0
            bbox = closed_loop_worker.bbox_from_mask(final) if final is not None else None
            record = {"frame": frame, "timestamp_ms": round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000),
                      "role": role, "object_id": AnchorGuidedPlayerTracker.OBJECT_IDS[role],
                      "visibility": visibility, "forward_mask_present": bool(forward is not None and forward.any()),
                      "visibility_review_sample": any(window.get("review_frame") == frame for window in visibility_windows),
                      "reverse_mask_present": bool(reverse is not None and reverse.any()),
                      "tracking_status": fusion["status"], "decision": fusion["decision"],
                      "tracking_state": tracking_state(visibility=visibility,
                                                        mask_available=bool(final is not None and final.any())),
                      "mask_source": fusion["source"], "mask_area": mask_area, "bbox": bbox,
                      "fusion_evidence": fusion["evidence"],
                      "source": "SAM2_FORWARD_REVERSE_SHORT_WINDOW",
                      "raw_forward_asset": str(forward_path.relative_to(job)) if forward is not None else None,
                      "raw_reverse_asset": str(reverse_path.relative_to(job)) if reverse is not None else None,
                      "final_asset": str((final_mask_dir / role.lower() / f"{frame:05d}.png").relative_to(job)) if final is not None else None}
            preceding_anchors = [anchor for anchor in anchor_frames if anchor <= frame]
            following_anchors = [anchor for anchor in anchor_frames if anchor >= frame]
            record["forward_source_anchor"] = max(preceding_anchors) if preceding_anchors else None
            record["reverse_source_anchor"] = min(following_anchors) if following_anchors else None
            records.append(record)
        closed_loop_worker.render_overlay(image, frame_display, overlay_dir / f"{frame:05d}.jpg", frame)
        overlay = Image.open(overlay_dir / f"{frame:05d}.jpg")
        draw = ImageDraw.Draw(overlay)
        unknown_roles = [role.replace("_PLAYER", "") for role in ("NEAR_PLAYER", "FAR_PLAYER")
                         if visibility_by_frame[role][frame] == "UNKNOWN"]
        if unknown_roles:
            draw.rectangle((10, 10, min(650, image.width - 10), 42), fill="#273141")
            draw.text((18, 18), "VISIBILITY UNKNOWN · MASKS REQUIRE REVIEW", fill="white")
        overlay.save(overlay_dir / f"{frame:05d}.jpg", quality=90, optimize=True)
        overlay.close()
        image.close()
        if (frame + 1) % 30 == 0:
            update(job_id, status="RUNNING", stage="正在合成逐帧追踪预览", processed=len(anchor_frames) + len(windows) + frame + 1)

    encode = __import__("subprocess").run([
        closed_loop_worker.get_ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-framerate", str(sample["sample_fps"]), "-start_number", "0",
        "-i", str(overlay_dir / "%05d.jpg"), "-frames:v", str(sample["frames"]),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-an", str(job / "anchor_guided_tracking_overlay.mp4"),
    ], capture_output=True, text=True, timeout=180)
    if encode.returncode:
        raise RuntimeError(f"ANCHOR_OVERLAY_ENCODE_FAILED:{encode.stderr[-1000:]}")

    role_summary = {}
    for role in ("NEAR_PLAYER", "FAR_PLAYER"):
        role_rows = [row for row in records if row["role"] == role]
        by_frame = {row["frame"]: row for row in role_rows}
        review_rows = [by_frame[window["review_frame"]] for window in visibility_windows]
        coverage = visibility_coverage([{"visibility": row["visibility"],
                                         "mask_present": bool(row["mask_area"])} for row in review_rows])
        missing_visible_windows = [
            window[role] in {"VISIBLE", "PARTIAL"}
            and by_frame[window["review_frame"]]["mask_area"] == 0
            for window in visibility_windows]
        longest_windows = current_windows = 0
        for missing in missing_visible_windows:
            current_windows = current_windows + 1 if missing else 0
            longest_windows = max(longest_windows, current_windows)
        longest_seconds = round(longest_windows * 0.5, 3)
        role_summary[role] = {
            "frames": len(role_rows), "tracked": sum(row["mask_area"] > 0 for row in role_rows),
            "mask_absent": sum(row["mask_area"] == 0 for row in role_rows),
            "visible_window_samples": coverage["eligible_frames"],
            "visible_mask_window_samples": coverage["mask_available"],
            "visible_window_sample_coverage": coverage["coverage"],
            "out_of_frame_window_samples": coverage["out_of_frame"],
            "unknown_window_samples": coverage["unknown"],
            "longest_missing_visible_window_samples": longest_windows,
            "longest_missing_visible_window_seconds": longest_seconds,
            "raw_forward_mask_frames": raw_stats[role]["forward"],
            "raw_reverse_mask_frames": raw_stats[role]["reverse"],
            "raw_bidirectional_mask_frames": raw_stats[role]["both"],
        }
        conflict_frames = sum(row["decision"] == "FORWARD_REVERSE_CONFLICT" for row in role_rows)
        role_summary[role]["mask_conflict_frames"] = conflict_frames
        if longest_windows and not conflict_frames:
            events.append({"type": "VISIBLE_MASK_GAP", "role": role,
                           "longest_window_samples": longest_windows,
                           "longest_seconds": longest_seconds,
                           "status": "REVIEW_REQUIRED"})
    conflict_events = group_mask_conflicts(records)
    for event in conflict_events:
        for row in records:
            if (row["role"] == event["role"] and
                    event["start_frame"] <= row["frame"] <= event["end_frame"] and
                    row["decision"] == "FORWARD_REVERSE_CONFLICT"):
                row["conflict_id"] = event["event_id"]
        # Keep the review payload compact: one representative frame plus all
        # per-frame raw masks referenced in tracking.json.
        review_frame = int(event["frame"])
        review_record = next(row for row in records
                             if row["role"] == event["role"] and row["frame"] == review_frame)
        review_dir = job / "review-conflicts" / event["role"].lower() / event["event_id"]
        review_dir.mkdir(parents=True, exist_ok=True)
        source_image = Image.open(frame_folder / f"{review_frame:05d}.jpg").convert("RGB")
        source_path = review_dir / "source.jpg"
        source_image.save(source_path, quality=92, optimize=True)
        for direction in ("forward", "reverse"):
            raw_path = job / review_record[f"raw_{direction}_asset"]
            raw_mask = _read_mask(raw_path, frame_size)
            overlay_path = review_dir / f"{direction}.jpg"
            closed_loop_worker.render_overlay(
                source_image, {event["role"]: raw_mask}, overlay_path, review_frame)
            event.setdefault("review_assets", {})[direction] = str(overlay_path.relative_to(job))
        source_image.close()
        event["review_assets"]["source"] = str(source_path.relative_to(job))
        event["review_frame"] = review_frame
        event["forward_source_anchor"] = review_record.get("forward_source_anchor")
        event["reverse_source_anchor"] = review_record.get("reverse_source_anchor")
        events.append(event)
    ambiguous_count = sum(event.get("type") == "IDENTITY_UNCERTAIN" for event in events)
    re_prompt_count = sum(event.get("type") == "AUTO_ANCHOR" for event in events)
    reverse_repairs = sum(row["mask_source"] == "REVERSE" for row in records)
    forward_reverse_agreements = sum(row["mask_source"] == "FORWARD_REVERSE_AGREE" for row in records)
    processed = sample["frames"]
    wall_seconds = time.perf_counter() - started
    torch.cuda.synchronize()
    events.sort(key=lambda row: row.get("timestamp_ms", 0))
    runtime = {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
               "torch_cuda": torch.version.cuda, "model_load_seconds": round(model_load_seconds, 3),
               "rtdetr_anchor_seconds": round(detector_seconds, 3), "rtdetr_calls": detector_calls,
               "sam2_bidirectional_seconds": round(inference_seconds, 3),
               "sam2_forward_anchor_windows": len(windows), "sam2_reverse_anchor_windows": len(windows),
               "elapsed_seconds": round(wall_seconds, 3), "effective_fps": round(processed / max(wall_seconds, .001), 3),
               "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
               "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved())}
    identity_swaps = None  # Semantic identity swaps require independent identity ground truth.
    manual_actions_path = job / "manual-actions.json"
    manual_action_payload = (json.loads(manual_actions_path.read_text(encoding="utf-8"))
                             if manual_actions_path.is_file() else {"actions": []})
    manual_actions = manual_action_payload.get("actions", [])
    if not manual_actions:
        manual_actions = [{"action": "initial_seed", "source": "USER_UI",
                           "frame": int(seed["seed_frame"]), "timestamp": seed.get("created_at")}]
        atomic_json(manual_actions_path, {"schema_version": "player-tracking-manual-actions-v1",
                                          "actions": manual_actions})
    action_summary = summarize_manual_actions(manual_actions, sample["duration_seconds"])
    manifest = {
        "schema_version": "anchor-guided-player-tracking-v1", "status": "ANCHOR_GUIDED_COMPLETE",
        "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING",
        "job_id": job_id, "sample_id": sample["sample_id"], "match_id": sample["match_id"],
        "evaluation_role": sample.get("evaluation_role", "DEVELOPMENT"),
        "frozen_config_sha256": sample.get("validation_config_sha256"),
        "dataset": sample["dataset"], "rights": sample["rights"], "commercial_use": False,
        "source_sha256": sample["clip_sha256"], "source_bytes": sample["bytes"],
        "source_fps": sample["source_fps"], "sample_fps": sample["sample_fps"],
        "duration_seconds": sample["duration_seconds"], "frames": sample["frames"],
        "seed_frame": seed["seed_frame"], "anchor_interval_seconds": interval_seconds,
        "config": {**config_payload, "sha256": config_sha},
        "table_context": table_context, "zones": zones,
        "visibility_truth_status": visibility_status,
        "visibility_truth_sha256": sha256_file(VISIBILITY_PATH) if VISIBILITY_PATH.is_file() else None,
        "anchor_count": len(anchor_frames), "rtdetr_anchor_calls": detector_calls,
        "window_cache_hits": window_cache_hits, "window_cache_misses": window_cache_misses,
        "anchors": raw_anchor_results, "windows": window_rows,
        "role_summary": role_summary,
        "recovery": {"automatic_anchors": re_prompt_count, "sam2_reprompts": re_prompt_count,
                     "reverse_mask_repairs": reverse_repairs,
                     "forward_reverse_agreements": forward_reverse_agreements,
                     "ambiguous_associations": ambiguous_count,
                     "manual_interventions": 0, "identity_swaps_observed": identity_swaps,
                     "identity_swap_note": "fixed object IDs; no frame-level identity ground truth was collected",
                     "manual_actions": action_summary},
        "manual_actions": manual_actions,
        "runtime": runtime, "events": events, "records": records,
        "outputs": {"overlay_video": "anchor_guided_tracking_overlay.mp4", "anchors": "anchors.json",
                    "checkpoints": "checkpoints/", "raw_masks": f"anchor-runs/{config_sha[:12]}/raw/",
                    "final_masks": f"anchor-runs/{config_sha[:12]}/final/"},
        "production_database": "NOT_ACCESSED", "completed_at": closed_loop_worker.now(),
    }
    atomic_json(job / "tracking.json", manifest)
    progress = load_job_progress(job_id)
    progress.update({"status": "COMPLETE", "stage": "锚点追踪完成", "processed_frames": total_steps,
                     "total_steps": total_steps,
                     "events": events, "summary": role_summary, "recovery": manifest["recovery"],
                     "manual_actions": action_summary,
                     "runtime": runtime, "anchor_interval_seconds": interval_seconds,
                     "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING",
                     "visibility_truth_status": visibility_status, "completed_at": closed_loop_worker.now()})
    save_job_progress(job_id, progress)


def command_resolve_conflict(job_id: str, event_id: str, role: str, choice: str,
                             action_id: str, bbox: list[float] | None = None):
    """Re-run only the healthy-anchor → conflict → healthy-anchor local window."""
    import numpy as np
    import torch
    from PIL import Image
    from sam2.build_sam import build_sam2_video_predictor
    from backend.anchor_guided_tracker import validate_mask_conflict_review

    job = (closed_loop_root() / "jobs" / job_id).resolve()
    if not job.is_dir():
        raise FileNotFoundError("CLOSED_LOOP_JOB_NOT_FOUND")
    manifest_path = job / "tracking.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = next((item for item in manifest.get("events", [])
                  if item.get("event_id") == event_id and item.get("type") == "MASK_CONFLICT"), None)
    if event is None:
        raise FileNotFoundError("MASK_CONFLICT_NOT_FOUND")
    sample = resolve_sample(manifest["sample_id"])
    if sample["clip_sha256"] != manifest.get("source_sha256"):
        raise RuntimeError("SOURCE_CHANGED")
    request = validate_mask_conflict_review(
        event=event, role=role, choice=choice, bbox=bbox,
        frame_size=(sample["width"], sample["height"]))
    if choice == "NEITHER":
        raise ValueError("NEITHER_REQUIRES_REBOX_BEFORE_LOCAL_RERUN")
    append_manual_action(
        job_id=job_id,
        action="manual_rebox" if choice == "REBOX" else "mask_choice",
        action_id=action_id,
        details={**request, "event_id": event_id, "role": role, "choice": choice},
        source=("QA_UI" if os.environ.get("PTTI_ENV") == "test"
                or os.environ.get("PTTI_REVIEW_SOURCE") == "QA_UI" else "USER_UI"),
    )

    records = [row for row in manifest.get("records", []) if row.get("role") == role]
    by_frame = {int(row["frame"]): row for row in records}
    start, end, seed_frame = request["start_frame"], request["end_frame"], request["frame"]
    left_options = [frame for frame, row in by_frame.items()
                    if frame < start and row.get("mask_area", 0) > 0
                    and row.get("tracking_status") in {"ACCEPTED", "CANDIDATE"}]
    right_options = [frame for frame, row in by_frame.items()
                     if frame > end and row.get("mask_area", 0) > 0
                     and row.get("tracking_status") in {"ACCEPTED", "CANDIDATE"}]
    if not left_options or not right_options:
        raise RuntimeError("HEALTHY_ANCHORS_NOT_AVAILABLE_AROUND_CONFLICT")
    left, right = max(left_options), min(right_options)
    if not left < seed_frame < right:
        raise RuntimeError("CONFLICT_SEED_OUTSIDE_LOCAL_HEALTHY_WINDOW")

    frame_size = (sample["width"], sample["height"])
    config_sha = manifest.get("config", {}).get("sha256")
    if not isinstance(config_sha, str) or len(config_sha) != 64:
        raise RuntimeError("TRACKING_CONFIG_SHA_MISSING")
    seed_record = next(row for row in manifest["records"]
                       if row.get("role") == role and int(row["frame"]) == seed_frame)
    if choice == "REBOX":
        seed_bbox = list(map(float, bbox))
    else:
        raw_key = "raw_forward_asset" if choice == "FORWARD" else "raw_reverse_asset"
        raw_asset = seed_record.get(raw_key)
        if not raw_asset:
            raise RuntimeError("SELECTED_RAW_MASK_NOT_AVAILABLE")
        seed_mask = _read_mask(job / raw_asset, frame_size)
        seed_bbox = closed_loop_worker.bbox_from_mask(seed_mask)
        if not seed_bbox:
            raise RuntimeError("SELECTED_RAW_MASK_EMPTY_USE_REBOX")
        seed_bbox = list(map(float, seed_bbox))

    def healthy_bbox(frame: int) -> list[float]:
        row = by_frame[frame]
        if row.get("bbox") and len(row["bbox"]) == 4:
            return list(map(float, row["bbox"]))
        asset = row.get("final_asset")
        if not asset:
            raise RuntimeError("HEALTHY_ANCHOR_MASK_MISSING")
        return list(map(float, closed_loop_worker.bbox_from_mask(
            _read_mask(job / asset, frame_size))))

    left_bbox, right_bbox = healthy_bbox(left), healthy_bbox(right)
    decoded = closed_loop_worker.ensure_decoded_frames(sample)
    torch, _ = closed_loop_worker.runtime_metadata()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    predictor = build_sam2_video_predictor(
        str(closed_loop_worker.SAM2_CONFIG), str(closed_loop_worker.SAM2_CHECKPOINT),
        device="cuda", mode="eval", apply_postprocessing=False, vos_optimized=False)
    model_load_seconds = time.perf_counter() - started
    # Windows preview installations can add a long MSIX LocalCache prefix.
    # Keep generated research paths well below MAX_PATH while retaining the
    # full action ID in manifests and audit logs.
    action_root = job / "anchor-runs" / config_sha[:12] / "review" / action_id[:10]
    if action_root.exists():
        raise RuntimeError("REVIEW_ACTION_PATH_COLLISION")
    action_root.mkdir(parents=True, exist_ok=False)
    update = closed_loop_worker.update_progress
    update(job_id, status="RUNNING_REVIEW", stage="正在局部重跑冲突区间；原始前后向证据保持不变",
           review_event_id=event_id, review_action_id=action_id,
           review_window={"start_frame": left, "end_frame": right,
                          "conflict_start_frame": start, "conflict_end_frame": end})
    output_segments = []
    segment_bounds = [(left, seed_frame, {"bbox": left_bbox}, {"bbox": seed_bbox}),
                      (seed_frame, right, {"bbox": seed_bbox}, {"bbox": right_bbox})]
    for segment_index, (segment_left, segment_right, left_prompt, right_prompt) in enumerate(segment_bounds, 1):
        input_dir = _materialize_window_frames(decoded, job, segment_left, segment_right)
        try:
            result = _run_window(
                predictor, input_dir, segment_left, segment_right,
                {role: left_prompt}, {role: right_prompt}, torch, frame_size)
            output_segments.append((segment_left, segment_right, result))
        finally:
            shutil.rmtree(input_dir, ignore_errors=True)
        update(job_id, status="RUNNING_REVIEW", stage=f"局部传播与反向校验 · {segment_index}/2",
               processed=segment_index)

    visibility_windows, visibility_status = load_visibility_windows(sample)
    rerun_root = action_root / "m"
    final_dir = job / "anchor-runs" / config_sha[:12] / "final" / role.lower()
    overlay_dir = job / "anchor-overlay-frames"
    action_outputs = []
    unresolved = 0
    for frame in range(start, end + 1):
        segment = output_segments[0] if frame <= seed_frame else output_segments[1]
        segment_left, _, masks = segment
        local_forward = masks["forward"][role].get(frame)
        local_reverse = masks["reverse"][role].get(frame)
        visibility = visibility_at(visibility_windows, role, frame)
        fused = fuse_masks(local_forward, local_reverse, visibility=visibility,
                           agreement_iou=MASK_CONFLICT_AGREEMENT_IOU)
        output_paths = {}
        for direction, value in (("forward", local_forward), ("reverse", local_reverse)):
            if value is not None:
                direction_dir = "f" if direction == "forward" else "r"
                role_dir = "near" if role == "NEAR_PLAYER" else "far"
                path = rerun_root / direction_dir / role_dir / f"{frame:05d}.png"
                closed_loop_worker.atomic_mask(value, path)
                output_paths[direction] = str(path.relative_to(job))
        row = by_frame[frame]
        row["review_rerun"] = {"action_id": action_id, "choice": choice,
                               "seed_frame": seed_frame, "seed_bbox": seed_bbox,
                               "local_window": {"start_frame": left, "end_frame": right},
                               "raw_assets": output_paths,
                               "decision": fused["decision"],
                               "evidence": fused["evidence"]}
        final_mask = fused["final_mask"]
        if final_mask is not None and bool(final_mask.any()):
            final_path = final_dir / f"{frame:05d}.png"
            closed_loop_worker.atomic_mask(final_mask, final_path)
            row.update({"tracking_status": fused["status"], "decision": "LOCAL_RERUN_" + fused["decision"],
                        "tracking_state": tracking_state(visibility=visibility, mask_available=True),
                        "mask_source": "SAM2_LOCAL_RERUN", "mask_area": int(final_mask.sum()),
                        "bbox": closed_loop_worker.bbox_from_mask(final_mask),
                        "final_asset": str(final_path.relative_to(job)),
                        "resolved_conflict_id": event_id})
        else:
            unresolved += 1
            row.update({"tracking_status": "REVIEW_REQUIRED",
                        "decision": "LOCAL_RERUN_" + fused["decision"],
                        "tracking_state": tracking_state(visibility=visibility, mask_available=False),
                        "mask_source": None, "mask_area": 0, "bbox": None,
                        "final_asset": None})
        other_role = "FAR_PLAYER" if role == "NEAR_PLAYER" else "NEAR_PLAYER"
        masks_for_overlay = {}
        if final_mask is not None and bool(final_mask.any()):
            masks_for_overlay[role] = final_mask
        other_record = next((item for item in manifest["records"]
                             if item.get("role") == other_role and int(item["frame"]) == frame), None)
        if other_record and other_record.get("final_asset"):
            other_mask = _read_mask(job / other_record["final_asset"], frame_size)
            if bool(other_mask.any()):
                masks_for_overlay[other_role] = other_mask
        source_frame = Image.open(decoded / f"{frame:05d}.jpg").convert("RGB")
        closed_loop_worker.render_overlay(source_frame, masks_for_overlay,
                                          overlay_dir / f"{frame:05d}.jpg", frame)
        source_frame.close()
        action_outputs.append({"frame": frame, "decision": row["decision"],
                               "raw_assets": output_paths})

    # The source video stays untouched; only the locally affected overlay frames
    # are regenerated before the combined preview is encoded again.
    ffmpeg = closed_loop_worker.get_ffmpeg()
    encode = __import__("subprocess").run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-framerate", str(sample["sample_fps"]),
        "-start_number", "0", "-i", str(overlay_dir / "%05d.jpg"),
        "-frames:v", str(sample["frames"]), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "21", "-pix_fmt", "yuv420p", "-an",
        str(job / "anchor_guided_tracking_overlay.mp4")],
        capture_output=True, text=True, timeout=180)
    if encode.returncode:
        raise RuntimeError(f"ANCHOR_OVERLAY_ENCODE_FAILED:{encode.stderr[-1000:]}")

    unresolved_rows = [row for row in records if row.get("conflict_id") == event_id
                       and row.get("tracking_status") == "REVIEW_REQUIRED"]
    event["last_review_action"] = {"action_id": action_id, "choice": choice,
                                   "seed_frame": seed_frame, "seed_bbox": seed_bbox,
                                   "local_window": {"start_frame": left, "end_frame": right},
                                   "rerun_frames": len(action_outputs),
                                   "remaining_conflict_frames": len(unresolved_rows),
                                   "completed_at": closed_loop_worker.now()}
    if not unresolved_rows:
        event["status"] = "RESOLVED"
        event["resolution"] = "LOCAL_RERUN"
        event["resolved_at"] = closed_loop_worker.now()
        manifest["events"].append({"type": "MASK_CONFLICT_RESOLVED", "event_id": event_id,
                                   "role": role, "frame": seed_frame,
                                   "timestamp_ms": by_frame[seed_frame]["timestamp_ms"],
                                   "status": "RESOLVED", "source": "USER_UI",
                                   "choice": choice, "local_window": {"start_frame": left,
                                                                          "end_frame": right}})
    else:
        event["status"] = "REVIEW_REQUIRED"
    manual_actions_path = job / "manual-actions.json"
    action_log = json.loads(manual_actions_path.read_text(encoding="utf-8"))
    for item in action_log.get("actions", []):
        if item.get("action_id") == action_id:
            item["status"] = "COMPLETED" if not unresolved_rows else "REVIEW_REQUIRED"
            item["result"] = {"event_id": event_id, "resolved_frames": len(action_outputs) - unresolved,
                              "remaining_conflict_frames": len(unresolved_rows),
                              "local_window": {"start_frame": left, "end_frame": right}}
            break
    atomic_json(manual_actions_path, action_log)
    # Recompute only visible-sample availability; unknown and out-of-frame
    # samples remain excluded exactly as in the original result.
    for item_role in ("NEAR_PLAYER", "FAR_PLAYER"):
        role_rows = [row for row in manifest["records"] if row["role"] == item_role]
        summary = manifest["role_summary"][item_role]
        review_rows = [next(row for row in role_rows if row["frame"] == window["review_frame"])
                       for window in visibility_windows]
        coverage = visibility_coverage([{"visibility": row["visibility"],
                                         "mask_present": bool(row["mask_area"])} for row in review_rows])
        summary["tracked"] = sum(row["mask_area"] > 0 for row in role_rows)
        summary["mask_absent"] = sum(row["mask_area"] == 0 for row in role_rows)
        summary["visible_window_samples"] = coverage["eligible_frames"]
        summary["visible_mask_window_samples"] = coverage["mask_available"]
        summary["visible_window_sample_coverage"] = coverage["coverage"]
        summary["out_of_frame_window_samples"] = coverage["out_of_frame"]
        summary["unknown_window_samples"] = coverage["unknown"]
        current_start = None
        longest_missing_seconds = 0.0
        for window, row in zip(visibility_windows, review_rows):
            missing = (window[item_role] in {"VISIBLE", "PARTIAL"}
                       and row["mask_area"] == 0)
            if missing and current_start is None:
                current_start = float(window["start_seconds"])
            if current_start is not None and (not missing):
                longest_missing_seconds = max(
                    longest_missing_seconds, float(window["start_seconds"]) - current_start)
                current_start = None
        if current_start is not None and visibility_windows:
            longest_missing_seconds = max(
                longest_missing_seconds, float(visibility_windows[-1]["end_seconds"]) - current_start)
        summary["longest_missing_visible_window_seconds"] = round(longest_missing_seconds, 3)
        summary["longest_missing_visible_window_samples"] = round(longest_missing_seconds / 0.5)
        summary["mask_conflict_frames"] = sum(row.get("decision", "").endswith("FORWARD_REVERSE_CONFLICT")
                                               for row in role_rows)
    manifest["manual_actions"] = action_log["actions"]
    manifest["recovery"]["manual_interventions"] = sum(
        row.get("action") != "initial_seed" for row in action_log["actions"])
    manifest["recovery"]["manual_actions"] = summarize_manual_actions(
        action_log["actions"], sample["duration_seconds"])
    manifest["review_reruns"] = manifest.get("review_reruns", [])
    manifest["review_reruns"].append({"action_id": action_id, "event_id": event_id,
                                      "role": role, "choice": choice, "seed_frame": seed_frame,
                                      "local_window": {"start_frame": left, "end_frame": right},
                                      "source_sha256": sample["clip_sha256"],
                                      "rerun_frames": len(action_outputs),
                                      "remaining_conflict_frames": len(unresolved_rows),
                                      "raw_outputs": action_outputs,
                                      "runtime": {"model_load_seconds": round(model_load_seconds, 3),
                                                  "elapsed_seconds": round(time.perf_counter() - started, 3),
                                                  "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                                                  "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved())}})
    manifest["events"] = sorted(manifest["events"], key=lambda row: row.get("timestamp_ms", 0))
    atomic_json(manifest_path, manifest)
    progress = load_job_progress(job_id)
    progress.update({"status": "COMPLETE", "stage": "局部复核处理完成；原始前后向结果仍保留",
                     "events": manifest["events"], "summary": manifest["role_summary"],
                     "recovery": manifest["recovery"], "manual_actions": manifest["recovery"]["manual_actions"],
                     "review_reruns": manifest["review_reruns"],
                     "completed_at": closed_loop_worker.now()})
    save_job_progress(job_id, progress)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["track", "resolve-conflict"])
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--interval-seconds", type=float)
    parser.add_argument("--event-id")
    parser.add_argument("--role")
    parser.add_argument("--choice")
    parser.add_argument("--action-id")
    parser.add_argument("--bbox", nargs=4, type=float)
    args = parser.parse_args()
    try:
        if args.action == "track":
            if args.interval_seconds is None:
                raise ValueError("ANCHOR_INTERVAL_REQUIRED")
            command_track(args.job_id, args.interval_seconds)
        else:
            if not all((args.event_id, args.role, args.choice, args.action_id)):
                raise ValueError("CONFLICT_REVIEW_ARGUMENTS_REQUIRED")
            command_resolve_conflict(args.job_id, args.event_id, args.role, args.choice,
                                     args.action_id, args.bbox)
    except Exception as exc:
        if args.action == "resolve-conflict":
            try:
                root = closed_loop_root() / "jobs" / args.job_id
                action_path = root / "manual-actions.json"
                if action_path.is_file():
                    action_log = json.loads(action_path.read_text(encoding="utf-8"))
                    for row in action_log.get("actions", []):
                        if row.get("action_id") == args.action_id:
                            row["status"] = "FAILED_REVIEW_RETAINED"
                            row["error_code"] = str(exc).split(":", 1)[0]
                    atomic_json(action_path, action_log)
                progress = load_job_progress(args.job_id)
                progress.update({"status": "COMPLETE", "stage": "局部重跑未完成；原始冲突证据保留",
                                 "review_error": str(exc).split(":", 1)[0]})
                save_job_progress(args.job_id, progress)
            except Exception:
                pass
            raise
        try:
            closed_loop_worker.update_progress(args.job_id, status="FAILED",
                                               stage="锚点追踪未完成；原始输入和检查点已保留",
                                               error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
