#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for AutoPromotionEngine — Stage 2 of OmniMedical v2.0"""

import os
os.environ["API_KEY"] = "test-key"

import sqlite3
import tempfile
import pytest
from datetime import datetime, timedelta
from app.learning.auto_promotion import (
    AutoPromotionEngine,
    PromotionCriteria,
    PromotionResult,
)


class TestAutoPromotionEngine:
    """Tests for automatic correction promotion."""

    @pytest.fixture
    def db_path(self, tmp_path):
        path = str(tmp_path / "test_corrections.db")
        # Create the corrections table
        with sqlite3.connect(path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY, original TEXT UNIQUE, corrected TEXT,
                    language TEXT, context_before TEXT, context_after TEXT,
                    confidence_before REAL, confidence_after REAL, confidence_gain REAL,
                    frequency INTEGER DEFAULT 1, first_seen TEXT, last_used TEXT,
                    source_files TEXT, auto_promoted INTEGER DEFAULT 0
                );
            """)
            # Insert test data
            recent = datetime.now().isoformat()
            old = (datetime.now() - timedelta(days=60)).isoformat()

            corrections = [
                # Should be promoted: high freq, good gain, recent
                ("فخد", "عظم الفخذ", "ar", "", "", 0.6, 0.92, 0.32, 5, recent, recent, "f1,f2,f3", 0),
                # Should NOT: low frequency
                ("ساعد", "الساعد", "ar", "", "", 0.7, 0.85, 0.15, 1, recent, recent, "f1", 0),
                # Should NOT: already promoted
                ("كتف", "الكتف", "ar", "", "", 0.5, 0.88, 0.38, 4, recent, recent, "f1,f2,f3,f4", 1),
                # Should NOT: too old
                ("قدم", "القدم", "ar", "", "", 0.6, 0.90, 0.30, 3, old, old, "f1,f2,f3", 0),
                # Should NOT: low confidence gain
                ("يد", "اليد", "ar", "", "", 0.8, 0.82, 0.02, 3, recent, recent, "f1,f2,f3", 0),
                # Should be promoted: meets all criteria
                ("رأس", "الرأس", "en", "", "", 0.55, 0.90, 0.35, 4, recent, recent, "f1,f2,f3,f4", 0),
            ]

            for c in corrections:
                conn.execute(
                    "INSERT INTO corrections "
                    "(original, corrected, language, context_before, context_after, "
                    "confidence_before, confidence_after, confidence_gain, "
                    "frequency, first_seen, last_used, source_files, auto_promoted) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    c
                )
        return path

    @pytest.fixture
    def engine(self, db_path):
        return AutoPromotionEngine(db_path)

    def test_promotion_cycle_promotes_qualified(self, engine, db_path):
        """Should promote corrections meeting all criteria."""
        results = engine.run_promotion_cycle()
        promoted = [r for r in results if r.promoted]
        # Should promote at least the first and last corrections
        assert len(promoted) >= 2

    def test_promotion_cycle_skips_low_frequency(self, engine, db_path):
        """Should not evaluate corrections with insufficient frequency (filtered by SQL)."""
        results = engine.run_promotion_cycle()
        low_freq = [r for r in results if r.original == "ساعد"]
        # SQL query filters WHERE frequency >= min_frequency, so low freq items are never evaluated
        assert len(low_freq) == 0

    def test_promotion_cycle_skips_already_promoted(self, engine, db_path):
        """Should skip already promoted corrections (filtered by SQL)."""
        results = engine.run_promotion_cycle()
        already = [r for r in results if r.original == "كتف"]
        # SQL query filters WHERE auto_promoted = 0, so already promoted items are never evaluated
        assert len(already) == 0

    def test_promotion_cycle_skips_old_corrections(self, engine, db_path):
        """Should skip corrections older than max_age_days."""
        results = engine.run_promotion_cycle()
        old = [r for r in results if r.original == "قدم"]
        assert len(old) == 1
        assert old[0].promoted is False

    def test_promotion_cycle_skips_low_gain(self, engine, db_path):
        """Should skip corrections with low confidence gain."""
        results = engine.run_promotion_cycle()
        low_gain = [r for r in results if r.original == "يد"]
        assert len(low_gain) == 1
        assert low_gain[0].promoted is False

    def test_promotion_updates_database(self, engine, db_path):
        """Promoted corrections should be marked in DB."""
        results = engine.run_promotion_cycle()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            for r in results:
                if r.promoted:
                    row = conn.execute(
                        "SELECT auto_promoted FROM corrections WHERE id = ?",
                        (r.correction_id,)
                    ).fetchone()
                    assert row["auto_promoted"] == 1

    def test_promotion_stats(self, engine, db_path):
        """get_promotion_stats should return correct counts."""
        engine.run_promotion_cycle()
        stats = engine.get_promotion_stats()
        assert stats["total_evaluated"] > 0
        assert stats["promoted"] > 0
        assert stats["rejected"] > 0
        assert 0 <= stats["promotion_rate"] <= 1.0

    def test_custom_criteria(self, db_path):
        """Should respect custom promotion criteria."""
        strict = AutoPromotionEngine(
            db_path,
            criteria=PromotionCriteria(min_frequency=10)
        )
        results = strict.run_promotion_cycle()
        # With min_frequency=10, nothing should be promoted
        assert all(not r.promoted for r in results)

    def test_promotion_result_dataclass(self):
        """PromotionResult should store all fields correctly."""
        result = PromotionResult(
            correction_id=1, original="a", corrected="b",
            frequency=5, confidence_gain=0.2,
            promoted=True, reasons=[], checks={"freq": True}
        )
        assert result.correction_id == 1
        assert result.promoted is True
        assert result.checks["freq"] is True

    def test_days_since_parsing(self, engine):
        """_days_since should handle valid ISO dates."""
        assert engine._days_since(datetime.now().isoformat()) == 0
        assert engine._days_since("invalid") == 999

    def test_empty_database(self, tmp_path):
        """Should handle empty database gracefully."""
        path = str(tmp_path / "empty.db")
        with sqlite3.connect(path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY, original TEXT UNIQUE, corrected TEXT,
                    language TEXT, context_before TEXT, context_after TEXT,
                    confidence_before REAL, confidence_after REAL, confidence_gain REAL,
                    frequency INTEGER DEFAULT 1, first_seen TEXT, last_used TEXT,
                    source_files TEXT, auto_promoted INTEGER DEFAULT 0
                );
            """)
        engine = AutoPromotionEngine(path)
        results = engine.run_promotion_cycle()
        assert len(results) == 0
