"""Schemas for the public consultation form.

The seven areas are the ones the firm publishes on wabogados.co. The form and
this module must agree on them exactly: a `Literal` here means an area the site
does not offer is rejected by the API rather than quietly stored as a typo.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import CONSULTATION_STATUSES

#: Written this way in Spanish and matched case-sensitively, because these are
#: the labels the firm already prints on its own pages.
ConsultationArea = Literal[
    "Derecho penal",
    "Ley familiar",
    "Derecho laboral",
    "Derecho constitucional",
    "Derecho civil",
    "Derecho comercial",
    "Asesorías empresariales",
    "Otra consulta",
]

#: The version of the privacy notice shown on the form. Stored on every row so
#: that a later dispute can be answered with the text that was on screen, not
#: with the text that is on screen today.
PRIVACY_NOTICE_VERSION = "2026-10"


class ConsultationCreate(BaseModel):
    """The public payload.

    `consent` and `website` exist to protect the person, not the server:

    - `consent` must be `True`. Declaring consent in the body rather than
      inferring it from the fact that a form was filled in is what makes the
      stored `consent_at` mean anything.
    - `website` is a field a person cannot see. It exists only to be filled in by
      a robot; a human's browser leaves it empty. See `_reject_filled_trap`.

    Note on error bodies: the application's validation handler echoes the
    offending value back inside `input`. That is the sender's own text returning
    to the sender, and nothing of it reaches `audit_logs`, which never reads a
    request body — but it does mean a rejected message can be read in a 422.
    """

    full_name: str = Field(min_length=3, max_length=255)
    phone: str = Field(min_length=6, max_length=50)
    email: EmailStr
    area: ConsultationArea
    message: str = Field(min_length=10, max_length=1500)
    consent: bool
    website: str = Field(default="", max_length=200)

    @field_validator("full_name", "message")
    @classmethod
    def _collapse_whitespace(cls, value: str) -> str:
        """One line, trimmed: a name wrapped across three lines is one name."""

        return " ".join(value.split())

    @field_validator("phone")
    @classmethod
    def _normalise_phone(cls, value: str) -> str:
        """Keep the digits a person can read back over the phone."""

        return " ".join(value.split())

    @field_validator("consent")
    @classmethod
    def _require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "Debe aceptar el aviso de privacidad para enviar la solicitud"
            )
        return value

    @field_validator("website")
    @classmethod
    def _reject_filled_trap(cls, value: str) -> str:
        """Fail exactly as any other invalid field would.

        Returning a success would be a lie to the person, and there is nothing
        else worth leaking: the response is a 422 like any other validation
        failure, and the only thing it reveals is the field name — which the
        sender already knows, because they filled it in.
        """

        if value:
            raise ValueError("Solicitud no válida")
        return value


class ConsultationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    phone: str
    email: EmailStr
    area: str
    message: str
    status: str
    consent_at: datetime
    privacy_notice_version: str
    handled_by: UUID | None
    handled_at: datetime | None
    client_id: UUID | None
    internal_notes: str | None
    created_at: datetime


class ConsultationPublicAck(BaseModel):
    """What the public site is shown after a successful submission.

    It carries a reference and nothing else. The person is told their request
    was recorded, not what the firm thinks of it: returning the stored row would
    echo back the legal problem they just described and prove the request landed
    in a system they know nothing about.
    """

    reference: UUID
    status: str
    message: str


class ConsultationUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=20)
    internal_notes: str | None = Field(default=None, max_length=4000)
    client_id: UUID | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in CONSULTATION_STATUSES:
            raise ValueError(
                "Estado no válido. Use uno de: " + ", ".join(CONSULTATION_STATUSES)
            )
        return value


class PaginatedConsultations(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ConsultationResponse]


__all__ = [
    "CONSULTATION_STATUSES",
    "PRIVACY_NOTICE_VERSION",
    "ConsultationArea",
    "ConsultationCreate",
    "ConsultationPublicAck",
    "ConsultationResponse",
    "ConsultationUpdate",
    "PaginatedConsultations",
]