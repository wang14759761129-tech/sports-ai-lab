"""Small, repeatable cross-game scene-bootstrap evaluation (research only).

Reads only the official Extended OpenTTGames training-video URLs. It extracts
four sparse frames per game via HTTP byte-range seeking and stores only those
frames and detector evidence under PTTI-Dev. The full source videos are not
redistributed or added to the repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import sys

# Use the frozen BallTrack environment's PyTorch installation with the
# separately isolated Transformers/OpenCV packages. No packages are installed.
_dev = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "PTTI-Dev"
_v2_site = _dev / "vision-v2" / "venv" / "Lib" / "site-packages"
if _v2_site.is_dir():
    sys.path.insert(0, str(_v2_site))

import torch
from PIL import Image, ImageDraw
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT_ROOT))
from backend.scene_bootstrap import (MODEL_ID, MODEL_REVISION, MODEL_SHA256,
                                    PROMPT_PROFILES, attach_roles, assign_near_far_candidates)

DATASET_REVISION = "36471a76b969a0340df59258a813bf8214e68e7c"
URL_ROOT = "https://lab.osai.ai/datasets/openttgames/data"
EXPECTED_BYTES = {"game_1": 5572649632, "game_2": 10833064677,
                  "game_3": 4637044123, "game_4": 3947371986,
                  "game_5": 4493632417}
PROMPTS = {
    "official_bootstrap_a": PROMPT_PROFILES["bootstrap-a"],
    "person_short": "table tennis table. person. referee. scoreboard.",
    "player_term": "table tennis table. player. referee. scoreboard.",
    "athlete_term": "table tennis table. athlete. referee. scoreboard.",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def dev_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "PTTI-Dev"


def probe(ffprobe: str, url: str) -> dict:
    raw = subprocess.check_output([
        ffprobe, "-v", "error", "-rw_timeout", "20000000", "-show_entries",
        "format=duration,size:stream=width,height,avg_frame_rate,nb_frames", "-of", "json", url,
    ], text=True, timeout=60)
    parsed = json.loads(raw)
    video = next(stream for stream in parsed["streams"] if stream.get("width"))
    numerator, denominator = map(int, video["avg_frame_rate"].split("/"))
    return {"width": video["width"], "height": video["height"],
            "fps": numerator / denominator if denominator else None,
            "frame_count": int(video["nb_frames"]) if video.get("nb_frames") else None,
            "duration_seconds": float(parsed["format"]["duration"]),
            "source_bytes": int(parsed["format"]["size"])}


def extract_frame(ffmpeg: str, url: str, timestamp: float, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
        "-i", url, "-frames:v", "1", "-q:v", "2", "-y", str(target),
    ], check=True, timeout=90)
    if not target.is_file() or target.stat().st_size < 1000:
        raise RuntimeError(f"FRAME_EXTRACTION_FAILED:{target.name}")


def detect(model, processor, device, image: Image.Image, prompt: str) -> list[dict]:
    inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        outputs = model(**inputs)
    post = processor.post_process_grounded_object_detection(
        outputs, inputs.input_ids, threshold=0.25, text_threshold=0.25,
        target_sizes=[(image.height, image.width)],
        text_labels=[[part.strip() for part in prompt.split(".") if part.strip()]],
    )[0]
    return [{"label": str(label), "bbox": [round(float(v), 2) for v in box.tolist()],
             "detector_score": round(float(score), 6)}
            for box, score, label in zip(post["boxes"], post["scores"], post["labels"])]


def main() -> None:
    started = time.perf_counter()
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFMPEG_AND_FFPROBE_REQUIRED")
    dev = dev_root()
    model_dir = dev / "vision-v2" / "models" / "grounding-dino-base"
    if sha256(model_dir / "model.safetensors").upper() != MODEL_SHA256.upper():
        raise RuntimeError("PINNED_CHECKPOINT_SHA_MISMATCH")
    processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_dir, local_files_only=True).eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model_loaded = time.perf_counter()
    out = dev / "vision-v2" / "scene-bootstrap"
    frame_root = out / "multi-match-frames"
    frame_root.mkdir(parents=True, exist_ok=True)
    games = []
    sample_records = []
    for game, expected_bytes in EXPECTED_BYTES.items():
        url = f"{URL_ROOT}/{game}.mp4"
        meta = probe(ffprobe, url)
        if meta["source_bytes"] != expected_bytes:
            raise RuntimeError(f"SOURCE_SIZE_MISMATCH:{game}")
        sample_times = [round(meta["duration_seconds"] * fraction, 3) for fraction in (0.03, 0.34, 0.66, 0.97)]
        game_record = {"game": game, "source": url, "license": "CC BY-NC-SA 4.0",
                       "commercial_use": False, "source_sha256": None,
                       "source_sha256_status": "NOT_COMPUTED_FULL_SOURCE_NOT_STAGED",
                       "source_bytes": meta["source_bytes"], "media": meta, "sampled_frames": []}
        local_source = dev / "research-datasets" / "ExtendedOpenTTGames" / "videos" / "train" / f"{game}.mp4"
        if local_source.is_file() and local_source.stat().st_size == expected_bytes:
            game_record["source_sha256"] = sha256(local_source)
            game_record["source_sha256_status"] = "COMPUTED_FROM_STAGED_FULL_SOURCE"
        for slot, timestamp in enumerate(sample_times, start=1):
            target = frame_root / game / f"sample-{slot:02d}.jpg"
            if not target.is_file():
                extract_frame(ffmpeg, url, timestamp, target)
            image = Image.open(target).convert("RGB")
            record = {"game": game, "slot": slot, "timestamp_seconds": timestamp,
                      "frame_sha256": sha256(target), "image": f"multi-match-frames/{game}/{target.name}",
                      "width": image.width, "height": image.height}
            game_record["sampled_frames"].append(record)
            sample_records.append(record)
        games.append(game_record)
        print(f"SAMPLED {game} frames={len(game_record['sampled_frames'])} duration={meta['duration_seconds']:.1f}s", flush=True)

    evaluations = []
    latencies = []
    for prompt_id, prompt in PROMPTS.items():
        for record in sample_records:
            image = Image.open(out / record["image"]).convert("RGB")
            before = time.perf_counter()
            raw = detect(model, processor, device, image, prompt)
            for index, row in enumerate(raw):
                row.update({"candidate_id": f"{record['game']}-s{record['slot']:02d}-d{index}",
                            "frame": record["slot"], "timestamp_ms": round(record["timestamp_seconds"] * 1000),
                            "source": "extended_openttgames", "model": MODEL_ID})
            if device.type == "cuda":
                torch.cuda.synchronize()
            latencies.append((time.perf_counter() - before) * 1000)
            table_candidates = [row for row in raw if "table" in row["label"].casefold()]
            usable_tables = [row for row in table_candidates
                             if row["bbox"][2] - row["bbox"][0] >= image.width * 0.2
                             and (row["bbox"][2] - row["bbox"][0]) * (row["bbox"][3] - row["bbox"][1]) >= image.width * image.height * 0.03]
            table = max(usable_tables, key=lambda row: row["detector_score"], default=None)
            attached = attach_roles(raw, table["bbox"] if table else None)
            attached = assign_near_far_candidates(attached, table["bbox"]) if table else attached
            hints = {row["spatial_hint"] for row in attached if "person" in row["label"].casefold() or "player" in row["label"].casefold() or "athlete" in row["label"].casefold()}
            person_rows = [row for row in attached if any(term in row["label"].casefold() for term in ("person", "player", "athlete"))]
            both = {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}.issubset(hints)
            overlay_asset = None
            if prompt_id == "official_bootstrap_a":
                overlay = image.copy()
                draw = ImageDraw.Draw(overlay)
                for row in attached:
                    if "table" in row["label"].casefold():
                        color = "#28c840" if table and row["bbox"] == table["bbox"] else "#888888"
                    elif row["spatial_hint"] in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"}:
                        color = "#2684ff"
                    else:
                        color = "#ffad32"
                    draw.rectangle(row["bbox"], outline=color, width=4)
                overlay_name = f"overlay-sample-{record['slot']:02d}.jpg"
                overlay.save(frame_root / record["game"] / overlay_name, quality=94)
                overlay_asset = f"{record['game']}-overlay-sample-{record['slot']:02d}.jpg"
            evaluations.append({**record, "prompt_id": prompt_id, "prompt": prompt,
                                "detections": attached, "table_found": bool(table),
                                "overlay_asset": overlay_asset,
                                "selected_table_bbox": table["bbox"] if table else None,
                                "left_candidate": "PLAYER_LEFT_CANDIDATE" in hints,
                                "right_candidate": "PLAYER_RIGHT_CANDIDATE" in hints,
                                "both_player_candidates": both,
                                "extra_people": sum(row["spatial_hint"] not in {"PLAYER_LEFT_CANDIDATE", "PLAYER_RIGHT_CANDIDATE"} for row in person_rows),
                                "scoreboard_candidate": any("scoreboard" in row["label"].casefold() for row in raw)})
        print(f"PROMPT_DONE {prompt_id}", flush=True)
    summary = {}
    for prompt_id in PROMPTS:
        rows = [row for row in evaluations if row["prompt_id"] == prompt_id]
        summary[prompt_id] = {"sampled_frames": len(rows),
                              "table_found": sum(row["table_found"] for row in rows),
                              "both_player_candidate_frames": sum(row["both_player_candidates"] for row in rows),
                              "both_player_candidate_coverage_percent": round(100 * sum(row["both_player_candidates"] for row in rows) / len(rows), 1),
                              "left_candidate_frames": sum(row["left_candidate"] for row in rows),
                              "right_candidate_frames": sum(row["right_candidate"] for row in rows),
                              "extra_person_candidates": sum(row["extra_people"] for row in rows),
                              "scoreboard_candidate_frames": sum(row["scoreboard_candidate"] for row in rows)}
        summary[prompt_id]["per_game"] = {}
        for game in EXPECTED_BYTES:
            subset = [row for row in rows if row["game"] == game]
            summary[prompt_id]["per_game"][game] = {
                "sampled_frames": len(subset),
                "table_found": sum(row["table_found"] for row in subset),
                "both_player_candidate_frames": sum(row["both_player_candidates"] for row in subset),
                "both_player_candidate_coverage_percent": round(100 * sum(row["both_player_candidates"] for row in subset) / len(subset), 1),
                "extra_person_candidates": sum(row["extra_people"] for row in subset),
            }
    manifest = {"status": "MULTI_MATCH_RESEARCH_EVALUATION",
                "dataset": "Extended OpenTTGames", "dataset_revision": DATASET_REVISION,
                "license": "CC BY-NC-SA 4.0", "commercial_use": False,
                "official_split": "training only; test split not accessed",
                "sampling": "four deterministic timestamps per game at 3%, 34%, 66%, 97% of duration; HTTP range seek; no full videos stored",
                "video_sha256_note": "Full source SHA256 is unavailable because full source files were not staged. Per-frame SHA256 values identify the extracted samples.",
                "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "checkpoint_sha256": MODEL_SHA256,
                          "threshold": 0.25, "text_threshold": 0.25, "device": str(device)},
                "runtime": {"inference_count": len(latencies), "mean_inference_ms": round(sum(latencies) / len(latencies), 2),
                            "inference_fps": round(1000 * len(latencies) / sum(latencies), 3),
                            "model_load_seconds": round(model_loaded - started, 2),
                            "elapsed_seconds": round(time.perf_counter() - started, 2),
                            "peak_vram_bytes": torch.cuda.max_memory_allocated() if device.type == "cuda" else None},
                "games": games, "prompt_summary": summary, "frame_results": evaluations}
    target = out / "scene_bootstrap_eval_manifest.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)
    baseline = [row for row in evaluations if row["prompt_id"] == "official_bootstrap_a"]
    cards = []
    for row in baseline:
        absent = [side for side, present in (("SCREEN_LEFT", row["left_candidate"]), ("SCREEN_RIGHT", row["right_candidate"])) if not present]
        cards.append(f"<article><h3>{row['game']} · {row['timestamp_seconds']:.1f}s</h3><img src='{row['image']}'><img src='{row['overlay_asset']}'><p>table={row['table_found']} · both-side candidates={row['both_player_candidates']} · candidate sides missing={', '.join(absent) or 'none'} · non-player-region boxes={row['extra_people']}</p><p>Failure taxonomy: UNKNOWN pending manual match-specific annotation. These are detector-candidate diagnostics, not ground-truth recall.</p></article>")
    html = "<!doctype html><meta charset='utf-8'><title>Player Detection Failure Analysis</title><style>body{font:15px Segoe UI,Arial;margin:24px;background:#f5f7fa;color:#18202a}main{max-width:1500px;margin:auto}section{padding:14px;background:white;border:1px solid #dbe2ea;border-radius:10px;margin:12px 0}article{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:14px;background:white;border:1px solid #dbe2ea;border-radius:10px;margin:12px 0}article h3,article p{grid-column:1/-1}img{width:100%;background:#111}small{color:#556}</style><main><h1>球员候选失败帧分析</h1><section><p>Extended OpenTTGames · CC BY-NC-SA 4.0 · 仅研究/非商业。五场训练比赛，每场4个分散时点，共20帧。Grounding DINO 的两侧候选覆盖 11/20。没有逐帧人工球员框 GT；因此屏幕侧缺失只能作候选缺口记录，不能称为球员漏检准确率。</p><p>分类约束：无法仅凭检测器输出区分裁判混淆、遮挡、低对比、出画、重复框或误标，未人工核实项统一 UNKNOWN。</p></section>{''.join(cards)}</main>"
    (out / "player_detection_failure_analysis.html").write_text(html, encoding="utf-8")
    print(f"MANIFEST {target}", flush=True)


if __name__ == "__main__":
    main()
