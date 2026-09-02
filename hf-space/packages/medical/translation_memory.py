"""Exact-match translation memory service.

Translation memory is a lookup/suggestion system, not a text replacement engine.
It never calls str.replace() and never edits substrings inside arbitrary text.
Potential PII-bearing TM segments are rejected at runtime as an additional safety
boundary, even if an upstream extraction filter was bypassed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List

from .dictionary_registry import canonical_specialty
from .dictionary_router import SpecialtyDictionaryRouter
from .medical_dictionary_loader import normalize_arabic_key

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+\s*[0-9٠-٩][0-9٠-٩\s().-]{7,}[0-9٠-٩])(?!\w)")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)


def contains_runtime_pii(text: str) -> bool:
    """Reject obvious contact/identifier material from runtime TM."""
    if not text:
        return False
    return bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text) or _URL_RE.search(text))


class ExactTranslationMemory:
    """Exact sentence/phrase lookup with provenance and no arbitrary replacement."""

    def __init__(self, entries: Iterable[dict] = ()) -> None:
        self._index: Dict[str, List[dict]] = {}
        for entry in entries:
            source = str(entry.get("key", entry.get("en", ""))).strip()
            target = str(entry.get("value", entry.get("ar", ""))).strip()
            if not source or not target:
                continue
            # TMX is corpus data, so contact information must never become a
            # runtime translation memory entry, regardless of provenance.
            if contains_runtime_pii(source) or contains_runtime_pii(target):
                continue
            key = normalize_arabic_key(source)
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
        """Build TM from sources applicable to the selected specialty.

        A configured specialty artifact is fail-closed: requesting a specific
        specialty must not silently degrade to general TM when that specialty's
        generated artifact has not been installed.
        """
        canonical = canonical_specialty(specialty)
        router = SpecialtyDictionaryRouter(canonical)
        require_specialty_artifact = canonical not in {"general", "general_medical"}
        all_entries: list[dict] = []
        for path in router.translation_memory_sources(
            require_specialty_artifact=require_specialty_artifact
        ):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries = data.get("entries", data) if isinstance(data, dict) else data
                if not isinstance(entries, list):
                    raise ValueError("expected a JSON list of translation-memory entries")
                for entry in entries:
                    if isinstance(entry, dict):
                        enriched = dict(entry)
                        enriched.setdefault("source", f"{path.name}:tmx")
                        enriched.setdefault("category", "translation_memory")
                        all_entries.append(enriched)
            except (json.JSONDecodeError, OSError, UnicodeError, TypeError, ValueError) as e:
                raise RuntimeError(
                    f"Specialty TM artifact is corrupted or unreadable: {path}: {e}"
                ) from e
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
