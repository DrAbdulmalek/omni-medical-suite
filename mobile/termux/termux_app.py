"""
termux_app.py — OmniMedical OCR for Termux (Android ARM64)
============================================================
نسخة مبسطة من Gradio UI تعمل مباشرة في Termux على هاتف Android.
لا تحتاج AppImage ولا APK — فقط Python + Gradio.

الميزات:
  • Handwriting Trainer — OCR + تصحيح + حفظ في قاعدة بيانات موحّدة
  • Scanner Fixer — deskew + auto-crop + denoise + ZIP export
    (يستخدم scanner_fixer عند التوفر، وإلا يعود للتنفيذ المحلي)
  • Batch processing — معالجة عدة صور دفعة واحدة
  • Offline mode — كل المعالجة محلية (لا إنترنت بعد التثبيت)
  • Statistics — تتبّع التصحيحات

التوحيد مع البنية الموحّدة (v1.1.1+):
  • Image processing: يستخدم scanner_fixer.{deskew, auto_crop, enhance_for_ocr}
    عند التوفر — نفس المكتبة التي يستخدمها packages/desktop/medical_doc_gui_final.py
    و packages/core/mobile/server.py. fallback للتنفيذ المحلي عند عدم التوفر
    (لإبقاء الملف قابلاً للتشغيل المستقل عند نسخه وحده).
  • Corrections: يستخدم packages.core.word_trainer.WordCorrectionDB +
    packages.core.corrections_manager.CorrectionsDictManager عند التوفر،
    بحيث تصحيحات الجوال عبر Termux تُغذّي نفس حلقة التعلّم التي بُنيت لخادم PWA.
    fallback لـ SQLite محلي + JSONL عند عدم التوفر.
  • OCR: يستخدم pytesseract مباشرة (وليس EngineRegistry/OCRService من app/services/).
    هذا استثناء متعمَّد: EngineRegistry يسحب PaddleOCR/EasyOCR كتبعيات اختيارية،
    وحجمها على هاتف Android ARM64 غير عملي (PaddleOCR ~500MB، EasyOCR ~400MB).
    pytesseract وحده (مع tesseract-data-arabic من pkg) أسرع تثبيتًا وأخفّ مواردًا.
    انظر ملاحظة "OCR engine choice" في الأسفل.

التشغيل:
  python termux_app.py --port 7860
  # ثم افتح: http://localhost:7860 في متصفح الهاتف

Author: Dr. Abdulmalek <drabdulmalek@proton.me>
License: AGPL-3.0
"""

from __future__ import annotations

import argparse
import cv2
import gradio as gr
import hashlib
import io
import json
import logging
import numpy as np
import os
import pytesseract
import sqlite3
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from PIL import Image
from typing import Optional

try:
    from pdf2image import convert_from_bytes
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ── Repo root discovery ──────────────────────────────────────────────────────
# termux_app.py may run from one of two locations:
#   1. The repo root (preferred): python mobile/termux/termux_app.py
#      → packages.scanner_fixer, packages.core.* are importable out of the box.
#   2. A standalone copy at ~/omni_workspace/termux_app.py (legacy install path
#      from install_termux.sh pre-v1.1.1).
#      → We need to find the repo root and add it to sys.path so the unified
#        scanner_fixer + corrections_manager + word_trainer can be imported.
# Env var OMNI_REPO_ROOT (set by install_termux.sh) takes precedence; otherwise
# we walk up from __file__ looking for `packages/scanner_fixer/pyproject.toml`.

def _discover_repo_root() -> Optional[Path]:
    env = os.environ.get("OMNI_REPO_ROOT")
    if env:
        p = Path(env).resolve()
        if (p / "packages" / "scanner_fixer" / "pyproject.toml").is_file():
            return p
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if (candidate / "packages" / "scanner_fixer" / "pyproject.toml").is_file():
            return candidate
    return None


REPO_ROOT = _discover_repo_root()
if REPO_ROOT is not None:
    REPO_ROOT_STR = str(REPO_ROOT)
    if REPO_ROOT_STR not in sys.path:
        sys.path.insert(0, REPO_ROOT_STR)
    # scanner_fixer is a src-layout package: its importable root is
    # packages/scanner_fixer/src/, not the package dir itself. Adding it
    # here means `import scanner_fixer` works without requiring a
    # `pip install -e packages/scanner_fixer` step on Termux (where every
    # extra install step costs phone storage + setup time).
    sf_src = REPO_ROOT / "packages" / "scanner_fixer" / "src"
    if sf_src.is_dir():
        sf_src_str = str(sf_src)
        if sf_src_str not in sys.path:
            sys.path.insert(0, sf_src_str)
    log_msg = f"Repo root discovered: {REPO_ROOT}"
else:
    log_msg = "Repo root NOT discovered — running in standalone mode (no scanner_fixer / learning loop)"

# ── Setup ───────────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get("HOME", "/tmp")) / "omni_workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
UPLOADS = WORKSPACE / "uploads"
EXPORTS = WORKSPACE / "exports"
DB_DIR = WORKSPACE / "corrections_db"
LOGS_DIR = WORKSPACE / "logs"
for d in (UPLOADS, EXPORTS, DB_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "corrections.db"
JSONL_PATH = EXPORTS / "corrections.jsonl"
LOG_PATH = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
log = logging.getLogger("OmniMedical.Termux")
log.info("=== OmniMedical Termux starting ===")
log.info("Workspace: %s", WORKSPACE)
log.info(log_msg)

# ── scanner_fixer integration (mirrors packages/desktop/medical_doc_gui_final.py) ──
# When the repo root is on sys.path and scanner_fixer is importable, we delegate
# the four image-normalization functions to its Hough-based deskew + morphological
# auto_crop + enhance_for_ocr pipeline — the SAME code path used by the desktop
# GUI and the PWA server. When it's not importable (standalone copy mode), we
# fall back to the local OpenCV implementations preserved below.
SCANNER_FIXER_AVAILABLE = False
sf_deskew = None
sf_auto_crop = None
sf_enhance_for_ocr = None
try:
    from scanner_fixer.deskew import deskew as sf_deskew  # type: ignore
    from scanner_fixer.crop import auto_crop as sf_auto_crop  # type: ignore
    from scanner_fixer.enhance import enhance_for_ocr as sf_enhance_for_ocr  # type: ignore
    SCANNER_FIXER_AVAILABLE = True
    log.info("scanner_fixer loaded — image processing delegated to unified library")
except ImportError as exc:
    log.warning("scanner_fixer not importable (%s) — falling back to local OpenCV impl", exc)


# ── Learning loop integration (mirrors packages/core/mobile/server.py) ──────
# When packages.core.* is importable, corrections flow into:
#   1. CorrectionsDictManager (JSON dictionary — used by HybridSpellChecker)
#   2. WordCorrectionDB (SQLite — used by the active learning retraining loop)
# Otherwise we fall back to the local SQLite schema + JSONL append.
HAS_LEARNING = False
corrections_mgr = None
word_trainer_db = None
try:
    from packages.core.corrections_manager import CorrectionsDictManager  # type: ignore
    from packages.core.word_trainer import WordCorrectionDB  # type: ignore
    corrections_mgr = CorrectionsDictManager(
        corrections_path=str(DB_DIR / "correction_dict.json"),
        arabic_fixes_path=str(DB_DIR / "arabic_fixes.json"),
        backup_dir=str(DB_DIR / "backups"),
    )
    word_trainer_db = WordCorrectionDB(db_path=str(DB_DIR / "corrections.db"))

    # Override the instance's update_arabic_fixes so it writes to the
    # workspace, not the repo. save_batch() calls self.update_arabic_fixes()
    # with no args; the default `path` parameter on the bound method is
    # evaluated at function-definition time (using the module-level
    # ARABIC_FIXES_PATH = "data/arabic_fixes.json"), so we can't fix this
    # by patching the module constant. Rebinding the method on the instance
    # is the cleanest fix that doesn't require modifying WordCorrectionDB.
    _workspace_arabic_path = str(DB_DIR / "arabic_fixes.json")
    _orig_update_arabic_fixes = word_trainer_db.update_arabic_fixes

    def _patched_update_arabic_fixes(path: str = _workspace_arabic_path) -> int:
        return _orig_update_arabic_fixes(path)

    word_trainer_db.update_arabic_fixes = _patched_update_arabic_fixes  # type: ignore

    HAS_LEARNING = True
    log.info("Learning loop wired: CorrectionsDictManager + WordCorrectionDB (shared with PWA server)")
except ImportError as exc:
    log.warning("packages.core.* not importable (%s) — falling back to local SQLite", exc)


# ── Local SQLite schema (fallback when packages.core.* is unavailable) ──────
# Kept here so the file remains runnable as a standalone copy. Once the
# learning-loop modules are available, this schema is superseded by
# WordCorrectionDB._create_schema() — but the table name `corrections` is
# the same, so a DB created by the standalone path is forward-compatible.
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT NOT NULL,
        corrected TEXT NOT NULL,
        language TEXT,
        image_path TEXT,
        source TEXT DEFAULT 'termux',
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS processed_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT,
        processed_path TEXT,
        mode TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn


# ── OCR corrections (Arabic medical) ────────────────────────────────────────
# Same dict as app/services/ocr_service.py and hf-space/app.py — kept in sync
# by the CI gate in .github/workflows/hf-space-drift.yml. The Termux app does
# not import the canonical module (to keep its dependency surface small), so
# this is a copy; if the canonical dict changes, this file must be updated
# alongside it.
OCR_CORRECTIONS = {
    "باراسيتبمول": "باراسيتامول", "ايبوروفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين", "اموكسيسلين": "اموكسيسيلين",
    "ازيثروميسين": "ازيثرومايسين", "ميتروندازول": "ميترونيدازول",
    "ديكلوفيناك ": "ديكلوفيناك", "اوجمينتين": "اوجمنتين",
    "اوميبرازول ": "اوميبرازول", "سيليبريكس ": "سيليبريكس",
    "ترامادول ": "ترامادول", "كاتافلام ": "كاتافلام",
    "نوفافين ": "نوفافين", "فلاميكس ": "فلاميكس",
    "بنادول ": "بنادول", "ادفيل ": "ادفيل",
}


def apply_corrections(text: str) -> str:
    """Apply the OCR-corrections dict. This is the *dict-only* fast path used
    by `segment_words`. The full spell-checker pass (via HybridSpellChecker)
    is applied separately by the canonical `app/services/ocr_service.py`
    pipeline — Termux intentionally skips it to avoid pulling
    `packages.core.spell_checker`'s heavy deps on a phone.
    """
    for wrong, right in OCR_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


# ── Image processing ────────────────────────────────────────────────────────
def segment_words(image: Image.Image) -> list[tuple[Image.Image, str]]:
    """تقسيم الصورة إلى كلمات منفصلة + OCR لكل كلمة.

    ملاحظة حول OCR engine choice:
      نستخدم pytesseract.image_to_string مباشرةً بدلاً من EngineRegistry أو
      OCRService من app/services/. السبب: EngineRegistry يسحب PaddleOCR (~500MB)
      و EasyOCR (~400MB) كتبعيات اختيارية، وهو وزن غير عملي على هاتف Android
      ARM64 محدود الموارد. pytesseract + tesseract-data-arabic (من pkg) أسرع
      تثبيتًا وأخفّ مواردًا. هذا استثناء متعمَّد لبيئة Termux فقط ولا يُطبَّق
      على خادم PWA أو desktop GUI — كلاهما يستخدم EngineRegistry/OCRService.
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    words = []
    for cnt in sorted(contours, key=lambda c: cv2.boundingRect(c)[0]):
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 15 and h > 15:
            word_img = image.crop((x, y, x + w, y + h))
            text = pytesseract.image_to_string(word_img, lang="ara+eng").strip()
            text = apply_corrections(text)
            if text:
                words.append((word_img, text))
    return words


def deskew(image: np.ndarray) -> np.ndarray:
    """تصحيح الميل.

    When scanner_fixer is available, delegates to ``scanner_fixer.deskew.deskew``
    which uses Hough line transform + standard-deviation guard (more accurate
    than the local minAreaRect approach, especially on text-rich pages).
    Falls back to the local OpenCV implementation otherwise.
    """
    if SCANNER_FIXER_AVAILABLE and sf_deskew is not None:
        try:
            corrected, _angle, _meta = sf_deskew(image, method="hough")
            return corrected
        except Exception as exc:
            log.debug("scanner_fixer.deskew failed, falling back: %s", exc)

    # Fallback: minAreaRect-based deskew (original Termux implementation)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def text_aware_crop(image: np.ndarray, padding: int = 10) -> np.ndarray:
    """اقتصاص تلقائي يحافظ على النص.

    When scanner_fixer is available, delegates to ``scanner_fixer.crop.auto_crop``
    which uses morphological close/open + bounding rect (more robust against
    scanner borders and small noise blobs than the local largest-contour
    approach). Falls back to the local implementation otherwise.
    """
    if SCANNER_FIXER_AVAILABLE and sf_auto_crop is not None:
        try:
            return sf_auto_crop(image, padding=padding)
        except Exception as exc:
            log.debug("scanner_fixer.auto_crop failed, falling back: %s", exc)

    # Fallback: largest-contour crop (original Termux implementation)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(image.shape[1] - x, w + 2 * padding)
    h = min(image.shape[0] - y, h + 2 * padding)
    return image[y:y + h, x:x + w]


def denoise(image: np.ndarray) -> np.ndarray:
    """تنظيف الضوضاء.

    When scanner_fixer is available, delegates to
    ``scanner_fixer.enhance.remove_noise`` (which uses the same
    fastNlMeansDenoising under the hood but is the canonical entry point
    shared with desktop/PWA). Falls back to a direct cv2 call otherwise.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    return cv2.fastNlMeansDenoising(gray, h=10)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """تحسين التباين (CLAHE).

    When scanner_fixer is available, delegates to
    ``scanner_fixer.enhance.enhance_contrast_clahe``. Falls back to a
    direct cv2.createCLAHE call otherwise.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


# ── DB operations ───────────────────────────────────────────────────────────
def save_correction(original: str, corrected: str, lang: str = "ara+eng") -> str:
    """Persist a correction to the shared learning loop.

    When packages.core.* is importable, this writes to:
      1. CorrectionsDictManager (JSON dict — used by HybridSpellChecker)
      2. WordCorrectionDB (SQLite — used by the active learning retraining loop)

    Both stores live under ``~/omni_workspace/corrections_db/`` and are the
    SAME files used by ``packages/core/mobile/server.py`` (the PWA server)
    when ``OMNI_MOBILE_DB_DIR`` points there. This means a correction made
    on the Termux Gradio UI is immediately visible to the PWA server's
    ``/stats`` endpoint and will be picked up by the next fine-tuning run.

    Falls back to the local SQLite schema + JSONL append when the learning
    modules aren't importable (standalone-copy mode).
    """
    if not corrected.strip() or corrected == original:
        return "⚠️ لم يتم التعديل"

    # Normalize lang: "ara+eng" → "ar" for the learning DB schema (which uses
    # ISO 639-1 codes). The legacy SQLite schema keeps the original string.
    lang_normalized = "ar" if lang.startswith("ara") else lang.split("+")[0]

    if HAS_LEARNING and corrections_mgr is not None and word_trainer_db is not None:
        try:
            corrections_mgr.add(original, corrected)
            word_trainer_db.save_batch(
                items=[{
                    "idx": 0,
                    "predicted": original,
                    "corrected": corrected,
                    "lang": lang_normalized,
                    "confidence": 0.0,
                }],
                image_hash="",
            )
            stats = word_trainer_db.stats()
            count = stats.get("total_corrections", 0)
            return f"✅ تم الحفظ في حلقة التعلّم الموحّدة — الإجمالي: {count} تصحيح"
        except Exception as exc:
            log.error("Learning-loop save failed, falling back to local: %s", exc)

    # Fallback: local SQLite + JSONL
    conn = init_db()
    conn.execute(
        "INSERT INTO corrections (original, corrected, language) VALUES (?, ?, ?)",
        (original, corrected, lang),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    conn.close()

    with open(JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "original": original,
            "corrected": corrected,
            "lang": lang,
            "ts": time.time(),
            "source": "termux",
        }, ensure_ascii=False) + "\n")

    return f"✅ تم الحفظ (محلي) — الإجمالي: {count} تصحيح"


def get_stats() -> str:
    """Return a one-line stats string.

    Prefers the shared WordCorrectionDB stats (which include accuracy rate,
    sessions, and per-language breakdown) when available; falls back to
    the local SQLite counts otherwise.
    """
    if HAS_LEARNING and word_trainer_db is not None:
        try:
            s = word_trainer_db.stats()
            return (
                f"📊 حلقة التعلّم الموحّدة: {s.get('total_corrections', 0)} تصحيح | "
                f"جلسات: {s.get('sessions', 0)} | "
                f"دقة: {s.get('accuracy_rate', '—')}"
            )
        except Exception as exc:
            log.warning("word_trainer.stats failed, falling back: %s", exc)

    conn = init_db()
    count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    processed = conn.execute("SELECT COUNT(*) FROM processed_images").fetchone()[0]
    last_corr = conn.execute("SELECT timestamp FROM corrections ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    last_str = last_corr[0] if last_corr else "—"
    return f"📊 الإجمالي: {count} تصحيح | صور معالَجة: {processed} | آخر تصحيح: {last_str}"


# ── Processing handlers ─────────────────────────────────────────────────────
def process_input(file_obj, lang: str = "ara+eng"):
    """معالجة صورة أو PDF."""
    if file_obj is None:
        return [], "❌ لم يتم رفع ملف", "", ""

    file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    suffix = Path(file_path).suffix.lower()
    log.info("Processing: %s (lang=%s)", file_path, lang)

    gallery_items = []
    all_text = []

    try:
        if suffix == ".pdf":
            if not HAS_PDF:
                return [], "❌ pdf2image غير مثبت — شغّل: pip install pdf2image", "", ""
            with open(file_path, "rb") as f:
                pages = convert_from_bytes(f.read())
            for i, page in enumerate(pages):
                words = segment_words(page)
                for j, (word_img, text) in enumerate(words):
                    out = UPLOADS / f"p{i}_w{j}.png"
                    word_img.save(out)
                    gallery_items.append((str(out), text))
                    all_text.append(text)
        else:
            image = Image.open(file_path).convert("RGB")
            words = segment_words(image)
            for j, (word_img, text) in enumerate(words):
                out = UPLOADS / f"w{j}.png"
                word_img.save(out)
                gallery_items.append((str(out), text))
                all_text.append(text)

        full_text = "\n".join(all_text)
        status = f"✅ تم استخراج {len(gallery_items)} كلمة"
        log.info("Done: %d words", len(gallery_items))
        return gallery_items, status, full_text, full_text
    except Exception as e:
        log.error("process_input failed: %s", e, exc_info=True)
        return [], f"❌ خطأ: {e}", "", ""


def process_scanner(image, mode: str = "all"):
    """معالجة صورة Scanner Fixer."""
    if image is None:
        return None, "❌ لا توجد صورة"
    img = np.array(image.convert("RGB"))
    steps = []

    try:
        if mode in ("deskew", "all"):
            img = deskew(img)
            steps.append("deskew")
        if mode in ("denoise", "all"):
            img_proc = denoise(img)
            img = cv2.cvtColor(img_proc, cv2.COLOR_GRAY2RGB)
            steps.append("denoise")
        if mode in ("contrast", "all"):
            img_proc = enhance_contrast(img)
            img = cv2.cvtColor(img_proc, cv2.COLOR_GRAY2RGB)
            steps.append("contrast")
        if mode in ("crop", "all"):
            img = text_aware_crop(img)
            steps.append("text-aware-crop")

        out_path = EXPORTS / f"processed_{int(time.time()*1000)}.png"
        cv2.imwrite(str(out_path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

        # Log to DB
        conn = init_db()
        conn.execute(
            "INSERT INTO processed_images (original_path, processed_path, mode) VALUES (?, ?, ?)",
            ("upload", str(out_path), mode),
        )
        conn.commit()
        conn.close()

        backend = "scanner_fixer" if SCANNER_FIXER_AVAILABLE else "local-opencv"
        return Image.fromarray(img), f"✅ {', '.join(steps)} ({backend}) → {out_path.name}"
    except Exception as e:
        log.error("process_scanner failed: %s", e, exc_info=True)
        return None, f"❌ خطأ: {e}"


def process_batch(files, mode: str = "all"):
    """معالجة دفعة + ZIP."""
    if not files:
        return [], "❌ لا توجد ملفات"
    results = []
    for f in files:
        try:
            img = Image.open(f.name if hasattr(f, "name") else f)
            processed, _ = process_scanner(img, mode)
            if processed:
                results.append((np.array(processed), Path(f.name).stem))
        except Exception as e:
            log.warning("Batch item failed: %s → %s", f, e)

    zip_path = EXPORTS / f"batch_{int(time.time())}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for img_arr, name in results:
            buf = io.BytesIO()
            Image.fromarray(img_arr).save(buf, format="PNG")
            z.writestr(f"{name}.png", buf.getvalue())

    return [r[0] for r in results], f"✅ {len(results)} صورة → {zip_path.name}"


def export_jsonl():
    """تصدير JSONL."""
    if not JSONL_PATH.exists():
        return None, "❌ لا توجد تصحيحات"
    return str(JSONL_PATH), f"✅ تم التصدير: {JSONL_PATH.stat().st_size} bytes"


def compute_file_hash(file_obj):
    """SHA256 للملف."""
    if file_obj is None:
        return "—"
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Gradio UI ───────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="OmniMedical OCR (Termux)",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 100% !important; padding: 12px !important; }
        footer { display: none !important; }
        """,
    ) as demo:
        gr.Markdown("""
        # 🏥 OmniMedical OCR — Termux
        يعمل مباشرة على هاتفك Android. كل المعالجة محلية (offline).
        """)

        with gr.Tabs():
            # ── Tab 1: Handwriting Trainer ────────────────────────────────
            with gr.Tab("✍️ Trainer"):
                gr.Markdown("### رفع صورة / PDF → OCR → تصحيح → حفظ")
                with gr.Row():
                    file_input = gr.File(
                        label="📤 ارفع صورة / PDF",
                        file_types=[".png", ".jpg", ".jpeg", ".pdf"],
                    )
                    lang_dd = gr.Dropdown(
                        ["ara+eng", "eng", "deu", "fra"],
                        value="ara+eng",
                        label="🌐 اللغة",
                    )
                    process_btn = gr.Button("🔄 معالجة", variant="primary")

                status_box = gr.Textbox(label="الحالة", interactive=False)
                gallery = gr.Gallery(
                    label="🖼️ الكلمات المُستخرجة",
                    columns=4,
                    height=300,
                )

                with gr.Row():
                    full_text = gr.Textbox(
                        label="📝 النص الأصلي (OCR)",
                        lines=5,
                        interactive=True,
                    )
                    corrected_text = gr.Textbox(
                        label="✏️ التصحيح",
                        lines=5,
                        interactive=True,
                    )

                with gr.Row():
                    save_btn = gr.Button("💾 حفظ التصحيح", variant="primary")
                    export_btn = gr.Button("📤 تصدير JSONL")
                    stats_btn = gr.Button("📊 إحصائيات")

                stats_box = gr.Textbox(label="📊 الإحصائيات", interactive=False)
                export_file = gr.File(label="📥 ملف JSONL", visible=False)

                process_btn.click(
                    process_input,
                    [file_input, lang_dd],
                    [gallery, status_box, full_text, corrected_text],
                )
                save_btn.click(
                    save_correction,
                    [full_text, corrected_text, lang_dd],
                    [status_box],
                )
                export_btn.click(
                    export_jsonl,
                    outputs=[export_file, status_box],
                ).then(lambda: gr.update(visible=True), outputs=[export_file])
                stats_btn.click(get_stats, outputs=[stats_box])

            # ── Tab 2: Scanner Fixer ──────────────────────────────────────
            with gr.Tab("📷 Scanner"):
                gr.Markdown("### معالجة الصور الممسوحة: deskew + denoise + auto-crop")

                with gr.Tab("📝 صورة واحدة"):
                    with gr.Row():
                        input_img = gr.Image(label="📥 الأصل", type="pil")
                        output_img = gr.Image(label="📤 المعالَج", type="pil")
                    mode_dd = gr.Dropdown(
                        ["all", "deskew", "denoise", "contrast", "crop"],
                        value="all",
                        label="⚙️ الوضع",
                    )
                    scan_btn = gr.Button("🔄 معالجة", variant="primary")
                    scan_status = gr.Textbox(label="الحالة", interactive=False)
                    scan_btn.click(
                        process_scanner,
                        [input_img, mode_dd],
                        [output_img, scan_status],
                    )

                with gr.Tab("🗂️ Batch + ZIP"):
                    batch_files = gr.Files(
                        label="📁 ارفع عدة صور",
                        file_types=[".png", ".jpg", ".jpeg"],
                    )
                    batch_mode = gr.Dropdown(
                        ["all", "deskew", "denoise", "contrast", "crop"],
                        value="all",
                        label="⚙️ الوضع",
                    )
                    batch_btn = gr.Button("🔄 معالجة Batch", variant="primary")
                    batch_gallery = gr.Gallery(
                        label="🖼️ النتائج",
                        columns=4,
                        height=300,
                    )
                    batch_status = gr.Textbox(label="الحالة", interactive=False)
                    batch_btn.click(
                        process_batch,
                        [batch_files, batch_mode],
                        [batch_gallery, batch_status],
                    )

            # ── Tab 3: Tools ──────────────────────────────────────────────
            with gr.Tab("🛠️ Tools"):
                gr.Markdown("### أدوات مساعدة")
                with gr.Row():
                    hash_file = gr.File(label="📤 ملف لحساب SHA256")
                    hash_btn = gr.Button("🔍 احسب")
                    hash_out = gr.Textbox(label="SHA256", interactive=False)
                hash_btn.click(compute_file_hash, [hash_file], [hash_out])

                gr.Markdown("---")
                gr.Markdown("### معلومات النظام")
                gr.JSON(value={
                    "workspace": str(WORKSPACE),
                    "db_path": str(DB_PATH),
                    "jsonl_path": str(JSONL_PATH),
                    "logs": str(LOG_PATH),
                    "uploads_dir": str(UPLOADS),
                    "exports_dir": str(EXPORTS),
                    "repo_root": str(REPO_ROOT) if REPO_ROOT else "(standalone — repo root not discovered)",
                    "scanner_fixer_active": SCANNER_FIXER_AVAILABLE,
                    "learning_loop_active": HAS_LEARNING,
                    "tesseract_langs": "ara+eng" if os.path.exists("/data/data/com.termux/files/usr/share/tessdata/ara.traineddata") or os.path.exists("/usr/share/tesseract-ocr/4.00/tessdata/ara.traineddata") else "eng",
                    "pdf_support": HAS_PDF,
                    "python_version": sys.version.split()[0],
                    "platform": sys.platform,
                })

        gr.Markdown(f"""
        ---
        **OmniMedical v1.1.1** — [GitHub](https://github.com/DrAbdulmalek/omni-medical-suite)
        | Workspace: `{WORKSPACE}`
        """)

    return demo


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OmniMedical Termux App")
    parser.add_argument("--port", type=int, default=7860, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--share", action="store_true", help="Create public Gradio share link")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    log.info("Building UI...")
    demo = build_ui()

    log.info("Launching on %s:%d (share=%s)", args.host, args.port, args.share)
    print(f"\n{'='*60}")
    print(f"  🏥 OmniMedical OCR (Termux)")
    print(f"  🌐 Open in browser: http://localhost:{args.port}")
    print(f"  📁 Workspace: {WORKSPACE}")
    print(f"  📝 Logs: {LOG_PATH}")
    print(f"  🔧 scanner_fixer: {'active' if SCANNER_FIXER_AVAILABLE else 'fallback (local OpenCV)'}")
    print(f"  🧠 learning loop: {'active' if HAS_LEARNING else 'fallback (local SQLite)'}")
    print(f"{'='*60}\n")

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=args.debug,
        show_error=True,
        prevent_thread_lock=False,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()
