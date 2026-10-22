"""Schemas for the multimedia library (MASTER_PROMPT V4).

The `kind` of a resource is **not** accepted from the client. A browser is free to
send whatever it likes, and `kind` decides whether the browser will be offered a
`<video>` player; deriving it on the server from the detected MIME type means the
decision follows the bytes and cannot be talked into disagreeing with them.
"""

from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import StorageTier
from app.models import MediaItem

MediaKind = Literal["video", "image", "audio", "document"]
MediaStatus = Literal["activo", "archivado"]
MediaConfidentiality = Literal["interno", "restringido", "confidencial"]


class MediaCreate(BaseModel):
    """Register the row first; the bytes are uploaded afterwards.

    Split in two on purpose: a librarian may register a recording that has not
    arrived yet, and a single POST carrying both would have to invent what to do
    with the row when the upload fails halfway.
    """

    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    confidentiality: MediaConfidentiality = "interno"
    tags: str | None = Field(default=None, max_length=1000)
    case_id: UUID | None = None
    #: Display only. The storage key never contains it.
    original_filename: str | None = Field(default=None, max_length=255)


class MediaUpdate(BaseModel):
    """Editable fields of a resource.

    **`duration_seconds` is not accepted here, on purpose.** The column comment on
    `MediaItem.duration_seconds` says it stays null until something measures the
    file, and no measurement exists: the browser cannot report the duration of a
    video the server has not decoded, so accepting the field would let a client
    write a guess into a column documented as a measurement. When ffprobe arrives,
    the value comes back through the processing pipeline — not through PATCH.
    """

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    confidentiality: MediaConfidentiality | None = None
    status: MediaStatus | None = None
    tags: str | None = Field(default=None, max_length=1000)
    case_id: UUID | None = None


class MediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    kind: MediaKind
    status: MediaStatus
    confidentiality: MediaConfidentiality
    tags: str | None
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    tier: str = StorageTier.HOT.value
    duration_seconds: int | None
    case_id: UUID | None
    case_number: str | None = None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    deleted_at: datetime | None
    #: Whether a file is actually attached. A registered row with nothing in it is
    #: a normal state, and a screen that cannot tell them apart is lying.
    has_file: bool


class PaginatedMedia(BaseModel):
    items: list[MediaResponse]
    total: int
    skip: int
    limit: int


def media_response(item: MediaItem, *, case_number: str | None = None) -> MediaResponse:
    return MediaResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        kind=cast(MediaKind, item.kind),
        status=cast(MediaStatus, item.status),
        confidentiality=cast(MediaConfidentiality, item.confidentiality),
        tags=item.tags,
        original_filename=item.original_filename,
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
        sha256=item.sha256,
        tier=item.storage_tier,
        duration_seconds=item.duration_seconds,
        case_id=item.case_id,
        case_number=case_number,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        is_active=item.is_active,
        deleted_at=item.deleted_at,
        has_file=item.has_file,
    )


__all__ = [
    "MediaConfidentiality",
    "MediaCreate",
    "MediaKind",
    "MediaResponse",
    "MediaStatus",
    "MediaUpdate",
    "PaginatedMedia",
    "media_response",
]
