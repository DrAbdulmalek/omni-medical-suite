"""Unit tests for the B200 benchmark metrics skeleton (S3-T1, pure functions)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omni_medical_suite.benchmark_metrics import (  # noqa: E402
    Manifest,
    cer,
    levenshtein,
    normalize_arabic,
    wer,
)


def test_levenshtein_basics():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "abd") == 1
    assert levenshtein("kitten", "sitting") == 3


def test_cer_identical_is_zero():
    assert cer("وصفة طبية", "وصفة طبية") == 0.0


def test_cer_counts_edits_on_normalized_text():
    # hamza-form difference disappears after normalization -> zero edits
    assert cer("أحمد", "احمد") == 0.0
    # one real insertion -> 1 / len(ref)
    ref = "المريض يعاني"
    hyp = "المريض يعانني"
    assert abs(cer(ref, hyp) - 1 / len("المريض يعاني")) < 1e-9


def test_cer_empty_reference():
    assert cer("", "anything") == 1.0
    assert cer("", "") == 0.0


def test_wer_word_level():
    ref = "خمس مكتبات منفصلة"
    hyp = "خمس مكتبة منفصلة"  # one word substitution
    assert abs(wer(ref, hyp) - 1 / 3) < 1e-9
    assert wer("خمس مكتبات", "") == 1.0
    assert wer("", "كلمة") == 1.0


def test_normalize_arabic_rules():
    assert normalize_arabic("ـــ") == ""          # tatweel only
    assert normalize_arabic("مُحَمَّد") == "محمد"   # harakat stripped
    assert normalize_arabic("على") == normalize_arabic("عليٰ")  # maqsura unify


def test_manifest_build_and_validate():
    names = iter(f"img_{i}.png" for i in range(300))
    m = Manifest().build(names)
    assert len(m.entries) == 200
    problems = m.validate()
    # every entry lacks gt_final at skeleton stage -> flagged, ids unique
    assert all(p.startswith("b200_") or p == "duplicate benchmark ids" for p in problems)
    assert sum(1 for p in problems if "missing gt_final" in p) == 200


def test_manifest_flags_identifier_like_names():
    m = Manifest()
    m.entries = [{"id": "b200_0001", "stratum": "mixed",
                  "image": "patient_123456.png", "gt_final": "x"}]
    problems = m.validate()
    assert any("possible identifier" in p for p in problems)
