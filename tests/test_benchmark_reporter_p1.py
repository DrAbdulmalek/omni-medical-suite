"""Tests for P1-2 benchmark reporter — CSV/JSON export + aggregate metrics."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def pipeline():
    from omni_medical_suite.preprocessing.compare_raw_vs_printed import OCRComparisonPipeline

    return OCRComparisonPipeline()


@pytest.fixture
def sample_results(pipeline):
    """Generate a small batch of comparison results for testing."""
    rows = [
        {
            "document_id": "doc1",
            "raw_text": "اسم المريض: أحمد",
            "processed_text": "اسم المريض: أحمد علي",
            "reference_text": "اسم المريض: أحمد علي",
        },
        {
            "document_id": "doc2",
            "raw_text": "Patient: X",
            "processed_text": "Patient: Y",
            "reference_text": "Patient: Z",
        },
        {
            "document_id": "doc3",
            "raw_text": "Diagnosis: Flu",
            "processed_text": "Diagnosis: Influenza",
            "reference_text": "Diagnosis: Influenza",
        },
    ]
    return pipeline.compare_batch(rows)


# ---------------------------------------------------------------------------
# to_csv
# ---------------------------------------------------------------------------
class TestToCsv:
    def test_returns_string_when_no_path(self, pipeline, sample_results):
        csv_str = pipeline.to_csv(sample_results)
        assert isinstance(csv_str, str)
        assert len(csv_str) > 0

    def test_writes_to_file(self, pipeline, sample_results, tmp_path):
        out = tmp_path / "results.csv"
        pipeline.to_csv(sample_results, str(out))
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "document_id" in content
        assert "doc1" in content

    def test_csv_has_header_row(self, pipeline, sample_results):
        csv_str = pipeline.to_csv(sample_results)
        first_line = csv_str.splitlines()[0]
        assert "raw_vs_processed_similarity" in first_line
        assert "document_id" in first_line

    def test_csv_data_rows_match_count(self, pipeline, sample_results):
        csv_str = pipeline.to_csv(sample_results)
        lines = [l for l in csv_str.splitlines() if l.strip()]
        # 1 header + 3 data rows
        assert len(lines) == 4

    def test_csv_field_aware_flattened_by_default(self, pipeline, sample_results):
        csv_str = pipeline.to_csv(sample_results)
        # Should have flattened keys like "field_aware_similarity.<key>"
        assert "field_aware_similarity." in csv_str

    def test_csv_field_aware_json_when_not_flattened(self, pipeline, sample_results):
        csv_str = pipeline.to_csv(sample_results, flatten_field_aware=False)
        # The field_aware_similarity column should contain a JSON string
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            if row.get("field_aware_similarity"):
                parsed = json.loads(row["field_aware_similarity"])
                assert isinstance(parsed, dict)
                break

    def test_empty_results_returns_empty_string(self, pipeline):
        csv_str = pipeline.to_csv([])
        assert csv_str == ""


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------
class TestToJson:
    def test_returns_valid_json_string(self, pipeline, sample_results):
        json_str = pipeline.to_json(sample_results)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 3

    def test_writes_to_file(self, pipeline, sample_results, tmp_path):
        out = tmp_path / "results.json"
        pipeline.to_json(sample_results, str(out))
        assert out.exists()
        parsed = json.loads(out.read_text(encoding="utf-8"))
        assert len(parsed) == 3

    def test_json_preserves_unicode(self, pipeline, sample_results):
        json_str = pipeline.to_json(sample_results)
        # Arabic content should be preserved as-is (not \\u-escaped)
        assert "أحمد" in json_str or "أحمد" in json_str.replace("\\u", "")

    def test_json_indent_param(self, pipeline, sample_results):
        compact = pipeline.to_json(sample_results, indent=None)
        pretty = pipeline.to_json(sample_results, indent=4)
        # Pretty should be longer due to whitespace
        assert len(pretty) > len(compact)

    def test_empty_results_returns_json_array(self, pipeline):
        json_str = pipeline.to_json([])
        assert json.loads(json_str) == []


# ---------------------------------------------------------------------------
# aggregate_metrics
# ---------------------------------------------------------------------------
class TestAggregateMetrics:
    def test_returns_count(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        assert agg["count"] == 3

    def test_empty_results_returns_count_zero(self, pipeline):
        agg = pipeline.aggregate_metrics([])
        assert agg == {"count": 0}

    def test_top_level_metrics_have_stats(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        for metric in [
            "raw_vs_processed_similarity",
            "raw_vs_reference_similarity",
            "processed_vs_reference_similarity",
            "improvement_vs_reference",
        ]:
            assert metric in agg
            stats = agg[metric]
            assert "count" in stats
            assert "min" in stats
            assert "max" in stats
            assert "mean" in stats
            assert "median" in stats
            assert "stdev" in stats

    def test_percentiles_present(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        stats = agg["raw_vs_processed_similarity"]
        assert "p50" in stats
        assert "p90" in stats
        assert "p95" in stats

    def test_custom_percentiles(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results, percentiles=[0.25, 0.75])
        stats = agg["raw_vs_processed_similarity"]
        assert "p25" in stats
        assert "p75" in stats
        assert "p50" not in stats  # not requested

    def test_field_aware_aggregated(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        assert "field_aware_similarity" in agg
        assert isinstance(agg["field_aware_similarity"], dict)

    def test_improvement_mean(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        assert "improvement_mean" in agg
        # improvement_mean is None only if no results have improvement_vs_reference;
        # our sample_results all have reference_text so it should be a number
        assert agg["improvement_mean"] is not None

    def test_processed_better_count(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        assert "processed_better_count" in agg
        assert "processed_better_ratio" in agg
        assert isinstance(agg["processed_better_count"], int)
        assert 0 <= agg["processed_better_count"] <= 3
        assert 0.0 <= agg["processed_better_ratio"] <= 1.0

    def test_stats_min_le_max(self, pipeline, sample_results):
        agg = pipeline.aggregate_metrics(sample_results)
        stats = agg["raw_vs_processed_similarity"]
        assert stats["min"] <= stats["max"]
        assert stats["min"] <= stats["median"] <= stats["max"]


# ---------------------------------------------------------------------------
# Integration: end-to-end batch + export
# ---------------------------------------------------------------------------
class TestEndToEnd:
    def test_full_workflow(self, pipeline, tmp_path):
        """Run a full batch → CSV + JSON + aggregates workflow."""
        rows = [
            {
                "document_id": f"doc{i}",
                "raw_text": f"Patient Name: Test{i}",
                "processed_text": f"Patient Name: Test{i} Refined",
                "reference_text": f"Patient Name: Test{i} Refined",
            }
            for i in range(5)
        ]
        results = pipeline.compare_batch(rows)
        assert len(results) == 5

        # Export to CSV
        csv_path = tmp_path / "batch.csv"
        pipeline.to_csv(results, str(csv_path))
        assert csv_path.exists()

        # Export to JSON
        json_path = tmp_path / "batch.json"
        pipeline.to_json(results, str(json_path))
        assert json_path.exists()

        # Aggregate
        agg = pipeline.aggregate_metrics(results)
        assert agg["count"] == 5

        # All three artifacts should be consistent
        with open(csv_path, encoding="utf-8") as f:
            csv_rows = list(csv.DictReader(f))
        assert len(csv_rows) == 5

        with open(json_path, encoding="utf-8") as f:
            json_data = json.load(f)
        assert len(json_data) == 5


# ---------------------------------------------------------------------------
# _stats helper
# ---------------------------------------------------------------------------
class TestStatsHelper:
    def test_empty_list(self):
        from omni_medical_suite.preprocessing.compare_raw_vs_printed import _stats

        assert _stats([], [0.5]) == {"count": 0}

    def test_single_value(self):
        from omni_medical_suite.preprocessing.compare_raw_vs_printed import _stats

        result = _stats([0.5], [0.5])
        assert result["count"] == 1
        assert result["min"] == 0.5
        assert result["max"] == 0.5
        assert result["mean"] == 0.5
        assert result["stdev"] == 0.0  # single value

    def test_multiple_values(self):
        from omni_medical_suite.preprocessing.compare_raw_vs_printed import _stats

        result = _stats([0.1, 0.5, 0.9], [0.5])
        assert result["count"] == 3
        assert result["min"] == 0.1
        assert result["max"] == 0.9
        assert result["mean"] == 0.5
        assert result["stdev"] > 0
