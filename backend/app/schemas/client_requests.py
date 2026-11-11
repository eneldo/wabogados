from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RequestType = Literal["documento", "informacion", "tarea"]
RequestStatus = Literal["pendiente", "respondida", "revisada", "cancelada"]
RequestPriority = Literal["normal", "alta", "urgente"]


class ClientRequestBase(BaseModel):
    request_type: RequestType
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    priority: RequestPriority = "normal"
    due_at: datetime | None = None


class ClientRequestCreate(ClientRequestBase):
    pass


class ClientRequestUpdate(BaseModel):
    request_type: RequestType | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    due_at: datetime | None = None
    review_note: str | None = Field(default=None, max_length=2000)


class ClientRequestRespond(BaseModel):
    response_text: str = Field(min_length=1, max_length=4000)


class ClientRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    case_number: str | None = None
    case_title: str | None = None
    client_id: UUID
    request_type: str
    title: str
    description: str | None
    status: str
    priority: str
    due_at: datetime | None
    requested_by: UUID | None
    requested_by_name: str | None = None
    response_text: str | None
    responded_at: datetime | None
    responded_by: UUID | None
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    review_note: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
