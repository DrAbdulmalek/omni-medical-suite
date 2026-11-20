"""Runtime-aware engine registry with availability checks.

Each OCR engine is represented by an ``EngineAdapter`` that knows how to:
- Check whether the engine is actually importable at runtime (``is_available``)
- Run a lightweight health check without loading heavy model weights
  (``healthcheck``)
- Report resource requirements (``estimated_ram_gb``, ``supported_tasks``)

The ``EngineRegistry`` collects all adapters and lets ``EngineRouter``
filter its recommendations by *actual* availability rather than static
profile strings.
"""

from __future__ import annotations

import importlib
import logging
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ────────────────────────────────────────────────────

@dataclass(frozen=True)
class EngineInfo:
    """Immutable snapshot of an engine's capabilities and status."""

    name: str
    available: bool
    healthy: bool
    estimated_ram_gb: float
    supported_tasks: List[str]
    load_time_ms: float
    error: Optional[str] = None


# ── Abstract adapter ───────────────────────────────────────────────

class EngineAdapter(ABC):
    """Base class for OCR engine adapters."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def estimated_ram_gb(self) -> float: ...

    @property
    @abstractmethod
    def supported_tasks(self) -> List[str]: ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine's core package is importable."""

    @abstractmethod
    def healthcheck(self) -> Dict[str, Any]:
        """Run a lightweight check. Must not load model weights.

        Returns a dict with at least:
        - ``ok`` (bool)
        - ``error`` (str | None)
        - ``version`` (str | None)
        - ``details`` (dict)
        """

    def probe(self) -> EngineInfo:
        """Full probe: availability + healthcheck with timing."""
        if not self.is_available():
            return EngineInfo(
                name=self.name,
                available=False,
                healthy=False,
                estimated_ram_gb=self.estimated_ram_gb,
                supported_tasks=self.supported_tasks,
                load_time_ms=0.0,
                error="package not importable",
            )

        t0 = time.perf_counter()
        hc = self.healthcheck()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return EngineInfo(
            name=self.name,
            available=True,
            healthy=hc.get("ok", False),
            estimated_ram_gb=self.estimated_ram_gb,
            supported_tasks=self.supported_tasks,
            load_time_ms=round(elapsed_ms, 1),
            error=hc.get("error"),
        )


# ── Concrete adapters ───────────────────────────────────────────────

class _EasyOCRAdapter(EngineAdapter):
    name = "EasyOCR"
    estimated_ram_gb = 1.5
    supported_tasks = ["printed", "arabic", "mixed", "handwriting"]

    def is_available(self) -> bool:
        return _can_import("easyocr")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import easyocr
            return {"ok": True, "version": getattr(easyocr, "__version__", "unknown"), "details": {}}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _TesseractAdapter(EngineAdapter):
    name = "Tesseract"
    estimated_ram_gb = 0.5
    supported_tasks = ["printed", "arabic", "latin", "low_quality"]

    def is_available(self) -> bool:
        return _can_import("pytesseract") and _has_binary("tesseract")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import pytesseract
            v = pytesseract.get_tesseract_version()
            return {"ok": True, "version": str(v), "details": {"lang_count": len(_tesseract_langs())}}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _TrOCRAdapter(EngineAdapter):
    name = "TrOCR"
    estimated_ram_gb = 3.5
    supported_tasks = ["handwriting", "printed", "latin", "arabic"]

    def is_available(self) -> bool:
        return _can_import("transformers") and _can_import("torch")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import torch
            return {
                "ok": True,
                "version": f"torch {torch.__version__}",
                "details": {"cuda": torch.cuda.is_available(), "device_count": torch.cuda.device_count()},
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _PaddleOCRAdapter(EngineAdapter):
    name = "PaddleOCR"
    estimated_ram_gb = 4.0
    supported_tasks = ["printed", "arabic", "table", "layout"]

    def is_available(self) -> bool:
        return _can_import("paddleocr")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import paddleocr
            return {"ok": True, "version": getattr(paddleocr, "__version__", "unknown"), "details": {}}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _QwenHandwrittenAdapter(EngineAdapter):
    name = "Arabic-handwritten-OCR (Qwen)"
    estimated_ram_gb = 5.5
    supported_tasks = ["handwriting", "arabic"]

    def is_available(self) -> bool:
        return _can_import("transformers") and _can_import("torch") and _can_import("qwen_vl_utils")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import torch
            import transformers
            return {
                "ok": True,
                "version": f"transformers {transformers.__version__}",
                "details": {"cuda": torch.cuda.is_available(), "qwen_vl": True},
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _QARIAdapter(EngineAdapter):
    name = "QARI"
    estimated_ram_gb = 4.5
    supported_tasks = ["arabic", "vocalized", "tashkeel", "printed"]

    def is_available(self) -> bool:
        return _can_import("transformers") and _can_import("torch")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import torch
            return {
                "ok": True,
                "version": f"torch {torch.__version__}",
                "details": {"cuda": torch.cuda.is_available()},
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


class _NougatAdapter(EngineAdapter):
    name = "Nougat"
    estimated_ram_gb = 4.5
    supported_tasks = ["structured", "table", "form", "report", "academic"]

    def is_available(self) -> bool:
        return _can_import("nougat")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            import nougat
            return {"ok": True, "version": getattr(nougat, "__version__", "unknown"), "details": {}}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "version": None, "details": {}}


# ── Helpers ─────────────────────────────────────────────────────────

def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _has_binary(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def _tesseract_langs() -> List[str]:
    try:
        import pytesseract
        return pytesseract.get_languages()
    except Exception:
        return []


# ── Registry ────────────────────────────────────────────────────────

class EngineRegistry:
    """Central registry that probes engine availability at runtime.

    Usage::

        reg = EngineRegistry()
        reg.discover()                        # probe all adapters

        print(reg.available_engine_names())   # ['EasyOCR', 'Tesseract']
        print(reg.health_report())            # full dict

        # Integrate with EngineRouter:
        available = reg.available_engine_names()
        router.select(language="ar", ...)     # filtered by actual availability
    """

    # Default adapter classes to register on ``discover()``.
    DEFAULT_ADAPTERS: List[type[EngineAdapter]] = [
        _EasyOCRAdapter,
        _TesseractAdapter,
        _TrOCRAdapter,
        _PaddleOCRAdapter,
        _QwenHandwrittenAdapter,
        _QARIAdapter,
        _NougatAdapter,
    ]

    def __init__(self, adapters: Optional[List[EngineAdapter]] = None) -> None:
        self._adapters: Dict[str, EngineAdapter] = {}
        if adapters:
            for a in adapters:
                self._adapters[a.name] = a
        self._probed: Dict[str, EngineInfo] = {}

    def register(self, adapter: EngineAdapter) -> None:
        """Manually register an adapter (useful for custom engines)."""
        self._adapters[adapter.name] = adapter

    def discover(self, adapter_classes: Optional[List[type[EngineAdapter]]] = None) -> None:
        """Instantiate default (or provided) adapters and probe them."""
        classes = adapter_classes or self.DEFAULT_ADAPTERS
        for cls in classes:
            adapter = cls()
            self._adapters[adapter.name] = adapter
            info = adapter.probe()
            self._probed[adapter.name] = info
            level = logging.DEBUG if info.available else logging.INFO
            logger.log(
                level,
                "Engine %s: available=%s healthy=%s ram=%.1fGB (%.0fms)",
                info.name, info.available, info.healthy,
                info.estimated_ram_gb, info.load_time_ms,
            )

    def available_engine_names(self) -> List[str]:
        """Return names of engines that are both available AND healthy."""
        return [
            name for name, info in self._probed.items()
            if info.available and info.healthy
        ]

    def get_info(self, name: str) -> Optional[EngineInfo]:
        return self._probed.get(name)

    def health_report(self) -> Dict[str, Dict[str, Any]]:
        """Return full health report for all probed engines."""
        return {
            name: {
                "available": info.available,
                "healthy": info.healthy,
                "estimated_ram_gb": info.estimated_ram_gb,
                "supported_tasks": info.supported_tasks,
                "load_time_ms": info.load_time_ms,
                "error": info.error,
            }
            for name, info in self._probed.items()
        }

    def filter_by_ram(self, engine_names: List[str], available_ram_gb: float) -> List[str]:
        """Return only the engines that fit within the RAM budget."""
        result: List[str] = []
        total = 0.0
        for name in engine_names:
            info = self._probed.get(name)
            ram = info.estimated_ram_gb if info else 1.0
            if total + ram <= available_ram_gb:
                result.append(name)
                total += ram
        return result if result else engine_names[:1]  # keep at least one