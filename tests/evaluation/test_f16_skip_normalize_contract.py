"""عقد F-16 — skip_internal_normalize في calculate_cer/calculate_wer.

يُثبت أربعة أمور حاكمة:
1. legacy callers: السلوك الافتراضي (skip_internal_normalize=False) لم يتغير إطلاقاً —
   بما فيه compute_cer/compute_wer وevaluate() وتحمّل None.
2. pre-normalized input: مع skip_internal_normalize=True تُقارن السلاسل كما وردت
   حرفياً — الفروق التي كان التطبيق الداخلي يطويها تُكشف.
3. منع double-normalization: مسار الـharness يطبّع الطرفين مرة واحدة حصراً عبر
   normalize_v1 ثم يستدعي المقاييس بـskip=True — لو جرى تطبيع داخلي ثانٍ
   (_normalize_arabic) لتغيّرت النتيجة (زوج المستشفى/مستشفي).
4. mutation-negative: إزالة البرامتر كلياً أو تجاهله (العودة للتطبيع الداخلي
   غير المشروط) تجعل هذه الاختبارات تفشل — توقيعاً وسلوكاً.

الزوج المرجعي المميز: «مستشفى» مقابل «مستشفي» (ى مقابل ي، 6 أحرف لكلٍّ) —
التطبيق الداخلي القديم يطوي ى→ي فيطمس الفرق (CER=0.0)،
بينما المقارنة المباشرة تكشفه (CER=1/6).
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from packages.evaluation.arabic_normalize import normalize_v1  # noqa: E402
from packages.evaluation.metrics import (  # noqa: E402
    _normalize_arabic,
    calculate_cer,
    calculate_wer,
    compute_cer,
    compute_wer,
    evaluate,
)

# الزوج المميز: يطويه التطبيق الداخلي القديم إلى تطابق، وتكشفه المقارنة المباشرة.
REF_FOLD = "مستشفى"   # تنتهي بـ ى
HYP_FOLD = "مستشفي"   # تنتهي بـ ي
FOLD_CER = 1 / 6      # بديل واحد من أصل 6 أحرف

# زوج الأرقام: normalize_v1 يحول ٥→5، بينما _normalize_arabic يترك ٥ كما هي —
# لذا يكشف ما إذا كان المرجع في مسار الـharness مطبَّعاً بالسياسة الكانونية أم لا.
REF_DIGITS = "مستشفى ٥"
HYP_DIGITS = "مستشفى 5"


# ══════════════════════════════════════════════ 1) legacy callers لم تتغير ══

def test_legacy_default_folds_ya_and_alef():
    """السلوك القديم: ى→ي وإ/أ→ا داخل المقاييس افتراضياً — CER=0.0."""
    cer, edits, total = calculate_cer(REF_FOLD, HYP_FOLD)
    assert cer == 0.0 and edits == 0 and total == 6


def test_legacy_default_diacritics_and_hamza_still_folded():
    cer, _, _ = calculate_cer("أَبجد", "ابجد")
    assert cer == 0.0


def test_legacy_wer_default_unchanged():
    wer, edits, total = calculate_wer(REF_FOLD + " كبير", HYP_FOLD + " كبير")
    assert wer == 0.0 and edits == 0 and total == 2


def test_legacy_aliases_unchanged():
    assert compute_cer(REF_FOLD, HYP_FOLD) == 0.0
    assert compute_wer(REF_FOLD + " كبير", HYP_FOLD + " كبير") == 0.0


def test_legacy_evaluate_unchanged():
    result = evaluate(REF_FOLD, HYP_FOLD)
    assert result.cer == 0.0 and result.wer == 0.0


def test_legacy_none_tolerance_unchanged():
    """تحمّل None في المسار الافتراضي كما هو: مرجع فارغ → إدراج كامل."""
    cer, edits, total = calculate_cer(None, "نص")
    assert (cer, edits, total) == (1.0, 2, 0)
    cer_w, edits_w, total_w = calculate_wer(None, "نص")
    assert (cer_w, edits_w, total_w) == (1.0, 1, 0)


def test_legacy_existing_harness_pairs_unchanged():
    """أزواج اختبارات الـharness القائمة تبقى بقيمها على المسار الافتراضي."""
    cer, edits, total = calculate_cer("السلام عليكم", "السلام عليكم")
    assert cer == 0.0 and edits == 0
    cer2, _, _ = calculate_cer("أبجد", "ابجده")
    assert 0.0 < cer2 <= 0.5


# ════════════════════════════════════ 2) pre-normalized input يعمل ══════════

def test_prenormalized_exposes_ya_difference():
    """مع skip=True تُقارن السلاسل حرفياً: ى≠ي → بديل واحد من 7."""
    cer, edits, total = calculate_cer(REF_FOLD, HYP_FOLD, skip_internal_normalize=True)
    assert total == 6
    assert edits == 1
    assert cer == pytest.approx(FOLD_CER)
    assert cer > 0.0  # الفرق الذي كان يُطمس صار مكشوفاً


def test_prenormalized_wer_exposes_difference():
    wer, edits, total = calculate_wer(
        REF_FOLD + " كبير", HYP_FOLD + " كبير", skip_internal_normalize=True
    )
    assert total == 2 and edits == 1
    assert wer == pytest.approx(0.5)


def test_prenormalized_identical_strings_zero():
    cer, edits, _ = calculate_cer(REF_FOLD, REF_FOLD, skip_internal_normalize=True)
    assert cer == 0.0 and edits == 0


def test_prenormalized_agrees_with_manual_levenshtein():
    """نتيجة skip=True تطابق الحساب اليدوي على السلاسل المطبَّعة سلفاً."""
    ref_n, _ = normalize_v1("أَبجد ٥")
    hyp_n, _ = normalize_v1("ابجد 5")
    cer, edits, total = calculate_cer(ref_n, hyp_n, skip_internal_normalize=True)
    from packages.evaluation.metrics import _levenshtein_distance
    manual_edits, _, _ = _levenshtein_distance(ref_n, hyp_n)
    assert edits == manual_edits
    assert cer == pytest.approx(manual_edits / len(ref_n))


# ══════════════════════════════════ 3) منع double-normalization ═════════════

def test_no_double_normalization_skip_flag_is_honored_not_ignored():
    """لو جرى تطبيع داخلي ثانٍ بعد normalize_v1 لَطُوِيَ الفرق وعاد CER إلى 0.0 —
    بقاء القيمة 1/6 يثبت أن التطبيع الداخلي لم يُشغَّل (تطبيع واحد حصراً)."""
    ref_n, _ = normalize_v1(REF_FOLD)   # normalize_v1 لا يطوي ى
    hyp_n, _ = normalize_v1(HYP_FOLD)   # فالفرق باقٍ بعد التطبيع الكانوني
    assert ref_n != hyp_n
    cer, _, _ = calculate_cer(ref_n, hyp_n, skip_internal_normalize=True)
    assert cer == pytest.approx(FOLD_CER)  # لولا honored لكان 0.0


def test_normalize_v1_is_idempotent_single_pass_semantics():
    once, p1 = normalize_v1("مُستشفى ٥")
    twice, _ = normalize_v1(once)
    assert once == twice
    assert p1["changed"] is True


def test_harness_reference_side_uses_normalize_v1_single_pass(tmp_path):
    """مسار الـharness: المرجع يُطبَّع بـnormalize_v1 مرة واحدة مثل الفرضية —
    أرقام المرجع العربية-الهندية تتحول للغربية فتطابق ناتج المحرك.

    بالسلوك القديم كان المرجع خاماً يُطبَّع بـ_normalize_arabic (تبقى ٥)
    والفرضية بـnormalize_v1 ثم _normalize_arabic (تصير 5) — فاختُرق CER
    على نص متطابق دلالياً.
    """
    from packages.evaluation.golden_harness import _provenance_row
    tmp = tmp_path / "probe.bin"
    tmp.write_bytes(b"f16-probe")
    sample = {
        "id": "gs_unit_f16",
        "category": "unit",
        "path": tmp,
        "reference": REF_DIGITS,
    }
    out = {"text": HYP_DIGITS, "model": "unit-probe", "cloud": False, "latency_ms": 0.0}
    row = _provenance_row(sample, "unit_probe", out)
    assert row["cer"] == 0.0, f"CER should be 0.0, got {row['cer']}"
    assert row["wer"] == 0.0
    # الأدلة على التطبيع المتماثل أحادي المرة في السجل
    assert row["normalized_text"] == normalize_v1(HYP_DIGITS)[0]
    assert row["normalize_policy"]["version"].startswith("normalize_v1/")


# ════════════════════════════════ 4) mutation-negative proof ════════════════

@pytest.mark.parametrize("fn", [calculate_cer, calculate_wer])
def test_mutation_negative_flag_exists_keyword_only_default_false(fn):
    """الطفرات التي يعترضها هذا الاختبار:
    a) حذف skip_internal_normalize من التوقيع كلياً → KeyError.
    b) تغييره لموضعي (positional) → kind mismatch.
    c) تغيير الافتراضي إلى True → سلوك legacy ينعكس في الاختبارات أعلاه."""
    p = inspect.signature(fn).parameters["skip_internal_normalize"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is False


@pytest.mark.parametrize("fn", [calculate_cer, calculate_wer])
def test_mutation_negative_ignoring_flag_is_detected(fn):
    """لو عومل skip=True كأنه skip=False (تجاهل الطفرة الشائع) لانقلب
    هذا التوكيد: التطبيق الداخلي سيطوي ى→ي ويعيد 0.0 بدل 1/6."""
    if fn is calculate_cer:
        value = fn(REF_FOLD, HYP_FOLD, skip_internal_normalize=True)[0]
    else:
        value = fn(REF_FOLD + " كبير", HYP_FOLD + " كبير", skip_internal_normalize=True)[0]
    assert value > 0.0


def test_mutation_negative_harness_must_normalize_reference(tmp_path):
    """إزالة تطبيع المرجع في الـharness (أو إزالة skip=True منها) تعيد
    إنتاج الخلل القديم: ٥ مقابل 5 تُحسب خطأً على نص متطابق دلالياً."""
    from packages.evaluation.golden_harness import _provenance_row
    tmp = tmp_path / "probe.bin"
    tmp.write_bytes(b"f16-probe")
    sample = {"id": "gs_unit_f16b", "category": "unit", "path": tmp, "reference": REF_DIGITS}
    out = {"text": HYP_DIGITS, "model": "unit-probe", "cloud": False, "latency_ms": 0.0}
    row = _provenance_row(sample, "unit_probe", out)
    assert row["cer"] == 0.0


def test_mutation_negative_guard_against_silent_policy_divergence():
    """سياسة التطبيع في الـharness والمقاييس يجب أن تبقى مميزة وموثقة:
    _normalize_arabic (القديمة، للمستدعين القدامى) ≠ normalize_v1 (الكانونية).
    هذا الاختبار يفشل إذا اختلطت السياسات بصمت — مثلاً إذا صار الافتراضي
    يطابق normalize_v1 أو صار skip يطبّع بـ_normalize_arabic."""
    # الدليل على أن السياستين مختلفتان فعلاً (وإلا فالتمييز بلا معنى):
    assert _normalize_arabic(REF_DIGITS) != normalize_v1(REF_DIGITS)[0]
    assert _normalize_arabic(REF_FOLD) != normalize_v1(REF_FOLD)[0]
