"""Dashboard response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import Action, Case, Document, Evidence


class DashboardKpis(BaseModel):
    """Counters for the tiles.

    Every field counts rows the caller is allowed to read. There is no
    "total in the firm" figure here on purpose.
    """

    active_clients: int = Field(ge=0, description="Clientes con ficha activa")
    active_cases: int = Field(ge=0, description="Expedientes no cerrados")
    closed_cases: int = Field(ge=0, description="Expedientes cerrados")
    active_lawyers: int = Field(ge=0, description="Abogados activos")
    actions_this_month: int = Field(ge=0, description="Actuaciones del mes en curso")
    upcoming_hearings: int = Field(ge=0, description="Audiencias en el horizonte")
    pending_actions: int = Field(ge=0, description="Actuaciones con paso pendiente")
    open_deadlines: int = Field(ge=0, description="Vencimientos por llegar")
    overdue_deadlines: int = Field(ge=0, description="Vencimientos ya vencidos")
    evidences: int = Field(ge=0, description="Evidencias visibles para el llamante")
    pending_messages: int = Field(ge=0, description="Mensajes sin leer")
    unread_notifications: int = Field(ge=0, description="Notificaciones sin leer")


class DashboardCaseItem(BaseModel):
    id: UUID
    case_number: str
    title: str
    status: str
    priority: str
    client_name: str
    opened_at: str

    @classmethod
    def from_case(cls, case: Case, client_name: str) -> "DashboardCaseItem":
        return cls(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            status=case.status,
            priority=case.priority,
            client_name=client_name,
            opened_at=case.opened_at.isoformat(),
        )


class DashboardHearingItem(BaseModel):
    """A hearing built from the (hearing, event) pair.

    `HearingResponse.from_hearing` walks `hearing.event` and `event.case`. Those
    relationships are lazy, and reading them outside an awaited query raises
    MissingGreenlet, so the dashboard builds its own view from the tuple it
    already selected.
    """

    id: UUID
    event_id: UUID
    case_id: UUID
    title: str
    starts_at: datetime
    status: str
    court: str | None = None
    courtroom: str | None = None
    procedural_stage: str | None = None


class DashboardDeadlineItem(BaseModel):
    source: str
    reference_id: UUID
    case_id: UUID
    title: str
    due_at: datetime
    is_overdue: bool


class DashboardActionItem(BaseModel):
    id: UUID
    case_id: UUID
    action_type: str
    description: str
    occurred_at: datetime
    next_action: str | None = None
    next_action_at: datetime | None = None


class DashboardDocumentItem(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    document_type: str
    status: str
    created_at: datetime

    @classmethod
    def from_document(cls, document: Document) -> "DashboardDocumentItem":
        return cls(
            id=document.id,
            case_id=document.case_id,
            title=document.title,
            document_type=document.document_type,
            status=document.status,
            created_at=document.created_at,
        )


class DashboardEvidenceItem(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    evidence_type: str
    status: str
    created_at: datetime

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "DashboardEvidenceItem":
        return cls(
            id=evidence.id,
            case_id=evidence.case_id,
            title=evidence.title,
            evidence_type=evidence.evidence_type,
            status=evidence.status,
            created_at=evidence.created_at,
        )


class DashboardActionEntry(BaseModel):
    """A recent actuación. Built from the row so no extra query is needed."""

    @classmethod
    def from_action(cls, action: Action) -> "DashboardActionItem":
        return DashboardActionItem(
            id=action.id,
            case_id=action.case_id,
            action_type=action.action_type,
            description=action.description,
            occurred_at=action.occurred_at,
            next_action=action.next_action,
            next_action_at=action.next_action_at,
        )


class DashboardResponse(BaseModel):
    """Everything the caller's dashboard shows, already scoped."""

    view: str = Field(description="administrador, abogado o cliente")
    generated_at: datetime
    kpis: DashboardKpis
    cases: list[DashboardCaseItem] = Field(default_factory=list)
    next_hearing: DashboardHearingItem | None = None
    hearings: list[DashboardHearingItem] = Field(default_factory=list)
    deadlines: list[DashboardDeadlineItem] = Field(default_factory=list)
    recent_actions: list[DashboardActionItem] = Field(default_factory=list)
    documents: list[DashboardDocumentItem] = Field(default_factory=list)
    evidences: list[DashboardEvidenceItem] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    """The header badge counters. Cheap enough to poll."""

    pending_messages: int = Field(ge=0)
    unread_notifications: int = Field(ge=0)


__all__ = [
    "DashboardActionEntry",
    "DashboardActionItem",
    "DashboardCaseItem",
    "DashboardDeadlineItem",
    "DashboardDocumentItem",
    "DashboardEvidenceItem",
    "DashboardHearingItem",
    "DashboardKpis",
    "DashboardResponse",
    "DashboardSummaryResponse",
]