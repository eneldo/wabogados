from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import CalendarEvent, Hearing

EventType = Literal[
    "audiencia",
    "reunion",
    "vencimiento",
    "llamada",
    "cita",
    "recordatorio",
]
EventStatus = Literal["programada", "realizada", "cancelada", "aplazada"]
EventVisibility = Literal["interna", "equipo", "publicada"]
ProceduralStage = Literal[
    "primera_instancia",
    "apelacion",
    "ejecucion",
    "previa",
    "conciliacion",
    "otra",
]
Attendance = Literal["pendiente", "presente", "ausente", "justificada"]
CalendarView = Literal["day", "week", "month", "lawyer", "case"]
HearingStatus = Literal["programada", "realizada", "aplazada", "cancelada", "suspendida"]

HEARING_ONLY_TYPES = ("audiencia",)


class CalendarEventCreate(BaseModel):
    case_id: UUID
    event_type: EventType
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    location: str | None = Field(default=None, max_length=255)
    lawyer_id: UUID | None = None
    visibility: EventVisibility = "interna"
    status: EventStatus = "programada"
    reminder_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 30)

    @model_validator(mode="after")
    def _default_duration(self) -> "CalendarEventCreate":
        if self.event_type in HEARING_ONLY_TYPES:
            raise ValueError("Las audiencias se crean mediante /hearings")
        if self.ends_at is None:
            if self.all_day:
                self.ends_at = self.starts_at + timedelta(days=1)
            else:
                self.ends_at = self.starts_at + timedelta(hours=1)
        return self


class CalendarEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    location: str | None = Field(default=None, max_length=255)
    lawyer_id: UUID | None = None
    visibility: EventVisibility | None = None
    status: EventStatus | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 30)


class HearingCreate(BaseModel):
    case_id: UUID
    title: str = Field(min_length=3, max_length=255)
    starts_at: datetime
    ends_at: datetime | None = None
    lawyer_id: UUID | None = None
    court: str | None = Field(default=None, max_length=200)
    courtroom: str | None = Field(default=None, max_length=100)
    judge: str | None = Field(default=None, max_length=200)
    procedural_stage: ProceduralStage = "primera_instancia"
    file_number: str | None = Field(default=None, max_length=100)
    notified_at: datetime | None = None
    visibility: EventVisibility = "interna"
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class HearingUpdate(BaseModel):
    court: str | None = Field(default=None, max_length=200)
    courtroom: str | None = Field(default=None, max_length=100)
    judge: str | None = Field(default=None, max_length=200)
    procedural_stage: ProceduralStage | None = None
    file_number: str | None = Field(default=None, max_length=100)
    notified_at: datetime | None = None
    attendance: Attendance | None = None
    result: str | None = Field(default=None, max_length=4000)
    status: HearingStatus | None = None


class HearingReschedule(BaseModel):
    starts_at: datetime
    ends_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=1000)


class CalendarEventResponse(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    event_type: EventType
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    location: str | None
    lawyer_id: UUID | None
    lawyer_name: str | None
    visibility: EventVisibility
    status: EventStatus
    reminder_minutes: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_event(cls, event: CalendarEvent) -> "CalendarEventResponse":
        lawyer = event.lawyer
        return cls(
            id=event.id,
            case_id=event.case_id,
            case_number=event.case.case_number if event.case else "",
            event_type=cast(EventType, event.event_type),
            title=event.title,
            description=event.description,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            all_day=event.all_day,
            location=event.location,
            lawyer_id=event.lawyer_id,
            lawyer_name=lawyer.full_name if lawyer else None,
            visibility=cast(EventVisibility, event.visibility),
            status=cast(EventStatus, event.status),
            reminder_minutes=event.reminder_minutes,
            is_active=event.is_active,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )


class HearingResponse(BaseModel):
    id: UUID
    event_id: UUID
    case_id: UUID
    case_number: str
    title: str
    starts_at: datetime
    ends_at: datetime
    status: HearingStatus
    attendance: Attendance
    court: str | None
    courtroom: str | None
    judge: str | None
    procedural_stage: ProceduralStage
    file_number: str | None
    notified_at: datetime | None
    result: str | None
    rescheduled_from_id: UUID | None
    reschedule_count: int
    is_active: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_hearing(cls, hearing: Hearing, reschedule_count: int = 0) -> "HearingResponse":
        event = hearing.event
        return cls(
            id=hearing.id,
            event_id=hearing.event_id,
            case_id=hearing.case_id,
            case_number=event.case.case_number if event and event.case else "",
            title=event.title if event else "",
            starts_at=event.starts_at if event else hearing.updated_at,
            ends_at=event.ends_at if event else hearing.updated_at,
            status=cast(HearingStatus, hearing.status),
            attendance=cast(Attendance, hearing.attendance),
            court=hearing.court,
            courtroom=hearing.courtroom,
            judge=hearing.judge,
            procedural_stage=cast(ProceduralStage, hearing.procedural_stage),
            file_number=hearing.file_number,
            notified_at=hearing.notified_at,
            result=hearing.result,
            rescheduled_from_id=hearing.rescheduled_from_id,
            reschedule_count=reschedule_count,
            is_active=event.is_active if event else False,
            updated_at=hearing.updated_at,
        )


class CalendarViewResponse(BaseModel):
    view: CalendarView
    start: datetime
    end: datetime
    total: int
    events: list[CalendarEventResponse]


class DeadlineItem(BaseModel):
    source: Literal["evento", "actuacion"]
    reference_id: UUID
    case_id: UUID
    case_number: str
    title: str
    due_at: datetime
    overdue: bool
    source_label: str
