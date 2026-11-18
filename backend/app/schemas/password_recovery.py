from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.schemas.identity import PasswordResetRequest


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=255)


class RecoverPasswordRequest(PasswordResetRequest):
    token: SecretStr = Field(min_length=43, max_length=43)
