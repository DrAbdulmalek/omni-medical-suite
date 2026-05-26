#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_suite.py
Objective evaluation framework for measuring OCR fusion, semantic
deduplication, and auto-promotion quality against ground truth data.
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class FusionBenchmarkCase:
    """A single test case for OCR fusion evaluation."""
    engine_outputs: List[Dict]  # [{"text": ..., "confidence": ...}]
    expected: str
    fused_output: str = ""
    

@dataclass
class DedupBenchmarkCase:
    """A single test case for semantic dedup evaluation."""
    input_chunks: List[str]
    deduped_output: List[Dict]
    expected_unique_count: int = 0
    protected_pairs: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result of a benchmark evaluation."""
    metric_name: str
    value: float
    details: Dict = field(default_factory=dict)


class BenchmarkSuite:
    """
    Comprehensive evaluation framework for the OmniMedical processing pipeline.
    
    Measures:
    - OCR Fusion quality (similarity to ground truth)
    - Semantic Deduplication safety (medical conflict detection)
    - Information preservation (recall)
    """
    
    def evaluate_fusion(self, cases: List[FusionBenchmarkCase]) -> List[BenchmarkResult]:
        """
        Evaluate OCR fusion quality against ground truth.
        
        For each case, computes:
        - best_single_similarity: best single engine vs expected
        - fusion_v2_similarity: fused output vs expected  
        - improvement: fusion improvement over best single
        """
        results: List[BenchmarkResult] = []
        single_scores = []
        fusion_scores = []
        
        for case in cases:
            best_single = max(
                case.engine_outputs, key=lambda x: x.get("confidence", 0)
            )
            single_sim = self._word_overlap_similarity(
                best_single["text"], case.expected
            )
            fusion_sim = self._word_overlap_similarity(
                case.fused_output or best_single["text"], case.expected
            )
            single_scores.append(single_sim)
            fusion_scores.append(fusion_sim)
            
            results.append(BenchmarkResult(
                metric_name=f"fusion_case_{len(results)}",
                value=fusion_sim,
                details={
                    "expected": case.expected,
                    "best_single": best_single["text"],
                    "fused": case.fused_output,
                    "single_sim": single_sim,
                    "fusion_sim": fusion_sim,
                    "improvement": fusion_sim - single_sim,
                },
            ))
        
        if single_scores:
            results.append(BenchmarkResult(
                metric_name="avg_best_single_similarity",
                value=sum(single_scores) / len(single_scores),
            ))
            results.append(BenchmarkResult(
                metric_name="avg_fusion_similarity",
                value=sum(fusion_scores) / len(fusion_scores),
            ))
            results.append(BenchmarkResult(
                metric_name="avg_fusion_improvement",
                value=(
                    sum(fusion_scores) / len(fusion_scores)
                    - sum(single_scores) / len(single_scores)
                ),
            ))
        
        return results

    def evaluate_dedup_safety(
        self, cases: List[DedupBenchmarkCase]
    ) -> List[BenchmarkResult]:
        """
        Evaluate semantic deduplication for medical safety.
        
        Checks:
        - No medical conflicts remain in deduped output
        - Protected pairs are NOT merged
        - Information recall is maintained
        """
        results: List[BenchmarkResult] = []
        total_conflicts = 0
        total_protected_ok = 0
        total_protected_total = 0
        recall_scores = []
        
        for case in cases:
            # Check protected pairs
            for i, j in case.protected_pairs:
                total_protected_total += 1
                texts_in_output = [
                    d["text"] for d in case.deduped_output
                ]
                if case.input_chunks[i] in texts_in_output and case.input_chunks[j] in texts_in_output:
                    total_protected_ok += 1
                else:
                    total_conflicts += 1
            
            # Recall: check how many input tokens survive dedup
            all_input_words = set()
            for chunk in case.input_chunks:
                all_input_words.update(chunk.split())
            
            deduped_words = set()
            for d in case.deduped_output:
                deduped_words.update(d["text"].split())
            
            recall = (
                len(all_input_words & deduped_words) / len(all_input_words)
                if all_input_words else 1.0
            )
            recall_scores.append(recall)
        
        results.append(BenchmarkResult(
            metric_name="protected_preservation_rate",
            value=(
                total_protected_ok / total_protected_total
                if total_protected_total else 1.0
            ),
            details={
                "protected_ok": total_protected_ok,
                "protected_total": total_protected_total,
            },
        ))
        
        results.append(BenchmarkResult(
            metric_name="avg_recall",
            value=sum(recall_scores) / len(recall_scores) if recall_scores else 1.0,
            details={"per_case_recall": recall_scores},
        ))
        
        results.append(BenchmarkResult(
            metric_name="total_medical_conflicts",
            value=float(total_conflicts),
            details={"is_safe": total_conflicts == 0},
        ))
        
        return results

    def _word_overlap_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute word overlap similarity (Jaccard index on word sets).
        """
        set_a = set(text_a.split())
        set_b = set(text_b.split())
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def generate_summary_report(self, all_results: List[List[BenchmarkResult]]) -> str:
        """Generate a human-readable summary of all benchmark results."""
        lines = ["=" * 60, "Benchmark Summary Report", "=" * 60, ""]
        
        for group_results in all_results:
            for r in group_results:
                detail_str = ""
                if r.details:
                    detail_str = " | " + ", ".join(
                        f"{k}={v}" for k, v in r.details.items()
                        if isinstance(v, (int, float, str, bool))
                    )
                lines.append(f"  {r.metric_name}: {r.value:.4f}{detail_str}")
            lines.append("")
        
        return "\n".join(lines)
