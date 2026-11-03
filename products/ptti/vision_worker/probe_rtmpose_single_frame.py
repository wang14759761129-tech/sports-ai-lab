"""One-frame CUDA and coordinate smoke test on an eligible real player crop."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


PRODUCT_ROOT = Path(os.environ["PTTI_PRODUCT_ROOT"]).resolve()
LOCAL = Path(os.environ["LOCALAPPDATA"]).resolve()
RUNTIME_ROOT = LOCAL / "PTTI-Dev" / "vision-v2-rtmpose"
MODEL = RUNTIME_ROOT / "models" / "rtmpose-m-halpe26.onnx"
EXPECTED_MODEL_SHA = "26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf"
ARCHIVE_SHA = "55b81170e236040b59fc792ad0a8315301ac4c079a3bdb1095d838aad3088d18"
RTMLIB_COMMIT = "cc359b924ec441b3563fb71f8cd012e576b8d262"

sys.path.insert(0, str(PRODUCT_ROOT))

from backend.player_motion import (  # noqa: E402
    build_person_crop, build_track_windows, halpe26_observations,
    load_tracking_evidence, pose_file_sha256,
)


def main():
    import cv2
    import numpy as np

    shared_cuda_lib = LOCAL / "PTTI-Dev" / "vision-v2-sam2" / "venv" / "Lib" / "site-packages" / "torch" / "lib"
    dll_directory = None
    if shared_cuda_lib.is_dir():
        os.environ["PATH"] = str(shared_cuda_lib) + os.pathsep + os.environ.get("PATH", "")
        try:
            dll_directory = os.add_dll_directory(str(shared_cuda_lib))
        except (AttributeError, OSError):
            pass
    import onnxruntime as ort
    if shared_cuda_lib.is_dir() and hasattr(ort, "preload_dlls"):
        ort.preload_dlls(directory=str(shared_cuda_lib))
    from rtmlib_compat import load_rtmpose_class
    RTMPose = load_rtmpose_class()

    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-job-id", required=True)
    args = parser.parse_args()
    if pose_file_sha256(MODEL) != EXPECTED_MODEL_SHA:
        raise RuntimeError("RTMPOSE_MODEL_SHA_MISMATCH")
    providers = ort.get_available_providers()
    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError("ONNXRUNTIME_CUDA_PROVIDER_UNAVAILABLE")
    manifest, video_path = load_tracking_evidence(args.tracking_job_id)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise OSError("SOURCE_VIDEO_OPEN_FAILED")
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or float(manifest.get("sample_fps", 30))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    windows = build_track_windows(manifest["records"], manifest.get("events", []),
                                  frame_count=count, fps=fps, frame_size=(width, height))
    rows_by_frame = {}
    for record in manifest["records"]:
        rows_by_frame.setdefault((int(record["frame"]), record["role"]), []).append(record)
    seed = None
    for window in windows:
        for role in ("NEAR_PLAYER", "FAR_PLAYER"):
            if window["players"][role]["status"] != "POSE_READY":
                continue
            for frame in range(window["start_frame"], window["end_frame"]):
                rows = rows_by_frame.get((frame, role), [])
                if (len(rows) == 1 and rows[0].get("tracking_status") == "ACCEPTED"
                        and rows[0].get("visibility") in {"VISIBLE", "PARTIAL"}
                        and rows[0].get("mask_area", 0) > 0):
                    seed = (frame, role, rows[0], window["players"][role])
                    break
            if seed:
                break
        if seed:
            break
    if seed is None:
        cap.release()
        raise RuntimeError("NO_POSE_READY_REAL_TRACK_WINDOW")
    frame_index, role, record, gate = seed
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise OSError("SOURCE_FRAME_DECODE_FAILED")
    crop = build_person_crop((width, height), record["bbox"])
    image = frame[crop["y"]:crop["y"] + crop["height"], crop["x"]:crop["x"] + crop["width"]]
    sessions = []
    original_session = ort.InferenceSession
    def capture_session(*args, **kwargs):
        session = original_session(*args, **kwargs)
        sessions.append(session)
        return session
    ort.InferenceSession = capture_session
    load_start = time.perf_counter()
    try:
        model = RTMPose(onnx_model=str(MODEL), model_input_size=(192, 256),
                        backend="onnxruntime", device="cuda")
    finally:
        load_seconds = time.perf_counter() - load_start
        ort.InferenceSession = original_session
    session_providers = [session.get_providers() for session in sessions]
    if not session_providers or not any("CUDAExecutionProvider" in row for row in session_providers):
        raise RuntimeError("RTMPOSE_NOT_RUNNING_ON_CUDA")
    inference_samples = []
    keypoints = scores = None
    for _ in range(3):
        inference_start = time.perf_counter()
        keypoints, scores = model(image, bboxes=[[0, 0, image.shape[1], image.shape[0]]])
        inference_samples.append((time.perf_counter() - inference_start) * 1000)
    inference_ms = inference_samples[-1]
    if len(keypoints) != 1 or len(scores) != 1:
        raise RuntimeError("POSE_ESTIMATOR_DID_NOT_RETURN_ONE_PERSON")
    raw, selected = halpe26_observations(np.asarray(keypoints)[0].tolist(),
                                         np.asarray(scores)[0].tolist(),
                                         origin=(crop["x"], crop["y"]))
    if len(raw) != 26 or not selected:
        raise RuntimeError("HALPE26_OUTPUT_INVALID")
    from backend.player_motion import pose_quality_state
    quality = pose_quality_state({point["joint"]: point["score"] for point in selected},
                                 track_quality="POSE_READY")
    color = (60, 210, 255) if role == "NEAR_PLAYER" else (255, 145, 50)
    annotated = frame.copy()
    x0, y0, x1, y1 = map(int, record["bbox"])
    cv2.rectangle(annotated, (x0, y0), (x1, y1), color, 2)
    joints = {point["joint"]: point for point in selected}
    bones = [("left_shoulder", "right_shoulder"), ("left_shoulder", "left_elbow"),
             ("left_elbow", "left_wrist"), ("right_shoulder", "right_elbow"),
             ("right_elbow", "right_wrist"), ("left_shoulder", "left_hip"),
             ("right_shoulder", "right_hip"), ("left_hip", "right_hip"),
             ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
             ("right_hip", "right_knee"), ("right_knee", "right_ankle")]
    for a, b in bones:
        p, q = joints.get(a), joints.get(b)
        if p and q and p["score"] >= .35 and q["score"] >= .35:
            cv2.line(annotated, (round(p["x_global"]), round(p["y_global"])),
                     (round(q["x_global"]), round(q["y_global"])), color, 3, cv2.LINE_AA)
    for point in selected:
        if point["score"] >= .35:
            cv2.circle(annotated, (round(point["x_global"]), round(point["y_global"])),
                       5, color, -1, cv2.LINE_AA)
    probe_dir = RUNTIME_ROOT / "probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    image_path = probe_dir / "rtmpose-single-frame.jpg"
    cv2.imwrite(str(image_path), annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    report = {
        "status": "PASS_ONE_FRAME_CUDA",
        "tracking_job_id": args.tracking_job_id,
        "sample_id": manifest["sample_id"],
        "rights": manifest["rights"],
        "source_sha256": manifest["source_sha256"],
        "frame": frame_index,
        "timestamp_ms": int(record["timestamp_ms"]),
        "role": role,
        "track_window": gate,
        "bbox_global": record["bbox"],
        "crop": crop,
        "keypoints_returned": len(raw),
        "required_joints": len(selected),
        "pose_quality": quality,
        "model_load_seconds": round(load_seconds, 4),
        "pose_inference_ms": round(inference_ms, 3),
        "same_crop_repeat_inference_ms": [round(value, 3) for value in inference_samples],
        "available_providers": providers,
        "session_providers": session_providers,
        "rtmlib_version": "0.0.10",
        "rtmlib_commit": RTMLIB_COMMIT,
        "model_sha256": EXPECTED_MODEL_SHA,
        "model_archive_sha256": ARCHIVE_SHA,
        "probe_image": str(image_path),
        "dll_directory": str(shared_cuda_lib) if shared_cuda_lib.is_dir() else None,
    }
    out = probe_dir / "single-frame-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime = {
        "status": "CUDA_INFERENCE_VERIFIED",
        "python": sys.version.split()[0],
        "rtmlib_version": "0.0.10", "rtmlib_commit": RTMLIB_COMMIT,
        "onnxruntime": ort.__version__, "available_providers": providers,
        "session_providers": session_providers,
        "cuda_provider_available": "CUDAExecutionProvider" in providers,
        "cuda_session_verified": any("CUDAExecutionProvider" in row for row in session_providers),
        "onnx_sha256": EXPECTED_MODEL_SHA, "archive_sha256": ARCHIVE_SHA,
        "model_load_seconds": round(load_seconds, 4),
        "one_frame_pose_inference_ms": round(inference_ms, 3),
        "same_crop_repeat_inference_ms": [round(value, 3) for value in inference_samples],
        "gpu": "NVIDIA GeForce RTX 5060 Laptop GPU",
        "shared_cuda_runtime_source": str(shared_cuda_lib) if shared_cuda_lib.is_dir() else None,
        "license_status": "RTMLib Apache-2.0; exact checkpoint license unknown; research only",
        "sample_id": manifest["sample_id"], "source_sha256": manifest["source_sha256"],
    }
    (RUNTIME_ROOT / "runtime.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    # Keep DLL directory registration alive through session destruction.
    _ = dll_directory


if __name__ == "__main__":
    main()
