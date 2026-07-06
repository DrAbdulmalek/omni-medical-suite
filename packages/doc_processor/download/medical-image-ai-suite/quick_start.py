#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Medical Image AI Suite - سكريبت البدء السريع
==============================================
تشغيل: python quick_start.py

يجمع بين تجربة شاملة لجميع المحاور الأربعة:
  1. معالجة صور DICOM/JPG
  2. استخراج الكيانات الطبية (NER) من التقارير العربية
  3. إشارات تدريب ضعيفة + تدريب شبه خاضع للإشراف
  4. تعزيز البيانات وتوليد اصطناعي
  5. توليد تقارير تلقائية من الصور
"""

import sys
import os
import time
import json
import numpy as np
from pathlib import Path

# إضافة المسار
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def print_header(title: str):
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def demo_text_processing():
    """المحور 1: معالجة النصوص الطبية العربية"""
    print_header("المحور 1: معالجة النصوص الطبية العربية")

    from src.preprocessing.text_handler import TextHandler
    handler = TextHandler(language="ar")

    # تقرير نموذجي
    report = """تقرير الفحص الشعاعي للصدر
القصة المرضية: مريض عمره 55 سنة يشكو من سعال وألم صدري
النتائج: يُظهر الفحص وجود التهاب رئوي في الفص السفلي الأيمن
مع انصباب جنبي بسيط في الجانب الأيسر. القلب بحجم طبيعي.
لا يوجد استرواح صدر.
الاستنتاج: التهاب رئوي أيمن سفلية مع انصباب جنبي أيسر بسيط"""

    # تنظيف النص
    cleaned = handler.clean(report)
    print(f"✓ تنظيف النص: {len(report)} → {len(cleaned)} حرف")

    # تقسيم الأقسام
    sections = handler.split_report(report)
    filled = [k for k, v in sections.items() if v]
    print(f"✓ الأقسام المكتشفة: {filled}")

    # كشف النفي
    negations = handler.detect_negation(report)
    negated = [s for s, info in negations.items() if info["is_negated"]]
    print(f"✓ الجمل المنفية: {len(negated)}")
    for s in negated:
        print(f"    ❌ {s[:60]}")

    # استخراج القياسات
    meas = handler.extract_measurements("حجم الورم 3.5 سم مع سمك جدار 2mm ونسبة 15%")
    print(f"✓ القياسات المستخرجة: {len(meas)}")
    for m in meas:
        print(f"    {m['value']} {m['unit']} ← {m['context'][:40]}")

    return cleaned, sections


def demo_ner(cleaned_text: str):
    """المحور 2: استخراج الكيانات الطبية (NER)"""
    print_header("المحور 2: استخراج الكيانات الطبية (NER)")

    from src.ner.arabic_ner import ArabicMedicalNER
    from src.ner.medical_entities import MedicalDictionary

    # عرض القاموس
    dictionary = MedicalDictionary()
    categories = dictionary.get_categories()
    total_entities = sum(len(v) for v in dictionary.entities.values())
    print(f"✓ القاموس الطبي: {total_entities} كيان في {len(categories)} تصنيف")

    # استخراج الكيانات
    ner = ArabicMedicalNER(use_dictionary=True, use_patterns=True, use_model=False)
    results = ner.extract(cleaned_text)

    entities = results["entities"]
    print(f"\n✓ الكيانات المستخرجة ({len(entities)}):")
    print(f"  {'الحالة':8s} | {'العربية':20s} | {'الإنجليزية':25s} | {'التصنيف'}")
    print(f"  {'-'*8} | {'-'*20} | {'-'*25} | {'-'*10}")
    for e in entities:
        status = "❌ منفي" if e.get("is_negated") else "✅ موجو"
        conf = e.get("confidence", 0)
        print(f"  {status:8s} | {e.get('ar','')[:20]:20s} | {e.get('en','')[:25]:25s} | {e.get('category','')}")

    # العلاقات
    relations = results["relations"]
    if relations:
        print(f"\n✓ العلاقات المستخرجة ({len(relations)}):")
        for rel in relations:
            print(f"    {rel['subject']} → {rel['relations']}")

    # الإشارات
    labels = results["labels"]
    print(f"\n✓ إشارات التصنيف: {labels}")

    return results


def demo_weak_labels():
    """المحور 3: إشارات تدريب ضعيفة + شبه خاضع للإشراف"""
    print_header("المحور 3: إشارات تدريب ضعيفة (Weak Labels)")

    from src.semisupervised.weak_labels import (
        BinaryLabelExtractor, SegmentationLabelExtractor, WeakLabelExtractor
    )

    # تقارير نموذجية
    reports = [
        "يوجد التهاب رئوي في الرئة اليمنى مع انصباب جنبي",
        "لا يوجد ارتشاح رئوي والرئتان سليمتان تماماً",
        "كسر في الضلع السادس والسابع الأيمن مع ورم دموي رئوي",
        "تضخم القلب مع انصباب جنبي بسيط في الجانب الأيسر",
        "الرئتان سالمتان لا يوجد أي مرض أو ارتشاح",
        "يوجد ورم في الفص العلوي الأيمن حجمه 3 سم",
        "استرواح صدر يساري مع انصباب جنبي يساري معتدل",
        "نقائل رئوية ثنائية الجانب مع انصباب جنبي",
    ]

    # استخراج إشارات ثنائية
    extractor = BinaryLabelExtractor()
    label_matrix, class_names, stats = extractor.extract_batch(reports, min_frequency=1)

    print(f"✓ مصفوفة الإشارات: {label_matrix.shape}")
    print(f"✓ عدد الفئات: {len(class_names)}")
    print(f"  الفئات: {class_names}")
    print(f"  كثافة التسميات: {stats['label_density']:.1%}")
    print(f"  متوسط الإشارات/تقرير: {stats['avg_labels_per_report']:.1f}")

    # عرض المصفوفة
    print(f"\n  {'التقرير':10s}", end="")
    for cn in class_names:
        print(f" | {cn[:15]:15s}", end="")
    print()
    print(f"  {'-'*10}", end="")
    for _ in class_names:
        print(f" | {'-'*15}", end="")
    print()
    for i, (row, report) in enumerate(zip(label_matrix, reports)):
        short = report[:30].replace("\n", " ")
        print(f"  {short:30s}", end="")
        for val in row:
            sym = "●" if val > 0.5 else "○" if val < -0.5 else "·"
            print(f" | {sym:^15s}", end="")
        print()

    # أقنعة التقسيم
    print(f"\n✓ أقنعة التقسيم التقريبية:")
    seg_ext = SegmentationLabelExtractor(image_size=(256, 256))
    test_reports = [
        "ارتشاح رئوي في الفص السفلي الأيمن",
        "انصباب جنبي ثنائي الجانب",
        "تضخم القلب مع توسع المنصف",
    ]
    for r in test_reports:
        mask = seg_ext.extract_mask(r)
        coverage = np.mean(mask > 0.1) * 100
        print(f"    '{r[:40]}' → تغطية القناع: {coverage:.1f}%")

    return label_matrix, class_names


def demo_image_augmentation():
    """المحور 4: تعزيز البيانات وتوليد اصطناعي"""
    print_header("المحور 4: تعزيز البيانات (Augmentation)")

    from src.preprocessing.image_handler import ImageHandler

    handler = ImageHandler(target_size=(256, 256))

    # إنشاء صورة تجريبية تحاكي صورة صدر
    np.random.seed(42)
    size = 256
    img = np.zeros((size, size), dtype=np.float32)
    img[:] = 20  # خلفية داكنة

    # رئة يمنى
    yy, xx = np.ogrid[:size, :size]
    right = ((xx - size*0.3)**2 / (size*0.22)**2 + (yy - size*0.45)**2 / (size*0.35)**2) < 1
    img[right] = 180

    # رئة يسرى
    left = ((xx - size*0.7)**2 / (size*0.2)**2 + (yy - size*0.45)**2 / (size*0.32)**2) < 1
    img[left] = 170

    # قلب
    heart = ((xx - size*0.5)**2 / (size*0.12)**2 + (yy - size*0.48)**2 / (size*0.15)**2) < 1
    img[heart] = 220

    # تعزيز البيانات
    print(f"✓ الصورة الأصلية: {img.shape}")

    augmented_versions = []
    aug_names = ["أصلية", "دوران 10°", "سطوع 1.2×", "قلب أفقي", "ضوضاء", "تكبير 1.1×"]

    augmented_versions.append(img)
    for i in range(5):
        aug = handler.apply_augmentation(img)
        augmented_versions.append(aug)

    print(f"✓ نسخ مُحسّنة: {len(augmented_versions)}")

    # توليد مجموعة بيانات مُحسّنة
    images_batch = np.stack([img] * 10, axis=0)
    aug_dataset, labels = handler.generate_augmented_dataset(images_batch, augmentations_per_image=5)
    print(f"✓ مجموعة مُحسّنة: {len(images_batch)} → {len(aug_dataset)} صورة")
    print(f"  (كل صورة × 6 نسخ = {len(images_batch) * 6})")

    return augmented_versions


def demo_report_generation():
    """المحور 5: توليد تقارير تلقائية"""
    print_header("المحور 5: توليد تقارير تلقائية (Template)")

    from src.reportgen.vlm_reporter import ReportGenerator

    generator = ReportGenerator(language="ar")

    # محاكاة نتائج NER
    ner_results = {
        "entities": [
            {"ar": "التهاب رئوي", "en": "pneumonia", "category": "DISEASE", "is_negated": False, "text": "التهاب رئوي"},
            {"ar": "ايمن", "en": "right", "category": "LATERALITY", "is_negated": False, "text": "ايمن"},
            {"ar": "انصباب جنبي", "en": "pleural effusion", "category": "DISEASE", "is_negated": False, "text": "انصباب جنبي"},
            {"ar": "ايسر", "en": "left", "category": "LATERALITY", "is_negated": False, "text": "ايسر"},
            {"ar": "استرواح صدر", "en": "pneumothorax", "category": "DISEASE", "is_negated": True, "text": "استرواح صدر"},
        ],
        "relations": [
            {"subject": "التهاب رئوي", "relations": {"location": "ايمن", "laterality": "ايمن"}},
            {"subject": "انصباب جنبي", "relations": {"location": "ايسر", "laterality": "ايسر"}},
        ],
        "labels": {"pneumonia": 1.0, "pleural_effusion": 1.0, "pneumothorax": -1.0, "abnormal": 1.0},
    }

    report = generator.generate_report(
        image=np.random.rand(256, 256).astype(np.float32),
        ner_results=ner_results,
        use_template=True,
    )

    print("✓ التقرير المُولّد:")
    print("-" * 40)
    print(report)
    print("-" * 40)

    return report


def demo_metrics():
    """مقاييس التقييم"""
    print_header("مقاييس التقييم الطبية")

    from src.utils.metrics import MedicalMetrics

    metrics = MedicalMetrics(num_classes=4, class_names=["normal", "pneumonia", "effusion", "cardiomegaly"])

    # بيانات تجريبية
    y_true = np.array([0, 1, 2, 1, 0, 3, 1, 0, 2, 3])
    y_pred = np.array([0, 1, 2, 1, 1, 3, 1, 0, 1, 3])
    y_prob = np.array([
        [0.8, 0.1, 0.05, 0.05],
        [0.1, 0.7, 0.1, 0.1],
        [0.05, 0.1, 0.8, 0.05],
        [0.1, 0.7, 0.1, 0.1],
        [0.3, 0.5, 0.1, 0.1],
        [0.05, 0.05, 0.1, 0.8],
        [0.1, 0.8, 0.05, 0.05],
        [0.85, 0.05, 0.05, 0.05],
        [0.2, 0.5, 0.2, 0.1],
        [0.05, 0.05, 0.1, 0.8],
    ])

    metrics.update(y_pred, y_true, y_prob)
    results = metrics.compute_classification()

    print(f"  الدقة (Accuracy):        {results['accuracy']:.2%}")
    print(f"  Precision (Macro):       {results['precision_macro']:.2%}")
    print(f"  Recall (Macro):          {results['recall_macro']:.2%}")
    print(f"  F1 Score (Macro):        {results['f1_macro']:.2%}")
    print(f"  F1 Score (Weighted):     {results['f1_weighted']:.2%}")

    # Dice و IoU
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask1[20:80, 20:80] = 1
    mask2 = mask1.copy()
    mask2[25:75, 25:75] = 1  # أصغر قليلاً

    dice = MedicalMetrics.dice_coefficient(mask1, mask2)
    iou = MedicalMetrics.iou_score(mask1, mask2)
    hd = MedicalMetrics.hausdorff_distance(mask1, mask2)

    print(f"\n  مقاييس التقسيم:")
    print(f"    Dice Coefficient:      {dice:.4f}")
    print(f"    IoU (Jaccard):         {iou:.4f}")
    print(f"    Hausdorff Distance:    {hd:.2f} px")

    # PSNR
    img1 = np.random.rand(100, 100).astype(np.float32) * 255
    img2 = img1 + np.random.normal(0, 5, (100, 100)).astype(np.float32)
    psnr = MedicalMetrics.psnr(img1, img2)

    print(f"\n  مقاييس جودة الصور:")
    print(f"    PSNR:                  {psnr:.2f} dB")


def main():
    """تشغيل العرض التجريبي الكامل"""
    total_start = time.time()

    print("╔══════════════════════════════════════════════════════╗")
    print("║   Medical Image AI Suite - تشغيل تجريبي شامل       ║")
    print("╚══════════════════════════════════════════════════════╝")

    # التحقق من التبعيات
    try:
        import pydicom, cv2, torch, sklearn
        print(f"\n✓ pydicom: {pydicom.__version__}")
        print(f"✓ opencv:  {cv2.__version__}")
        print(f"✓ torch:   {torch.__version__}")
        print(f"✓ sklearn: {sklearn.__version__}")
    except ImportError as e:
        print(f"\n⚠ تبعية مفقودة: {e}")
        print("  شغّل: pip install -r requirements.txt")

    # تشغيل العروض
    cleaned, sections = demo_text_processing()
    ner_results = demo_ner(cleaned)
    demo_weak_labels()
    demo_image_augmentation()
    demo_report_generation()
    demo_metrics()

    # الملخص
    elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"  ✓ العرض التجريبي اكتمل بنجاح! ({elapsed:.2f} ثانية)")
    print(f"{'=' * 60}")
    print(f"\n📌 الخطوات التالية:")
    print(f"   1. ضع صورك DICOM/JPG في مجلد data/raw/")
    print(f"   2. ضع تقاريرك في مجلد data/reports/")
    print(f"   3. شغّل: python main_pipeline.py --phase 1")
    print(f"   4. شغّل: python main_pipeline.py --phase 2 --mode ner")
    print(f"   5. افتح دفتر Colab: notebooks/01_medical_pipeline.ipynb")


if __name__ == "__main__":
    main()
