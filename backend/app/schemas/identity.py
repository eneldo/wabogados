from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationInfo, field_validator

from app.models import Role
from app.schemas.auth import UserCreate, UserResponse, UserUpdate


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_role(cls, role: Role) -> "RoleResponse":
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(permission.name for permission in role.permissions),
            created_at=role.created_at,
        )


class PermissionResponse(BaseModel):
    id: UUID
    name: str
    resource: str
    action: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleAssignmentRequest(BaseModel):
    role_name: str = Field(min_length=2, max_length=100)


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_names: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permission_names: list[str] | None = None


class SessionInfo(BaseModel):
    id: UUID
    jti: str
    expires_at: datetime
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedUsers(BaseModel):
    items: list[UserResponse]
    total: int
    skip: int
    limit: int


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID | None = None
    # Filled by the route from the eager-loaded relation: an audit trail that
    # only prints UUIDs tells the firm nothing about who did what.
    user_email: str | None = None
    action: str
    entity: str
    entity_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    result: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int
    skip: int
    limit: int


class UserCreateAdmin(UserCreate):
    role_names: list[str] = Field(default_factory=list)


class UserUpdateAdmin(UserUpdate):
    pass


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: SecretStr = Field(min_length=8, max_length=128)
    confirm_password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: SecretStr, info: "ValidationInfo") -> SecretStr:
        password = info.data.get("new_password")
        if password is not None and value.get_secret_value() != password.get_secret_value():
            raise ValueError("Las contraseñas no coinciden")
        return value


class PasswordResetResponse(BaseModel):
    message: str
    revoked_sessions: int


__all__ = [
    "AuditLogResponse",
    "PaginatedAuditLogs",
    "PaginatedUsers",
    "PermissionResponse",
    "RoleAssignmentRequest",
    "RoleCreate",
    "RoleResponse",
    "RoleUpdate",
    "SessionInfo",
    "UserCreateAdmin",
    "UserUpdateAdmin",
]
