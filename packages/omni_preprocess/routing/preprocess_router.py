# packages/omni_preprocess/routing/preprocess_router.py
from pathlib import Path
from ..backends.stirling_client import StirlingPDFClient

class PreprocessRouter:
    """يقرر متى يستخدم Stirling PDF لتحضير المستندات."""

    NEEDS_PREPROCESS = {
        ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp",
    }

    def __init__(self, stirling_url: str = "http://localhost:8080"):
        self.client = StirlingPDFClient(base_url=stirling_url)

    def should_preprocess(self, path: str, quality: str = "unknown") -> dict:
        """يقرر إذا كان المستند يحتاج preprocessing."""
        suffix = Path(path).suffix.lower()

        if suffix not in self.NEEDS_PREPROCESS:
            return {"preprocess": False, "reason": "Format not supported"}

        if quality == "poor":
            return {
                "preprocess": True,
                "reason": "Poor quality scan — needs deskew + clean",
                "operations": ["deskew", "clean"],
            }

        return {
            "preprocess": True,
            "reason": "Default pre-processing for OCR readiness",
            "operations": ["deskew", "clean"],
        }

    def preprocess(self, input_path: str, output_path: str,
                   operations: list = None) -> dict:
        """يُنفذ preprocessing."""
        operations = operations or ["deskew", "clean"]

        result = self.client.ocr_preprocess(
            input_path=input_path,
            output_path=output_path,
            languages=["ara", "eng"],
            deskew="deskew" in operations,
            clean="clean" in operations,
        )

        return {
            "output_path": result.output_path,
            "success": result.success,
            "operations_applied": operations,
            "processing_time_ms": result.processing_time_ms,
            "errors": result.errors,
        }
