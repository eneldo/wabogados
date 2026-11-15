"""Create the public justice artwork without modifying the supplied original.

Run with Pillow installed. Lossless WebP preserves the full artwork and alpha;
no cropping, recolouring or resizing is performed.
"""

from pathlib import Path

from PIL import Image


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "Logo de Justicia.png"
    target = root / "frontend/public/marca/logo-justicia.webp"
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        original.convert("RGBA").save(target, lossless=True, method=6, exact=True)
        print(f"Justice artwork: {original.width}×{original.height}; original preserved")
    print(f"Original: {source.stat().st_size} bytes; WebP: {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
