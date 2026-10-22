"""Image and PDF processing for the evidence engine.

Two rules dominate every decision in this module:

1. **The original is never touched.** Derivatives are produced from the bytes
   received and stored under their own keys. Nothing here writes back to the
   original's storage key.
2. **A derivative never legally substitutes the original.** Every derivative is
   recorded with its own digest, and the signed PDF case is treated specially: a
   signed PDF is copied, never re-encoded.

MASTER_PROMPT section 21 is explicit about the objective: not the smallest file,
but the smallest file that keeps probative value and legibility. That is why the
profiles differ by purpose rather than by a single quality slider.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from io import BytesIO

from PIL import Image, ImageOps
from PIL.ExifTags import TAGS as EXIF_TAGS

logger = logging.getLogger(__name__)

# Pillow's own guard against decompression bombs. Kept in sync with
# `MAX_PIXELS` in evidence_validation; the check there runs before decoding.
Image.MAX_IMAGE_PIXELS = 150_000_000


class ProcessingError(Exception):
    """Raised when an evidence cannot be processed."""


class DerivativeType(StrEnum):
    OPTIMIZED = "optimized"
    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"


class Profile(StrEnum):
    """MASTER_PROMPT section 21 profiles."""

    LOSSLESS = "lossless"
    LEGAL_STANDARD = "legal_standard"
    WEB_PREVIEW = "web_preview"


@dataclass(frozen=True)
class ImageProfile:
    """A named output profile. Targets are per the profile definitions."""

    name: Profile
    max_side: int
    quality: int
    strip_metadata: bool


#: Photographed documents: legible text matters more than pixel count.
DOCUMENT_PROFILE = ImageProfile(Profile.LEGAL_STANDARD, 2200, 85, strip_metadata=True)

#: Scenes, damage, vehicles: more detail, smaller derivative.
PHOTO_PROFILE = ImageProfile(Profile.LEGAL_STANDARD, 2560, 86, strip_metadata=True)

#: Fast navigation only. Explicitly not for legal reading.
WEB_PREVIEW = ImageProfile(Profile.WEB_PREVIEW, 1200, 72, strip_metadata=True)

LOSSLESS_PROFILE = ImageProfile(Profile.LOSSLESS, 0, 100, strip_metadata=False)

THUMBNAIL_SIDE = 400


@dataclass
class Derivative:
    """A produced derivative, ready to be stored."""

    derivative_type: DerivativeType
    content: bytes
    mime_type: str
    width: int | None = None
    height: int | None = None
    page_count: int | None = None
    profile: Profile | None = None
    source_size: int = 0
    detail: str | None = None

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def compression_ratio(self) -> float:
        """Percentage of the original removed.

        A **percentage**, not a fraction, even though the column is a plain
        float. The custody trail prints it as `reducción {ratio}%`, so the unit
        has to match or the record says something the arithmetic does not.

        The value goes negative when the derivative weighs more than its
        source, which happens for an already-optimised image: that is a real
        measurement and callers must not clamp it to zero and call it a saving.
        """
        if self.source_size <= 0:
            return 0.0
        return round((1 - (len(self.content) / self.source_size)) * 100, 2)


@dataclass
class ImageAnalysis:
    """Metadata read from an image, kept for the custody record."""

    width: int
    height: int
    mode: str
    format_name: str
    has_alpha: bool
    exif_present: bool
    orientation: int | None = None
    exif_summary: dict[str, str] = field(default_factory=dict)


@dataclass
class PdfAnalysis:
    """Metadata read from a PDF, kept for the custody record."""

    page_count: int
    pdf_version: str
    is_encrypted: bool
    is_signed: bool
    signature_covers_whole_file: bool
    has_text: bool
    title: str | None = None
    author: str | None = None
    producer: str | None = None

    @property
    def signature_broken(self) -> bool:
        """A signature that no longer covers the file was invalidated by editing."""
        return self.is_signed and not self.signature_covers_whole_file


# --- Images ---------------------------------------------------------------


def analyse_image(content: bytes) -> ImageAnalysis:
    """Read image metadata without changing anything."""
    try:
        with Image.open(BytesIO(content)) as image:
            exif = _read_exif(image)
            orientation = exif.get("Orientation") if exif else None
            return ImageAnalysis(
                width=image.width,
                height=image.height,
                mode=image.mode,
                format_name=(image.format or "").upper(),
                has_alpha=image.mode in ("RGBA", "LA", "PA"),
                exif_present=bool(exif),
                orientation=_as_int(orientation),
                exif_summary={
                    key: str(value)
                    for key, value in (exif or {}).items()
                    if key in ("Make", "Model", "DateTime", "GPSInfo")
                },
            )
    except Exception as error:
        raise ProcessingError(f"No se pudo leer la imagen: {error}") from error


def _read_exif(image: Image.Image) -> dict[str, object] | None:
    try:
        raw = image.getexif()
    except Exception:
        return None
    if not raw:
        return None
    return {
        EXIF_TAGS.get(tag, str(tag)): value
        for tag, value in raw.items()
        if isinstance(value, str | int | float)
    }


def _as_int(value: object) -> int | None:
    """Best effort integer coercion for EXIF values of unknown type."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fit_within(width: int, height: int, max_side: int) -> tuple[int, int]:
    """Scale preserving the aspect ratio. Never enlarges, never distorts."""
    if max_side <= 0:
        return width, height
    longest = max(width, height)
    if longest <= max_side:
        return width, height
    factor = max_side / longest
    return max(1, round(width * factor)), max(1, round(height * factor))


def process_image(
    content: bytes,
    analysis: ImageAnalysis,
    *,
    source_size: int | None = None,
) -> list[Derivative]:
    """Produce the consultation derivative and the thumbnail.

    The rules from MASTER_PROMPT section 19 are enforced here: aspect ratio is
    preserved, EXIF rotation is applied before resizing, and metadata is only
    stripped on the copies.
    """
    derivatives: list[Derivative] = []
    original_size = source_size if source_size is not None else len(content)

    try:
        with Image.open(BytesIO(content)) as image:
            # Auto-rotate from EXIF before anything else, so the derivative is
            # upright and the recorded dimensions are the real ones.
            upright = ImageOps.exif_transpose(image) or image.copy()

            profile = _profile_for(analysis)
            derivative, target, size = _render(upright, profile, analysis.has_alpha)

            thumbnail, _thumb_target, thumb_size = _render(
                upright,
                ImageProfile(
                    Profile.WEB_PREVIEW, THUMBNAIL_SIDE, 72, strip_metadata=True
                ),
                analysis.has_alpha,
                force_format="JPEG",
            )

            derivatives.append(
                Derivative(
                    derivative_type=DerivativeType.OPTIMIZED,
                    content=derivative,
                    mime_type=_mime_for_format(target),
                    width=size[0],
                    height=size[1],
                    profile=profile.name,
                    source_size=original_size,
                    detail=f"máximo {profile.max_side} px, calidad {profile.quality}",
                )
            )
            derivatives.append(
                Derivative(
                    derivative_type=DerivativeType.THUMBNAIL,
                    content=thumbnail,
                    mime_type="image/jpeg",
                    width=thumb_size[0],
                    height=thumb_size[1],
                    profile=Profile.WEB_PREVIEW,
                    source_size=original_size,
                    detail="miniatura para listados",
                )
            )
    except ProcessingError:
        raise
    except Exception as error:
        raise ProcessingError(f"No se pudo procesar la imagen: {error}") from error

    return derivatives


def _profile_for(analysis: ImageAnalysis) -> ImageProfile:
    # A photographed document is a text heavy image: keep more pixels so the
    # text stays readable. A photo needs less.
    megapixels = (analysis.width * analysis.height) / 1_000_000
    if megapixels >= 3 or analysis.format_name == "PNG":
        return DOCUMENT_PROFILE
    return PHOTO_PROFILE


def _render(
    image: Image.Image,
    profile: ImageProfile,
    has_alpha: bool,
    *,
    force_format: str | None = None,
) -> tuple[bytes, str, tuple[int, int]]:
    """Encode one derivative.

    Returns the bytes, the chosen format and the final dimensions, so the caller
    records exactly what was produced instead of recomputing the fit.
    """
    target_size = fit_within(image.width, image.height, profile.max_side)
    resized = image
    if target_size != (image.width, image.height):
        resized = image.resize(target_size, Image.Resampling.LANCZOS)

    keep_alpha = has_alpha and profile is DOCUMENT_PROFILE and force_format is None
    if keep_alpha:
        buffer = BytesIO()
        resized.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "PNG", target_size

    converted = to_rgb(resized)
    buffer = BytesIO()
    converted.save(buffer, format=force_format or "WEBP", quality=profile.quality, method=4)
    return buffer.getvalue(), force_format or "WEBP", target_size


def _mime_for_format(target: str) -> str:
    """Map the encoder format to the MIME type actually produced."""
    return {
        "WEBP": "image/webp",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }.get(target, "application/octet-stream")


def to_rgb(image: Image.Image) -> Image.Image:
    """Convert to a mode JPEG accepts, flattening transparency onto white.

    Shared with the multimedia library's thumbnails: a JPEG cannot carry an
    alpha channel, and pasting onto white is the same decision both modules
    want — a transparent PNG on a listing must not turn black.
    """
    if image.mode in ("RGB",):
        return image
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        converted = image.convert("RGBA")
        background.paste(converted, mask=converted.split()[-1])
        return background
    return image.convert("RGB")


# --- PDF ------------------------------------------------------------------


def analyse_pdf(content: bytes) -> PdfAnalysis:
    """Inspect a PDF and, crucially, determine whether it carries a signature.

    A signed PDF is legally meaningful material. Two facts matter and are both
    reported: that a signature exists, and whether its ByteRange still covers the
    whole file. A signature that does not means the document was modified after
    it was signed, which a lawyer absolutely needs to know.
    """
    import pikepdf

    try:
        with pikepdf.open(BytesIO(content)) as pdf:
            is_signed = _has_signature_field(pdf) or _has_sig_flags(pdf)
            covers = _signature_covers_file(pdf, content)
            has_text = _looks_like_text(pdf)
            metadata: dict[str, object] = dict(pdf.docinfo or {})
            return PdfAnalysis(
                page_count=len(pdf.pages),
                pdf_version=str(pdf.pdf_version),
                is_encrypted=bool(pdf.is_encrypted),
                is_signed=is_signed,
                signature_covers_whole_file=covers,
                has_text=has_text,
                title=_clean_text(metadata.get("/Title")),
                author=_clean_text(metadata.get("/Author")),
                producer=_clean_text(metadata.get("/Producer")),
            )
    except ProcessingError:
        raise
    except Exception as error:
        raise ProcessingError(f"No se pudo leer el PDF: {error}") from error


def _has_sig_flags(pdf: object) -> bool:
    """`/SigFlags` bit 1 means the form contains signatures.

    Reading it through a helper keeps the pikepdf dynamic object out of the
    type checker's way.
    """
    try:
        acroform = pdf.Root.get("/AcroForm")  # type: ignore[attr-defined]
        if acroform is None:
            return False
        return bool(int(acroform.get("/SigFlags", 0)) & 1)
    except (TypeError, ValueError):
        return False
    except Exception:
        return False


def _has_signature_field(pdf: object) -> bool:
    try:
        acroform = pdf.Root.get("/AcroForm")  # type: ignore[attr-defined]
    except Exception:
        return False
    if acroform is None:
        return False
    try:
        return any(
            field.get("/FT") == "/Sig" for field in acroform.get("/Fields", [])
        )
    except Exception:
        return False


def _signature_covers_file(pdf: object, content: bytes) -> bool:
    """True when at least one signature spans the entire document.

    ByteRange is a list of byte offsets the signature covers. If the last offset
    plus its length equals the file size, the signature is intact.
    """
    total = len(content)
    try:
        acroform = pdf.Root.get("/AcroForm")  # type: ignore[attr-defined]
        fields = acroform.get("/Fields", []) if acroform is not None else []
    except Exception:
        return False

    for signature_field in fields:
        try:
            value = signature_field.get("/V")
            if value is None:
                continue
            byte_range = value.get("/ByteRange")
            if not byte_range:
                continue
            offsets = [int(item) for item in byte_range]
            if len(offsets) < 4:
                continue
            # Total signed length is the sum of both ranges.
            length = (offsets[1] - offsets[0]) + (offsets[3] - offsets[2])
            if length >= total:
                return True
        except Exception:
            continue
    return False


def _looks_like_text(pdf: object) -> bool:
    """A textual PDF must not be rasterised (MASTER_PROMPT section 20)."""
    try:
        for page in pdf.pages[:3]:  # type: ignore[attr-defined]
            resources = page.get("/Resources", {})
            fonts = resources.get("/Font", {}) if resources is not None else {}
            if len(fonts) > 0:
                return True
    except Exception:
        return False
    return False


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:255] or None


def optimise_pdf(content: bytes, analysis: PdfAnalysis) -> Derivative:
    """Produce a consultation copy of a PDF.

    A **signed** PDF is copied byte for byte. Re-encoding a signed document
    destroys the signature, and a broken signature on evidence is worse than a
    larger file. This is MASTER_PROMPT rule 15.
    """
    import pikepdf

    if analysis.is_signed:
        return Derivative(
            derivative_type=DerivativeType.OPTIMIZED,
            content=content,
            mime_type="application/pdf",
            page_count=analysis.page_count,
            profile=Profile.LOSSLESS,
            source_size=len(content),
            detail=(
                "PDF firmado: se conserva íntegro sin reoptimizar para no "
                "invalidar la firma"
            ),
        )

    try:
        with pikepdf.open(BytesIO(content)) as pdf:
            buffer = BytesIO()
            # Linearize and recompress object streams: lossless structural work
            # that keeps text selectable and bookmarks intact.
            pdf.save(
                buffer,
                linearize=True,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
            optimised = buffer.getvalue()
    except Exception as error:
        raise ProcessingError(f"No se pudo optimizar el PDF: {error}") from error

    # Never hand back something larger than what we received.
    if len(optimised) >= len(content):
        optimised = content

    return Derivative(
        derivative_type=DerivativeType.OPTIMIZED,
        content=optimised,
        mime_type="application/pdf",
        page_count=analysis.page_count,
        profile=Profile.LOSSLESS,
        source_size=len(content),
        detail="optimización estructural sin pérdida",
    )


__all__ = [
    "DOCUMENT_PROFILE",
    "LOSSLESS_PROFILE",
    "PHOTO_PROFILE",
    "WEB_PREVIEW",
    "Derivative",
    "DerivativeType",
    "ImageAnalysis",
    "ImageProfile",
    "PdfAnalysis",
    "ProcessingError",
    "Profile",
    "analyse_image",
    "analyse_pdf",
    "fit_within",
    "optimise_pdf",
    "process_image",
    "to_rgb",
]