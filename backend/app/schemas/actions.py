from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Action

ActionType = Literal[
    "reunion",
    "llamada",
    "visita",
    "notificacion",
    "presentacion",
    "diligencia",
    "consulta",
    "seguimiento",
    "otro",
]
ActionVisibility = Literal["interna", "equipo", "publicada"]


class ActionCreate(BaseModel):
    case_id: UUID
    action_type: ActionType
    occurred_at: datetime
    description: str = Field(min_length=3, max_length=4000)
    result: str | None = Field(default=None, max_length=4000)
    responsible_lawyer_id: UUID | None = None
    visibility: ActionVisibility = "interna"
    next_action: str | None = Field(default=None, max_length=1000)
    next_action_at: datetime | None = None

    @model_validator(mode="after")
    def _next_action_has_date(self) -> "ActionCreate":
        if self.next_action_at is not None and not self.next_action:
            raise ValueError("next_action_at requiere next_action")
        return self


class ActionUpdate(BaseModel):
    action_type: ActionType | None = None
    occurred_at: datetime | None = None
    description: str | None = Field(default=None, min_length=3, max_length=4000)
    result: str | None = Field(default=None, max_length=4000)
    responsible_lawyer_id: UUID | None = None
    visibility: ActionVisibility | None = None
    next_action: str | None = Field(default=None, max_length=1000)
    next_action_at: datetime | None = None

    @model_validator(mode="after")
    def _next_action_has_date(self) -> "ActionUpdate":
        if self.next_action_at is not None and not self.next_action:
            raise ValueError("next_action_at requiere next_action")
        return self


class ActionResponse(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    action_type: ActionType
    occurred_at: datetime
    description: str
    result: str | None
    responsible_lawyer_id: UUID | None
    responsible_lawyer_name: str | None
    visibility: ActionVisibility
    next_action: str | None
    next_action_at: datetime | None
    created_by: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_action(cls, action: Action) -> "ActionResponse":
        return cls(
            id=action.id,
            case_id=action.case_id,
            case_number=action.case.case_number if action.case else "",
            action_type=cast(ActionType, action.action_type),
            occurred_at=action.occurred_at,
            description=action.description,
            result=action.result,
            responsible_lawyer_id=action.responsible_lawyer_id,
            responsible_lawyer_name=(
                action.responsible_lawyer.full_name if action.responsible_lawyer else None
            ),
            visibility=cast(ActionVisibility, action.visibility),
            next_action=action.next_action,
            next_action_at=action.next_action_at,
            created_by=action.created_by,
            is_active=action.is_active,
            created_at=action.created_at,
            updated_at=action.updated_at,
        )


class ActionTimelineEntry(BaseModel):
    """Timeline item enriched with what changed on the case around that moment."""

    action: ActionResponse
    case_status: str
    is_pending: bool


class PendingActionResponse(BaseModel):
    action_id: UUID
    case_id: UUID
    case_number: str
    case_title: str
    next_action: str
    next_action_at: datetime
    overdue: bool


class TimelineResponse(BaseModel):
    case_id: UUID
    case_number: str
    total: int
    entries: list[ActionTimelineEntry]
