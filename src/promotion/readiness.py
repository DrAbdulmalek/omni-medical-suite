#!/usr/bin/env python3
"""
ReadinessScorer — Automated readiness evaluation for datasets and models.

Computes a 0-100 readiness score based on configurable criteria:
  - schema_valid  (25 pts): all files parse correctly against expected schema
  - min_samples   (20 pts): at least N samples present
  - cer_threshold (20 pts): CER below max allowed
  - has_benchmark (15 pts): benchmark report file exists
  - has_changelog (10 pts): changelog file exists
  - reviewed      (10 pts): human review flag set
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════

@dataclass
class CriterionResult:
    """Result for a single readiness criterion."""

    name: str
    points_max: int
    points_earned: int
    passed: bool
    message: str


@dataclass
class ReadinessReport:
    """Full readiness evaluation report."""

    dataset_id: str
    total_score: int
    max_score: int
    percentage: float
    criteria: List[CriterionResult]
    recommendations: List[str]
    ready_for_stage: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# ReadinessScorer
# ══════════════════════════════════════════════════════════════════

class ReadinessScorer:
    """
    Evaluates dataset/model readiness using configurable scoring criteria.

    Each criterion contributes a fixed number of points toward a total of 100.
    The scorer inspects the dataset directory on disk and any associated
    metadata (evaluation results, review flags, etc.) to compute scores.

    Parameters
    ----------
    base_dir : Path
        Root directory containing dataset subdirectories.
    thresholds : dict, optional
        Override default thresholds for CER, min samples, etc.
    """

    # Default scoring weights and thresholds
    DEFAULT_THRESHOLDS = {
        "min_samples": 100,
        "cer_max": 0.05,          # 5% CER for printed text
        "wer_max": 0.15,          # 15% WER
        "cer_max_handwritten": 0.12,  # 12% for handwritten
    }

    CRITERION_WEIGHTS = {
        "schema_valid": 25,
        "min_samples": 20,
        "cer_threshold": 20,
        "has_benchmark": 15,
        "has_changelog": 10,
        "reviewed": 10,
    }

    def __init__(
        self,
        base_dir: Path,
        thresholds: Optional[Dict[str, Any]] = None,
    ):
        self.base_dir = Path(base_dir)
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        logger.info(
            "ReadinessScorer initialized with base_dir=%s, thresholds=%s",
            self.base_dir,
            self.thresholds,
        )

    # ── Public API ──────────────────────────────────────────────

    def score(self, dataset_id: str) -> ReadinessReport:
        """
        Compute the full readiness report for a dataset.

        Parameters
        ----------
        dataset_id : str
            Identifier of the dataset (used as subdirectory name).

        Returns
        -------
        ReadinessReport
            Complete score breakdown with per-criteria details and
            actionable recommendations.
        """
        dataset_dir = self.base_dir / dataset_id
        criteria: List[CriterionResult] = []

        criteria.append(self._check_schema_valid(dataset_id, dataset_dir))
        criteria.append(self._check_min_samples(dataset_id, dataset_dir))
        criteria.append(self._check_cer_threshold(dataset_id, dataset_dir))
        criteria.append(self._check_has_benchmark(dataset_id, dataset_dir))
        criteria.append(self._check_has_changelog(dataset_id, dataset_dir))
        criteria.append(self._check_reviewed(dataset_id, dataset_dir))

        total_score = sum(c.points_earned for c in criteria)
        max_score = sum(c.points_max for c in criteria)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0.0

        recommendations = self._generate_recommendations(criteria, percentage)
        ready_stage = self._determine_ready_stage(percentage, criteria)

        report = ReadinessReport(
            dataset_id=dataset_id,
            total_score=total_score,
            max_score=max_score,
            percentage=round(percentage, 1),
            criteria=criteria,
            recommendations=recommendations,
            ready_for_stage=ready_stage,
        )

        logger.info(
            "Readiness score for %s: %d/%d (%.1f%%) — ready for: %s",
            dataset_id,
            total_score,
            max_score,
            percentage,
            ready_stage or "none",
        )

        return report

    def quick_check(self, dataset_id: str) -> bool:
        """Return True if the dataset meets the minimum score for 'candidate' stage (50+)."""
        report = self.score(dataset_id)
        return report.percentage >= 50.0

    # ── Individual Criterion Checks ─────────────────────────────

    def _check_schema_valid(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that all data files parse correctly (25 pts)."""
        name = "schema_valid"
        max_pts = self.CRITERION_WEIGHTS[name]

        if not dataset_dir.exists():
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=0,
                passed=False,
                message=f"Dataset directory does not exist: {dataset_dir}",
            )

        # Collect all JSONL and JSON files
        data_files = list(dataset_dir.glob("*.jsonl")) + list(dataset_dir.glob("*.json"))

        if not data_files:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=0,
                passed=False,
                message="No JSON/JSONL data files found in dataset directory",
            )

        total_entries = 0
        parse_errors = 0

        for fpath in data_files:
            try:
                if fpath.suffix == ".jsonl":
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            json.loads(line)
                            total_entries += 1
                else:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            total_entries += len(data)
                        else:
                            total_entries += 1
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                parse_errors += 1
                logger.warning("Parse error in %s: %s", fpath.name, exc)

        if parse_errors == 0 and total_entries > 0:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=max_pts,
                passed=True,
                message=f"All {len(data_files)} file(s) valid ({total_entries} entries)",
            )

        # Partial credit: proportional to successfully parsed files
        valid_files = len(data_files) - parse_errors
        earned = int(max_pts * valid_files / len(data_files))
        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=earned,
            passed=False,
            message=(
                f"{parse_errors}/{len(data_files)} file(s) failed to parse. "
                f"Valid entries: {total_entries}"
            ),
        )

    def _check_min_samples(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that at least N samples are present (20 pts)."""
        name = "min_samples"
        max_pts = self.CRITERION_WEIGHTS[name]
        min_required = self.thresholds["min_samples"]

        if not dataset_dir.exists():
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=0,
                passed=False,
                message=f"Dataset directory does not exist: {dataset_dir}",
            )

        sample_count = self._count_samples(dataset_dir)

        if sample_count >= min_required:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=max_pts,
                passed=True,
                message=f"{sample_count} samples (required: {min_required})",
            )

        # Proportional credit
        ratio = sample_count / min_required
        earned = int(max_pts * ratio)
        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=earned,
            passed=False,
            message=(
                f"Only {sample_count} samples found (required: {min_required}). "
                f"Need {min_required - sample_count} more."
            ),
        )

    def _check_cer_threshold(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that CER/WER are below acceptable thresholds (20 pts)."""
        name = "cer_threshold"
        max_pts = self.CRITERION_WEIGHTS[name]

        eval_report = dataset_dir / "evaluation_results.json"
        if not eval_report.exists():
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=0,
                passed=False,
                message="No evaluation_results.json found. Run benchmarks first.",
            )

        try:
            with open(eval_report, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=0,
                passed=False,
                message=f"Failed to read evaluation results: {exc}",
            )

        metrics = eval_data.get("metrics", {})
        cer = metrics.get("cer", metrics.get("character_error_rate", 1.0))
        wer = metrics.get("wer", metrics.get("word_error_rate", 1.0))

        # Determine which CER threshold to use
        data_type = eval_data.get("data_type", "printed")
        cer_max = (
            self.thresholds["cer_max_handwritten"]
            if data_type == "handwritten"
            else self.thresholds["cer_max"]
        )
        wer_max = self.thresholds["wer_max"]

        cer_ok = cer <= cer_max
        wer_ok = wer <= wer_max

        if cer_ok and wer_ok:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=max_pts,
                passed=True,
                message=f"CER={cer:.4f} (<={cer_max}), WER={wer:.4f} (<={wer_max})",
            )

        # Partial credit if at least CER passes
        if cer_ok:
            earned = max_pts // 2
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=earned,
                passed=False,
                message=(
                    f"CER OK ({cer:.4f} <={cer_max}) but WER too high "
                    f"({wer:.4f} >{wer_max})"
                ),
            )

        # Proportional credit based on how close CER is to threshold
        ratio = min(cer_max / max(cer, 0.0001), 1.0)
        earned = int(max_pts * ratio)
        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=earned,
            passed=False,
            message=(
                f"CER={cer:.4f} (max {cer_max}), WER={wer:.4f} (max {wer_max}). "
                f"Both metrics exceed thresholds."
            ),
        )

    def _check_has_benchmark(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that a benchmark report file exists (15 pts)."""
        name = "has_benchmark"
        max_pts = self.CRITERION_WEIGHTS[name]

        benchmark_patterns = ["benchmark_report.json", "benchmark_report.md", "readiness_report.md"]
        found = None
        for pattern in benchmark_patterns:
            candidate = dataset_dir / pattern
            if candidate.exists():
                found = candidate
                break

        # Also check in a reports/ subdirectory
        if found is None:
            reports_dir = dataset_dir / "reports"
            if reports_dir.exists():
                for pattern in benchmark_patterns:
                    candidate = reports_dir / pattern
                    if candidate.exists():
                        found = candidate
                        break

        if found:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=max_pts,
                passed=True,
                message=f"Benchmark report found: {found.name}",
            )

        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=0,
            passed=False,
            message="No benchmark report found. Generate one before promotion.",
        )

    def _check_has_changelog(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that a changelog file exists (10 pts)."""
        name = "has_changelog"
        max_pts = self.CRITERION_WEIGHTS[name]

        changelog_patterns = ["CHANGELOG.md", "changelog.md", "CHANGES.md"]
        found = None
        for pattern in changelog_patterns:
            candidate = dataset_dir / pattern
            if candidate.exists():
                found = candidate
                break

        if found:
            return CriterionResult(
                name=name,
                points_max=max_pts,
                points_earned=max_pts,
                passed=True,
                message=f"Changelog found: {found.name}",
            )

        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=0,
            passed=False,
            message="No changelog found. Generate one with the changelog tool.",
        )

    def _check_reviewed(self, dataset_id: str, dataset_dir: Path) -> CriterionResult:
        """Check that human review flag is set (10 pts)."""
        name = "reviewed"
        max_pts = self.CRITERION_WEIGHTS[name]

        # Check for a metadata file with a review flag
        meta_file = dataset_dir / "metadata.json"
        if not meta_file.exists():
            meta_file = dataset_dir / "promotion_meta.json"

        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("reviewed", False) or meta.get("human_reviewed", False):
                    reviewer = meta.get("reviewer", meta.get("reviewed_by", "unknown"))
                    return CriterionResult(
                        name=name,
                        points_max=max_pts,
                        points_earned=max_pts,
                        passed=True,
                        message=f"Human-reviewed by {reviewer}",
                    )
                else:
                    return CriterionResult(
                        name=name,
                        points_max=max_pts,
                        points_earned=0,
                        passed=False,
                        message="Metadata exists but human_reviewed flag is not set.",
                    )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read metadata for %s: %s", dataset_id, exc)

        return CriterionResult(
            name=name,
            points_max=max_pts,
            points_earned=0,
            passed=False,
            message="No metadata file with review flag found. Require human review.",
        )

    # ── Helpers ─────────────────────────────────────────────────

    def _count_samples(self, dataset_dir: Path) -> int:
        """Count the total number of data entries across all data files."""
        count = 0
        for fpath in list(dataset_dir.glob("*.jsonl")) + list(dataset_dir.glob("*.json")):
            try:
                if fpath.suffix == ".jsonl":
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                count += 1
                else:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            count += len(data)
                        else:
                            count += 1
            except (json.JSONDecodeError, OSError):
                pass
        return count

    def _generate_recommendations(
        self, criteria: List[CriterionResult], percentage: float
    ) -> List[str]:
        """Generate actionable recommendations based on failed criteria."""
        recommendations = []

        for c in criteria:
            if not c.passed:
                if c.name == "schema_valid":
                    recommendations.append(
                        "Fix JSON parse errors in data files. Run schema validation."
                    )
                elif c.name == "min_samples":
                    min_req = self.thresholds["min_samples"]
                    recommendations.append(
                        f"Collect more samples. At least {min_req} are required for promotion."
                    )
                elif c.name == "cer_threshold":
                    recommendations.append(
                        "Improve model accuracy. Retrain with additional data or adjust hyperparameters."
                    )
                elif c.name == "has_benchmark":
                    recommendations.append(
                        "Generate a benchmark report by running evaluation benchmarks."
                    )
                elif c.name == "has_changelog":
                    recommendations.append(
                        "Generate a changelog documenting changes for this version."
                    )
                elif c.name == "reviewed":
                    recommendations.append(
                        "Obtain human review. Set 'human_reviewed: true' in metadata.json."
                    )

        if percentage < 30:
            recommendations.insert(
                0,
                "Score is very low (< 30%). This dataset needs significant work before promotion.",
            )
        elif percentage < 60:
            recommendations.insert(
                0,
                "Score is below 60%. Focus on the highest-weighted failing criteria first.",
            )

        return recommendations

    def _determine_ready_stage(
        self, percentage: float, criteria: List[CriterionResult]
    ) -> Optional[str]:
        """
        Determine which promotion stage the dataset is ready for.

        Stage readiness thresholds:
          - draft:      always (entry point)
          - candidate:  score >= 50 and schema_valid + min_samples pass
          - approved:   score >= 75 and schema_valid + min_samples + cer_threshold + reviewed pass
          - production: score >= 90 and all criteria pass
        """
        passed_names = {c.name for c in criteria if c.passed}

        if percentage >= 90 and len(passed_names) == len(criteria):
            return "production"

        if (
            percentage >= 75
            and "schema_valid" in passed_names
            and "min_samples" in passed_names
            and "cer_threshold" in passed_names
            and "reviewed" in passed_names
        ):
            return "approved"

        if percentage >= 50 and "schema_valid" in passed_names and "min_samples" in passed_names:
            return "candidate"

        return "draft"