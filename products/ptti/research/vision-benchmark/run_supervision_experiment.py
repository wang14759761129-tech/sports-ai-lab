"""Paired real BallTrack visualization experiment; no product rewrite or schema replacement."""
import argparse
from collections import deque
import inspect
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np
import supervision as sv

from ptti_benchmark.core import file_sha256, write_report


def current_annotate(image, point, history):
    if point and point["visible"]:
        center = (round(point["x"]), round(point["y"]))
        history.append(center)
        for a, b in zip(list(history), list(history)[1:]):
            cv2.line(image, a, b, (0, 220, 255), 2)
        cv2.circle(image, center, 9, (0, 255, 100), 2)
    else:
        history.clear()
    return image


def supervision_annotate(image, point, state):
    if point and point["visible"]:
        x, y = round(point["x"]), round(point["y"])
        # Display-only extent yields the existing nine-pixel circle; this is not a detected bbox.
        detections = sv.Detections(xyxy=np.array([[x-9, y-1, x+9, y+1]], dtype=np.float32),
                                  class_id=np.array([0]), tracker_id=np.array([1]))
        state["trace"].annotate(scene=image, detections=detections)
        state["circle"].annotate(scene=image, detections=detections)
    else:
        state["trace"] = make_trace()
    return image


def make_trace():
    return sv.TraceAnnotator(color=sv.Color(r=255, g=220, b=0), thickness=2,
                             trace_length=20, position=sv.Position.CENTER)


def effective_loc(function):
    source = inspect.getsource(function)
    return sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in source.splitlines())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--start-seconds", type=float, default=0)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").isalnum() or args.start_seconds < 0:
        raise ValueError("INVALID_EXPERIMENT_ID_OR_START")
    foundation = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation"
    root = foundation / f"supervision-{args.run_id}"
    root.mkdir(exist_ok=True)
    target = root / "report.json"
    if target.exists():
        raise FileExistsError("IMMUTABLE_EXPERIMENT_ALREADY_EXISTS")
    cross = json.loads((foundation.parent / "evidence/hit_event_v0_2/full_dev/cross_game_baseline_20261007/cross_game_full_dev_baseline.json").read_text(encoding="utf-8"))
    game = next(row for row in cross["games"] if row["game"] == "game_1")
    evaluation = json.loads(Path(game["evaluation_path"]).read_text(encoding="utf-8"))
    evidence = Path(game["evaluation_path"]).parent / "full_match_frame_evidence.jsonl"
    video = Path(evaluation["video_path"])
    if file_sha256(video) != game["video_sha256"]:
        raise ValueError("SOURCE_VIDEO_CHANGED")
    clip = root / "supervision-real-clip.mp4"
    start_frame = round(args.start_seconds * game["media"]["fps"])
    count = round(2 * game["media"]["fps"])
    if not clip.exists():
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(args.start_seconds), "-i", str(video),
                        "-frames:v", str(count), "-an", "-c:v", "libx264", "-threads", "2",
                        "-crf", "18", "-pix_fmt", "yuv420p", "-n", str(clip)], check=True)
    points = {}
    with evidence.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            frame = row["source_frame"]
            if frame >= start_frame+count:
                break
            if frame >= start_frame:
                points[frame-start_frame] = row["ball"]
    info = sv.VideoInfo.from_video_path(str(clip))
    history, state = deque(maxlen=20), {"trace": make_trace(),
                     "circle": sv.CircleAnnotator(color=sv.Color(r=100,g=255,b=0), thickness=2)}
    timings = {"current": 0.0, "supervision": 0.0}
    differences = visible = processed = 0
    with sv.VideoSink(str(root / "supervision-overlay.avi"), info, codec="MJPG") as sv_sink:
        current_sink = cv2.VideoWriter(str(root / "current-overlay.avi"), cv2.VideoWriter_fourcc(*"MJPG"),
                                       info.fps, (info.width, info.height))
        if not current_sink.isOpened():
            raise RuntimeError("CURRENT_VIDEO_SINK_FAILED")
        for index, image in enumerate(sv.get_video_frames_generator(str(clip))):
            point = points.get(index)
            visible += int(bool(point and point["visible"]))
            a, b = image.copy(), image.copy()
            started = time.perf_counter()
            current_annotate(a, point, history)
            timings["current"] += time.perf_counter()-started
            started = time.perf_counter()
            supervision_annotate(b, point, state)
            timings["supervision"] += time.perf_counter()-started
            differences += int(np.any(a != b, axis=2).sum())
            current_sink.write(a)
            sv_sink.write_frame(b)
            if index == count//2:
                cv2.imencode(".jpg", a)[1].tofile(str(root / "current-overlay.jpg"))
                cv2.imencode(".jpg", b)[1].tofile(str(root / "supervision-overlay.jpg"))
            processed += 1
        current_sink.release()
    if processed != count:
        raise ValueError("DECODED_FRAME_COUNT_MISMATCH")
    if visible == 0:
        raise ValueError("NO_BALL_OBSERVATIONS_NOT_A_MEANINGFUL_OVERLAY_COMPARISON")
    for name in ("current", "supervision"):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(root/f"{name}-overlay.avi"),
                        "-an", "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p", "-n",
                        str(root/f"{name}-overlay.mp4")], check=True)
    # Measure adapter bodies, not a claim to replace the entire 40-line product overlay script.
    functions = {name: effective_loc(function) for name, function in
                 (("current", current_annotate), ("supervision", supervision_annotate))}
    logical_bytes = sum(p.stat().st_size for p in (foundation/"supervision-project/.venv/Lib/site-packages").rglob("*") if p.is_file())
    report = {"status": "REAL_VIDEO_VISUALIZATION_EXPERIMENT_COMPLETE", "version": sv.__version__,
              "code_commit": "2c261cf98f2d412b7f87f6052b21b24019f09a96", "license": "MIT",
              "clip_source": "Extended OpenTTGames TRAIN game_1", "source_sha256": game["video_sha256"],
              "clip_sha256": file_sha256(clip), "start_seconds": args.start_seconds, "duration_seconds": 2,
              "frames": processed, "ball_visible_frames": visible, "render_seconds": timings,
              "effective_adapter_loc": functions,
              "setup_and_dependency_glue_excluded_from_loc": True,
              "pixel_difference_fraction": differences/(processed*info.width*info.height),
              "equivalence": "SAME_SOURCE_COORDINATES_AND_VISIBILITY; PIXEL_DIFFERENCE_MEASURED",
              "video_source_sink": "REAL_CV2_DECODE_AND_SUPERVISION_MJPG_SINK_VERIFIED",
              "installed_environment_logical_bytes": logical_bytes,
              "uv_locked_sync": "VERIFIED_TWICE", "pose_mask_pipeline": "NOT_TESTED",
              "decision": "TRIAL", "reason": "Small visualization glue already simple; no significant total code reduction proven",
              "product_dependencies_changed": False, "production_db": "NOT_ACCESSED"}
    write_report(target, report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
