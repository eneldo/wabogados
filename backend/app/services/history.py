"""Field level history recorder shared by the business modules.

MASTER_PROMPT requires the modification history of legal records. Storing it
once keeps the audit trail queryable without duplicating tables per entity.
"""

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog

TRACKED_CLIENT_FIELDS = (
    "full_name",
    "legal_name",
    "commercial_name",
    "email",
    "phone",
    "address",
    "notes",
    "user_id",
)


def stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def record_changes(
    session: AsyncSession,
    *,
    entity: str,
    entity_id: UUID,
    before: dict[str, Any],
    after: dict[str, Any],
    changed_by: UUID | None,
    fields: Iterable[str] = TRACKED_CLIENT_FIELDS,
    reason: str | None = None,
) -> list[ChangeLog]:
    """Persist one entry per modified field, ignoring unchanged values.

    `reason` explains a change nobody ordered, such as the retention policy
    archiving a version. A trail that says "tier: hot -> archive" without a
    reason cannot be explained to an auditor months later.
    """
    entries: list[ChangeLog] = []
    for field in fields:
        if field not in after:
            continue
        old_value = stringify(before.get(field))
        new_value = stringify(after.get(field))
        if old_value == new_value:
            continue
        entry = ChangeLog(
            entity=entity,
            entity_id=entity_id,
            field_name=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            change_reason=reason,
        )
        session.add(entry)
        entries.append(entry)
    return entries
