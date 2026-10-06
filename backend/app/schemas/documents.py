from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import StorageTier
from app.models import Document, DocumentVersion

DocumentType = Literal[
    "contrato",
    "poder",
    "demanda",
    "contestacion",
    "memorial",
    "auto",
    "sentencia",
    "prueba",
    "identificacion",
    "comunicacion",
    "otro",
]
DocumentStatus = Literal["borrador", "vigente", "reemplazado", "anulado"]
Confidentiality = Literal["publico", "interno", "confidencial", "secreto"]
Visibility = Literal["interna", "equipo", "publicada"]


class DocumentCreate(BaseModel):
    case_id: UUID
    document_type: DocumentType
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    confidentiality: Confidentiality = "interno"
    visibility: Visibility = "interna"


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    document_type: DocumentType | None = None
    status: DocumentStatus | None = None
    confidentiality: Confidentiality | None = None
    visibility: Visibility | None = None


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    notes: str | None
    is_current: bool
    tier: str = StorageTier.HOT.value
    tiered_at: datetime | None = None
    created_by: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_version(cls, version: DocumentVersion) -> "DocumentVersionResponse":
        return cls(
            id=version.id,
            document_id=version.document_id,
            version_number=version.version_number,
            original_name=version.original_name,
            mime_type=version.mime_type,
            size_bytes=version.size_bytes,
            sha256=version.sha256,
            notes=version.notes,
            is_current=version.is_current,
            tier=version.tier,
            tiered_at=version.tiered_at,
            created_by=version.created_by,
            created_at=version.created_at,
        )


class DocumentResponse(BaseModel):
    id: UUID
    case_id: UUID
    case_number: str
    document_type: DocumentType
    title: str
    description: str | None
    status: DocumentStatus
    confidentiality: Confidentiality
    visibility: Visibility
    current_version: int | None
    version_count: int
    legal_hold: bool = False
    legal_hold_reason: str | None = None
    legal_hold_at: datetime | None = None
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_document(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            case_id=document.case_id,
            case_number=document.case.case_number if document.case else "",
            document_type=cast(DocumentType, document.document_type),
            title=document.title,
            description=document.description,
            status=cast(DocumentStatus, document.status),
            confidentiality=cast(Confidentiality, document.confidentiality),
            visibility=cast(Visibility, document.visibility),
            current_version=document.current_version,
            version_count=len(document.versions),
            legal_hold=document.legal_hold,
            legal_hold_reason=document.legal_hold_reason,
            legal_hold_at=document.legal_hold_at,
            is_active=document.is_active,
            deleted_at=document.deleted_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class DocumentDetailResponse(DocumentResponse):
    versions: list[DocumentVersionResponse]


class PaginatedDocuments(BaseModel):
    """One page of the global document browser."""

    items: list[DocumentResponse]
    total: int
    skip: int
    limit: int


class DocumentDownloadMetadata(BaseModel):
    """Metadata of an audited download, returned by the version detail view."""

    document_id: UUID
    version_id: UUID
    version_number: int
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str


class LegalHoldUpdate(BaseModel):
    """Activate or release the retention freeze of a document."""

    active: bool
    reason: str | None = Field(default=None, max_length=500)


class RetentionCandidateResponse(BaseModel):
    version_id: UUID
    document_id: UUID
    age_days: int
    reason: str


class RetentionReportResponse(BaseModel):
    """Preview of the retention policy. Read only, changes nothing."""

    hot_days: int
    tiering_enabled: bool
    backend: str
    native_tiers: bool
    total_by_tier: dict[str, int]
    legal_holds: int
    eligible: int
    candidates: list[RetentionCandidateResponse]


class RetentionRunResponse(BaseModel):
    """Result of a retention run. No content is ever deleted."""

    examined: int
    archived: int
    skipped_legal_hold: int
    skipped_current: int
    skipped_missing: int
    failed: int
    native_tier_applied: bool
    dry_run: bool
    errors: list[str]


class IntegrityFindingResponse(BaseModel):
    """`from_attributes` is required: Pydantic does not propagate it to nested models."""

    model_config = ConfigDict(from_attributes=True)

    finding_type: str
    storage_key: str | None
    document_id: UUID | None
    version_id: UUID | None
    expected_sha256: str | None
    actual_sha256: str | None
    detail: str | None


class IntegrityScanResponse(BaseModel):
    """A recorded verification run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mode: str
    status: str
    backend: str
    checked: int
    ok_count: int
    missing_count: int
    corrupted_count: int
    unreadable_count: int
    orphaned_count: int
    check_orphans: bool
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    detail: str | None
    findings: list[IntegrityFindingResponse] = Field(default_factory=list)


class IntegrityReportResponse(BaseModel):
    """Integrity verification history, for an auditor."""

    total_versions: int
    last_scan: IntegrityScanResponse | None
