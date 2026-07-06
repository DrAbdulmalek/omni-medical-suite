"""
Tests for ExactDeduplicator — add texts, check duplicates, verify stats.
"""

import pytest
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Minimal ExactDeduplicator replica for standalone testing
# ---------------------------------------------------------------------------

class DeduplicationResult:
    """Result of a deduplication check."""

    __slots__ = ("text", "is_duplicate", "duplicate_of")

    def __init__(self, text: str, is_duplicate: bool, duplicate_of: str | None = None):
        self.text = text
        self.is_duplicate = is_duplicate
        self.duplicate_of = duplicate_of


class ExactDeduplicator:
    """Deduplicate text chunks using exact string matching."""

    def __init__(self, case_sensitive: bool = False, strip_whitespace: bool = True):
        self.case_sensitive = case_sensitive
        self.strip_whitespace = strip_whitespace
        self._seen: dict[str, str] = {}  # normalized text -> first chunk_id

    def _normalize(self, text: str) -> str:
        if self.strip_whitespace:
            text = " ".join(text.split())
        if not self.case_sensitive:
            text = text.lower()
        return text

    def add(self, text: str, chunk_id: str) -> DeduplicationResult:
        """Add a text and check if it's a duplicate."""
        normalized = self._normalize(text)

        if normalized in self._seen:
            return DeduplicationResult(
                text=text,
                is_duplicate=True,
                duplicate_of=self._seen[normalized],
            )

        self._seen[normalized] = chunk_id
        return DeduplicationResult(
            text=text,
            is_duplicate=False,
            duplicate_of=None,
        )

    def check(self, text: str) -> bool:
        """Check if text is a duplicate without adding it."""
        normalized = self._normalize(text)
        return normalized in self._seen

    def add_batch(self, items: List[Tuple[str, str]]) -> List[DeduplicationResult]:
        """Add multiple (text, chunk_id) pairs and return results."""
        return [self.add(text, cid) for text, cid in items]

    @property
    def stats(self) -> dict:
        """Return deduplication statistics."""
        total_added = len(self._seen)
        # We track duplicates only when add() returns is_duplicate=True,
        # so we need a counter. Let's add one.
        return {
            "unique_count": total_added,
            "seen_normalized_count": total_added,
        }

    @property
    def unique_count(self) -> int:
        return len(self._seen)


class CountingDeduplicator(ExactDeduplicator):
    """Extended deduplicator that tracks duplicate count."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._total_processed = 0
        self._duplicate_count = 0

    def add(self, text: str, chunk_id: str) -> DeduplicationResult:
        self._total_processed += 1
        result = super().add(text, chunk_id)
        if result.is_duplicate:
            self._duplicate_count += 1
        return result

    @property
    def stats(self) -> dict:
        return {
            "total_processed": self._total_processed,
            "unique_count": self.unique_count,
            "duplicate_count": self._duplicate_count,
            "dedup_rate": (
                self._duplicate_count / self._total_processed
                if self._total_processed > 0
                else 0.0
            ),
        }


# ── Tests ──────────────────────────────────────────────────────────────────

class TestExactDeduplicatorInit:
    """Test deduplicator initialization."""

    def test_default_case_insensitive(self):
        dedup = ExactDeduplicator()
        assert dedup.case_sensitive is False

    def test_case_sensitive_mode(self):
        dedup = ExactDeduplicator(case_sensitive=True)
        assert dedup.case_sensitive is True

    def test_empty_on_init(self):
        dedup = ExactDeduplicator()
        assert dedup.unique_count == 0


class TestExactDeduplicatorAdd:
    """Test adding texts and detecting duplicates."""

    def test_add_unique_text(self):
        dedup = ExactDeduplicator()
        result = dedup.add("Hello world", "c1")
        assert result.is_duplicate is False
        assert result.duplicate_of is None
        assert dedup.unique_count == 1

    def test_add_exact_duplicate(self):
        dedup = ExactDeduplicator()
        dedup.add("Hello world", "c1")
        result = dedup.add("Hello world", "c2")
        assert result.is_duplicate is True
        assert result.duplicate_of == "c1"
        assert dedup.unique_count == 1

    def test_case_insensitive_duplicate(self):
        dedup = ExactDeduplicator(case_sensitive=False)
        dedup.add("Hello World", "c1")
        result = dedup.add("hello world", "c2")
        assert result.is_duplicate is True
        assert result.duplicate_of == "c1"

    def test_case_sensitive_no_duplicate(self):
        dedup = ExactDeduplicator(case_sensitive=True)
        dedup.add("Hello World", "c1")
        result = dedup.add("hello world", "c2")
        assert result.is_duplicate is False
        assert dedup.unique_count == 2

    def test_whitespace_normalized(self):
        dedup = ExactDeduplicator(strip_whitespace=True)
        dedup.add("Hello   world  test", "c1")
        result = dedup.add("Hello world test", "c2")
        assert result.is_duplicate is True

    def test_different_texts_not_duplicate(self):
        dedup = ExactDeduplicator()
        dedup.add("First text chunk", "c1")
        result = dedup.add("Second different text", "c2")
        assert result.is_duplicate is False
        assert dedup.unique_count == 2

    def test_empty_string(self):
        dedup = ExactDeduplicator()
        result = dedup.add("", "c_empty")
        assert result.is_duplicate is False


class TestExactDeduplicatorCheck:
    """Test checking without adding."""

    def test_check_existing(self):
        dedup = ExactDeduplicator()
        dedup.add("Existing text", "c1")
        assert dedup.check("Existing text") is True

    def test_check_non_existing(self):
        dedup = ExactDeduplicator()
        dedup.add("Existing text", "c1")
        assert dedup.check("Non-existing text") is False

    def test_check_does_not_add(self):
        dedup = ExactDeduplicator()
        dedup.check("Will not be added")
        assert dedup.unique_count == 0


class TestExactDeduplicatorBatch:
    """Test batch deduplication."""

    def test_batch_mixed(self):
        dedup = ExactDeduplicator()
        items = [
            ("Text A", "c1"),
            ("Text B", "c2"),
            ("Text A", "c3"),  # duplicate of c1
            ("Text C", "c4"),
            ("Text B", "c5"),  # duplicate of c2
        ]
        results = dedup.add_batch(items)
        assert len(results) == 5
        assert results[0].is_duplicate is False
        assert results[1].is_duplicate is False
        assert results[2].is_duplicate is True
        assert results[2].duplicate_of == "c1"
        assert results[3].is_duplicate is False
        assert results[4].is_duplicate is True
        assert results[4].duplicate_of == "c2"
        assert dedup.unique_count == 3


class TestCountingDeduplicatorStats:
    """Test statistics tracking."""

    def test_stats_initial(self):
        dedup = CountingDeduplicator()
        stats = dedup.stats
        assert stats["total_processed"] == 0
        assert stats["unique_count"] == 0
        assert stats["duplicate_count"] == 0
        assert stats["dedup_rate"] == 0.0

    def test_stats_after_processing(self):
        dedup = CountingDeduplicator()
        items = [
            ("Alpha", "c1"),
            ("Beta", "c2"),
            ("Alpha", "c3"),
            ("Gamma", "c4"),
            ("Beta", "c5"),
            ("Alpha", "c6"),
        ]
        dedup.add_batch(items)
        stats = dedup.stats
        assert stats["total_processed"] == 6
        assert stats["unique_count"] == 3
        assert stats["duplicate_count"] == 3
        assert stats["dedup_rate"] == pytest.approx(0.5)

    def test_all_unique_stats(self):
        dedup = CountingDeduplicator()
        dedup.add_batch([("A", "c1"), ("B", "c2"), ("C", "c3")])
        stats = dedup.stats
        assert stats["dedup_rate"] == 0.0
        assert stats["unique_count"] == 3
