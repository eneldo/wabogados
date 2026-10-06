"""Domain constants shared by models, services and schemas.

These live in `core` so that the ORM layer can reference them without importing
from `services`, which would invert the dependency direction.
"""

from enum import StrEnum


class StorageTier(StrEnum):
    """Lifecycle tier of a stored object.

    HOT is served normally and cheaply. ARCHIVE is cheaper to keep and may take
    longer to read, but it stays fully retrievable. Neither tier is
    disposable: the retention policy never deletes content
    (PROJECT_RULES, rule 5).
    """

    HOT = "hot"
    ARCHIVE = "archive"


TIERABLE = (StorageTier.HOT, StorageTier.ARCHIVE)

__all__ = ["TIERABLE", "StorageTier"]
