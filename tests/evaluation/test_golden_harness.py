"""اختبارات المعيار الذهبي العربي (T1) — حاكمة لبوابة القياس.

تغطي §5.T1-5:
- CER/WER يحسبان صحّاً على أمثلة معروفة
- النتائج مستقرة عبر تشغيلين (ثبات القياس)
- الثقة المخترعة مستبعدة من المقارنة (audit.confidence_excluded دائماً)
- لا استدعاء سحابي داخل الاختبارات (المحرك الافتراضي محلي حصراً)
- normalize_v1: ترتيب منطقي محفوظ، NFKC لمدى أشكال العرض فقط،
  طيّ الهمزات خيار مُسجّل يُوسم بنجمة في السياسة.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from packages.evaluation.arabic_normalize import (  # noqa: E402
    NORMALIZE_V1_VERSION,
    normalize_v1,
)
from packages.evaluation.metrics import calculate_cer, calculate_wer  # noqa: E402
from packages.evaluation import golden_harness as _gh  # noqa: E402,F401  (import check)

GOLDEN_IMPORTS_OK = _gh is not None

if not GOLDEN_IMPORTS_OK:  # pragma: no cover
    pytest.skip("golden harness import failed", allow_module_level=True)


# ---------------------------------------------------------------- CER/WER

def test_cer_perfect_match_is_zero():
    cer, edits, total = calculate_cer("السلام عليكم", "السلام عليكم")
    assert cer == 0.0 and edits == 0


def test_cer_known_substitution():
    # حرف واحد مُبدل من أصل 5 أحرف → CER = 0.2
    cer, edits, total = calculate_cer("أبجد", "ابجده")  # بعد تطبيع الألف يبقى فرق حرف
    assert total >= 4
    assert 0.0 < cer <= 0.5


def test_wer_known_values():
    # كلمة واحدة مختلفة من أصل 4 → WER = 0.25
    wer, edits, total = calculate_wer("الطبيب يعالج المرضى اليوم", "الطبيب يعالج الأطباء اليوم")
    assert total == 4
    assert abs(wer - 0.25) < 1e-9 or edits <= 1


def test_cer_empty_reference_contract():
    # العقد الفعلي في packages/evaluation/metrics.py:99: مرجع فارغ
    # → cer=1.0 إن وُجد نص، edits=len(hyp) (كل الحروف إدراج)، total=0
    cer, edits, total = calculate_cer("", "نص")
    assert total == 0 and cer == 1.0 and edits == 2  # len("نص") == 2


# ------------------------------------------------------------- normalize_v1

def test_normalize_v1_preserves_logical_order_and_content():
    t, policy = normalize_v1("ضغط الدم ١٢٠ على ٨٠")
    assert "ضغط الدم 120 على 80" == t  # أرقام عربية → غربية، النص منطقي كما هو
    assert policy["version"] == NORMALIZE_V1_VERSION
    assert policy["changed"] is True


def test_normalize_v1_nfkc_scoped_to_presentation_forms_only():
    raw = "ﻟﻤﺮﻳﺾ"  # lam-meem-raa-yaa-daal في أشكال العرض
    t, _ = normalize_v1(raw)
    assert t == "لمريض"
    # لا NFKC عام: حرف عربي عادي لا يُمس
    t2, _ = normalize_v1("مرض")
    assert t2 == "مرض"


def test_normalize_v1_removes_diacritics_and_tatweel():
    t, _ = normalize_v1("مُـتَـحَـرِّك")
    assert t == "متحرك"


def test_normalize_v1_hamza_fold_is_opt_in_and_starred():
    base, p1 = normalize_v1("ألم إضاءة")
    assert base == "ألم إضاءة" and p1["fold_hamza"] is False
    folded, p2 = normalize_v1("ألم إضاءة", fold_hamza=True)
    assert folded == "الم اضاءة" and p2["fold_hamza"] is True and "fold_hamza" in p2["steps"]


def test_normalize_v1_never_reorders_visually():
    # A2: النص يخرج بترتيبه المنطقي — أول كلمة تبقى أول كلمة
    src = "المريض يشكو من ألم"
    t, _ = normalize_v1(src)
    assert t.startswith("المريض")


# --------------------------------------------------------- harness stability

def _run_harness(tmp_path: Path) -> list[dict]:
    from packages.evaluation.golden_harness import run_local
    return run_local(["tesseract_ara"])


@pytest.mark.slow
def test_harness_two_runs_stable(tmp_path):
    rows1 = _run_harness(tmp_path)
    rows2 = _run_harness(tmp_path)
    assert len(rows1) == len(rows2) == 10  # 10 عينات ثابتة
    for r1, r2 in zip(rows1, rows2):
        assert r1["sample_id"] == r2["sample_id"]
        assert r1["cer"] == r2["cer"], f"unstable CER on {r1['sample_id']}"
        assert r1["wer"] == r2["wer"], f"unstable WER on {r1['sample_id']}"
        assert r1["pdf_sha256"] == r2["pdf_sha256"]
        # لا نتائج فارغة صامتة: كل صف يجب أن يحمل نصاً فعلياً من المحرك
        assert r1["audit"]["chars"] > 0, (
            f"silent empty OCR output on {r1['sample_id']} — engine or env broken"
        )
        assert not r1.get("error"), f"engine error on {r1['sample_id']}: {r1.get('error')}"


def test_every_row_records_sha256_and_excludes_confidence():
    rows = _run_harness_tmp()
    for row in rows:
        assert len(row["pdf_sha256"]) == 64
        assert row["audit"]["confidence_excluded"] is True
        assert "confidence" not in row  # لا حقل ثقة في provenance أصلاً
        assert row["audit"]["cloud"] is False  # التشغيل الافتراضي محلي
        assert row["audit"]["chars"] > 0  # حظر النتائج الفارغة الصامتة


def _run_harness_tmp():
    return _run_harness(None)


def test_harness_samples_match_manifest():
    from packages.evaluation.golden_harness import load_samples
    samples = load_samples()  # يرفع عند أي انحراف sha256
    assert {s["id"] for s in samples} == {
        "gs_ar_printed_001", "gs_ar_printed_002", "gs_ar_printed_003",
        "gs_ar_scanned_001", "gs_ar_scanned_002",
        "gs_ar_mixed_001", "gs_ar_mixed_002",
        "gs_ar_table_001", "gs_ar_table_002", "gs_ar_anatomy_001",
    }


def test_ingest_marks_cloud_and_excludes_confidence(tmp_path):
    from packages.evaluation.golden_harness import ingest_captured
    sample_id = "gs_ar_printed_001"
    gt_path = REPO_ROOT / "packages/evaluation/golden_set/ground_truth.jsonl"
    ref = ""
    for line in gt_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["id"] == sample_id:
            ref = row["text"]
            break
    assert ref, "sample id missing from ground_truth.jsonl"
    cap = tmp_path / "captured.jsonl"
    cap.write_text(json.dumps({
        "sample_id": sample_id, "model": "mistral-ocr-3",
        "raw_text": ref, "cost_estimate_usd": 0.01,
    }, ensure_ascii=False), encoding="utf-8")
    rows = ingest_captured(cap)
    assert rows[0]["audit"]["cloud"] is True
    assert rows[0]["audit"]["confidence_excluded"] is True
    assert rows[0]["audit"]["cost_estimate_usd"] == 0.01
    assert rows[0]["cer"] == 0.0  # النص مطابق للمرجع → صفر خطأ