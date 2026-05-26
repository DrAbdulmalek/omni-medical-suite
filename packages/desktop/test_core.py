"""
test_core.py — اختبارات الوحدة لمعالج الوثائق الطبية
تشغيل: pytest test_core.py -v
"""

import numpy as np
import pytest
import sys
import os

# ── إضافة المجلد الجذر للمسار ─────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from medical_doc_gui import (
    apply_processing,
    calc_blur,
    quality_label,
    smart_auto_crop,
    cv2_to_pixmap,
    AdaptiveLearner,
    ImageFeatureExtractor,
    TrainingDataCollector,
    _remove_shadow,
    auto_detect_skew,
)

# ══════════════════════════════════════════════
#  بيانات مساعدة
# ══════════════════════════════════════════════

def make_white_img(h: int = 400, w: int = 300) -> np.ndarray:
    """صورة بيضاء نظيفة."""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def make_text_img() -> np.ndarray:
    """صورة بيضاء تحتوي مستطيلاً داكناً يمثل نصاً."""
    import cv2
    img = make_white_img()
    cv2.rectangle(img, (30, 50), (270, 350), (0, 0, 0), -1)
    return img


def make_gradient_img() -> np.ndarray:
    """صورة بتدرج رمادي لمحاكاة ظل خفيف."""
    img = np.zeros((400, 300, 3), dtype=np.uint8)
    for y in range(400):
        val = int(80 + (y / 400) * 120)
        img[y, :] = [val, val, val]
    # نص وهمي
    img[100:300, 50:250] = [10, 10, 10]
    return img


def default_params(**overrides) -> dict:
    base = {
        "crop": (0, 0, 0, 0),
        "deskew_angle": 0.0,
        "flip_h": False,
        "sharpen": False,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════
#  apply_processing
# ══════════════════════════════════════════════

class TestApplyProcessing:

    def test_no_op_preserves_shape(self):
        """بدون أي عملية — الشكل لا يتغير."""
        img = make_white_img(400, 300)
        out = apply_processing(img, default_params())
        assert out.shape == img.shape

    def test_crop_reduces_size(self):
        """القص يُصغّر الصورة."""
        img = make_white_img(400, 300)
        out = apply_processing(img, default_params(crop=(10, 20, 10, 20)))
        assert out.shape[0] == 400 - 20 - 20   # ارتفاع
        assert out.shape[1] == 300 - 10 - 10   # عرض

    def test_crop_zero_stays_same(self):
        """قص بصفر لا يغير شيئاً."""
        img = make_white_img(400, 300)
        out = apply_processing(img, default_params(crop=(0, 0, 0, 0)))
        assert out.shape == img.shape

    def test_flip_h_changes_pixels(self):
        """القلب الأفقي يغير مواضع البكسل."""
        img = make_white_img(100, 100)
        img[:, :10] = 0   # عمود أسود على اليسار
        out = apply_processing(img, default_params(flip_h=True))
        assert out[0, -1, 0] == 0   # يجب أن يكون على اليمين الآن

    def test_flip_twice_is_identity(self):
        """قلبان متتاليان يُعيدان الصورة الأصلية."""
        img = make_text_img()
        once  = apply_processing(img, default_params(flip_h=True))
        twice = apply_processing(once, default_params(flip_h=True))
        np.testing.assert_array_equal(img, twice)

    def test_deskew_preserves_shape(self):
        """تصحيح الميلان لا يغير أبعاد الصورة."""
        img = make_white_img(400, 300)
        out = apply_processing(img, default_params(deskew_angle=5.0))
        assert out.shape == img.shape

    def test_deskew_zero_no_change(self):
        """ميلان صفر = لا تغيير."""
        img = make_white_img(400, 300)
        out = apply_processing(img, default_params(deskew_angle=0.0))
        np.testing.assert_array_equal(img, out)

    def test_sharpen_changes_pixels(self):
        """التحسين يغير قيم البكسل على الحواف فعلاً.
        نستخدم صورة رمادية بخط نصف اللون (128) بجانب أبيض
        حتى يظهر أثر kernel التحسين بوضوح.
        """
        import cv2
        img = make_white_img(100, 100)
        # خط رمادي عمودي في المنتصف — حافة واضحة
        img[:, 48:52] = 128
        out = apply_processing(img, default_params(sharpen=True))
        # البكسل على حافة الخط (col 47 أو 52) يجب أن يتغير
        assert not np.array_equal(img[:, 45:55], out[:, 45:55])

    def test_sharpen_preserves_shape(self):
        """التحسين لا يغير الأبعاد."""
        img = make_white_img()
        out = apply_processing(img, default_params(sharpen=True))
        assert out.shape == img.shape

    def test_invalid_crop_is_safe(self):
        """قص أكبر من الصورة لا يُعطل البرنامج."""
        img = make_white_img(100, 100)
        out = apply_processing(img, default_params(crop=(60, 60, 60, 60)))
        # l=60 > r2=100-60=40 → لا قص → يُرجع الصورة الأصلية
        assert out.shape[0] > 0 and out.shape[1] > 0

    def test_rotation_90(self):
        """تدوير 90 درجة يبدّل الأبعاد."""
        img = make_white_img(100, 200)
        out = apply_processing(img, default_params(rotation=90))
        assert out.shape[0] == 200
        assert out.shape[1] == 100

    def test_rotation_180(self):
        """تدوير 180 درجة يحافظ على الأبعاد."""
        img = make_white_img(100, 200)
        out = apply_processing(img, default_params(rotation=180))
        assert out.shape == (100, 200, 3)

    def test_rotation_270(self):
        """تدوير 270 درجة يبدّل الأبعاد مثل 90 لكن عكسه."""
        img = make_white_img(100, 200)
        out = apply_processing(img, default_params(rotation=270))
        assert out.shape[0] == 200
        assert out.shape[1] == 100

    def test_rotation_360_is_identity(self):
        """تدوير 360 = لا تغيير."""
        img = make_text_img()
        out = apply_processing(img, default_params(rotation=360))
        np.testing.assert_array_equal(img, out)

    def test_rotation_preserves_pixel_count(self):
        """العدد الإجمالي للبكسل ثابت بعد التدوير."""
        img = make_white_img(100, 200)
        out = apply_processing(img, default_params(rotation=90))
        assert img.size == out.size

    def test_remove_shadow_changes_pixels(self):
        """إزالة الظل تغيّر الصورة."""
        img = make_gradient_img()
        out = apply_processing(img, default_params(remove_shadow=True))
        assert not np.array_equal(img, out)

    def test_remove_shadow_preserves_shape(self):
        """إزالة الظل تحافظ على الأبعاد."""
        img = make_gradient_img()
        out = apply_processing(img, default_params(remove_shadow=True))
        assert out.shape == img.shape

    def test_combined_operations(self):
        """تطبيق عدة عمليات معاً لا يُعطل البرنامج."""
        img = make_text_img()
        params = default_params(
            crop=(5, 5, 5, 5),
            deskew_angle=2.0,
            flip_h=True,
            sharpen=True,
            remove_shadow=True,
            rotation=90,
        )
        out = apply_processing(img, params)
        assert out.ndim == 3
        assert out.shape[2] == 3  # BGR


# ══════════════════════════════════════════════
#  _remove_shadow
# ══════════════════════════════════════════════

class TestRemoveShadow:

    def test_returns_same_shape(self):
        """إزالة الظل تحافظ على أبعاد الصورة."""
        img = make_gradient_img()
        out = _remove_shadow(img)
        assert out.shape == img.shape

    def test_white_image_stays_valid(self):
        """صورة بيضاء كاملة تبقى بصيغة صالحة.
        normalize قد تُنتج نتائج مختلفة عندما min==max (كل القيم متساوية)."""
        img = make_white_img()
        out = _remove_shadow(img)
        assert out.shape == img.shape
        assert out.dtype == img.dtype
        assert out.min() >= 0
        assert out.max() <= 255

    def test_gradient_image_changed(self):
        """صورة بتدرج تتغير بعد إزالة الظل."""
        img = make_gradient_img()
        out = _remove_shadow(img)
        assert not np.array_equal(img, out)

    def test_output_in_valid_range(self):
        """قيم البكسل بعد إزالة الظل تبقى 0-255."""
        img = make_gradient_img()
        out = _remove_shadow(img)
        assert out.min() >= 0
        assert out.max() <= 255


# ══════════════════════════════════════════════
#  calc_blur
# ══════════════════════════════════════════════

class TestCalcBlur:

    def test_white_image_is_zero_blur(self):
        """صورة بيضاء موحدة = لا حدود = وضوح صفر."""
        img = make_white_img()
        assert calc_blur(img) == pytest.approx(0.0, abs=1e-6)

    def test_text_image_has_higher_blur(self):
        """صورة بها حواف نص > صورة بيضاء."""
        white = make_white_img()
        text  = make_text_img()
        assert calc_blur(text) > calc_blur(white)

    def test_grayscale_input(self):
        """يقبل صور رمادية (2D) بدون خطأ."""
        import cv2
        img  = make_text_img()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        score = calc_blur(gray)
        assert score >= 0.0

    def test_returns_float(self):
        assert isinstance(calc_blur(make_white_img()), float)


# ══════════════════════════════════════════════
#  quality_label
# ══════════════════════════════════════════════

class TestQualityLabel:

    def test_excellent(self):
        label, color, icon = quality_label(300.0, 100.0)
        assert label == "ممتازة"
        assert icon  == "✅"

    def test_acceptable(self):
        label, color, icon = quality_label(120.0, 100.0)
        assert label == "مقبولة"
        assert icon  == "⚠️"

    def test_blurry(self):
        label, color, icon = quality_label(50.0, 100.0)
        assert label == "ضبابية"
        assert icon  == "❌"

    def test_boundary_exactly_threshold(self):
        """عند العتبة بالضبط → مقبولة."""
        label, _, _ = quality_label(100.0, 100.0)
        assert label == "مقبولة"

    def test_boundary_exactly_double(self):
        """عند ضعف العتبة بالضبط → ممتازة."""
        label, _, _ = quality_label(200.0, 100.0)
        assert label == "ممتازة"


# ══════════════════════════════════════════════
#  smart_auto_crop
# ══════════════════════════════════════════════

class TestSmartAutoCrop:

    def test_returns_four_values(self):
        """يجب أن يُرجع tuple من 4 قيم."""
        img = make_text_img()
        result = smart_auto_crop(img)
        assert len(result) == 4

    def test_all_margins_non_negative(self):
        """جميع الهوامش يجب أن تكون >= 0."""
        img = make_text_img()
        l, t, r, b = smart_auto_crop(img)
        assert l >= 0 and t >= 0 and r >= 0 and b >= 0

    def test_white_image_returns_zeros(self):
        """صورة بيضاء فارغة → لا محتوى → (0,0,0,0)."""
        img = make_white_img()
        result = smart_auto_crop(img)
        assert result == (0, 0, 0, 0)

    def test_content_centered(self):
        """محتوى في المنتصف → هوامش متقاربة من الجانبين."""
        img = make_white_img(400, 400)
        import cv2
        # مستطيل في المنتصف تقريباً
        cv2.rectangle(img, (150, 150), (250, 250), (0, 0, 0), -1)
        l, t, r, b = smart_auto_crop(img, padding=0)
        # المحتوى في الوسط → هوامش يمين ويسار متقاربة
        assert abs(l - r) < 30

    def test_margins_do_not_exceed_image(self):
        """الهوامش لا تتجاوز أبعاد الصورة."""
        img = make_text_img()
        h, w = img.shape[:2]
        l, t, r, b = smart_auto_crop(img)
        assert l + r < w
        assert t + b < h


# ══════════════════════════════════════════════
#  auto_detect_skew
# ══════════════════════════════════════════════

class TestAutoDetectSkew:

    def test_straight_image_small_angle(self):
        """صورة أفقية بلا ميلان → زاوية صغيرة تقريباً."""
        img = make_text_img()
        angle = auto_detect_skew(img)
        assert -2.0 < angle < 2.0

    def test_returns_float(self):
        """النتيجة يجب أن تكون float."""
        img = make_text_img()
        angle = auto_detect_skew(img)
        assert isinstance(angle, float)

    def test_custom_step(self):
        """يمكن تغيير خطوة البحث."""
        img = make_text_img()
        angle = auto_detect_skew(img, step=1.0)
        assert isinstance(angle, float)


# ══════════════════════════════════════════════
#  AdaptiveLearner
# ══════════════════════════════════════════════

class TestAdaptiveLearner:

    def test_suggest_returns_none_when_empty(self):
        learner = AdaptiveLearner()
        img = make_text_img()
        result, sim = learner.suggest(img)
        assert result is None
        assert sim == pytest.approx(0.0)

    def test_add_increases_history(self):
        learner = AdaptiveLearner()
        img     = make_text_img()
        params  = default_params(crop=(10, 10, 10, 10))
        learner.add(img, params)
        assert len(learner.history) == 1

    def test_suggest_identical_image(self):
        """صورة مطابقة → اقتراح بتشابه عالٍ جداً."""
        learner = AdaptiveLearner()
        img     = make_text_img()
        params  = default_params(crop=(15, 15, 15, 15))
        # نضيف نفس الصورة مرتين (الحد الأدنى للاقتراح)
        for _ in range(2):
            learner.add(img, params)
        suggested, sim = learner.suggest(img)
        assert suggested is not None
        assert sim > 0.9

    def test_max_history_limit(self):
        """لا يتجاوز الحد الأقصى MAX=30."""
        learner = AdaptiveLearner()
        img     = make_white_img()
        params  = default_params()
        for _ in range(40):
            learner.add(img, params)
        assert len(learner.history) == AdaptiveLearner.MAX

    def test_export_and_load(self, tmp_path):
        """التصدير والاستيراد يحافظان على البيانات."""
        learner = AdaptiveLearner()
        img     = make_text_img()
        params  = default_params(crop=(5, 5, 5, 5), deskew_angle=1.5)
        learner.add(img, params)
        learner.add(img, default_params(flip_h=True))

        path = str(tmp_path / "learner_test.json")
        learner.export(path)

        learner2 = AdaptiveLearner()
        learner2.load(path)
        assert len(learner2.history) == 2
        assert learner2.history[0]["params"]["crop"] == [5, 5, 5, 5]


# ══════════════════════════════════════════════
#  ImageFeatureExtractor
# ══════════════════════════════════════════════

class TestImageFeatureExtractor:

    def test_extract_returns_dict(self):
        """يُرجع قاموس."""
        feats = ImageFeatureExtractor.extract(make_text_img())
        assert isinstance(feats, dict)

    def test_extract_has_required_keys(self):
        """يحتوي المفاتيح الأساسية."""
        feats = ImageFeatureExtractor.extract(make_text_img())
        required = ["w", "h", "aspect_ratio", "brightness_mean",
                     "blur_score", "edge_density", "dark_ratio", "grad_mean"]
        for key in required:
            assert key in feats, f"Missing key: {key}"

    def test_extract_has_histogram_bins(self):
        """يحتوي 16 حاوية هيستوغرام (hist_00 إلى hist_15)."""
        feats = ImageFeatureExtractor.extract(make_text_img())
        for i in range(16):
            assert f"hist_{i:02d}" in feats

    def test_extract_dimensions_match(self):
        """قيم w و h تطابق أبعاد الصورة."""
        img = make_text_img()  # 400x300
        feats = ImageFeatureExtractor.extract(img)
        assert feats["w"] == 300
        assert feats["h"] == 400

    def test_similarity_identical_is_one(self):
        """تشابه صورتين متطابقتين = 1.0."""
        feats = ImageFeatureExtractor.extract(make_text_img())
        assert ImageFeatureExtractor.similarity(feats, feats) == pytest.approx(1.0, abs=1e-6)

    def test_similarity_different_images(self):
        """صورتان مختلفتان → تشابه < 1.0."""
        f1 = ImageFeatureExtractor.extract(make_white_img())
        f2 = ImageFeatureExtractor.extract(make_text_img())
        sim = ImageFeatureExtractor.similarity(f1, f2)
        assert sim < 1.0

    def test_similarity_range(self):
        """قيمة التشابه بين 0 و 1."""
        f1 = ImageFeatureExtractor.extract(make_white_img(200, 200))
        f2 = ImageFeatureExtractor.extract(make_gradient_img())
        sim = ImageFeatureExtractor.similarity(f1, f2)
        assert 0.0 <= sim <= 1.0


# ══════════════════════════════════════════════
#  TrainingDataCollector
# ══════════════════════════════════════════════

class TestTrainingDataCollector:

    def test_init_empty_stats(self):
        """إحصائيات فارغة عند الإنشاء بدون ملف."""
        tdc = TrainingDataCollector.__new__(TrainingDataCollector)
        tdc.records = []
        s = tdc.stats()
        assert s["count"] == 0

    def test_save_record_increases_count(self, tmp_path):
        """حفظ سجل يزيد العدد."""
        import json
        from pathlib import Path

        # نستخدم ملف مؤقت
        test_file = tmp_path / "test_training.jsonl"

        tdc = TrainingDataCollector.__new__(TrainingDataCollector)
        tdc.FILEPATH = test_file
        tdc.records = []

        img = make_text_img()
        tdc.save_record(
            img=img,
            initial_params=default_params(),
            final_params=default_params(crop=(10, 10, 10, 10)),
            operations=["crop"],
            blur_before=50.0,
            blur_after=120.0,
            image_name="test.png",
        )
        assert len(tdc.records) == 1
        # الملف يجب أن يُكتب
        assert test_file.exists()
        with open(test_file, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["image_name"] == "test.png"
        assert "features" in data
        assert "quality" in data

    def test_predict_returns_none_below_min(self, tmp_path):
        """أقل من MIN_INFER سجلات → لا تنبؤ."""
        test_file = tmp_path / "test_predict.jsonl"

        tdc = TrainingDataCollector.__new__(TrainingDataCollector)
        tdc.FILEPATH = test_file
        tdc.records = []

        img = make_text_img()
        result, sim = tdc.predict(img)
        assert result is None
        assert sim == 0.0

    def test_stats_returns_correct_values(self, tmp_path):
        """إحصائيات حسابية صحيحة."""
        test_file = tmp_path / "test_stats.jsonl"

        tdc = TrainingDataCollector.__new__(TrainingDataCollector)
        tdc.FILEPATH = test_file
        tdc.records = []

        img = make_text_img()
        tdc.save_record(
            img=img,
            initial_params=default_params(),
            final_params=default_params(crop=(5, 5, 5, 5)),
            operations=["crop"],
            blur_before=50.0,
            blur_after=150.0,
            image_name="test1.png",
        )
        tdc.save_record(
            img=img,
            initial_params=default_params(),
            final_params=default_params(crop=(10, 10, 10, 10)),
            operations=["crop", "sharpen"],
            blur_before=30.0,
            blur_after=180.0,
            image_name="test2.png",
        )

        s = tdc.stats()
        assert s["count"] == 2
        # avg_improvement = ((150-50) + (180-30)) / 2 = 125.0
        assert s["avg_improvement"] == pytest.approx(125.0, abs=0.1)
        # max_improvement = 150
        assert s["max_improvement"] == pytest.approx(150.0, abs=0.1)

    def test_quality_fields_in_record(self, tmp_path):
        """حقول الجودة موجودة في السجل المحفوظ."""
        import json

        test_file = tmp_path / "test_quality.jsonl"
        tdc = TrainingDataCollector.__new__(TrainingDataCollector)
        tdc.FILEPATH = test_file
        tdc.records = []

        img = make_text_img()
        tdc.save_record(
            img=img,
            initial_params=default_params(),
            final_params=default_params(sharpen=True),
            operations=["sharpen"],
            blur_before=40.0,
            blur_after=200.0,
            image_name="quality_test.png",
        )

        data = tdc.records[0]
        assert "blur_before" in data["quality"]
        assert "blur_after" in data["quality"]
        assert "improvement" in data["quality"]
        assert data["quality"]["improvement"] == pytest.approx(160.0, abs=0.1)


# ══════════════════════════════════════════════
#  cv2_to_pixmap  (بدون عرض)
# ══════════════════════════════════════════════

class TestCv2ToPixmap:

    def test_returns_pixmap(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        img = make_white_img(200, 150)
        pix = cv2_to_pixmap(img, max_w=100, max_h=100)
        assert not pix.isNull()

    def test_respects_max_dimensions(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        img = make_white_img(1000, 800)
        pix = cv2_to_pixmap(img, max_w=200, max_h=200)
        assert pix.width()  <= 200
        assert pix.height() <= 200

    def test_zoom_factor(self):
        """معامل التكبير يُكبّر الصورة."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        img = make_white_img(100, 100)
        pix = cv2_to_pixmap(img, zoom=2.0)
        assert pix.width() == 200
        assert pix.height() == 200

    def test_zoom_with_max_dims(self):
        """التكبير مع حد أقصى يطبّق الحد."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        img = make_white_img(100, 100)
        pix = cv2_to_pixmap(img, zoom=5.0, max_w=200, max_h=200)
        assert pix.width() <= 200
        assert pix.height() <= 200

    def test_no_zoom_no_max(self):
        """بدون تكبير أو حد → نفس الحجم (h=200, w=150)."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        # make_white_img(h=200, w=150) → الصورة بالشكل (200, 150, 3)
        img = make_white_img(200, 150)
        pix = cv2_to_pixmap(img)
        assert pix.width() == 150   # w
        assert pix.height() == 200  # h
