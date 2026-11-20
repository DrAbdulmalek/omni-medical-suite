<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 91 | حُفظ: 2026-10-08 -->

# omni-ocr-core Foundation — Phase 1 of 8 Master Prompt

# مراجعة التدقيق + البرومبت المقترح

## 🎯 أولاً: حكمي على تدقيق Mistral

**التدقيق ممتاز، وأثبت ثلاث حقائق حرجة كان يجب أن نعرفها قبل الآن:**

| # | الاكتشاف | الخطورة |
|---|---|---|
| 1 | **نظامان OCR متوازيان** في omni-medical-suite: `packages/omni_ocr/adapter.py` + `packages/vision/ocr_engine.py` | 🔴 CRITICAL |
| 2 | **5 مخططات نتائج غير متوافقة** + **4 تمثيلات مختلفة** لـBoundingBox | 🔴 CRITICAL |
| 3 | **PR #135 (ATR Phase) وPR #134/119/118/130 مفتوحة** وغير مدموجة في `main` | 🟠 HIGH |

**هذه هي جوهر المشكلة.** لم يكن لديك مشكلة "تشتت بين مستودعات" فقط — لديك **انفصام داخلي في المستودع الرئيسي** نفسه.

---

## ⚠️ ثانياً: مشاكل البرومبت المقترح لـZ.ai

البرومبت الذي كتبته جيد في الروح، لكن فيه **15 مشكلة تقنية** قد تجعل Z.ai يبني حزمة **ناقصة** أو **متعارضة مع التدقيق**. هذه أهمها:

### 1. تناقض في مسار الحزمة

**المشكلة:** تقول `packages/omni-ocr-core` (بشرطة) ثم `src/omni_ocr/` (بشرطة سفلية).

**الإصلاح:** حسم المسار:
```
packages/omni_ocr_core/
├── pyproject.toml          (name = "omni-ocr-core")
├── src/omni_ocr/           (import name = "omni_ocr")
└── tests/
```
القاعدة: **الاسم في PyPI يستخدم شرطة، الاستيراد يستخدم شرطة سفلية.**

### 2. حقل `language` و`script` و`rtl` مفقود

**المشكلة:** التدقيق ذكر صراحة "Arabic RTL/mixed-script"، لكن الـSchema المقترح لا يحتوي على:
- `language: str` (ar, en, mixed)
- `script: str` (arabic, latin, mixed)
- `rtl_direction: bool`

**الإصلاح:** أضفها إلى `TokenResult` و`OCRResult`.

### 3. حقل `alternatives` مفقود

**المشكلة:** التدقيق ذكر أن `OCRResult` في `adapter.py:57` يحمل `alternatives`. الـSchema الجديد **يحذفها**.

**الأثر:** ستفقد إمكانية عرض بدائل من محركات مختلفة — وهذا **قلب مشروعك**.

**الإصلاح:** أضف:
```python
alternatives: List[EngineAlternative] = []
```

### 4. `ExtractionResult` مفقود

**المشكلة:** التدقيق يذكر أن OLMoCR/Xberg يحتاجان عقد استخراج منفصل. البرومبت **لا يذكرها**.

**الإصلاح:** أضف ملف `contract/extraction.py` مع `ExtractionResult`.

### 5. إصدارات الاعتماديات لا تحل التعارضات

**المشكلة:** التدقيق وجد:
- `transformers`: 4.35 vs 4.57
- `torch`: 2.0 vs 2.7
- `numpy`: <2.0 في HF فقط

البرومبت يقترح `transformers>=4.45.0` — هذا **لا يحل التعارض**.

**الإصلاح:**
```toml
dependencies = [
    "torch>=2.7.0,<3.0",
    "transformers>=4.57.3,<5.0",
    "numpy>=1.26.0,<2.1.0",
    "pydantic>=2.9.0,<3.0",
    "Pillow>=10.0.0",
]
```

### 6. لا يوجد `py.typed` marker

**المشكلة:** بدون `py.typed`، mypy لن يفحص الحزمة.

**الإصلاح:** أضف `src/omni_ocr/py.typed` (ملف فارغ).

### 7. `__version__.py` مفقود

**المشكلة:** لا يوجد مصدر وحيد للإصدار.

**الإصلاح:** أضف `src/omni_ocr/__version__.py`:
```python
__version__ = "0.1.0"
```

### 8. لا يوجد Backward Compatibility Strategy

**المشكلة:** البرومبت يقول "لا تكسر الاستيرادات" لكن لا يشرح **كيف**.

**الإصلاح:** حدد إحدى الاستراتيجيات:
- **Option A:** Shim layer في `omni-medical-suite/packages/omni_ocr/__init__.py` يعيد التصدير من الحزمة الجديدة.
- **Option B:** نسخ المحرك القديم مع DeprecationWarning.

### 9. لا يوجد `.gitignore` للحزمة

**الإصلاح:** أضف:
```
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
```

### 10. لا يوجد pytest config

**الإصلاح:** أضف إلى `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=omni_ocr --cov-report=term-missing"
```

### 11. لا يوجد Linting/Formatting

**الإصلاح:** أضف:
```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
```

### 12. اختبارات ناقصة

**المشكلة:** البرومبت يطلب `test_schema.py` فقط. يجب أن يشمل:
- `test_schema.py` — Pydantic validation
- `test_bounding_box.py` — التحويلات
- `test_provenance.py` — التسلسل والاسترجاع
- `test_alternatives.py` — البدائل
- `test_backward_compat.py` — الشيم

### 13. لا يوجد CI/CD

**الإصلاح:** أضف `.github/workflows/test.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest
```

### 14. تفاصيل `BaseOCREngine` ناقصة

**المشكلة:** الواجهة لا تحدد:
- هل `process_image` يقبل PDF؟
- هل يجب أن يعيد `alternatives`؟
- كيف يتعامل مع الأخطاء؟

**الإصلاح:** وسّع الـinterface.

### 15. لا يوجد Migration Roadmap

**المشكلة:** البرومبت يبني الحزمة **دون خطة** لكيفية نقل المحركات.

**الإصلاح:** أضف قسم "Phase 2 + 3 Outlook" يوضح الخطوات التالية.

---

## ✅ البرومبت المُصحّح (V2) — جاهز للنسخ

هذا هو الإصدار المصحّح. **انسخه كاملاً وأرسله إلى Z.ai.**

```markdown
# MASTER PROMPT — omni-ocr-core Foundation (Phase 1 of 8)
## Unified OCR Library Setup — License, Contract, Base Interface, Tests, CI

## 0. Role & Context

You are a Senior Python Architect + Open-Source Standardizer.

**Mission:** Set up the foundational skeleton of `omni-ocr-core` — 
the unified OCR library that will consolidate ALL OCR engines from 
DrAbdulmalek's repositories (Tesseract, Paddle, EasyOCR, TrOCR, Surya, 
QARI, Nougat, Qwen, OLMoCR, Xberg).

**Audit basis:** docs/audit/MISTRAL_REPOSITORY_AUDIT.md (PR #143)
which found 5 incompatible OCRResult schemas, 4 BoundingBox 
representations, and 2 parallel OCR systems in omni-medical-suite.

**This phase produces ONLY:** package skeleton + contract + base 
interface + tests + CI. NO engine migration. NO modification of 
existing repos. NO push to main.

---

## 1. Hard Constraints

### 1.1 FORBIDDEN
- Modifying any existing file in omni-medical-suite
- Modifying any archived repository
- Migrating any engine (that's Phase 2+)
- Deleting any file
- Pushing to main
- Creating secrets or API keys
- Downloading models
- Running servers

### 1.2 REQUIRED
- Work in NEW directory: packages/omni_ocr_core/
- Use branch: feature/omni-ocr-core-foundation
- Commit as you go (small logical commits)
- Each commit must pass tests
- Push after every successful commit

### 1.3 VERIFICATION
Before starting, verify:
```bash
git -C /home/z/my-project/repos/omni-medical-suite status
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
test -d /home/z/my-project/repos/omni-medical-suite/packages/omni_ocr_core && echo "EXISTS - STOP" || echo "OK - proceed"
```

If `packages/omni_ocr_core` exists, STOP and report.

---

## 2. Task Scope — Phase 1 Only

### 2.1 Package Structure

Create EXACTLY this tree (no additions, no omissions):

```
packages/omni_ocr_core/
├── LICENSE
├── README.md
├── pyproject.toml
├── .gitignore
├── .github/
│   └── workflows/
│       └── test.yml
├── src/
│   └── omni_ocr/
│       ├── __init__.py
│       ├── __version__.py
│       ├── py.typed
│       ├── contract/
│       │   ├── __init__.py
│       │   ├── bounding_box.py
│       │   ├── token.py
│       │   ├── provenance.py
│       │   ├── alternative.py
│       │   ├── result.py
│       │   └── extraction.py
│       ├── engines/
│       │   ├── __init__.py
│       │   └── base.py
│       └── exceptions.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── contract/
    │   ├── __init__.py
    │   ├── test_bounding_box.py
    │   ├── test_token.py
    │   ├── test_provenance.py
    │   ├── test_alternative.py
    │   ├── test_result.py
    │   └── test_extraction.py
    └── engines/
        ├── __init__.py
        └── test_base.py
```

### 2.2 LICENSE

Standard MIT License, Copyright (c) 2026 Dr. Abdulmalek Al-Husseini.

### 2.3 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "omni-ocr-core"
version = "0.1.0"
description = "Unified OCR library for Arabic medical documents"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "Dr. Abdulmalek Al-Husseini" }
]
keywords = ["ocr", "arabic", "medical", "htr", "handwriting"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Image Recognition",
]

dependencies = [
    "pydantic>=2.9.0,<3.0",
    "Pillow>=10.0.0",
    "numpy>=1.26.0,<2.1.0",
    "python-dateutil>=2.8.0",
]

[project.optional-dependencies]
engines = [
    "pytesseract>=0.3.10",
    "paddleocr>=2.9.0",
    "easyocr>=1.7.0",
    "transformers>=4.57.3,<5.0",
    "torch>=2.7.0,<3.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/omni_ocr"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --strict-markers --cov=omni_ocr --cov-report=term-missing"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
```

### 2.4 .gitignore

```
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.DS_Store
*.log
```

### 2.5 Contract — BoundingBox

`src/omni_ocr/contract/bounding_box.py`:

```python
"""Standardized bounding box representation.

Supports both:
- Rectangle form: (x, y, width, height)
- Polygon form: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
"""

from __future__ import annotations
from typing import Union, List, Tuple
from pydantic import BaseModel, Field, model_validator


Point = Tuple[float, float]


class BoundingBox(BaseModel):
    """Standardized bounding box for OCR tokens.
    
    Internally stores both representations. Use factory methods
    to create from either form.
    """
    
    model_config = {"frozen": True}
    
    x: float
    y: float
    width: float
    height: float
    polygon: List[Point] = Field(default_factory=list)
    
    @classmethod
    def from_xywh(cls, x: float, y: float, w: float, h: float) -> "BoundingBox":
        """Create from (x, y, width, height)."""
        polygon = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return cls(x=x, y=y, width=w, height=h, polygon=polygon)
    
    @classmethod
    def from_polygon(cls, points: List[Point]) -> "BoundingBox":
        """Create from 4-point polygon (RTL-aware)."""
        if len(points) != 4:
            raise ValueError(f"Polygon must have exactly 4 points, got {len(points)}")
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x, y = min(xs), min(ys)
        w = max(xs) - x
        h = max(ys) - y
        return cls(x=x, y=y, width=w, height=h, polygon=points)
    
    @classmethod
    def from_htr(cls, bbox: List[List[float]]) -> "BoundingBox":
        """Create from HTR-style bbox: [[x,y], [x,y], [x,y], [x,y]]."""
        return cls.from_polygon([(float(p[0]), float(p[1])) for p in bbox])
    
    def to_xywh(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)
    
    def to_polygon(self) -> List[Point]:
        if self.polygon:
            return self.polygon
        return [(self.x, self.y), (self.x + self.width, self.y),
                (self.x + self.width, self.y + self.height),
                (self.x, self.y + self.height)]
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Point:
        return (self.x + self.width / 2, self.y + self.height / 2)
```

### 2.6 Contract — Provenance

`src/omni_ocr/contract/provenance.py`:

```python
"""Full lineage tracking for every OCR result."""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Complete audit trail for an OCR operation."""
    
    model_config = {"frozen": True}
    
    engine_name: str
    engine_version: str
    
    pdf_sha256: Optional[str] = None
    source_path: Optional[str] = None
    
    execution_time_ms: float = 0.0
    cloud_provider: Optional[str] = None
    cloud_cost_usd: Optional[float] = 0.0
    
    preprocessing_applied: list[str] = Field(default_factory=list)
    profiles_used: list[str] = Field(default_factory=list)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    extra: Dict[str, Any] = Field(default_factory=dict)
```

### 2.7 Contract — Token

`src/omni_ocr/contract/token.py`:

```python
"""Single recognized token (word or phrase)."""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .bounding_box import BoundingBox


Language = Literal["ar", "en", "mixed", "unknown"]
Script = Literal["arabic", "latin", "mixed", "unknown"]


class TokenResult(BaseModel):
    """A single OCR-recognized token."""
    
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None
    
    language: Language = "unknown"
    script: Script = "unknown"
    rtl: bool = False
    
    is_medical_term: bool = False
    is_critical: bool = False
    
    source_engine: Optional[str] = None
```

### 2.8 Contract — Alternative

`src/omni_ocr/contract/alternative.py`:

```python
"""Alternative OCR candidate from a different engine."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class EngineAlternative(BaseModel):
    """An alternative OCR output (from a different engine)."""
    
    engine_name: str
    engine_version: Optional[str] = None
    text: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rank: int = 0
    notes: Optional[str] = None
```

### 2.9 Contract — OCRResult

`src/omni_ocr/contract/result.py`:

```python
"""The Master OCR Contract — single source of truth."""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .token import TokenResult, Language, Script
from .provenance import Provenance
from .alternative import EngineAlternative


class PageResult(BaseModel):
    """One page of OCR output."""
    
    page_number: int
    width: int
    height: int
    tokens: List[TokenResult] = Field(default_factory=list)
    text: str = ""


class OCRResult(BaseModel):
    """Canonical OCR result — used by ALL engines.
    
    This is the single source of truth for OCR output across
    the entire omni-medical ecosystem.
    """
    
    raw_text: str
    normalized_text: Optional[str] = None
    
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    language: Language = "unknown"
    script: Script = "unknown"
    rtl: bool = False
    
    pages: List[PageResult] = Field(default_factory=list)
    alternatives: List[EngineAlternative] = Field(default_factory=list)
    
    provenance: Provenance
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
```

### 2.10 Contract — ExtractionResult

`src/omni_ocr/contract/extraction.py`:

```python
"""Extraction result for document-structuring layers (Xberg, Docling)."""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .provenance import Provenance


class ExtractionResult(BaseModel):
    """Result from document extraction backends."""
    
    text: str
    markdown: str = ""
    structured: Dict[str, Any] = Field(default_factory=dict)
    
    format: str = "text"
    mime_type: str = ""
    
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    
    source_path: str = ""
    page_count: int = 0
    
    confidence: Optional[float] = None
    provenance: Provenance
    
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
```

### 2.11 Base Interface

`src/omni_ocr/engines/base.py`:

```python
"""Abstract base class for all OCR engines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, List, Optional
from PIL import Image

from ..contract.result import OCRResult


ImageInput = Union[str, Path, Image.Image, bytes]


class BaseOCREngine(ABC):
    """Abstract interface for all OCR engine drivers.
    
    Every engine (Tesseract, Paddle, EasyOCR, TrOCR, Surya, etc.)
    MUST inherit from this class and implement all abstract methods.
    """
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Unique identifier (e.g., 'tesseract', 'paddle')."""
        ...
    
    @property
    @abstractmethod
    def engine_version(self) -> str:
        """Version string of the engine."""
        ...
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine dependencies are installed."""
        ...
    
    @abstractmethod
    def process_image(
        self,
        image: ImageInput,
        language: str = "ara+eng",
        return_tokens: bool = True,
        **kwargs,
    ) -> OCRResult:
        """Process a single image and return standardized OCRResult.
        
        Args:
            image: Path, PIL Image, or bytes
            language: Language hint (e.g., "ara", "eng", "ara+eng")
            return_tokens: If True, populate TokenResult list
            **kwargs: Engine-specific options
        
        Returns:
            OCRResult with full provenance
        
        Raises:
            EngineNotAvailableError: If engine not installed
            OCRProcessingError: If processing fails
        """
        ...
    
    def process_batch(
        self,
        images: List[ImageInput],
        **kwargs,
    ) -> List[OCRResult]:
        """Process multiple images. Default: sequential."""
        return [self.process_image(img, **kwargs) for img in images]
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.engine_name} v{self.engine_version}>"
```

### 2.12 Exceptions

`src/omni_ocr/exceptions.py`:

```python
"""Unified exception hierarchy for omni-ocr-core."""


class OmniOCRError(Exception):
    """Base exception for all OCR errors."""


class EngineNotAvailableError(OmniOCRError):
    """Engine dependencies not installed."""


class OCRProcessingError(OmniOCRError):
    """OCR processing failed."""


class ContractValidationError(OmniOCRError):
    """Result doesn't match the OCRResult contract."""


class PrivacyViolationError(OmniOCRError):
    """External transmission attempted without consent."""
```

### 2.13 `__init__.py` الرئيسي

`src/omni_ocr/__init__.py`:

```python
"""omni-ocr-core — Unified OCR library for Arabic medical documents."""

from .__version__ import __version__
from .contract.bounding_box import BoundingBox
from .contract.token import TokenResult
from .contract.provenance import Provenance
from .contract.alternative import EngineAlternative
from .contract.result import OCRResult, PageResult
from .contract.extraction import ExtractionResult
from .engines.base import BaseOCREngine
from .exceptions import (
    OmniOCRError,
    EngineNotAvailableError,
    OCRProcessingError,
    ContractValidationError,
    PrivacyViolationError,
)

__all__ = [
    "__version__",
    "BoundingBox",
    "TokenResult",
    "Provenance",
    "EngineAlternative",
    "OCRResult",
    "PageResult",
    "ExtractionResult",
    "BaseOCREngine",
    "OmniOCRError",
    "EngineNotAvailableError",
    "OCRProcessingError",
    "ContractValidationError",
    "PrivacyViolationError",
]
```

### 2.14 Tests

اكتب اختبارات شاملة لكل ملف في القسم 2.13. كل اختبار يجب أن يغطي:
- الحالة الطبيعية (Happy path)
- الحالات الحدية (Empty, Zero, Negative)
- التحويلات (xywh ↔ polygon ↔ htr)
- التحقق من Pydantic (validation errors)
- Serialization/Deserialization (JSON round-trip)

على الأقل **30 اختباراً** يمرون بـ`pytest`.

### 2.15 CI Workflow

`.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main, feature/*]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      
      - name: Lint with ruff
        run: ruff check src/ tests/
      
      - name: Type check with mypy
        run: mypy src/
      
      - name: Run tests
        run: pytest
```

---

## 3. Execution Steps

Execute in this EXACT order:

1. **Verify** environment (see Section 1.3). If package exists → STOP.
2. **Create branch** `feature/omni-ocr-core-foundation`.
3. **Create directory** `packages/omni_ocr_core/`.
4. **Write files** in this order:
   - LICENSE
   - .gitignore
   - pyproject.toml
   - README.md
   - src/omni_ocr/__version__.py
   - src/omni_ocr/py.typed (empty)
   - src/omni_ocr/exceptions.py
   - src/omni_ocr/contract/bounding_box.py
   - src/omni_ocr/contract/token.py
   - src/omni_ocr/contract/provenance.py
   - src/omni_ocr/contract/alternative.py
   - src/omni_ocr/contract/result.py
   - src/omni_ocr/contract/extraction.py
   - src/omni_ocr/engines/base.py
   - src/omni_ocr/__init__.py
   - All `__init__.py` files
   - All test files
   - .github/workflows/test.yml
5. **Install** in editable mode: `pip install -e ".[dev]"`.
6. **Run tests**: `pytest -v`.
7. **Run ruff**: `ruff check src/ tests/`.
8. **Run mypy**: `mypy src/`.
9. **Fix** any issues.
10. **Commit** in logical chunks:
    - Commit 1: LICENSE + pyproject + .gitignore + README
    - Commit 2: Contract (all 6 files)
    - Commit 3: Engines base + exceptions
    - Commit 4: Tests
    - Commit 5: CI workflow
11. **Push** branch.
12. **Create PR** with title: `feat: omni-ocr-core foundation (Phase 1/8)`.
13. **Report** results.

---

## 4. What You MUST NOT Do

- ❌ Do NOT migrate any engine. That's Phase 2.
- ❌ Do NOT modify omni-medical-suite files.
- ❌ Do NOT modify archived repos.
- ❌ Do NOT push to main.
- ❌ Do NOT touch PR #143 (Mistral audit).
- ❌ Do NOT install heavy dependencies (torch, paddle) — only dev deps.
- ❌ Do NOT add engines dependencies to core (they're in `[engines]` extra).

---

## 5. STOP CONDITIONS

Stop immediately and report if:
1. `packages/omni_ocr_core` already exists.
2. Any test fails and cannot be fixed within 2 attempts.
3. `pip install -e` fails due to dependency conflicts.
4. Git push fails 3 times.
5. Any secret/PHI detected.

---

## 6. Required Report

At the end, provide:

```
=== OMNI-OCR-CORE FOUNDATION — PHASE 1 ===

BRANCH:                  feature/omni-ocr-core-foundation
HEAD SHA:                <full>
REMOTE SHA:              <verified>
PR URL:                  <url>

FILES CREATED:           <count>
LINES OF CODE:           <count>
TESTS:                   <X passing / Y total>
RUFF:                    <clean | N warnings>
MYPY:                    <clean | N errors>

CONTRACT SCHEMAS:
  - BoundingBox          ✅ (xywh + polygon + htr)
  - TokenResult          ✅ (language + script + rtl)
  - Provenance           ✅ (full lineage)
  - EngineAlternative    ✅
  - OCRResult            ✅ (master contract)
  - ExtractionResult     ✅ (for Xberg/Docling)

DEPENDENCIES:
  - pydantic>=2.9.0
  - Pillow>=10.0.0
  - numpy>=1.26.0,<2.1.0
  - python-dateutil>=2.8.0

EXTRA: engines (torch, transformers, paddleocr, etc.) — NOT installed

PROVEN:
  - <list>
  
PARTIALLY PROVEN:
  - <list>

BLOCKED:
  - <list>

NEXT PHASE:
  Phase 2 — Migrate Tesseract + EasyOCR to omni-ocr-core
  (requires explicit authorization)

FINAL REMINDER: Foundation only. No engines migrated.
No repos modified. PR awaits review.
```

---

## 7. Final Principle

```
Phase 1 = Foundation only.
No engines. No migration. No breakage.

Every file justified.
Every test passing.
Every commit clean.

If in doubt, STOP and ask.
```

**Begin now. Complete Phase 1. Then STOP.**
```

---

## 📋 ما بعد التنفيذ (خارطة الطريق)

بعد أن ينجح Z.ai في Phase 1، سيكون لديك أساس صلب. هذه المراحل التالية:

| المرحلة | المدة | المخرج |
|---|---|---|
| **Phase 2** | أسبوع | نقل Tesseract + EasyOCR |
| **Phase 3** | أسبوع | نقل Paddle + TrOCR |
| **Phase 4** | أسبوع | نقل Surya + QARI + Nougat + Qwen |
| **Phase 5** | أسبوع | نقل OLMoCR + Xberg adapters |
| **Phase 6** | أسبوع | Router + Profiles |
| **Phase 7** | أسبوع | Normalization (RTL) + Validation |
| **Phase 8** | أسبوع | Shim layer + deprecation |

---

## 🎯 ثلاث توصيات أخيرة

### 1. **لا تدمج PR #143 قبل أن تقرأه كاملاً**

التدقيق يحتوي على 7 ملفات. راجع كل ملف قبل الدمج. خاصة `security_findings.csv` — فيه 6 findings يجب أن تفهمها.

### 2. **أغلق PRs #118, #119, #130 أو ادمجها**

التدقيق كشف أن هذه PRs تحتوي إصلاحات أمنية حرجة (pickle، shell injection) لم تُدمج في `main`. هذا يعني أن `main` **غير آمن حالياً**.

### 3. **PR #135 (ATR Phase) يجب أن يُدمج أولاً أو يُغلق**

إذا كان ATR Phase مكتملاً، ادمجه. إذا لم يكن، أغلق الفرع. وجود 6 PRs مفتوحة = فوضى.

---

**ابدأ بإرسال البرومبت المُصحّح لـZ.ai. عندما يعود بالنتيجة، شاركها معي وسأراجعها قبل Phase 2.**
