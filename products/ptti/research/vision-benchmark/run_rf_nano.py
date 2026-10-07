"""One pretrained RAW comparison on a locked sparse research manifest; no threshold sweep."""
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import statistics
import threading
import time

from ptti_benchmark.adapters import rfdetr_rows, select_named_sports_balls
from ptti_benchmark.core import (BallDetection, FrameObservation, evaluate_ball, file_sha256,
                                 rank_models, verify_manifest, write_report)

CHECKPOINT_SHA = "d8d6b9ee57d4d0ed2b1f305163624712a0532cb7bce0c747317984fc5457440d"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").isalnum():
        raise ValueError("INVALID_RUN_ID")
    if file_sha256(args.manifest) != args.manifest_sha:
        raise ValueError("MANIFEST_CHANGED")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    root = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation"
    target = root / f"rf-detr-comparison-{args.run_id}.json"
    if target.exists():
        raise FileExistsError("COMPARISON_ALREADY_EXISTS")
    checkpoint = root / "rf-detr-model/rf-detr-nano.pth"
    if file_sha256(checkpoint) != CHECKPOINT_SHA:
        raise ValueError("CHECKPOINT_SHA_MISMATCH")
    os.environ["RF_HOME"] = str(checkpoint.parent)
    os.environ["HF_HOME"] = str(root / "rf-detr-hf-cache")
    import psutil
    minimum_start_gib = 3.5 if args.device == "cuda" else 2.5
    if psutil.virtual_memory().available < minimum_start_gib * 1024**3:
        raise RuntimeError(f"RESOURCE_GUARD_WAIT_FOR_{minimum_start_gib}_GIB_AVAILABLE_RAM")
    samples, stop = [], threading.Event()

    def monitor():
        while not stop.wait(.2):
            samples.append({"rss": psutil.Process().memory_info().rss,
                            "available": psutil.virtual_memory().available})

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    started = time.perf_counter()
    completed_frames = 0
    try:
        import cv2
        from PIL import Image, ImageDraw
        import torch
        from rfdetr import RFDETRNano
        torch.set_num_threads(2)
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA_REQUIRED_FOR_THIS_REGISTERED_EXPERIMENT")
        model = RFDETRNano(pretrain_weights=str(checkpoint), device=args.device)
        if args.device == "cuda":
            torch.cuda.synchronize()
        load_seconds = time.perf_counter() - started
        from rfdetr.assets.coco_classes import COCO_CLASSES
        sports_ids = [i for i, name in COCO_CLASSES.items() if name.lower() == "sports ball"]
        if len(sports_ids) != 1:
            raise ValueError("OFFICIAL_SPORTS_BALL_CLASS_MAPPING_NOT_UNIQUE")
        sports_id = int(sports_ids[0])
        timings, decode_times, clip_results = [], [], []
        all_truth, all_rv, all_rf = [], [], []
        offset = 0
        raw_dir = root / f"rf-detr-raw-{args.run_id}"
        raw_dir.mkdir(exist_ok=True)
        for clip in manifest["clips"]:
            rows = []
            cap = cv2.VideoCapture(clip["video"]["path"])
            labels = json.loads(Path(clip["canonical_labels"]).read_text(encoding="utf-8"))
            for label in labels:
                decode_start = time.perf_counter()
                cap.set(cv2.CAP_PROP_POS_FRAMES, label["source_frame"])
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError("FRAME_DECODE_FAILED")
                decode_times.append(time.perf_counter()-decode_start)
                image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                if args.device == "cuda":
                    torch.cuda.synchronize()
                t = time.perf_counter()
                detection = model.predict(image, threshold=manifest["rf_detr_threshold"], include_source_image=False)
                if args.device == "cuda":
                    torch.cuda.synchronize()
                timings.append(time.perf_counter()-t)
                names = detection.data.get("class_name")
                selected = select_named_sports_balls(detection.xyxy, detection.confidence,
                                                     detection.class_id, names)
                rows.append({"source_frame": label["source_frame"], "timestamp_ms": label["timestamp_ms"],
                             "detections": selected, "source_video_sha256": clip["video"]["sha256"],
                             "native_all_detections": [{"bbox": [float(v) for v in box], "score": float(score),
                                                        "class_id": int(cid), "class_name": str(name)}
                                                       for box, score, cid, name in zip(detection.xyxy,
                                                        detection.confidence, detection.class_id, names)]})
                completed_frames += 1
                with (root / f"rf-detr-attempt-observations-{args.run_id}.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"clip": clip["id"], **rows[-1]}) + "\n")
                if label is labels[len(labels)//2]:
                    draw = ImageDraw.Draw(image)
                    if label["visible"]:
                        draw.ellipse((label["x"]-9,label["y"]-9,label["x"]+9,label["y"]+9), outline="lime", width=3)
                    for d in selected:
                        draw.rectangle(d["bbox"], outline="magenta", width=3)
                    image.save(raw_dir / (clip["id"].replace("/", "_") + ".jpg"))
                if psutil.virtual_memory().available < 1.25 * 1024**3:
                    raise RuntimeError("RESOURCE_GUARD_STOP_NEW_INFERENCE")
            cap.release()
            raw_path = raw_dir / (clip["id"].replace("/", "_") + ".json")
            raw_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            rf = rfdetr_rows(rows)
            rv_json = json.loads(Path(clip["racketvision_raw"]).read_text(encoding="utf-8"))
            rv = [FrameObservation(r["source_frame"], r["timestamp_ms"],
                                   tuple(BallDetection(**d) for d in r["detections"]), r["model"], r["source"]) for r in rv_json]
            metrics = {"RacketVision_RAW": evaluate_ball(rv, labels, clip["width"], clip["height"], clip["fps"]),
                       "RF_DETR_Nano": evaluate_ball(rf, labels, clip["width"], clip["height"], clip["fps"])}
            clip_results.append({"clip": clip["id"], "metrics": metrics, "raw_output": str(raw_path),
                                 "raw_sha256": file_sha256(raw_path), "scene_strata": clip["scene_strata"]})
            # Offset source frame IDs solely for aggregate counting; never report this as a real timeline.
            all_truth.extend({**r, "source_frame": r["source_frame"]+offset} for r in labels)
            all_rv.extend(FrameObservation(r.source_frame+offset, r.timestamp_ms, r.detections, r.model, r.source) for r in rv)
            all_rf.extend(FrameObservation(r.source_frame+offset, r.timestamp_ms, r.detections, r.model, r.source) for r in rf)
            offset += clip["frames"] + 1000
            print(json.dumps({"clip": clip["id"], "RF_recall": metrics["RF_DETR_Nano"]["recall"],
                              "RV_recall": metrics["RacketVision_RAW"]["recall"]}), flush=True)
        aggregate = {"RacketVision_RAW": evaluate_ball(all_rv, all_truth, 1920, 1080, 50),
                     "RF_DETR_Nano": evaluate_ball(all_rf, all_truth, 1920, 1080, 50)}
        rf_metrics, rv_metrics = aggregate["RF_DETR_Nano"], aggregate["RacketVision_RAW"]
        decision = "WINNER" if (rf_metrics["recall"] >= rv_metrics["recall"] and
                                rf_metrics["false_detections"] <= rv_metrics["false_detections"]) else (
                   "PROMISING_FINE_TUNE" if rf_metrics["recall"] >= .5 else "NO_VALUE")
        report = {"experiment": "PRETRAINED_NANO_RAW_SPARSE_DEV", "manifest_sha256": args.manifest_sha,
                  "checkpoint_sha256": CHECKPOINT_SHA, "license": "Apache-2.0 core Nano",
                  "code_commit": "7433d5919d0f7e72cc6cb78663e0a731afd499e0", "model_version": metadata.version("rfdetr"),
                  "threshold": manifest["rf_detr_threshold"], "sports_ball_class_id": sports_id,
                  "class_selection": "OFFICIAL_NATIVE_PER_DETECTION_CLASS_NAME",
                  "score_semantics": "DETECTOR_SCORE_NOT_CALIBRATED_PROBABILITY", "clips": clip_results,
                  "aggregate": aggregate, "decision": decision,
                  "suitability": "PRETRAINED_NOT_SUITABLE" if decision == "NO_VALUE" else "RESEARCH_ONLY",
                  "ranking": rank_models([{"manifest_sha256": args.manifest_sha, "model": name, "metrics": m}
                                          for name, m in aggregate.items()]),
                  "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                              "device": args.device, "cuda_build": torch.version.cuda,
                              "gpu": torch.cuda.get_device_name(0) if args.device == "cuda" else "NOT_USED_CPU_FALLBACK",
                              "load_seconds_including_imports": load_seconds,
                              "predict_seconds": sum(timings), "predict_fps": len(timings)/sum(timings),
                              "mean_predict_ms": statistics.mean(timings)*1000, "decode_seconds": sum(decode_times),
                              "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if args.device == "cuda" else None,
                              "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if args.device == "cuda" else None,
                              "process_peak_rss_bytes": max(s["rss"] for s in samples),
                              "minimum_system_available_bytes": min(s["available"] for s in samples)},
                  "downstream_hit": "NOT_EVALUABLE_SPARSE_OBSERVATIONS_AND_NO_ALIGNED_STROKE_GT",
                  "limitations": ["Known TRAIN clips, not untouched generalization", "scene strata unreviewed",
                                  "FP/min and FN/min unavailable for sparse labels", "No fine-tuning",
                                  "RacketVision runtime not remeasured on this cache comparison"],
                  "production_database": "NOT_ACCESSED", "training": "NONE"}
        write_report(target, report)
        print(json.dumps({"report": str(target), "decision": decision, "aggregate": aggregate, "runtime": report["runtime"]}), flush=True)
    except Exception as error:
        failure = {"status": "FAILED_ATTEMPT_NOT_ACCURACY_EVALUATION", "error": str(error),
                   "completed_frames": completed_frames, "manifest_sha256": args.manifest_sha,
                   "checkpoint_sha256": CHECKPOINT_SHA,
                   "peak_process_rss_bytes": max((s["rss"] for s in samples), default=None),
                   "minimum_available_bytes": min((s["available"] for s in samples), default=None),
                   "runtime_seconds": time.perf_counter()-started}
        failure_path = root / f"rf-detr-failure-{time.time_ns()}.json"
        failure_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure), flush=True)
        raise
    finally:
        stop.set()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
