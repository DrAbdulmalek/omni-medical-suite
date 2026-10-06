"""Hybrid cascading router: student model first, ABBYY as fallback.

Production policy mirroring the "Fallback / Cascading Architecture":

* documents/lines the *student* model recognises confidently are served by
  the student (cheaper, faster, no licence cost);
* low-confidence units are escalated to the FineReader SDK / Engine as a
  fallback until the standalone model matures;
* the grey zone goes to human-in-the-loop review (the repo's existing
  review/HITL services).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import PageAnnotation, RouteDecision


@dataclass
class CascadeThresholds:
    """Routing thresholds (all confidences in [0, 1])."""

    accept: float = 0.92   # >= accept  -> trust the student output
    escalate: float = 0.60  # <  escalate -> send to ABBYY fallback
    suspicious_penalty: float = 0.05  # subtracted per suspicious flag (capped)
    max_penalty: float = 0.25


@dataclass
class CascadeReport:
    """Aggregate of routing decisions over one page/document."""

    decisions: list[RouteDecision] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"student": 0, "review": 0, "abbyy_fallback": 0}
        for d in self.decisions:
            out[d.engine] = out.get(d.engine, 0) + 1
        return out

    @property
    def fallback_ratio(self) -> float:
        if not self.decisions:
            return 0.0
        return self.counts.get("abbyy_fallback", 0) / len(self.decisions)

    def to_dict(self) -> dict:
        return {
            "counts": self.counts,
            "fallback_ratio": round(self.fallback_ratio, 4),
            "decisions": [d.to_dict() for d in self.decisions],
        }


class CascadeRouter:
    """Confidence-based routing between the student model, HITL review and
    the ABBYY FineReader fallback."""

    def __init__(self, thresholds: Optional[CascadeThresholds] = None) -> None:
        self.thresholds = thresholds or CascadeThresholds()

    def decide(self, confidence: float, suspicious: bool = False, suspicious_count: int = 0) -> RouteDecision:
        t = self.thresholds
        c = max(0.0, min(1.0, float(confidence)))
        if suspicious_count:
            penalty = min(t.max_penalty, suspicious_count * t.suspicious_penalty)
            c = max(0.0, c - penalty)
        elif suspicious:
            c = max(0.0, c - t.suspicious_penalty)

        if c >= t.accept and not suspicious:
            return RouteDecision(
                engine="student",
                reason=f"confidence {c:.2f} >= accept {t.accept:.2f} and no suspicious flags",
                confidence=c,
                suspicious=False,
            )
        if c < t.escalate:
            return RouteDecision(
                engine="abbyy_fallback",
                reason=f"confidence {c:.2f} < escalate {t.escalate:.2f} -> FineReader fallback",
                confidence=c,
                suspicious=suspicious,
            )
        return RouteDecision(
            engine="review",
            reason=f"confidence {c:.2f} in grey zone [{t.escalate:.2f}, {t.accept:.2f}) -> HITL review",
            confidence=c,
            suspicious=suspicious,
        )

    def route_page(self, annotation: PageAnnotation) -> CascadeReport:
        """Route every line of a parsed teacher page (teacher output used as
        the confidence proxy for the student engine in training runs)."""
        report = CascadeReport()
        for line in annotation.lines:
            if not line.text.strip():
                continue
            susp = any(w.suspicious for w in line.words)
            susp_count = sum(1 for w in line.words if w.suspicious)
            report.decisions.append(
                self.decide(line.confidence, suspicious=susp, suspicious_count=susp_count)
            )
        return report

    def route_student_result(self, lines: list[tuple[str, float]], suspicious: Optional[list[bool]] = None) -> CascadeReport:
        """Route results coming from the *student* engine at inference time.

        Args:
            lines: list of ``(text, confidence)`` tuples from the student OCR.
            suspicious: optional per-line suspicion flags (e.g. ABBYY-style
                'suspicious character' equivalents produced by our validators).
        """
        suspicious = suspicious or [False] * len(lines)
        report = CascadeReport()
        for (text, conf), susp in zip(lines, suspicious):
            if not text.strip():
                continue
            report.decisions.append(self.decide(conf, suspicious=susp))
        return report
