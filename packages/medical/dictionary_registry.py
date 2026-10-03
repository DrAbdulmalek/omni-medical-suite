"""Registry for every dictionary-like source in the repository.

The registry separates what a source is from how it may be applied. Large
terminology resources are never exposed as blind text replacements.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    DictionarySpec("arabic_ocr_fixes", ROOT / "data/arabic_fixes.json", "general", "ocr_correction", "json_map", "loaded", "OCR-safe spelling corrections"),
    DictionarySpec("safe_ocr_corrections", ROOT / "data/dictionaries/ocr_corrections_safe.json", "general", "ocr_correction", "json_map", "loaded", "audited OCR corrections"),
    DictionarySpec("general_correction_seed", ROOT / "data/correction_dict_seed.json", "general", "protected_lexicon", "json_map", "loaded", "general/technical vocabulary; not a replacement dictionary"),
    DictionarySpec("medical_dictionary", ROOT / "data/medical_dictionary.json", "general_medical", "terminology", "medical_json", "loaded", "general medical terminology"),
    DictionarySpec("orthopedic_lexicon", ROOT / "data/ortho_lexicon.json", "orthopedic_surgery", "terminology", "ortho_json", "loaded", "orthopedic surgery terminology"),
    DictionarySpec("medical_glossary", ROOT / "data/arabic-medical-glossary/glossaries/final_unified_glossary.csv", "general_medical", "terminology", "csv", "loaded", "medical bilingual glossary"),
    DictionarySpec("malek_tmx", ROOT / "data/dictionaries/malek_data_terms.json", "general_medical", "translation_memory", "entries_json", "loaded", "extracted TMX translation memory"),
    # Generated specialty TM artifacts. They are optional repository artifacts:
    # the registry exposes them when installed, while runtime validation can
    # report an explicit missing artifact instead of silently pretending that a
    # specialty-specific TM is available.
    DictionarySpec("malek_tm_general_medical", ROOT / "data/dictionaries/specialty/general_medical.json", "general_medical", "translation_memory", "entries_json", "optional_artifact", "generated general medical TM"),
    DictionarySpec("malek_tm_orthopedic_surgery", ROOT / "data/dictionaries/specialty/orthopedic_surgery.json", "orthopedic_surgery", "translation_memory", "entries_json", "optional_artifact", "generated orthopedic surgery TM"),
    DictionarySpec("malek_tm_anatomy", ROOT / "data/dictionaries/specialty/anatomy.json", "anatomy", "translation_memory", "entries_json", "optional_artifact", "generated anatomy TM"),
    DictionarySpec("malek_tm_cardiovascular", ROOT / "data/dictionaries/specialty/cardiovascular.json", "cardiovascular", "translation_memory", "entries_json", "optional_artifact", "generated cardiovascular TM"),
    DictionarySpec("malek_tm_oncology", ROOT / "data/dictionaries/specialty/oncology.json", "oncology", "translation_memory", "entries_json", "optional_artifact", "generated oncology TM"),
    DictionarySpec("malek_tm_endocrinology", ROOT / "data/dictionaries/specialty/endocrinology.json", "endocrinology", "translation_memory", "entries_json", "optional_artifact", "generated endocrinology TM"),
    DictionarySpec("malek_tm_surgery_general", ROOT / "data/dictionaries/specialty/surgery_general.json", "surgery_general", "translation_memory", "entries_json", "optional_artifact", "generated general surgery TM"),
    DictionarySpec("malek_tm_abdomen_pelvis", ROOT / "data/dictionaries/specialty/abdomen_pelvis.json", "abdomen_pelvis", "translation_memory", "entries_json", "optional_artifact", "generated abdomen/pelvis TM"),
    DictionarySpec("translation_rules", ROOT / "data/translation_rules.json", "general", "translation_rule", "rules_json", "loaded", "structural and grammatical translation rules"),
)

NON_DICTIONARY_RESOURCES = {
    "data/learning_database.json": "learning database",
    "data/medical_doc_training.jsonl": "training corpus",
    "data/ground_truth_588.txt": "evaluation ground truth",
}

# Canonical names shared with MedicalClassifier.  The router must accept the
# classifier's actual category names; otherwise specialty routing can silently
# fall back to a non-existent namespace and become architectural dead code.
SPECIALTY_ALIASES = {
    "ortho": "orthopedic_surgery",
    "orthopedics": "orthopedic_surgery",
    "orthopaedics": "orthopedic_surgery",
    "orthopedic": "orthopedic_surgery",
    "orthopedic surgery": "orthopedic_surgery",
    "orthopedic_surgery": "orthopedic_surgery",
    "trauma": "orthopedic_surgery",
    "cardiology": "cardiovascular",
    "cardiovascular": "cardiovascular",
    "neurology": "neurology",
    "anatomy": "anatomy",
    "oncology": "oncology",
    "endocrinology": "endocrinology",
    "abdomen_pelvis": "abdomen_pelvis",
    "general_surgery": "surgery_general",
    "surgery": "surgery_general",
    "surgery_general": "surgery_general",
    "radiology": "radiology",
    "pathology": "pathology",
    "pharmacology": "pharmacology",
    "research": "research",
    "medical_admin": "medical_admin",
    "engineering": "engineering",
    "medicine": "general_medical",
    "medical": "general_medical",
    "general_medical": "general_medical",
    "general": "general",
}


def canonical_specialty(value: str | None) -> str:
    value = (value or "general").strip().lower()
    return SPECIALTY_ALIASES.get(value, value)


def specs_for_specialty(specialty: str | None) -> list[DictionarySpec]:
    """Return the general + medical inheritance chain + specialty sources."""
    specialty = canonical_specialty(specialty)
    if specialty == "general":
        allowed = {"general"}
    elif specialty == "general_medical":
        allowed = {"general", "general_medical"}
    else:
        allowed = {"general", "general_medical", specialty}
    return [s for s in DICTIONARY_REGISTRY if s.specialty in allowed]


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
    """Extract terminology for recognition/protection, never replacement."""
    if not spec.path.exists() or spec.role != "terminology":
        return set()
    terms: set[str] = set()
    if spec.format == "medical_json":
        data = _read_json(spec.path)
        pairs = data.get("arabic_corrections") or {}
        terms.update(pairs.keys())
        terms.update(pairs.values())
    elif spec.format == "ortho_json":
        data = _read_json(spec.path)
        for category in (data.get("categories") or {}).values():
            for language in ("arabic", "english"):
                terms.update(category.get(language) or [])
    elif spec.format == "csv":
        import csv as _csv
        with spec.path.open(encoding="utf-8", newline="") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                en = (row.get("en") or "").strip()
                ar = (row.get("ar") or "").strip()
                if en:
                    terms.add(en)
                if ar:
                    terms.add(ar)
    return {t.strip() for t in terms if isinstance(t, str) and t.strip()}


def protected_lexicon_terms(spec: DictionarySpec) -> set[str]:
    """Extract protected vocabulary without turning it into replacement rules."""
    if not spec.path.exists() or spec.role != "protected_lexicon":
        return set()
    data = _read_json(spec.path)
    if not isinstance(data, dict):
        return set()
    terms: set[str] = set()
    for key, value in data.items():
        if isinstance(key, str) and key.strip():
            terms.add(key.strip())
        if isinstance(value, str) and value.strip():
            terms.add(value.strip())
        elif isinstance(value, list):
            terms.update(str(v).strip() for v in value if str(v).strip())
    return terms


def protected_terms_for_specialty(specialty: str | None) -> set[str]:
    terms: set[str] = set()
    for spec in specs_for_specialty(specialty):
        if spec.role == "terminology":
            terms.update(terminology_terms(spec))
        elif spec.role == "protected_lexicon":
            terms.update(protected_lexicon_terms(spec))
    return terms
