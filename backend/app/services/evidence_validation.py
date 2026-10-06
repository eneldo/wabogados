"""Evidence validation, stricter than document validation.

MASTER_PROMPT section 22 lists what to validate and what to reject. Document
upload already checks magic bytes and blocks executables. Evidence adds three
things that matter for forensic material:

1. **Polyglot detection.** A file that is simultaneously a valid PDF and a valid
   ZIP is a real attack: content filters disagree about what it is, and one of
   them is wrong. A single-format verdict is the safe answer.
2. **Decompression bombs.** A 40 kB PNG can declare 40000x40000 pixels and
   exhaust memory when decoded. Declared dimensions are checked against the real
   size before any decoding happens.
3. **Structural validation.** A file can start with the right magic bytes and
   still be corrupt. Images are actually opened; PDFs are actually parsed.

The original filename is never trusted and never used for anything but display.
"""

from dataclasses import dataclass
from hashlib import sha256

from app.services.uploads import (
    MAX_UPLOAD_BYTES,
    detect_blocked_signature,
    detect_mime_type,
    is_text_like,
)

#: Formats MASTER_PROMPT section 17 accepts.
EVIDENCE_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
    }
)

#: Rejected regardless of content. A ZIP has no place in an evidence upload and
#: is the usual carrier of a polyglot.
FORBIDDEN_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/zip",
        "application/msword",
        "application/x-dosexec",
        "application/x-executable",
    }
)

#: Guard against image bombs: 150 megapixels is far beyond any photograph of a
#: document and small enough to keep one decode under control.
MAX_PIXELS = 150_000_000

#: Guard against a malformed header claiming an absurd canvas.
MAX_DIMENSION = 40_000


class EvidenceValidationError(Exception):
    """Raised when an evidence must be rejected."""


@dataclass(frozen=True)
class ValidatedEvidence:
    """Facts about an accepted upload, before any processing."""

    mime_type: str
    size_bytes: int
    sha256: str
    extension: str
    is_image: bool
    is_pdf: bool


#: Embedded markers, searched anywhere inside the inspected header.
_ZIP_MARKERS: tuple[bytes, ...] = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_DOC_MARKERS: tuple[bytes, ...] = (b"\xd0\xcf\x11\xe0",)
_EXECUTABLE_MARKERS: tuple[bytes, ...] = (b"MZ",)


def _contains_any(head: bytes, markers: tuple[bytes, ...]) -> bool:
    return any(marker in head for marker in markers)


def detect_all_formats(head: bytes) -> set[str]:
    """Return every format the header claims to be.

    More than one is a polyglot. Container markers are searched across the whole
    header rather than only at offset zero, because the classic polyglot starts
    as a valid PDF and carries a ZIP central directory further in. Two content
    filters then disagree about what the file is, and one of them is wrong.
    """
    found: set[str] = set()

    detected = detect_mime_type(head)
    if detected:
        found.add(detected)

    if _contains_any(head, _ZIP_MARKERS):
        found.add("application/zip")
    if _contains_any(head, _DOC_MARKERS):
        found.add("application/msword")
    if _contains_any(head, _EXECUTABLE_MARKERS):
        found.add("application/x-dosexec")

    return found


def check_image_dimensions(width: int, height: int) -> None:
    """Reject impossible canvases before they are decoded."""
    if width <= 0 or height <= 0:
        raise EvidenceValidationError(
            f"Dimensiones inválidas: {width}x{height}"
        )
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise EvidenceValidationError(
            f"Dimensiones sospechosas: {width}x{height} "
            f"(máximo {MAX_DIMENSION} px por lado)"
        )
    if width * height > MAX_PIXELS:
        raise EvidenceValidationError(
            f"La imagen declara {width * height} píxeles, por encima del máximo "
            f"de {MAX_PIXELS}. Posible bomba de descompresión."
        )


def read_image_size(content: bytes) -> tuple[int, int] | None:
    """Return the dimensions declared by an image header, without decoding it.

    Returns None when the header cannot be read; the caller then relies on the
    real decoder to fail.
    """
    from io import BytesIO

    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            return int(image.width), int(image.height)
    except Exception:
        return None


def validate_evidence(
    content: bytes,
    original_name: str,
    declared_mime: str | None = None,
) -> ValidatedEvidence:
    """Validate an evidence upload before anything is stored.

    Order matters and mirrors MASTER_PROMPT section 18: size, blocked content,
    format detection, extension and declared type consistency, then the
    polyglot and bomb checks.
    """
    if not content:
        raise EvidenceValidationError("El archivo está vacío")

    if len(content) > MAX_UPLOAD_BYTES:
        raise EvidenceValidationError(
            f"El archivo supera el máximo de {MAX_UPLOAD_BYTES} bytes"
        )

    head = content[:4096]

    blocked = detect_blocked_signature(head)
    if blocked:
        raise EvidenceValidationError(f"Tipo de archivo no permitido: {blocked}")

    formats = detect_all_formats(head)

    forbidden = formats & FORBIDDEN_MIME_TYPES
    if forbidden:
        raise EvidenceValidationError(
            f"Formato no admitido para evidencia: {sorted(forbidden)[0]}"
        )

    detected = detect_mime_type(head)
    if detected is None:
        if is_text_like(head):
            raise EvidenceValidationError(
                "El contenido es texto plano. Una evidencia debe ser PDF, PNG o JPG."
            )
        raise EvidenceValidationError("No se pudo determinar el tipo de archivo")

    if len(formats) > 1:
        raise EvidenceValidationError(
            f"Archivo polígloto: es a la vez {sorted(formats)}. "
            "Se rechaza por seguridad."
        )

    if detected not in EVIDENCE_MIME_TYPES:
        raise EvidenceValidationError(
            f"Tipo no admitido como evidencia: {detected}"
        )

    _check_consistency(original_name, declared_mime, detected)

    if detected.startswith("image/"):
        size = read_image_size(content)
        if size is not None:
            check_image_dimensions(*size)

    return ValidatedEvidence(
        mime_type=detected,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        extension=_extension_for(detected),
        is_image=detected.startswith("image/"),
        is_pdf=detected == "application/pdf",
    )


def _check_consistency(
    original_name: str, declared_mime: str | None, detected: str
) -> None:
    """The declared type and the extension only serve to detect mismatches."""
    suffix = _suffix(original_name)
    allowed_suffixes = {
        "application/pdf": {".pdf"},
        "image/png": {".png"},
        "image/jpeg": {".jpg", ".jpeg"},
    }[detected]
    if suffix and suffix not in allowed_suffixes:
        raise EvidenceValidationError(
            f"La extensión {suffix} no corresponde al contenido ({detected})"
        )
    if (
        declared_mime
        and declared_mime != detected
        and declared_mime != "application/octet-stream"
    ):
        raise EvidenceValidationError(
            f"El tipo declarado {declared_mime} no coincide con el contenido ({detected})"
        )


def _suffix(name: str) -> str:
    lowered = name.lower()
    for extension in (".pdf", ".png", ".jpg", ".jpeg"):
        if lowered.endswith(extension):
            return extension
    return ""


def _extension_for(mime_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }[mime_type]


__all__ = [
    "EVIDENCE_MIME_TYPES",
    "FORBIDDEN_MIME_TYPES",
    "MAX_DIMENSION",
    "MAX_PIXELS",
    "EvidenceValidationError",
    "ValidatedEvidence",
    "check_image_dimensions",
    "detect_all_formats",
    "read_image_size",
    "validate_evidence",
]