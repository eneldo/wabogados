"""Operational metrics for the evidence engine.

MASTER_PROMPT section 43 lists what the system must measure. These figures are
administrator-only: they describe the firm's storage and processing, not a
client's case.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import User
from app.services.observability import storage_health

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics/evidence")
async def evidence_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("metrics:read"))],
) -> dict[str, object]:
    """Evidence count, volumes, saving ratio, failures and storage use."""
    del actor
    return await storage_health(session)


@router.get("/metrics/evidence/derivatives")
async def derivative_breakdown(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("metrics:read"))],
) -> dict[str, object]:
    """Where the derivatives stand, grouped by type.

    Useful when a firm asks why the bucket grew: a single runaway profile shows
    up here immediately.
    """
    del actor
    from sqlalchemy import func, select

    from app.models import EvidenceDerivative

    rows = await session.execute(
        select(
            EvidenceDerivative.derivative_type,
            func.count(),
            func.coalesce(func.sum(EvidenceDerivative.size_bytes), 0),
        ).group_by(EvidenceDerivative.derivative_type)
    )
    # Sorted on the megabyte value before serialising, so the ordering never
    # depends on the dictionary being untyped.
    sized = sorted(
        ((str(kind), int(count), float(total) / (1024 * 1024)) for kind, count, total in rows),
        key=lambda row: row[2],
        reverse=True,
    )
    breakdown = [
        {"derivative_type": kind, "count": count, "size_mb": round(size_mb, 2)}
        for kind, count, size_mb in sized
    ]

    return {"derivatives": breakdown, "total": len(breakdown)}


__all__ = ["derivative_breakdown", "evidence_metrics", "router"]