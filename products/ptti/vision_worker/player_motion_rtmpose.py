"""Run quality-gated RTMPose on isolated, hash-verified tracking clips."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path


PRODUCT_ROOT = Path(os.environ["PTTI_PRODUCT_ROOT"]).resolve()
LOCAL = Path(os.environ["LOCALAPPDATA"]).resolve()
RUNTIME_ROOT = LOCAL / "PTTI-Dev" / "vision-v2-rtmpose"
MODEL_PATH = RUNTIME_ROOT / "models" / "rtmpose-m-halpe26.onnx"
MODEL_SHA256 = "26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf"
ARCHIVE_SHA256 = "55b81170e236040b59fc792ad0a8315301ac4c079a3bdb1095d838aad3088d18"
RTMLIB_COMMIT = "cc359b924ec441b3563fb71f8cd012e576b8d262"
RTMLIB_VERSION = "0.0.10"
ONNXRUNTIME_VERSION = "1.26.0"
SOURCE = "RTMPose via rtmlib / ONNX Runtime"
LICENSE = "CC BY-NC-SA 4.0 research/non-commercial video; model checkpoint license not separately stated"
SKELETON = (
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
)
_DLL_DIRECTORY = None

sys.path.insert(0, str(PRODUCT_ROOT))
from backend.player_motion import (  # noqa: E402
    atomic_pose_json, build_person_crop, build_track_windows, evaluate_track_window,
    halpe26_observations, motion_metrics, player_motion_job_root, pose_file_sha256,
    supports_pose_tracking_manifest,
)
from backend.player_tracking_closed_loop import resolve_sample  # noqa: E402
from backend.player_motion import tracking_job_path  # noqa: E402


def progress(path: Path, *, status: str, stage: str, **values) -> None:
    atomic_pose_json(path, {"status": status, "stage": stage, "updated_at": time.time(), **values})


def draw_pose(frame, record, *, color):
    import cv2

    points = record.get("keypoints") or {}
    for left, right in SKELETON:
        a, b = points.get(left), points.get(right)
        if (a and b and a["score"] >= 0.35 and b["score"] >= 0.35):
            cv2.line(frame, (round(a["x_global"]), round(a["y_global"])),
                     (round(b["x_global"]), round(b["y_global"])), color, 3, cv2.LINE_AA)
    for joint in points.values():
        if joint["score"] >= 0.35:
            cv2.circle(frame, (round(joint["x_global"]), round(joint["y_global"])),
                       4, color, -1, cv2.LINE_AA)


def memory_snapshot() -> dict:
    """Capture process RAM and device-wide VRAM, keeping their scopes explicit."""
    ram = None
    try:
        import psutil
        ram = int(psutil.Process(os.getpid()).memory_info().rss)
    except (ImportError, OSError, ValueError):
        pass
    vram = None
    try:
        process = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False)
        values = [int(float(line.strip())) for line in process.stdout.splitlines()
                  if line.strip().replace(".", "", 1).isdigit()]
        if process.returncode == 0 and values:
            vram = max(values) * 1024 * 1024
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {"process_ram_working_set_bytes": ram,
            "gpu_device_memory_used_bytes": vram,
            "gpu_memory_scope": "DEVICE_TOTAL" if vram is not None else "UNAVAILABLE"}


def encode_browser_preview(source: Path, destination: Path) -> float | None:
    """Make an H.264 copy for WebView/Chromium; never modify the source video."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    temporary = destination.with_name(destination.stem + ".encoding.mp4")
    started = time.perf_counter()
    try:
        subprocess.run(
            [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(source), "-map", "0:v:0", "-an", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(temporary)],
            capture_output=True, timeout=180, check=True)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            return None
        temporary.replace(destination)
        return time.perf_counter() - started
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        temporary.unlink(missing_ok=True)


def run(tracking_job_id: str) -> dict:
    global _DLL_DIRECTORY
    import cv2
    import numpy as np
    shared_cuda_lib = LOCAL / "PTTI-Dev" / "vision-v2-sam2" / "venv" / "Lib" / "site-packages" / "torch" / "lib"
    if shared_cuda_lib.is_dir():
        os.environ["PATH"] = str(shared_cuda_lib) + os.pathsep + os.environ.get("PATH", "")
        try:
            _DLL_DIRECTORY = os.add_dll_directory(str(shared_cuda_lib))
        except (AttributeError, OSError):
            _DLL_DIRECTORY = None
    import onnxruntime as ort
    if shared_cuda_lib.is_dir() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls(directory=str(shared_cuda_lib))
    from rtmlib_compat import load_rtmpose_class
    RTMPose = load_rtmpose_class()

    tracking_path = tracking_job_path(tracking_job_id)
    if not tracking_path.is_file():
        raise FileNotFoundError("TRACKING_RESULT_UNAVAILABLE")
    tracking = json.loads(tracking_path.read_text(encoding="utf-8"))
    if tracking.get("job_id") != tracking_job_id or not supports_pose_tracking_manifest(tracking):
        raise ValueError("TRACKING_JOB_NOT_ELIGIBLE_FOR_POSE")
    sample = resolve_sample(tracking["sample_id"], verify_hash=True)
    if sample["clip_sha256"] != tracking.get("source_sha256"):
        raise ValueError("TRACKING_SOURCE_HASH_MISMATCH")
    if not MODEL_PATH.is_file() or pose_file_sha256(MODEL_PATH) != MODEL_SHA256:
        raise ValueError("RTMPOSE_MODEL_SHA_MISMATCH")

    output_root = player_motion_job_root(tracking_job_id)
    output_root.mkdir(parents=True, exist_ok=True)
    result_path = output_root / "player_motion.json"
    progress_path = output_root / "progress.json"
    if result_path.exists():
        raise FileExistsError("POSE_RESULT_ALREADY_EXISTS_DO_NOT_OVERWRITE")
    progress(progress_path, status="RUNNING", stage="载入姿态模型",
             tracking_job_id=tracking_job_id, sample_id=sample["sample_id"])

    providers = ort.get_available_providers()
    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError("ONNXRUNTIME_CUDA_PROVIDER_UNAVAILABLE")
    load_started = time.perf_counter()
    sessions = []
    original_session = ort.InferenceSession
    def capture_session(*args, **kwargs):
        session = original_session(*args, **kwargs)
        sessions.append(session)
        return session
    ort.InferenceSession = capture_session
    try:
        pose_model = RTMPose(onnx_model=str(MODEL_PATH), model_input_size=(192, 256),
                             backend="onnxruntime", device="cuda")
    finally:
        ort.InferenceSession = original_session
    load_seconds = time.perf_counter() - load_started
    actual_providers = [session.get_providers() for session in sessions]
    if not actual_providers or not any("CUDAExecutionProvider" in row for row in actual_providers):
        raise RuntimeError("RTMPOSE_NOT_RUNNING_ON_CUDA")

    video_path = Path(sample["video_path"])
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise OSError("POSE_SOURCE_VIDEO_CANNOT_BE_OPENED")
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or float(tracking.get("sample_fps", 30.0))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    expected_frames = int(tracking.get("frames", sample["frames"]))
    if frame_count <= 0 or frame_count != expected_frames:
        cap.release()
        raise ValueError("TRACKING_VIDEO_FRAME_COUNT_MISMATCH")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    windows = build_track_windows(tracking["records"], tracking.get("events", []),
                                 frame_count=frame_count, fps=fps,
                                 frame_size=(width, height), window_seconds=1.0)
    window_frames = max(1, round(fps))
    window_lookup = {row["start_frame"]: row for row in windows}
    rows_by_frame: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in tracking["records"]:
        rows_by_frame[int(row["frame"])][row["role"]].append(row)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    overlay_path = output_root / "player_motion_overlay.mp4"
    writer = cv2.VideoWriter(str(overlay_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise OSError("POSE_OVERLAY_WRITER_UNAVAILABLE")

    raw_poses: list[dict] = []
    inference_ms: list[float] = []
    run_started = time.perf_counter()
    memory_samples = [memory_snapshot()]
    counts = {role: Counter() for role in ("NEAR_PLAYER", "FAR_PLAYER")}
    snapshot_frames = {0, frame_count // 2, frame_count - 1}
    sampled_frames = []
    for frame_index in range(frame_count):
        ok, frame = cap.read()
        if not ok:
            writer.release()
            cap.release()
            raise OSError(f"POSE_SOURCE_DECODE_FAILED_AT_FRAME_{frame_index}")
        annotated = frame.copy()
        window_start = (frame_index // window_frames) * window_frames
        window = window_lookup[window_start]
        for role, color in (("NEAR_PLAYER", (60, 210, 255)), ("FAR_PLAYER", (255, 145, 50))):
            candidates = rows_by_frame[frame_index].get(role, [])
            record = candidates[0] if len(candidates) == 1 else None
            role_gate = window["players"][role]
            if role_gate["status"] != "POSE_READY" or record is None:
                reason = role_gate["reasons"] or (["DUPLICATE_TRACK_FRAME"] if len(candidates) > 1 else ["NO_TRUSTED_TRACK"])
                raw_poses.append({"frame": frame_index,
                                  "timestamp_ms": int(record["timestamp_ms"]) if record else
                                                  int(round((sample["start_seconds"] + frame_index / fps) * 1000)),
                                  "player_role": role, "pose_quality": "NO_POSE",
                                  "track_quality": role_gate["status"], "reasons": reason,
                                  "pose_source": SOURCE})
                counts[role]["NO_POSE"] += 1
                continue
            if not (record.get("tracking_status") == "ACCEPTED"
                    and record.get("visibility") in {"VISIBLE", "PARTIAL"}
                    and int(record.get("mask_area") or 0) > 0):
                raw_poses.append({"frame": frame_index, "timestamp_ms": int(record.get("timestamp_ms", 0)),
                                  "player_role": role, "pose_quality": "NO_POSE",
                                  "track_quality": "REVIEW", "reasons": ["TRACK_RECORD_NOT_TRUSTED"],
                                  "pose_source": SOURCE})
                counts[role]["NO_POSE"] += 1
                continue
            crop = build_person_crop((width, height), record["bbox"])
            image = frame[crop["y"]:crop["y"] + crop["height"],
                           crop["x"]:crop["x"] + crop["width"]]
            if image.size == 0:
                raw_poses.append({"frame": frame_index, "timestamp_ms": int(record["timestamp_ms"]),
                                  "player_role": role, "pose_quality": "NO_POSE",
                                  "track_quality": "REVIEW", "reasons": ["EMPTY_PERSON_CROP"],
                                  "pose_source": SOURCE})
                counts[role]["NO_POSE"] += 1
                continue
            before = time.perf_counter()
            kpts, scores = pose_model(image, bboxes=[[0, 0, image.shape[1], image.shape[0]]])
            inference_ms.append((time.perf_counter() - before) * 1000)
            keypoints = np.asarray(kpts)[0]
            joint_scores = np.asarray(scores)[0]
            full_raw, selected = halpe26_observations(
                keypoints.tolist(), joint_scores.tolist(), origin=(crop["x"], crop["y"]))
            score_map = {point["joint"]: point["score"] for point in selected}
            quality = __import__("backend.player_motion", fromlist=["pose_quality_state"]).pose_quality_state(
                score_map, track_quality=role_gate["status"])
            pose_record = {
                "frame": frame_index,
                "timestamp_ms": int(record["timestamp_ms"]),
                "player_role": role,
                "object_id": int(record.get("object_id", 1 if role == "NEAR_PLAYER" else 2)),
                "pose_quality": quality,
                "track_quality": role_gate["status"],
                "identity_continuous": bool(role_gate.get("motion_eligible")),
                "visibility": record.get("visibility"),
                "bbox": record["bbox"],
                "crop": crop,
                "raw_model_keypoints": full_raw,
                "keypoints": {point["joint"]: point for point in selected},
                "pose_source": SOURCE,
                "model_probability": None,
                "source": "RTMPOSE_MODEL_OBSERVATION",
            }
            raw_poses.append(pose_record)
            counts[role][quality] += 1
            if quality in {"GOOD", "PARTIAL"}:
                draw_pose(annotated, pose_record, color=color)
            x0, y0, x1, y1 = map(int, record["bbox"])
            cv2.rectangle(annotated, (x0, y0), (x1, y1), color, 2)
            cv2.putText(annotated, f"{role.replace('_PLAYER', '')} · {quality}",
                        (x0, max(24, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2, cv2.LINE_AA)
        writer.write(annotated)
        if frame_index in snapshot_frames:
            preview = output_root / f"pose-frame-{frame_index:05d}.jpg"
            cv2.imwrite(str(preview), annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            sampled_frames.append({"frame": frame_index, "timestamp_ms":
                                   int(round((sample["start_seconds"] + frame_index / fps) * 1000)),
                                   "asset": preview.name})
        if (frame_index + 1) % max(1, round(fps * 2)) == 0:
            memory_samples.append(memory_snapshot())
            progress(progress_path, status="RUNNING", stage="正在识别可信片段的人体姿态",
                     tracking_job_id=tracking_job_id, sample_id=sample["sample_id"],
                     processed_frames=frame_index + 1, total_frames=frame_count)
    writer.release()
    cap.release()
    source_preview_path = output_root / "player_motion_source_preview.mp4"
    source_preview_seconds = encode_browser_preview(video_path, source_preview_path)
    overlay_preview_seconds = encode_browser_preview(overlay_path, overlay_path.with_name("player_motion_overlay_h264.mp4"))
    if overlay_preview_seconds is not None:
        overlay_path.with_name("player_motion_overlay_h264.mp4").replace(overlay_path)
    memory_samples.append(memory_snapshot())
    total_seconds = time.perf_counter() - run_started

    pose_by_role = {
        role: [row for row in raw_poses if row.get("player_role") == role and row.get("pose_quality") in {"GOOD", "PARTIAL"}]
        for role in ("NEAR_PLAYER", "FAR_PLAYER")
    }
    metrics = {role: motion_metrics(rows) for role, rows in pose_by_role.items()}
    good_or_partial = {role: counts[role]["GOOD"] + counts[role]["PARTIAL"]
                       for role in counts}
    report = {
        "schema_version": "player-motion-v0.1",
        "status": "COMPLETE",
        "tracking_job_id": tracking_job_id,
        "sample_id": sample["sample_id"],
        "match_id": sample["match_id"],
        "dataset": "Extended OpenTTGames",
        "rights": sample["rights"],
        "commercial_use": False,
        "source_sha256": sample["clip_sha256"],
        "tracking_source_sha256": pose_file_sha256(tracking_path),
        "official_split": "TRAIN",
        "model": {
            "name": "RTMPose-m SimCC Halpe26",
            "model_source": "OpenMMLab RTMPose ONNX SDK archive",
            "archive_sha256": ARCHIVE_SHA256,
            "onnx_sha256": MODEL_SHA256,
            "input_size": [192, 256],
            "keypoint_schema": "Halpe26; 13 required body joints selected; full raw output preserved",
            "checkpoint_license": "UNKNOWN: no separate checkpoint license found; research-only and not redistributed",
        },
        "runtime": {
            "python": platform.python_version(),
            "rtmlib_version": RTMLIB_VERSION,
            "rtmlib_commit": RTMLIB_COMMIT,
            "onnxruntime": ort.__version__,
            "available_providers": providers,
            "session_providers": actual_providers,
            "device_requested": "cuda",
            "model_load_seconds": round(load_seconds, 3),
            "mean_pose_inference_ms_per_person": round(sum(inference_ms) / len(inference_ms), 3) if inference_ms else None,
            "pose_inferences": len(inference_ms),
            "total_processing_seconds": round(total_seconds, 3),
            "effective_processing_fps": round(frame_count / max(total_seconds, 1e-9), 3),
            "realtime_factor": round((frame_count / fps) / max(total_seconds, 1e-9), 4),
            "browser_preview_transcode_seconds": round((source_preview_seconds or 0)
                                                       + (overlay_preview_seconds or 0), 3),
            "browser_video_encoding": "H.264 / yuv420p" if source_preview_seconds is not None else "UNAVAILABLE",
            "peak_process_ram_working_set_bytes": max(
                (row["process_ram_working_set_bytes"] for row in memory_samples
                 if row["process_ram_working_set_bytes"] is not None), default=None),
            "peak_gpu_device_memory_used_bytes": max(
                (row["gpu_device_memory_used_bytes"] for row in memory_samples
                 if row["gpu_device_memory_used_bytes"] is not None), default=None),
            "gpu_memory_scope": next((row["gpu_memory_scope"] for row in memory_samples
                                      if row["gpu_device_memory_used_bytes"] is not None), "UNAVAILABLE"),
            "gpu": "NVIDIA GeForce RTX 5060 Laptop GPU",
        },
        "video": {"fps": fps, "frame_count": frame_count, "width": width, "height": height,
                  "duration_seconds": frame_count / fps},
        "quality_policy": {"window_seconds": 1.0, "pose_ready_coverage": 0.8,
                           "candidate_threshold": 0.35,
                           "tracking_gate": "ACCEPTED + visible/partial + mask + sane bbox + no unresolved event"},
        "summary": {
            role: {"frames": frame_count,
                  "pose_ready_frames": good_or_partial[role],
                  "good": counts[role]["GOOD"], "partial": counts[role]["PARTIAL"],
                  "low_confidence": counts[role]["LOW_CONFIDENCE"], "no_pose": counts[role]["NO_POSE"],
                  "pose_coverage_over_clip": round(good_or_partial[role] / max(1, frame_count), 4),
                  "metrics": metrics[role]}
            for role in counts
        },
        "windows": windows,
        "sampled_frames": sampled_frames,
        "assets": {"overlay": overlay_path.name,
                   "source_preview": source_preview_path.name if source_preview_seconds is not None else None,
                   "browser_video_status": "READY" if source_preview_seconds is not None else "SOURCE_CODEC_FALLBACK"},
        "records": raw_poses,
    }
    atomic_pose_json(result_path, report)
    progress(progress_path, status="COMPLETE", stage="姿态分析完成",
             tracking_job_id=tracking_job_id, sample_id=sample["sample_id"],
             processed_frames=frame_count, total_frames=frame_count,
             summary=report["summary"], result_file=result_path.name)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-job-id", required=True)
    args = parser.parse_args()
    root = player_motion_job_root(args.tracking_job_id)
    root.mkdir(parents=True, exist_ok=True)
    try:
        result = run(args.tracking_job_id)
        summary = {role: {key: value for key, value in row.items() if key != "metrics"}
                   for role, row in result["summary"].items()}
        print(json.dumps({"status": result["status"], "sample_id": result["sample_id"],
                          "summary": summary, "runtime": result["runtime"]}, ensure_ascii=False), flush=True)
    except Exception as exc:
        progress(root / "progress.json", status="FAILED", stage="姿态分析失败",
                 tracking_job_id=args.tracking_job_id, error=str(exc),
                 detail=traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
