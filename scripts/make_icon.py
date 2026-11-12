"""Generates backend/assets/wrench.ico (provisional icon): a stylised white wrench on a
rounded square in the accent colour of the light theme (--accent in frontend/src/theme).

Usage, from the repository root: uv run --project backend python scripts/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ACCENT = (0, 103, 192, 255)  # #0067c0, --accent of the light theme
WHITE = (255, 255, 255, 255)
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)]
CANVAS = 1024
OUTPUT = Path(__file__).resolve().parents[1] / "backend" / "assets" / "wrench.ico"


def wrench_mask() -> Image.Image:
    """A vertical wrench (head with an open jaw on top), rotated to point up-right."""
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((462, 380, 562, 880), radius=50, fill=255)  # handle
    draw.ellipse((342, 130, 682, 470), fill=255)  # head
    draw.rectangle((447, 80, 577, 300), fill=0)  # jaw
    return mask.rotate(-45, resample=Image.Resampling.BICUBIC, center=(CANVAS // 2, CANVAS // 2))


def build() -> Image.Image:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, CANVAS - 1, CANVAS - 1), radius=220, fill=ACCENT)
    image.paste(WHITE, (0, 0), wrench_mask())
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    base = build().resize((256, 256), Image.Resampling.LANCZOS)
    base.save(OUTPUT, format="ICO", sizes=SIZES)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
