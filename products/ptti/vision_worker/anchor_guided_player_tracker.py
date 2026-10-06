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
    checkpoint_matches,
    derive_play_zones,
    fuse_masks,
    visibility_coverage,
)
from backend.player_tracking_closed_loop import (  # noqa: E402
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
                event = {"type": "IDENTITY_AMBIGUOUS", "frame": frame,
                         "timestamp_ms": round((sample["start_seconds"] + frame / sample["sample_fps"]) * 1000),
                         "role": role, "object_id": AnchorGuidedPlayerTracker.OBJECT_IDS[role],
                         "candidate_id": result.get("best_candidate", {}).get("candidate_id"),
                         "source": "RTDETR_ASSOCIATION", "status": "REVIEW_REQUIRED",
                         "evidence": result.get("best_candidate", {}).get("evidence", {})}
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
                      "association": orchestrator.config, "sam2_checkpoint_sha256": closed_loop_worker.EXPECTED_SAM2_SHA,
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
            fusion = fuse_masks(forward, reverse, visibility=visibility)
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
                      "mask_source": fusion["source"], "mask_area": mask_area, "bbox": bbox,
                      "fusion_evidence": fusion["evidence"],
                      "source": "SAM2_FORWARD_REVERSE_SHORT_WINDOW",
                      "raw_forward_asset": str(forward_path.relative_to(job)) if forward is not None else None,
                      "raw_reverse_asset": str(reverse_path.relative_to(job)) if reverse is not None else None,
                      "final_asset": str((final_mask_dir / role.lower() / f"{frame:05d}.png").relative_to(job)) if final is not None else None}
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
        if longest_windows:
            events.append({"type": "VISIBLE_MASK_GAP", "role": role,
                           "longest_window_samples": longest_windows,
                           "longest_seconds": longest_seconds,
                           "status": "REVIEW_REQUIRED"})
    ambiguous_count = sum(event.get("type") == "IDENTITY_AMBIGUOUS" for event in events)
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
    manifest = {
        "schema_version": "anchor-guided-player-tracking-v1", "status": "ANCHOR_GUIDED_COMPLETE",
        "job_id": job_id, "sample_id": sample["sample_id"], "match_id": sample["match_id"],
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
                     "identity_swap_note": "fixed object IDs; no frame-level identity ground truth was collected"},
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
                     "runtime": runtime, "anchor_interval_seconds": interval_seconds,
                     "tracking_architecture": "DETECTION_ANCHORED_MASK_TRACKING",
                     "visibility_truth_status": visibility_status, "completed_at": closed_loop_worker.now()})
    save_job_progress(job_id, progress)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("track", choices=["track"])
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--interval-seconds", required=True, type=float)
    args = parser.parse_args()
    try:
        command_track(args.job_id, args.interval_seconds)
    except Exception as exc:
        try:
            closed_loop_worker.update_progress(args.job_id, status="FAILED",
                                               stage="锚点追踪未完成；原始输入和检查点已保留",
                                               error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
