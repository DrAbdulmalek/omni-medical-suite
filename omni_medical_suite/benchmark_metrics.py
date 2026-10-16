"""Arabic OCR benchmark metrics — pure stdlib implementations (S3-T1 skeleton).

Design doc: marathon-suite/docs/plans/benchmark-200-design.md
Contract: pure functions only, no I/O, deterministic, unit-tested.
Normalization is a documented subset of ``arabic_strong_normalize`` (ocr-core):
strip tatweel + harakat, unify alef forms, ya/alef maqsura, ta-marbuta.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_TATWEEL = "\u0640"
_HARAKAT = re.compile(r"[\u064B-\u065F\u0670]")
_DIACRITIC_OR_SPACE = re.compile(r"[\s]+")


def normalize_arabic(text: str) -> str:
    """Documented normalization subset applied to both sides before CER/WER."""
    out = text.replace(_TATWEEL, "")
    out = _HARAKAT.sub("", out)
    out = out.replace("\u0623", "\u0627")  # alef-hamza-above -> alef
    out = out.replace("\u0625", "\u0627")  # alef-hamza-below -> alef
    out = out.replace("\u0622", "\u0627")  # alef-madda -> alef
    out = out.replace("\u0649", "\u064A")  # alef maqsura -> ya
    out = out.replace("\u0629", "\u0647")  # ta-marbuta -> ha
    out = _DIACRITIC_OR_SPACE.sub(" ", out)
    return out.strip()


def levenshtein(a: str, b: str) -> int:
    """Classic O(len(a)*len(b)) DP with a single rolling row (stdlib only)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate on normalized text: lev(ref, hyp) / len(ref)."""
    ref = normalize_arabic(reference)
    hyp = normalize_arabic(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate on normalized text: word-list edit distance / len(ref words)."""
    ref = normalize_arabic(reference).split()
    hyp = normalize_arabic(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, rw in enumerate(ref, 1):
        cur = [i]
        for j, hw in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw)))
        prev = cur
    return prev[-1] / len(ref)


STRATA = ("printed_clean", "printed_degraded", "hand_easy", "hand_hard", "mixed")
STRATA_SIZES = {"printed_clean": 40, "printed_degraded": 40, "hand_easy": 50,
                "hand_hard": 40, "mixed": 30}


@dataclass
class Manifest:
    """B200 manifest skeleton — the origin mapping stays LOCAL ONLY by design."""

    entries: list[dict] = field(default_factory=list)

    def build(self, image_names: Iterable[str]) -> "Manifest":
        counter = 0
        for stratum in STRATA:
            for _ in range(STRATA_SIZES[stratum]):
                counter += 1
                self.entries.append({
                    "id": f"b200_{counter:04d}",
                    "stratum": stratum,
                    "image": next(image_names, None),
                    "gt_a": None, "gt_b": None, "gt_final": None,
                })
        return self

    def validate(self) -> list[str]:
        """De-identification + completeness checks (skeleton rules)."""
        problems: list[str] = []
        ids = [e["id"] for e in self.entries]
        if len(ids) != len(set(ids)):
            problems.append("duplicate benchmark ids")
        long_digit = re.compile(r"\d{5,}")
        for e in self.entries:
            if e["image"] and long_digit.search(str(e["image"])):
                problems.append(f"{e['id']}: possible identifier in image name")
            if not e["gt_final"]:
                problems.append(f"{e['id']}: missing gt_final")
        return problems
