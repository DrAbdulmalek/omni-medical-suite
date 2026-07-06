# -*- coding: utf-8 -*-
"""BGL dictionary importer for the OmniMedical Suite.

Handles importing medical terminology from Babylon Glossary (``.bgl``) files
into a local SQLite database, with optional JSON export for fast look-ups.

The module gracefully degrades when ``bglconverter`` is not installed: raw
BGL files cannot be parsed, but the rest of the pipeline (search, export,
statistics) remains fully functional against previously imported data.

Typical usage::

    importer = BGLMedicalImporter(data_dir="data/dictionary")
    importer.import_bgl_file("path/to/medical.bgl")
    results = importer.search("carditis")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DictionarySource,
    MedicalTerm,
    TermCategory,
    TermLanguage,
)

logger = logging.getLogger(__name__)

# Attempt to import the third-party BGL converter.
try:
    from bglconverter import reader as bgl_reader  # type: ignore[import-untyped]

    _HAS_BGL_CONVERTER = True
except ImportError:
    bgl_reader = None  # type: ignore[assignment]
    _HAS_BGL_CONVERTER = False


# ---------------------------------------------------------------------------
# Keyword maps for auto-categorisation
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "anatomy": [
        "artery", "vein", "nerve", "bone", "muscle", "ligament", "tendon",
        "organ", "lobe", "cortex", "ganglion", "fascia", "cartilage",
    ],
    "diagnosis": [
        "itis", "osis", "oma", "syndrome", "disease", "disorder",
        "failure", "insufficiency", "deficiency",
    ],
    "procedure": [
        "ectomy", "otomy", "ostomy", "plasty", "scopy", "puncture",
        "biopsy", "transplant", "resection",
    ],
    "medication": [
        "azole", "pril", "lol", "statin", "cillin", "mycin", "cidal",
        "capsule", "tablet", "injection", "syrup",
    ],
    "symptom": [
        "pain", "fever", "cough", "nausea", "fatigue", "dizziness",
        "headache", "bleeding", "swelling", "numbness",
    ],
    "lab_test": [
        "count", "panel", "culture", "assay", "titr", "level",
        "marker", "index", "ratio",
    ],
    "imaging": [
        "x-ray", "radiograph", "ultrasound", "mri", "ct scan",
        "pet scan", "angiogram", "mammogram",
    ],
    "specialty": [
        "cardiology", "oncology", "neurology", "dermatology",
        "orthopedics", "pediatrics", "psychiatry", "radiology",
    ],
}


class BGLMedicalImporter:
    """Import, store, and query medical terminology from BGL glossaries.

    Parameters
    ----------
    data_dir:
        Directory for the SQLite database, JSON exports, and working files.
    """

    def __init__(self, data_dir: str = "data/dictionary") -> None:
        self.data_dir: str = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._db_path: str = os.path.join(data_dir, "medical_dict.db")
        self._init_database()

    # -- Database initialisation --------------------------------------------

    def _init_database(self) -> None:
        """Create the SQLite schema if it does not already exist.

        Tables:
        * ``terms`` – canonical medical terms with category and language.
        * ``sources`` – metadata about imported dictionary files.
        * ``synonyms_index`` – fast synonym → term_id lookup.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS terms (
                    id          TEXT PRIMARY KEY,
                    canonical   TEXT NOT NULL,
                    synonyms    TEXT NOT NULL DEFAULT '[]',
                    category    TEXT NOT NULL DEFAULT 'diagnosis',
                    language    TEXT NOT NULL DEFAULT 'english',
                    definition  TEXT NOT NULL DEFAULT '',
                    source      TEXT NOT NULL DEFAULT '',
                    confidence  REAL NOT NULL DEFAULT 1.0,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_terms_canonical
                    ON terms(canonical);
                CREATE INDEX IF NOT EXISTS idx_terms_category
                    ON terms(category);
                CREATE INDEX IF NOT EXISTS idx_terms_language
                    ON terms(language);

                CREATE TABLE IF NOT EXISTS sources (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL DEFAULT '',
                    filename    TEXT NOT NULL DEFAULT '',
                    language    TEXT NOT NULL DEFAULT 'english',
                    term_count  INTEGER NOT NULL DEFAULT 0,
                    imported_at TEXT NOT NULL,
                    checksum    TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'pending'
                );

                CREATE TABLE IF NOT EXISTS synonyms_index (
                    synonym     TEXT NOT NULL,
                    term_id     TEXT NOT NULL,
                    PRIMARY KEY (synonym, term_id)
                );
                CREATE INDEX IF NOT EXISTS idx_synonyms_term_id
                    ON synonyms_index(term_id);
                """
            )
            conn.commit()

    # -- Utility methods ----------------------------------------------------

    def _compute_checksum(self, filepath: str) -> str:
        """Return the SHA-256 hex digest of *filepath*.

        Parameters
        ----------
        filepath:
            Absolute or relative path to the file.

        Returns
        -------
        str
            64-character hexadecimal checksum.
        """
        sha = hashlib.sha256()
        with open(filepath, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _detect_language(text: str) -> TermLanguage:
        """Guess the language of *text* based on Arabic character ranges.

        Falls back to :pyattr:`TermLanguage.ENGLISH` when no Arabic
        characters are detected.
        """
        if any("\u0600" <= ch <= "\u06FF" for ch in text):
            return TermLanguage.ARABIC
        return TermLanguage.ENGLISH

    @staticmethod
    def _categorize_term(term: str) -> TermCategory:
        """Assign a :class:`TermCategory` based on keyword matching.

        Scans both the full term and each individual word against
        ``_CATEGORY_KEYWORDS``.  Returns :pyattr:`TermCategory.DIAGNOSIS`
        when no keywords match.
        """
        lower = term.lower()
        for category, keywords in _CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    return TermCategory(category)
        # Check individual words for multi-word terms.
        for word in lower.split():
            for category, keywords in _CATEGORY_KEYWORDS.items():
                if word in keywords:
                    return TermCategory(category)
        return TermCategory.DIAGNOSIS

    # -- Main import pipeline -----------------------------------------------

    def import_bgl_file(
        self,
        filepath: str,
        source_name: str = "",
    ) -> int:
        """Import a BGL glossary file into the dictionary database.

        Steps:
        1. Compute a SHA-256 checksum to detect duplicate imports.
        2. Skip if a source with the same checksum already exists.
        3. Parse the BGL file (requires ``bglconverter``).
        4. For each entry, auto-detect language and category.
        5. Insert terms and synonyms into SQLite.
        6. Export the full dictionary to a JSON cache file.

        Parameters
        ----------
        filepath:
            Path to the ``.bgl`` file.
        source_name:
            Optional human-readable name.  Falls back to the file name.

        Returns
        -------
        int
            Number of terms successfully imported.

        Raises
        ------
        RuntimeError
            If ``bglconverter`` is not installed.
        """
        if not _HAS_BGL_CONVERTER:
            raise RuntimeError(
                "bglconverter is required to import BGL files.  "
                "Install it with:  pip install bglconverter"
            )

        checksum = self._compute_checksum(filepath)
        source_name = source_name or os.path.basename(filepath)

        # Skip duplicate imports.
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id FROM sources WHERE checksum = ?",
                (checksum,),
            ).fetchone()
            if row:
                logger.info(
                    "Source '%s' already imported (checksum match).", source_name
                )
                return 0

        # Parse BGL file.
        entries: List[Tuple[str, str]] = []
        with open(filepath, "rb") as fh:
            for entry in bgl_reader.BGLReader().readfile(fh):
                # entry is typically (headword, definition)
                entries.append(
                    (str(entry[0]).strip(), str(entry[1]).strip())
                )

        if not entries:
            logger.warning("No entries parsed from '%s'.", filepath)
            return 0

        # Store terms.
        imported: int = 0
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            for canonical, definition in entries:
                if not canonical:
                    continue
                lang = self._detect_language(canonical + " " + definition)
                cat = self._categorize_term(canonical)
                term_id = hashlib.md5(canonical.encode()).hexdigest()
                synonyms = json.dumps([])
                metadata = json.dumps({"original_definition": definition})

                conn.execute(
                    """
                    INSERT OR REPLACE INTO terms
                        (id, canonical, synonyms, category, language,
                         definition, source, confidence, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term_id, canonical, synonyms, cat.value, lang.value,
                        definition[:2000], source_name, 0.85, metadata, now,
                    ),
                )
                imported += 1

            source_id = hashlib.md5(
                (source_name + checksum).encode()
            ).hexdigest()
            conn.execute(
                """
                INSERT OR REPLACE INTO sources
                    (id, name, filename, language, term_count,
                     imported_at, checksum, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id, source_name, os.path.basename(filepath),
                    TermLanguage.ENGLISH.value, imported, now,
                    checksum, "imported",
                ),
            )
            conn.commit()

        logger.info(
            "Imported %d terms from '%s'.", imported, source_name
        )
        self._export_json()
        return imported

    # -- Query interface ----------------------------------------------------

    def search(
        self,
        query: str,
        language: Optional[TermLanguage] = None,
        category: Optional[TermCategory] = None,
        limit: int = 50,
    ) -> List[MedicalTerm]:
        """Fuzzy search for medical terms using SQL ``LIKE``.

        Parameters
        ----------
        query:
            Free-text search string (matched against canonical term and
            definition).
        language:
            Optional language filter.
        category:
            Optional category filter.
        limit:
            Maximum number of results (default ``50``).

        Returns
        -------
        list[MedicalTerm]
            Matching term records.
        """
        sql = "SELECT * FROM terms WHERE canonical LIKE ? OR definition LIKE ?"
        params: list[Any] = [f"%{query}%", f"%{query}%"]

        if language:
            sql += " AND language = ?"
            params.append(language.value)
        if category:
            sql += " AND category = ?"
            params.append(category.value)

        sql += f" ORDER BY confidence DESC LIMIT {int(limit)}"

        results: List[MedicalTerm] = []
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(sql, params):
                results.append(
                    MedicalTerm(
                        id=row["id"],
                        canonical=row["canonical"],
                        synonyms=json.loads(row["synonyms"]),
                        category=TermCategory(row["category"]),
                        language=TermLanguage(row["language"]),
                        definition=row["definition"],
                        source=row["source"],
                        confidence=row["confidence"],
                        metadata=json.loads(row["metadata"]),
                        created_at=row["created_at"],
                    )
                )
        return results

    # -- Statistics ---------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics about the dictionary.

        Returns
        -------
        dict
            Keys: ``total_terms``, ``by_language``, ``by_category``,
            ``sources_count``, ``db_size_bytes``.
        """
        stats: Dict[str, Any] = {}
        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            stats["total_terms"] = total

            stats["by_language"] = {}
            for row in conn.execute(
                "SELECT language, COUNT(*) AS c FROM terms GROUP BY language"
            ):
                stats["by_language"][row[0]] = row[1]

            stats["by_category"] = {}
            for row in conn.execute(
                "SELECT category, COUNT(*) AS c FROM terms GROUP BY category"
            ):
                stats["by_category"][row[0]] = row[1]

            stats["sources_count"] = conn.execute(
                "SELECT COUNT(*) FROM sources"
            ).fetchone()[0]

        stats["db_size_bytes"] = (
            os.path.getsize(self._db_path)
            if os.path.exists(self._db_path)
            else 0
        )
        return stats

    # -- JSON export --------------------------------------------------------

    def _export_json(self) -> str:
        """Export all terms to a JSON cache file for fast loading.

        Returns
        -------
        str
            Path to the generated JSON file.
        """
        export_path = os.path.join(self.data_dir, "medical_terms.json")
        terms: List[Dict[str, Any]] = []
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT * FROM terms"):
                term = MedicalTerm(
                    id=row["id"],
                    canonical=row["canonical"],
                    synonyms=json.loads(row["synonyms"]),
                    category=TermCategory(row["category"]),
                    language=TermLanguage(row["language"]),
                    definition=row["definition"],
                    source=row["source"],
                    confidence=row["confidence"],
                    metadata=json.loads(row["metadata"]),
                    created_at=row["created_at"],
                )
                terms.append(term.to_dict())
        with open(export_path, "w", encoding="utf-8") as fh:
            json.dump(terms, fh, ensure_ascii=False, indent=2)
        logger.info("Exported %d terms to '%s'.", len(terms), export_path)
        return export_path
