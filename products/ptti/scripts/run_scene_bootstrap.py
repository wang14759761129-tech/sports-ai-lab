"""Run a research-only Grounding DINO scene bootstrap on game_4.

All inputs are pinned to the staged Extended OpenTTGames training sample. All
outputs are written under PTTI-Dev and must not be redistributed commercially.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import cv2
import torch
import transformers
from PIL import Image, ImageDraw
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.scene_bootstrap import (  # noqa: E402
    MODEL_ID, MODEL_REVISION, MODEL_SHA256, MODEL_BYTES, PROMPT_PROFILES,
    attach_roles,
)
from backend.vision_v2 import KeyframeSampler, SceneBoundaryDetector  # noqa: E402

VIDEO_BYTES = 3_947_371_986
VIDEO_SHA256 = "DDB2BC49915A99DB46702825FF322759FAA9205C846A1BA902419E38C1E23B39"
ANNOTATION_SHA256 = "9D6A558A1A933341B9C9BEABC8561327DA928E387D4FE743A492F76627207271"
EXPECTED_FRAMES = 63_120
EXPECTED_DURATION_S = 526.0
PROMPT_ID = os.environ.get("PTTI_SCENE_BOOTSTRAP_PROMPT", "bootstrap-a")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def dev_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    return base / "PTTI-Dev"


def verify_inputs(dev: Path) -> tuple[Path, Path, Path]:
    root = dev / "research-datasets" / "ExtendedOpenTTGames"
    video = root / "videos" / "train" / "game_4.mp4"
    annotation = root / "annotations" / "train" / "game_data" / "game_4.json"
    license_file = root / "source-snapshot" / "LICENSE"
    if not video.is_file() or video.stat().st_size != VIDEO_BYTES or digest(video) != VIDEO_SHA256.upper():
        raise RuntimeError("SOURCE_VIDEO_INTEGRITY_FAILED")
    if not annotation.is_file() or digest(annotation) != ANNOTATION_SHA256.upper():
        raise RuntimeError("SOURCE_ANNOTATION_INTEGRITY_FAILED")
    if not license_file.is_file() or "CC BY-NC-SA 4.0" not in license_file.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("SOURCE_LICENSE_NOT_VERIFIED")
    return video, annotation, license_file


def verify_checkpoint(model_dir: Path) -> None:
    config_path = model_dir / "config.json"
    weights = model_dir / "model.safetensors"
    if not config_path.is_file() or not weights.is_file():
        raise RuntimeError("PINNED_CHECKPOINT_MISSING")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("model_type") != "grounding-dino" or "GroundingDino" not in " ".join(config.get("architectures", [])):
        raise RuntimeError("CHECKPOINT_ARCHITECTURE_MISMATCH")
    if weights.stat().st_size != MODEL_BYTES or digest(weights) != MODEL_SHA256.upper():
        raise RuntimeError("CHECKPOINT_INTEGRITY_FAILED")


def sample_frames(video: Path) -> tuple[list[dict], dict]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError("VIDEO_DECODE_OPEN_FAILED")
    fps = cap.get(cv2.CAP_PROP_FPS)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if count != EXPECTED_FRAMES or abs(count / fps - EXPECTED_DURATION_S) > 0.02:
        cap.release()
        raise RuntimeError("VIDEO_PROBE_MISMATCH")
    detector = SceneBoundaryDetector(threshold=0.48, minimum_gap_frames=round(fps * 2))
    cuts = []
    # Scene detector samples every two seconds over the full video. Each cut is
    # still a candidate and triggers a fresh detector keyframe below.
    frame_no = 0
    sample_step = round(fps * 2)
    print(f"SOURCE_VERIFIED duration={count / fps:.2f}s fps={fps:g} frames={count}", flush=True)
    while frame_no < count:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, bgr = cap.read()
        if not ok:
            break
        small = cv2.resize(bgr, (320, 180), interpolation=cv2.INTER_AREA)
        candidate = detector.observe(frame_no, round(frame_no * 1000 / fps), cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        if candidate:
            cuts.append({"frame": candidate.frame, "timestamp_ms": candidate.timestamp_ms,
                         "status": candidate.status,
                         "evidence": [e.__dict__ for e in candidate.evidence]})
        frame_no += sample_step
        if frame_no % round(fps * 60) < sample_step:
            print(f"SCENE_SCAN {min(frame_no, count)}/{count} frames cuts={len(cuts)}", flush=True)
    sampler = KeyframeSampler(interval_seconds=20.0)
    keyframes = sampler.sample(count, fps, scene_cut_frames=(x["frame"] for x in cuts))
    # Bound the gallery to 50 frames; retain start/end and distribute the rest
    # deterministically when cut candidates are unusually numerous.
    if len(keyframes) > 50:
        protected = {i for i, item in enumerate(keyframes)
                     if set(item.reasons) & {"VIDEO_START", "VIDEO_END", "SCENE_CHANGE"}}
        slots = max(0, 50 - len(protected))
        optional = [i for i in range(len(keyframes)) if i not in protected]
        chosen = {optional[round(i * (len(optional) - 1) / max(1, slots - 1))]
                  for i in range(slots)} if slots and optional else set()
        keyframes = [keyframes[i] for i in sorted(protected | chosen)]
    records = []
    frame_dir = dev_root() / "vision-v2" / "scene-bootstrap" / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for key in keyframes:
        cap.set(cv2.CAP_PROP_POS_FRAMES, key.frame)
        ok, bgr = cap.read()
        if not ok:
            raise RuntimeError(f"KEYFRAME_DECODE_FAILED:{key.frame}")
        path = frame_dir / f"frame-{key.frame:06d}.jpg"
        if not cv2.imwrite(str(path), bgr, [cv2.IMWRITE_JPEG_QUALITY, 94]):
            raise RuntimeError(f"KEYFRAME_WRITE_FAILED:{key.frame}")
        records.append({"frame": key.frame, "timestamp_ms": key.timestamp_ms,
                        "reasons": list(key.reasons), "image": path.name,
                        "width": width, "height": height})
    cap.release()
    return records, {"width": width, "height": height, "fps": fps, "frame_count": count,
                     "duration_s": count / fps, "scene_cuts": cuts, "sample_step_frames": sample_step}


def main() -> None:
    job_started = time.perf_counter()
    dev = dev_root()
    out = dev / "vision-v2" / "scene-bootstrap"
    out.mkdir(parents=True, exist_ok=True)
    video, annotation, license_file = verify_inputs(dev)
    model_dir = dev / "vision-v2" / "models" / "grounding-dino-base"
    verify_checkpoint(model_dir)
    sampling_started = time.perf_counter()
    frames, media = sample_frames(video)
    sampling_seconds = time.perf_counter() - sampling_started
    model_started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_dir, local_files_only=True).eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model_load_s = time.perf_counter() - model_started
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    prompt = PROMPT_PROFILES[PROMPT_ID]
    detections = []
    latency = []
    image_dir = out / "frames"
    overlay_dir = out / "scene_bootstrap_overlay"
    overlay_dir.mkdir(exist_ok=True)
    for item in frames:
        path = image_dir / item["image"]
        image = Image.open(path).convert("RGB")
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
        started = time.perf_counter()
        with torch.inference_mode():
            outputs = model(**inputs)
        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - started) * 1000
        latency.append(elapsed)
        print(f"DETECT {item['frame']} ms={elapsed:.1f} n={len(latency)}/{len(frames)}", flush=True)
        post = processor.post_process_grounded_object_detection(
            outputs, inputs.input_ids, threshold=0.25, text_threshold=0.25,
            target_sizes=[(image.height, image.width)],
            text_labels=[[part.strip() for part in prompt.split(".") if part.strip()]],
        )[0]
        this = []
        for n, (box, score, label) in enumerate(zip(post["boxes"], post["scores"], post["labels"])):
            xyxy = [round(float(v), 2) for v in box.tolist()]
            phrase = str(label)
            candidate = {"candidate_id": f"f{item['frame']}-d{n}", "frame": item["frame"],
                         "timestamp_ms": item["timestamp_ms"], "label": phrase, "bbox": xyxy,
                         "detector_score": round(float(score), 6), "prompt": prompt,
                         "model": MODEL_ID, "model_revision": MODEL_REVISION,
                         "source": "extended_openttgames", "status": "SUGGESTED"}
            this.append(candidate)
        table_rows = [d for d in this if "table" in d["label"].casefold()]
        usable_tables = [d for d in table_rows if
                         (d["bbox"][2]-d["bbox"][0]) >= image.width * 0.2 and
                         (d["bbox"][2]-d["bbox"][0])*(d["bbox"][3]-d["bbox"][1]) >= image.width*image.height*0.03]
        table = max(usable_tables, key=lambda d: d["detector_score"], default=None)
        role_assigned = attach_roles(this, table["bbox"] if table else None)
        detections.extend(role_assigned)
        draw = ImageDraw.Draw(image)
        colors = {"PLAYER_A": "#3b82f6", "PLAYER_B": "#f59e0b", "REFEREE": "#ef4444"}
        for d in role_assigned:
            d["visualization_suppressed"] = False
        for candidate in (d for d in role_assigned if "table" in d["label"].casefold()):
            candidate["visualization_suppressed"] = candidate["candidate_id"] != (table or {}).get("candidate_id")
        for d in role_assigned:
            if d["visualization_suppressed"]:
                continue
            box = d["bbox"]
            role = d["role"]
            hint = d["spatial_hint"]
            color = colors.get(role, "#22c55e" if "table" in d["label"].casefold() else
                               "#3b82f6" if hint in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"} else
                               "#f59e0b" if hint == "REFEREE_OTHER_CANDIDATE" else "#a855f7")
            display_label = (hint if hint.endswith("CANDIDATE") else role) if "person" in d["label"].casefold() else ("TABLE" if "table" in d["label"].casefold() else role)
            draw.rectangle(box, outline=color, width=4)
            draw.text((box[0] + 2, max(0, box[1] - 20)), f"{display_label} · {d['label']} · {d['detector_score']:.2f}", fill=color)
        draw.text((10, 10), f"frame {item['frame']} · {item['timestamp_ms']} ms", fill="#ffffff", stroke_width=2, stroke_fill="#111827")
        item["overlay"] = "overlay-" + item["image"]
        overlay_path = overlay_dir / item["overlay"]
        image.save(overlay_path, quality=94)

    frames_by = {f["frame"]: f for f in frames}
    grouped = {}
    for d in detections:
        grouped.setdefault(d["frame"], []).append(d)
    for item in frames:
        rows = grouped.get(item["frame"], [])
        people = [x for x in rows if "person" in x["label"].casefold() or "player" in x["label"].casefold()]
        tables = [x for x in rows if "table" in x["label"].casefold() and x["visualization_suppressed"] is False and
                  (x["bbox"][2]-x["bbox"][0]) >= item["width"]*0.2 and
                  (x["bbox"][2]-x["bbox"][0])*(x["bbox"][3]-x["bbox"][1]) >= item["width"]*item["height"]*0.03]
        boards = [x for x in rows if "scoreboard" in x["label"].casefold()]
        item["detections"] = rows
        item["table_found"] = bool(tables)
        player_sides = {x["spatial_hint"] for x in people}
        item["player_candidates"] = int({"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}.issubset(player_sides))
        item["extra_people"] = sum(x["spatial_hint"] == "REFEREE_OTHER_CANDIDATE" or x["role"] in {"REFEREE", "OTHER"} for x in people)
        item["unknown_people"] = sum(x["role"] == "UNKNOWN" and x["spatial_hint"] not in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"} for x in people)
        item["scoreboard_candidate"] = bool(boards)
        item["review_required"] = True
    report = {
        "status": "RESEARCH_CANDIDATES_READY", "dataset": "Extended OpenTTGames",
        "dataset_repository": "https://github.com/moamal01/table_tennis_data",
        "dataset_revision": "36471a76b969a0340df59258a813bf8214e68e7c",
        "rights": "CC BY-NC-SA 4.0", "commercial_use": False,
        "source": {"video": str(video), "video_sha256": VIDEO_SHA256, "video_size_bytes": VIDEO_BYTES,
                   "annotations_sha256": ANNOTATION_SHA256, "license_file": str(license_file)},
        "media": media, "keyframes": frames, "detections": detections,
        "metrics": {"sampled_frames": len(frames),
                    "table_found_percent": round(100 * sum(f["table_found"] for f in frames) / max(1, len(frames)), 1),
                    "two_player_candidate_percent": round(100 * sum(f["player_candidates"] for f in frames) / max(1, len(frames)), 1),
                    "extra_person_detections": sum(f["extra_people"] for f in frames),
                    "unknown_person_candidates": sum(f["unknown_people"] for f in frames),
                    "scoreboard_candidate_percent": round(100 * sum(f["scoreboard_candidate"] for f in frames) / max(1, len(frames)), 1),
                    "review_required_frames": sum(f["review_required"] for f in frames)},
        "runtime": {"python": platform.python_version(), "torch": torch.__version__,
                    "transformers": transformers.__version__, "opencv": cv2.__version__,
                    "cuda": torch.version.cuda, "device": str(device),
                    "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
                    "model_load_seconds": round(model_load_s, 2),
                    "scene_sampling_seconds": round(sampling_seconds, 2),
                    "inference_ms_mean": round(statistics.mean(latency), 2) if latency else None,
                    "inference_ms_median": round(statistics.median(latency), 2) if latency else None,
                    "inference_fps": round(1000 / statistics.mean(latency), 3) if latency else None,
                    "peak_vram_bytes": torch.cuda.max_memory_allocated() if device.type == "cuda" else None,
                    "total_vram_bytes": torch.cuda.get_device_properties(0).total_memory if device.type == "cuda" else None,
                    "total_job_seconds": round(time.perf_counter()-job_started, 2)},
        "execution": {"code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                      "source_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())},
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "checkpoint_sha256": MODEL_SHA256,
                  "license": "Apache-2.0", "code_license": "Apache-2.0",
                  "checkpoint_source": "https://huggingface.co/IDEA-Research/grounding-dino-base",
                  "prompt_id": PROMPT_ID, "prompt": prompt, "box_threshold": 0.25,
                  "text_threshold": 0.25},
        "interpretation": {"detector_score": "raw model output; not a calibrated probability",
                           "player_roles": "spatial candidates, require human review",
                           "scoreboard": "candidate localization only; OCR is disabled",
                           "scene_cut": "histogram difference candidates trigger keyframe sampling"},
    }
    target = out / "scene_bootstrap.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)
    cards = "\n".join(
        f'<figure><img src="scene_bootstrap_overlay/{f["overlay"]}" alt="检测叠加"><figcaption>{f["timestamp_ms"] / 1000:.2f}s · 帧 {f["frame"]} · {len(f["detections"])} 个候选框</figcaption></figure>'
        for f in frames
    )
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PTTI 场景识别研究结果</title>'
            '<style>body{font:15px system-ui;margin:24px;background:#f3f5f7;color:#17202b}main{max-width:1200px;margin:auto}section{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}figure{margin:0;background:white;padding:10px;border-radius:10px}img{width:100%;height:auto}figcaption{padding:6px}</style>'
            '<main><h1>PTTI 真实场景识别候选</h1><p>Extended OpenTTGames · CC BY-NC-SA 4.0 · 仅限研究 / 非商业用途。检测分数不是校准概率，所有角色均须人工复核。</p><section>'
            + cards + '</section></main></html>')
    (out / "scene_bootstrap_gallery.html").write_text(html, encoding="utf-8")
    print(json.dumps({"output": str(target), "metrics": report["metrics"], "runtime": report["runtime"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
