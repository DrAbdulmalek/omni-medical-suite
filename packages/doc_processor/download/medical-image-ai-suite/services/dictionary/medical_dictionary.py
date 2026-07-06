# -*- coding: utf-8 -*-
"""High-level medical dictionary interface for the OmniMedical Suite.

Provides a unified API for term look-up, fuzzy search, spelling correction,
and clinical text enrichment.  Results are cached in memory for fast
subsequent access.

Typical usage::

    dictionary = MedicalDictionary(data_dir="data/dictionary")
    term = dictionary.lookup("carditis")
    corrections = dictionary.suggest_corrections("cardtis")
    enriched = dictionary.enrich_text("Patient presents with myocarditis …")
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .bgl_importer import BGLMedicalImporter
from .models import (
    MedicalTerm,
    TermCategory,
    TermLanguage,
)

logger = logging.getLogger(__name__)


class MedicalDictionary:
    """Unified dictionary service for medical terminology.

    Lazily loads a JSON term cache on first access so that start-up is
    near-instant even with large dictionaries.  When the cache is
    unavailable the service transparently falls back to direct SQLite
    queries.

    Parameters
    ----------
    data_dir:
        Directory containing the SQLite database and JSON exports.
    cache_path:
        Explicit path to the JSON cache file.  When ``None`` the default
        location inside *data_dir* is used.
    """

    def __init__(
        self,
        data_dir: str = "data/dictionary",
        cache_path: Optional[str] = None,
    ) -> None:
        self.data_dir: str = data_dir
        self._db_path: str = os.path.join(data_dir, "medical_dict.db")
        self._cache_path: str = (
            cache_path or os.path.join(data_dir, "medical_terms.json")
        )
        self._importer = BGLMedicalImporter(data_dir=data_dir)

        # Lazy-loaded caches.
        self._term_cache: Dict[str, MedicalTerm] = {}
        self._synonym_cache: Dict[str, str] = {}  # synonym → canonical
        self._loaded: bool = False

    # -- Cache loading ------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the JSON cache into memory on first access.

        Reads the exported JSON file and builds two dictionaries:
        * ``_term_cache`` maps canonical terms to :class:`MedicalTerm` objects.
        * ``_synonym_cache`` maps synonym strings to canonical terms.

        If no JSON cache is found, terms are loaded directly from the
        SQLite database so that all API methods work even without a
        pre-exported cache file.
        """
        if self._loaded:
            return

        loaded = False

        # --- Attempt JSON cache first (fast path) ---
        if os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, "r", encoding="utf-8") as fh:
                    raw_terms = json.load(fh)
                for entry in raw_terms:
                    term = MedicalTerm.from_dict(entry)
                    self._term_cache[term.canonical.lower()] = term
                    for syn in term.synonyms:
                        self._synonym_cache[syn.lower()] = term.canonical.lower()
                loaded = True
                logger.info(
                    "Loaded %d terms from JSON cache.", len(self._term_cache)
                )
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load JSON cache: %s", exc)

        # --- Fall back to SQLite database ---
        if not loaded and os.path.exists(self._db_path):
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute("SELECT * FROM terms").fetchall()
                for row in rows:
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
                    self._term_cache[term.canonical.lower()] = term
                    for syn in term.synonyms:
                        self._synonym_cache[syn.lower()] = term.canonical.lower()
                loaded = True
                logger.info(
                    "Loaded %d terms from SQLite database.", len(self._term_cache)
                )
            except (sqlite3.Error, KeyError) as exc:
                logger.warning("Failed to load from SQLite: %s", exc)

        self._loaded = True

    # -- Public API ---------------------------------------------------------

    def lookup(
        self,
        term: str,
        language: Optional[TermLanguage] = None,
    ) -> Optional[MedicalTerm]:
        """Exact look-up for a medical term.

        Searches the in-memory cache first, then falls back to a direct
        SQLite query.

        Parameters
        ----------
        term:
            The canonical term to look up.
        language:
            Optional language filter.

        Returns
        -------
        MedicalTerm or None
            The matching term, or ``None`` if not found.
        """
        self._ensure_loaded()

        # 1. Check the in-memory term cache.
        key = term.lower()
        cached = self._term_cache.get(key)
        if cached is not None:
            if language and cached.language != language:
                return None
            return cached

        # 2. Check synonym redirect.
        canonical_key = self._synonym_cache.get(key)
        if canonical_key:
            cached = self._term_cache.get(canonical_key)
            if cached and (not language or cached.language == language):
                return cached

        # 3. Fall back to SQLite.
        return self._lookup_db(term, language)

    def search(
        self,
        query: str,
        language: Optional[TermLanguage] = None,
        category: Optional[TermCategory] = None,
        limit: int = 20,
    ) -> List[MedicalTerm]:
        """Flexible fuzzy search for medical terms.

        Delegates to :meth:`BGLMedicalImporter.search` which uses SQL
        ``LIKE`` pattern matching against canonical terms and definitions.

        Parameters
        ----------
        query:
            Free-text search string.
        language:
            Optional language filter.
        category:
            Optional semantic category filter.
        limit:
            Maximum number of results.

        Returns
        -------
        list[MedicalTerm]
            Matching terms ordered by confidence descending.
        """
        return self._importer.search(
            query=query,
            language=language,
            category=category,
            limit=limit,
        )

    def validate_term(
        self,
        term: str,
        category: Optional[TermCategory] = None,
    ) -> bool:
        """Check whether *term* exists in the dictionary.

        Parameters
        ----------
        term:
            The term to validate.
        category:
            If provided, the term must also match this category.

        Returns
        -------
        bool
            ``True`` if the term is recognised (and matches the category
            when specified).
        """
        result = self.lookup(term)
        if result is None:
            return False
        if category is not None and result.category != category:
            return False
        return True

    def suggest_corrections(
        self,
        term: str,
        threshold: float = 0.7,
        max_suggestions: int = 5,
    ) -> List[Tuple[str, float]]:
        """Suggest spelling corrections for a possibly misspelled term.

        Uses :class:`difflib.SequenceMatcher` to rank candidates from the
        term cache by similarity ratio.

        Parameters
        ----------
        term:
            The potentially misspelled word.
        threshold:
            Minimum similarity ratio (``0.0`` – ``1.0``) to include a
            candidate.  Default ``0.7``.
        max_suggestions:
            Maximum number of suggestions to return.

        Returns
        -------
        list[tuple[str, float]]
            Pairs of ``(canonical_term, similarity_ratio)``, sorted by
            similarity descending.
        """
        self._ensure_loaded()
        lower_term = term.lower()
        candidates: List[Tuple[str, float]] = []

        for canonical, cached_term in self._term_cache.items():
            ratio = SequenceMatcher(None, lower_term, canonical).ratio()
            if ratio >= threshold:
                candidates.append((cached_term.canonical, ratio))

        # Also check synonyms.
        for synonym, canonical_key in self._synonym_cache.items():
            ratio = SequenceMatcher(None, lower_term, synonym).ratio()
            if ratio >= threshold:
                cached_term = self._term_cache.get(canonical_key)
                if cached_term:
                    candidates.append((cached_term.canonical, ratio))

        # Deduplicate and sort.
        seen: set[str] = set()
        unique: List[Tuple[str, float]] = []
        for term_text, ratio in sorted(
            candidates, key=lambda x: x[1], reverse=True
        ):
            if term_text not in seen:
                seen.add(term_text)
                unique.append((term_text, ratio))
            if len(unique) >= max_suggestions:
                break

        return unique

    def enrich_text(
        self,
        text: str,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Identify medical terms inside a block of free text.

        Scans *text* for any word (or multi-word phrase from the term
        cache) and returns matched terms with their category and confidence.

        Parameters
        ----------
        text:
            Clinical or narrative text to analyse.
        min_confidence:
            Minimum confidence score to include a match.

        Returns
        -------
        list[dict]
            Each dict contains keys ``term``, ``category``, ``confidence``,
            ``start``, and ``end`` (character offsets).
        """
        self._ensure_loaded()
        results: List[Dict[str, Any]] = []

        # Sort canonical terms by length descending so that longer phrases
        # are matched before their shorter substrings.
        sorted_terms = sorted(
            self._term_cache.values(),
            key=lambda t: len(t.canonical),
            reverse=True,
        )

        text_lower = text.lower()
        matched_spans: List[Tuple[int, int]] = []

        for term_obj in sorted_terms:
            if term_obj.confidence < min_confidence:
                continue
            needle = term_obj.canonical.lower()
            start = 0
            while True:
                idx = text_lower.find(needle, start)
                if idx == -1:
                    break
                end = idx + len(term_obj.canonical)
                # Avoid overlapping matches.
                if not any(s < end and e > idx for s, e in matched_spans):
                    matched_spans.append((idx, end))
                    results.append(
                        {
                            "term": term_obj.canonical,
                            "category": term_obj.category.value,
                            "confidence": term_obj.confidence,
                            "start": idx,
                            "end": end,
                        }
                    )
                start = idx + 1

        # Sort by position in the text.
        results.sort(key=lambda r: r["start"])
        return results

    def add_custom_term(self, term: MedicalTerm) -> bool:
        """Insert a user-defined term into the database.

        Parameters
        ----------
        term:
            A fully populated :class:`MedicalTerm` instance.  If ``id`` is
            empty a new one is generated from the canonical spelling.

        Returns
        -------
        bool
            ``True`` if the insert succeeded.
        """
        import hashlib

        term_id = term.id or hashlib.md5(
            term.canonical.encode()
        ).hexdigest()
        term.id = term_id

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO terms
                        (id, canonical, synonyms, category, language,
                         definition, source, confidence, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term.id,
                        term.canonical,
                        json.dumps(term.synonyms),
                        term.category.value,
                        term.language.value,
                        term.definition,
                        term.source or "custom",
                        term.confidence,
                        json.dumps(term.metadata),
                        term.created_at
                        or datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()

            # Refresh the cache so the new term is immediately visible.
            self._term_cache[term.canonical.lower()] = term
            for syn in term.synonyms:
                self._synonym_cache[syn.lower()] = term.canonical.lower()
            return True

        except sqlite3.Error as exc:
            logger.error("Failed to add custom term '%s': %s", term.canonical, exc)
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics from the dictionary.

        Delegates to :meth:`BGLMedicalImporter.get_stats`.

        Returns
        -------
        dict
            See :meth:`BGLMedicalImporter.get_stats` for the full schema.
        """
        return self._importer.get_stats()

    # -- Private helpers -----------------------------------------------------

    def _lookup_db(
        self,
        term: str,
        language: Optional[TermLanguage] = None,
    ) -> Optional[MedicalTerm]:
        """Direct SQLite look-up bypassing the in-memory cache.

        Searches both the ``canonical`` column and the ``synonyms`` JSON
        column so that synonym queries are resolved correctly.
        """
        sql = "SELECT * FROM terms WHERE (canonical = ? COLLATE NOCASE OR synonyms LIKE ?)"
        params: list[Any] = [term, f'%"{term.lower()}"%']
        if language:
            sql += " AND language = ?"
            params.append(language.value)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, params).fetchone()
            if row is None:
                return None
            return MedicalTerm(
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
