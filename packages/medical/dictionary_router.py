"""Specialty-aware runtime router for dictionary resources.

Each source keeps its semantic role: OCR corrections, protected lexicon,
terminology, TMX, and translation rules are not interchangeable maps.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .dictionary_registry import (
    DictionarySpec,
    canonical_specialty,
    protected_lexicon_terms,
    protected_terms_for_specialty,
    specs_for_specialty,
)
from .medical_dictionary_loader import normalize_arabic_key


class SpecialtyDictionaryRouter:
    def __init__(self, specialty: str | None = "general_medical") -> None:
        self.specialty = canonical_specialty(specialty)
        self._specs = specs_for_specialty(self.specialty)
        self._term_index: dict[str, list[dict[str, Any]]] | None = None
        self._translation_index: dict[str, list[dict[str, Any]]] | None = None

    @property
    def specs(self) -> tuple[DictionarySpec, ...]:
        return tuple(self._specs)

    def set_specialty(self, specialty: str | None) -> None:
        self.specialty = canonical_specialty(specialty)
        self._specs = specs_for_specialty(self.specialty)
        self._term_index = None
        self._translation_index = None

    def protected_terms(self) -> set[str]:
        return protected_terms_for_specialty(self.specialty)

    def protected_lexicon(self) -> set[str]:
        """Return protected vocabulary only; never expose it as replacements."""
        terms: set[str] = set()
        for spec in self._specs:
            if spec.role == "protected_lexicon":
                terms.update(protected_lexicon_terms(spec))
        return terms

    def _build_term_index(self) -> dict[str, list[dict[str, Any]]]:
        if self._term_index is not None:
            return self._term_index
        index: dict[str, list[dict[str, Any]]] = {}
        for spec in self._specs:
            if spec.role != "terminology" or not spec.path.exists():
                continue
            if spec.format == "medical_json":
                data = json.loads(spec.path.read_text(encoding="utf-8"))
                pairs = data.get("arabic_corrections") or {}
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

    def _build_translation_index(self) -> dict[str, list[dict[str, Any]]]:
        """Build only from explicitly bilingual translation resources.

        OCR correction dictionaries and specialty lexicons are deliberately
        excluded: their values are not guaranteed to be translations.
        """
        if self._translation_index is not None:
            return self._translation_index
        index: dict[str, list[dict[str, Any]]] = {}
        for spec in self._specs:
            if spec.role != "terminology" or spec.format != "csv" or not spec.path.exists():
                continue
            with spec.path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    en = (row.get("en") or "").strip()
                    ar = (row.get("ar") or "").strip()
                    if not en or not ar:
                        continue
                    self._add_translation(index, en, ar, spec, "en", "ar", row.get("type") or "term")
                    self._add_translation(index, ar, en, spec, "ar", "en", row.get("type") or "term")
        self._translation_index = index
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

    @staticmethod
    def _add_translation(index: dict[str, list[dict[str, Any]]], source: str, target: str, spec: DictionarySpec, source_lang: str, target_lang: str, category: str) -> None:
        key = normalize_arabic_key(source)
        if not key:
            return
        index.setdefault(key, []).append({
            "source": source,
            "target": target,
            "source_lang": source_lang,
            "target_lang": target_lang,
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

    def lookup_translation_exact(self, text: str, target_lang: str) -> list[dict[str, Any]]:
        """Exact whole-input lookup from bilingual glossary resources only."""
        if not text or not text.strip():
            return []
        return [
            item for item in self._build_translation_index().get(normalize_arabic_key(text), ())
            if item["target_lang"] == target_lang
        ]

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

    def translation_memory_specs(self) -> tuple[DictionarySpec, ...]:
        """Return all configured TM sources, including unavailable artifacts."""
        return tuple(s for s in self._specs if s.role == "translation_memory")

    def missing_translation_memory_artifacts(self) -> list[DictionarySpec]:
        """Return configured optional specialty artifacts that are not installed."""
        return [
            s for s in self.translation_memory_specs()
            if s.runtime == "optional_artifact" and not s.path.exists()
        ]

    def specialty_translation_memory_specs(self) -> tuple[DictionarySpec, ...]:
        """Return configured TM resources for the exact canonical specialty."""
        return tuple(
            s for s in self.translation_memory_specs()
            if s.specialty == self.specialty and s.runtime == "optional_artifact"
        )

    def translation_memory_sources(self, *, require_specialty_artifact: bool = False) -> list[Path]:
        """Return installed TM paths with optional fail-closed specialty validation."""
        specialty_specs = self.specialty_translation_memory_specs()
        missing_specialty = [s for s in specialty_specs if not s.path.exists()]
        if require_specialty_artifact and specialty_specs and missing_specialty:
            names = ", ".join(
                str(s.path.relative_to(Path(__file__).resolve().parents[2]))
                for s in missing_specialty
            )
            raise RuntimeError(
                f"Specialty translation-memory artifact is not installed for "
                f"{self.specialty!r}: {names}"
            )
        return [s.path for s in self.translation_memory_specs() if s.path.exists()]

    def translation_rule_sources(self) -> list[Path]:
        return [s.path for s in self._specs if s.role == "translation_rule" and s.path.exists()]

    def describe(self) -> dict[str, Any]:
        return {
            "specialty": self.specialty,
            "sources": [
                {"name": s.name, "path": str(s.path), "role": s.role, "available": s.path.exists()}
                for s in self._specs
            ],
            "protected_term_count": len(self.protected_terms()),
        }
