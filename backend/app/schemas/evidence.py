"""API contracts for the evidence engine."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import Evidence

EvidenceType = Literal[
    "documental", "fotografica", "audiovisual", "testimonial", "pericial", "otra"
]
EvidenceVisibility = Literal["interna", "equipo", "publicada"]
EvidenceConfidentiality = Literal["interno", "confidencial", "restringido"]
EvidenceStatusValue = Literal[
    "uploaded",
    "validating",
    "scanning",
    "processing",
    "optimized",
    "ready",
    "failed",
    "quarantined",
]


class EvidenceCreate(BaseModel):
    """Register an evidence before its file arrives."""

    case_id: UUID
    title: str = Field(min_length=3, max_length=255)
    evidence_type: EvidenceType
    description: str | None = Field(default=None, max_length=4000)
    action_id: UUID | None = None
    visibility: EvidenceVisibility = "interna"
    confidentiality: EvidenceConfidentiality = "interno"
    captured_at: datetime | None = None
    captured_location: str | None = Field(default=None, max_length=255)


class EvidenceUpdate(BaseModel):
    """Only the mutable fields.

    There is deliberately no field for the original hash, the upload date or the
    storage key. MASTER_PROMPT section 24 forbids a user modifying them.
    """

    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    evidence_type: EvidenceType | None = None
    visibility: EvidenceVisibility | None = None
    confidentiality: EvidenceConfidentiality | None = None
    action_id: UUID | None = None
    captured_at: datetime | None = None
    captured_location: str | None = Field(default=None, max_length=255)

    def changes(self) -> dict[str, object]:
        """Only the fields the caller actually sent."""
        return self.model_dump(exclude_unset=True, exclude_none=True)


class EvidenceFileResponse(BaseModel):
    """Metadata of the received original. Never the bytes."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    width: int | None
    height: int | None
    page_count: int | None
    is_original: bool
    is_signed_pdf: bool
    signature_broken: bool
    created_at: datetime


class EvidenceDerivativeResponse(BaseModel):
    """A derived view. Legally it never substitutes the original."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    derivative_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    compression_ratio: float | None
    profile: str | None
    width: int | None
    height: int | None
    page_count: int | None
    created_at: datetime


class EvidenceResponse(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    action_id: UUID | None
    title: str
    description: str | None
    evidence_type: str
    status: str
    visibility: str
    confidentiality: str
    original_filename: str | None
    original_mime_type: str | None
    original_size: int | None
    original_sha256: str | None
    is_signed_pdf: bool
    captured_at: datetime | None
    captured_location: str | None
    derivative_count: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "EvidenceResponse":
        return cls(
            id=evidence.id,
            case_id=evidence.case_id,
            case_number=evidence.case.case_number if evidence.case else "",
            action_id=evidence.action_id,
            title=evidence.title,
            description=evidence.description,
            evidence_type=evidence.evidence_type,
            status=evidence.status,
            visibility=evidence.visibility,
            confidentiality=evidence.confidentiality,
            original_filename=evidence.original_filename,
            original_mime_type=evidence.original_mime_type,
            original_size=evidence.original_size,
            original_sha256=evidence.original_sha256,
            is_signed_pdf=evidence.is_signed_pdf,
            captured_at=evidence.captured_at,
            captured_location=evidence.captured_location,
            derivative_count=len(evidence.derivatives),
            is_active=evidence.is_active,
            created_at=evidence.created_at,
            updated_at=evidence.updated_at,
        )


class EvidenceDetailResponse(EvidenceResponse):
    files: list[EvidenceFileResponse] = Field(default_factory=list)
    derivatives: list[EvidenceDerivativeResponse] = Field(default_factory=list)

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "EvidenceDetailResponse":
        base = EvidenceResponse.from_evidence(evidence)
        detail = cls(**base.model_dump())
        detail.files = [
            EvidenceFileResponse.model_validate(item) for item in evidence.files
        ]
        detail.derivatives = [
            EvidenceDerivativeResponse.model_validate(item)
            for item in evidence.derivatives
        ]
        return detail


class EvidenceUploadResponse(BaseModel):
    """Result of attaching and processing the original."""

    evidence: EvidenceDetailResponse
    derivatives_created: int
    queued: bool
    page_count: int | None = None
    is_signed_pdf: bool = False
    signature_broken: bool = False
    detail: str | None = None


class EvidenceEventResponse(BaseModel):
    """One entry of the chain of custody. Append only."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    from_value: str | None
    to_value: str | None
    detail: str | None
    actor_id: UUID | None
    ip_address: str | None
    created_at: datetime


class EvidenceAccessLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    access_type: str
    user_id: UUID | None
    ip_address: str | None
    created_at: datetime


class EvidenceCustodyResponse(BaseModel):
    """The full custody record: events plus access history."""

    evidence_id: UUID
    original_sha256: str | None
    events: list[EvidenceEventResponse]
    accesses: list[EvidenceAccessLogResponse]


__all__ = [
    "EvidenceAccessLogResponse",
    "EvidenceCreate",
    "EvidenceCustodyResponse",
    "EvidenceDerivativeResponse",
    "EvidenceDetailResponse",
    "EvidenceEventResponse",
    "EvidenceFileResponse",
    "EvidenceResponse",
    "EvidenceUpdate",
    "EvidenceUploadResponse",
]