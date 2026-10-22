"""Thumbnail generation for the multimedia library (MASTER_PROMPT V4).

The library keeps its own processor instead of reusing `evidence_processing`
wholesale, because the two pipelines answer different questions: an evidence
derivative must preserve probative value, while a library thumbnail has exactly
one job — letting a listing show what the resource is without reading the
original.

What this deliberately does **not** cover:

- **Video and audio need `ffprobe`/`ffmpeg`, which are not in the image.** An
  MP4 poster cannot be faked with Pillow, so those kinds get no thumbnail yet
  and the route answers with its own 404 rather than a guess.
- **PDF rasterisation** is a listed pending item ("derivaciones PDF
  rasterizadas") and stays out: a text PDF must not be rasterised (section 20)
  and the rasteriser is not here.

The JPEG flavour follows the evidence thumbnail for a reason: `500 px` was
considered and `400` kept, because the listing cell renders at half that and
retina doubles it — the same maths the evidence engine already settled.
"""

import logging
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps

from app.services.evidence_processing import fit_within, to_rgb

logger = logging.getLogger(__name__)

# Same guard as the evidence engine: a decompression bomb is refused by Pillow's
# own check before any decode.
Image.MAX_IMAGE_PIXELS = 150_000_000

#: Posters for grid cells. 400 px on the longest side, JPEG q~72: a few dozen
#: kilobytes at listing scale, which is the whole point of the derivative.
THUMBNAIL_SIDE = 400
THUMBNAIL_QUALITY = 72

#: The only kind this processor can derive from. Listed in one place so callers
#: and the route branch on the fact rather than on their own GIF-of-the-moment
#: interpretation of `MEDIA_MIME_KINDS`.
THUMBNAIL_KINDS: tuple[str, ...] = ("image",)


class MediaThumbnailError(Exception):
    """Raised when a thumbnail cannot be produced from the bytes."""


@dataclass(frozen=True)
class MediaThumbnail:
    """A produced poster, ready to be stored as a `thumbnail` derivative."""

    content: bytes
    mime_type: str = "image/jpeg"
    width: int = 0
    height: int = 0

    @property
    def size_bytes(self) -> int:
        return len(self.content)


def build_media_thumbnail(content: bytes) -> MediaThumbnail:
    """Derive the JPEG poster of an image.

    The decisions worth copying from the evidence engine are all here: EXIF
    rotation is applied **before** resizing so the poster is upright and its
    recorded dimensions are the real ones, the aspect ratio is preserved, a
    morphological upsize never happens, and transparency is flattened onto
    white rather than letting JPEG turn it black. An animated GIF contributes
    its first frame: a poster of a grid cell is not an animation surface.
    """
    try:
        with Image.open(BytesIO(content)) as image:
            upright = ImageOps.exif_transpose(image) or image.copy()
            target = fit_within(
                upright.width, upright.height, THUMBNAIL_SIDE
            )
            resized = (
                upright
                if target == (upright.width, upright.height)
                else upright.resize(target, Image.Resampling.LANCZOS)
            )
            buffer = BytesIO()
            to_rgb(resized).save(
                buffer, format="JPEG", quality=THUMBNAIL_QUALITY
            )
            return MediaThumbnail(
                content=buffer.getvalue(),
                mime_type="image/jpeg",
                width=target[0],
                height=target[1],
            )
    except Exception as error:
        raise MediaThumbnailError(
            f"No se pudo generar la miniatura: {error}"
        ) from error


__all__ = [
    "THUMBNAIL_KINDS",
    "THUMBNAIL_QUALITY",
    "THUMBNAIL_SIDE",
    "MediaThumbnail",
    "MediaThumbnailError",
    "build_media_thumbnail",
]
