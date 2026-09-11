"""Centralised configuration.

Every setting is read from the environment (or a local `.env` file). There are
no credentials in source control: a missing required variable is a hard startup
failure rather than a silent fallback to something insecure.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Values that ship in .env.example. If any of them survive into a running
# process we know the operator never configured the deployment.
PLACEHOLDER_MARKERS = ("CHANGE_ME", "REPLACE_ME", "changeme", "your-secret")

ALLOWED_UPLOAD_TYPES: dict[str, tuple[str, ...]] = {
    # mime type -> permitted filename extensions
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/tiff": (".tif", ".tiff"),
    "text/plain": (".txt",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx",),
    "application/msword": (".doc",),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------- application
    app_name: str = "NyayaVault"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"

    # ---------------------------------------------------------------- database
    database_url: str = Field(..., description="SQLAlchemy database URL")
    db_echo: bool = False

    # ------------------------------------------------------------------- minio
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = Field(..., description="MinIO access key")
    minio_secret_key: str = Field(..., description="MinIO secret key")
    minio_bucket: str = "nyayavault-documents"
    minio_secure: bool = False

    # --------------------------------------------------------------------- jwt
    jwt_secret_key: str = Field(..., description="HMAC signing key for access tokens")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    # bcrypt cost factor. Lowered only by the test-suite; production enforces a
    # floor of 10 regardless of this value (see app/security.py).
    bcrypt_rounds: int = 12

    # ------------------------------------------------------------- upload policy
    max_upload_bytes: int = 52_428_800  # 50 MiB

    # ------------------------------------------------------------- demo features
    allow_demo_tamper: bool = False

    # ---------------------------------------------------------------- blockchain
    blockchain_rpc_url: str = "http://hardhat-node:8545"
    blockchain_contract_address: str = "" 

    # ------------------------------------------------------------------ seeding
    seed_admin_username: str = "admin"
    seed_admin_email: str = "admin@nyayavault.local"
    seed_admin_password: str = ""

    # ------------------------------------------------------------------ helpers
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    # --------------------------------------------------------------- validation
    @field_validator("jwt_algorithm")
    @classmethod
    def _supported_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of {sorted(allowed)}")
        return v

    @field_validator("max_upload_bytes")
    @classmethod
    def _sane_upload_limit(cls, v: int) -> int:
        if not (1024 <= v <= 512 * 1024 * 1024):
            raise ValueError("MAX_UPLOAD_BYTES must be between 1 KiB and 512 MiB")
        return v

    @model_validator(mode="after")
    def _reject_placeholder_secrets(self) -> "Settings":
        """Fail closed in production, warn loudly in development.

        This is the single guard that stops the prototype from ever being run
        with the example credentials that ship in .env.example.
        """
        problems: list[str] = []

        if len(self.jwt_secret_key) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")
        if any(m in self.jwt_secret_key for m in PLACEHOLDER_MARKERS):
            problems.append("JWT_SECRET_KEY still contains a placeholder value")
        if any(m in self.minio_secret_key for m in PLACEHOLDER_MARKERS):
            problems.append("MINIO_SECRET_KEY still contains a placeholder value")
        if any(m in self.database_url for m in PLACEHOLDER_MARKERS):
            problems.append("DATABASE_URL still contains a placeholder password")

        if problems:
            message = "Insecure configuration: " + "; ".join(problems)
            if self.is_production:
                raise ValueError(message)
            logger.warning("%s. This is tolerated only because APP_ENV=%s.", message, self.app_env)

        if self.is_production and "*" in self.cors_origins:
            raise ValueError("ALLOWED_ORIGINS must not be '*' in production")

        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used everywhere, including as a FastAPI dependency."""
    return Settings()  # type: ignore[call-arg]
