"""تجزئة صفحة خط اليد العربي — مستوى سطر + كلمة (reconstructed).

RECONSTRUCTION NOTE (no-silent-fallback):
    الملف الأصلي ``segment.py`` المشار إليه في الماستر برومبت (ATR-F4) غير موجود
    في المستودع — فُقد مع env reset سابق (سابقة M001 الموثقة). هذه إعادة بناء
    استنادًا إلى مرجعين أحياء:
      1. أداة S001 v7 الباقية محليًا خارج المستودع:
         data/handwriting-ar/tools/segment_words_s001.py
         (binarization + paper crop + إزالة خطوط التسطير + كشف أسطر بـ dilation
          أفقي عريض + دمج النقاط العائمة + فصل الرسوم) — مجرَّبة على S001 كاملًا.
      2. مفاهيم ArabicWordSegmenter الموجودة فعلًا في المستودع:
         hf-space/packages/vision/htr/word_segmenter.py
         (المسقط الرأسي لتقسيم السطر إلى كلمات).

الواجهة المطلوبة من ATR-F4:
    preprocess(gray)               -> ink (ثنائية: الحبر=255، خارج الورقة=0)
    detect_layout(ink)             -> (line_boxes, graphic_boxes) ترتيب أعلى→أسفل
    extract_words(gray, line_box)  -> word_boxes بترتيب RTL (الأولى أقصى اليمين)

ملاحظة صدق (موثقة من قياس S001 2026-09-23): الفجوات بين كلمات الخط العربي
المتدفق ذات توزيع أحادي القمة — التجزئة بالفجوات الهندسية على خط اليد الحر
best-effort (DRAFT للمراجعة)، بينما على النص المطبوع/المتباعد تعمل بثبات.
مستوى السطر يبقى المعيار الموثوق (IAM-HTR convention).

بلا شبكة — معالجة صور كلاسيكية فقط (cv2/numpy).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

Box = Tuple[int, int, int, int]  # (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Preprocessing primitives (من مرجع S001 v7 — مجربة)
# ---------------------------------------------------------------------------
def binarize_ink(gray: np.ndarray, block: int = 35, c: int = 12,
                 min_area: int = 6) -> np.ndarray:
    """صورة ثنائية: الحبر=255، الخلفية=0 (adaptive Gaussian + تنظيف شظايا)."""
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, c
    )
    n, lab, stats, _ = cv2.connectedComponentsWithStats(th, connectivity=8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            th[lab == i] = 0
    return th


def paper_bbox(gray: np.ndarray, thresh: int = 170, margin: int = 35) -> Box:
    """bbox الورقة البيضاء + هامش داخلي — يزيل حواف المسح الداكنة."""
    bright = (gray > thresh).astype(np.uint8) * 255
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    if n <= 1:
        H, W = gray.shape
        return 0, 0, W, H
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(stats[best, cv2.CC_STAT_LEFT]), int(stats[best, cv2.CC_STAT_TOP]),
                  int(stats[best, cv2.CC_STAT_WIDTH]), int(stats[best, cv2.CC_STAT_HEIGHT]))
    H, W = gray.shape
    return (max(0, x + margin), max(0, y + margin),
            min(W, x + w - margin), min(H, y + h - margin))


def remove_hlines(ink: np.ndarray, min_len: int = 200) -> np.ndarray:
    """إزالة خطوط التسطير/المسطرات من صورة الكشف فقط (القصاصات من الأصلي)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1))
    mask = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)))
    return cv2.bitwise_and(ink, cv2.bitwise_not(mask))


def preprocess(gray: np.ndarray) -> np.ndarray:
    """ATR-F4 entry: binarize + قص الورقة + إزالة التسطير -> ink داخل حدود الورقة."""
    ink = binarize_ink(gray)
    px0, py0, px1, py1 = paper_bbox(gray)
    ink[:py0, :] = 0
    ink[py1:, :] = 0
    ink[:, :px0] = 0
    ink[:, px1:] = 0
    return remove_hlines(ink)


# ---------------------------------------------------------------------------
# Line detection (من مرجع S001 v7 — مجربة)
# ---------------------------------------------------------------------------
def _merge_small_into_lines(boxes: List[Box], v_gap: int = 18,
                            size_ratio: float = 0.55) -> List[Box]:
    """دمج الكتل الصغيرة (نقاط) مع أقرب سطر: فجوة رأسية صغيرة + تداخل أفقي
    + إحدى الكتلتين أصغر بوضوح (حتى لا يُدمج سطران متتاليان)."""
    if not boxes:
        return []
    bxs = sorted([list(b) for b in boxes], key=lambda b: (b[1], -b[0]))
    out = [bxs[0]]
    for b in bxs[1:]:
        last = out[-1]
        gap = b[1] - last[3]
        ox = min(last[2], b[2]) - max(last[0], b[0])
        h1 = last[3] - last[1]
        h2 = b[3] - b[1]
        min_h, max_h = min(h1, h2), max(h1, h2)
        if 0 <= gap < v_gap and ox > 0.2 * min(last[2] - last[0], b[2] - b[0]) \
                and min_h < size_ratio * max_h:
            last[0] = min(last[0], b[0])
            last[1] = min(last[1], b[1])
            last[2] = max(last[2], b[2])
            last[3] = max(last[3], b[3])
        else:
            out.append(list(b))
    return [tuple(b) for b in out]


def detect_lines(ink: np.ndarray) -> Tuple[List[Box], List[Box]]:
    """أسطر عبر ربط أفقي عريض. يُرجع (lines, graphics)."""
    H, W = ink.shape
    k = max(25, int(W * 0.018))
    dil = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    dil = cv2.dilate(dil, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dil, connectivity=8)
    lines, graphics = [], []
    for i in range(1, n):
        x, y, w, h = (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                      stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT])
        if w < 6 and h < 6:
            continue
        box = (int(x), int(y), int(x + w), int(y + h))
        # رسوم/تظليل: ضخم (السطر النصي ارتفاعه ~4-6% من H كحد أقصى)
        if (w * h) > 0.05 * W * H or (w > 0.55 * W and h > 0.09 * H):
            graphics.append(box)
        else:
            lines.append(box)
    lines = _merge_small_into_lines(lines)
    lines.sort(key=lambda b: ((b[1] + b[3]) / 2.0, -b[0]))
    return lines, graphics


def detect_layout(ink: np.ndarray) -> Tuple[List[Box], List[Box]]:
    """ATR-F4 entry: (line_boxes, graphic_boxes) مرتبة أعلى→أسفل."""
    return detect_lines(ink)


# ---------------------------------------------------------------------------
# Word extraction (المسقط الرأسي — مفاهيم ArabicWordSegmenter)
# ---------------------------------------------------------------------------
def extract_words(gray: np.ndarray, line_box: Box, ink: Optional[np.ndarray] = None,
                  gap_factor: float = 0.4, min_gap_px: int = 6,
                  min_word_w: int = 8) -> List[Box]:
    """قصاصات كلمات داخل سطر عبر المسقط الرأسي (vertical projection).

    Args:
        gray: الصورة الرمادية الكاملة (للسقوط الرجعي إلى binarization المحلي
              إذا لم تُمرر ink).
        line_box: صندوق السطر (x0, y0, x1, y1) من detect_layout.
        ink: صورة الكشف الثنائية الكاملة من preprocess() — تُفضَّل (تجنب
             adaptiveThreshold على شريط ضيق).
        gap_factor: عتبة الفجوة = max(min_gap_px, gap_factor * وسيط عروض
                    التشكيلات المتصلة داخل السطر).
        min_word_w: أقل عرض كلمة — الشظايا الأصغر تُلحق بالكلمة المجاورة.

    Returns:
        قائمة صناديق كلمات بترتيب RTL (الكلمة الأولى أقصى اليمين — ترتيب
        القراءة العربية).
    """
    x0, y0, x1, y1 = [int(v) for v in line_box]
    if ink is not None:
        strip = ink[y0:y1, x0:x1]
    else:
        strip_src = gray[y0:y1, x0:x1]
        if strip_src.size == 0:
            return []
        _, strip = cv2.threshold(strip_src, 0, 255,
                                 cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if strip.size == 0 or strip.sum() == 0:
        return []

    col = (strip > 0).sum(axis=0)
    runs: List[List[int]] = []
    in_run, s = False, 0
    for i, v in enumerate(col):
        if v > 0 and not in_run:
            in_run, s = True, i
        elif v == 0 and in_run:
            in_run = False
            runs.append([s, i])
    if in_run:
        runs.append([s, len(col)])
    runs = [r for r in runs if r[1] > r[0]]
    if not runs:
        return []

    widths = [b - a for a, b in runs]
    med_w = float(np.median(widths))
    thr = max(int(min_gap_px), int(gap_factor * med_w))

    # دمج التشكيلات المتقاربة (فجوة < العتبة) -> كلمات
    merged: List[List[int]] = [list(runs[0])]
    for a, b in runs[1:]:
        if a - merged[-1][1] < thr:
            merged[-1][1] = b
        else:
            merged.append([a, b])

    # الشظايا الصغيرة (نقاط معزولة) تُلحق بالكلمة السابقة إن وُجدت
    words: List[List[int]] = []
    for a, b in merged:
        if words and (b - a) < min_word_w:
            words[-1][1] = b
        else:
            words.append([a, b])

    boxes: List[Box] = []
    for a, b in words:
        sub = strip[:, a:b]
        rows = np.where(sub.any(axis=1))[0]
        if len(rows) == 0:
            continue
        wy0, wy1 = int(rows[0]), int(rows[-1]) + 1
        boxes.append((x0 + a, y0 + wy0, x0 + b, y0 + wy1))

    # ترتيب RTL: تنازلي حسب x0 (الأولى أقصى اليمين)
    boxes.sort(key=lambda b: -b[0])
    return boxes


# ---------------------------------------------------------------------------
# Crop / preview helpers
# ---------------------------------------------------------------------------
def crop_save(gray: np.ndarray, box: Box, path: str, pad: int = 6):
    """قص من الرمادي الأصلي مع padding — يُرجع (w, h) أو None إذا قُصّ فارغ."""
    H, W = gray.shape
    x0, y0, x1, y1 = box
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(W, x1 + pad)
    y1 = min(H, y1 + pad)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    cv2.imwrite(path, gray[y0:y1, x0:x1])
    return (x1 - x0, y1 - y0)


def preview_with_boxes(gray: np.ndarray, word_boxes: List[Box],
                       graphic_boxes: Optional[List[Box]] = None) -> np.ndarray:
    """معاينة BGR: صناديق الكلمات خضراء بترتيب RTL + الرسوم حمراء."""
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for b in word_boxes:
        cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), (0, 160, 0), 2)
    for b in (graphic_boxes or []):
        cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), (0, 0, 220), 3)
    return vis
