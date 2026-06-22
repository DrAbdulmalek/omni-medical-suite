"""Shared test fixtures for services/api tests."""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Ensure the app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars BEFORE any app module is imported
os.environ.setdefault("API_KEY", "test-api-key-12345")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_omni.db")


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Return a mock Settings object with test overrides."""
    settings = MagicMock()
    settings.APP_NAME = "OmniMedicalSuite"
    settings.APP_VERSION = "2.0.0"
    settings.DATABASE_URL = "sqlite:///./test_omni.db"
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.API_KEY = "test-api-key-12345"
    settings.CORS_ORIGINS = ["http://localhost:3000"]
    settings.OCR_ENGINE_PRIORITY = ["tesseract", "easyocr"]
    settings.OCR_FUSION_METHOD = "weighted_vote"
    settings.OCR_CONFIDENCE_THRESHOLD = 0.6
    settings.SEMANTIC_SIMILARITY_THRESHOLD = 0.85
    settings.DBSCAN_EPS = 0.3
    settings.MISTRAL_API_KEY = None
    settings.GEMINI_API_KEY = None
    settings.LOG_LEVEL = "DEBUG"
    settings.MAX_UPLOAD_SIZE_MB = 50
    settings.RATE_LIMIT_REQUESTS = 100
    settings.RATE_LIMIT_WINDOW = 60
    settings.STARTUP_TIME = None
    settings.has_mistral = False
    settings.has_gemini = False
    settings.max_upload_size_bytes = 50 * 1024 * 1024
    return settings


@pytest.fixture
def mock_prisma():
    """Return a mock PrismaClient."""
    prisma = MagicMock()
    prisma.connect = AsyncMock()
    prisma.disconnect = AsyncMock()
    prisma.user = MagicMock()
    prisma.user.find_many = AsyncMock(return_value=[])
    prisma.user.find_unique = AsyncMock(return_value=None)
    prisma.user.create = AsyncMock(return_value={"id": "1", "email": "test@test.com"})
    prisma.document = MagicMock()
    prisma.document.find_many = AsyncMock(return_value=[])
    prisma.document.find_unique = AsyncMock(return_value=None)
    prisma.document.create = AsyncMock(return_value={"id": "doc-1", "filename": "test.png"})
    prisma.document.delete = AsyncMock(return_value={"id": "doc-1"})
    prisma.document.update = AsyncMock(return_value={"id": "doc-1"})
    return prisma


@pytest.fixture
def mock_redis():
    """Return a mock RedisClient."""
    redis = MagicMock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.health_check = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_ocr_output():
    """Return a mock OCROutput result."""
    from app.vision.ocr_fusion_system import BoundingBox, OCROutput

    return OCROutput(
        engine_name="tesseract",
        text="Patient Name: John Doe\nDiagnosis: Diabetes Type 2",
        confidence=0.92,
        regions=[
            BoundingBox(x=10, y=10, w=200, h=30),
            BoundingBox(x=10, y=50, w=300, h=30),
        ],
        processing_time_ms=150.0,
        language_detected="eng",
    )


@pytest.fixture
def mock_ocr_engine(mock_ocr_output):
    """Return a mock OCR engine."""
    engine = MagicMock()
    engine.name = "tesseract"
    engine.supported_languages = ["eng", "ara"]
    engine.is_available.return_value = True
    engine.recognize = AsyncMock(return_value=mock_ocr_output)
    return engine


@pytest.fixture
def sample_document_data():
    """Return sample document data for testing."""
    return {
        "id": "doc-123",
        "filename": "medical_report.png",
        "file_path": "/tmp/medical_report.png",
        "file_size": 102400,
        "mime_type": "image/png",
        "page_count": 1,
        "extracted_text": "Patient: John Doe\nDiagnosis: Type 2 Diabetes\nMedication: Metformin 500mg",
        "status": "completed",
    }
