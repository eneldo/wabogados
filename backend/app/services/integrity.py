"""Bucket integrity verification.

This module answers one question: does the stored content still match what the
database says it should be? It exists because a silent failure is the only kind
that actually loses data. A missing row is noticed the moment someone opens the
document. A corrupted byte on disk is noticed when it matters most, which is
during a hearing.

What it deliberately cannot do:

- **It never repairs.** There is no write path to document content anywhere in
  this module. Corruption is reported to a human, who decides whether to restore
  from a backup. Silently overwriting a legal document is worse than any outage.
- **It never deletes.** Not even an object with no database row. An orphan may
  be the remnant of a write that failed to commit, and that evidence matters.

Findings per version:

- ``ok``: the content hashes to the recorded digest.
- ``missing``: the key is absent from the storage backend.
- ``corrupted``: content is present but the digest differs. Bit rot, a partial
  write or an out of band edit. The worst case, because it looks available.
- ``size_mismatch``: the size differs, detected without downloading anything.
- ``unreadable``: the backend raised an error. Reported rather than raised, so a
  single unreachable object does not abort the run.
- ``orphaned``: the object exists in the backend with no database row.

Cost control: a full run downloads every byte in the bucket. ``sample`` mode
verifies a deterministic subset so a nightly job stays affordable while a full
audit is run periodically.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

import anyio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import DocumentVersion, IntegrityFinding, IntegrityScan
from app.services.storage import StorageBackend, StorageError, build_storage

logger = logging.getLogger(__name__)

# How many objects are hashed at the same time. Reads are I/O bound, so a small
# pool gives most of the speed-up without exhausting the backend connection
# limits or memory.
READ_CONCURRENCY = 8

# Rows fetched per batch. Batching keeps memory flat and gives the database a
# chance to release rows while the reads run.
BATCH_SIZE = 200


class FindingType(StrEnum):
    OK = "ok"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    SIZE_MISMATCH = "size_mismatch"
    UNREADABLE = "unreadable"
    ORPHANED = "orphaned"


#: Findings that mean the firm could lose access to a document.
BLOCKING_FINDINGS = frozenset(
    {FindingType.MISSING, FindingType.CORRUPTED, FindingType.SIZE_MISMATCH}
)


class ScanMode(StrEnum):
    FULL = "full"
    SAMPLE = "sample"


class ScanStatus(StrEnum):
    OK = "ok"
    PROBLEMS = "problems"
    FAILED = "failed"


@dataclass(frozen=True)
class Finding:
    """A single verification result. Not persisted unless it is a problem."""

    finding_type: FindingType
    storage_key: str
    document_id: UUID | None = None
    version_id: UUID | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    detail: str | None = None

    @property
    def blocking(self) -> bool:
        return self.finding_type in BLOCKING_FINDINGS


@dataclass
class ScanReport:
    """Outcome of a verification run, suitable for JSON and for the CLI."""

    mode: str
    status: str
    backend: str
    checked: int = 0
    ok: int = 0
    missing: int = 0
    corrupted: int = 0
    size_mismatch: int = 0
    unreadable: int = 0
    orphaned: int = 0
    check_orphans: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    detail: str | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> int:
        return self.missing + self.corrupted + self.size_mismatch

    @property
    def healthy(self) -> bool:
        return self.blocking == 0 and self.unreadable == 0

    def as_dict(self, *, include_findings: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "mode": self.mode,
            "status": self.status,
            "backend": self.backend,
            "checked": self.checked,
            "ok": self.ok,
            "missing": self.missing,
            "corrupted": self.corrupted,
            "size_mismatch": self.size_mismatch,
            "unreadable": self.unreadable,
            "orphaned": self.orphaned,
            "blocking": self.blocking,
            "healthy": self.healthy,
            "check_orphans": self.check_orphans,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "detail": self.detail,
        }
        if include_findings:
            payload["findings"] = [
                {
                    "finding_type": str(finding.finding_type),
                    "storage_key": finding.storage_key,
                    "document_id": str(finding.document_id) if finding.document_id else None,
                    "version_id": str(finding.version_id) if finding.version_id else None,
                    "expected_sha256": finding.expected_sha256,
                    "actual_sha256": finding.actual_sha256,
                    "detail": finding.detail,
                }
                for finding in self.findings
            ]
        return payload


class IntegrityService:
    """Read only verification of the stored content against the database."""

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageBackend | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        if storage is not None:
            self.storage = storage
        else:
            self.storage = build_storage(self.settings)

    async def _candidate_keys(
        self, sample: int | None
    ) -> list[tuple[UUID, UUID, str, str, int]]:
        """Return (document_id, version_id, key, sha256, size) to verify.

        Only active documents are included: a soft deleted document keeps its
        content on purpose and must still be verifiable.
        """
        statement = select(
            DocumentVersion.document_id,
            DocumentVersion.id,
            DocumentVersion.storage_key,
            DocumentVersion.sha256,
            DocumentVersion.size_bytes,
        ).order_by(DocumentVersion.created_at.desc())

        if sample is not None:
            # `TABLESAMPLE` would need the physical rows and is not portable.
            # Ordering by newest and taking the head gives a deterministic,
            # reproducible sample, which matters when two runs must agree.
            statement = statement.limit(sample)

        result = await self.session.execute(statement)
        return [
            (document_id, version_id, key, digest, size)
            for document_id, version_id, key, digest, size in result.all()
        ]

    async def _verify_one(
        self, document_id: UUID, version_id: UUID, key: str, expected: str, size: int
    ) -> Finding:
        stat = await self.storage.stat(key)
        if stat is None:
            return Finding(
                finding_type=FindingType.MISSING,
                storage_key=key,
                document_id=document_id,
                version_id=version_id,
                expected_sha256=expected,
                detail="La clave no existe en el almacenamiento",
            )

        if stat.size_bytes != size:
            # Caught without downloading anything, so a truncated file is cheap
            # to detect in a full scan.
            return Finding(
                finding_type=FindingType.SIZE_MISMATCH,
                storage_key=key,
                document_id=document_id,
                version_id=version_id,
                expected_sha256=expected,
                detail=f"tamaño {stat.size_bytes} en el storage, {size} registrados",
            )

        try:
            content = await self.storage.read(key)
        except StorageError as error:
            return Finding(
                finding_type=FindingType.UNREADABLE,
                storage_key=key,
                document_id=document_id,
                version_id=version_id,
                expected_sha256=expected,
                detail=str(error),
            )

        actual = sha256(content).hexdigest()
        if actual != expected:
            return Finding(
                finding_type=FindingType.CORRUPTED,
                storage_key=key,
                document_id=document_id,
                version_id=version_id,
                expected_sha256=expected,
                actual_sha256=actual,
                detail="El contenido almacenado no coincide con su hash",
            )

        return Finding(
            finding_type=FindingType.OK,
            storage_key=key,
            document_id=document_id,
            version_id=version_id,
            expected_sha256=expected,
            actual_sha256=actual,
        )

    async def _verify_batch(
        self, rows: list[tuple[UUID, UUID, str, str, int]]
    ) -> list[Finding]:
        """Verify a batch with bounded concurrency.

        The database session is deliberately not touched here: an AsyncSession
        is not safe to share across concurrent tasks. Reads happen in parallel,
        then the caller persists results sequentially.
        """
        findings: list[Finding] = []
        limiter = anyio.CapacityLimiter(READ_CONCURRENCY)
        results: list[Finding | None] = [None] * len(rows)

        async def run(index: int, row: tuple[UUID, UUID, str, str, int]) -> None:
            async with limiter:
                results[index] = await self._verify_one(*row)

        async with anyio.create_task_group() as group:
            for index, row in enumerate(rows):
                group.start_soon(run, index, row)

        for finding in results:
            if finding is not None:
                findings.append(finding)
        return findings

    async def _find_orphans(self, known_keys: set[str]) -> list[Finding]:
        """Objects present in the backend with no database row.

        An orphan is not corruption: it is usually a write whose database
        transaction failed after the bytes were stored. It is still reported,
        because it is the only way to prove nothing was added to the bucket.
        """
        orphans: list[Finding] = []
        async for key in self.storage.iter_keys():
            if key in known_keys:
                continue
            orphans.append(
                Finding(
                    finding_type=FindingType.ORPHANED,
                    storage_key=key,
                    detail="Objeto en el almacenamiento sin fila en la base de datos",
                )
            )
        return orphans

    async def run(
        self,
        *,
        mode: ScanMode = ScanMode.FULL,
        sample: int | None = None,
        check_orphans: bool = False,
        actor_id: UUID | None = None,
        persist: bool = True,
    ) -> ScanReport:
        """Verify the backend against the database. Never modifies content."""
        started = time.monotonic()
        started_at = datetime.now(UTC)
        effective_sample = sample if mode is ScanMode.SAMPLE else None
        if mode is ScanMode.SAMPLE and effective_sample is None:
            effective_sample = 200

        report = ScanReport(
            mode=str(mode),
            status=str(ScanStatus.FAILED),
            backend=type(self.storage).__name__,
            started_at=started_at,
            check_orphans=check_orphans,
        )

        try:
            rows = await self._candidate_keys(effective_sample)
        except Exception as error:
            report.detail = f"No se pudo leer el inventario: {error}"
            report.finished_at = datetime.now(UTC)
            report.duration_seconds = round(time.monotonic() - started, 3)
            if persist:
                await self._persist(report, actor_id)
            return report

        findings: list[Finding] = []
        for start in range(0, len(rows), BATCH_SIZE):
            findings.extend(await self._verify_batch(rows[start : start + BATCH_SIZE]))

        known_keys = {row[2] for row in rows}
        if check_orphans:
            try:
                findings.extend(await self._find_orphans(known_keys))
            except StorageError as error:
                report.detail = f"No se pudo listar el almacenamiento: {error}"
                logger.warning("Fallo al listar el almacenamiento: %s", error)

        report.findings = findings
        report.checked = len(rows)
        report.ok = sum(1 for f in findings if f.finding_type is FindingType.OK)
        report.missing = sum(1 for f in findings if f.finding_type is FindingType.MISSING)
        report.corrupted = sum(1 for f in findings if f.finding_type is FindingType.CORRUPTED)
        report.size_mismatch = sum(
            1 for f in findings if f.finding_type is FindingType.SIZE_MISMATCH
        )
        report.unreadable = sum(
            1 for f in findings if f.finding_type is FindingType.UNREADABLE
        )
        report.orphaned = sum(1 for f in findings if f.finding_type is FindingType.ORPHANED)
        report.finished_at = datetime.now(UTC)
        report.duration_seconds = round(time.monotonic() - started, 3)
        report.status = str(ScanStatus.OK if report.healthy else ScanStatus.PROBLEMS)
        if mode is ScanMode.SAMPLE:
            report.detail = (
                report.detail
                or f"muestra determinista de {len(rows)} versiones más recientes"
            )

        if persist:
            await self._persist(report, actor_id)
        return report

    async def _persist(self, report: ScanReport, actor_id: UUID | None) -> None:
        """Record the run so verification history exists for an auditor."""
        scan = IntegrityScan(
            mode=report.mode,
            status=report.status,
            backend=report.backend,
            checked=report.checked,
            ok_count=report.ok,
            missing_count=report.missing,
            corrupted_count=report.corrupted,
            unreadable_count=report.unreadable,
            orphaned_count=report.orphaned,
            check_orphans=report.check_orphans,
            started_at=report.started_at,
            finished_at=report.finished_at,
            duration_seconds=report.duration_seconds,
            detail=report.detail,
            created_by=actor_id,
        )
        self.session.add(scan)
        await self.session.flush()

        for finding in report.findings:
            if finding.finding_type is FindingType.OK:
                continue
            self.session.add(
                IntegrityFinding(
                    scan_id=scan.id,
                    finding_type=str(finding.finding_type),
                    storage_key=finding.storage_key,
                    document_id=finding.document_id,
                    version_id=finding.version_id,
                    expected_sha256=finding.expected_sha256,
                    actual_sha256=finding.actual_sha256,
                    detail=finding.detail,
                )
            )
        await self.session.flush()

    async def total_versions(self) -> int:
        value = await self.session.scalar(select(func.count()).select_from(DocumentVersion))
        return int(value or 0)

    async def latest_scan(self) -> IntegrityScan | None:
        result = await self.session.execute(
            select(IntegrityScan).order_by(IntegrityScan.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def findings_for_version(self, version_id: UUID) -> list[IntegrityFinding]:
        result = await self.session.execute(
            select(IntegrityFinding)
            .where(IntegrityFinding.version_id == version_id)
            .order_by(IntegrityFinding.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = [
    "BLOCKING_FINDINGS",
    "Finding",
    "FindingType",
    "IntegrityService",
    "ScanMode",
    "ScanReport",
    "ScanStatus",
]