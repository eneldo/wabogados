"""Runtime settings stored in the database.

MASTER_PROMPT section 37 lists `system_settings`. It holds values an
administrator must be able to change while the system runs, without a
redeploy.

**Not a place for secrets.** Every row here is readable by any administrator,
is included in `pg_dump`, and its previous value is written to `change_logs`.
A password stored as a setting would therefore end up in every backup and every
audit trail. `reject_credential_keys` refuses those writes up front.
"""

import json
import logging
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting, User
from app.services.history import record_changes

logger = logging.getLogger(__name__)

SETTING_ENTITY = "system_settings"

#: Keys are lowercase, digits, dots and underscores: `retention.default_days`.
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")

#: A value longer than this is a mistake or an attempt to smuggle a payload.
MAX_VALUE_LENGTH = 8000

#: Any key that smells like a credential is refused rather than stored.
FORBIDDEN_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
    "session_key",
    "encryption_key",
)

TRACKED_SETTING_FIELDS = ("value", "description", "category")


class SettingsError(Exception):
    """Raised when a setting violates a rule."""


def reject_credential_keys(key: str) -> None:
    """Refuse a key that looks like it holds a secret.

    This is a blunt instrument on purpose. It would be easy to store a secret
    under an innocent name, so the real guarantee is the one in the module
    docstring: secrets live in the environment. This check catches the obvious
    mistake, which is the mistake that actually happens.
    """
    lowered = key.lower()
    if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
        raise SettingsError(
            "Un ajuste no puede contener credenciales: use el entorno o un "
            "gestor de secretos"
        )


def validate_key(key: str) -> str:
    if not KEY_PATTERN.match(key):
        raise SettingsError(
            "Clave inválida: use minúsculas, dígitos, punto, guion o guion bajo"
        )
    return key


def encode_value(value: Any) -> str:
    """Store structured values as JSON and leave plain strings alone."""
    if isinstance(value, str):
        if len(value) > MAX_VALUE_LENGTH:
            raise SettingsError("El valor es demasiado largo")
        return value
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(encoded) > MAX_VALUE_LENGTH:
        raise SettingsError("El valor es demasiado largo")
    return encoded


def decode_value(raw: str) -> Any:
    """Return the JSON value, or the original string when it is not JSON."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_settings(
        self, *, category: str | None = None
    ) -> list[SystemSetting]:
        statement = select(SystemSetting).order_by(
            SystemSetting.category, SystemSetting.key
        )
        if category is not None:
            statement = statement.where(SystemSetting.category == category)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get(self, key: str) -> SystemSetting | None:
        return await self.session.get(SystemSetting, validate_key(key))

    async def get_value(self, key: str, default: Any = None) -> Any:
        """Read a value with its type restored, or `default` when unset."""
        setting = await self.get(key)
        return default if setting is None else decode_value(setting.value)

    async def upsert(
        self,
        key: str,
        value: Any,
        actor: User,
        *,
        description: str | None = None,
        category: str = "general",
    ) -> SystemSetting:
        validate_key(key)
        reject_credential_keys(key)
        encoded = encode_value(value)

        setting = await self.session.get(SystemSetting, key)
        if setting is None:
            setting = SystemSetting(
                key=key, value=encoded, description=description, category=category
            )
            setting.updated_by = actor.id
            self.session.add(setting)
            await self.session.flush()
            record_changes(
                self.session,
                entity=SETTING_ENTITY,
                entity_id=_key_as_id(key),
                before={},
                after={"value": encoded, "category": category},
                changed_by=actor.id,
                fields=TRACKED_SETTING_FIELDS,
                reason="Ajuste creado",
            )
            await self.session.flush()
            return setting

        before = {
            "value": setting.value,
            "description": setting.description,
            "category": setting.category,
        }
        setting.value = encoded
        if description is not None:
            setting.description = description
        setting.category = category
        setting.updated_by = actor.id
        await self.session.flush()

        record_changes(
            self.session,
            entity=SETTING_ENTITY,
            entity_id=_key_as_id(key),
            before=before,
            after={
                "value": setting.value,
                "description": setting.description,
                "category": setting.category,
            },
            changed_by=actor.id,
            fields=TRACKED_SETTING_FIELDS,
            reason="Ajuste modificado",
        )
        await self.session.flush()
        # `updated_at` is `onupdate=func.now()`, a server-side expression: after an
        # UPDATE the ORM cannot know its new value, so the attribute is left expired
        # and reading it triggers a lazy load. The router serialises the response
        # from a plain function, outside the greenlet, and that lazy load is an
        # await in the wrong place: `MissingGreenlet`, a 500, and a setting that
        # changed while the screen says it failed. An INSERT returns its columns,
        # which is why only this branch needs it.
        await self.session.refresh(setting)
        return setting

    async def delete(self, key: str, actor: User) -> None:
        """Remove a setting. Not legal data, so a hard delete is acceptable.

        The previous value still reaches `change_logs`, so the change remains
        recoverable even though the row is gone.
        """
        validate_key(key)
        setting = await self.session.get(SystemSetting, key)
        if setting is None:
            raise SettingsError("El ajuste no existe")

        await self.session.delete(setting)
        await self.session.flush()
        record_changes(
            self.session,
            entity=SETTING_ENTITY,
            entity_id=_key_as_id(key),
            before={"value": setting.value, "category": setting.category},
            # The new value of every tracked field is "absent". `record_changes`
            # skips a field whose value did not change, so passing an empty
            # `after` would record nothing at all and a deletion would leave no
            # trace whatsoever.
            after={"value": None, "description": None, "category": None},
            changed_by=actor.id,
            fields=TRACKED_SETTING_FIELDS,
            reason="Ajuste eliminado",
        )
        await self.session.flush()


def _key_as_id(key: str) -> UUID:
    """Settings are keyed by text, but the audit trail wants a UUID.

    A UUIDv5 derived from the key keeps the identifier stable across updates,
    so the audit entries of one setting group together.
    """
    return uuid5(NAMESPACE_URL, f"wabogados/setting/{key}")


__all__ = [
    "FORBIDDEN_KEY_PARTS",
    "KEY_PATTERN",
    "MAX_VALUE_LENGTH",
    "SETTING_ENTITY",
    "SettingsError",
    "SettingsService",
    "decode_value",
    "encode_value",
    "reject_credential_keys",
    "validate_key",
]