"""
Unified Configuration System - Pydantic-based
"""
from app.config.app import AppConfig
from app.config.security import SecurityConfig
from app.config.database import DatabaseConfig
from app.config.ocr import OCRConfig
from app.config.ml import MLConfig
from app.config.storage import StorageConfig

# Re-export all configs
__all__ = [
    'AppConfig', 'SecurityConfig', 'DatabaseConfig',
    'OCRConfig', 'MLConfig', 'StorageConfig',
    'get_app_config', 'get_security_config', 'get_db_config',
    'get_ocr_config', 'get_ml_config', 'get_storage_config',
    'validate_config'
]

from app.config.app import get_app_config
from app.config.security import get_security_config
from app.config.database import get_db_config
from app.config.ocr import get_ocr_config
from app.config.ml import get_ml_config
from app.config.storage import get_storage_config
from app.config.security import validate_config