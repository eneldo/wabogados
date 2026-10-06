"""Administration of runtime settings."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import User
from app.services.settings import SettingsError, SettingsService, decode_value

router = APIRouter(prefix="/admin/settings", tags=["admin"])


class SettingResponse(BaseModel):
    key: str
    value: Any
    raw_value: str = Field(description="Exactly what is stored in the row")
    description: str | None
    category: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class SettingWrite(BaseModel):
    value: Any = Field(description="String, number, boolean or a JSON object")
    description: str | None = None
    category: str = Field(default="general", max_length=50)


def _response(setting: Any) -> SettingResponse:
    return SettingResponse(
        key=setting.key,
        value=decode_value(setting.value),
        raw_value=setting.value,
        description=setting.description,
        category=setting.category,
        updated_at=setting.updated_at.isoformat(),
    )


def _fail(exc: SettingsError) -> HTTPException:
    return HTTPException(
        status_code=HTTP_422_UNPROCESSABLE, detail=str(exc)
    )


@router.get("", response_model=list[SettingResponse])
async def list_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("settings:read"))],
    category: Annotated[str | None, Query(max_length=50)] = None,
) -> list[SettingResponse]:
    settings = await SettingsService(session).list_settings(category=category)
    return [_response(item) for item in settings]


@router.get("/{key}", response_model=SettingResponse)
async def read_setting(
    key: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("settings:read"))],
) -> SettingResponse:
    setting = await SettingsService(session).get(key)
    if setting is None:
        raise HTTPException(status_code=404, detail="El ajuste no existe")
    return _response(setting)


@router.put("/{key}", response_model=SettingResponse)
async def write_setting(
    key: str,
    payload: SettingWrite,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("settings:write"))],
) -> SettingResponse:
    try:
        setting = await SettingsService(session).upsert(
            key,
            payload.value,
            actor,
            description=payload.description,
            category=payload.category,
        )
    except SettingsError as exc:
        raise _fail(exc) from exc
    await session.commit()
    return _response(setting)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    key: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("settings:write"))],
) -> None:
    try:
        await SettingsService(session).delete(key, actor)
    except SettingsError as exc:
        raise _fail(exc) from exc
    await session.commit()


__all__ = [
    "SettingResponse",
    "SettingWrite",
    "delete_setting",
    "list_settings",
    "read_setting",
    "router",
    "write_setting",
]
