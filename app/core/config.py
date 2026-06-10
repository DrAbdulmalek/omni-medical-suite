"""
Application configuration with environment variable support.
For production, use Kubernetes Secrets or external secret managers.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "OmniMedical Suite"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = Field(default="change-me-in-production")
    ALLOWED_ORIGINS: list[str] = Field(default=["*"])
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://omnimedical:omnimedical@localhost:5432/omnimedical")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # Qdrant
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_COLLECTION: str = Field(default="medical_documents")
    QDRANT_VECTOR_SIZE: int = Field(default=384)
    
    # OCR Settings
    OCR_MAX_FILE_SIZE: int = Field(default=50 * 1024 * 1024)  # 50MB
    OCR_SUPPORTED_FORMATS: list[str] = Field(default=["png", "jpg", "jpeg", "tiff", "bmp", "pdf"])
    OCR_TIMEOUT: int = Field(default=300)  # 5 minutes
    
    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")
    
    # OpenTelemetry
    OTEL_ENABLED: bool = Field(default=True)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(default="http://localhost:4318")
    OTEL_SERVICE_NAME: str = Field(default="omnimedical-api")
    
    # Medical Dictionary
    MEDICAL_DICT_PATH: str = Field(default="data/medical_dictionary.json")
    
    # Upload
    UPLOAD_DIR: str = Field(default="services/uploads")
    MAX_UPLOAD_SIZE: int = Field(default=50 * 1024 * 1024)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
