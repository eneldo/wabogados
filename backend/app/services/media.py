"""The multimedia library (MASTER_PROMPT V4, "Videos y biblioteca").

A collection of the firm's own material: an inspection recording, a photograph of a
site, an audio note, a signed PDF kept for reuse.

**It is not the evidence engine.** Evidence is a legal record with an immutable
original, a custody chain and a retention policy (section 28). Here a file is
replaced in place when it is corrected, there are no derivatives and no custody
trail. Keeping the two apart is what allowed this module to accept video without
reopening `EVIDENCE_MIME_TYPES`, whose narrower list is a contract about legal
records and was not this module's to change.

Two rules carry most of the weight:

- **The kind follows the bytes.** `kind` decides whether the browser is offered a
  `<video>` player, so a client that sent `"kind": "image"` for an MP4 would be
  believed about its own content. The MIME type is detected from the header here
  and the kind is derived from that.
- **Nothing is deleted.** `DELETE /media/{id}` deactivates (ADR-051): the row, its
  history and its digest survive, and only the actor, the moment and the reason
  are added. The file itself is left in storage, because a deactivated row that
  lost its bytes could not be reactivated.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import StorageTier
from app.models import MediaAccessLog, MediaItem, User
from app.schemas.media import MediaCreate, MediaUpdate
from app.services.history import record_changes
from app.services.storage import (
    StorageBackend,
    StorageError,
    build_media_key,
    build_storage,
)

logger = logging.getLogger(__name__)

MEDIA_ENTITY = "media_items"

#: Fields whose change is recorded in `change_logs`. The digest and the size are
#: included on purpose: "the file changed" is the entry anybody asks for first when
#: a recording is questioned months later.
TRACKED_MEDIA_FIELDS = (
    "title",
    "description",
    "status",
    "confidentiality",
    "tags",
    "mime_type",
    "sha256",
    "size_bytes",
    "case_id",
    "is_active",
)

#: What the library accepts, by detected type. Video is here on purpose; it is
#: absent from `EVIDENCE_MIME_TYPES` because an evidence is a legal record with a
#: narrower contract, not because video is a dangerous file.
MEDIA_MIME_KINDS: dict[str, str] = {
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/mp4": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/pdf": "document",
}

#: Header signatures, checked against the first bytes of the upload. A container
#: format is recognised by its magic number rather than by a file extension: an
#: uploaded name is attacker-controlled text, and an MP4 renamed to `.jpg` is
#: still an MP4.
MEDIA_SIGNATURES: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("video/mp4", (b"ftyp",)),
    ("video/quicktime", (b"moov", b"mdat", b"wide", b"free")),
    ("video/webm", (b"\x1a\x45\xdf\xa3",)),
    ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ("image/jpeg", (b"\xff\xd8\xff",)),
    ("image/gif", (b"GIF87a", b"GIF89a")),
    ("application/pdf", (b"%PDF-",)),
    ("audio/mpeg", (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")),
    ("audio/wav", (b"RIFF",)),
    ("audio/ogg", (b"OggS",)),
)

#: Extension written into the storage key, per detected type. It lives here and
#: not in `uploads.EXTENSION_MIME_MAP` because that map answers a different
#: question — it is the reverse index of what the document uploader accepts — and
#: it holds no video at all. Falling back to `.bin` for an MP4 would store a film
#: in a file the browser cannot identify.
MEDIA_EXTENSIONS: dict[str, str] = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}

#: How much of the file is needed to recognise it. Enough for every signature
#: above, including the RIFF family where the type sits at offset 8.
HEADER_BYTES = 32


class MediaError(Exception):
    """Raised when a request about the library cannot be honoured."""


class MediaValidationError(MediaError):
    """Raised when the uploaded bytes are not something the library accepts."""


def detect_media_type(head: bytes) -> str | None:
    """Return the detected MIME type of the library, or None when unknown.

    RIFF is a container: `RIFF....WAVE` is audio and `RIFF....WEBP` is an image, so
    the four bytes at offset 8 decide. Getting this wrong would let a `.webp`
    announce itself as audio, which is why the container is resolved rather than
    assumed.
    """
    if head.startswith(b"RIFF") and len(head) >= 12:
        form = head[8:12]
        if form == b"WAVE":
            return "audio/wav"
        if form == b"WEBP":
            return "image/webp"
        if form == b"AVI ":
            return "video/x-msvideo"
        return None

    # ISO base media files start with a box size; the brand follows at offset 4.
    if len(head) >= 8 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return "video/mp4"

    for mime, signatures in MEDIA_SIGNATURES:
        if any(head.startswith(signature) for signature in signatures):
            return mime
    return None


def kind_for(mime_type: str) -> str:
    try:
        return MEDIA_MIME_KINDS[mime_type]
    except KeyError as error:
        raise MediaValidationError(
            f"Tipo no admitido en la biblioteca: {mime_type}"
        ) from error


class MediaService:
    def __init__(
        self, session: AsyncSession, storage: StorageBackend | None = None
    ) -> None:
        self.session = session
        #: Injected by the tests so an endpoint cannot write to the real
        #: configured root. Same shape as `DocumentService`.
        self.storage = storage

    def _backend(self) -> StorageBackend:
        return self.storage or build_storage()

    async def list_media(
        self,
        skip: int = 0,
        limit: int = 25,
        *,
        scope_clause: ColumnElement[bool] | None,
        search: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        confidentiality: str | None = None,
        case_id: UUID | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[MediaItem], int]:
        # No join: every filter and the ordering read `media_items` columns, and the
        # case number arrives with the row through `MediaItem.case`, which is
        # `lazy="selectin"`. Joining `cases` here would be a join nothing selects
        # from.
        statement = select(MediaItem).order_by(MediaItem.created_at.desc())
        conditions: list[Any] = []
        if scope_clause is not None:
            conditions.append(scope_clause)
        if not include_inactive:
            conditions.append(MediaItem.is_active.is_(True))
        if kind:
            conditions.append(MediaItem.kind == kind)
        if status:
            conditions.append(MediaItem.status == status)
        if confidentiality:
            conditions.append(MediaItem.confidentiality == confidentiality)
        if case_id:
            conditions.append(MediaItem.case_id == case_id)
        if search:
            # Title, description and tags. The tags are free text with commas, so
            # they are searched as written; a library that could not be searched by
            # its own labels would not be used.
            needle = f"%{search.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(MediaItem.title).like(needle),
                    func.lower(func.coalesce(MediaItem.description, "")).like(needle),
                    func.lower(func.coalesce(MediaItem.tags, "")).like(needle),
                )
            )
        if conditions:
            statement = statement.where(*conditions)

        total = await self.session.scalar(
            select(func.count())
            .select_from(MediaItem)
            .where(*conditions)
        )

        result = await self.session.execute(statement.offset(skip).limit(limit))
        return list(result.scalars().all()), int(total or 0)

    async def case_number_for(self, item: MediaItem) -> str | None:
        if item.case is None:
            return None
        return item.case.case_number

    async def get(
        self, media_id: UUID, *, scope_clause: ColumnElement[bool] | None
    ) -> MediaItem | None:
        """Fetch one resource inside the caller's scope.

        `scope_clause` has no default, for the same reason as the billing service: a
        permissive default is indistinguishable from a correct one until the test
        where a lawyer opens another expediente's file.

        A resource with `case_id IS NULL` is firm material and stays visible to any
        holder of `media:read`; `case_scoped` returns NULL for those rows, so the
        router ORs it back in. See `_clause` there.
        """
        statement = select(MediaItem).where(MediaItem.id == media_id)
        if scope_clause is not None:
            statement = statement.where(scope_clause)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create(self, payload: MediaCreate, actor: User) -> MediaItem:
        item = MediaItem(
            title=payload.title,
            description=payload.description,
            confidentiality=payload.confidentiality,
            tags=payload.tags,
            case_id=payload.case_id,
            original_filename=payload.original_filename,
            created_by=actor.id,
            # Registered before a byte arrives. The row exists so the librarian can
            # file a recording that has not been uploaded yet; `has_file` is what
            # tells the two states apart in the screen.
            kind="document",
        )
        self.session.add(item)
        await self.session.flush()
        record_changes(
            self.session,
            entity=MEDIA_ENTITY,
            entity_id=item.id,
            before={},
            after={
                "title": item.title,
                "description": item.description,
                "confidentiality": item.confidentiality,
                "tags": item.tags,
                "case_id": item.case_id,
            },
            changed_by=actor.id,
            fields=TRACKED_MEDIA_FIELDS,
            reason="Recurso registrado",
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update(
        self, item: MediaItem, payload: MediaUpdate, actor: User
    ) -> MediaItem:
        data = payload.model_dump(exclude_unset=True)
        before = {field: getattr(item, field, None) for field in TRACKED_MEDIA_FIELDS}
        for field, value in data.items():
            setattr(item, field, value)
        record_changes(
            self.session,
            entity=MEDIA_ENTITY,
            entity_id=item.id,
            before=before,
            after=data,
            changed_by=actor.id,
            fields=TRACKED_MEDIA_FIELDS,
            reason="Recurso editado",
        )
        await self.session.flush()
        # `updated_at` carries `onupdate=func.now()`, a server-side expression the
        # ORM cannot evaluate; without this refresh the response would try to read
        # the expired attribute from a plain function and answer 500.
        await self.session.refresh(item)
        return item

    async def attach_file(
        self, item: MediaItem, content: bytes, filename: str | None
    ) -> MediaItem:
        """Store the bytes and record what was actually persisted.

        The digest returned by the backend is the one kept, not one computed here:
        it describes the object that exists, which is the only digest that can later
        prove the file was not altered (ADR-041).
        """
        detected = detect_media_type(content[:HEADER_BYTES])
        if detected is None:
            raise MediaValidationError(
                "No se reconoce el tipo del archivo por su contenido. "
                "La biblioteca admite vídeo, imagen, audio y PDF."
            )
        if detected not in MEDIA_MIME_KINDS:
            raise MediaValidationError(f"Tipo no admitido en la biblioteca: {detected}")

        if item.storage_key is not None:
            # Replacing a file keeps one object per record, so the previous one is
            # removed — the one case where `delete` is right, because the row keeps
            # the history and only the superseded bytes go.
            await self._drop_previous(item)

        storage = self._backend()
        key = build_media_key(item.id, MEDIA_EXTENSIONS.get(detected, ".bin"))
        try:
            stored = await storage.write(key, content, tier=StorageTier.HOT)
        except StorageError as error:
            raise MediaError(f"No se pudo guardar el archivo: {error}") from error

        before = {field: getattr(item, field, None) for field in TRACKED_MEDIA_FIELDS}
        item.storage_key = stored.key
        item.sha256 = stored.sha256
        item.size_bytes = stored.size_bytes
        item.mime_type = detected
        item.kind = kind_for(detected)
        item.storage_tier = stored.tier.value
        if filename:
            item.original_filename = filename
        record_changes(
            self.session,
            entity=MEDIA_ENTITY,
            entity_id=item.id,
            before=before,
            after={
                "mime_type": detected,
                "sha256": stored.sha256,
                "size_bytes": stored.size_bytes,
            },
            changed_by=None,
            fields=TRACKED_MEDIA_FIELDS,
            reason="Archivo cargado",
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def read_file(self, item: MediaItem) -> bytes:
        if item.storage_key is None:
            raise MediaError("El recurso todavía no tiene archivo")
        storage = self._backend()
        try:
            return await storage.read(item.storage_key)
        except StorageError as error:
            raise MediaError(f"No se pudo leer el archivo: {error}") from error

    async def record_access(
        self,
        item: MediaItem,
        *,
        user: User,
        access_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        bytes_served: int | None = None,
    ) -> MediaAccessLog:
        """Write one row per read of the bytes.

        `bytes_served` is what this request delivered rather than the stored size,
        because the download route honours `Range`: a player seeking through a video
        issues many partial reads, and recording the whole file on each of them would
        make the column useless for a question like "how much left the server last
        week".
        """
        entry = MediaAccessLog(
            media_id=item.id,
            access_type=access_type,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            bytes_served=bytes_served,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def deactivate(self, item: MediaItem, actor: User) -> MediaItem:
        """Take a resource out of the library without removing it.

        The file stays. A deactivated row whose bytes had been deleted could not be
        brought back, and the whole reason not to delete rows is that they must stay
        readable.
        """
        before = {field: getattr(item, field, None) for field in TRACKED_MEDIA_FIELDS}
        item.is_active = False
        item.deleted_at = datetime.now(UTC)
        item.deleted_by = actor.id
        record_changes(
            self.session,
            entity=MEDIA_ENTITY,
            entity_id=item.id,
            before=before,
            after={"is_active": False},
            changed_by=actor.id,
            fields=TRACKED_MEDIA_FIELDS,
            reason="Recurso desactivado",
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def reactivate(self, item: MediaItem, actor: User) -> MediaItem:
        before = {field: getattr(item, field, None) for field in TRACKED_MEDIA_FIELDS}
        item.is_active = True
        item.deleted_at = None
        item.deleted_by = None
        record_changes(
            self.session,
            entity=MEDIA_ENTITY,
            entity_id=item.id,
            before=before,
            after={"is_active": True},
            changed_by=actor.id,
            fields=TRACKED_MEDIA_FIELDS,
            reason="Recurso reactivado",
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def _drop_previous(self, item: MediaItem) -> None:
        key = item.storage_key
        if key is None:
            return
        try:
            await self._backend().delete(key)
        except StorageError:
            # The new file is written under a new key and the row still points at
            # the old one until the update lands, so an orphan is a cost, not a
            # loss. It is reported instead of swallowed.
            logger.exception("No se pudo retirar el archivo anterior de %s", key)
            return
        item.storage_key = None
        item.sha256 = None
        item.size_bytes = None
        item.mime_type = None
        item.storage_tier = StorageTier.HOT.value


def media_type_label(mime_type: str | None) -> str:
    """Short, human label for a detected type, shown next to the file name."""
    labels: dict[str, str] = {
        "video/mp4": "MP4",
        "video/webm": "WebM",
        "video/quicktime": "QuickTime",
        "video/x-msvideo": "AVI",
        "audio/mpeg": "MP3",
        "audio/mp4": "M4A",
        "audio/wav": "WAV",
        "audio/ogg": "Ogg",
        "image/png": "PNG",
        "image/jpeg": "JPEG",
        "image/webp": "WebP",
        "image/gif": "GIF",
        "application/pdf": "PDF",
    }
    return labels.get(mime_type or "", "Archivo")


__all__ = [
    "HEADER_BYTES",
    "MEDIA_ENTITY",
    "MEDIA_MIME_KINDS",
    "MEDIA_SIGNATURES",
    "TRACKED_MEDIA_FIELDS",
    "MediaError",
    "MediaService",
    "MediaValidationError",
    "detect_media_type",
    "kind_for",
    "media_type_label",
]
