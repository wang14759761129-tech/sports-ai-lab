"""Convert the user-selected Cinema image; never generate a replacement design.

Run with a Pillow-enabled asset-tool Python. Pillow is not an app runtime dependency.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    from PIL import Image

    source = ROOT / "assets" / "ptti-cinema.png"
    destination = ROOT / "assets" / "ptti.ico"
    with Image.open(source) as image:
        image.load()
        width, height = image.size
        side = max(width, height)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 255))
        canvas.alpha_composite(image.convert("RGBA"), ((side - width) // 2, (side - height) // 2))
        temporary = destination.with_suffix(".ico.tmp")
        try:
            canvas.save(temporary, format="ICO", sizes=SIZES)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    public = ROOT / "frontend" / "public"
    public.mkdir(exist_ok=True)
    temporary = public / "ptti.ico.tmp"
    try:
        shutil.copyfile(destination, temporary)
        temporary.replace(public / "ptti.ico")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
