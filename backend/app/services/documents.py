"""Document service: logical documents with immutable versions."""

import hashlib
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_user_permission_names
from app.models import Case, Document, DocumentDownload, DocumentVersion, User
from app.schemas.documents import DocumentCreate, DocumentUpdate
from app.services.history import record_changes
from app.services.storage import StorageBackend, StorageError, build_storage
from app.services.uploads import UploadValidationError, validate_upload

DOCUMENT_ENTITY = "documents"

INTERNAL_VISIBILITY = ("interna", "equipo")
PUBLISHED_VISIBILITY = "publicada"

TRACKED_DOCUMENT_FIELDS = (
    "title",
    "description",
    "document_type",
    "status",
    "confidentiality",
    "visibility",
)


class DocumentError(Exception):
    """Raised when a document operation violates a business rule."""


def visible_visibilities(user: User) -> tuple[str, ...]:
    permissions = get_user_permission_names(user)
    if user.is_superuser or "documents:read" in permissions:
        return (*INTERNAL_VISIBILITY, PUBLISHED_VISIBILITY)
    if "documents:read_published" in permissions:
        return (PUBLISHED_VISIBILITY,)
    return ()


class DocumentService:
    def __init__(
        self, session: AsyncSession, storage: StorageBackend | None = None
    ) -> None:
        self.session = session
        self.storage = storage or build_storage()

    def _visibility_filter(self, allowed: tuple[str, ...]) -> ColumnElement[bool]:
        if not allowed:
            return func.false()
        return Document.visibility.in_(allowed)

    def _base_filters(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
        case_id: UUID | None = None,
        document_type: str | None = None,
        status: str | None = None,
    ) -> list[ColumnElement[bool]]:
        """The conditions every listing shares, so the two can never drift apart.

        The global browser and the per-case listing must agree on what a user is
        allowed to see; if they differ, the menu promises something the endpoint
        then refuses.
        """
        filters: list[ColumnElement[bool]] = [
            Document.is_active.is_(True),
            self._visibility_filter(visible_visibilities(user)),
        ]
        if scope_clause is not None:
            filters.append(scope_clause)
        if case_id is not None:
            filters.append(Document.case_id == case_id)
        if document_type:
            filters.append(Document.document_type == document_type)
        if status:
            filters.append(Document.status == status)
        return filters

    async def list_documents(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
        case_id: UUID | None = None,
        document_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Document]:
        filters = self._base_filters(
            user,
            scope_clause=scope_clause,
            case_id=case_id,
            document_type=document_type,
            status=status,
        )

        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.versions), selectinload(Document.case))
            .where(*filters)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def browse_documents(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        case_id: UUID | None = None,
        document_type: str | None = None,
        status: str | None = None,
        confidentiality: str | None = None,
        visibility: str | None = None,
        legal_hold: bool | None = None,
    ) -> tuple[list[Document], int]:
        """The global browser: one page of documents across every visible case.

        Returns the page and the total so the pager can show `1-50 de 312`
        instead of guessing from whether the page came back full.
        """
        filters = self._base_filters(
            user,
            scope_clause=scope_clause,
            case_id=case_id,
            document_type=document_type,
            status=status,
        )
        if confidentiality:
            filters.append(Document.confidentiality == confidentiality)
        if visibility:
            # A filter may only narrow what the user can already see; it can
            # never widen visibility, which stays with `visible_visibilities`.
            filters.append(Document.visibility == visibility)
        if legal_hold is not None:
            filters.append(Document.legal_hold.is_(legal_hold))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                Document.title.ilike(pattern)
                | Document.description.ilike(pattern)
                | Document.case.has(Case.case_number.ilike(pattern))
                | Document.case.has(Case.title.ilike(pattern))
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Document).where(*filters)
        ) or 0
        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.versions), selectinload(Document.case))
            .where(*filters)
            # Most recently touched first: the browser is opened to work on
            # what is in hand, not to read the archive from the top.
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_document(self, document_id: UUID) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.versions), selectinload(Document.case))
            .where(Document.id == document_id)
            # Refresh eagerly loaded collections: a version may have been added
            # earlier in the same session and the identity map would be stale.
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_visible_document(
        self,
        document_id: UUID,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None,
    ) -> Document | None:
        """Return the document only if the caller may read it.

        Both conditions apply, and the scope is **not optional**:

        - the visibility must be one the caller is allowed to read, and
        - the document must be inside the caller's case scope.

        Checking only the visibility was a real leak. `browse_documents` filtered by
        case and this lookup did not, so a lawyer with no assignments saw an empty
        listing and could still read, edit, extend and **download** any document in
        the firm by guessing its UUID. A client could read every published document
        of every client.

        `scope_clause` is keyword-only and has no default on purpose. With a
        default of `None` a new endpoint would compile, pass every existing test
        and reintroduce the leak; here `mypy` fails at every call site that has not
        decided which cases the caller may reach. Passing `None` is still possible
        and still a decision — `get_user_scope` returns `ALL` for an administrator
        and `scope_filter` turns that into `None` — but it can no longer happen by
        omission.
        """
        filters: list[ColumnElement[bool]] = [
            Document.id == document_id,
            Document.is_active.is_(True),
            self._visibility_filter(visible_visibilities(user)),
        ]
        if scope_clause is not None:
            filters.append(scope_clause)

        result = await self.session.execute(
            select(Document)
            .options(
                selectinload(Document.versions),
                selectinload(Document.case),
            )
            .where(*filters)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _require_case(self, case_id: UUID) -> Case:
        result = await self.session.execute(
            select(Case).where(Case.id == case_id, Case.is_active.is_(True))
        )
        case = result.scalar_one_or_none()
        if case is None:
            raise DocumentError("El expediente no existe o está inactivo")
        return case

    async def create_document(
        self, payload: DocumentCreate, *, actor_id: UUID | None = None
    ) -> Document:
        await self._require_case(payload.case_id)
        document = Document(
            case_id=payload.case_id,
            document_type=payload.document_type,
            title=payload.title,
            description=payload.description,
            status="borrador",
            confidentiality=payload.confidentiality,
            visibility=payload.visibility,
            created_by=actor_id,
            is_active=True,
        )
        self.session.add(document)
        await self.session.flush()
        record_changes(
            self.session,
            entity=DOCUMENT_ENTITY,
            entity_id=document.id,
            before={},
            after=payload.model_dump(mode="json"),
            changed_by=actor_id,
            fields=TRACKED_DOCUMENT_FIELDS,
        )
        await self.session.flush()
        return document

    async def update_document(
        self, document: Document, payload: DocumentUpdate, *, actor_id: UUID | None = None
    ) -> Document:
        data = payload.model_dump(exclude_unset=True)
        if data.get("status") == "anulado" and document.status == "anulado":
            raise DocumentError("El documento ya está anulado")
        before = {field: getattr(document, field, None) for field in TRACKED_DOCUMENT_FIELDS}
        for field, value in data.items():
            setattr(document, field, value)
        record_changes(
            self.session,
            entity=DOCUMENT_ENTITY,
            entity_id=document.id,
            before=before,
            after=data,
            changed_by=actor_id,
            fields=TRACKED_DOCUMENT_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def add_version(
        self,
        document: Document,
        content: bytes,
        original_name: str,
        *,
        declared_mime: str | None = None,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> DocumentVersion:
        """Append an immutable version; the previous content is never touched."""
        if document.status == "anulado":
            raise DocumentError("No se pueden añadir versiones a un documento anulado")

        try:
            validated = validate_upload(content, original_name, declared_mime)
        except UploadValidationError as error:
            raise DocumentError(str(error)) from error

        last = await self.session.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document.id
            )
        )
        next_number = int(last or 0) + 1

        if await self._duplicate_hash(document.id, validated.sha256):
            raise DocumentError("El archivo ya existe como versión de este documento")

        key = self.storage.build_key(
            document.case_id, document.id, next_number, validated.extension
        )
        try:
            stored = await self.storage.write(key, content)
        except StorageError as error:
            raise DocumentError(str(error)) from error

        # The backend reports what it actually persisted. Refuse to record a
        # version whose stored bytes do not match the validated upload.
        if stored.sha256 != validated.sha256 or stored.size_bytes != validated.size_bytes:
            await self.storage.delete(key)
            raise DocumentError(
                "El almacenamiento no devolvió el contenido esperado; "
                "la versión no se ha registrado"
            )

        previous = (
            await self.session.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.is_current.is_(True),
                )
            )
        ).scalar_one_or_none()
        if previous is not None:
            previous.is_current = False

        version = DocumentVersion(
            document_id=document.id,
            version_number=next_number,
            original_name=original_name[:255],
            storage_key=key,
            mime_type=validated.mime_type,
            size_bytes=validated.size_bytes,
            sha256=validated.sha256,
            notes=notes,
            is_current=True,
            created_by=actor_id,
        )
        self.session.add(version)
        document.current_version = next_number
        if document.status == "borrador":
            document.status = "vigente"
        try:
            await self.session.flush()
        except SQLAlchemyError:
            # Compensate: never leave a stored file without its database row.
            await self.storage.delete(key)
            raise
        # Reload the collection so the in session object matches the database.
        # Without this, `len(document.versions)` can report a stale count and
        # touching the collection outside a greenlet raises MissingGreenlet.
        await self.session.refresh(document, ["versions"])
        await self.session.refresh(version)
        return version

    async def _duplicate_hash(self, document_id: UUID, digest: str) -> bool:
        result = await self.session.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.sha256 == digest,
            )
        )
        return result.scalar_one_or_none() is not None

    async def current_version(self, document_id: UUID) -> DocumentVersion | None:
        result = await self.session.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_current.is_(True),
            )
            .order_by(DocumentVersion.version_number.desc())
        )
        return result.scalar_one_or_none()

    async def read_version(
        self,
        version: DocumentVersion,
        *,
        user: User | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bytes:
        """Read the stored content and always record the download."""
        try:
            content = await self.storage.read(version.storage_key)
        except StorageError as error:
            raise DocumentError(str(error)) from error

        # A download that does not match the recorded hash is an integrity
        # incident, not a successful transfer. Never serve corrupted bytes.
        if hashlib.sha256(content).hexdigest() != version.sha256:
            raise DocumentError(
                "El contenido almacenado no coincide con su hash registrado; "
                "la descarga se ha bloqueado"
            )

        self.session.add(
            DocumentDownload(
                document_id=version.document_id,
                version_id=version.id,
                user_id=user.id if user else None,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:2000] or None,
            )
        )
        await self.session.flush()
        return content

    async def download_history(self, document_id: UUID, limit: int) -> list[DocumentDownload]:
        result = await self.session.execute(
            select(DocumentDownload)
            .where(DocumentDownload.document_id == document_id)
            .order_by(DocumentDownload.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


__all__ = [
    "DOCUMENT_ENTITY",
    "PUBLISHED_VISIBILITY",
    "DocumentError",
    "DocumentService",
    "visible_visibilities",
]
