"""
OCR Configuration - Pydantic-based
"""
from typing import List, Optional
try:
    from pydantic.v1 import BaseSettings, validator  # Pydantic v2 with v1 compat
except ImportError:
    from pydantic import BaseSettings, validator  # Pydantic v1

class OCRConfig(BaseSettings):
    """OCR processing configuration"""

    # OCR Engines
    DEFAULT_ENGINE: str = "tesseract"  # tesseract, easyocr, paddleocr
    ENABLED_ENGINES: List[str] = ["tesseract", "easyocr"]

    # Tesseract
    TESSERACT_PATH: str = "/usr/bin/tesseract"
    TESSERACT_LANG: str = "ara+eng"  # Arabic + English
    TESSERACT_CONFIG: str = ""
    TESSERACT_OCR_ENGINE_MODE: int = 3  # 0=Legacy, 1=LSTM, 2=Legacy+LSTM, 3=Default

    # EasyOCR
    EASYOCR_USER_NETWORK_DIRECTORY: Optional[str] = None
    EASYOCR_RECOGNITION_NETWORK: str = "arabic"
    EASYOCR_USER_NETWORK: str = "arabic"
    EASYOCR_MODEL_STORAGE_DIRECTORY: str = "./models/easyocr"
    EASYOCR_DOWNLOAD_ENABLED: bool = True

    # PaddleOCR
    PADDLEOCR_USE_ANGLE_CLAS: bool = True
    PADDLEOCR_LANG: str = "ar"
    PADDLEOCR_PAGE_NUM: int = 0  # 0 for all pages
    PADDLEOCR_MODEL_DIR: str = "./models/paddleocr"
    PADDLEOCR_USE_DYNAMIC_SHAPE: bool = True

    # Preprocessing
    ENABLE_PREPROCESSING: bool = True
    PREPROCESSING_METHODS: List[str] = ["deskew", "binarization", "denoising", "contrast"]

    # Postprocessing
    ENABLE_POSTPROCESSING: bool = True
    POSTPROCESSING_METHODS: List[str] = ["spell_check", "language_detection", "text_cleaning"]

    # Performance
    MAX_CONCURRENT_OCR: int = 4
    OCR_TIMEOUT: int = 300  # 5 minutes
    OCR_MEMORY_LIMIT: str = "4GB"

    # Output
    OUTPUT_FORMAT: str = "json"  # json, text, html
    SAVE_IMAGES: bool = True
    IMAGE_QUALITY: int = 90  # 0-100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("DEFAULT_ENGINE")
    @classmethod
    def validate_engine(cls, v):
        valid_engines = ["tesseract", "easyocr", "paddleocr"]
        if v not in valid_engines:
            raise ValueError(f"DEFAULT_ENGINE must be one of: {', '.join(valid_engines)}")
        return v

    @validator("MAX_CONCURRENT_OCR")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("MAX_CONCURRENT_OCR must be positive")
        return v

from functools import lru_cache

@lru_cache()
def get_ocr_config() -> OCRConfig:
    """Get OCR configuration - cached for performance"""
    return OCRConfig()