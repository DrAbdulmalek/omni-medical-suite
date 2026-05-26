#!/usr/bin/env python3
"""
test_core.py — اختبارات الوحدة لـ medical_doc_gui_v10
تشغيل: pytest test_core.py -v
"""
import numpy as np
import cv2
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# استيراد الدوال من الملف الرئيسي
import importlib.util
spec = importlib.util.spec_from_file_location(
    "app", os.path.join(os.path.dirname(__file__), "medical_doc_gui.py"))
mod = importlib.util.module_from_spec(spec)
# تشغيل جزئي (بدون PyQt5)
import unittest.mock as mock
with mock.patch.dict('sys.modules', {
    'PyQt5': mock.MagicMock(), 'PyQt5.QtWidgets': mock.MagicMock(),
    'PyQt5.QtCore': mock.MagicMock(), 'PyQt5.QtGui': mock.MagicMock(),
}):
    spec.loader.exec_module(mod)

apply_processing   = mod.apply_processing
calc_blur          = mod.calc_blur
quality_label      = mod.quality_label
smart_auto_crop    = mod.smart_auto_crop
find_page_bounds   = mod.find_page_bounds
auto_detect_skew   = mod.auto_detect_skew
AdaptiveLearner    = mod.AdaptiveLearner
LazyImage          = mod.LazyImage


# ══════════════════════════════════════════════
#  helpers
# ══════════════════════════════════════════════
def white_img(h=400, w=300):
    return np.full((h, w, 3), 255, dtype=np.uint8)

def text_img():
    img = white_img()
    cv2.rectangle(img, (30, 50), (270, 350), (0, 0, 0), -1)
    return img

def gray_border_img(h=2800, w=2550, gray_val=155, border=300):
    """صورة بيضاء بحواف رمادية مثل الماسح الضوئي."""
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    img[:, :border]      = gray_val   # يسار
    img[:, w-border:]    = gray_val   # يمين
    # محتوى نصي في المنتصف
    cv2.rectangle(img, (border+50, 100), (w-border-50, h-100), (0, 0, 0), 2)
    return img

def default_params(**kw):
    p = {"crop":(0,0,0,0),"deskew_angle":0.0,"flip_h":False,"sharpen":False,"rotation":0}
    p.update(kw)
    return p

import pytest

# ══════════════════════════════════════════════
#  apply_processing
# ══════════════════════════════════════════════
class TestApplyProcessing:
    def test_noop(self):
        img = white_img(400, 300)
        assert apply_processing(img, default_params()).shape == img.shape

    def test_crop_reduces_size(self):
        img = white_img(400, 300)
        out = apply_processing(img, default_params(crop=(10,20,10,20)))
        assert out.shape[0] == 360 and out.shape[1] == 280

    def test_flip_mirrors(self):
        img = white_img(100,100); img[:,:10] = 0
        out = apply_processing(img, default_params(flip_h=True))
        assert out[0,-1,0] == 0

    def test_rotation_90(self):
        img = white_img(400, 300)
        out = apply_processing(img, default_params(rotation=90))
        assert out.shape == (300, 400, 3)

    def test_rotation_180(self):
        img = white_img(400, 300)
        out = apply_processing(img, default_params(rotation=180))
        assert out.shape == img.shape

    def test_sharpen_usm_changes_edges(self):
        """USM يُغيّر الحواف — نستخدم صورة بخط رمادي بين أبيض وأسود."""
        img = white_img(100, 100)
        img[:, 48:52] = 128   # خط رمادي في المنتصف → حافة يؤثر عليها USM
        out = apply_processing(img, default_params(sharpen=True))
        assert not np.array_equal(img[:, 45:55], out[:, 45:55])

    def test_safe_overcrop(self):
        img = white_img(100, 100)
        out = apply_processing(img, default_params(crop=(60,60,60,60)))
        assert out.shape[0] > 0 and out.shape[1] > 0


# ══════════════════════════════════════════════
#  calc_blur & quality_label
# ══════════════════════════════════════════════
class TestBlurAndQuality:
    def test_white_is_zero(self):
        assert calc_blur(white_img()) == pytest.approx(0.0, abs=1e-6)

    def test_text_higher_than_white(self):
        assert calc_blur(text_img()) > calc_blur(white_img())

    def test_quality_excellent(self):
        assert quality_label(300, 100) == ("ممتازة", "#16a34a", "✅")

    def test_quality_acceptable(self):
        assert quality_label(120, 100) == ("مقبولة", "#d97706", "⚠️")

    def test_quality_blurry(self):
        assert quality_label(50, 100) == ("ضبابية", "#dc2626", "❌")


# ══════════════════════════════════════════════
#  find_page_bounds
# ══════════════════════════════════════════════
class TestFindPageBounds:
    def test_no_gray_returns_zero(self):
        img = white_img()
        l,t,r,b = find_page_bounds(img)
        assert l == 0 and r == 0   # لا رمادي

    def test_detects_gray_borders(self):
        img = gray_border_img(w=2550, border=300)
        l,t,r,b = find_page_bounds(img)
        assert l >= 250 and r >= 250   # يكتشف ~300px من كل جانب

    def test_returns_four_values(self):
        assert len(find_page_bounds(white_img())) == 4

    def test_top_bottom_zero(self):
        img = gray_border_img()
        l,t,r,b = find_page_bounds(img)
        assert t == 0 and b == 0   # الخوارزمية لا تعالج الصفوف


# ══════════════════════════════════════════════
#  smart_auto_crop
# ══════════════════════════════════════════════
class TestSmartAutoCrop:
    def test_white_no_content_returns_zeros(self):
        assert smart_auto_crop(white_img()) == (0,0,0,0)

    def test_gray_border_removed(self):
        img = gray_border_img(h=1000, w=2550, border=300)
        l,t,r,b = smart_auto_crop(img)
        assert l >= 200   # الرمادي يُزال

    def test_margins_within_image(self):
        img = text_img()
        h, w = img.shape[:2]
        l,t,r,b = smart_auto_crop(img)
        assert l+r < w and t+b < h


# ══════════════════════════════════════════════
#  AdaptiveLearner
# ══════════════════════════════════════════════
class TestAdaptiveLearner:
    def test_empty_returns_none(self):
        l = AdaptiveLearner()
        p, sim = l.suggest(text_img())
        assert p is None and sim == pytest.approx(0.0)

    def test_add_increases_history(self):
        l = AdaptiveLearner()
        l.add(text_img(), default_params(crop=(10,10,10,10)))
        assert len(l.history) == 1

    def test_max_history_30(self):
        l = AdaptiveLearner()
        for _ in range(40):
            l.add(white_img(), default_params())
        assert len(l.history) == AdaptiveLearner.MAX

    def test_suggest_identical(self):
        l = AdaptiveLearner()
        img = text_img()
        for _ in range(3):
            l.add(img, default_params(crop=(15,15,15,15)))
        p, sim = l.suggest(img)
        assert p is not None and sim > 0.9

    def test_export_load(self, tmp_path):
        l = AdaptiveLearner()
        l.add(text_img(), default_params(crop=(5,5,5,5)))
        path = str(tmp_path / "test.json")
        l.export(path)
        l2 = AdaptiveLearner()
        l2.load(path)
        assert len(l2.history) == 1


# ══════════════════════════════════════════════
#  LazyImage
# ══════════════════════════════════════════════
class TestLazyImage:
    def test_array_source(self):
        img = white_img()
        li = LazyImage(img, "test.png")
        assert np.array_equal(li.get(), img)

    def test_nonexistent_path_returns_none(self):
        from pathlib import Path
        li = LazyImage(Path("/nonexistent/path.png"), "missing.png")
        assert li.get() is None

    def test_clear_cache(self):
        img = white_img()
        li = LazyImage(img, "test.png")
        li._cache = img
        li.clear_cache()
        assert li._cache is None

    def test_exists_array(self):
        li = LazyImage(white_img(), "test.png")
        assert li.exists()

    def test_is_path_false_for_array(self):
        li = LazyImage(white_img(), "test.png")
        assert not li.is_path


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
