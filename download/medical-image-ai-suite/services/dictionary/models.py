# -*- coding: utf-8 -*-
"""Data models for the medical dictionary service.

Defines enumerations and data-classes that represent medical terms,
dictionary sources, and supporting metadata used throughout the
OmniMedical Suite dictionary pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TermCategory(str, Enum):
    """Semantic category for a medical term."""

    ANATOMY = "anatomy"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    SYMPTOM = "symptom"
    LAB_TEST = "lab_test"
    IMAGING = "imaging"
    SPECIALTY = "specialty"
    ABBREVIATION = "abbreviation"


class TermLanguage(str, Enum):
    """Language of a medical term or dictionary source."""

    ARABIC = "arabic"
    ENGLISH = "english"
    FRENCH = "french"
    LATIN = "latin"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MedicalTerm:
    """A single medical terminology entry.

    Attributes
    ----------
    id:
        Unique persistent identifier (UUID string or auto-generated).
    canonical:
        Primary / preferred spelling of the term.
    synonyms:
        Alternative spellings or recognised variants.
    category:
        Semantic classification (see :class:`TermCategory`).
    language:
        Language of the term (see :class:`TermLanguage`).
    definition:
        Human-readable description or explanation.
    source:
        Origin dictionary or reference work.
    confidence:
        Numerical confidence score in the range ``[0.0, 1.0]``.
    metadata:
        Arbitrary key-value pairs for extensions.
    created_at:
        ISO-8601 timestamp of when the record was created.
    """

    id: str = ""
    canonical: str = ""
    synonyms: List[str] = field(default_factory=list)
    category: TermCategory = TermCategory.DIAGNOSIS
    language: TermLanguage = TermLanguage.ENGLISH
    definition: str = ""
    source: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the term to a plain :class:`dict` suitable for JSON."""
        data = asdict(self)
        data["category"] = self.category.value
        data["language"] = self.language.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MedicalTerm":
        """Deserialise a plain dictionary into a :class:`MedicalTerm`.

        Enum fields (``category`` / ``language``) are accepted as either
        raw enum members or their string ``.value`` equivalents.
        """
        if "category" in data and not isinstance(
            data["category"], TermCategory
        ):
            data["category"] = TermCategory(data["category"])
        if "language" in data and not isinstance(
            data["language"], TermLanguage
        ):
            data["language"] = TermLanguage(data["language"])
        return cls(**data)


@dataclass
class DictionarySource:
    """Metadata about an imported dictionary file.

    Attributes
    ----------
    id:
        Unique identifier for the source record.
    name:
        Human-readable name (e.g. ``"Stedman's Medical Dictionary"``).
    filename:
        Original file name on disk.
    language:
        Primary language of the dictionary.
    term_count:
        Number of terms successfully imported.
    imported_at:
        ISO-8601 timestamp of the import operation.
    checksum:
        SHA-256 digest of the source file for integrity checks.
    status:
        Import status – one of ``"pending"``, ``"imported"``, ``"failed"``.
    """

    id: str = ""
    name: str = ""
    filename: str = ""
    language: TermLanguage = TermLanguage.ENGLISH
    term_count: int = 0
    imported_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    checksum: str = ""
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the source record to a plain dictionary."""
        data = asdict(self)
        data["language"] = self.language.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DictionarySource":
        """Deserialise a dictionary into a :class:`DictionarySource`."""
        if "language" in data and not isinstance(
            data["language"], TermLanguage
        ):
            data["language"] = TermLanguage(data["language"])
        return cls(**data)
