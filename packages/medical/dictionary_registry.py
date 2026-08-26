"""Registry for every dictionary-like source in the repository.

The registry separates *what a source is* from *how it may be applied*.
Large terminology resources are never exposed as blind text replacements.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DictionarySpec:
    name: str
    path: Path
    specialty: str
    role: str
    format: str
    runtime: str
    description: str


DICTIONARY_REGISTRY: tuple[DictionarySpec, ...] = (
    DictionarySpec("arabic_ocr_fixes", ROOT / "data/arabic_fixes.json", "general", "ocr_correction", "json_map", "ocr-safe spelling corrections"),
    DictionarySpec("safe_ocr_corrections", ROOT / "data/dictionaries/ocr_corrections_safe.json", "general", "ocr_correction", "json_map", "audited OCR corrections"),
    DictionarySpec("general_correction_seed", ROOT / "data/correction_dict_seed.json", "general", "protected_lexicon", "json_map", "general/technical vocabulary; not a replacement dictionary"),
    DictionarySpec("medical_dictionary", ROOT / "data/medical_dictionary.json", "general_medical", "terminology", "medical_json", "general medical and orthopedic terminology"),
    DictionarySpec("orthopedic_lexicon", ROOT / "data/ortho_lexicon.json", "orthopedic_surgery", "terminology", "ortho_json", "orthopedic surgery terminology"),
    DictionarySpec("medical_glossary", ROOT / "data/arabic-medical-glossary/glossaries/final_unified_glossary.csv", "general_medical", "terminology", "csv", "medical bilingual glossary"),
    DictionarySpec("malek_tmx", ROOT / "data/dictionaries/malek_data_terms.json", "general_medical", "translation_memory", "entries_json", "extracted TMX translation memory"),
    DictionarySpec("translation_rules", ROOT / "data/translation_rules.json", "general", "translation_rule", "rules_json", "structural and grammatical translation rules"),
)

# These are corpora/training resources, not dictionaries and must not be routed
# into runtime correction or translation replacement.
NON_DICTIONARY_RESOURCES = {
    "data/learning_database.json": "learning database",
    "data/medical_doc_training.jsonl": "training corpus",
    "data/ground_truth_588.txt": "evaluation ground truth",
}

SPECIALTY_ALIASES = {
    "ortho": "orthopedic_surgery",
    "orthopedics": "orthopedic_surgery",
    "orthopaedics": "orthopedic_surgery",
    "orthopedic": "orthopedic_surgery",
    "orthopedic surgery": "orthopedic_surgery",
    "trauma": "orthopedic_surgery",
    "medicine": "general_medical",
    "medical": "general_medical",
    "general": "general",
}


def canonical_specialty(value: str | None) -> str:
    value = (value or "general").strip().lower()
    return SPECIALTY_ALIASES.get(value, value)


def specs_for_specialty(specialty: str | None) -> list[DictionarySpec]:
    """Return sources applicable to a specialty, ordered deterministically."""
    specialty = canonical_specialty(specialty)
    selected: list[DictionarySpec] = []
    for spec in DICTIONARY_REGISTRY:
        if spec.specialty == "general" or spec.specialty == specialty:
            selected.append(spec)
    return selected


def registry_manifest() -> list[dict[str, Any]]:
    return [
        {
            "name": s.name,
            "path": str(s.path.relative_to(ROOT)),
            "specialty": s.specialty,
            "role": s.role,
            "format": s.format,
            "runtime": s.runtime,
            "description": s.description,
            "available": s.path.exists(),
        }
        for s in DICTIONARY_REGISTRY
    ]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def terminology_terms(spec: DictionarySpec) -> set[str]:
    """Extract terms for protection/recognition, never replacement."""
    if not spec.path.exists() or spec.role != "terminology":
        return set()
    data = _read_json(spec.path)
    terms: set[str] = set()
    if spec.format == "medical_json":
        terms.update((data.get("arabic_corrections") or {}).keys())
        terms.update((data.get("arabic_corrections") or {}).values())
        return {t.strip() for t in terms if isinstance(t, str) and t.strip()}
    if spec.format == "ortho_json":
        for category in (data.get("categories") or {}).values():
            for language in ("arabic", "english"):
                terms.update(category.get(language) or [])
        return {t.strip() for t in terms if isinstance(t, str) and t.strip()}
    return terms


def protected_terms_for_specialty(specialty: str | None) -> set[str]:
    terms: set[str] = set()
    for spec in specs_for_specialty(specialty):
        terms.update(terminology_terms(spec))
    return terms
