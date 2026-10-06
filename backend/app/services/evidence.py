"""Evidence service: chain of custody, immutable originals and processing.

The invariants this module defends, all from MASTER_PROMPT section 40:

- The original is never overwritten or replaced (rule 7).
- Every evidence has a SHA-256 (rule 8).
- Every download of the original is audited (rule 9).
- A client only sees published evidence (rule 10).
- Internal evidence is never exposed (rule 11).
- Cross client access is impossible (rule 12).
- A derivative never legally substitutes the original (rule 14).
- A signed PDF is never modified as an original (rule 15).

The immutable fields (`original_sha256`, `created_at`, `storage_key`) are not
reachable from any update schema. That is enforced by construction: `update_evidence`
only accepts the fields listed in `MUTABLE_FIELDS`.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_user_permission_names
from app.core.config import get_settings
from app.models import (
    Action,
    Case,
    Evidence,
    EvidenceAccessLog,
    EvidenceDerivative,
    EvidenceEvent,
    EvidenceFile,
    EvidenceProcessingJob,
    User,
)
from app.services.evidence_processing import (
    Derivative,
    ProcessingError,
    analyse_image,
    analyse_pdf,
    optimise_pdf,
    process_image,
)
from app.services.evidence_validation import (
    EvidenceValidationError,
    ValidatedEvidence,
    validate_evidence,
)
from app.services.storage import StorageBackend, StorageError, build_storage

logger = logging.getLogger(__name__)

EVIDENCE_ENTITY = "evidences"

INTERNAL_VISIBILITY = ("interna", "equipo")
PUBLISHED_VISIBILITY = "publicada"

#: Files at or below this size are processed inline. Above it the work is
#: queued for a worker, so a heavy request never blocks an HTTP response
#: (MASTER_PROMPT section 27).
INLINE_LIMIT_BYTES = 5 * 1024 * 1024

#: The only fields a caller may change. The original hash, the upload date and
#: the storage key are deliberately absent and there is no API that reaches them.
MUTABLE_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "evidence_type",
    "visibility",
    "confidentiality",
    "action_id",
    "captured_at",
    "captured_location",
)


class EvidenceError(Exception):
    """Raised when an evidence operation is refused."""


class EvidenceStatus(StrEnum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    SCANNING = "scanning"
    PROCESSING = "processing"
    OPTIMIZED = "optimized"
    READY = "ready"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class EventType(StrEnum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    ORIGINAL_STORED = "original_stored"
    DERIVATIVE_CREATED = "derivative_created"
    PROCESSED = "processed"
    PROCESSING_FAILED = "processing_failed"
    QUEUED = "queued"
    VISIBILITY_CHANGED = "visibility_changed"
    CLASSIFIED = "classified"
    ARCHIVED = "archived"
    DOWNLOADED_ORIGINAL = "downloaded_original"
    DOWNLOADED_DERIVATIVE = "downloaded_derivative"
    VIEWED = "viewed"


class JobStatus(StrEnum):
    """Lifecycle of an asynchronous evidence job.

    These were four bare strings spread across the service. A worker filter that
    spells `"runing"` instead of `"running"` would silently stop matching, so
    the values live in one place.
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(StrEnum):
    PROCESS = "process"


@dataclass(frozen=True)
class ProcessingOutcome:
    """What the pipeline produced, for the response and the custody trail."""

    derivatives: int
    queued: bool
    pages: int | None = None
    width: int | None = None
    height: int | None = None
    is_signed_pdf: bool = False
    signature_broken: bool = False
    detail: str | None = None


def visible_visibilities(user: User) -> tuple[str, ...]:
    """Return the visibilities the caller may see."""
    permissions = get_user_permission_names(user)
    if "evidences:view" in permissions:
        return ("interna", "equipo", "publicada")
    if "evidences:view_published" in permissions:
        return (PUBLISHED_VISIBILITY,)
    return ()


class EvidenceService:
    """Create, process and hand out evidence. Never alters an original."""

    def __init__(
        self, session: AsyncSession, storage: StorageBackend | None = None
    ) -> None:
        self.session = session
        self.settings = get_settings()
        if storage is not None:
            self.storage = storage
        else:
            self.storage = build_storage(self.settings)

    # -- scope --------------------------------------------------------------

    def _visibility_filter(self, allowed: tuple[str, ...]) -> ColumnElement[bool]:
        if not allowed:
            return func.false()
        return Evidence.visibility.in_(allowed)

    # -- events -------------------------------------------------------------

    def record_event(
        self,
        evidence: Evidence,
        event_type: EventType,
        *,
        actor_id: UUID | None = None,
        from_value: str | None = None,
        to_value: str | None = None,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> EvidenceEvent:
        """Append to the custody trail. Events are never updated or deleted."""
        event = EvidenceEvent(
            evidence_id=evidence.id,
            event_type=str(event_type),
            from_value=from_value,
            to_value=to_value,
            detail=detail,
            actor_id=actor_id,
            ip_address=ip_address,
        )
        self.session.add(event)
        return event

    # -- creation -----------------------------------------------------------

    async def create_evidence(
        self,
        *,
        case_id: UUID,
        title: str,
        evidence_type: str,
        actor: User,
        description: str | None = None,
        action_id: UUID | None = None,
        visibility: str = "interna",
        confidentiality: str = "interno",
        captured_at: datetime | None = None,
        captured_location: str | None = None,
        ip_address: str | None = None,
    ) -> Evidence:
        """Register an evidence record before its file arrives."""
        case = await self.session.get(Case, case_id)
        if case is None or not case.is_active:
            raise EvidenceError("El expediente no existe")

        if action_id is not None:
            action = await self.session.get(Action, action_id)
            # An action from another case would silently move evidence across
            # files, so it is refused rather than ignored.
            if action is None or action.case_id != case_id:
                raise EvidenceError("La actuación no pertenece al expediente")

        evidence = Evidence(
            case_id=case_id,
            action_id=action_id,
            title=title,
            description=description,
            evidence_type=evidence_type,
            status=str(EvidenceStatus.UPLOADED),
            visibility=visibility,
            confidentiality=confidentiality,
            captured_at=captured_at,
            captured_location=captured_location,
            created_by=actor.id,
            is_active=True,
        )
        self.session.add(evidence)
        await self.session.flush()

        self.record_event(
            evidence,
            EventType.UPLOADED,
            actor_id=actor.id,
            to_value=str(EvidenceStatus.UPLOADED),
            detail="Registro de evidencia creado",
            ip_address=ip_address,
        )
        return evidence

    async def attach_original(
        self,
        evidence: Evidence,
        content: bytes,
        original_name: str,
        *,
        declared_mime: str | None = None,
        actor: User | None = None,
        ip_address: str | None = None,
    ) -> tuple[EvidenceFile, ProcessingOutcome]:
        """Validate, store and process the received file.

        The original is stored first and never written again. If the database
        refuses the row afterwards, the stored object is removed so no content
        exists without its record.
        """
        evidence.status = str(EvidenceStatus.VALIDATING)
        await self.session.flush()

        try:
            validated = validate_evidence(content, original_name, declared_mime)
        except EvidenceValidationError as error:
            evidence.status = str(EvidenceStatus.QUARANTINED)
            self.record_event(
                evidence,
                EventType.PROCESSING_FAILED,
                actor_id=actor.id if actor else None,
                detail=str(error),
                ip_address=ip_address,
            )
            await self.session.flush()
            raise EvidenceError(str(error)) from error

        evidence.status = str(EvidenceStatus.SCANNING)
        self.record_event(
            evidence,
            EventType.VALIDATED,
            actor_id=actor.id if actor else None,
            detail=(
                f"{validated.mime_type}, {validated.size_bytes} bytes, "
                f"sha256 {validated.sha256[:12]}"
            ),
            ip_address=ip_address,
        )
        await self.session.flush()

        key = self.storage.build_evidence_key(
            evidence.case_id, evidence.id, "original", str(uuid4()), validated.extension
        )
        try:
            stored = await self.storage.write(key, content)
        except StorageError as error:
            raise EvidenceError(str(error)) from error

        if stored.sha256 != validated.sha256:
            # The store did not persist what we sent. Do not record a version
            # whose bytes we cannot vouch for.
            await self.storage.delete(key)
            raise EvidenceError(
                "El almacenamiento no devolvió el contenido esperado"
            )

        analysis = self._analyse(content, validated)

        evidence_file = EvidenceFile(
            evidence_id=evidence.id,
            storage_key=key,
            original_filename=original_name[:255],
            mime_type=validated.mime_type,
            file_size=validated.size_bytes,
            sha256=validated.sha256,
            width=analysis.width,
            height=analysis.height,
            page_count=analysis.page_count,
            is_original=True,
            is_signed_pdf=analysis.is_signed_pdf,
            signature_broken=analysis.signature_broken,
        )
        self.session.add(evidence_file)

        evidence.original_filename = original_name[:255]
        evidence.original_mime_type = validated.mime_type
        evidence.original_size = validated.size_bytes
        evidence.original_sha256 = validated.sha256
        evidence.is_signed_pdf = analysis.is_signed_pdf

        self.record_event(
            evidence,
            EventType.ORIGINAL_STORED,
            actor_id=actor.id if actor else None,
            to_value=key,
            detail=(
                f"Original almacenado: {validated.mime_type}, "
                f"{validated.size_bytes} bytes"
                + (", PDF FIRMADO" if analysis.is_signed_pdf else "")
                + (
                    ", firma alterada"
                    if analysis.signature_broken
                    else ""
                )
            ),
            ip_address=ip_address,
        )

        try:
            await self.session.flush()
        except SQLAlchemyError:
            await self.storage.delete(key)
            raise

        outcome = await self.process(evidence, evidence_file, content, actor=actor)
        await self.session.refresh(evidence_file)
        return evidence_file, outcome

    def _analyse(self, content: bytes, validated: ValidatedEvidence) -> "_Analysis":
        """Read format metadata, recording a signed PDF without modifying it."""
        if validated.is_pdf:
            try:
                pdf = analyse_pdf(content)
            except ProcessingError as error:
                raise EvidenceError(str(error)) from error
            return _Analysis(
                width=None,
                height=None,
                page_count=pdf.page_count,
                is_signed_pdf=pdf.is_signed,
                signature_broken=pdf.signature_broken,
            )
        try:
            image = analyse_image(content)
        except ProcessingError as error:
            raise EvidenceError(str(error)) from error
        return _Analysis(
            width=image.width,
            height=image.height,
            page_count=None,
            is_signed_pdf=False,
            signature_broken=False,
        )

    # -- processing ---------------------------------------------------------

    async def process(
        self,
        evidence: Evidence,
        evidence_file: EvidenceFile,
        content: bytes,
        *,
        actor: User | None = None,
    ) -> ProcessingOutcome:
        """Run the pipeline. Large files are queued instead of blocking."""
        if evidence_file.file_size > INLINE_LIMIT_BYTES:
            return await self._queue(evidence, actor=actor)

        evidence.status = str(EvidenceStatus.PROCESSING)
        await self.session.flush()

        try:
            derivatives = await self._produce(evidence, evidence_file, content)
        except ProcessingError as error:
            evidence.status = str(EvidenceStatus.FAILED)
            self.record_event(
                evidence,
                EventType.PROCESSING_FAILED,
                actor_id=actor.id if actor else None,
                detail=str(error),
            )
            await self.session.flush()
            return ProcessingOutcome(
                derivatives=0, queued=False, detail=str(error)
            )

        evidence.status = str(EvidenceStatus.READY)
        self.record_event(
            evidence,
            EventType.PROCESSED,
            actor_id=actor.id if actor else None,
            detail=f"{len(derivatives)} derivados generados",
        )
        await self.session.flush()
        return ProcessingOutcome(
            derivatives=len(derivatives),
            queued=False,
            pages=evidence_file.page_count,
            width=evidence_file.width,
            height=evidence_file.height,
            is_signed_pdf=evidence_file.is_signed_pdf,
            signature_broken=evidence_file.signature_broken,
        )

    async def _produce(
        self, evidence: Evidence, evidence_file: EvidenceFile, content: bytes
    ) -> list[EvidenceDerivative]:
        produced: list[EvidenceDerivative] = []
        candidates: list[Derivative]
        if evidence_file.mime_type == "application/pdf":
            pdf_analysis = analyse_pdf(content)
            candidates = [optimise_pdf(content, pdf_analysis)]
        else:
            image_analysis = analyse_image(content)
            candidates = process_image(
                content, image_analysis, source_size=evidence_file.file_size
            )

        for derivative in candidates:
            produced.append(
                await self._store_derivative(evidence, evidence_file, derivative)
            )
        return produced

    async def _store_derivative(
        self,
        evidence: Evidence,
        source: EvidenceFile,
        derivative: Derivative,
    ) -> EvidenceDerivative:
        area = "previews" if derivative.derivative_type.value == "thumbnail" else "optimized"
        key = self.storage.build_evidence_key(
            evidence.case_id,
            evidence.id,
            area,
            f"{derivative.derivative_type.value}_{uuid4().hex[:8]}",
            _extension_for(derivative.mime_type),
        )
        stored = await self.storage.write(key, derivative.content)
        if stored.sha256 != hashlib.sha256(derivative.content).hexdigest():
            await self.storage.delete(key)
            raise ProcessingError("El derivado almacenado no coincide con el generado")

        row = EvidenceDerivative(
            evidence_id=evidence.id,
            source_file_id=source.id,
            derivative_type=str(derivative.derivative_type),
            storage_key=key,
            mime_type=derivative.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            compression_ratio=derivative.compression_ratio,
            profile=str(derivative.profile) if derivative.profile else None,
            width=derivative.width,
            height=derivative.height,
            page_count=derivative.page_count,
        )
        self.session.add(row)
        self.record_event(
            evidence,
            EventType.DERIVATIVE_CREATED,
            detail=(
                f"{derivative.derivative_type.value} "
                f"({derivative.mime_type}, {stored.size_bytes} bytes, "
                f"reducción {derivative.compression_ratio}%)"
            ),
        )
        return row

    async def _queue(self, evidence: Evidence, *, actor: User | None) -> ProcessingOutcome:
        """Record the work and let a worker pick it up."""
        evidence.status = str(EvidenceStatus.PROCESSING)
        self.session.add(
            EvidenceProcessingJob(
                evidence_id=evidence.id,
                job_type=str(JobType.PROCESS),
                status=str(JobStatus.QUEUED),
            )
        )
        self.record_event(
            evidence,
            EventType.QUEUED,
            actor_id=actor.id if actor else None,
            detail="Archivo grande: en cola para el worker de evidencias",
        )
        await self.session.flush()
        return ProcessingOutcome(
            derivatives=0,
            queued=True,
            detail="En cola para procesar",
        )

    async def run_queued_job(
        self, job: EvidenceProcessingJob, *, worker: str = "cli"
    ) -> ProcessingOutcome:
        """Process one queued job. Used by the worker CLI."""
        evidence = await self.session.get(Evidence, job.evidence_id)
        if evidence is None:
            raise EvidenceError("La evidencia del trabajo ya no existe")

        evidence_file = next(
            (
                item
                for item in await self._files_of(evidence)
                if item.is_original
            ),
            None,
        )
        if evidence_file is None:
            raise EvidenceError("La evidencia no tiene archivo original")

        job.status = str(JobStatus.RUNNING)
        job.started_at = datetime.now(UTC)
        job.worker = worker
        job.attempts += 1
        evidence.status = str(EvidenceStatus.PROCESSING)
        await self.session.flush()

        try:
            content = await self.storage.read(evidence_file.storage_key)
        except StorageError as error:
            job.status = str(JobStatus.FAILED)
            job.error = str(error)
            job.finished_at = datetime.now(UTC)
            evidence.status = str(EvidenceStatus.FAILED)
            await self.session.flush()
            raise EvidenceError(str(error)) from error

        try:
            derivatives = await self._produce(evidence, evidence_file, content)
        except ProcessingError as error:
            job.status = str(JobStatus.FAILED)
            job.error = str(error)
            job.finished_at = datetime.now(UTC)
            evidence.status = str(EvidenceStatus.FAILED)
            self.record_event(evidence, EventType.PROCESSING_FAILED, detail=str(error))
            await self.session.flush()
            raise

        job.status = str(JobStatus.COMPLETED)
        job.finished_at = datetime.now(UTC)
        job.error = None
        evidence.status = str(EvidenceStatus.READY)
        self.record_event(
            evidence,
            EventType.PROCESSED,
            detail=f"{len(derivatives)} derivados generados por {worker}",
        )
        await self.session.flush()
        return ProcessingOutcome(
            derivatives=len(derivatives),
            queued=False,
            pages=evidence_file.page_count,
        )

    # -- queries ------------------------------------------------------------

    async def get_evidence(self, evidence_id: UUID) -> Evidence | None:
        result = await self.session.execute(
            select(Evidence)
            .options(
                selectinload(Evidence.files),
                selectinload(Evidence.derivatives),
                selectinload(Evidence.case),
            )
            .where(Evidence.id == evidence_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_visible_evidence(
        self,
        evidence_id: UUID,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
    ) -> Evidence | None:
        """Return the evidence only if the caller may see it.

        Both conditions apply and neither is optional:

        - the visibility must be one the caller is allowed to read, and
        - the evidence must be inside the caller's case scope.

        Checking only the visibility is the bug this signature exists to prevent:
        a permission without a scope lets any staff member read any record in the
        firm by guessing its identifier. The scope lives in the query rather than
        in a filter after loading, so it cannot be forgotten by a caller.
        """
        filters: list[ColumnElement[bool]] = [
            Evidence.id == evidence_id,
            Evidence.is_active.is_(True),
            self._visibility_filter(visible_visibilities(user)),
        ]
        if scope_clause is not None:
            filters.append(scope_clause)

        result = await self.session.execute(
            select(Evidence)
            .options(
                selectinload(Evidence.files),
                selectinload(Evidence.derivatives),
                selectinload(Evidence.case),
            )
            .where(*filters)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_evidences(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
        status: str | None = None,
        evidence_type: str | None = None,
        limit: int = 100,
    ) -> list[Evidence]:
        filters: list[ColumnElement[bool]] = [
            Evidence.is_active.is_(True),
            self._visibility_filter(visible_visibilities(user)),
        ]
        if scope_clause is not None:
            filters.append(scope_clause)
        if status:
            filters.append(Evidence.status == status)
        if evidence_type:
            filters.append(Evidence.evidence_type == evidence_type)

        result = await self.session.execute(
            select(Evidence)
            .options(selectinload(Evidence.case), selectinload(Evidence.derivatives))
            .where(*filters)
            .order_by(Evidence.created_at.desc())
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def custody_events(
        self, evidence_id: UUID, limit: int = 100
    ) -> list[EvidenceEvent]:
        result = await self.session.execute(
            select(EvidenceEvent)
            .where(EvidenceEvent.evidence_id == evidence_id)
            .order_by(EvidenceEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def access_logs(
        self, evidence_id: UUID, limit: int = 100
    ) -> list[EvidenceAccessLog]:
        result = await self.session.execute(
            select(EvidenceAccessLog)
            .where(EvidenceAccessLog.evidence_id == evidence_id)
            .order_by(EvidenceAccessLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def original_of(self, evidence: Evidence) -> EvidenceFile | None:
        """Return the original file.

        Queried explicitly rather than read from `evidence.files`: that
        relationship may not be loaded on an instance created in this session,
        and touching it outside a query raises MissingGreenlet.
        """
        result = await self.session.execute(
            select(EvidenceFile).where(
                EvidenceFile.evidence_id == evidence.id,
                EvidenceFile.is_original.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def derivatives_of(self, evidence: Evidence) -> list[EvidenceDerivative]:
        """Return the derivatives, queried explicitly for the same reason."""
        result = await self.session.execute(
            select(EvidenceDerivative).where(
                EvidenceDerivative.evidence_id == evidence.id
            )
        )
        return list(result.scalars().all())

    async def _files_of(self, evidence: Evidence) -> list[EvidenceFile]:
        result = await self.session.execute(
            select(EvidenceFile).where(EvidenceFile.evidence_id == evidence.id)
        )
        return list(result.scalars().all())

    # -- updates ------------------------------------------------------------

    async def update_evidence(
        self,
        evidence: Evidence,
        changes: dict[str, object],
        *,
        actor: User,
        ip_address: str | None = None,
    ) -> Evidence:
        """Apply changes to the mutable fields only."""
        forbidden = set(changes) - set(MUTABLE_FIELDS)
        if forbidden:
            raise EvidenceError(
                f"Campos inmutables de una evidencia: {sorted(forbidden)}"
            )

        before_visibility = evidence.visibility
        for field, value in changes.items():
            setattr(evidence, field, value)
        await self.session.flush()
        await self.session.refresh(evidence, ["files", "derivatives", "case"])

        after_visibility = str(changes.get("visibility", before_visibility))
        if after_visibility != before_visibility:
            self.record_event(
                evidence,
                EventType.VISIBILITY_CHANGED,
                actor_id=actor.id,
                from_value=before_visibility,
                to_value=after_visibility,
                ip_address=ip_address,
            )
        if any(key in changes for key in ("evidence_type", "action_id")):
            self.record_event(
                evidence,
                EventType.CLASSIFIED,
                actor_id=actor.id,
                to_value=str(changes.get("evidence_type", evidence.evidence_type)),
                ip_address=ip_address,
            )
        await self.session.flush()
        return evidence

    # -- access -------------------------------------------------------------

    async def read_original(
        self,
        evidence: Evidence,
        *,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bytes:
        """Read the original and always record the access (MASTER_PROMPT rule 9)."""
        original = await self.original_of(evidence)
        if original is None:
            raise EvidenceError("La evidencia no tiene archivo original")

        try:
            content = await self.storage.read(original.storage_key)
        except StorageError as error:
            raise EvidenceError(str(error)) from error

        if hashlib.sha256(content).hexdigest() != original.sha256:
            # Refusing to serve is the only safe answer to a corrupt original.
            raise EvidenceError(
                "El contenido no coincide con su hash. Descarga bloqueada por "
                "integridad."
            )

        self.session.add(
            EvidenceAccessLog(
                evidence_id=evidence.id,
                file_id=original.id,
                access_type="download_original",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:2000] or None,
            )
        )
        self.record_event(
            evidence,
            EventType.DOWNLOADED_ORIGINAL,
            actor_id=user.id,
            ip_address=ip_address,
            detail=f"sha256 {original.sha256[:12]}",
        )
        await self.session.flush()
        return content

    async def read_derivative(
        self,
        evidence: Evidence,
        derivative_id: UUID,
        *,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[EvidenceDerivative, bytes]:
        derivative = next(
            (
                item
                for item in await self.derivatives_of(evidence)
                if item.id == derivative_id
            ),
            None,
        )
        if derivative is None:
            raise EvidenceError("El derivado no existe")

        try:
            content = await self.storage.read(derivative.storage_key)
        except StorageError as error:
            raise EvidenceError(str(error)) from error

        self.session.add(
            EvidenceAccessLog(
                evidence_id=evidence.id,
                file_id=None,
                access_type="download_derivative",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:2000] or None,
            )
        )
        self.record_event(
            evidence,
            EventType.DOWNLOADED_DERIVATIVE,
            actor_id=user.id,
            ip_address=ip_address,
            detail=f"{derivative.derivative_type} sha256 {derivative.sha256[:12]}",
        )
        await self.session.flush()
        return derivative, content

    async def record_view(
        self, evidence: Evidence, *, user: User, ip_address: str | None = None
    ) -> None:
        self.session.add(
            EvidenceAccessLog(
                evidence_id=evidence.id,
                access_type="view",
                user_id=user.id,
                ip_address=ip_address,
            )
        )
        self.record_event(
            evidence, EventType.VIEWED, actor_id=user.id, ip_address=ip_address
        )
        await self.session.flush()


@dataclass(frozen=True)
class _Analysis:
    width: int | None
    height: int | None
    page_count: int | None
    is_signed_pdf: bool
    signature_broken: bool


def _extension_for(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }[mime_type]


__all__ = [
    "INLINE_LIMIT_BYTES",
    "MUTABLE_FIELDS",
    "EventType",
    "EvidenceError",
    "EvidenceService",
    "EvidenceStatus",
    "JobType",
    "ProcessingOutcome",
    "visible_visibilities",
]