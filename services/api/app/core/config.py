"""Application configuration module for OmniMedicalSuite.

Uses Pydantic Settings for environment-variable-driven configuration with
sensible defaults for local development.  All sensitive values (API keys,
database credentials, etc.) should be supplied via environment variables or
a ``.env`` file – never committed to version control.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class OCRFusionMethod(str, Enum):
    """Supported OCR result fusion strategies."""

    WEIGHTED_VOTE = "weighted_vote"
    CHARACTER_LEVEL = "character_level"
    BEST_CONFIDENCE = "best_confidence"
    SMART_FALLBACK = "smart_fallback"


class Settings(BaseSettings):
    """Centralised application settings.

    Values are resolved from environment variables (case-insensitive) or a
    ``.env`` file in the working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application metadata ────────────────────────────────────────────
    STARTUP_TIME: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp recorded when the application process started.",
    )
    APP_NAME: str = "OmniMedicalSuite"
    APP_VERSION: str = "2.0.0"

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./omni_medical.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _ensure_wal_mode(cls, v: str) -> str:
        """Append WAL-mode pragma for SQLite DSNs."""
        if v.startswith("sqlite"):
            sep = "&" if "?" in v else "?"
            if "journal_mode" not in v:
                v = f"{v}{sep}_journal_mode=WAL"
        return v

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Authentication ──────────────────────────────────────────────────
    API_KEY: str = Field(
        ...,
        description="Bearer token required for API authentication.",
    )

    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        description="List of allowed CORS origins.",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── OCR configuration ───────────────────────────────────────────────
    OCR_ENGINE_PRIORITY: list[str] = Field(
        default=["tesseract", "easyocr", "paddleocr", "trocr", "surya"],
        description="Ordered list of OCR engines to try (first = highest priority).",
    )

    @field_validator("OCR_ENGINE_PRIORITY", mode="before")
    @classmethod
    def _parse_ocr_engines(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [engine.strip() for engine in v.split(",") if engine.strip()]
        return v

    OCR_FUSION_METHOD: OCRFusionMethod = OCRFusionMethod.WEIGHTED_VOTE

    OCR_CONFIDENCE_THRESHOLD: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for an OCR result to be accepted.",
    )

    # ── Semantic / clustering ───────────────────────────────────────────
    SEMANTIC_SIMILARITY_THRESHOLD: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Cosine-similarity threshold for semantic matching.",
    )

    DBSCAN_EPS: float = Field(
        default=0.3,
        gt=0.0,
        description="DBSCAN epsilon parameter for document clustering.",
    )

    # ── LLM provider keys (optional) ────────────────────────────────────
    MISTRAL_API_KEY: str | None = Field(
        default=None,
        description="API key for Mistral AI (optional).",
    )
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="API key for Google Gemini (optional).",
    )

    # ── Logging ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Python logging level.",
    )

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        return v.strip().upper()

    # ── Upload / rate-limiting ──────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        gt=0,
        description="Maximum file upload size in megabytes.",
    )
    RATE_LIMIT_REQUESTS: int = Field(
        default=100,
        gt=0,
        description="Maximum number of requests per window per client.",
    )
    RATE_LIMIT_WINDOW: int = Field(
        default=60,
        gt=0,
        description="Rate-limit window in seconds.",
    )

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def max_upload_size_bytes(self) -> int:
        """Return ``MAX_UPLOAD_SIZE_MB`` converted to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def uptime_seconds(self) -> float:
        """Seconds elapsed since ``STARTUP_TIME``."""
        return (datetime.now(timezone.utc) - self.STARTUP_TIME).total_seconds()

    @property
    def has_mistral(self) -> bool:
        return bool(self.MISTRAL_API_KEY)

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @property
    def has_any_llm(self) -> bool:
        return self.has_mistral or self.has_gemini


# ---------------------------------------------------------------------------
# Singleton instance – import this throughout the codebase
# ---------------------------------------------------------------------------
def get_settings() -> Settings:
    """Return the cached :class:`Settings` singleton.

    Subsequent calls return the same object (Pydantic-Settings caches the
    instance internally on the first instantiation).
    """
    return Settings()


settings = get_settings()
