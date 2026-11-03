"""Isolated RT-DETR + SAM 2.1 closed-loop runner for PTTI-Dev research clips."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_ROOT = Path(os.environ["PTTI_PRODUCT_ROOT"]).resolve()
LOCAL = Path(os.environ["LOCALAPPDATA"]).resolve()
RUNTIME_ROOT = LOCAL / "PTTI-Dev" / "vision-v2-sam2"
SAMPLE_ROOT = RUNTIME_ROOT / "datasets" / "extended-openttgames"
RTDETR_ROOT = LOCAL / "PTTI-Dev" / "vision-v2" / "models" / "rtdetr-r18vd"
SAM2_REPO = RUNTIME_ROOT / "sam2"
SAM2_CHECKPOINT = RUNTIME_ROOT / "checkpoints" / "sam2.1_hiera_small.pt"
SAM2_CONFIG = SAM2_REPO / "sam2" / "configs" / "sam2.1" / "sam2.1_hiera_s.yaml"
LOCKED_CONFIG = RUNTIME_ROOT / "tracker_config.json"
EXPECTED_R18_SHA = "fe87a5a30f5daf298d10794c7682a63b6107986f97d6a770ba948d89e4340093"
EXPECTED_SAM2_SHA = "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"
EXPECTED_CONFIG_SHA = "592306d059a2df49898fefcb939c11abc9dfc8fd962bc77c31d132e68cb4320a"
EXPECTED_TRACKER_SHA = "9f2cc04ed25e935b6edb53fa296203a5091dabe9ff7ae349d77ce538dbb914bd"
EXPECTED_SAM2_COMMIT = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
EXPECTED_R18_REVISION = "ac77a11ff0170a41b771c03264987f8ce2b0d753"
WATCHDOG_INTERVAL = 30

sys.path.insert(0, str(PRODUCT_ROOT))
sys.path.insert(0, str(SAM2_REPO))
sys.path.insert(0, str(LOCAL / "PTTI-Dev" / "vision-v2" / "venv" / "Lib" / "site-packages"))

from backend.player_tracking_closed_loop import (  # noqa: E402
    atomic_json,
    closed_loop_root,
    load_job_progress,
    resolve_sample,
    save_job_progress,
)
from backend.player_tracking_loop import (  # noqa: E402
    RecoveryEpisodeGate,
    candidate_identifier,
    choose_reassociation,
    classify_track_health,
    tracking_status_for,
)


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_metadata():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("ISOLATED_GPU_RUNTIME_UNAVAILABLE")
    if not SAM2_REPO.is_dir() or not SAM2_CHECKPOINT.is_file() or not SAM2_CONFIG.is_file():
        raise RuntimeError("PINNED_SAM2_ARTIFACT_MISSING")
    if file_sha(SAM2_CHECKPOINT) != EXPECTED_SAM2_SHA:
        raise RuntimeError("SAM2_CHECKPOINT_SHA_MISMATCH")
    if file_sha(SAM2_CONFIG) != EXPECTED_CONFIG_SHA:
        raise RuntimeError("SAM2_MODEL_CONFIG_SHA_MISMATCH")
    if file_sha(LOCKED_CONFIG) != EXPECTED_TRACKER_SHA:
        raise RuntimeError("FROZEN_BALLTRACK_CONFIG_SHA_MISMATCH")
    commit = subprocess.check_output(["git", "-C", str(SAM2_REPO), "rev-parse", "HEAD"], text=True).strip()
    if commit != EXPECTED_SAM2_COMMIT:
        raise RuntimeError("SAM2_SOURCE_COMMIT_MISMATCH")
    return torch, commit


def get_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFMPEG_NOT_AVAILABLE_IN_ISOLATED_WORKER")
    return found


def decoded_frame_root(sample: dict) -> Path:
    key = f"{sample['sample_id']}-{sample['clip_sha256']}"
    return closed_loop_root() / "decoded-cache" / key


def ensure_decoded_frames(sample: dict) -> Path:
    source = Path(sample["video_path"])
    if not source.is_file() or file_sha(source) != sample["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")
    output = decoded_frame_root(sample)
    marker = output / "decode.json"
    frames = sorted(output.glob("*.jpg"), key=lambda item: int(item.stem)) if output.is_dir() else []
    if marker.is_file() and len(frames) == sample["frames"]:
        metadata = json.loads(marker.read_text(encoding="utf-8"))
        if metadata.get("clip_sha256") == sample["clip_sha256"] and metadata.get("frames") == len(frames):
            return output
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg()
    pattern = output / "%05d.jpg"
    result = subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", f"fps={sample['sample_fps']}", "-frames:v", str(sample["frames"]),
        "-start_number", "0", "-q:v", "2", "-an", str(pattern),
    ], capture_output=True, text=True, timeout=180)
    frames = sorted(output.glob("*.jpg"), key=lambda item: int(item.stem))
    if result.returncode or len(frames) != sample["frames"]:
        raise RuntimeError(f"FRAME_DECODE_FAILED:{result.stderr[-1000:]}:count={len(frames)}")
    atomic_json(marker, {"sample_id": sample["sample_id"], "clip_sha256": sample["clip_sha256"],
                         "frames": len(frames), "sample_fps": sample["sample_fps"], "created_at": now()})
    return output


def load_rtdetr(torch):
    from backend.person_detector import R18_FILES, verify_r18
    from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

    if not RTDETR_ROOT.is_dir():
        raise RuntimeError("RTDETR_CHECKPOINT_MISSING")
    provenance = verify_r18(RTDETR_ROOT)
    if provenance["revision"] != EXPECTED_R18_REVISION or R18_FILES["model.safetensors"] != EXPECTED_R18_SHA:
        raise RuntimeError("RTDETR_PROVENANCE_MISMATCH")
    processor = RTDetrImageProcessor.from_pretrained(RTDETR_ROOT, local_files_only=True)
    model = RTDetrForObjectDetection.from_pretrained(RTDETR_ROOT, local_files_only=True).eval().to("cuda")
    torch.cuda.synchronize()
    return processor, model, provenance


def detect_people(image, *, frame_index: int, timestamp_ms: int, torch, processor, model,
                  threshold: float = 0.4) -> list[dict]:
    from backend.person_detector import RTDetrPredictionAdapter

    inputs = processor(images=image, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        outputs = model(**inputs)
    found = processor.post_process_object_detection(
        outputs,
        target_sizes=torch.tensor([[image.height, image.width]], device="cuda"),
        threshold=threshold,
    )[0]
    raw = []
    for score, label, box in zip(found["scores"], found["labels"], found["boxes"]):
        raw.append({"label": model.config.id2label[int(label)], "score": float(score),
                    "bbox": [float(value) for value in box]})
    return RTDetrPredictionAdapter().adapt(raw, image_size=image.size, frame=frame_index,
                                            timestamp_ms=timestamp_ms, threshold=threshold)


def annotate_detection_image(image, detections):
    from PIL import ImageDraw
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    for item in detections:
        box = item["bbox"]
        draw.rectangle(box, outline="#ffd166", width=5)
        draw.text((box[0], max(0, box[1] - 24)),
                  f"{item['candidate_id']}  {item['detector_score']:.2f}",
                  fill="white", stroke_width=2, stroke_fill="black")
    return canvas


def command_detect_seed(sample_id: str, frame_index: int, detection_set_id: str):
    import torch
    from PIL import Image
    from backend.player_tracking_closed_loop import seed_detection_dir

    sample = resolve_sample(sample_id)
    if file_sha(Path(sample["video_path"])) != sample["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")
    frames_dir = ensure_decoded_frames(sample)
    frame_path = frames_dir / f"{frame_index:05d}.jpg"
    if not frame_path.is_file():
        raise RuntimeError("SEED_FRAME_NOT_DECODED")
    output = seed_detection_dir(sample_id, frame_index, detection_set_id)
    output.mkdir(parents=True, exist_ok=False)
    image = Image.open(frame_path).convert("RGB")
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    processor, model, provenance = load_rtdetr(torch)
    load_seconds = time.perf_counter() - started
    inference_started = time.perf_counter()
    detections = detect_people(image, frame_index=frame_index,
                               timestamp_ms=round((sample["start_seconds"] + frame_index / sample["sample_fps"]) * 1000),
                               torch=torch, processor=processor, model=model)
    torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - inference_started
    image.save(output / "seed-frame.jpg", quality=94)
    annotate_detection_image(image, detections).save(output / "seed-overlay.jpg", quality=94)
    atomic_json(output / "detections.json", {
        "detection_set_id": detection_set_id, "sample_id": sample_id,
        "frame_index": frame_index, "clip_sha256": sample["clip_sha256"],
        "width": image.width, "height": image.height, "detections": detections,
        "detector": provenance, "detector_score_semantics": "RT-DETR detector output; not a calibrated probability",
        "runtime": {"device": torch.cuda.get_device_name(0), "load_seconds": round(load_seconds, 3),
                    "inference_seconds": round(inference_seconds, 3),
                    "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated())},
        "created_at": now(),
    })


def bbox_from_mask(mask):
    import numpy as np
    ys, xs = np.nonzero(mask)
    return None if len(xs) == 0 else [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def atomic_mask(mask, path: Path):
    import numpy as np
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(path, optimize=True)


def render_overlay(image, masks, path: Path, frame_index: int):
    import numpy as np
    from PIL import Image, ImageDraw
    base = image.convert("RGBA")
    colors = {"NEAR_PLAYER": (255, 78, 95), "FAR_PLAYER": (33, 210, 164)}
    for role, mask in masks.items():
        layer = Image.new("RGBA", base.size, colors[role] + (0,))
        layer.putalpha(Image.fromarray(mask.astype(np.uint8) * 100, mode="L"))
        base = Image.alpha_composite(base, layer)
    result = base.convert("RGB")
    draw = ImageDraw.Draw(result)
    for role, mask in masks.items():
        bbox = bbox_from_mask(mask)
        if bbox:
            draw.rectangle(bbox, outline=colors[role], width=3)
            draw.text((bbox[0], max(0, bbox[1] - 22)), role, fill="white", stroke_width=2, stroke_fill="black")
    result.save(path, quality=90, optimize=True)


def mask_from_output(value, shape):
    import numpy as np
    array = value.detach().float().cpu().numpy()
    array = array[0] if array.ndim == 3 else array
    mask = array > 0
    if mask.shape != shape:
        # SAM2 may return model resolution; align to the source raster by nearest-neighbour.
        from PIL import Image
        mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize((shape[1], shape[0]), Image.Resampling.NEAREST)) > 0
    return mask


def extrapolated_box(history):
    if not history:
        return None
    last = history[-1]["bbox"]
    if len(history) < 2:
        return last
    previous = history[-2]["bbox"]
    dx = ((last[0] + last[2]) - (previous[0] + previous[2])) / 2
    dy = ((last[1] + last[3]) - (previous[1] + previous[3])) / 2
    return [last[0] + dx, last[1] + dy, last[2] + dx, last[3] + dy]


def update_progress(job_id, *, status=None, stage=None, processed=None, total_steps=None,
                    event=None, error=None, review_event_id=None, review_action_id=None,
                    review_window=None):
    progress = load_job_progress(job_id)
    if status is not None:
        progress["status"] = status
    if stage is not None:
        progress["stage"] = stage
    if processed is not None:
        progress["processed_frames"] = processed
    if total_steps is not None:
        progress["total_steps"] = total_steps
    if review_event_id is not None:
        progress["review_event_id"] = review_event_id
    if review_action_id is not None:
        progress["review_action_id"] = review_action_id
    if review_window is not None:
        progress["review_window"] = review_window
    if event is not None:
        progress.setdefault("events", []).append(event)
    if error is not None:
        if error:
            progress["error"] = str(error)[:1000]
        else:
            progress.pop("error", None)
    progress["updated_at"] = now()
    save_job_progress(job_id, progress)
    return progress


def detector_candidates(image, frame_idx, start_seconds, fps, torch, processor, model):
    timestamp = round((start_seconds + frame_idx / fps) * 1000)
    return detect_people(image, frame_index=frame_idx, timestamp_ms=timestamp,
                         torch=torch, processor=processor, model=model)


def wait_for_manual_command(job_root: Path, job_id: str, *, role_rankings, frame_idx, timestamp_ms,
                            detections, image, requested_role, timeout_seconds=3600):
    candidate_ids_by_role = {
        role: [row["candidate_id"] for row in ranking.get("ranked", [])]
        for role, ranking in role_rankings.items()
    }
    candidates = {"frame_index": frame_idx, "timestamp_ms": timestamp_ms,
                  "requested_role": requested_role,
                  "candidate_ids_by_role": candidate_ids_by_role,
                  "role_rankings": role_rankings, "detections": detections}
    atomic_json(job_root / "review_candidates.json", candidates)
    review_dir = job_root / "review-frames"
    review_dir.mkdir(exist_ok=True)
    annotate_detection_image(image, detections).save(review_dir / f"{frame_idx:05d}.jpg", quality=94)
    update_progress(job_id, status="NEEDS_USER_CONFIRMATION", stage="等待用户确认追丢后的球员身份",
                    event={"type": "IDENTITY_UNCERTAIN", "frame": frame_idx,
                           "timestamp_ms": timestamp_ms, "source": "SAM2_HEALTH_AND_RTDETR",
                           "candidate_count": len(detections)})
    command_path = job_root / "reacquisition-command.json"
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        if command_path.is_file():
            try:
                command = json.loads(command_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                time.sleep(0.2)
                continue
            command_path.unlink(missing_ok=True)
            role = command.get("role")
            allowed = candidate_ids_by_role.get(role, [])
            row = next((item for item in detections if item["candidate_id"] == command.get("candidate_id")), None)
            if (command.get("action") == "MANUAL_REACQUIRE" and command.get("frame") == frame_idx
                    and row and role in {"NEAR_PLAYER", "FAR_PLAYER"}
                    and command.get("candidate_id") in allowed):
                return command, row
        time.sleep(0.2)
    raise TimeoutError("USER_REACQUISITION_TIMEOUT")


def command_track(job_id: str):
    import numpy as np
    import torch
    from PIL import Image
    from sam2.build_sam import build_sam2_video_predictor

    job = closed_loop_root() / "jobs" / job_id
    job = job.resolve()
    seed = json.loads((job / "seed.json").read_text(encoding="utf-8"))
    sample = resolve_sample(seed["sample_id"])
    source = Path(sample["video_path"])
    if file_sha(source) != seed["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")
    decoded = ensure_decoded_frames(sample)
    frame_folder = job / "frames"
    frame_folder.mkdir(exist_ok=False)
    frame_paths = []
    for index in range(sample["frames"]):
        src = decoded / f"{index:05d}.jpg"
        dst = frame_folder / f"{index:05d}.jpg"
        shutil.copy2(src, dst)
        frame_paths.append(dst)
    if file_sha(source) != seed["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")

    torch, sam2_commit = runtime_metadata()
    torch.cuda.reset_peak_memory_stats()
    initial = time.perf_counter()
    predictor = build_sam2_video_predictor(str(SAM2_CONFIG), str(SAM2_CHECKPOINT), device="cuda",
                                           mode="eval", apply_postprocessing=False, vos_optimized=False)
    processor, detector, rtdetr_provenance = load_rtdetr(torch)
    model_load_seconds = time.perf_counter() - initial
    update_progress(job_id, status="RUNNING", stage="初始化视频与双模型状态")
    state = predictor.init_state(str(frame_folder), offload_video_to_cpu=True,
                                 offload_state_to_cpu=True, async_loading_frames=False)
    selected = seed["selected_seeds"]
    for item in selected:
        predictor.add_new_points_or_box(state, frame_idx=seed["seed_frame"],
                                        obj_id=item["object_id"], box=item["bbox"])

    role_by_id = {int(item["object_id"]): item["role"] for item in selected}
    seed_bbox = {item["role"]: item["bbox"] for item in selected}
    detection_history = {role: [] for role in role_by_id.values()}
    last_mask_bbox = {role: None for role in role_by_id.values()}
    previous_mask_bbox = {role: None for role in role_by_id.values()}
    previous_mask_area = {role: None for role in role_by_id.values()}
    records_by_frame = {}
    progress_at_start = load_job_progress(job_id)
    events = list(progress_at_start.get("events", []))
    if not any(event.get("type") == "INITIAL_SEED" for event in events):
        initial_seed_event = {"type": "INITIAL_SEED", "frame": seed["seed_frame"],
                              "timestamp_ms": seed["timestamp_ms"], "source": "USER_UI",
                              "object_ids": {"NEAR_PLAYER": 1, "FAR_PLAYER": 2},
                              "seed_sources": [item["source"] for item in selected]}
        events.append(initial_seed_event)
        update_progress(job_id, status="RUNNING", stage="已读取人工确认的双球员种子",
                        processed=0, event=initial_seed_event)
    overlay_dir = job / "overlay-frames"
    mask_dir = job / "masks"
    overlay_dir.mkdir()
    started = time.perf_counter()
    inference_seconds = 0.0
    detector_seconds = 0.0
    detector_calls = 0
    re_prompts = 0
    manual_reacquisitions = 0
    auto_reacquisitions = 0
    loss_events = 0
    review_events = 0
    processed = set()
    cut_detector = None
    scene_cut_candidates = []
    recovery_gate = RecoveryEpisodeGate(retry_interval=WATCHDOG_INTERVAL, healthy_reset_frames=3)
    try:
        from backend.vision_v2 import SceneBoundaryDetector
        cut_detector = SceneBoundaryDetector()
    except Exception:
        cut_detector = None

    def run_detections(image, frame_idx):
        nonlocal detector_seconds, detector_calls
        started_detector = time.perf_counter()
        raw = detector_candidates(image, frame_idx, sample["start_seconds"], sample["sample_fps"], torch, processor, detector)
        torch.cuda.synchronize()
        detector_seconds += time.perf_counter() - started_detector
        detector_calls += 1
        return raw

    def process_output(frame_idx, object_ids, video_masks, *, direction="FORWARD"):
        nonlocal inference_seconds, re_prompts, manual_reacquisitions, auto_reacquisitions
        nonlocal loss_events, review_events
        if frame_idx in processed:
            return
        processed.add(frame_idx)
        image = Image.open(frame_paths[frame_idx]).convert("RGB")
        shape = (image.height, image.width)
        scene_cut = None
        if direction == "FORWARD" and cut_detector is not None:
            scene_cut = cut_detector.observe(
                frame_idx,
                round((sample["start_seconds"] + frame_idx / sample["sample_fps"]) * 1000),
                np.asarray(image.convert("RGB")),
            )
            if scene_cut:
                scene_cut_candidates.append(asdict(scene_cut))
                scene_event = {"type": "SCENE_RESET", "frame": frame_idx,
                               "timestamp_ms": round((sample["start_seconds"] + frame_idx / sample["sample_fps"]) * 1000),
                               "source": "SCENE_BOUNDARY_DETECTOR", "evidence": asdict(scene_cut)}
                events.append(scene_event)
                recovery_gate.reset_for_scene_change()
                update_progress(job_id, status="RUNNING", stage="发现镜头切换，准备重新检测球员",
                                event=scene_event)
        mask_by_role = {}
        frame_records = []
        frame_health = {}
        array = video_masks.detach().float().cpu().numpy()
        for position, object_id in enumerate([int(value) for value in object_ids]):
            role = role_by_id.get(object_id)
            if not role:
                raise RuntimeError("SAM2_RETURNED_UNKNOWN_OBJECT_ID")
            mask = mask_from_output(torch.from_numpy(array[position]), shape)
            bbox = bbox_from_mask(mask)
            area = int(mask.sum())
            if direction == "FORWARD":
                health = classify_track_health(
                    bbox=bbox, mask_area=area, frame_size=(image.width, image.height),
                    previous_bbox=last_mask_bbox[role], previous_area=previous_mask_area[role],
                    other_bbox=next((last_mask_bbox[other] for other in role_by_id.values() if other != role), None),
                    previous_previous_bbox=previous_mask_bbox[role],
                )
                frame_health[role] = health
                previous_mask_bbox[role] = last_mask_bbox[role]
                if bbox:
                    last_mask_bbox[role] = bbox
                previous_mask_area[role] = area
            else:
                health = {"status": "HEALTH_NOT_ASSESSED_REVERSE", "reason": "REVERSE_SEED_PROPAGATION"}
            mask_by_role[role] = mask
            mask_asset = f"masks/{role.lower()}/{frame_idx:05d}.png"
            atomic_mask(mask, job / mask_asset)
            timestamp_ms = round((sample["start_seconds"] + frame_idx / sample["sample_fps"]) * 1000)
            status = tracking_status_for(frame_index=frame_idx, seed_frame=seed["seed_frame"],
                                         mask_area=area, health_status=health["status"],
                                         direction=direction)
            frame_records.append({
                "frame": frame_idx, "timestamp_ms": timestamp_ms,
                "tracking_direction": direction,
                "object_id": object_id, "role": role, "bbox": bbox, "mask_area": area,
                "mask_area_ratio": round(area / max(1, image.width * image.height), 6),
                "tracking_status": status, "health": health,
                "source": "USER_CONFIRMED_SEED" if frame_idx == seed["seed_frame"] else "SAM2_PROPAGATED",
                "mask_asset": mask_asset, "detector_observation": None,
                "decision": "SEED_ACCEPTED" if frame_idx == seed["seed_frame"] else "SAM2_PROPAGATED",
                "reason": health["reason"],
            })
        def record_reprompt(role, candidate, *, source, reason):
            row = next(item for item in frame_records if item["role"] == role)
            event = {"type": "SAM2_REPROMPT", "frame": frame_idx,
                     "timestamp_ms": row["timestamp_ms"], "role": role,
                     "object_id": row["object_id"],
                     "old_state": {"tracking_status": row["tracking_status"],
                                   "health": row["health"], "bbox": row["bbox"]},
                     "new_bbox": list(candidate["bbox"]), "reason": reason,
                     "source": source}
            events.append(event)
            update_progress(job_id, status="RUNNING", stage="以原 object ID 重新提示 SAM2",
                            event=event)

        if direction == "FORWARD":
            for role, value in frame_health.items():
                recovery_gate.observe(role, value["status"], frame=frame_idx)
            health_by_role = {role: value["status"] for role, value in frame_health.items()}
            needs_recovery = recovery_gate.due_roles(health_by_role, frame=frame_idx)
            if scene_cut:
                needs_recovery = list(role_by_id.values())
            recovery_gate.mark_attempts(needs_recovery, frame=frame_idx)
            due_watchdog = frame_idx > seed["seed_frame"] and frame_idx % WATCHDOG_INTERVAL == 0
            if due_watchdog or needs_recovery:
                detections = run_detections(image, frame_idx)
                choices = {}
                for role in role_by_id.values():
                    history = detection_history[role]
                    choices[role] = choose_reassociation(
                        role=role, candidates=detections,
                        previous_bbox=history[-1]["bbox"] if history else None,
                        predicted_bbox=extrapolated_box(history), seed_bbox=seed_bbox[role],
                        frame_size=(image.width, image.height),
                    )
                # Detector observations corroborate healthy masks on watchdog frames.
                if due_watchdog and not needs_recovery:
                    best_ids = [candidate_identifier(choices[role])
                                for role in role_by_id.values()]
                    if len(best_ids) == 2 and best_ids[0] and best_ids[0] == best_ids[1]:
                        review_events += 1
                        target_role = min(
                            role_by_id.values(),
                            key=lambda role: max((row["association"]["score"]
                                                  for row in choices[role].get("ranked", [])), default=0.0),
                        )
                        event = {"type": "IDENTITY_UNCERTAIN", "frame": frame_idx,
                                 "timestamp_ms": frame_records[0]["timestamp_ms"],
                                 "source": "RTDETR_WATCHDOG", "evidence": "SAME_PERSON_CANDIDATE_FOR_BOTH_FIXED_OBJECT_IDS"}
                        if recovery_gate.may_request_review(target_role, frame=frame_idx):
                            recovery_gate.mark_review_requested(target_role, frame=frame_idx)
                            events.append(event)
                            command, candidate = wait_for_manual_command(
                                job, job_id, role_rankings=choices, frame_idx=frame_idx,
                                timestamp_ms=event["timestamp_ms"], detections=detections, image=image,
                                requested_role=target_role)
                            role = command["role"]
                            recovery_gate.mark_review_requested(role, frame=frame_idx)
                            predictor.add_new_points_or_box(state, frame_idx=frame_idx,
                                                            obj_id=command["object_id"], box=candidate["bbox"])
                            detection_history[role].append(candidate)
                            record_reprompt(role, candidate, source="USER_UI",
                                            reason="WATCHDOG_IDENTITY_COLLISION")
                            manual_reacquisitions += 1
                            re_prompts += 1
                            events.append({"type": "MANUAL_REACQUIRED", "frame": frame_idx,
                                           "timestamp_ms": event["timestamp_ms"], "role": role,
                                           "object_id": command["object_id"], "candidate_id": candidate["candidate_id"],
                                           "source": "USER_CONFIRMED_SEED"})
                            update_progress(job_id, status="RUNNING", stage="已人工确认，继续传播",
                                            event=events[-1])
                    else:
                        for role in role_by_id.values():
                            choice = choices[role]
                            candidate = choice.get("candidate")
                            if candidate and choice["decision"] == "AUTO_REACQUIRED":
                                if all(item.get("candidate_id") != candidate["candidate_id"]
                                       for item in detection_history[role][-2:]):
                                    detection_history[role].append(candidate)
                for role in needs_recovery:
                    choice = choices[role]
                    candidate = choice.get("candidate")
                    if choice["decision"] == "AUTO_REACQUIRED" and candidate:
                        other_role = "FAR_PLAYER" if role == "NEAR_PLAYER" else "NEAR_PLAYER"
                        other_choice = choices[other_role]
                        if candidate_identifier(other_choice) == candidate["candidate_id"]:
                            choice = {"decision": "REQUIRES_USER_CONFIRMATION", "ranked": choice.get("ranked", [])}
                    if choice["decision"] == "AUTO_REACQUIRED" and candidate:
                        predictor.add_new_points_or_box(state, frame_idx=frame_idx,
                                                        obj_id=1 if role == "NEAR_PLAYER" else 2,
                                                        box=candidate["bbox"])
                        detection_history[role].append(candidate)
                        record_reprompt(role, candidate, source="RTDETR_R18",
                                        reason="TRACK_HEALTH_RECOVERY")
                        auto_reacquisitions += 1
                        re_prompts += 1
                        event = {"type": "AUTO_REACQUIRED", "frame": frame_idx,
                                 "timestamp_ms": frame_records[0]["timestamp_ms"], "role": role,
                                 "object_id": 1 if role == "NEAR_PLAYER" else 2,
                                 "candidate_id": candidate["candidate_id"],
                                 "source": "RTDETR_R18", "association": choice["candidate"]["association"]}
                        events.append(event)
                        update_progress(job_id, status="RUNNING", stage="检测到追踪异常并自动重新关联",
                                        event=event)
                    elif choice.get("ranked"):
                        if not recovery_gate.may_request_review(role, frame=frame_idx):
                            choice["decision"] = "REVIEW_ALREADY_REQUESTED_FOR_EPISODE"
                            continue
                        review_events += 1
                        recovery_gate.mark_review_requested(role, frame=frame_idx)
                        command, candidate = wait_for_manual_command(
                            job, job_id, role_rankings=choices, frame_idx=frame_idx,
                            timestamp_ms=frame_records[0]["timestamp_ms"], detections=detections, image=image,
                            requested_role=role)
                        role = command["role"]
                        recovery_gate.mark_review_requested(role, frame=frame_idx)
                        predictor.add_new_points_or_box(state, frame_idx=frame_idx,
                                                        obj_id=command["object_id"], box=candidate["bbox"])
                        detection_history[role].append(candidate)
                        record_reprompt(role, candidate, source="USER_UI",
                                        reason="USER_CONFIRMED_REASSOCIATION")
                        manual_reacquisitions += 1
                        re_prompts += 1
                        event = {"type": "MANUAL_REACQUIRED", "frame": frame_idx,
                                 "timestamp_ms": frame_records[0]["timestamp_ms"], "role": role,
                                 "object_id": command["object_id"], "candidate_id": candidate["candidate_id"],
                                 "source": "USER_UI"}
                        events.append(event)
                        update_progress(job_id, status="RUNNING", stage="已人工确认，继续传播", event=event)
                    elif choice["decision"] == "NO_CANDIDATE":
                        if recovery_gate.mark_loss_reported(role):
                            event_type = "OUT_OF_FRAME" if frame_health[role]["status"] == "OUT_OF_FRAME" else "TRACK_LOST"
                            event = {"type": event_type, "frame": frame_idx,
                                     "timestamp_ms": frame_records[0]["timestamp_ms"], "role": role,
                                     "object_id": 1 if role == "NEAR_PLAYER" else 2,
                                     "source": "SAM2_HEALTH_AND_RTDETR", "evidence": frame_health[role]}
                            events.append(event)
                            loss_events += int(event_type == "TRACK_LOST")
                            update_progress(job_id, status="RUNNING", stage="追踪状态已记录，继续检查后续帧",
                                            event=event)
                        else:
                            choice["decision"] = "LOSS_ALREADY_REPORTED_FOR_EPISODE"
                for row in frame_records:
                    row["detector_observation"] = detections
                    if row["role"] in needs_recovery:
                        row["decision"] = choices[row["role"]]["decision"]
                        row["reason"] = frame_health[row["role"]]["reason"]
        render_overlay(image, mask_by_role, overlay_dir / f"{frame_idx:05d}.jpg", frame_idx)
        records_by_frame[frame_idx] = frame_records
        if frame_idx % 10 == 0:
            update_progress(job_id, processed=len(processed), stage=f"SAM2 传播中 · {len(processed)}/{sample['frames']} 帧")

    try:
        import numpy as np
        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            for frame_idx, object_ids, video_masks in predictor.propagate_in_video(
                    state, start_frame_idx=seed["seed_frame"], max_frame_num_to_track=sample["frames"] - 1):
                started_infer = time.perf_counter()
                process_output(int(frame_idx), object_ids, video_masks)
                torch.cuda.synchronize()
                inference_seconds += time.perf_counter() - started_infer
            if seed["seed_frame"] > 0:
                for frame_idx, object_ids, video_masks in predictor.propagate_in_video(
                        state, start_frame_idx=seed["seed_frame"],
                        max_frame_num_to_track=seed["seed_frame"], reverse=True):
                    started_infer = time.perf_counter()
                    process_output(int(frame_idx), object_ids, video_masks, direction="REVERSE")
                    torch.cuda.synchronize()
                    inference_seconds += time.perf_counter() - started_infer
    finally:
        try:
            predictor.reset_state(state)
        except Exception:
            pass
    if len(processed) != sample["frames"]:
        raise RuntimeError(f"OUTPUT_FRAME_COVERAGE_INVALID:{len(processed)}/{sample['frames']}")
    source_after = file_sha(source)
    if source_after != seed["clip_sha256"]:
        raise RuntimeError("SOURCE_CHANGED")
    records = [row for idx in sorted(records_by_frame) for row in
               sorted(records_by_frame[idx], key=lambda item: item["object_id"])]
    if len(records) != sample["frames"] * 2:
        raise RuntimeError("OUTPUT_OBJECT_FRAME_COUNT_INVALID")
    timestamps = [row["timestamp_ms"] for row in records[::2]]
    if timestamps != sorted(set(timestamps)):
        raise RuntimeError("OUTPUT_TIMELINE_INVALID")
    encode = subprocess.run([
        get_ffmpeg(), "-hide_banner", "-loglevel", "error", "-framerate", str(sample["sample_fps"]),
        "-start_number", "0", "-i", str(overlay_dir / "%05d.jpg"), "-frames:v", str(sample["frames"]),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-an", str(job / "player_tracking_overlay.mp4"),
    ], capture_output=True, text=True, timeout=180)
    if encode.returncode:
        raise RuntimeError(f"OVERLAY_ENCODE_FAILED:{encode.stderr[-1000:]}")
    summary = {}
    for role in ("NEAR_PLAYER", "FAR_PLAYER"):
        rows = [row for row in records if row["role"] == role]
        summary[role] = {"object_id": 1 if role == "NEAR_PLAYER" else 2,
                         "frames": len(rows),
                         "tracked": sum(row["mask_area"] > 0 for row in rows),
                         "mask_absent": sum(row["mask_area"] <= 0 for row in rows),
                         "lost": sum(row["tracking_status"] == "LOST" for row in rows),
                         "suspect": sum(row["tracking_status"] == "SUSPECT" for row in rows),
                         "out_of_frame": sum(row["tracking_status"] == "OUT_OF_FRAME" for row in rows),
                         "unassessed_reverse": sum(row["tracking_status"] == "HEALTH_NOT_ASSESSED_REVERSE" for row in rows),
                         "tracked_reverse": sum(row["tracking_status"] == "TRACKED_REVERSE" for row in rows)}
    runtime = {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
               "torch_cuda": torch.version.cuda, "sam2_model_load_seconds": round(model_load_seconds, 3),
               "sam2_and_detector_inference_seconds": round(inference_seconds, 3),
               "rtdetr_re_detection_seconds": round(detector_seconds, 3),
               "rtdetr_watchdog_calls": detector_calls, "watchdog_interval_frames": WATCHDOG_INTERVAL,
               "re_prompts": re_prompts, "elapsed_seconds": round(time.perf_counter() - started, 3),
               "effective_fps": round(len(processed) / max(0.001, time.perf_counter() - started), 3),
               "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
               "peak_vram_reserved_bytes": int(torch.cuda.max_memory_reserved())}
    manifest = {"schema_version": "player-tracking-closed-loop-v1", "status": "CLOSED_LOOP_COMPLETE",
                "job_id": job_id, "sample_id": sample["sample_id"], "match_id": sample["match_id"],
                "dataset": sample["dataset"], "rights": sample["rights"], "commercial_use": False,
                "source_sha256": sample["clip_sha256"], "source_bytes": sample["bytes"],
                "source_fps": sample["source_fps"], "sample_fps": sample["sample_fps"],
                "duration_seconds": sample["duration_seconds"], "frames": sample["frames"],
                "frame_count": len(processed), "seed_frame": seed["seed_frame"],
                "seed_evidence": {k: v for k, v in seed.items() if k != "raw_detections"},
                "raw_seed_detections": seed["raw_detections"],
                "sam2": {"repo": "https://github.com/facebookresearch/sam2", "commit": sam2_commit,
                         "license": "Apache-2.0", "checkpoint_sha256": EXPECTED_SAM2_SHA,
                         "config_sha256": EXPECTED_CONFIG_SHA},
                "rtdetr": rtdetr_provenance, "runtime": runtime, "role_summary": summary,
                "recovery": {"auto_reacquisitions": auto_reacquisitions,
                             "manual_reacquisitions": manual_reacquisitions,
                             "track_lost_events": loss_events, "review_events": review_events,
                             "identity_swaps": 0,
                             "identity_note": "固定 object_id 1/2；无独立身份 GT，未声称语义身份连续已验证。"},
                "events": events, "records": records,
                "scene_cut_candidates": scene_cut_candidates,
                "outputs": {"overlay_video": "player_tracking_overlay.mp4",
                            "masks": "masks/", "overlay_frames": "overlay-frames/"},
                "production_database": "NOT_ACCESSED", "completed_at": now()}
    atomic_json(job / "tracking.json", manifest)
    progress = load_job_progress(job_id)
    progress.update({"status": "COMPLETE", "stage": "追踪完成", "processed_frames": len(processed),
                     "events": events, "summary": summary, "runtime": runtime,
                     "recovery": manifest["recovery"], "completed_at": now()})
    save_job_progress(job_id, progress)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    detect = sub.add_parser("detect-seed")
    detect.add_argument("--sample-id", required=True)
    detect.add_argument("--frame", required=True, type=int)
    detect.add_argument("--detection-set-id", required=True)
    track = sub.add_parser("track")
    track.add_argument("--job-id", required=True)
    args = parser.parse_args()
    if args.command == "detect-seed":
        command_detect_seed(args.sample_id, args.frame, args.detection_set_id)
    else:
        command_track(args.job_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        job_id = None
        try:
            job_id = sys.argv[sys.argv.index("--job-id") + 1]
        except (ValueError, IndexError):
            pass
        if job_id:
            try:
                job_log = closed_loop_root() / "jobs" / job_id / "worker.log"
                job_log.parent.mkdir(parents=True, exist_ok=True)
                with job_log.open("a", encoding="utf-8") as stream:
                    stream.write(traceback.format_exc())
                    stream.write("\n")
                update_progress(job_id, status="FAILED", stage="视觉处理失败", error=f"{type(exc).__name__}: {exc}")
            except Exception:
                pass
        raise
