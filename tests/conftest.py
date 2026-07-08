"""
Shared pytest fixtures for OmniMedical Suite tests.

This conftest provides:
- Database fixtures (SQLite in-memory for unit tests)
- FastAPI test client
- Sample medical OCR data fixtures
- Configuration fixtures
- Path helpers for monorepo package resolution

Monorepo path resolution: pythonpath includes . src packages
"""
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Monorepo root & path helpers
# ---------------------------------------------------------------------------
MONOREPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = MONOREPO_ROOT / "src"
PACKAGES_DIR = MONOREPO_ROOT / "packages"


def _ensure_monorepo_paths() -> None:
    """Add src/ and packages/ to sys.path so imports resolve in tests."""
    for p in (str(SRC_DIR), str(PACKAGES_DIR), str(MONOREPO_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_monorepo_paths()


@pytest.fixture
def monorepo_root() -> Path:
    """Return the absolute path to the monorepo root."""
    return MONOREPO_ROOT


@pytest.fixture
def samples_dir(monorepo_root: Path) -> Path:
    """Return the path to the samples/ directory."""
    return monorepo_root / "samples"


@pytest.fixture
def data_dir(monorepo_root: Path) -> Path:
    """Return the path to the data/ directory."""
    return monorepo_root / "data"


# ---------------------------------------------------------------------------
# Temporary directory / file helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Provide a clean temporary directory (auto-cleaned)."""
    with tempfile.TemporaryDirectory(prefix="omni_test_") as td:
        yield Path(td)


@pytest.fixture
def tmp_json_file(tmp_dir: Path) -> Generator[Path, None, None]:
    """Provide a temp JSON file path (file not created)."""
    p = tmp_dir / "test_output.json"
    yield p


# ---------------------------------------------------------------------------
# Sample medical data fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_arabic_text() -> str:
    """Sample Arabic medical text for testing."""
    return "المريض يعاني من ألم في الصدر وضيق في التنفس"


@pytest.fixture
def sample_medical_terms() -> list[str]:
    """List of common Arabic medical terms for dictionary / NLP tests."""
    return [
        "ضغط الدم",
        "السكري",
        "القلب",
        "الرئة",
        "الكبد",
        "التحليل المخبري",
        "الأشعة السينية",
        "الجراحة",
        "العلاج الكيميائي",
        "الفحص السريري",
    ]


@pytest.fixture
def sample_ocr_result() -> dict[str, Any]:
    """Simulated OCR engine output for pipeline tests."""
    return {
        "text": "ضغط الدم ١٢٠/٨٠ ملم زئبق",
        "confidence": 0.92,
        "blocks": [
            {"text": "ضغط الدم", "bbox": [10, 20, 200, 50], "confidence": 0.95},
            {"text": "١٢٠/٨٠", "bbox": [210, 20, 320, 50], "confidence": 0.88},
            {"text": "ملم زئبق", "bbox": [330, 20, 500, 50], "confidence": 0.93},
        ],
        "language": "ar",
        "page": 1,
    }


@pytest.fixture
def sample_medical_report_json() -> dict[str, Any]:
    """Full sample medical report structure for integration tests."""
    return {
        "patient_name": "أحمد محمد",
        "patient_id": "P-2024-00142",
        "date": "2024-06-15",
        "doctor": "د. خالد العلي",
        "department": "طب القلب",
        "diagnosis": "ارتفاع ضغط الدم الأساسي",
        "medications": [
            {"name": "أملوديبين", "dose": "5 مجم", "frequency": "مرة يومياً"},
            {"name": "أسبرين", "dose": "100 مجم", "frequency": "مرة يومياً"},
        ],
        "notes": "يُطلب متابعة بعد شهر مع تحليل وظائف الكلى",
    }


# ---------------------------------------------------------------------------
# FastAPI test client (conditional — only if app is importable)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def db():
    """
    Create a fresh SQLite in-memory database for each test.
    Requires: sqlalchemy, app.core.database, app.main
    """
    pytest.importorskip("sqlalchemy")
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        pytest.skip("sqlalchemy not installed")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    try:
        from app.core.database import Base
    except ImportError:
        # If app is not fully set up, create tables manually
        Base = None  # type: ignore[assignment]

    if Base is not None:
        Base.metadata.create_all(bind=engine)

    session = _Session()
    yield session
    session.close()
    if Base is not None:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """
    Create a FastAPI TestClient with DB override.
    Skips if the app module is not importable.
    """
    try:
        from fastapi.testclient import TestClient

        from app.core.database import get_db
        from app.main import app
    except ImportError:
        pytest.skip("FastAPI app not importable — skipping client fixture")

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers with a test API token."""
    return {"X-API-Key": "test-key-omni-medical"}


# ---------------------------------------------------------------------------
# Marker registration (extra safety — also in pytest.ini)
# ---------------------------------------------------------------------------
def pytest_configure(config: Any) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "benchmark: marks tests as benchmarks")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "ocr: tests requiring OCR engines (tesseract, paddleocr)")
    config.addinivalue_line("markers", "nlp: tests requiring NLP models")
    config.addinivalue_line("markers", "gpu: tests requiring GPU")
    config.addinivalue_line("markers", "requires_api_key: tests that call external APIs")
