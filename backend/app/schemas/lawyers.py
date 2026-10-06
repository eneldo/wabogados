from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import LegalArea

LawyerStatus = Literal["activo", "inactivo", "suspendido"]

#: Mirrors `app.schemas.clients.DocumentType`. The two lists drifted once and the
#: drift was invisible until a lawyer record failed to serialise; they are kept
#: identical deliberately, and `test_hardening` asserts that they stay so.
DocumentType = Literal["DNI", "CC", "NIF", "RUC", "CE", "PASSPORT", "OTROS"]


class LawyerBase(BaseModel):
    document_type: DocumentType
    document_number: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=3, max_length=255)
    professional_card: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    specialties: list[str] = Field(default_factory=list, max_length=20)
    status: LawyerStatus = "activo"
    photo_url: str | None = Field(default=None, max_length=500)
    legal_area_ids: list[UUID] = Field(default_factory=list)
    user_id: UUID | None = None

    @field_validator("specialties")
    @classmethod
    def _clean_specialties(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Las especialidades no pueden estar repetidas")
        return cleaned


class LawyerCreate(LawyerBase):
    pass


class LawyerUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    professional_card: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    specialties: list[str] | None = Field(default=None, max_length=20)
    status: LawyerStatus | None = None
    photo_url: str | None = Field(default=None, max_length=500)
    legal_area_ids: list[UUID] | None = None
    user_id: UUID | None = None


class LawyerResponse(BaseModel):
    id: UUID
    document_type: DocumentType
    document_number: str
    full_name: str
    professional_card: str | None
    email: str | None
    phone: str | None
    specialties: list[str]
    status: LawyerStatus
    photo_url: str | None
    user_id: UUID | None
    legal_areas: list[str]
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("legal_areas", mode="before")
    @classmethod
    def _flatten_areas(cls, value: object) -> object:
        if isinstance(value, list) and value and isinstance(value[0], LegalArea):
            return [area.name for area in value]
        return value


class PaginatedLawyers(BaseModel):
    items: list[LawyerResponse]
    total: int
    skip: int
    limit: int


class LegalAreaResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
