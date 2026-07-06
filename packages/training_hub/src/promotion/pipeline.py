#!/usr/bin/env python3
"""
PromotionPipeline — 4-stage promotion workflow for datasets and models.

Stages:  draft → candidate → approved → production

Each promotion requires the dataset to meet stage-specific readiness criteria.
State is persisted in a JSON file (promotion_state.json) for reproducibility
and auditability.

Rules:
  - Cannot skip stages (must go through each one in order).
  - Cannot demote without providing a reason string.
  - Readiness score is computed via ReadinessScorer before each promotion.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .readiness import ReadinessScorer, ReadinessReport
from .changelog import AutoChangelog

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════

STAGES = ["draft", "candidate", "approved", "production"]

# Minimum readiness score (out of 100) required to enter each stage
STAGE_MIN_SCORES = {
    "draft": 0,
    "candidate": 50,
    "approved": 75,
    "production": 90,
}

# For production: specific criteria that must all pass
PRODUCTION_REQUIRED_CRITERIA = [
    "schema_valid",
    "min_samples",
    "cer_threshold",
    "has_benchmark",
    "has_changelog",
    "reviewed",
]

DEFAULT_STATE_FILENAME = "promotion_state.json"


# ══════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════

@dataclass
class PromotionHistoryEntry:
    """A single entry in the promotion history log."""

    timestamp: str
    action: str  # "promoted", "demoted", "registered", "readiness_checked"
    from_stage: Optional[str]
    to_stage: Optional[str]
    score: Optional[int]
    reason: Optional[str] = None


@dataclass
class DatasetState:
    """Persistent state for a single dataset's promotion journey."""

    dataset_id: str
    stage: str = "draft"
    last_score: Optional[int] = None
    last_scored_at: Optional[str] = None
    registered_at: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetState":
        return cls(**data)

    def add_history_entry(
        self,
        action: str,
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None,
        score: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        entry = PromotionHistoryEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            from_stage=from_stage,
            to_stage=to_stage,
            score=score,
            reason=reason,
        )
        self.history.append(asdict(entry))


# ══════════════════════════════════════════════════════════════════
# PromotionPipeline
# ══════════════════════════════════════════════════════════════════

class PromotionPipeline:
    """
    Orchestrates the 4-stage promotion workflow for datasets/models.

    The pipeline persists state in a JSON file and integrates with
    ReadinessScorer for automated readiness checks and AutoChangelog
    for changelog generation.

    Parameters
    ----------
    state_file : Path, optional
        Path to the JSON state file. Defaults to promotion_state.json
        in the current working directory.
    datasets_dir : Path, optional
        Root directory containing dataset subdirectories. Used by
        ReadinessScorer to inspect dataset files.
    scorer_thresholds : dict, optional
        Override default readiness thresholds.
    """

    def __init__(
        self,
        state_file: Optional[Path] = None,
        datasets_dir: Optional[Path] = None,
        scorer_thresholds: Optional[Dict[str, Any]] = None,
    ):
        self.state_file = Path(state_file) if state_file else Path(DEFAULT_STATE_FILENAME)
        self.datasets_dir = Path(datasets_dir) if datasets_dir else Path.cwd() / "training_data"

        # Lazy-loaded components
        self._scorer: Optional[ReadinessScorer] = None
        self._changelog: Optional[AutoChangelog] = None
        self._scorer_thresholds = scorer_thresholds or {}

        # Load existing state
        self._state: Dict[str, DatasetState] = {}
        self._load_state()

        logger.info(
            "PromotionPipeline initialized — state_file=%s, datasets_dir=%s, %d dataset(s) loaded",
            self.state_file,
            self.datasets_dir,
            len(self._state),
        )

    # ── Properties ──────────────────────────────────────────────

    @property
    def scorer(self) -> ReadinessScorer:
        """Lazy-init the readiness scorer."""
        if self._scorer is None:
            self._scorer = ReadinessScorer(
                base_dir=self.datasets_dir,
                thresholds=self._scorer_thresholds,
            )
        return self._scorer

    @property
    def changelog_gen(self) -> AutoChangelog:
        """Lazy-init the changelog generator."""
        if self._changelog is None:
            self._changelog = AutoChangelog(repo_dir=self.datasets_dir.parent)
        return self._changelog

    # ── Public API ──────────────────────────────────────────────

    def register(self, dataset_id: str, initial_stage: str = "draft") -> DatasetState:
        """
        Register a new dataset in the promotion pipeline.

        Parameters
        ----------
        dataset_id : str
            Unique identifier for the dataset.
        initial_stage : str
            Starting stage (must be "draft").

        Returns
        -------
        DatasetState
            The newly created dataset state.

        Raises
        ------
        ValueError
            If the dataset is already registered or the initial stage is invalid.
        """
        if dataset_id in self._state:
            raise ValueError(f"Dataset '{dataset_id}' is already registered.")

        if initial_stage != "draft":
            raise ValueError(
                f"New datasets must start at 'draft' stage, got '{initial_stage}'."
            )

        ds = DatasetState(
            dataset_id=dataset_id,
            stage=initial_stage,
            registered_at=datetime.now().isoformat(),
        )
        ds.add_history_entry(action="registered", to_stage="draft")
        self._state[dataset_id] = ds
        self._save_state()

        logger.info("Registered dataset '%s' at stage 'draft'", dataset_id)
        return ds

    def promote(
        self,
        dataset_id: str,
        target_stage: str,
        force: bool = False,
    ) -> DatasetState:
        """
        Promote a dataset to the next stage (or a specific target stage).

        Parameters
        ----------
        dataset_id : str
            The dataset to promote.
        target_stage : str
            The stage to promote to. Must be the immediate next stage
            unless force=True.
        force : bool
            If True, skip stage-adjacency checks (but still require
            readiness scoring).

        Returns
        -------
        DatasetState
            Updated dataset state after promotion.

        Raises
        ------
        ValueError
            If the dataset is not registered, target stage is invalid,
            stages are skipped, or readiness criteria are not met.
        """
        if dataset_id not in self._state:
            raise ValueError(f"Dataset '{dataset_id}' is not registered. Use register() first.")

        if target_stage not in STAGES:
            raise ValueError(
                f"Invalid target stage '{target_stage}'. Must be one of: {STAGES}"
            )

        ds = self._state[dataset_id]
        current_idx = STAGES.index(ds.stage)
        target_idx = STAGES.index(target_stage)

        # Validate promotion direction (no demotion through promote())
        if target_idx <= current_idx:
            raise ValueError(
                f"Cannot promote from '{ds.stage}' to '{target_stage}' — "
                f"target must be a later stage. Use demote() to go backward."
            )

        # Check stage adjacency (can't skip stages)
        if not force and target_idx != current_idx + 1:
            raise ValueError(
                f"Cannot skip stages: '{ds.stage}' → '{target_stage}'. "
                f"Must promote through each stage in order, or use force=True."
            )

        # Run readiness check
        report = self.check_readiness(dataset_id)

        # Validate readiness score for target stage
        min_score = STAGE_MIN_SCORES[target_stage]
        if report.total_score < min_score and not force:
            raise ValueError(
                f"Readiness score {report.total_score} is below the minimum "
                f"{min_score} required for stage '{target_stage}'. "
                f"Recommendations: {'; '.join(report.recommendations)}"
            )

        # For production: all criteria must pass
        if target_stage == "production" and not force:
            failed_criteria = [
                c.name for c in report.criteria if not c.passed
            ]
            if failed_criteria:
                raise ValueError(
                    f"All criteria must pass for production promotion. "
                    f"Failed: {failed_criteria}"
                )

        # Perform the promotion
        old_stage = ds.stage
        ds.stage = target_stage
        ds.last_score = report.total_score
        ds.last_scored_at = datetime.now().isoformat()
        ds.add_history_entry(
            action="promoted",
            from_stage=old_stage,
            to_stage=target_stage,
            score=report.total_score,
        )
        self._save_state()

        logger.info(
            "Promoted '%s': %s → %s (score: %d)",
            dataset_id, old_stage, target_stage, report.total_score,
        )
        return ds

    def demote(
        self,
        dataset_id: str,
        target_stage: str,
        reason: str,
    ) -> DatasetState:
        """
        Demote a dataset to a previous stage.

        Requires a reason string explaining why the demotion is necessary.

        Parameters
        ----------
        dataset_id : str
            The dataset to demote.
        target_stage : str
            The stage to demote to.
        reason : str
            Mandatory explanation for the demotion.

        Returns
        -------
        DatasetState
            Updated dataset state after demotion.

        Raises
        ------
        ValueError
            If the dataset is not registered, target is not a prior stage,
            or reason is empty.
        """
        if not reason or not reason.strip():
            raise ValueError("A reason string is required for demotion.")

        if dataset_id not in self._state:
            raise ValueError(f"Dataset '{dataset_id}' is not registered.")

        if target_stage not in STAGES:
            raise ValueError(
                f"Invalid target stage '{target_stage}'. Must be one of: {STAGES}"
            )

        ds = self._state[dataset_id]
        current_idx = STAGES.index(ds.stage)
        target_idx = STAGES.index(target_stage)

        if target_idx >= current_idx:
            raise ValueError(
                f"Cannot demote from '{ds.stage}' to '{target_stage}' — "
                f"target must be an earlier stage. Use promote() to go forward."
            )

        old_stage = ds.stage
        ds.stage = target_stage
        ds.add_history_entry(
            action="demoted",
            from_stage=old_stage,
            to_stage=target_stage,
            reason=reason.strip(),
        )
        self._save_state()

        logger.warning(
            "Demoted '%s': %s → %s. Reason: %s",
            dataset_id, old_stage, target_stage, reason.strip(),
        )
        return ds

    def check_readiness(self, dataset_id: str) -> ReadinessReport:
        """
        Compute the readiness score for a dataset.

        Parameters
        ----------
        dataset_id : str
            The dataset to evaluate.

        Returns
        -------
        ReadinessReport
            Full readiness breakdown with per-criteria scores and recommendations.
        """
        report = self.scorer.score(dataset_id)

        # Update state with latest score
        if dataset_id in self._state:
            ds = self._state[dataset_id]
            ds.last_score = report.total_score
            ds.last_scored_at = datetime.now().isoformat()
            ds.add_history_entry(
                action="readiness_checked",
                score=report.total_score,
            )
            self._save_state()

        return report

    def get_status(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current promotion status of a dataset.

        Returns a dictionary with stage, score, history, and readiness details,
        or None if the dataset is not registered.

        Parameters
        ----------
        dataset_id : str

        Returns
        -------
        dict or None
        """
        if dataset_id not in self._state:
            return None

        ds = self._state[dataset_id]
        return {
            "dataset_id": ds.dataset_id,
            "stage": ds.stage,
            "stage_index": STAGES.index(ds.stage),
            "last_score": ds.last_score,
            "last_scored_at": ds.last_scored_at,
            "registered_at": ds.registered_at,
            "history_count": len(ds.history),
            "history": ds.history,
            "metadata": ds.metadata,
            "next_stage": (
                STAGES[STAGES.index(ds.stage) + 1]
                if STAGES.index(ds.stage) < len(STAGES) - 1
                else None
            ),
            "min_score_for_next": (
                STAGE_MIN_SCORES[STAGES[STAGES.index(ds.stage) + 1]]
                if STAGES.index(ds.stage) < len(STAGES) - 1
                else None
            ),
        }

    def list_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        """
        List all datasets at a given stage.

        Parameters
        ----------
        stage : str
            One of: draft, candidate, approved, production.

        Returns
        -------
        list of dict
            Each entry contains dataset_id, last_score, and registered_at.
        """
        if stage not in STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of: {STAGES}")

        results = []
        for ds in self._state.values():
            if ds.stage == stage:
                results.append({
                    "dataset_id": ds.dataset_id,
                    "stage": ds.stage,
                    "last_score": ds.last_score,
                    "last_scored_at": ds.last_scored_at,
                    "registered_at": ds.registered_at,
                })

        return sorted(results, key=lambda x: x.get("dataset_id", ""))

    def list_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all registered datasets grouped by stage.

        Returns
        -------
        dict
            Keys are stage names, values are lists of dataset summaries.
        """
        result = {stage: self.list_by_stage(stage) for stage in STAGES}
        result["_total"] = len(self._state)
        return result

    def remove(self, dataset_id: str) -> bool:
        """
        Remove a dataset from the promotion pipeline entirely.

        Parameters
        ----------
        dataset_id : str

        Returns
        -------
        bool
            True if the dataset was removed, False if not found.
        """
        if dataset_id in self._state:
            del self._state[dataset_id]
            self._save_state()
            logger.info("Removed dataset '%s' from pipeline", dataset_id)
            return True
        return False

    def generate_changelog(
        self,
        dataset_id: str,
        from_ref: str = "HEAD~20",
        to_ref: str = "HEAD",
        version: str = "Unreleased",
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate a changelog for a dataset.

        Parameters
        ----------
        dataset_id : str
            Dataset identifier.
        from_ref, to_ref : str
            Git refs for the changelog range.
        version : str
            Version string.
        output_path : Path, optional
            If provided, write the changelog to this file.

        Returns
        -------
        str
            Generated markdown changelog.
        """
        dataset_dir = self.datasets_dir / dataset_id
        if not dataset_dir.exists():
            dataset_dir = None  # Fall back to message-based filtering

        return self.changelog_gen.generate_for_dataset(
            dataset_id=dataset_id,
            dataset_dir=dataset_dir,
            from_ref=from_ref,
            to_ref=to_ref,
            version=version,
        )

    # ── State Persistence ───────────────────────────────────────

    def _load_state(self):
        """Load state from the JSON file, creating defaults if needed."""
        if not self.state_file.exists():
            logger.info("No state file found at %s — starting fresh", self.state_file)
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_datasets = data.get("datasets", {})
            for ds_id, ds_data in raw_datasets.items():
                self._state[ds_id] = DatasetState.from_dict(ds_data)

            logger.info(
                "Loaded %d dataset(s) from %s",
                len(self._state),
                self.state_file,
            )
        except (json.JSONDecodeError, OSError, TypeError, KeyError) as exc:
            logger.error(
                "Failed to load state from %s: %s — starting fresh",
                self.state_file,
                exc,
            )
            self._state = {}

    def _save_state(self):
        """Persist current state to the JSON file."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "datasets": {
                ds_id: ds.to_dict() for ds_id, ds in self._state.items()
            },
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to save state to %s: %s", self.state_file, exc)
            raise