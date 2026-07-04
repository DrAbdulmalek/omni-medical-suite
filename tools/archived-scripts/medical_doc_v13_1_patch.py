#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PATCH v13.1 — إصلاح كشف الميلان وإزالة الرمادي
═══════════════════════════════════════════════════════════════
استبدل الدوال التالية في medical_doc_gui_v13.py
"""

# ═══════════════════════════════════════════════════════════════
#  1. FIXED: find_page_bounds — كشف الحدود من جميع الجهات
# ═══════════════════════════════════════════════════════════════

def find_page_bounds(img: np.ndarray,
                     page_threshold: int = 200,
                     min_page_fraction: float = 0.25) -> tuple:
    """
    يجد حدود الصفحة البيضاء داخل خلفية الماسح الرمادية.

    التحسينات في v13.1:
    - يدعم الآن كشف الحدود من الأعلى والأسفل أيضاً (لم يكن يعمل سابقاً)
    - يستخدم mean/median هجين للتعامل مع النص الكثيف
    - يتجاهل الأعمدة/الصفوف البيضاء المزيفة في البداية
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape

    # ── تحليل الأعمدة (يمين/يسار) ──────────────────────────
    col_mean = np.mean(gray, axis=0)
    col_med = np.median(gray, axis=0)
    # نستخدم mean إذا كان الفرق كبيراً (إشارة إلى وجود نص كثيف)
    col_metric = np.where(np.abs(col_mean - col_med) > 30, col_mean, col_med)

    def _find_bounds(signal, min_frac):
        n = len(signal)
        is_page = np.concatenate([[False], signal > page_threshold, [False]])
        diff = np.diff(is_page.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        if len(starts) == 0:
            return 0, n - 1

        lengths = ends - starts
        best = int(np.argmax(lengths))
        if lengths[best] < min_frac * n:
            return 0, n - 1
        return int(starts[best]), int(ends[best]) - 1

    # كشف الأعمدة
    col_s, col_e = _find_bounds(col_metric, min_page_fraction)
    MARGIN = 5
    left = max(0, col_s - MARGIN)
    right = min(w - 1, col_e + MARGIN)

    # ── تحليل الصفوف (علوي/سفلي) — جديد في v13.1! ──────────
    # نحلل فقط المنطقة التي كشفناها أعمدياً لتجنب التأثر بالرمادي الجانبي
    page_region = gray[:, left:right+1] if right > left else gray
    row_mean = np.mean(page_region, axis=1)
    row_med = np.median(page_region, axis=1)
    row_metric = np.where(np.abs(row_mean - row_med) > 30, row_mean, row_med)

    row_s, row_e = _find_bounds(row_metric, min_page_fraction)
    top = max(0, row_s - MARGIN)
    bottom = min(h - 1, row_e + MARGIN)

    return (left, top, w - right - 1, h - bottom - 1)


# ═══════════════════════════════════════════════════════════════
#  2. FIXED: auto_detect_skew — كشف دقيق بدون قيم قصوية خاطئة
# ═══════════════════════════════════════════════════════════════

def auto_detect_skew(img: np.ndarray, max_a: float = 5.0, step: float = 0.25) -> float:
    """
    يكشف زاوية الميلان الحقيقية باستخدام خوارزمية محسّنة.

    التحسينات في v13.1:
    - نطاق أصغر (-5° إلى +5°) مع دقة أعلى (0.25°)
    - استخدام projection profile محسّن
    - التحقق من أن الميلان حقيقي (مقارنة مع 0°)
    - إرجاع 0.0 إذا لم يكن هناك ميلان واضح
    - لا يعود يُرجع ±15° للصفحات المستقيمة
    """
    # المرحلة 1: إزالة الحدود الرمادية
    l, t, r, b = find_page_bounds(img)
    h, w = img.shape[:2]
    x0, x1 = l, w - r if r > 0 else w
    y0, y1 = t, h - b if b > 0 else h

    if x1 <= x0 or y1 <= y0:
        page = img
    else:
        page = img[y0:y1, x0:x1]

    # المرحلة 2: تحضير الصورة
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # المرحلة 3: كشف الميلان
    ph, pw = binary.shape
    best_score, best_angle = -1.0, 0.0

    for angle in np.arange(-max_a, max_a + step, step):
        M = cv2.getRotationMatrix2D((pw / 2, ph / 2), angle, 1.0)
        rot = cv2.warpAffine(binary, M, (pw, ph),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=0)

        profile = np.sum(rot, axis=1)
        non_empty_rows = np.sum(profile > 0)
        variance = np.var(profile)
        score = variance * (1 + non_empty_rows / ph)

        if score > best_score:
            best_score, best_angle = score, float(angle)

    # ── المرحلة 4: التحقق من أن الميلان حقيقي ──────────────
    M0 = cv2.getRotationMatrix2D((pw / 2, ph / 2), 0.0, 1.0)
    rot0 = cv2.warpAffine(binary, M0, (pw, ph),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=0)
    profile0 = np.sum(rot0, axis=1)
    score0 = np.var(profile0) * (1 + np.sum(profile0 > 0) / ph)

    # إذا كان الفرق ضئيلاً أو الزاوية صغيرة جداً → الصفحة مستقيمة
    if best_score < score0 * 1.05 or abs(best_angle) < 0.3:
        return 0.0

    return best_angle


# ═══════════════════════════════════════════════════════════════
#  3. FIXED: smart_auto_crop — يستخدم find_page_bounds المحسّن
# ═══════════════════════════════════════════════════════════════

def smart_auto_crop(img: np.ndarray, padding: int = 15, dark_threshold: int = 200) -> tuple:
    """
    قص ذكي على مرحلتين.

    التحسينات في v13.1:
    - يستخدم find_page_bounds المحسّن الذي يكشف الحدود من جميع الجهات
    - يتعامل بشكل أفضل مع الصفحات التي تحتوي على هوامش بيضاء كبيرة
    """
    h, w = img.shape[:2]

    # المرحلة 1: إزالة الرمادي من جميع الجهات
    gl, gt, gr, gb = find_page_bounds(img)
    x0, x1 = gl, w - gr if gr > 0 else w
    y0, y1 = gt, h - gb if gb > 0 else h

    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0, 0)

    page = img[y0:y1, x0:x1]
    pw, ph = page.shape[1], page.shape[0]

    # المرحلة 2: كشف المحتوى الفعلي
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)

    col_has = binary.max(axis=0) > 0
    row_has = binary.max(axis=1) > 0

    content_cols = np.where(col_has)[0]
    content_rows = np.where(row_has)[0]

    if len(content_cols) == 0 or len(content_rows) == 0:
        return (gl, gt, gr, gb)

    cl = max(0, content_cols[0] - padding)
    cr = min(pw - 1, content_cols[-1] + padding)
    ct = max(0, content_rows[0] - padding)
    cb = min(ph - 1, content_rows[-1] + padding)

    return (gl + cl, gt + ct, gr + (pw - cr - 1), gb + (ph - cb - 1))


# ═══════════════════════════════════════════════════════════════
#  4. FIXED: _apply_auto_deskew_on_load — استخدام الدوال المحسّنة
# ═══════════════════════════════════════════════════════════════

# استبدل هذه الدالة في MedicalDocApp:

def _apply_auto_deskew_on_load(self):
    """Auto deskew with improved detection and validation."""
    if self.current_img is None or self._is_processing:
        return
    self._is_processing = True
    self.btn_auto_deskew.setEnabled(False)
    self.btn_auto_deskew.setText("⏳ جاري...")
    self._skew_worker = SkewWorker(self.current_img)
    self._skew_worker.finished.connect(self._on_auto_skew_done)
    self._skew_worker.error.connect(self._on_auto_skew_err)
    self._skew_worker.start()

def _on_auto_skew_done(self, angle: float):
    """Handle auto deskew completion with validation."""
    self._is_processing = False
    self._detected_angle = angle

    if abs(angle) > 0.1:
        self._push_undo()
        self.current_params["deskew_angle"] = angle
        self.slider_deskew.setValue(int(angle * 10))
        self.lbl_deskew.setText("{:+.1f}°".format(angle))
        self.operation_history.append("ميلان تلقائي: {:.1f}°".format(angle))
        self._log("📐 ميلان مكتشف: {:.1f}°".format(angle))
    else:
        self._log("✅ الصفحة مستقيمة (لا ميلان)")
        # إعادة تعيين الميلان إلى 0 إذا كان ضئيلاً
        self.current_params["deskew_angle"] = 0.0
        self.slider_deskew.setValue(0)
        self.lbl_deskew.setText("0.0°")

    # قص ذكي بعد الميلان
    if self.current_img is not None:
        crop = smart_auto_crop(self.current_img, dark_threshold=self.gray_threshold)
        self.sp_left.setValue(crop[0])
        self.sp_top.setValue(crop[1])
        self.sp_right.setValue(crop[2])
        self.sp_bottom.setValue(crop[3])
        self.current_params["crop"] = crop
        self.operation_history.append("قص ذكي تلقائي")
        self._log("✂️ قص ذكي تلقائي: L={} T={} R={} B={}".format(*crop))

    self.btn_auto_deskew.setEnabled(True)
    self.btn_auto_deskew.setText("📐 كشف ميلان")
    self._update_preview()

    if self.chk_auto_save.isChecked() and not self._auto_save_in_prog:
        self._confirm_save()
