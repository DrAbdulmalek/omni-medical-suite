"""
Storage Configuration - Pydantic-based
"""

try:
    from pydantic.v1 import BaseSettings, validator  # Pydantic v2 with v1 compat
except ImportError:
    from pydantic import BaseSettings, validator  # Pydantic v1

class StorageConfig(BaseSettings):
    """Storage configuration for files and artifacts"""

    # Local Storage
    STORAGE_DIR: str = "./storage"
    UPLOAD_DIR: str = "./storage/uploads"
    OUTPUT_DIR: str = "./storage/outputs"
    TEMP_DIR: str = "./storage/temp"
    CACHE_DIR: str = "./storage/cache"

    # File Limits
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    MAX_TOTAL_STORAGE: str = "100GB"  # Total storage limit
    MAX_FILES: int = 10000  # Maximum number of files

    # Allowed Extensions
    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".webp",
        ".txt", ".json", ".csv", ".xml", ".yaml", ".yml"
    ]

    # Cleanup
    CLEANUP_TEMP_FILES: bool = True
    TEMP_FILE_EXPIRY: int = 24  # hours
    CLEANUP_SCHEDULE: str = "0 2 * * *"  # Daily at 2 AM

    # Cloud Storage (Optional)
    CLOUD_STORAGE_ENABLED: bool = False
    CLOUD_STORAGE_PROVIDER: str = "local"  # local, s3, gcs, azure
    CLOUD_STORAGE_BUCKET: str | None = None

    # S3 Configuration
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    S3_REGION: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("STORAGE_DIR", "UPLOAD_DIR", "OUTPUT_DIR", "TEMP_DIR", "CACHE_DIR")
    @classmethod
    def validate_directory(cls, v):
        if not v or v == ".":
            raise ValueError("Directory path cannot be empty or root")
        return v

    @validator("MAX_FILE_SIZE")
    @classmethod
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError("MAX_FILE_SIZE must be positive")
        return v

from functools import lru_cache


@lru_cache
def get_storage_config() -> StorageConfig:
    """Get storage configuration - cached for performance"""
    return StorageConfig()
