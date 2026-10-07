"""Isolated RT-DETR worker for the locked game_4 calibration source only.

The request contains candidate frame numbers, not annotations or ground truth.
This worker is intentionally separate from the game_1--3 DEV worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

PRODUCT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibration import enforce_calibration_scope, resolve_ptti_dev_root  # noqa: E402

FROZEN_SCENE_MANIFEST_SHA256 = "67bc35a5a1570d4610e524141030f1c93aa5b2a8516767f12023d4eb9f75276f"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_request(request: dict) -> tuple[Path, Path, Path]:
    enforce_calibration_scope(request.get("game"), request.get("split_role"),
                              request.get("official_split"))
    if request.get("game_5") != "NOT_ACCESSED" or request.get("official_test") != "NOT_ACCESSED":
        raise ValueError("CALIBRATION_LOCK_MARKERS_REQUIRED")
    if any(key in request for key in {"annotations", "stroke_gt", "bounce_gt", "net_gt",
                                      "rally_ending_gt", "ground_truth"}):
        raise ValueError("GT_CONTENT_FORBIDDEN_AT_INFERENCE")
    frames = request.get("frames")
    if (not isinstance(frames, list) or not 1 <= len(frames) <= 256 or
            any(type(frame) is not int or frame < 0 for frame in frames) or
            frames != sorted(set(frames)) or request.get("fps") != 120.0):
        raise ValueError("UNSAFE_OR_NONCANONICAL_CALIBRATION_FRAME_REQUEST")
    video = Path(request["video_path"]).resolve()
    dev_root = resolve_ptti_dev_root(video)
    source_path = (dev_root / "evidence" / "hit_event_v0_3" /
                   "game4-calibration-20261008" / "GAME4_CALIBRATION_SOURCE_VERIFICATION.json").resolve()
    if Path(request["source_verification_path"]).resolve() != source_path:
        raise ValueError("NONCANONICAL_CALIBRATION_SOURCE_VERIFICATION")
    if _sha(source_path) != request.get("source_verification_sha256"):
        raise ValueError("CALIBRATION_SOURCE_VERIFICATION_HASH_CHANGED")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    enforce_calibration_scope(source.get("game"), source.get("split_role"),
                              source.get("official_split"))
    identity = source["video"]
    if (video != Path(identity["path"]).resolve() or
            request.get("video_sha256") != identity.get("sha256") or
            video.stat().st_size != int(identity["size_bytes"]) or
            video.stat().st_mtime_ns != int(request.get("video_mtime_ns", -1))):
        raise ValueError("CALIBRATION_VIDEO_IDENTITY_CHANGED")
    if max(frames) >= int(identity["frame_count"]):
        raise ValueError("CALIBRATION_FRAME_OUT_OF_RANGE")
    scene_path = (dev_root / "vision-v2" / "scene-bootstrap" /
                  "scene_bootstrap_eval_manifest.json").resolve()
    if (Path(request["scene_manifest_path"]).resolve() != scene_path or
            _sha(scene_path) != FROZEN_SCENE_MANIFEST_SHA256 or
            request.get("scene_manifest_sha256") != FROZEN_SCENE_MANIFEST_SHA256):
        raise ValueError("SCENE_EVIDENCE_MANIFEST_CHANGED")
    table = request.get("table_bbox")
    if table is not None and (len(table) != 4 or any(not isinstance(value, (int, float)) for value in table)):
        raise ValueError("INVALID_COARSE_TABLE_BOX")
    return video, source_path, dev_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    request_bytes = args.request.read_bytes()
    request = json.loads(request_bytes)
    video, source_path, dev_root = validate_request(request)

    sys.path.insert(0, str(dev_root / "vision-v2" / "venv" / "Lib" / "site-packages"))
    import cv2
    import torch
    from PIL import Image
    from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
    from backend.person_detector import RTDetrPredictionAdapter, TablePersonRoleResolver, verify_r18
    from resources import available_ram, process_rss

    if available_ram() < 3 * 1024**3:
        raise RuntimeError("RESOURCE_GUARD_INSUFFICIENT_AVAILABLE_RAM")
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    model_folder = dev_root / "vision-v2" / "models" / "rtdetr-r18"
    provenance = verify_r18(model_folder)
    started = time.perf_counter()
    processor = RTDetrImageProcessor.from_pretrained(model_folder, local_files_only=True)
    model = RTDetrForObjectDetection.from_pretrained(model_folder, local_files_only=True).eval().to("cuda")
    load_seconds = time.perf_counter() - started
    torch.cuda.reset_peak_memory_stats()
    capture = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_N_THREADS, 2])
    if not capture.isOpened():
        raise RuntimeError("CALIBRATION_VIDEO_DECODER_UNAVAILABLE")
    frames = request["frames"]
    capture.set(cv2.CAP_PROP_POS_FRAMES, frames[0])
    actual = int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))
    if actual != frames[0]:
        raise RuntimeError("CALIBRATION_SEEK_FRAME_MISMATCH")
    adapter = RTDetrPredictionAdapter()
    resolver = TablePersonRoleResolver()
    rows, inference_seconds = [], []
    max_rss = 0
    min_ram = available_ram()
    target_index = 0
    try:
        while target_index < len(frames):
            if not capture.grab():
                raise RuntimeError("CALIBRATION_VIDEO_DECODE_FAILED")
            if actual == frames[target_index]:
                ok, bgr = capture.retrieve()
                if not ok:
                    raise RuntimeError("CALIBRATION_FRAME_RETRIEVE_FAILED")
                image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                before = time.perf_counter()
                with torch.inference_mode():
                    inputs = processor(images=image, return_tensors="pt").to("cuda")
                    output = model(**inputs)
                    result = processor.post_process_object_detection(
                        output, target_sizes=torch.tensor([[image.height, image.width]], device="cuda"),
                        threshold=0.25)[0]
                torch.cuda.synchronize()
                inference_seconds.append(time.perf_counter() - before)
                predictions = [
                    {"label": model.config.id2label[int(label)], "score": float(score), "bbox": box.tolist()}
                    for score, label, box in zip(result["scores"], result["labels"], result["boxes"])
                ]
                raw_people = adapter.adapt(predictions, image_size=image.size, frame=actual,
                                           timestamp_ms=actual * 1000.0 / 120.0)
                resolved_people = resolver.resolve(request.get("table_bbox"), raw_people,
                                                   image_size=image.size)
                pts_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                timestamp_ms = actual * 1000.0 / 120.0
                if abs(pts_ms - timestamp_ms) > 0.5:
                    raise RuntimeError("CALIBRATION_DECODED_PTS_MISMATCH")
                rows.append({"source_frame": actual, "timestamp_ms": timestamp_ms,
                             "decoded_pts_ms": pts_ms, "video_sha256": request["video_sha256"],
                             "raw_people": raw_people, "resolved_people": resolved_people})
                target_index += 1
                min_ram = min(min_ram, available_ram())
                max_rss = max(max_rss, process_rss())
                if min_ram < 1.5 * 1024**3 or max_rss > 3 * 1024**3:
                    raise RuntimeError("RESOURCE_GUARD_CALIBRATION_WORKER_MEMORY_LIMIT")
                del inputs, output, result, image, bgr
                if target_index < len(frames) and frames[target_index] - actual > 240:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frames[target_index])
                    actual = int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))
                    if actual != frames[target_index]:
                        raise RuntimeError("CALIBRATION_RESEEK_FRAME_MISMATCH")
                    continue
            actual += 1
    finally:
        capture.release()

    final_stat = video.stat()
    expected = json.loads(source_path.read_text(encoding="utf-8"))["video"]
    if (final_stat.st_size != int(expected["size_bytes"]) or
            final_stat.st_mtime_ns != int(request["video_mtime_ns"])):
        raise ValueError("CALIBRATION_SOURCE_CHANGED_DURING_PLAYER_INFERENCE")
    if args.output.exists():
        raise FileExistsError("CALIBRATION_PLAYER_RESULT_IS_IMMUTABLE")
    report = {"status": "COMPLETE", "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
              "game": "game_4", "split_role": "CALIBRATION", "video_sha256": request["video_sha256"],
              "source_verification_sha256": request["source_verification_sha256"],
              "scene_manifest_sha256": request["scene_manifest_sha256"],
              "model_provenance": provenance, "table_bbox": request.get("table_bbox"),
              "frames": rows, "runtime": {"model_load_seconds": load_seconds,
              "inference_seconds": sum(inference_seconds), "frames": len(rows),
              "mean_inference_fps": len(rows) / sum(inference_seconds) if inference_seconds else None,
              "peak_rss_bytes": max_rss, "minimum_available_ram_bytes": min_ram,
              "peak_allocated_vram_bytes": torch.cuda.max_memory_allocated()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + f".{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False)
    temporary.replace(args.output)
    print(json.dumps(report["runtime"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
