"""Phase 4 test: WeightedMedicalDeduplicator on real validation scenarios.

Tests:
1. Edge case: same template, different patient → is_same_patient MUST be False
2. Same document pairs → is_same_patient MUST be True
3. Different document → is_same_patient MUST be False
4. Batch dedup on mixed set → correct unique count
"""
import sys
sys.path.insert(0, "/home/z/my-project/omni-medical-suite")

from src.ocr.deduplication import WeightedMedicalDeduplicator, field_aware_similarity
from src.ocr.field_extractor import ArabicMedicalFieldExtractor

dedup = WeightedMedicalDeduplicator()

print("=" * 70)
print("PHASE 4 — Weighted Field-Aware Deduplication (Genspark integration)")
print("=" * 70)

# ── Test 1: Edge case — same template, different patient ──
print("\n[Test 1] Same template, different patient (THE critical edge case)")
print("-" * 60)

# Simulate the real scenario: same Arabic medical form, two different patients
# The template text is ~85% identical (hospital header, department, doctor, etc.)
# Only patient name, ID, and possibly date differ
same_template_patient_a = """
مستشفى الملك فهد التخصصي
قسم الباطنية
رقم الملف: MRN-2026-1007
اسم المريض: أحمد محمد العلي
تاريخ الميلاد: 15/03/1965
التاريخ: 2026-07-12
التشخيص: ارتفاع ضغط الدم الأساسي
الأدوية: أملوديبين 5mg، أسبرين 81mg
الطبيب المعالج: د. خالد الرشيدي
"""

same_template_patient_b = """
مستشفى الملك فهد التخصصي
قسم الباطنية
رقم الملف: MRN-2026-2044
اسم المريض: فاطمة سعيد الحربي
تاريخ الميلاد: 22/08/1978
التاريخ: 2026-07-12
التشخيص: ارتفاع ضغط الدم الأساسي
الأدوية: أملوديبين 5mg، لوسارتان 50mg
الطبيب المعالج: د. خالد الرشيدي
"""

result = dedup.compare(same_template_patient_a, same_template_patient_b)
print(f"  Weighted score:         {result.score:.4f}")
print(f"  patient_name similarity: {result.field_scores['patient_name']:.4f}")
print(f"  patient_id similarity:   {result.field_scores['patient_id']:.4f}")
print(f"  date similarity:         {result.field_scores['date']:.4f}")
print(f"  diagnosis similarity:    {result.field_scores['diagnosis']:.4f}")
print(f"  template_signature sim:  {result.field_scores['template_signature']:.4f}")
print(f"  is_same_patient:         {result.is_same_patient}")
print(f"  explanation:             {result.explanation}")

# Also check with raw fuzz.ratio for comparison
from rapidfuzz import fuzz
raw_ratio = fuzz.ratio(same_template_patient_a, same_template_patient_b)
print(f"\n  [COMPARISON] raw fuzz.ratio: {raw_ratio:.1f}% (was 98.3% in Phase 4 EasyOCR test)")

if result.is_same_patient:
    print("  ❌ FAIL — same template/different patient was classified as same patient!")
    edge_pass = False
else:
    print("  ✅ PASS — correctly rejected same-template/different-patient")
    edge_pass = True

# ── Test 2: Same document, minor OCR variation ──
print("\n[Test 2] Same document, minor OCR variation (should be duplicate)")
print("-" * 60)

doc_original = """
اسم المريض: أحمد محمد العلي
رقم المريض: MRN-2026-1007
التاريخ: 2026-07-12
التشخيص: ارتفاع ضغط الدم الأساسي
الأدوية: أملوديبين 5mg، أسبرين 81mg
"""

doc_ocr_variant = """
اسم المريض: احمد محمد العلي
رقم المريض: MRN-2026-1007
التاريخ: 2026-07-12
التشخيص: ارتفاع ضغط الدم الاساسي
الادوية: املوديبين 5mg، اسبرين 81mg
"""

result2 = dedup.compare(doc_original, doc_ocr_variant)
print(f"  Weighted score:         {result2.score:.4f}")
print(f"  patient_name similarity: {result2.field_scores['patient_name']:.4f}")
print(f"  patient_id similarity:   {result2.field_scores['patient_id']:.4f}")
print(f"  is_same_patient:         {result2.is_same_patient}")
print(f"  explanation:             {result2.explanation}")

if result2.is_same_patient:
    print("  ✅ PASS — same patient correctly detected despite OCR noise")
    same_pass = True
else:
    print("  ❌ FAIL — same patient was not detected!")
    same_pass = False

# ── Test 3: Different document entirely ──
print("\n[Test 3] Completely different document (should NOT be duplicate)")
print("-" * 60)

doc_different = """
اسم المريض: سارة عبدالله القحطاني
رقم المريض: MRN-2026-8899
التاريخ: 2026-06-01
التشخيص: التهاب الجيوب الأنفية المزمن
الأدوية: أموكسيسيلين 500mg، سودوافيدرين
"""

result3 = dedup.compare(doc_original, doc_different)
print(f"  Weighted score:         {result3.score:.4f}")
print(f"  patient_name similarity: {result3.field_scores['patient_name']:.4f}")
print(f"  patient_id similarity:   {result3.field_scores['patient_id']:.4f}")
print(f"  is_same_patient:         {result3.is_same_patient}")
print(f"  explanation:             {result3.explanation}")

if not result3.is_same_patient:
    print("  ✅ PASS — different patient correctly rejected")
    diff_pass = True
else:
    print("  ❌ FAIL — different patient incorrectly classified as same!")
    diff_pass = False

# ── Test 4: Batch dedup with mixed records ──
print("\n[Test 4] Batch dedup — 4 records (2 unique patients, 1 duplicate each)")
print("-" * 60)

records = [
    # Patient A - original
    "اسم المريض: أحمد محمد العلي\nرقم المريض: MRN-2026-1007\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم",
    # Patient A - OCR variant (should be detected as duplicate)
    "اسم المريض: احمد محمد العلي\nرقم المريض: MRN-2026-1007\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم الاساسي",
    # Patient B
    "اسم المريض: فاطمة سعيد الحربي\nرقم المريض: MRN-2026-2044\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم",
    # Patient B - OCR variant (should be detected as duplicate)
    "اسم المريض: فاطمة سعيد الحربي\nرقم المريض: MRN-2026-2044\nالتاريخ: 2026-07-12\nالتشخيص: ارتفاع ضغط الدم",
    # Patient C (same template, different patient - must NOT be merged with A or B)
    "اسم المريض: سارة عبدالله القحطاني\nرقم المريض: MRN-2026-8899\nالتاريخ: 2026-06-01\nالتشخيص: التهاب الجيوب الأنفية",
]

batch_result = dedup.deduplicate(records)
print(f"  Input records:    {batch_result['input_count']}")
print(f"  Unique records:   {batch_result['unique_count']}")
print(f"  Duplicates found: {len(batch_result['duplicates'])}")
for d in batch_result['duplicates']:
    src = d['source_index']
    match = d['matched_unique_index']
    sim = d['similarity']
    print(f"    Record {src} → matched unique {match} (score={sim['score']:.4f}, same_patient={sim['is_same_patient']})")

if batch_result['unique_count'] == 3 and len(batch_result['duplicates']) == 2:
    print("  ✅ PASS — batch correctly found 3 unique patients (A, B, C)")
    batch_pass = True
else:
    print(f"  ❌ FAIL — expected 3 unique, got {batch_result['unique_count']}")
    batch_pass = False

# ── Summary ──
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Test 1 (edge case: same-template/diff-patient):  {'PASS ✅' if edge_pass else 'FAIL ❌'}")
print(f"  Test 2 (same patient, OCR noise):                {'PASS ✅' if same_pass else 'FAIL ❌'}")
print(f"  Test 3 (different patient):                      {'PASS ✅' if diff_pass else 'FAIL ❌'}")
print(f"  Test 4 (batch: 3 unique from 5 records):        {'PASS ✅' if batch_pass else 'FAIL ❌'}")
all_pass = edge_pass and same_pass and diff_pass and batch_pass
print(f"\n  Overall: {'ALL PASSED ✅' if all_pass else 'SOME FAILED ❌'}")
sys.exit(0 if all_pass else 1)