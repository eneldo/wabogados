from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.constants import StorageTier


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class User(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary="user_roles", back_populates="users", lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", lazy="selectin"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary="role_permissions", back_populates="roles", lazy="selectin"
    )
    users: Mapped[list["User"]] = relationship(
        "User", secondary="user_roles", back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary="role_permissions", back_populates="permissions", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name})>"


class UserRole(TimestampMixin, Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_user_roles_user_id", "user_id"),
        Index("ix_user_roles_role_id", "role_id"),
    )


class RolePermission(TimestampMixin, Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_role_permissions_role_id", "role_id"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )


class RefreshToken(TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User | None"] = relationship(
        "User", back_populates="refresh_tokens"
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(user_id={self.user_id}, revoked={self.revoked_at is not None})>"


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False, default="success")

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs", lazy="selectin")

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_entity_entity_id", "entity", "entity_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, entity={self.entity})>"


class ChangeLog(Base):
    """Field level history shared by every business module.

    MASTER_PROMPT requires registering the modification history of legal
    records, so the trail is stored once instead of per entity.
    """

    __tablename__ = "change_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Why the change happened. Essential for automated changes such as the
    # retention policy, where nobody clicked anything.
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_change_logs_entity_entity_id", "entity", "entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChangeLog(entity={self.entity}, "
            f"entity_id={self.entity_id}, field={self.field_name})>"
        )


class Client(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commercial_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "document_type", "document_number", name="uq_client_document"
        ),
        Index("ix_clients_type_status", "client_type", "is_active"),
    )

    @property
    def display_name(self) -> str:
        if self.client_type == "juridica":
            return self.legal_name or self.commercial_name or self.document_number
        return self.full_name or self.document_number

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, type={self.client_type}, document={self.document_number})>"


class LegalArea(TimestampMixin, Base):
    __tablename__ = "legal_areas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<LegalArea(name={self.name})>"


lawyer_legal_areas_table = Table(
    "lawyer_legal_areas",
    Base.metadata,
    Column(
        "lawyer_id",
        PG_UUID(as_uuid=True),
        ForeignKey("lawyers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "legal_area_id",
        PG_UUID(as_uuid=True),
        ForeignKey("legal_areas.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class Lawyer(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "lawyers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    professional_card: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    specialties: Mapped[list[str]] = mapped_column(
        ARRAY(String(150)), default=list, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="activo", nullable=False, index=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    legal_areas: Mapped[list["LegalArea"]] = relationship(
        "LegalArea", secondary=lawyer_legal_areas_table, lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("document_type", "document_number", name="uq_lawyer_document"),
    )

    def __repr__(self) -> str:
        return f"<Lawyer(id={self.id}, name={self.full_name}, status={self.status})>"


class Action(TimestampMixin, SoftDeleteMixin, Base):
    """Actuación registrada sobre un expediente. Alimenta la timeline."""

    __tablename__ = "actions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_lawyer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lawyers.id", ondelete="SET NULL"), nullable=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="interna", nullable=False, index=True
    )
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case"] = relationship("Case", lazy="selectin")
    responsible_lawyer: Mapped["Lawyer | None"] = relationship("Lawyer", lazy="selectin")

    __table_args__ = (
        Index("ix_actions_case_occurred", "case_id", "occurred_at"),
        Index("ix_actions_case_visibility", "case_id", "visibility"),
    )

    def __repr__(self) -> str:
        return (
            f"<Action(case_id={self.case_id}, "
            f"type={self.action_type}, visibility={self.visibility})>"
        )


class CalendarEvent(TimestampMixin, SoftDeleteMixin, Base):
    """Agenda entry. Always tied to a case so access scope is unambiguous."""

    __tablename__ = "calendar_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lawyer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lawyers.id", ondelete="SET NULL"), nullable=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="interna", nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="programada", nullable=False, index=True
    )
    reminder_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    hearing: Mapped["Hearing | None"] = relationship(
        "Hearing", back_populates="event", lazy="selectin", uselist=False
    )
    lawyer: Mapped["Lawyer | None"] = relationship("Lawyer", lazy="selectin")
    case: Mapped["Case"] = relationship("Case", lazy="selectin")

    __table_args__ = (
        Index("ix_calendar_events_case_start", "case_id", "starts_at"),
        Index("ix_calendar_events_lawyer_start", "lawyer_id", "starts_at"),
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent(type={self.event_type}, starts_at={self.starts_at})>"


class Hearing(Base):
    """Specialised data for a hearing, the only event type that carries it."""

    __tablename__ = "hearings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    court: Mapped[str | None] = mapped_column(String(200), nullable=True)
    courtroom: Mapped[str | None] = mapped_column(String(100), nullable=True)
    judge: Mapped[str | None] = mapped_column(String(200), nullable=True)
    procedural_stage: Mapped[str] = mapped_column(
        String(30), default="primera_instancia", nullable=False, index=True
    )
    file_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attendance: Mapped[str] = mapped_column(
        String(20), default="pendiente", nullable=False
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="programada", nullable=False, index=True
    )
    rescheduled_from_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hearings.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    event: Mapped["CalendarEvent"] = relationship(
        "CalendarEvent", back_populates="hearing", lazy="joined"
    )

    __table_args__ = (
        Index("ix_hearings_case_status", "case_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Hearing(case_id={self.case_id}, status={self.status})>"


class Document(TimestampMixin, SoftDeleteMixin, Base):
    """Logical document. Its file content lives in immutable versions."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="vigente", nullable=False, index=True
    )
    confidentiality: Mapped[str] = mapped_column(
        String(20), default="interno", nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="interna", nullable=False, index=True
    )
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # A legal hold freezes the retention policy for this document: no version is
    # moved between tiers while it is active (PROJECT_RULES, rule 5).
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legal_hold_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        lazy="selectin",
        order_by="DocumentVersion.version_number",
    )
    case: Mapped["Case"] = relationship("Case", lazy="selectin")

    __table_args__ = (Index("ix_documents_case_status", "case_id", "status"),)

    def __repr__(self) -> str:
        return f"<Document(title={self.title}, type={self.document_type})>"


class IntegrityFinding(Base):
    """A single problem found by an integrity verification run.

    Only problems are stored. A clean run produces no rows, which keeps the
    table small and makes "how many problems do we have" a single count.
    """

    __tablename__ = "integrity_findings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("integrity_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=True,
    )
    expected_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scan: Mapped["IntegrityScan"] = relationship("IntegrityScan", back_populates="findings")


class IntegrityScan(Base):
    """One execution of the bucket integrity verification.

    Kept as a record because a law firm has to be able to show that verification
    actually happened, and when, and with what result.
    """

    __tablename__ = "integrity_scans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    backend: Mapped[str] = mapped_column(String(50), nullable=False)
    checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ok_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    corrupted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unreadable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orphaned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    check_orphans: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    findings: Mapped[list["IntegrityFinding"]] = relationship(
        "IntegrityFinding",
        back_populates="scan",
        lazy="selectin",
        order_by="IntegrityFinding.finding_type",
    )


class Conversation(Base, TimestampMixin, SoftDeleteMixin):
    """A thread of messages, optionally linked to a case and to a client.

    The ``conversation_type`` is the security boundary, not a label. A client
    only ever sees ``cliente`` conversations whose ``client_id`` is their own
    client record. An ``interna`` conversation has no client participants at
    all and is invisible to the portal.
    """

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    client_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_type: Mapped[str] = mapped_column(
        String(20), default="interna", nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="abierto", nullable=False, index=True
    )
    # A message addressed to the client but not yet acknowledged by them.
    awaiting_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_message_preview: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case | None"] = relationship("Case", lazy="selectin")
    participants: Mapped[list["ConversationParticipant"]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class ConversationParticipant(Base):
    """Membership and read state. One row per person in a conversation."""

    __tablename__ = "conversation_participants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="miembro", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Messages sent after this instant are unread for this participant.
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="participants"
    )

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
    )


class Message(Base):
    """A single message. Soft deleted so the thread keeps its shape."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Set for messages the platform posts, not a person.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # Python side, not only server_default: in PostgreSQL now() is the
        # transaction timestamp, so every message written inside one request
        # would share an instant and the thread order would be arbitrary.
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MessageAttachment(Base):
    """A file sent inside a message.

    Chat attachments are not evidence: they carry no probative guarantee and no
    immutability promise. They are validated and hashed so a tampered file can be
    detected, and they are never executed or rendered inline.
    """

    __tablename__ = "message_attachments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Notification(Base):
    """An in product notification for one user."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Evidence(Base, TimestampMixin, SoftDeleteMixin):
    """Logical evidence record. Its bytes live in immutable files.

    Every evidence belongs to at least one case (MASTER_PROMPT rule 5) and may
    optionally be linked to an action.
    """

    __tablename__ = "evidences"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded", nullable=False, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="interna", nullable=False, index=True
    )
    confidentiality: Mapped[str] = mapped_column(
        String(20), default="interno", nullable=False, index=True
    )
    # Snapshot of the chain of custody, denormalised for the list view.
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    original_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    captured_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set when the source file carried a digital signature. A signed PDF is
    # never modified as an original (MASTER_PROMPT rule 15).
    is_signed_pdf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    case: Mapped["Case"] = relationship("Case", lazy="selectin")
    action: Mapped["Action | None"] = relationship("Action", lazy="selectin")
    files: Mapped[list["EvidenceFile"]] = relationship(
        "EvidenceFile",
        back_populates="evidence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    derivatives: Mapped[list["EvidenceDerivative"]] = relationship(
        "EvidenceDerivative",
        back_populates="evidence",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class EvidenceFile(Base):
    """The received original. Immutable once written (MASTER_PROMPT rule 7).

    There is exactly one original per evidence. No column of this table is
    writable through the API: no hash, no upload date, no storage key.
    """

    __tablename__ = "evidence_files"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_original: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_signed_pdf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # True when a signature exists but no longer covers the whole file, which
    # means the document was modified after being signed.
    signature_broken: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="files")

    __table_args__ = (
        # "At most one original per evidence", enforced by the database rather
        # than by application code. The predicate is what makes this correct: a
        # plain UNIQUE(evidence_id, is_original) would also cap non original
        # rows at one per evidence.
        Index(
            "uq_evidence_single_original",
            "evidence_id",
            unique=True,
            postgresql_where=text("is_original"),
        ),
    )


class EvidenceDerivative(Base):
    """A derived view of an evidence. Never legally substitutes the original."""

    __tablename__ = "evidence_derivatives"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidence_files.id", ondelete="CASCADE"),
        nullable=True,
    )
    derivative_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    compression_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    profile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="derivatives")


class EvidenceProcessingJob(Base):
    """A unit of processing work. Large files wait here for a worker."""

    __tablename__ = "evidence_processing_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceAccessLog(Base):
    """Every download and view of an evidence. Mandatory for the original."""

    __tablename__ = "evidence_access_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidence_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MediaAccessLog(Base):
    """Every download or playback of a media resource.

    The media library served its bytes with no record of who asked, while the
    evidence chain of custody recorded every single read. A recording of a
    conversation, a signature image or a photo of a document is exactly the kind of
    material that ends up in a dispute about what was shown and when, so the
    download path now writes here.

    Append only, like `evidence_events`: a trail that can be edited is not a trail.
    """

    __tablename__ = "media_access_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: How many bytes this request actually served. A `Range` request serves a slice,
    #: and recording the whole file would overstate it.
    bytes_served: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceEvent(Base):
    """Chain of custody: an append only record of what happened to an evidence.

    Nothing updates these rows. That is the point: the trail cannot be edited,
    only appended to.
    """

    __tablename__ = "evidence_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    from_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentVersion(Base):
    """Immutable file revision. Content is never modified once written."""

    __tablename__ = "document_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tier: Mapped[str] = mapped_column(
        String(20), default=StorageTier.HOT.value, nullable=False, index=True
    )
    tiered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentVersion(document_id={self.document_id}, "
            f"version={self.version_number}, sha256={self.sha256[:8]})>"
        )


class DocumentDownload(Base):
    """Audit trail of every file download, required by MASTER_PROMPT."""

    __tablename__ = "document_downloads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DocumentDownload(document_id={self.document_id})>"


class SystemSetting(TimestampMixin, Base):
    """Key/value settings that live in the database rather than the environment.

    MASTER_PROMPT section 37 requires the table. It exists for values an
    administrator must change while the system runs, without a redeploy and
    without editing a container environment: retention policy switches, the
    maintenance notice shown on the status page, a hold on evidence processing.

    It is deliberately **not** a place to keep secrets. Anything credential
    belongs in `.env`; a setting row is readable by every administrator and is
    included in backups, so a password written here would be copied to every
    backup and printed in every audit trail.
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    #: Free-form value. Kept as text so callers decide how to interpret it.
    value: Mapped[str] = mapped_column(Text, nullable=False)
    #: What the setting is for, shown in the administration screen.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Optional grouping so the list is not a flat wall of keys.
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    #: Changing a setting is audited; this records who last did it.
    updated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SystemSetting(key={self.key!r})>"


class MediaItem(TimestampMixin, SoftDeleteMixin, Base):
    """One asset of the firm's multimedia library (MASTER_PROMPT V4).

    A library of the firm's own material: an inspection recording, a photograph of
    a site, an audio note. It is **internal** — nothing here is published to the
    portal, which is why no row carries a visibility column and the client role
    holds no permission on the resource.

    **It is not an evidence.** Evidence is a legal record with an immutable
    original, a custody chain and a retention policy (section 28), and this table
    touches none of that: one file, replaced in place when it is corrected, and no
    derivative. A recording that belongs to a case is registered *as evidence*, and
    a copy filed here for convenience is a working material.

    That separation is the reason this module could be built without reopening
    `EVIDENCE_MIME_TYPES`: a legal record keeps its own, narrower contract.

    `case_id` is nullable on purpose. Most of the library is firm material that
    belongs to no expediente — a template, a recording of the firm's own premises —
    and forcing a case would mean inventing one. When it is filled, the row is
    simply about that case.
    """

    __tablename__ = "media_items"
    __table_args__ = (
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_media_size"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: `video`, `image`, `audio` or `document`. Decided by the detected MIME type,
    #: never by the extension the browser offered.
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    #: `activo` or `archivado`. Separate from `is_active`, which is the record of a
    #: deactivation, exactly as in documents.
    status: Mapped[str] = mapped_column(String(20), default="activo", nullable=False, index=True)
    #: `interno`, `restringido` or `confidencial`. Read by the screen to warn
    #: before a file is played in front of somebody.
    confidentiality: Mapped[str] = mapped_column(
        String(20), default="interno", nullable=False, index=True
    )
    #: Free text, comma separated. Deliberately not a taxonomy: a controlled
    #: vocabulary is a decision the firm has not taken, and inventing one here
    #: would mean untagging the whole library later.
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What the uploader called it. Display only: never part of the storage key,
    #: which is built from a generated UUID (see `build_media_key`).
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: Digest of the bytes actually persisted, so a later read can prove the file
    #: is the one that was uploaded (ADR-041).
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    storage_tier: Mapped[str] = mapped_column(String(20), default="hot", nullable=False)
    #: Unknown until something measures it. There is no transcoder in the project,
    #: so writing a number here from the browser would be a guess presented as a
    #: fact; it stays null until it is measured.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    case_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case: Mapped["Case | None"] = relationship("Case", lazy="selectin")

    @property
    def has_file(self) -> bool:
        return self.storage_key is not None

    def __repr__(self) -> str:
        return f"<MediaItem(title={self.title!r}, kind={self.kind!r})>"


class MediaDerivative(Base, TimestampMixin):
    """A derived file of a library asset: a thumbnail, a preview, a transcode.

    Separate from `MediaItem` rather than a column on it, because an asset can have
    several derivatives and they are all disposable: regenerating them is always
    cheaper than defending them. That is the opposite of `EvidenceFile`, whose
    original is immutable and whose chain of custody is the reason it exists.

    `kind` says what the derivative is (`thumbnail`, `preview`, `transcode`) and
    is part of the storage key, so two derivatives of the same kind cannot
    collide and the original area stays reserved.
    """

    __tablename__ = "media_derivatives"
    __table_args__ = (
        UniqueConstraint("media_id", "kind", name="uq_media_derivative_kind"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_media_derivative_size"),
        Index("ix_media_derivative_media", "media_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Human-readable detail: the ffmpeg version, the encoder used, why a
    #: transcode was skipped. A derivative nobody can explain is one nobody can
    #: delete confidently.
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<MediaDerivative(kind={self.kind!r})>"


class MediaProcessingJob(Base, TimestampMixin):
    """Queued work for a library asset: measuring, thumbnailing, transcoding.

    Its own table and not a shared queue with `EvidenceProcessingJob`, because
    that one carries `evidence_id NOT NULL` and a library asset is not evidence —
    ADR-055 draws exactly that line. The `SKIP LOCKED` claim and the retry policy
    are copied from that worker because they are already proven.
    """

    __tablename__ = "media_processing_jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_media_job_attempts"),
        Index("ix_media_job_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    media_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: `process` for now. Separate from the evidence queue's vocabulary on
    #: purpose: a future `transcode` belongs here, not there.
    job_type: Mapped[str] = mapped_column(String(40), default="process", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker: Mapped[str | None] = mapped_column(String(80), nullable=True)

    media: Mapped["MediaItem"] = relationship("MediaItem", lazy="selectin")

    def __repr__(self) -> str:
        return f"<MediaProcessingJob(status={self.status!r})>"


class InvoiceNumberSequence(Base):
    """Per year counter backing the `FE-AAAA-000001` invoice numbering."""

    __tablename__ = "invoice_number_sequences"

    year: Mapped[int] = mapped_column(primary_key=True)
    last_number: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<InvoiceNumberSequence(year={self.year!r})>"


class Invoice(TimestampMixin, Base):
    """A bill the firm issues. `MASTER_PROMPT` V3: honorarios, pagos y cuentas.

    **It is not a legal record, and it is never deleted.** A voided invoice keeps
    its number, which is what an accountant needs in order to explain, months later,
    why a number that was issued no longer counts. Voiding and deleting are
    different acts and confusing them is how a declared number disappears.

    **Every total on this row is derived.** The browser sends line items and never a
    total: a total the client can write is a total somebody can forge. `subtotal`,
    `tax_amount` and `total` are recomputed from the lines whenever one changes,
    with `Decimal` over `Numeric(14, 2)` — never a float, because `0.1 + 0.2` is
    not `0.3` in binary and an invoice that misses a cent is an invoice nobody uses.

    `tax_rate` defaults to **0**, and that is deliberate: the rate is a fact about
    the firm's tax position that somebody has to bring, not one a migration should
    assert on the firm's behalf.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_invoice_subtotal_positive"),
        CheckConstraint("tax_rate >= 0", name="ck_invoice_tax_rate_positive"),
        Index("ix_invoices_status_issued", "status", "issued_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    #: `FE-AAAA-NNNNNN`, allocated from `invoice_number_sequences` under a row lock
    #: so two concurrent drafts cannot receive the same number.
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    #: Optional: a retainer invoice covers no single matter.
    case_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="borrador", nullable=False, index=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Zero means "no tax applied", not "tax computed as zero".
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0"), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: A void always carries a reason: an unexplained void is not auditable.
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        lazy="selectin",
        order_by="InvoiceLine.position",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", lazy="selectin", order_by="Payment.paid_at"
    )
    client: Mapped["Client"] = relationship("Client", lazy="selectin")
    case: Mapped["Case | None"] = relationship("Case", lazy="selectin")

    @property
    def paid_amount(self) -> Decimal:
        return sum((payment.amount for payment in self.payments), Decimal("0"))

    @property
    def balance(self) -> Decimal:
        """What is still owed. Derived, never stored.

        A `pagada` status is a claim; this is the arithmetic. They agree only
        because the service sets one from the other, and a payment recorded without
        the status would leave the ledger lying.
        """
        return self.total - self.paid_amount

    def __repr__(self) -> str:
        return f"<Invoice(number={self.number!r}, status={self.status!r})>"


class InvoiceLine(TimestampMixin, Base):
    """One chargeable concept on an invoice."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_invoice_line_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_line_price_positive"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Order on the invoice. Documents are read top to bottom and a concept list
    #: that reorders itself between two printouts is not a bill.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: Derived on write, and recomputed with the invoice's totals.
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")

    def __repr__(self) -> str:
        return f"<InvoiceLine(invoice_id={self.invoice_id!r}, description={self.description!r})>"


class Payment(TimestampMixin, Base):
    """A payment received against an invoice.

    Money in is only ever a **positive** amount: a refund is an invoice, not a
    negative receipt, so that "total received" stays a true sum and the ledger does
    not need a sign convention nobody remembers. The check constraint is what
    enforces it, not a validation the service could forget.
    """

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    #: `efectivo`, `transferencia`, `tarjeta`, `cheque`. Free text would make the
    #: ledger impossible to filter by method.
    method: Mapped[str] = mapped_column(
        String(30), default="transferencia", nullable=False, index=True
    )
    paid_at: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    #: Bank reference, cheque number, receipt: whatever proves it later.
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(invoice_id={self.invoice_id!r}, amount={self.amount})>"


class CaseNumberSequence(Base):
    """Per year counter backing the `WA-AAAA-000001` case numbering."""

    __tablename__ = "case_number_sequences"

    year: Mapped[int] = mapped_column(primary_key=True)
    last_number: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<CaseNumberSequence(year={self.year}, last={self.last_number})>"


class Case(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    responsible_lawyer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lawyers.id", ondelete="SET NULL"), nullable=True
    )
    legal_area_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("legal_areas.id", ondelete="SET NULL"), nullable=True
    )
    process_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(150), nullable=True)
    court: Mapped[str | None] = mapped_column(String(200), nullable=True)
    file_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="abierto", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False, index=True)
    opened_at: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    client: Mapped["Client"] = relationship("Client", lazy="selectin")
    responsible_lawyer: Mapped["Lawyer | None"] = relationship("Lawyer", lazy="selectin")
    legal_area: Mapped["LegalArea | None"] = relationship("LegalArea", lazy="selectin")

    __table_args__ = (
        Index("ix_cases_status_priority", "status", "priority"),
        Index("ix_cases_client_id", "client_id"),
    )

    def __repr__(self) -> str:
        return f"<Case(number={self.case_number}, status={self.status})>"


case_lawyers_table = Table(
    "case_lawyers",
    Base.metadata,
    Column(
        "case_id",
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "lawyer_id",
        PG_UUID(as_uuid=True),
        ForeignKey("lawyers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("role", String(30), nullable=False),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "assigned_by",
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class CaseLawyer(Base):
    __tablename__ = "case_lawyers"
    __table__ = case_lawyers_table

    # Columns come from case_lawyers_table; re-declaring them is not allowed.
    case_id: Mapped[UUID]
    lawyer_id: Mapped[UUID]
    role: Mapped[str]
    assigned_at: Mapped[datetime]
    assigned_by: Mapped[UUID | None]

    lawyer: Mapped["Lawyer"] = relationship("Lawyer", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<CaseLawyer(case_id={self.case_id}, "
            f"lawyer_id={self.lawyer_id}, role={self.role})>"
        )


class CaseParty(TimestampMixin, Base):
    __tablename__ = "case_parties"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    document_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_case_parties_case_id", "case_id"),
    )

    def __repr__(self) -> str:
        return f"<CaseParty(case_id={self.case_id}, role={self.party_role})>"


#: The lifecycle of a request that arrived through the public form. A firm that
#: accepts consultations cannot afford to answer everyone, so "descartada" is a
#: first-class state rather than a deleted row: the person was told no, and the
#: record of that decision is worth keeping.
CONSULTATION_STATUSES: tuple[str, ...] = (
    "nueva",
    "en_revision",
    "atendida",
    "convertida",
    "descartada",
)


class ConsultationRequest(TimestampMixin, Base):
    """A consultation request submitted from the public site.

    Every column here is personal data: a name, two ways to call the person and
    a description of their legal problem. Three consequences shape the model.

    **The consent is a column, not a checkbox.** `consent_at` and
    `privacy_notice_version` record what the person agreed to and which text
    they agreed to it, because a claim of consent that cannot be reconstructed
    later is not consent. It is not defaulted in Python: the endpoint fills it
    from the request, so a row can never exist without it.

    **No IP, no user agent.** Those belong in `audit_logs`, where the audit
    middleware already records the request without reading its body. Copying
    them here would duplicate personal data into a second table for no gain.

    **No `change_logs`.** The rest of the application calls `record_changes` to
    leave a per-field history. Doing that here would write the person's name,
    phone, email and legal problem into `change_logs` as well, doubling the
    surface for a breach to expose and giving the person no way to erase one
    copy without the other. The state transitions this table does need are
    carried by `status`, `handled_by` and `handled_at`.

    **No soft delete.** `PROJECT_RULES.md` forbids physically deleting legal
    records. A request that never became an expediente is not one: it is a lead,
    and Colombian data protection law gives the person the right to have it
    erased. `ConsultationService.erase` therefore really deletes, and writes an
    audit entry saying that it did.
    """

    __tablename__ = "consultation_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    area: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    privacy_notice_version: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="nueva", nullable=False, index=True)
    handled_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: A request may also arrive for a client who is already in the system, once
    #: the firm has matched it. Nullable on purpose: most requests arrive from
    #: strangers, and forcing a match would mean inventing one.
    client_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # The queue is read newest-first and filtered by state.
        Index("ix_consultation_requests_status_created", "status", "created_at"),
        Index("ix_consultation_requests_area_created", "area", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ConsultationRequest(area={self.area}, status={self.status})>"