from __future__ import annotations

import base64
from functools import cached_property

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    env: str = "development"
    log_level: str = "INFO"
    version: str = "0.1.0"

    # --- Helpdesk Postgres ---
    database_url: str
    helpdesk_schema: str = "helpdesk"
    rag_schema: str = "helpdesk_rag"

    # --- Security / auth Postgres ---
    security_db_host: str
    security_db_port: int = 5432
    security_db_user: str
    security_db_password: str = ""
    security_db_name: str
    security_schema: str = "public"  # schema inside security DB (always 'public')

    @field_validator("security_schema")
    @classmethod
    def _validate_security_schema(cls, v: str) -> str:
        if v not in {"public", "security"}:
            raise ValueError(f"security_schema must be 'public' or 'security', got {v!r}")
        return v

    # TI department ID in public.department — users with this dept get it_agent role
    it_department_id: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def security_db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.security_db_user}:{self.security_db_password}"
            f"@{self.security_db_host}:{self.security_db_port}/{self.security_db_name}"
        )

    # --- Session / JWT ---
    secret_key: str
    csrf_secret: str = ""
    session_cookie_name: str = "__Host-sds_session"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 h

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- MinIO ---
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "helpdesk-attachments"
    minio_secure: bool = False

    # --- ClamAV ---
    clamav_host: str = "clamav"
    clamav_port: int = 3310

    # --- AI providers ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini-2024-07-18"
    openai_embed_model: str = "text-embedding-3-small"
    openai_max_retries: int = 1
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    ai_fallback_enabled: bool = False

    # --- Email / SMTP ---
    mail_host: str = "smtp.office365.com"
    mail_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""
    it_team_email: str = "ti@desangosse.com.br"
    frontend_url: str = "http://localhost:8081"
    cors_origins: str = "http://localhost:3004,http://localhost:8081"

    # --- PII / token_map ---
    pii_map_ttl_seconds: int = 86400

    # --- RBAC bootstrap (Sprint 0) — see ADR-0003 ---
    bootstrap_admin_uuids: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def fernet_key(self) -> bytes:
        """32-byte Fernet key derived from SECRET_KEY (URL-safe base64 of 32 bytes).

        Fernet requires a URL-safe base64-encoded 32-byte value (44 chars output).
        We decode SECRET_KEY, take the first 32 bytes, then re-encode. Fails at boot
        if SECRET_KEY is shorter than 32 bytes — fail-fast is intentional.
        """
        raw = base64.urlsafe_b64decode(self.secret_key + "==")
        if len(raw) < 32:  # noqa: PLR2004
            raise ValueError("SECRET_KEY must decode to at least 32 bytes for Fernet")
        return base64.urlsafe_b64encode(raw[:32])

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def bootstrap_admin_uuid_set(self) -> frozenset[str]:
        """Lower-cased UUID set for O(1) membership checks."""
        if not self.bootstrap_admin_uuids:
            return frozenset()
        return frozenset(
            u.strip().lower() for u in self.bootstrap_admin_uuids.split(",") if u.strip()
        )

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


settings = Settings()  # type: ignore[call-arg]
