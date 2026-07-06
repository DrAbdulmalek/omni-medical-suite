# -*- coding: utf-8 -*-
"""Dictionary service tests for the OmniMedical Suite.

Validates data models (MedicalTerm, DictionarySource), the BGL importer,
and the high-level MedicalDictionary API using in-memory SQLite databases.

Run with::

    pytest tests/test_dictionary.py -v
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Generator

import pytest


# ---------------------------------------------------------------------------
# Model tests — MedicalTerm and DictionarySource
# ---------------------------------------------------------------------------

class TestMedicalTerm:
    """Tests for the MedicalTerm data-class serialisation round-trips."""

    def test_to_dict_round_trip(self) -> None:
        """to_dict → from_dict preserves all fields."""
        from services.dictionary.models import MedicalTerm, TermCategory, TermLanguage

        original = MedicalTerm(
            id="t-001",
            canonical="myocarditis",
            synonyms=["carditis"],
            category=TermCategory.DIAGNOSIS,
            language=TermLanguage.ENGLISH,
            definition="Inflammation of the heart muscle.",
            source="Stedman's",
            confidence=0.92,
            metadata={"icd10": "I40.9"},
        )
        data = original.to_dict()
        restored = MedicalTerm.from_dict(data)

        assert restored.id == original.id
        assert restored.canonical == original.canonical
        assert restored.synonyms == original.synonyms
        assert restored.category == original.category
        assert restored.language == original.language
        assert restored.confidence == original.confidence
        assert restored.metadata["icd10"] == "I40.9"

    def test_from_dict_string_enums(self) -> None:
        """from_dict accepts category/language as plain strings."""
        from services.dictionary.models import MedicalTerm, TermCategory, TermLanguage

        term = MedicalTerm.from_dict({
            "canonical": "carditis",
            "category": "diagnosis",
            "language": "english",
            "confidence": 0.85,
        })
        assert isinstance(term.category, TermCategory)
        assert isinstance(term.language, TermLanguage)
        assert term.category == TermCategory.DIAGNOSIS


class TestDictionarySource:
    """Tests for the DictionarySource data-class serialisation round-trips."""

    def test_to_dict_round_trip(self) -> None:
        """to_dict → from_dict preserves all fields."""
        from services.dictionary.models import DictionarySource, TermLanguage

        original = DictionarySource(
            id="src-001",
            name="Stedman's Medical Dictionary",
            filename="stedmans.bgl",
            language=TermLanguage.ENGLISH,
            term_count=15000,
            status="imported",
            checksum="a" * 64,
        )
        restored = DictionarySource.from_dict(original.to_dict())

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.term_count == original.term_count
        assert restored.status == original.status
        assert restored.language == original.language


# ---------------------------------------------------------------------------
# BGLMedicalImporter tests
# ---------------------------------------------------------------------------

class TestBGLMedicalImporter:
    """Tests for the BGL dictionary importer using in-memory SQLite."""

    @pytest.fixture()
    def importer(self) -> Generator[Any, None, None]:
        """Create an importer backed by an in-memory SQLite database."""
        from services.dictionary.bgl_importer import BGLMedicalImporter
        tmpdir = tempfile.mkdtemp(prefix="dict_test_")
        imp = BGLMedicalImporter(data_dir=tmpdir)
        # Manually insert test data via raw SQL.
        import sqlite3, json
        db_path = imp._db_path
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO terms
                   (id, canonical, synonyms, category, language, definition, source, confidence, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("h001", "myocarditis", json.dumps(["carditis"]), "diagnosis", "english",
                 "Inflammation of the heart muscle.", "test", 0.90, json.dumps({}), "2025-01-01T00:00:00"),
            )
            conn.execute(
                """INSERT OR REPLACE INTO terms
                   (id, canonical, synonyms, category, language, definition, source, confidence, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("h002", "pneumonia", json.dumps([]), "diagnosis", "english",
                 "Infection of the lungs.", "test", 0.85, json.dumps({}), "2025-01-01T00:00:00"),
            )
            conn.commit()
        yield imp

    def test_search_exact(self, importer: Any) -> None:
        """Search returns terms matching the exact canonical name."""
        results = importer.search("myocarditis")
        assert len(results) >= 1
        assert results[0].canonical == "myocarditis"

    def test_search_fuzzy(self, importer: Any) -> None:
        """Search returns partial / LIKE matches."""
        results = importer.search("card")
        assert len(results) >= 1

    def test_search_by_language(self, importer: Any) -> None:
        """Search with a language filter narrows results."""
        from services.dictionary.models import TermLanguage
        results = importer.search("myocarditis", language=TermLanguage.ENGLISH)
        assert len(results) >= 1
        assert all(r.language == TermLanguage.ENGLISH for r in results)

    def test_stats(self, importer: Any) -> None:
        """get_stats returns aggregate statistics."""
        stats = importer.get_stats()
        assert stats["total_terms"] >= 2
        assert stats["by_language"]["english"] >= 2


# ---------------------------------------------------------------------------
# MedicalDictionary tests
# ---------------------------------------------------------------------------

class TestMedicalDictionary:
    """Tests for the high-level MedicalDictionary API."""

    @pytest.fixture()
    def dictionary(self) -> Generator[Any, None, None]:
        """Create a dictionary with pre-seeded in-memory data."""
        from services.dictionary.medical_dictionary import MedicalDictionary
        tmpdir = tempfile.mkdtemp(prefix="med_dict_test_")
        # Seed the underlying database.
        import sqlite3, json
        db_path = os.path.join(tmpdir, "medical_dict.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS terms (
                    id TEXT PRIMARY KEY, canonical TEXT NOT NULL,
                    synonyms TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL DEFAULT 'diagnosis',
                    language TEXT NOT NULL DEFAULT 'english',
                    definition TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )""")
            terms = [
                ("t1", "myocarditis", json.dumps(["carditis"]), "diagnosis", 0.92,
                 "Heart muscle inflammation."),
                ("t2", "pneumonia", json.dumps([]), "diagnosis", 0.88,
                 "Lung infection."),
                ("t3", "aspirin", json.dumps(["acetylsalicylic acid"]), "medication", 0.95,
                 "Antiplatelet drug."),
            ]
            for t in terms:
                conn.execute(
                    """INSERT INTO terms
                       (id, canonical, synonyms, category, language, definition, source, confidence, metadata, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (t[0], t[1], t[2], t[3], "english", t[5], "test", t[4], json.dumps({}), "2025-01-01"),
                )
            conn.commit()

        yield MedicalDictionary(data_dir=tmpdir)

    def test_lookup_exact(self, dictionary: Any) -> None:
        """lookup finds a term by canonical name."""
        result = dictionary.lookup("myocarditis")
        assert result is not None
        assert result.canonical == "myocarditis"

    def test_lookup_synonym(self, dictionary: Any) -> None:
        """lookup resolves a synonym to its canonical term."""
        result = dictionary.lookup("carditis")
        assert result is not None
        assert result.canonical == "myocarditis"

    def test_lookup_missing(self, dictionary: Any) -> None:
        """lookup returns None for unknown terms."""
        assert dictionary.lookup("xyznonexistent") is None

    def test_search(self, dictionary: Any) -> None:
        """search returns partial matches."""
        results = dictionary.search("card")
        assert len(results) >= 1

    def test_validate_term(self, dictionary: Any) -> None:
        """validate_term returns True for existing terms."""
        assert dictionary.validate_term("pneumonia") is True
        assert dictionary.validate_term("nonexistent") is False

    def test_suggest_corrections(self, dictionary: Any) -> None:
        """suggest_corrections returns similar canonical terms."""
        suggestions = dictionary.suggest_corrections("mycardites", threshold=0.6)
        canonicals = [s[0] for s in suggestions]
        assert "myocarditis" in canonicals

    def test_enrich_text(self, dictionary: Any) -> None:
        """enrich_text identifies medical terms in free text."""
        results = dictionary.enrich_text("Patient has myocarditis and takes aspirin.")
        terms_found = [r["term"] for r in results]
        assert "myocarditis" in terms_found
        assert "aspirin" in terms_found

    def test_add_custom_term(self, dictionary: Any) -> None:
        """add_custom_term inserts a term that is immediately visible."""
        from services.dictionary.models import MedicalTerm, TermCategory, TermLanguage

        term = MedicalTerm(
            canonical="ceftriaxone",
            category=TermCategory.MEDICATION,
            language=TermLanguage.ENGLISH,
            definition="Third-generation cephalosporin.",
            confidence=0.95,
        )
        success = dictionary.add_custom_term(term)
        assert success is True

        looked_up = dictionary.lookup("ceftriaxone")
        assert looked_up is not None
        assert looked_up.definition == "Third-generation cephalosporin."
