from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import User


class TokenBase(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Token(TokenBase):
    pass


class TokenPayload(BaseModel):
    sub: UUID
    type: str
    exp: datetime
    iat: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Optional session to revoke; omit it to revoke every active session."""

    refresh_token: str | None = None


class UserBase(BaseModel):
    # `str`, not `EmailStr`.
    #
    # The address was already validated on the way in, and re-validating it on
    # the way out means one stored value the rule later refuses answers the
    # **whole list** with a 500: `GET /admin/users` serialises every row through
    # `UserResponse`, so a single legacy address took the directory down for every
    # caller. That is the same failure the `NIF` document type caused for clients,
    # for the same reason, and `ClientResponse` / `LawyerResponse` read their
    # address as `str` for exactly this.
    email: str
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    # The input narrows it back: nothing new reaches the database without a
    # deliverable-looking address, while nothing already stored can break a read.
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    is_superuser: bool = False


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_verified: bool | None = None
    is_superuser: bool | None = None


class UserResponse(UserBase):
    id: UUID
    is_superuser: bool
    is_verified: bool
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten_authorization(cls, data: Any) -> Any:
        if not isinstance(data, User):
            return data
        roles = [role.name for role in data.roles]
        permissions = sorted(
            {permission.name for role in data.roles for permission in role.permissions}
        )
        return {
            "id": data.id,
            "email": data.email,
            "full_name": data.full_name,
            "is_superuser": data.is_superuser,
            "is_verified": data.is_verified,
            "is_active": data.is_active,
            "last_login_at": data.last_login_at,
            "created_at": data.created_at,
            "updated_at": data.updated_at,
            "roles": roles,
            "permissions": permissions,
        }


class MessageResponse(BaseModel):
    message: str