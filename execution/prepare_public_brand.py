"""Prepare the supplied logo for the public header without changing its artwork.

Run from any directory with Pillow installed. The original remains untouched;
only the white outer margins are trimmed, keeping an 8px safety margin.
"""

from pathlib import Path
from shutil import copyfile

from PIL import Image, ImageChops


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "logo_Wabogados.jpg"
    public = root / "frontend/public"
    target = public / "marca"
    target.mkdir(parents=True, exist_ok=True)
    copyfile(source, public / source.name)
    with Image.open(source) as original:
        image = original.convert("RGB")
        difference = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
        mask = difference.convert("L").point(lambda value: 255 if value > 65 else 0)
        bounds = mask.getbbox()
        if bounds is None:
            raise ValueError("The logo has no visible artwork")
        left, top, right, bottom = bounds
        bounds = (max(0, left - 8), max(0, top - 8),
                  min(image.width, right + 8), min(image.height, bottom + 8))
        cropped = image.crop(bounds)
        cropped.save(target / "wabogados-logo.webp", quality=95, method=6)
        icon = Image.new("RGB", (256, 256), "white")
        mark = cropped.copy()
        mark.thumbnail((240, 240), Image.Resampling.LANCZOS)
        icon.paste(mark, ((256 - mark.width) // 2, (256 - mark.height) // 2))
        icon.resize((64, 64), Image.Resampling.LANCZOS).save(root / "frontend/app/icon.png")
        print(f"Logo: {cropped.width}×{cropped.height}; original preserved")


if __name__ == "__main__":
    main()
