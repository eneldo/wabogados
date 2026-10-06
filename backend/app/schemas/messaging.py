"""API contracts for messaging."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ConversationTypeValue = Literal["interna", "cliente"]
ConversationStatusValue = Literal["abierto", "cerrado"]


class ConversationCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    conversation_type: ConversationTypeValue = "interna"
    case_id: UUID | None = None
    client_id: UUID | None = None
    participant_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("subject")
    @classmethod
    def clean_subject(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("El asunto debe tener al menos 3 caracteres")
        return cleaned

    @field_validator("participant_ids")
    @classmethod
    def unique_participants(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class ConversationUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    status: ConversationStatusValue | None = None

    @field_validator("subject")
    @classmethod
    def clean_optional_subject(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("El asunto no puede ser nulo")
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("El asunto debe tener al menos 3 caracteres")
        return cleaned

    @field_validator("status")
    @classmethod
    def status_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("El estado no puede ser nulo")
        return value


class ConversationResponse(BaseModel):
    id: UUID
    subject: str
    conversation_type: str
    status: str
    case_id: UUID | None
    case_number: str | None = None
    client_id: UUID | None
    message_count: int
    unread: int = 0
    last_message_preview: str | None
    last_message_at: datetime | None
    participant_count: int = 0
    created_at: datetime
    updated_at: datetime


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    role: str
    joined_at: datetime
    last_read_at: datetime | None
    is_muted: bool


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID | None
    sender_name: str
    body: str
    is_system: bool
    sent_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    attachments: list[MessageAttachmentResponse] = Field(default_factory=list)


class ThreadResponse(BaseModel):
    """A conversation with its messages, newest page first when paginated."""

    conversation: ConversationResponse
    participants: list[ParticipantResponse]
    messages: list[MessageResponse]
    unread: int = 0


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_type: str
    title: str
    body: str | None
    entity: str | None
    entity_id: UUID | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class UnreadSummaryResponse(BaseModel):
    """Feeds the dashboards: pending messages and notifications."""

    unread_messages: int
    unread_notifications: int


class ParticipantOptionResponse(BaseModel):
    id: UUID
    display_name: str
    account_type: Literal["personal", "cliente"]
    client_id: UUID | None = None


__all__ = [
    "ConversationCreate",
    "ConversationResponse",
    "ConversationUpdate",
    "MessageAttachmentResponse",
    "MessageCreate",
    "MessageResponse",
    "NotificationResponse",
    "ParticipantOptionResponse",
    "ParticipantResponse",
    "ThreadResponse",
    "UnreadSummaryResponse",
]
