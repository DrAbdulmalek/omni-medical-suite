"""Specialty-aware runtime router for dictionary resources.

Rules:
- OCR uses only audited exact-token correction maps.
- Terminology dictionaries are lookup/protection resources, never substring replacement.
- TMX is exact-segment lookup only.
- Translation rules are suggestions for a translation engine; this router does not
  execute arbitrary regex/string replacement.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .dictionary_registry import (
    DictionarySpec,
    canonical_specialty,
    protected_terms_for_specialty,
    specs_for_specialty,
)
from .medical_dictionary_loader import normalize_arabic_key


class SpecialtyDictionaryRouter:
    def __init__(self, specialty: str | None = "general_medical") -> None:
        self.specialty = canonical_specialty(specialty)
        self._specs = specs_for_specialty(self.specialty)
        self._term_index: dict[str, list[dict[str, Any]]] | None = None

    @property
    def specs(self) -> tuple[DictionarySpec, ...]:
        return tuple(self._specs)

    def set_specialty(self, specialty: str | None) -> None:
        self.specialty = canonical_specialty(specialty)
        self._specs = specs_for_specialty(self.specialty)
        self._term_index = None

    def protected_terms(self) -> set[str]:
        return protected_terms_for_specialty(self.specialty)

    def _build_term_index(self) -> dict[str, list[dict[str, Any]]]:
        if self._term_index is not None:
            return self._term_index
        index: dict[str, list[dict[str, Any]]] = {}
        for spec in self._specs:
            if spec.role != "terminology" or not spec.path.exists():
                continue
            if spec.format == "medical_json":
                data = json.loads(spec.path.read_text(encoding="utf-8"))
                pairs = (data.get("arabic_corrections") or {})
                for source, target in pairs.items():
                    self._add_term(index, source, target, spec)
            elif spec.format == "ortho_json":
                data = json.loads(spec.path.read_text(encoding="utf-8"))
                for category, values in (data.get("categories") or {}).items():
                    ar = values.get("arabic") or []
                    en = values.get("english") or []
                    for term in ar + en:
                        self._add_term(index, term, term, spec, category)
            elif spec.format == "csv":
                with spec.path.open(encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        en = (row.get("en") or "").strip()
                        ar = (row.get("ar") or "").strip()
                        if en and ar:
                            self._add_term(index, en, ar, spec, row.get("type") or "term")
                            self._add_term(index, ar, en, spec, row.get("type") or "term")
        self._term_index = index
        return index

    @staticmethod
    def _add_term(index: dict[str, list[dict[str, Any]]], source: str, target: str, spec: DictionarySpec, category: str = "term") -> None:
        key = normalize_arabic_key(source)
        if not key:
            return
        index.setdefault(key, []).append({
            "source": source,
            "target": target,
            "dictionary": spec.name,
            "specialty": spec.specialty,
            "category": category,
            "role": spec.role,
        })

    def lookup_term_exact(self, text: str) -> list[dict[str, Any]]:
        """Exact whole-input terminology lookup. Never modifies input text."""
        if not text or not text.strip():
            return []
        return list(self._build_term_index().get(normalize_arabic_key(text), ()))

    def ocr_corrections(self) -> dict[str, str]:
        """Return only audited OCR maps applicable to the current specialty."""
        result: dict[str, str] = {}
        for spec in self._specs:
            if spec.role != "ocr_correction" or spec.format != "json_map" or not spec.path.exists():
                continue
            data = json.loads(spec.path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, str):
                    result[key] = value
        return result

    def translation_memory_sources(self) -> list[Path]:
        return [s.path for s in self._specs if s.role == "translation_memory" and s.path.exists()]

    def translation_rule_sources(self) -> list[Path]:
        return [s.path for s in self._specs if s.role == "translation_rule" and s.path.exists()]

    def describe(self) -> dict[str, Any]:
        return {
            "specialty": self.specialty,
            "sources": [
                {
                    "name": s.name,
                    "path": str(s.path),
                    "role": s.role,
                    "available": s.path.exists(),
                }
                for s in self._specs
            ],
            "protected_term_count": len(self.protected_terms()),
        }
