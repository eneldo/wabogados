"""Upload validation for documents and future evidence files.

MASTER_PROMPT forbids trusting the file name or extension, so the MIME type is
detected from the content itself. Detection is signature based to avoid a
system `libmagic` dependency; Fase 7 can swap in `python-magic` if required.
"""

from dataclasses import dataclass
from hashlib import sha256

from app.core.config import get_settings

ALLOWED_MIME_TYPES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/tiff": (b"II*\x00", b"MM\x00*"),
    "application/zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "application/msword": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "text/plain": (),
}

BLOCKED_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "application/x-dosexec": (b"MZ",),
    "application/x-executable": (b"\x7fELF",),
    # Any shebang is treated as a script. Prose markers such as "import " or
    # "from " are deliberately not used: they would reject legitimate text.
    "application/x-script": (b"#!",),
}

EXTENSION_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".zip": "application/zip",
    ".doc": "application/msword",
    ".txt": "text/plain",
}

MAX_UPLOAD_BYTES = get_settings().max_upload_bytes


class UploadValidationError(Exception):
    """Raised when an upload must be rejected."""


@dataclass(frozen=True)
class ValidatedUpload:
    mime_type: str
    size_bytes: int
    sha256: str
    extension: str


def detect_blocked_signature(head: bytes) -> str | None:
    """Return the blocked type when the content looks executable."""
    for blocked, signatures in BLOCKED_SIGNATURES.items():
        if any(head.startswith(signature) for signature in signatures):
            return blocked
    return None


def detect_mime_type(head: bytes) -> str | None:
    """Detect the MIME type from the file content only."""
    for mime, signatures in ALLOWED_MIME_TYPES.items():
        if not signatures:
            continue
        if any(head.startswith(signature) for signature in signatures):
            return mime
    return None


def extension_for(mime_type: str) -> str:
    for extension, mapped in EXTENSION_MIME_MAP.items():
        if mapped == mime_type:
            return extension
    return ".bin"


def is_text_like(head: bytes) -> bool:
    if not head:
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return not any(byte < 9 for byte in head)


def validate_upload(
    content: bytes, original_name: str, declared_mime: str | None = None
) -> ValidatedUpload:
    """Validate size, content and declared type, returning the detected facts.

    The declared MIME type and the extension are only used to detect a
    mismatch; they never decide the stored type.
    """
    if not content:
        raise UploadValidationError("El archivo está vacío")

    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"El archivo supera el máximo de {MAX_UPLOAD_BYTES} bytes"
        )

    head = content[:1024]
    blocked = detect_blocked_signature(head)
    if blocked:
        raise UploadValidationError(f"Tipo de archivo no permitido: {blocked}")

    detected = detect_mime_type(head)
    if detected is None:
        if is_text_like(head):
            detected = "text/plain"
        else:
            raise UploadValidationError("No se pudo determinar el tipo de archivo")

    suffix = _suffix(original_name)
    extension_type = EXTENSION_MIME_MAP.get(suffix)
    if extension_type and extension_type != detected:
        raise UploadValidationError(
            f"La extensión {suffix} no coincide con el contenido ({detected})"
        )

    if declared_mime and declared_mime != detected and declared_mime != "application/octet-stream":
        raise UploadValidationError(
            f"El tipo declarado {declared_mime} no coincide con el contenido ({detected})"
        )

    return ValidatedUpload(
        mime_type=detected,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        extension=extension_for(detected),
    )


def _suffix(name: str) -> str:
    lowered = name.lower()
    for extension in EXTENSION_MIME_MAP:
        if lowered.endswith(extension):
            return extension
    return ""


__all__ = [
    "ALLOWED_MIME_TYPES",
    "BLOCKED_SIGNATURES",
    "EXTENSION_MIME_MAP",
    "MAX_UPLOAD_BYTES",
    "UploadValidationError",
    "ValidatedUpload",
    "detect_blocked_signature",
    "detect_mime_type",
    "validate_upload",
]
