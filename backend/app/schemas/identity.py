from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


__all__ = [
    "AuditLogResponse",
    "PaginatedAuditLogs",
    "PaginatedUsers",
    "PermissionResponse",
    "RoleAssignmentRequest",
    "RoleResponse",
    "SessionInfo",
    "UserCreateAdmin",
    "UserUpdateAdmin",
]
