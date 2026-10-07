"""Render a local TRAIN-only evidence-fusion preview from cached observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import os
import sys

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from backend.player_motion import pose_file_sha256


SKELETON = (
    ("left_shoulder", "right_shoulder"), ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"), ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"), ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"), ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
)


def render(run_directory: Path, sample_id: str) -> Path:
    import cv2

    run_directory = run_directory.resolve()
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")).resolve()
    allowed_root = (local / "PTTI-Dev" / "vision-v2-evidence-fusion" / "evaluation").resolve()
    if not run_directory.is_relative_to(allowed_root):
        raise ValueError("OUTPUT_MUST_STAY_IN_PTTI_DEV_EVALUATION")
    sample_dir = (run_directory / sample_id).resolve()
    if not sample_dir.is_relative_to(run_directory):
        raise ValueError("INVALID_SAMPLE_DIRECTORY")
    manifest = json.loads((sample_dir / "clip_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("official_split") != "TRAIN" or manifest.get("commercial_use") is not False:
        raise ValueError("ONLY_NONCOMMERCIAL_TRAIN_CLIPS_CAN_BE_RENDERED")
    source = Path(manifest["video_path"]).resolve()
    if pose_file_sha256(source) != manifest["video_sha256"]:
        raise ValueError("SOURCE_CHANGED_SINCE_EVALUATION")
    evidence = [json.loads(line) for line in (sample_dir / "frame_evidence.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    candidates = json.loads((sample_dir / "hit_candidates.json").read_text(encoding="utf-8"))
    by_frame = {int(row["processing_frame"]): row for row in evidence}
    events_by_frame: dict[int, list[dict]] = {}
    for event in candidates:
        if event.get("frame") is not None:
            events_by_frame.setdefault(int(event["frame"]), []).append(event)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError("SOURCE_VIDEO_COULD_NOT_BE_OPENED")
    fps = float(manifest["timeline_audit"]["processing_fps"])
    frame_count = int(manifest["timeline_audit"]["processing_frames"])
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)); height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output = sample_dir / "evidence_fusion_overlay.mp4"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("MP4_PREVIEW_ENCODER_UNAVAILABLE")
    colors = {"NEAR_PLAYER": (64, 210, 186), "FAR_PLAYER": (68, 157, 255)}
    try:
        for frame_index in range(frame_count):
            ok, image = capture.read()
            if not ok:
                raise ValueError(f"SOURCE_DECODE_STOPPED_AT_FRAME:{frame_index}")
            row = by_frame.get(frame_index)
            if row is not None:
                for role, color in colors.items():
                    player = row.get("players", {}).get(role) or {}
                    track = player.get("track") or {}
                    box = track.get("bbox")
                    if box and len(box) == 4:
                        x0, y0, x1, y1 = map(int, box)
                        cv2.rectangle(image, (x0, y0), (x1, y1), color, 2)
                        name = "NEAR" if role == "NEAR_PLAYER" else "FAR"
                        cv2.putText(image, name, (x0, max(24, y0 - 7)), cv2.FONT_HERSHEY_SIMPLEX,
                                    .65, color, 2, cv2.LINE_AA)
                    pose = player.get("pose") or {}
                    points = pose.get("keypoints") or {}
                    if pose.get("pose_quality") not in {"GOOD", "PARTIAL"}:
                        continue
                    for first, second in SKELETON:
                        a, b = points.get(first), points.get(second)
                        if a and b and min(float(a.get("score", 0)), float(b.get("score", 0))) >= .35:
                            cv2.line(image, (int(a["x_global"]), int(a["y_global"])),
                                     (int(b["x_global"]), int(b["y_global"])), color, 3, cv2.LINE_AA)
                    for point in points.values():
                        if float(point.get("score", 0)) >= .35:
                            cv2.circle(image, (int(point["x_global"]), int(point["y_global"])), 4,
                                       color, -1, cv2.LINE_AA)
                ball = row.get("ball") or {}
                if ball.get("visible") and ball.get("x") is not None and ball.get("y") is not None:
                    position = (int(ball["x"]), int(ball["y"]))
                    cv2.circle(image, position, 11, (0, 232, 255), 3, cv2.LINE_AA)
                for event in events_by_frame.get(frame_index, []):
                    player = event.get("candidate_player")
                    who = "Near" if player == "NEAR_PLAYER" else "Far" if player == "FAR_PLAYER" else "待确认"
                    cv2.rectangle(image, (12, 12), (310, 54), (18, 24, 27), -1)
                    cv2.putText(image, f"HIT? {who}", (22, 42), cv2.FONT_HERSHEY_SIMPLEX,
                                .9, (80, 238, 255), 2, cv2.LINE_AA)
            writer.write(image)
    finally:
        capture.release(); writer.release()
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("OVERLAY_OUTPUT_MISSING")
    print(json.dumps({"path": str(output), "size_bytes": output.stat().st_size,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "frames": frame_count, "fps": fps, "official_split": "TRAIN",
                      "production_database": "NOT_ACCESSED", "official_test_split": "NOT_ACCESSED"},
                     ensure_ascii=False, indent=2))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--sample-id", choices=("game_1-t60", "game_2-t60", "game_3-t60",
                                                  "game_4-t30", "game_5-t60"), required=True)
    args = parser.parse_args()
    render(args.run_directory, args.sample_id)


if __name__ == "__main__":
    main()
