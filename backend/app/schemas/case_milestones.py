from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MilestoneStatus = Literal["pendiente", "en_curso", "completado"]


class CaseMilestoneCreate(BaseModel):
    stage_key: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    status: MilestoneStatus = "pendiente"
    planned_at: datetime | None = None
    completed_at: datetime | None = None
    is_published: bool = False
    sort_order: int = 0


class CaseMilestoneUpdate(BaseModel):
    stage_key: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    status: MilestoneStatus | None = None
    planned_at: datetime | None = None
    completed_at: datetime | None = None
    is_published: bool | None = None
    sort_order: int | None = None


class CaseMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    stage_key: str
    title: str
    description: str | None
    status: str
    planned_at: datetime | None
    completed_at: datetime | None
    is_published: bool
    published_at: datetime | None
    sort_order: int
    created_at: datetime
    updated_at: datetime
