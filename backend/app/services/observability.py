"""Observability figures for the evidence engine (MASTER_PROMPT section 43).

The prompt asks the system to measure evidence count, MB uploaded, MB saved,
compression ratio, processing time, failures, quarantine and storage usage. This
module computes all of them from the tables that already exist.

Two deliberate choices:

* **Counts and sums happen in SQL.** Uploading 100 GB of evidence must not make
  the metrics endpoint read 100 GB of rows to add them up.
* **Storage usage comes from the database, not from the bucket.** `pg_dump`
  restores what the database says was stored. If the two disagree, the
  discrepancy is itself the finding, and `integrity` already reports it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DocumentVersion,
    Evidence,
    EvidenceDerivative,
    EvidenceFile,
    EvidenceProcessingJob,
)
from app.services.evidence import EvidenceStatus, JobStatus

#: Bytes in a megabyte, as used by every figure below.
BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True)
class EvidenceMetrics:
    """Every figure of section 43, in one place."""

    evidence_count: int
    evidence_by_status: dict[str, int]
    original_mb: float
    optimised_mb: float
    saved_mb: float
    compression_ratio_percent: float
    derivatives_count: int
    jobs_by_status: dict[str, int]
    failed_jobs: int
    quarantined_evidence: int
    quarantined_files: int
    average_processing_seconds: float | None
    document_original_mb: float
    document_versions: int
    storage_mb: float

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_count": self.evidence_count,
            "evidence_by_status": self.evidence_by_status,
            "original_mb": round(self.original_mb, 2),
            "optimised_mb": round(self.optimised_mb, 2),
            "saved_mb": round(self.saved_mb, 2),
            "compression_ratio_percent": round(self.compression_ratio_percent, 1),
            "derivatives_count": self.derivatives_count,
            "jobs_by_status": self.jobs_by_status,
            "failed_jobs": self.failed_jobs,
            "quarantined_evidence": self.quarantined_evidence,
            "quarantined_files": self.quarantined_files,
            "average_processing_seconds": (
                None
                if self.average_processing_seconds is None
                else round(self.average_processing_seconds, 2)
            ),
            "document_original_mb": round(self.document_original_mb, 2),
            "document_versions": self.document_versions,
            "storage_mb": round(self.storage_mb, 2),
        }


async def _scalar(session: AsyncSession, statement: Select[Any]) -> float:
    result = await session.execute(statement)
    value = result.scalar()
    return float(value or 0)


def compression_percent(original: float, optimised: float) -> float:
    """Percentage saved, or 0 when there is nothing to compare against.

    A firm with no evidence yet has an infinite saving ratio; reporting 0 is
    the only honest number.
    """
    if original <= 0:
        return 0.0
    return max(0.0, (original - optimised) / original * 100)


class ObservabilityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evidence_metrics(self) -> EvidenceMetrics:
        evidence_count, by_status = await self._evidence_counts()
        original_bytes = await self._original_bytes()
        optimised_bytes = await self._derivative_bytes()
        derivative_count = await self._derivative_count()
        jobs_by_status, avg_seconds = await self._job_stats()
        quarantined_files = await self._quarantined_files()
        document_bytes, version_count = await self._document_bytes()

        original_mb = original_bytes / BYTES_PER_MB
        optimised_mb = optimised_bytes / BYTES_PER_MB
        document_mb = document_bytes / BYTES_PER_MB

        return EvidenceMetrics(
            evidence_count=evidence_count,
            evidence_by_status=by_status,
            original_mb=original_mb,
            optimised_mb=optimised_mb,
            saved_mb=max(0.0, original_mb - optimised_mb),
            compression_ratio_percent=compression_percent(
                original_mb, optimised_mb
            ),
            derivatives_count=derivative_count,
            jobs_by_status=jobs_by_status,
            failed_jobs=jobs_by_status.get(str(JobStatus.FAILED), 0),
            quarantined_evidence=by_status.get(
                str(EvidenceStatus.QUARANTINED), 0
            ),
            quarantined_files=quarantined_files,
            average_processing_seconds=avg_seconds,
            document_original_mb=document_mb,
            document_versions=version_count,
            # Everything the database says is stored: evidence originals, their
            # derivatives and document versions. Derivatives count because they
            # occupy real space in the bucket.
            storage_mb=original_mb + optimised_mb + document_mb,
        )

    async def _evidence_counts(self) -> tuple[int, dict[str, int]]:
        rows = await self.session.execute(
            select(Evidence.status, func.count())
            .group_by(Evidence.status)
        )
        by_status = {str(status): int(total) for status, total in rows}
        return sum(by_status.values()), by_status

    async def _original_bytes(self) -> float:
        """Bytes held by evidence originals. One original per evidence."""
        return await _scalar(
            self.session,
            select(func.coalesce(func.sum(EvidenceFile.file_size), 0)).where(
                EvidenceFile.is_original.is_(True)
            ),
        )

    async def _derivative_bytes(self) -> float:
        return await _scalar(
            self.session,
            select(func.coalesce(func.sum(EvidenceDerivative.size_bytes), 0)),
        )

    async def _derivative_count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(EvidenceDerivative)
        )
        return int(result.scalar() or 0)

    async def _job_stats(self) -> tuple[dict[str, int], float | None]:
        rows = await self.session.execute(
            select(EvidenceProcessingJob.status, func.count()).group_by(
                EvidenceProcessingJob.status
            )
        )
        by_status = {str(status): int(total) for status, total in rows}

        # Average wall time of the jobs that actually finished. Averaging over
        # the failed ones would mix two different numbers.
        durations = await self.session.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        EvidenceProcessingJob.finished_at
                        - EvidenceProcessingJob.started_at,
                    )
                )
            ).where(
                EvidenceProcessingJob.started_at.is_not(None),
                EvidenceProcessingJob.finished_at.is_not(None),
            )
        )
        average = durations.scalar()
        return by_status, (float(average) if average is not None else None)

    async def _quarantined_files(self) -> int:
        """Files belonging to evidence that sits in quarantine."""
        quarantined_ids = select(Evidence.id).where(
            Evidence.status == str(EvidenceStatus.QUARANTINED)
        )
        result = await self.session.execute(
            select(func.count())
            .select_from(EvidenceFile)
            .where(EvidenceFile.evidence_id.in_(quarantined_ids))
        )
        return int(result.scalar() or 0)

    async def _document_bytes(self) -> tuple[float, int]:
        rows = await self.session.execute(
            select(
                func.coalesce(func.sum(DocumentVersion.size_bytes), 0),
                func.count(),
            )
        )
        total, count = rows.one()
        return float(total or 0), int(count or 0)


async def storage_health(session: AsyncSession) -> dict[str, object]:
    """Storage figures plus when they were computed."""
    metrics = await ObservabilityService(session).evidence_metrics()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        **metrics.as_dict(),
    }


__all__ = [
    "BYTES_PER_MB",
    "EvidenceMetrics",
    "ObservabilityService",
    "compression_percent",
    "storage_health",
]