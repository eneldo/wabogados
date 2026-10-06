"""Version retention policy.

Scope of this module, and its limits, are deliberate:

- It **tiers** superseded versions: after `RETENTION_HOT_DAYS` a version that is
  no longer the current one moves to the archive tier, which is cheaper to keep.
- It **never deletes** document content. PROJECT_RULES rule 5 forbids removing
  legal records, and a law firm that loses a superseded version of a signed
  contract has a problem far worse than an oversized storage bill.
- It **never tiers** a document under legal hold, and never the current version
  of a document.

Every decision is recorded in `change_logs`, so an administrator can answer
"why is this version in the archive tier" months later.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import StorageTier
from app.models import ChangeLog, Document, DocumentVersion
from app.services.storage import StorageBackend, StorageError

logger = logging.getLogger(__name__)

RETENTION_ENTITY = "document_retention"


@dataclass(frozen=True)
class RetentionCandidate:
    """A version that the policy may move to the archive tier."""

    version_id: object
    document_id: object
    storage_key: str
    sha256: str
    age_days: int
    reason: str


@dataclass
class RetentionReport:
    """Outcome of a policy run. Counts are what an operator needs to see."""

    examined: int = 0
    archived: int = 0
    skipped_legal_hold: int = 0
    skipped_current: int = 0
    skipped_missing: int = 0
    failed: int = 0
    native_tier_applied: bool = False
    dry_run: bool = False
    archived_keys: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "examined": self.examined,
            "archived": self.archived,
            "skipped_legal_hold": self.skipped_legal_hold,
            "skipped_current": self.skipped_current,
            "skipped_missing": self.skipped_missing,
            "failed": self.failed,
            "native_tier_applied": self.native_tier_applied,
            "dry_run": self.dry_run,
            "errors": self.errors,
        }


class RetentionError(Exception):
    """Raised when the retention policy cannot be applied as configured."""


class RetentionService:
    """Move superseded versions to the archive tier. Never delete anything."""

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
            from app.services.storage import build_storage

            self.storage = build_storage(self.settings)

    def cutoff(self, now: datetime | None = None) -> datetime:
        """Versions older than this are eligible for the archive tier."""
        reference = now or datetime.now(UTC)
        return reference - timedelta(days=self.settings.retention_hot_days)

    async def plan(
        self, *, now: datetime | None = None, limit: int = 500
    ) -> list[RetentionCandidate]:
        """Return the versions the policy would archive, without changing them.

        The plan is useful on its own: an administrator can inspect it before
        letting the policy act.
        """
        if self.settings.retention_hot_days < 0:
            raise RetentionError("RETENTION_HOT_DAYS no puede ser negativo")

        threshold = self.cutoff(now)
        result = await self.session.execute(
            select(DocumentVersion)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentVersion.tier == StorageTier.HOT.value,
                DocumentVersion.is_current.is_(False),
                DocumentVersion.created_at < threshold,
                Document.legal_hold.is_(False),
                Document.is_active.is_(True),
            )
            .order_by(DocumentVersion.created_at)
            .limit(limit)
        )
        versions = list(result.scalars().all())

        reference = now or datetime.now(UTC)
        candidates: list[RetentionCandidate] = []
        for version in versions:
            age = (reference - version.created_at).days
            candidates.append(
                RetentionCandidate(
                    version_id=version.id,
                    document_id=version.document_id,
                    storage_key=version.storage_key,
                    sha256=version.sha256,
                    age_days=age,
                    reason=(
                        f"version {version.version_number} superada hace {age} días "
                        f"(umbral {self.settings.retention_hot_days})"
                    ),
                )
            )
        return candidates

    async def apply(
        self,
        *,
        now: datetime | None = None,
        limit: int = 500,
        dry_run: bool = False,
        actor_id: object | None = None,
    ) -> RetentionReport:
        """Archive every eligible version. Nothing is ever deleted."""
        reference = now or datetime.now(UTC)
        report = RetentionReport(dry_run=dry_run)
        report.native_tier_applied = self.storage.supports_native_tiers()

        candidates = await self.plan(now=reference, limit=limit)
        report.examined = len(candidates)
        if dry_run:
            return report

        for candidate in candidates:
            try:
                applied = await self.storage.set_tier(
                    candidate.storage_key,
                    StorageTier.ARCHIVE,
                    expected_sha256=candidate.sha256,
                )
            except StorageError as error:
                report.failed += 1
                report.errors.append(f"{candidate.storage_key}: {error}")
                logger.warning(
                    "No se pudo archivar la versión %s: %s", candidate.version_id, error
                )
                continue

            version = await self.session.get(DocumentVersion, candidate.version_id)
            if version is None:  # pragma: no cover - deleted mid run
                report.skipped_missing += 1
                continue

            before = {"tier": version.tier, "tiered_at": None}
            version.tier = StorageTier.ARCHIVE.value
            version.tiered_at = reference
            self.session.add(
                ChangeLog(
                    entity=RETENTION_ENTITY,
                    entity_id=version.id,
                    field_name="tier",
                    old_value=before["tier"],
                    new_value=StorageTier.ARCHIVE.value,
                    changed_by=actor_id,
                    change_reason=candidate.reason,
                )
            )
            report.archived += 1
            report.archived_keys.append(candidate.storage_key)
            if not applied:
                # Recorded for transparency: the tier is logical on this backend.
                logger.debug(
                    "Tier lógico aplicado a %s: el backend no soporta clases remotas",
                    candidate.storage_key,
                )

        await self.session.flush()
        return report

    async def count_by_tier(self) -> dict[str, int]:
        """Totals per tier, for the administrative dashboard."""
        result = await self.session.execute(
            select(DocumentVersion.tier, DocumentVersion.id).where(
                DocumentVersion.tier.is_not(None)
            )
        )
        totals: dict[str, int] = {}
        for tier, _identifier in result.all():
            key = str(tier)
            totals[key] = totals.get(key, 0) + 1
        return totals

    async def count_legal_holds(self) -> int:
        result = await self.session.execute(
            select(Document.id).where(Document.legal_hold.is_(True))
        )
        return len(list(result.scalars().all()))


__all__ = [
    "RETENTION_ENTITY",
    "RetentionCandidate",
    "RetentionError",
    "RetentionReport",
    "RetentionService",
]
