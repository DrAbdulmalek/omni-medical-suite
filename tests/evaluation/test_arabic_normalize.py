"""اختبارات وحدة التطبيع normalize_v1 (T1-a) — حاكمة لقرار A2 وNFKC المُقيَّد."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.evaluation.arabic_normalize import (  # noqa: E402
    NORMALIZE_V1_STEPS,
    NORMALIZE_V1_VERSION,
    normalize_v1,
)


def test_version_is_declared():
    assert NORMALIZE_V1_VERSION == "normalize_v1/1.0.0"
    assert len(NORMALIZE_V1_STEPS) >= 6


def test_preserves_logical_order_and_unifies_digits():
    t, policy = normalize_v1("ضغط الدم ١٢٠ على ٨٠")
    assert t == "ضغط الدم 120 على 80"
    assert policy["version"] == NORMALIZE_V1_VERSION
    assert policy["changed"] is True


def test_nfkc_scoped_to_presentation_forms_only():
    t, _ = normalize_v1("ﻟﻤﺮﻳﺾ")  # أشكال عرض (U+FB50–U+FEFF)
    assert t == "لمريض"
    t2, p2 = normalize_v1("مرض")  # حروف عربية أساسية لا تُمس
    assert t2 == "مرض" and p2["changed"] is False


def test_removes_diacritics_tatweel_zero_width():
    t, _ = normalize_v1("مُـتَـحَـرِّك\u200f")
    assert t == "متحرك"


def test_punctuation_unification():
    t, _ = normalize_v1("سؤال؟ جواب، نعم؛")
    assert t == "سؤال? جواب, نعم;"


def test_hamza_fold_is_opt_in_and_recorded():
    base, p1 = normalize_v1("ألم إضاءة")
    assert base == "ألم إضاءة" and p1["fold_hamza"] is False
    folded, p2 = normalize_v1("ألم إضاءة", fold_hamza=True)
    assert folded == "الم اضاءة"
    assert p2["fold_hamza"] is True and "fold_hamza" in p2["steps"]


def test_never_reorders_visually_a2():
    src = "المريض يشكو من ألم"
    t, _ = normalize_v1(src)
    assert t.startswith("المريض") and t.endswith("ألم")


def test_none_and_empty_contract():
    t, p = normalize_v1(None)
    assert t == "" and p["changed"] is False
    t2, p2 = normalize_v1("")
    assert t2 == "" and p2["changed"] is False