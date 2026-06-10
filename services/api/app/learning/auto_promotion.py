#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_promotion.py
Automatically promotes trusted corrections from the review queue 
to the active correction cache based on configurable quality criteria.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PromotionCriteria:
    """Configurable criteria for auto-promoting corrections."""
    min_frequency: int = 3
    min_confidence_gain: float = 0.05
    min_avg_confidence_after: float = 0.80
    max_age_days: int = 30
    require_cross_context: bool = True
    require_cross_language: bool = False
    no_medical_conflict: bool = True


@dataclass
class PromotionResult:
    """Result of a single promotion evaluation."""
    correction_id: int
    original: str
    corrected: str
    frequency: int
    confidence_gain: float
    promoted: bool = False
    reasons: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)


class AutoPromotionEngine:
    """
    Monitors the correction memory database and automatically promotes
    corrections that meet quality criteria from the review queue to 
    the active correction cache.
    
    Promotion criteria (all must pass):
    - min_frequency: Correction seen in >= N different files/contexts
    - min_confidence_gain: At least 5% improvement in confidence
    - min_avg_confidence_after: Corrected text confidence >= 0.80
    - max_age_days: Correction not older than 30 days
    - not already promoted
    """
    
    DEFAULT_CRITERIA = PromotionCriteria()

    def __init__(self, db_path: str, criteria: Optional[PromotionCriteria] = None):
        self.db_path = db_path
        self.criteria = criteria or self.DEFAULT_CRITERIA
        self.promotion_history: List[PromotionResult] = []

    def evaluate_candidate(self, row: sqlite3.Row) -> PromotionResult:
        """
        Evaluate a single correction for promotion eligibility.
        
        Args:
            row: SQLite Row containing correction data
            
        Returns:
            PromotionResult with evaluation details
        """
        checks = {
            "frequency_ok": row["frequency"] >= self.criteria.min_frequency,
            "gain_ok": row["confidence_gain"] >= self.criteria.min_confidence_gain,
            "confidence_ok": (
                row["confidence_after"] >= self.criteria.min_avg_confidence_after
            ),
            "age_ok": self._days_since(row["first_seen"]) <= self.criteria.max_age_days,
            "not_promoted": row["auto_promoted"] == 0,
        }
        
        all_passed = all(checks.values())
        reasons = []
        if not checks["frequency_ok"]:
            reasons.append(f"Frequency {row['frequency']} < {self.criteria.min_frequency}")
        if not checks["gain_ok"]:
            reasons.append(f"Gain {row['confidence_gain']:.3f} < {self.criteria.min_confidence_gain}")
        if not checks["confidence_ok"]:
            reasons.append(
                f"Confidence {row['confidence_after']:.2f} < "
                f"{self.criteria.min_avg_confidence_after}"
            )
        if not checks["age_ok"]:
            reasons.append(f"Age {self._days_since(row['first_seen'])}d > {self.criteria.max_age_days}d")
        if not checks["not_promoted"]:
            reasons.append("Already promoted")
        
        return PromotionResult(
            correction_id=row["id"],
            original=row["original"],
            corrected=row["corrected"],
            frequency=row["frequency"],
            confidence_gain=row["confidence_gain"],
            promoted=all_passed,
            reasons=reasons,
            checks=checks,
        )

    def run_promotion_cycle(self) -> List[PromotionResult]:
        """
        Run a full promotion cycle over all pending corrections.
        
        Returns:
            List of PromotionResult for evaluated corrections
        """
        results: List[PromotionResult] = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute(
                "SELECT * FROM corrections "
                "WHERE frequency >= ? AND auto_promoted = 0 "
                "ORDER BY frequency DESC, confidence_gain DESC",
                (self.criteria.min_frequency,),
            )
            
            for row in cur.fetchall():
                result = self.evaluate_candidate(row)
                if result.promoted:
                    cur.execute(
                        "UPDATE corrections SET auto_promoted = 1 WHERE id = ?",
                        (result.correction_id,),
                    )
                results.append(result)
        
        self.promotion_history.extend(results)
        return results

    def get_promotion_stats(self) -> Dict:
        """Get statistics about promotion history."""
        total = len(self.promotion_history)
        promoted = sum(1 for r in self.promotion_history if r.promoted)
        rejected = total - promoted
        return {
            "total_evaluated": total,
            "promoted": promoted,
            "rejected": rejected,
            "promotion_rate": promoted / total if total > 0 else 0.0,
        }

    def _days_since(self, iso_date: str) -> int:
        """Calculate days since a given ISO date string."""
        try:
            return (datetime.now() - datetime.fromisoformat(iso_date)).days
        except (ValueError, TypeError):
            return 999  # treat unparseable dates as very old
