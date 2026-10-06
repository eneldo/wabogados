from datetime import date, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Case

ProcessType = Literal[
    "civil",
    "penal",
    "laboral",
    "administrativo",
    "comercial",
    "familia",
    "tributario",
    "arbitraje",
    "otro",
]
CaseStatus = Literal["abierto", "en_tramitacion", "suspendido", "cerrado", "archivado"]
CasePriority = Literal["baja", "normal", "alta", "urgente"]
PartyRole = Literal["demandante", "demandado", "contraparte", "tercero"]


class CaseBase(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    client_id: UUID
    process_type: ProcessType
    responsible_lawyer_id: UUID | None = None
    legal_area_id: UUID | None = None
    jurisdiction: str | None = Field(default=None, max_length=150)
    court: str | None = Field(default=None, max_length=200)
    file_number: str | None = Field(default=None, max_length=100)
    priority: CasePriority = "normal"
    opened_at: date = Field(default_factory=date.today)
    description: str | None = Field(default=None, max_length=4000)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=255)
    client_id: UUID | None = None
    responsible_lawyer_id: UUID | None = None
    legal_area_id: UUID | None = None
    process_type: ProcessType | None = None
    jurisdiction: str | None = Field(default=None, max_length=150)
    court: str | None = Field(default=None, max_length=200)
    file_number: str | None = Field(default=None, max_length=100)
    priority: CasePriority | None = None
    description: str | None = Field(default=None, max_length=4000)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)


class CaseCloseRequest(BaseModel):
    closed_at: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=4000)


class CaseResponse(BaseModel):
    id: UUID
    case_number: str
    title: str
    client_id: UUID
    client_name: str
    responsible_lawyer_id: UUID | None
    responsible_lawyer_name: str | None
    legal_area_id: UUID | None
    legal_area_name: str | None
    process_type: ProcessType
    jurisdiction: str | None
    court: str | None
    file_number: str | None
    status: CaseStatus
    priority: CasePriority
    opened_at: date
    closed_at: date | None
    description: str | None
    amount: Decimal | None
    notes: str | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_case(cls, case: Case) -> "CaseResponse":
        """Build the response joining the client, lawyer and legal area names."""
        return cls(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            client_id=case.client_id,
            client_name=case.client.display_name if case.client else "",
            responsible_lawyer_id=case.responsible_lawyer_id,
            responsible_lawyer_name=(
                case.responsible_lawyer.full_name if case.responsible_lawyer else None
            ),
            legal_area_id=case.legal_area_id,
            legal_area_name=case.legal_area.name if case.legal_area else None,
            process_type=cast(ProcessType, case.process_type),
            jurisdiction=case.jurisdiction,
            court=case.court,
            file_number=case.file_number,
            status=cast(CaseStatus, case.status),
            priority=cast(CasePriority, case.priority),
            opened_at=case.opened_at,
            closed_at=case.closed_at,
            description=case.description,
            amount=case.amount,
            notes=case.notes,
            is_active=case.is_active,
            deleted_at=case.deleted_at,
            created_at=case.created_at,
            updated_at=case.updated_at,
        )


class PaginatedCases(BaseModel):
    items: list[CaseResponse]
    total: int
    skip: int
    limit: int


class CaseAssignmentRequest(BaseModel):
    lawyer_id: UUID


class CasePartyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    party_role: PartyRole
    client_id: UUID | None = None
    document_type: str | None = Field(default=None, max_length=20)
    document_number: str | None = Field(default=None, max_length=50)
    is_external: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("is_external")
    @classmethod
    def _external_flag(cls, value: bool) -> bool:
        return value


class CasePartyResponse(BaseModel):
    id: UUID
    case_id: UUID
    client_id: UUID | None
    name: str
    party_role: PartyRole
    document_type: str | None
    document_number: str | None
    is_external: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseLawyerResponse(BaseModel):
    lawyer_id: UUID
    lawyer_name: str
    role: str
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("lawyer_name", mode="before")
    @classmethod
    def _lawyer_name(cls, value: object) -> str:
        lawyer = getattr(value, "lawyer", value)
        return str(getattr(lawyer, "full_name", lawyer))


class CaseCollaboratorResponse(BaseModel):
    lawyer_id: UUID
    lawyer_name: str
    role: str
    assigned_at: datetime

    @field_validator("lawyer_name", mode="before")
    @classmethod
    def _from_assignment(cls, value: object) -> str:
        lawyer = getattr(value, "lawyer", None)
        return str(getattr(lawyer, "full_name", value))


class CaseSection(BaseModel):
    available: bool
    items: list[dict[str, object]] = Field(default_factory=list)


class Case360Response(BaseModel):
    """Ficha 360°.

    Sections from later phases are declared but still empty so the frontend can
    render the full tab structure without backend support.
    """

    case: CaseResponse
    collaborators: list[CaseCollaboratorResponse]
    parties: list[CasePartyResponse]
    history_entries: int
    actuaciones: CaseSection
    actuaciones_total: int
    agenda: CaseSection
    agenda_total: int
    audiencias: CaseSection
    audiencias_total: int
    documentos: CaseSection
    documentos_total: int
    evidencias: CaseSection
    evidencias_total: int
    tareas: CaseSection
    mensajes: CaseSection
