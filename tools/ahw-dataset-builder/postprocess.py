#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post-processing للقصاصات العربية:
- دمج المكونات المتكسرة (connected script)
- إزالة الضوضاء المعزولة
- تنعيم الحدود
"""

import numpy as np
import cv2

def merge_broken_components(crop, kernel_size=(3, 15)):
    """
    يدمج المكونات الأفقية المتقاربة جداً (سطور عربية مكسورة).
    يُستخدم kernel أوسع أفقياً لأن الاتجاه عربي.
    """
    if crop.size == 0:
        return crop
    # binary: نص=255
    binary = (crop > 127).astype(np.uint8) * 255

    # morphological close أفقي لربط الحروف المكسورة
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_h)

    # نمسح الضوضاء الصغيرة
    n, labels, stats, _ = cv2.connectedComponentsWithStats(closed)
    if n <= 1:
        return crop
    out = np.zeros_like(closed)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 8:
            out[labels == i] = 255

    return out

def enhance_crop(crop, target_height=None):
    """
    يحسّن جودة قصاصة واحدة:
    - يوسّط النص عمودياً
    - يوحّد المقاس (اختياري)
    - يزيل الحدود البيضاء الزائدة
    """
    if crop.size == 0:
        return crop
    inv = 255 - crop

    # trim whitespace
    ys, xs = np.where(inv > 50)
    if len(ys) == 0:
        return crop
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    trimmed = inv[y0:y1+1, x0:x1+1]

    if target_height and trimmed.shape[0] != target_height:
        scale = target_height / trimmed.shape[0]
        new_w = int(trimmed.shape[1] * scale)
        trimmed = cv2.resize(trimmed, (new_w, target_height),
                             interpolation=cv2.INTER_AREA)

    return 255 - trimmed
