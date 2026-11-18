"""Opt-in recovery configuration, independent of unrelated application settings."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import EmailStr, Field, SecretStr, TypeAdapter, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class RecoverySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="PASSWORD_RECOVERY_", extra="ignore"
    )

    enabled: bool = False
    public_url: str = ""
    encryption_key: SecretStr = SecretStr("")
    proxy_key: SecretStr = SecretStr("")
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "tls", "plain"] = "starttls"
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    mail_from: str = ""
    smtp_timeout_seconds: float = Field(default=10, ge=1, le=30)
    ttl_minutes: int = Field(default=20, ge=5, le=60)
    request_ip_limit: int = Field(default=5, ge=1)
    confirm_ip_limit: int = Field(default=10, ge=1)
    global_limit: int = Field(default=100, ge=1)
    recipient_limit: int = Field(default=3, ge=1)
    cooldown_seconds: int = Field(default=60, ge=1)
    max_attempts: int = Field(default=3, ge=1, le=5)

    def validate_enabled(self, environment: str) -> None:
        if not self.enabled:
            return
        parts = urlsplit(self.public_url)
        local_test = (
            environment == "test"
            and parts.scheme == "http"
            and parts.hostname in {"localhost", "127.0.0.1"}
        )
        if (
            not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in {"", "/"}
            or (parts.scheme != "https" and not local_test)
        ):
            raise ValueError("PASSWORD_RECOVERY_PUBLIC_URL debe ser un origen HTTPS fijo")
        try:
            Fernet(self.encryption_key.get_secret_value().encode("ascii"))
        except (ValueError, UnicodeError):
            raise ValueError(
                "PASSWORD_RECOVERY_ENCRYPTION_KEY no es una clave Fernet válida"
            ) from None
        if len(self.proxy_key.get_secret_value()) < 32:
            raise ValueError("PASSWORD_RECOVERY_PROXY_KEY debe tener al menos 32 caracteres")
        if (
            not self.smtp_host
            or not self.mail_from
            or "@" not in self.mail_from
            or any(c in self.mail_from for c in "\r\n<>")
        ):
            raise ValueError("Configure SMTP y PASSWORD_RECOVERY_MAIL_FROM")
        try:
            TypeAdapter(EmailStr).validate_python(self.mail_from)
        except ValidationError:
            raise ValueError("PASSWORD_RECOVERY_MAIL_FROM debe ser un correo válido") from None
        if bool(self.smtp_user) != bool(self.smtp_password.get_secret_value()):
            raise ValueError("Configure conjuntamente el usuario y contraseña SMTP")
        if self.smtp_security == "plain" and environment != "test":
            raise ValueError("SMTP sin TLS solo se permite en entorno test")


@lru_cache
def get_recovery_settings() -> RecoverySettings:
    return RecoverySettings()
