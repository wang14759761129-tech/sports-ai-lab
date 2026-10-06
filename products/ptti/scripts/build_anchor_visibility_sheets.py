"""Create local-only human visibility-review sheets for the five QA clips.

The images stay under %LOCALAPPDATA%/PTTI-Dev and are never copied to Git.
Each tile is the midpoint of a half-second window; the reviewer assigns both
players one of VISIBLE, PARTIAL, OUT_OF_FRAME, or UNKNOWN for that window.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT_ROOT))

from PIL import Image, ImageDraw, ImageFont

from backend.player_tracking_closed_loop import closed_loop_root, list_closed_loop_samples


def main() -> None:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    root = local / "PTTI-Dev" / "vision-v2-sam2"
    out = root / "runs" / "anchor-guided" / "visibility-review" / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    samples = list_closed_loop_samples(local)
    selected = [item for item in samples if item["sample_id"] in {
        "game_1-t60", "game_2-t60", "game_3-t60", "game_4-t30", "game_5-t60"}]
    if len(selected) != 5:
        raise RuntimeError(f"EXPECTED_FIVE_CURRENT_DEV_CLIPS:{len(selected)}")
    for sample in selected:
        cache = closed_loop_root(local) / "decoded-cache" / f"{sample['sample_id']}-{sample['clip_sha256']}"
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
        for page in range(2):
            canvas = Image.new("RGB", (1280, 1970), "#101722")
            draw = ImageDraw.Draw(canvas)
            draw.text((20, 10), f"{sample['sample_id']} · HUMAN VISIBILITY REVIEW · 0.5 s windows · page {page+1}/2", fill="white", font=font)
            for slot in range(10):
                window = page * 10 + slot
                start_seconds = window * 0.5
                end_seconds = min((window + 1) * 0.5, sample["duration_seconds"])
                frame = min(sample["frames"] - 1, int((start_seconds + end_seconds) * 0.5 * sample["sample_fps"] + 0.5))
                path = cache / f"{frame:05d}.jpg"
                if not path.is_file():
                    raise FileNotFoundError(f"DECODED_FRAME_MISSING:{path}")
                image = Image.open(path).convert("RGB")
                image.thumbnail((624, 344), Image.Resampling.LANCZOS)
                column, row = slot % 2, slot // 2
                left, top = 12 + column * 634, 52 + row * 382
                x = left + (624 - image.width) // 2
                y = top + 27 + (344 - image.height) // 2
                draw.text((left + 2, top), f"window {window}: {start_seconds:.1f}–{end_seconds:.1f}s · frame {frame}", fill="#8ed4ff", font=font)
                canvas.paste(image, (x, y))
                image.close()
            target = out / f"{sample['sample_id']}-visibility-{page:02d}.jpg"
            canvas.save(target, quality=91, optimize=True)
            canvas.close()
            print(target)


if __name__ == "__main__":
    main()
