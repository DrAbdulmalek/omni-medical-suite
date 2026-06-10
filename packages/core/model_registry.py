"""
packages/core/model_registry.py
=================================
سجل النماذج المدرّبة — نُقل من packages/omni-core/

يتتبع:
  - إصدارات النماذج (TrOCR، PaddleOCR، نماذج مخصصة)
  - مسارات الأوزان والـ metadata
  - تقييمات الدقة لكل إصدار
  - اختيار أفضل نموذج بحسب اللغة والجودة
"""

from __future__ import annotations

import json
import os
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MODEL_REGISTRY_PATH = os.environ.get(
    "MODEL_REGISTRY_PATH",
    "./models/registry.json"
)


@dataclass
class ModelEntry:
    """وصف نموذج OCR مسجّل."""
    model_id: str
    name: str
    engine: str                      # trocr | paddleocr | tesseract | custom
    version: str
    language: str                    # ar | en | mixed
    weights_path: str
    accuracy: float = 0.0            # 0.0–1.0
    cer: float = 0.0                 # Character Error Rate
    wer: float = 0.0                 # Word Error Rate
    training_samples: int = 0
    is_active: bool = True
    is_default: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""
    checksum: Optional[str] = None

    def __post_init__(self):
        if not self.checksum and os.path.isfile(self.weights_path):
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        h = hashlib.md5()
        with open(self.weights_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @property
    def is_valid(self) -> bool:
        return os.path.isfile(self.weights_path)

    def to_dict(self) -> dict:
        return asdict(self)


class ModelRegistry:
    """
    سجل النماذج — يُحمَّل من JSON ويُحفظ إليه.

    الاستخدام:
        registry = ModelRegistry()
        registry.register(ModelEntry(...))
        best = registry.get_best(language="ar", engine="trocr")
    """

    def __init__(self, registry_path: str = MODEL_REGISTRY_PATH):
        self._path = Path(registry_path)
        self._models: dict[str, ModelEntry] = {}
        self._load()

    # ── CRUD ──────────────────────────────────────────────────

    def register(self, entry: ModelEntry, overwrite: bool = False) -> None:
        """سجّل نموذجاً جديداً."""
        if entry.model_id in self._models and not overwrite:
            raise ValueError(f"Model '{entry.model_id}' already exists. Use overwrite=True.")
        if not entry.is_valid:
            logger.warning(f"Model weights not found at {entry.weights_path} — registering anyway")
        self._models[entry.model_id] = entry
        self._save()
        logger.info(f"Registered model: {entry.model_id} (v{entry.version}, {entry.language})")

    def get(self, model_id: str) -> Optional[ModelEntry]:
        return self._models.get(model_id)

    def remove(self, model_id: str) -> bool:
        if model_id in self._models:
            del self._models[model_id]
            self._save()
            return True
        return False

    def update_accuracy(
        self, model_id: str, accuracy: float, cer: float = 0.0, wer: float = 0.0
    ) -> None:
        """حدّث تقييم دقة نموذج بعد التقييم على بيانات جديدة."""
        if model_id not in self._models:
            raise KeyError(f"Model '{model_id}' not found")
        self._models[model_id].accuracy = round(accuracy, 4)
        self._models[model_id].cer = round(cer, 4)
        self._models[model_id].wer = round(wer, 4)
        self._save()

    def set_default(self, model_id: str, language: str) -> None:
        """عيّن نموذجاً كافتراضي للغة معينة."""
        for m in self._models.values():
            if m.language == language:
                m.is_default = False
        if model_id in self._models:
            self._models[model_id].is_default = True
            self._save()

    def deactivate(self, model_id: str) -> None:
        if model_id in self._models:
            self._models[model_id].is_active = False
            self._save()

    # ── Query ─────────────────────────────────────────────────

    def list_all(self, active_only: bool = True) -> list[ModelEntry]:
        models = list(self._models.values())
        if active_only:
            models = [m for m in models if m.is_active]
        return sorted(models, key=lambda m: m.accuracy, reverse=True)

    def list_by_engine(self, engine: str, active_only: bool = True) -> list[ModelEntry]:
        return [m for m in self.list_all(active_only) if m.engine == engine]

    def list_by_language(self, language: str, active_only: bool = True) -> list[ModelEntry]:
        return [
            m for m in self.list_all(active_only)
            if m.language in (language, "mixed")
        ]

    def get_best(
        self,
        language: str = "ar",
        engine: Optional[str] = None,
        min_accuracy: float = 0.0,
    ) -> Optional[ModelEntry]:
        """أعد أفضل نموذج متاح بحسب اللغة والمحرك والدقة."""
        candidates = self.list_by_language(language)
        if engine:
            candidates = [m for m in candidates if m.engine == engine]
        candidates = [m for m in candidates if m.accuracy >= min_accuracy]
        if not candidates:
            return None
        # فضّل النموذج الافتراضي أولاً، ثم الأعلى دقةً
        defaults = [m for m in candidates if m.is_default]
        if defaults:
            return defaults[0]
        return candidates[0]

    def get_default(self, language: str) -> Optional[ModelEntry]:
        for m in self._models.values():
            if m.language == language and m.is_default and m.is_active:
                return m
        return None

    def summary(self) -> dict:
        models = self.list_all()
        return {
            "total_models": len(models),
            "by_engine":    self._count_by(models, "engine"),
            "by_language":  self._count_by(models, "language"),
            "avg_accuracy": round(sum(m.accuracy for m in models) / max(len(models), 1), 4),
            "best_arabic":  self.get_best("ar").model_id if self.get_best("ar") else None,
            "best_english": self.get_best("en").model_id if self.get_best("en") else None,
        }

    # ── Persistence ───────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            logger.info(f"Model registry not found at {self._path} — starting empty")
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for entry_data in data.get("models", []):
                entry = ModelEntry(**entry_data)
                self._models[entry.model_id] = entry
            logger.info(f"Loaded {len(self._models)} models from registry")
        except Exception as exc:
            logger.error(f"Failed to load registry: {exc}")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "2.0",
            "updated_at": datetime.utcnow().isoformat(),
            "models": [m.to_dict() for m in self._models.values()],
        }
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _count_by(models: list[ModelEntry], attr: str) -> dict:
        counts: dict = {}
        for m in models:
            key = getattr(m, attr, "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts
