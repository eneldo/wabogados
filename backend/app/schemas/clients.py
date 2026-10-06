from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

ClientType = Literal["natural", "juridica"]

#: `NIF` was missing and it broke the whole module, not just one record:
#: `GET /clients` serialises every row through `ClientResponse`, so a single
#: client carrying a `NIF` made the **list** answer 500 for every caller. That is
#: a seed script writing a value the schema then refused to read back.
#:
#: It is a real Colombian identification number, so it belongs here rather than in
#: the seed. Note that `DNI` is the Argentine document; Colombian practice calls a
#: citizen's identity card `CC`, and that is a naming question for the firm, not a
#: silent change to make mid-migration.
DocumentType = Literal["DNI", "CC", "NIF", "RUC", "CE", "PASSPORT", "OTROS"]


class ClientBase(BaseModel):
    document_type: DocumentType
    document_number: str = Field(min_length=3, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class ClientCreate(ClientBase):
    client_type: ClientType
    full_name: str | None = Field(default=None, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    commercial_name: str | None = Field(default=None, max_length=255)
    user_id: UUID | None = None

    @model_validator(mode="after")
    def _require_identity_name(self) -> "ClientCreate":
        if self.client_type == "natural" and not (self.full_name or "").strip():
            raise ValueError("Una persona natural requiere full_name")
        if self.client_type == "juridica" and not (
            (self.legal_name or "").strip() or (self.commercial_name or "").strip()
        ):
            raise ValueError("Una persona jurídica requiere legal_name o commercial_name")
        return self


class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    commercial_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    user_id: UUID | None = None


class ClientResponse(BaseModel):
    id: UUID
    client_type: ClientType
    document_type: DocumentType
    document_number: str
    full_name: str | None
    legal_name: str | None
    commercial_name: str | None
    display_name: str
    email: str | None
    phone: str | None
    address: str | None
    notes: str | None
    user_id: UUID | None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedClients(BaseModel):
    items: list[ClientResponse]
    total: int
    skip: int
    limit: int


class ChangeLogResponse(BaseModel):
    id: UUID
    entity: str
    entity_id: UUID
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
