"""اختبارات توافق مقاييس التقييم (F-13/F-16) — منع التطبيع المزدوج.

العقد الحاكم (المقترن مع ocr-core PR #56 / ocr_core.eval):
  تطبيع الطرفين عبر normalize_v1 (نقطة واحدة) ثم calculate_*(..., skip_internal_normalize=True).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.evaluation.arabic_normalize import normalize_v1
from packages.evaluation.metrics import calculate_cer, calculate_wer


def test_default_normalizes_internally():
    # الافتراضي (False) يطبّع داخلياً — توافق كامل مع السلوك السابق
    assert calculate_cer("إسلام", "اسلام") == (0.0, 0, 5)


def test_skip_true_changes_behavior():
    cer, edits, _ = calculate_cer("إسلام", "اسلام", skip_internal_normalize=True)
    assert cer > 0.0 and edits > 0


def test_governing_path_no_double_normalization():
    # المسار الحاكم: طبّع الطرفين عبر normalize_v1 ثم استدعِ بـ True
    ref_n, _ = normalize_v1("مُحَمَّد ١٢٣")
    hyp_n, _ = normalize_v1("محمد 123")
    cer, edits, _ = calculate_cer(ref_n, hyp_n, skip_internal_normalize=True)
    assert (cer, edits) == (0.0, 0)
    wer, _, _ = calculate_wer(ref_n, hyp_n, skip_internal_normalize=True)
    assert wer == 0.0


def test_wer_skip_kwarg():
    assert calculate_wer("الطبيب هنا", "الطبيب هناك", skip_internal_normalize=True) == (0.5, 1, 2)
