from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "wabogados-api"
    app_environment: str = "development"
    database_url: str = Field(
        default="postgresql+asyncpg://wabogados:wabogados@localhost:5432/wabogados"
    )

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Rate limiting
    # `redis_url` selects the shared counter (ADR-008). Empty keeps the
    # in-process one, which is only correct while a single API process serves
    # every request: with several workers each keeps its own count, so the real
    # budget becomes `limit * workers`, and a restart clears it for everyone.
    redis_url: str | None = None
    # Peers allowed to set `X-Forwarded-For`. Empty means "nobody": Compose puts
    # nothing in front of the API, so today the header is never believed. Listing
    # an address here is what makes it trustworthy, and each entry is one more
    # party that can rewrite the address the audit trail records.
    trusted_proxies: list[str] = Field(default_factory=list)
    # What to do when the shared store is unreachable. The default counts in
    # process: an outage of Redis must not become an unlimited login budget, and
    # it must not become an outage of the whole firm either. A deployment that
    # prefers to refuse every request while the limiter is blind can say so.
    rate_limit_fail_closed: bool = False
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 300

    # Messaging is a write heavy endpoint and an abuse vector. It gets its own,
    # much tighter budget than the generic one.
    message_rate_limit_requests: int = 30
    message_rate_limit_window_seconds: int = 60

    # The public consultation form is the only unauthenticated write in the
    # application, and what it accepts is somebody's legal problem. Three
    # requests an hour per IP is enough for a real person who mistyped a field
    # and sent it twice, and low enough that a scripted flood is not a
    # commercial event for the firm.
    contact_rate_limit_requests: int = 3
    contact_rate_limit_window_seconds: int = 3600
    # A single message cannot carry a large file.
    max_attachment_bytes: int = 10 * 1024 * 1024
    max_attachments_per_message: int = 5

    # Bootstrap administrator (used only by the CLI, never by the API)
    admin_email: str | None = None
    admin_password: str | None = Field(default=None, min_length=12)

    # Document storage
    storage_root: Path = Path(".tmp/storage")
    max_upload_bytes: int = 20 * 1024 * 1024
    # The multimedia library carries video, which is the first format in the
    # project whose useful size does not fit in a screenshot. It has its own cap
    # rather than raising the document one: a 20 MB ceiling is right for a signed
    # PDF and absurd for an inspection recording, and one shared number can only be
    # wrong for one of them.
    #
    # Beyond this the file belongs in the worker queue (ADR-049), which does not
    # exist yet; the cap is what keeps an unqueued upload from exhausting memory in
    # the request thread.
    max_media_bytes: int = 500 * 1024 * 1024
    storage_backend: Literal["local", "s3"] = "local"

    # Antivirus engine (see KNOWN_ISSUES.md and docs/RESTORE.md §8 for the
    # decision trail). `antivirus_host` None disables the scan; when set, every
    # upload pipeline is fail closed: an available-but-infected payload is
    # discarded and an unavailable engine refuses the upload or postpones the
    # queued work, never accepts it silently.
    antivirus_host: str | None = None
    antivirus_port: int = 3310
    antivirus_timeout_seconds: float = 60.0

    # S3 / MinIO. Credentials are never committed; use the environment.
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "wabogados-documents"
    s3_use_ssl: bool = False
    s3_addressing_style: Literal["auto", "path", "virtual"] = "path"
    # Remote storage class applied when a version is moved to the archive tier.
    # It must stay immediately readable: GLACIER and DEEP_ARCHIVE make an object
    # unavailable until a restore completes, which would break the promise that
    # any version can be downloaded at any time. STANDARD_IA is cheaper and
    # instantly retrievable.
    # MinIO on a single node cannot transition storage classes at all, so there
    # the tier is recorded in the database only and this value is ignored.
    s3_archive_storage_class: str = "STANDARD_IA"
    # Create the bucket on startup. Convenient in development, undesirable in
    # production where bucket creation is normally an infrastructure concern.
    s3_create_bucket: bool = False

    # Version retention. Tiering only: content is never deleted (PROJECT_RULES 5).
    retention_hot_days: int = 90
    retention_tiering_enabled: bool = True

    # Off site backup target. A backup that stays on the same host as the data it
    # protects survives nothing, so this is expected to be configured in
    # production. Empty means "not configured", never "skip silently".
    backup_remote_enabled: bool = False
    backup_remote_endpoint: str | None = None
    backup_remote_access_key: str | None = None
    backup_remote_secret_key: str | None = None
    backup_remote_bucket: str = "wabogados-backups"
    backup_remote_prefix: str = "wabogados"
    backup_remote_region: str = "us-east-1"
    backup_remote_use_ssl: bool = False
    backup_remote_addressing_style: Literal["auto", "path", "virtual"] = "path"
    # Read the uploaded object back and compare its digest. Metadata alone can be
    # wrong; only reading the bytes proves the remote copy is intact.
    backup_remote_verify_upload: bool = True
    backup_remote_keep: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
