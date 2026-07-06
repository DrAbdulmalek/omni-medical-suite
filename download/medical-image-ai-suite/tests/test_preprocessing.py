"""
اختبارات وحدات المعالجة المسبقة - Preprocessing Tests
"""

import os
import sys
import numpy as np
from pathlib import Path

# إضافة المسار
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_text_handler():
    """اختبار معالج النصوص"""
    from src.preprocessing.text_handler import TextHandler

    handler = TextHandler(language="ar")

    # اختبار التنظيف
    text = "التقرير يُظْهِرُ وجودَ ارتشاحٍ رئويٍّ في الرئةِ اليمنى"
    cleaned = handler.clean(text)
    assert "تشكيل" not in cleaned or len(cleaned) < len(text), "فشل إزالة التشكيل"
    assert "التقرير" in cleaned, "فقد نص أساسي"

    # اختبار تقسيم التقرير
    report = """القصة المرضية: ألم في الصدر

النتائج:
يوجد التهاب رئوي في الرئة اليمنى مع انصباب جنبي بسيط

الاستنتاج:
التهاب رئوي أيمن مع انصباب جنبي"""

    sections = handler.split_report(report)
    assert "findings" in sections or "نتائج" in str(sections).lower(), "فشل تقسيم التقرير"

    # اختبار كشف النفي
    negations = handler.detect_negation("لا يوجد انصباب جنبي وسالبة النتائج")
    assert len(negations) > 0, "فشل كشف النفي"

    # اختبار استخراج القياسات
    measurements = handler.extract_measurements("حجم الورم 2.5 سم مع سمك 3mm")
    assert len(measurements) >= 1, "فشل استخراج القياسات"

    print("✓ test_text_handler ناجح")


def test_medical_dictionary():
    """اختبار القاموس الطبي"""
    from src.ner.medical_entities import MedicalDictionary, MedicalEntityExtractor

    dictionary = MedicalDictionary()

    # اختبار البحث
    results = dictionary.search("التهاب رئوي في الرئة اليمنى")
    assert len(results) > 0, "فشل البحث في القاموس"

    # اختبار المستخرج
    extractor = MedicalEntityExtractor(dictionary)
    entities = extractor.extract("يوجد كسر في عظم الفخذ الأيسر مع نزيف")
    assert len(entities) > 0, "فشل الاستخراج"

    # اختبار التصدير
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        dictionary.export_json(f.name)
        assert os.path.exists(f.name), "فشل التصدير"
        os.unlink(f.name)

    print("✓ test_medical_dictionary ناجح")


def test_arabic_ner():
    """اختبار مستخرج الكيانات العربية"""
    from src.ner.arabic_ner import ArabicMedicalNER

    ner = ArabicMedicalNER(use_dictionary=True, use_patterns=True, use_model=False)

    # اختبار الاستخراج
    results = ner.extract("يظهر الفحص وجود التهاب رئوي في الرئة اليمنى مع انصباب جنبي بسيط")
    assert "entities" in results, "المفتاح entities غير موجود"
    assert len(results["entities"]) > 0, "لم يتم استخراج كيانات"

    # اختبار كشف النفي
    results_neg = ner.extract("لا يوجد انصباب جنبي والرئتان سليمتان")
    negated = results_neg.get("negated", [])
    assert len(negated) > 0, "فشل كشف النفي"

    # اختبار الإشارات
    labels = ner.extract_training_labels("يوجد التهاب رئوي حاد في الفص السفلي الأيمن")
    assert len(labels) > 0, "لم يتم استخراج إشارات"

    print("✓ test_arabic_ner ناجح")


def test_weak_labels():
    """اختبار مستخرج الإشارات الضعيفة"""
    from src.semisupervised.weak_labels import BinaryLabelExtractor, SegmentationLabelExtractor

    # اختبار المستخرج الثنائي
    binary_ext = BinaryLabelExtractor()
    labels = binary_ext.extract("يوجد التهاب رئوي في الرئة اليمنى مع انصباب جنبي")
    assert isinstance(labels, dict), "النتيجة ليست قاموساً"
    assert len(labels) > 0, "لم يتم استخراج إشارات ثنائية"

    # اختبار الاستخراج الجماعي
    reports = [
        "يوجد التهاب رئوي في الرئة اليمنى",
        "لا يوجد انصباب جنبي",
        "كسر في الضلع السادس مع ورم دموي",
        "تضخم القلب مع انصباب جنبي بسيط",
        "الرئتان سليمتان لا يوجد أي ارتشاح",
    ]
    label_matrix, class_names, stats = binary_ext.extract_batch(reports)
    assert label_matrix.ndim == 2, "مصفوفة الإشارات ليس ثنائية الأبعاد"
    assert len(class_names) > 0, "لم يتم تحديد فئات"

    # اختبار مستخرج الأقنعة
    seg_ext = SegmentationLabelExtractor(image_size=(256, 256))
    mask = seg_ext.extract_mask("ارتشاح رئوي في الفص السفلي الأيمن")
    assert mask.shape == (256, 256), "شكل القناع غير صحيح"
    assert mask.max() > 0, "القناع فارغ"

    print("✓ test_weak_labels ناجح")


def test_metrics():
    """اختبار مقاييس التقييم"""
    from src.utils.metrics import MedicalMetrics

    metrics = MedicalMetrics(num_classes=3, class_names=["normal", "pneumonia", "effusion"])

    # إضافة توقعات
    y_pred = np.array([0, 1, 2, 1, 0, 2, 1, 0])
    y_true = np.array([0, 1, 1, 1, 0, 2, 1, 0])
    y_prob = np.array([
        [0.9, 0.05, 0.05],
        [0.1, 0.8, 0.1],
        [0.1, 0.2, 0.7],
        [0.05, 0.9, 0.05],
        [0.85, 0.1, 0.05],
        [0.05, 0.05, 0.9],
        [0.1, 0.85, 0.05],
        [0.9, 0.05, 0.05],
    ])

    metrics.update(y_pred, y_true, y_prob)
    results = metrics.compute_classification()

    assert "accuracy" in results, "الدقة غير محسوبة"
    assert results["accuracy"] >= 0.5, "الدقة منخفضة جداً"

    # اختبار Dice
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask1[20:80, 20:80] = 1
    mask2 = mask1.copy()
    mask2[25:75, 25:75] = 1

    dice = MedicalMetrics.dice_coefficient(mask1, mask2)
    assert 0 < dice <= 1, "Dice خارج النطاق"

    # اختبار IoU
    iou = MedicalMetrics.iou_score(mask1, mask2)
    assert 0 < iou <= 1, "IoU خارج النطاق"

    # اختبار PSNR
    img1 = np.random.rand(100, 100).astype(np.float32)
    img2 = img1 + np.random.normal(0, 0.01, (100, 100)).astype(np.float32)
    psnr = MedicalMetrics.psnr(img1, img2)
    assert psnr > 0, "PSNR سالب"

    print("✓ test_metrics ناجح")


def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("=" * 50)
    print("Medical Image AI Suite - تشغيل الاختبارات")
    print("=" * 50)

    tests = [
        test_text_handler,
        test_medical_dictionary,
        test_arabic_ner,
        test_weak_labels,
        test_metrics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} فشل: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"النتيجة: {passed} نجح, {failed} فشل من أصل {len(tests)}")
    print(f"{'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
