"""
Parsers package for Medical Handwriting OCR (HF Spaces Edition).

Provides document parsing, table extraction, equation recognition,
medical image processing, and medical-specific object detection.

Imports are wrapped in try/except for graceful degradation when optional
dependencies (marker-pdf, python-docx, etc.) are unavailable.
"""

try:
    from app.parsers.document_parser import (
        DocumentParser,
        DocumentParseResult,
        ImageContent,
        PageContent,
        TableContent,
    )
except ImportError:
    DocumentParser = None
    DocumentParseResult = None
    PageContent = None
    TableContent = None
    ImageContent = None

try:
    from app.parsers.table_extractor import (
        TableData,
        TableExtractor,
    )
except ImportError:
    TableExtractor = None
    TableData = None

try:
    from app.parsers.equation_parser import (
        EquationParser,
        EquationRegion,
    )
except ImportError:
    EquationParser = None
    EquationRegion = None

try:
    from app.parsers.image_processor import (
        DetectedObject,
        MedicalImageProcessor,
        MedicalImageResult,
        RegionClassification,
    )
except ImportError:
    MedicalImageProcessor = None
    MedicalImageResult = None
    DetectedObject = None
    RegionClassification = None

try:
    from app.parsers.medical_detector import (
        MedicalElements,
        MedicalObjectDetector,
        PrescriptionBlock,
    )
except ImportError:
    MedicalObjectDetector = None
    MedicalElements = None
    PrescriptionBlock = None

# BatchProcessor requires Celery — skip on HF Spaces
BatchProcessor = None
BatchJob = None
BatchStatus = None
BatchResult = None
PatientBatchResult = None

__all__ = [
    "BatchJob",
    "BatchProcessor",
    "BatchResult",
    "BatchStatus",
    "DetectedObject",
    "DocumentParseResult",
    "DocumentParser",
    "EquationParser",
    "EquationRegion",
    "ImageContent",
    "MedicalElements",
    "MedicalImageProcessor",
    "MedicalImageResult",
    "MedicalObjectDetector",
    "PageContent",
    "PatientBatchResult",
    "PrescriptionBlock",
    "RegionClassification",
    "TableContent",
    "TableData",
    "TableExtractor",
]
