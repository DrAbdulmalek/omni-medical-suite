"""Exact-match translation memory service.

Translation memory is a lookup/suggestion system, not a text replacement engine.
It never calls str.replace() and never edits substrings inside arbitrary text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from .dictionary_registry import canonical_specialty
from .dictionary_router import SpecialtyDictionaryRouter
from .medical_dictionary_loader import normalize_arabic_key


class ExactTranslationMemory:
    """Exact sentence/phrase lookup with provenance and no arbitrary replacement."""

    def __init__(self, entries: Iterable[dict] = ()) -> None:
        self._index: Dict[str, List[dict]] = {}
        for entry in entries:
            source = str(entry.get("key", entry.get("en", ""))).strip()
            target = str(entry.get("value", entry.get("ar", ""))).strip()
            if not source or not target:
                continue
            key = normalize_arabic_key(source)
            # Provenance: must be non-empty; fall back to "unknown" if missing
            provenance = str(entry.get("source", "") or "").strip() or "unknown"
            category = str(entry.get("category", "") or "").strip() or "translation_memory"
            self._index.setdefault(key, []).append({
                "source": source,
                "target": target,
                "provenance": provenance,
                "category": category,
            })

    @classmethod
    def from_json(cls, path: Path) -> "ExactTranslationMemory":
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", data) if isinstance(data, dict) else data
        return cls(entries)

    @classmethod
    def from_specialty(cls, specialty: str | None = "general_medical") -> "ExactTranslationMemory":
        """Build TM from only TMX sources applicable to the selected specialty."""
        router = SpecialtyDictionaryRouter(canonical_specialty(specialty))
        all_entries: list[dict] = []
        for path in router.translation_memory_sources():
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("entries", data) if isinstance(data, dict) else data
            for entry in entries:
                if isinstance(entry, dict):
                    enriched = dict(entry)
                    enriched.setdefault("source", f"{path.name}:tmx")
                    enriched.setdefault("category", "translation_memory")
                    all_entries.append(enriched)
        return cls(all_entries)

    def lookup_exact(self, text: str) -> List[dict]:
        """Return candidates only when the complete input is an indexed key."""
        if not text or not text.strip():
            return []
        return list(self._index.get(normalize_arabic_key(text), ()))

    def translate_exact(self, text: str) -> str | None:
        """Return a target only for an exact whole-input match; otherwise None."""
        matches = self.lookup_exact(text)
        if not matches:
            return None
        return matches[0]["target"]

    def contains_exact(self, text: str) -> bool:
        return bool(self.lookup_exact(text))
