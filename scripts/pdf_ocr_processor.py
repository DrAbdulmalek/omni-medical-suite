#!/usr/bin/env python3
"""
pdf_ocr_processor.py — معالج PDF OCR مع ضبط تلقائي واستخراج مسارد
═══════════════════════════════════════════════════════════════════════

نظام متكامل لاستخراج النص من ملفات PDF الطبية باستخدام:
  - OCR متقدم (Tesseract) مع ضبط تلقائي لمعاملات PSM و DPI
  - معالجة مسبقة للصور عبر scanner_fixer (deskew, crop, normalize)
  - استخراج المسارد الثنائية اللغة (عربي-إنجليزي)
  - حفظ النتائج في تنسيقات متعددة (TXT, CSV, JSON)
  - دمج مع نظام التسجيل المتقدم (advanced_logger)

الاستخدام:
    python3 scripts/pdf_ocr_processor.py
    python3 scripts/pdf_ocr_processor.py --input data/report.pdf --output ~/output/
    python3 scripts/pdf_ocr_processor.py --auto-tune --engine tesseract
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ── إضافة مسار المشروع ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "scanner_fixer" / "src"))

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger("pdf_ocr_processor")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    _fh = logging.FileHandler("pdf_ocr_processor.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(_fh)
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_ch)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
_HAS_PDF2IMAGE = False
_HAS_TESSERACT = False
_HAS_SCANNER_FIXER = False
_HAS_FITZ = False
_HAS_PANDAS = False

try:
    from pdf2image import convert_from_path
    _HAS_PDF2IMAGE = True
except ImportError:
    pass

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    pass

try:
    from scanner_fixer.pipeline import fix_scan
    from scanner_fixer.normalize import normalize_scanned_image
    from scanner_fixer.deskew import detect_skew_angle
    from scanner_fixer.crop import auto_crop
    from scanner_fixer.enhance import enhance_for_ocr
    _HAS_SCANNER_FIXER = True
except ImportError:
    pass

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    pass

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PSM_MODES = [3, 4, 6, 11]  # Page Segmentation Modes to try
DPI_OPTIONS = [200, 300, 400]  # DPI values to try
GLOSSARY_PATTERNS = [
    re.compile(r'(.+?)\s*[=ـ]\s*(.+?)$'),           # العربية = English
    re.compile(r'(.+?)\s*[-–—]\s*(.+?)$'),            # العربية - English
    re.compile(r'(.+?)\s*[:：]\s*(.+?)$'),             # العربية : English
    re.compile(r'(.+?)\t+(.+?)$'),                     # العربية\tEnglish
]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}

# ---------------------------------------------------------------------------
# Advanced logger integration
# ---------------------------------------------------------------------------
_ADVANCED_LOGGER_AVAILABLE = False
_feedback_collector = None

try:
    from scripts.advanced_logger import get_feedback_collector
    _feedback_collector = get_feedback_collector()
    _ADVANCED_LOGGER_AVAILABLE = True
except ImportError:
    pass


def log_ocr_result(
    file_name: str,
    pages: int,
    entries: int,
    config: dict,
    source: str = "pdf_ocr_processor",
) -> None:
    """تسجيل نتيجة OCR في نظام التسجيل المتقدم."""
    if not _ADVANCED_LOGGER_AVAILABLE or _feedback_collector is None:
        return

    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "ocr_processed",
            "details": {
                "file": file_name,
                "pages": pages,
                "entries_found": entries,
                "config": config,
                "source": source,
            },
        }
        log_file = (
            Path("logs/user_actions")
            / f"actions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"OCR logged: {file_name} ({pages} pages, {entries} entries)")
    except Exception as exc:
        logger.debug(f"Advanced logging failed: {exc}")


# ===========================================================================
# PDFOCRProcessor
# ===========================================================================
class PDFOCRProcessor:
    """
    معالج PDF OCR مع ضبط تلقائي واستخراج مسارد.

    الخطوات:
        1. تحويل PDF إلى صور (PyMuPDF أو pdf2image)
        2. ضبط تلقائي لمعاملات OCR (PSM + DPI) على الصفحة الأولى
        3. معالجة مسبقة للصور (scanner_fixer: deskew + crop + enhance)
        4. استخراج النص عبر Tesseract
        5. استخراج المسارد الثنائية اللغة
        6. حفظ النتائج (TXT, CSV, JSON)
    """

    def __init__(
        self,
        output_dir: str | Path | None = None,
        language: str = "ara+eng",
        auto_tune: bool = True,
        normalize_images: bool = True,
        github_token: str | None = None,
    ) -> None:
        """
        تهيئة المعالج.

        Args:
            output_dir: مجلد الإخراج (افتراضي: ~/glossaries_output)
            language: لغة OCR لـ Tesseract
            auto_tune: تفعيل الضبط التلقائي لـ PSM و DPI
            normalize_images: تطبيع الصور عبر scanner_fixer قبل OCR
            github_token: توكن GitHub (اختياري)
        """
        self.output_dir = Path(output_dir or os.path.expanduser("~/glossaries_output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.language = language
        self.auto_tune = auto_tune
        self.normalize_images = normalize_images
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")

        # Results storage
        self.results: list[dict[str, Any]] = []
        self.combined_glossary: list[dict[str, str]] = []

        # Best config from auto-tuning
        self.best_config: dict[str, Any] = {
            "psm": 6,
            "dpi": 300,
            "language": self.language,
        }

        # Check dependencies
        if not _HAS_TESSERACT:
            logger.error("pytesseract غير مثبت! ثبّته: pip install pytesseract")
        if not _HAS_PDF2IMAGE and not _HAS_FITZ:
            logger.error("لا توجد مكتبة PDF! ثبّت: pip install PyMuPDF أو pdf2image")

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------
    def process_pdf(
        self,
        pdf_path: str | Path,
        pages: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        معالجة ملف PDF كامل.

        Args:
            pdf_path: مسار ملف PDF
            pages: أرقام صفحات محددة (0-indexed). None = الكل

        Returns:
            قاموس بالنتائج الكاملة
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"الملف غير موجود: {pdf_path}")

        logger.info(f"بدء معالجة: {pdf_path.name}")
        start = time.perf_counter()

        # Step 1: Convert PDF to images
        page_images = self._pdf_to_images(pdf_path, pages)
        if not page_images:
            return {"file": str(pdf_path), "pages": 0, "entries_found": 0, "error": "لا صفحات"}

        # Step 2: Auto-tune on first page
        if self.auto_tune and len(page_images) > 0:
            logger.info("ضبط تلقائي لمعاملات OCR على الصفحة الأولى...")
            self._auto_tune(page_images[0])
            logger.info(f"أفضل إعداد: PSM={self.best_config['psm']}, DPI={self.best_config['dpi']}")

        # Step 3: Process each page
        all_text = ""
        total_entries = 0

        for idx, pil_image in enumerate(page_images):
            page_num = idx if pages is None else pages[idx]
            logger.info(f"معالجة صفحة {page_num + 1}/{len(page_images)}...")

            # Normalize image
            if self.normalize_images and _HAS_SCANNER_FIXER:
                try:
                    bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    result = fix_scan(bgr, do_crop=True, do_deskew=True, do_enhance=True)
                    normalized_bgr = result["image"]
                    pil_image = Image.fromarray(
                        cv2.cvtColor(normalized_bgr, cv2.COLOR_BGR2RGB)
                    )
                except Exception as exc:
                    logger.warning(f"فشل التطبيع للصفحة {page_num}: {exc}")

            # OCR
            text = self._run_tesseract(pil_image)
            all_text += f"\n--- صفحة {page_num + 1} ---\n{text}\n"

            # Extract glossary entries
            entries = self._extract_glossary(text, source=pdf_path.name)
            total_entries += len(entries)
            self.combined_glossary.extend(entries)

        # Step 4: Save results
        elapsed = time.perf_counter() - start
        file_result = {
            "file": pdf_path.name,
            "file_path": str(pdf_path),
            "pages": len(page_images),
            "entries_found": total_entries,
            "best_config": self.best_config.copy(),
            "processing_time_seconds": round(elapsed, 2),
            "error": "",
        }
        self.results.append(file_result)

        # Save per-file outputs
        self._save_text(all_text, pdf_path.stem)
        self._save_csv(self.combined_glossary, pdf_path.stem)
        self._save_json(file_result, all_text, pdf_path.stem)

        # Log to advanced logger
        log_ocr_result(
            file_name=pdf_path.name,
            pages=len(page_images),
            entries=total_entries,
            config=self.best_config.copy(),
            source="pdf_ocr_processor",
        )

        logger.info(
            f"✅ اكتملت: {pdf_path.name} — {len(page_images)} صفحة، "
            f"{total_entries} مُدخلة مسرد، {elapsed:.1f} ثانية"
        )
        return file_result

    def process_directory(
        self,
        input_dir: str | Path,
    ) -> list[dict[str, Any]]:
        """
        معالجة جميع ملفات PDF في مجلد.

        Args:
            input_dir: مسار المجلد

        Returns:
            قائمة نتائج لكل ملف
        """
        input_dir = Path(input_dir)
        if not input_dir.is_dir():
            raise FileNotFoundError(f"المجلد غير موجود: {input_dir}")

        pdf_files = sorted(input_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"لا توجد ملفات PDF في: {input_dir}")
            return []

        logger.info(f"وجد {len(pdf_files)} ملف PDF في {input_dir}")
        all_results = []

        for pdf_path in pdf_files:
            try:
                result = self.process_pdf(pdf_path)
                all_results.append(result)
            except Exception as exc:
                logger.error(f"فشل في معالجة {pdf_path.name}: {exc}")
                all_results.append({
                    "file": pdf_path.name,
                    "error": str(exc),
                })

        # Save combined outputs
        self._save_combined_glossary()

        return all_results

    # ------------------------------------------------------------------
    # PDF → Image conversion
    # ------------------------------------------------------------------
    def _pdf_to_images(
        self,
        pdf_path: Path,
        pages: list[int] | None = None,
    ) -> list[Image.Image]:
        """تحويل صفحات PDF إلى صور PIL."""
        images: list[Image.Image] = []

        if _HAS_FITZ:
            images = self._pdf_to_images_fitz(pdf_path, pages)
        elif _HAS_PDF2IMAGE:
            images = self._pdf_to_images_pdf2image(pdf_path, pages)
        else:
            raise RuntimeError("لا توجد مكتبة PDF متاحة")

        logger.debug(f"تم تحويل {len(images)} صفحة إلى صور")
        return images

    def _pdf_to_images_fitz(
        self,
        pdf_path: Path,
        pages: list[int] | None = None,
    ) -> list[Image.Image]:
        """تحويل باستخدام PyMuPDF."""
        import fitz

        doc = fitz.open(str(pdf_path))
        total = len(doc)

        target_pages = pages if pages is not None else list(range(total))
        target_pages = [p for p in target_pages if 0 <= p < total]

        images = []
        dpi = self.best_config.get("dpi", 300)
        mat = fitz.Matrix(dpi / 72, dpi / 72)

        for pn in target_pages:
            page = doc[pn]
            pix = page.get_pixmap(matrix=mat)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.h, pix.w, pix.n
            )
            if pix.n == 4:
                pil_img = Image.fromarray(img_array[:, :, :3], mode="RGB")
            elif pix.n == 1:
                pil_img = Image.fromarray(img_array[:, :, 0], mode="L").convert("RGB")
            else:
                pil_img = Image.fromarray(img_array, mode="RGB")
            images.append(pil_img)

        doc.close()
        return images

    def _pdf_to_images_pdf2image(
        self,
        pdf_path: Path,
        pages: list[int] | None = None,
    ) -> list[Image.Image]:
        """تحويل باستخدام pdf2image (poppler)."""
        dpi = self.best_config.get("dpi", 300)

        if pages is not None:
            first_page = min(pages) + 1
            last_page = max(pages) + 1
            return convert_from_path(
                str(pdf_path), dpi=dpi,
                first_page=first_page, last_page=last_page,
            )
        else:
            return convert_from_path(str(pdf_path), dpi=dpi)

    # ------------------------------------------------------------------
    # OCR with Tesseract
    # ------------------------------------------------------------------
    def _run_tesseract(self, pil_image: Image.Image) -> str:
        """تشغيل Tesseract OCR على صورة PIL."""
        if not _HAS_TESSERACT:
            return ""

        config_str = f"--psm {self.best_config['psm']} --dpi {self.best_config['dpi']}"
        try:
            text = pytesseract.image_to_string(
                pil_image,
                lang=self.language,
                config=config_str,
            )
            return text.strip()
        except Exception as exc:
            logger.warning(f"Tesseract فشل: {exc}")
            # Fallback: try with default config
            try:
                text = pytesseract.image_to_string(pil_image, lang=self.language)
                return text.strip()
            except Exception:
                return ""

    # ------------------------------------------------------------------
    # Auto-tuning
    # ------------------------------------------------------------------
    def _auto_tune(self, pil_image: Image.Image) -> None:
        """
        ضبط تلقائي لمعاملات OCR (PSM + DPI) على صورة واحدة.

        يجرّب كل توليفة PSM × DPI ويختار الأفضل بناءً على:
        - طول النص المستخرج (أطول = أفضل عادةً)
        - عدد الكلمات العربية
        - تناسق النص
        """
        if not _HAS_TESSERACT:
            return

        best_score = -1
        best_psm = 6
        best_dpi = 300

        # Resize image to different DPIs for testing
        original_width, original_height = pil_image.size

        for psm in PSM_MODES:
            for dpi in DPI_OPTIONS:
                try:
                    # Resize image to simulate DPI
                    scale = dpi / 300
                    new_width = int(original_width * scale)
                    new_height = int(original_height * scale)
                    resized = pil_image.resize(
                        (new_width, new_height), Image.LANCZOS
                    )

                    config_str = f"--psm {psm}"
                    text = pytesseract.image_to_string(
                        resized,
                        lang=self.language,
                        config=config_str,
                    )

                    score = self._evaluate_ocr_text(text)
                    logger.debug(
                        f"PSM={psm}, DPI={dpi}: score={score:.2f}, "
                        f"len={len(text)}, words={len(text.split())}"
                    )

                    if score > best_score:
                        best_score = score
                        best_psm = psm
                        best_dpi = dpi

                except Exception:
                    continue

        self.best_config = {
            "psm": best_psm,
            "dpi": best_dpi,
            "language": self.language,
            "auto_tune_score": round(best_score, 3),
        }

    @staticmethod
    def _evaluate_ocr_text(text: str) -> float:
        """
        تقييم جودة النص المستخرج.

        العوامل:
        - طول النص (أطول أفضل حتى حد معين)
        - نسبة الأحرف العربية
        - عدد الكلمات
        - تناسق الأطوال
        """
        if not text.strip():
            return 0.0

        # Length score (normalize to 0-1, cap at 2000 chars)
        length_score = min(len(text) / 2000, 1.0)

        # Arabic character ratio
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_alpha = len(re.findall(r'[a-zA-Z\u0600-\u06FF]', text))
        arabic_ratio = arabic_chars / max(total_alpha, 1)

        # Word count score
        words = text.split()
        word_score = min(len(words) / 200, 1.0)

        # Consistency: variance of line lengths (lower = more consistent)
        lines = [l for l in text.split("\n") if l.strip()]
        if lines:
            line_lengths = [len(l) for l in lines]
            avg_len = sum(line_lengths) / len(line_lengths)
            variance = sum((l - avg_len) ** 2 for l in line_lengths) / len(line_lengths)
            consistency = 1.0 / (1.0 + variance / 1000)
        else:
            consistency = 0.0

        # Weighted combination
        score = (
            0.30 * length_score
            + 0.25 * arabic_ratio
            + 0.25 * word_score
            + 0.20 * consistency
        )
        return score

    # ------------------------------------------------------------------
    # Glossary extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_glossary(
        text: str,
        source: str = "unknown",
    ) -> list[dict[str, str]]:
        """
        استخراج المسارد الثنائية اللغة من النص.

        يبحث عن أنماط:
        - العربية = English
        - العربية - English
        - العربية : English
        - العربية\tEnglish

        Returns:
            قائمة قواميس: [{"term_arabic": "...", "term_english": "...", "source": "..."}]
        """
        entries: list[dict[str, str]] = []
        seen = set()

        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) < 3:
                continue

            for pattern in GLOSSARY_PATTERNS:
                match = pattern.match(line)
                if match:
                    left = match.group(1).strip()
                    right = match.group(2).strip()

                    # Determine which is Arabic and which is English
                    has_arabic_left = bool(re.search(r'[\u0600-\u06FF]', left))
                    has_arabic_right = bool(re.search(r'[\u0600-\u06FF]', right))
                    has_english_left = bool(re.search(r'[a-zA-Z]', left))
                    has_english_right = bool(re.search(r'[a-zA-Z]', right))

                    # Must have one Arabic and one English
                    if has_arabic_left and has_english_right:
                        term_ar, term_en = left, right
                    elif has_arabic_right and has_english_left:
                        term_ar, term_en = right, left
                    elif has_arabic_left and has_arabic_right:
                        # Both Arabic — skip
                        continue
                    else:
                        continue

                    # Clean up
                    term_ar = re.sub(r'^[\s\-=:]+|[\s\-=:]+$', '', term_ar)
                    term_en = re.sub(r'^[\s\-=:]+|[\s\-=:]+$', '', term_en)

                    # Minimum length
                    if len(term_ar) < 2 or len(term_en) < 2:
                        continue

                    # Deduplicate
                    key = (term_ar, term_en)
                    if key not in seen:
                        seen.add(key)
                        entries.append({
                            "term_arabic": term_ar,
                            "term_english": term_en,
                            "source": source,
                        })

                    break  # Don't match same line with multiple patterns

        return entries

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    def _save_text(self, text: str, stem: str) -> Path:
        """حفظ النص المستخرج كملف TXT."""
        path = self.output_dir / f"{stem}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.debug(f"تم حفظ النص: {path}")
        return path

    def _save_csv(self, entries: list[dict[str, str]], stem: str) -> Path:
        """حفظ المسارد كملف CSV."""
        # Only save entries from this file
        file_entries = [e for e in entries if e.get("source", "").startswith(stem)]
        if not file_entries:
            file_entries = entries  # fallback

        path = self.output_dir / f"{stem}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["term_arabic", "term_english", "source"])
            writer.writeheader()
            writer.writerows(file_entries)
        logger.debug(f"تم حفظ المسارد: {path} ({len(file_entries)} مُدخلة)")
        return path

    def _save_json(
        self,
        file_result: dict[str, Any],
        text: str,
        stem: str,
    ) -> Path:
        """حفظ النتيجة الكاملة كملف JSON."""
        path = self.output_dir / f"{stem}.json"
        output = {
            **file_result,
            "extracted_text": text,
            "glossary_entries": [
                e for e in self.combined_glossary
                if e.get("source", "").startswith(stem)
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        logger.debug(f"تم حفظ JSON: {path}")
        return path

    def _save_combined_glossary(self) -> None:
        """حفظ المسارد الموحدة لجميع الملفات."""
        # CSV
        csv_path = self.output_dir / "combined_glossary.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["term_arabic", "term_english", "source"])
            writer.writeheader()
            writer.writerows(self.combined_glossary)
        logger.info(f"مسرد موحد CSV: {csv_path} ({len(self.combined_glossary)} مُدخلة)")

        # JSON
        json_path = self.output_dir / "combined_glossary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.combined_glossary, f, ensure_ascii=False, indent=2)
        logger.info(f"مسرد موحد JSON: {json_path}")

    def generate_processing_log(self) -> Path:
        """إنشاء تقرير معالجة Markdown."""
        log_path = self.output_dir / "OCR_PROCESSING_LOG.md"
        lines = [
            "# سجل معالجة OCR",
            f"\n**التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**الإعداد المستخدم:** PSM={self.best_config.get('psm')}, "
            f"DPI={self.best_config.get('dpi')}, "
            f"lang={self.best_config.get('language')}",
            f"**المعالجة المسبقة:** {'scanner_fixer' if self.normalize_images and _HAS_SCANNER_FIXER else 'معطّلة'}",
            "",
            "## الملفات المعالجة",
            "",
            "| الملف | الصفحات | المسارد | الوقت (ث) | الحالة |",
            "|---|---|---|---|---|",
        ]
        for r in self.results:
            status = "✅" if not r.get("error") else f"❌ {r['error'][:30]}"
            lines.append(
                f"| {r.get('file', '?')} | {r.get('pages', 0)} | "
                f"{r.get('entries_found', 0)} | {r.get('processing_time_seconds', 0):.1f} | {status} |"
            )

        lines.extend([
            "",
            "## إجمالي المسارد",
            f"- **إجمالي المُدخلات:** {len(self.combined_glossary)}",
            f"- **ملفات PDF:** {len(self.results)}",
        ])

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"تقرير المعالجة: {log_path}")
        return log_path


# ===========================================================================
# CLI
# ===========================================================================
def main() -> None:
    """نقطة الدخول الرئيسية لمعالج PDF OCR."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PDF OCR Processor — معالج PDF OCR مع ضبط تلقائي واستخراج مسارد",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
أمثلة:
  %(prog)s                                    # معالجة كل PDF في data/
  %(prog)s --input report.pdf                 # ملف واحد
  %(prog)s --input ./pdfs/ --auto-tune        # مع ضبط تلقائي
  %(prog)s --input report.pdf --no-normalize  # بدون معالجة مسبقة
        """,
    )
    parser.add_argument(
        "--input", "-i",
        default="data/",
        help="مسار ملف PDF أو مجلد (افتراضي: data/)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="مجلد الإخراج (افتراضي: ~/glossaries_output)",
    )
    parser.add_argument(
        "--language", "-l",
        default="ara+eng",
        help="لغة OCR (افتراضي: ara+eng)",
    )
    parser.add_argument(
        "--no-auto-tune",
        action="store_true",
        help="تعطيل الضبط التلقائي",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="تعطيل المعالجة المسبقة للصور",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=None,
        help="PSM mode يدوي (3, 4, 6, 11)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=None,
        help="DPI يدوي (200, 300, 400)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="تسجيل مفصّل",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Check dependencies
    print("═══════════════════════════════════════════════════")
    print("  PDF OCR Processor — معالج PDF OCR الطبي")
    print("═══════════════════════════════════════════════════")
    print()

    checks = [
        ("Tesseract OCR", _HAS_TESSERACT),
        ("PDF Library (PyMuPDF/pdf2image)", _HAS_FITZ or _HAS_PDF2IMAGE),
        ("scanner_fixer", _HAS_SCANNER_FIXER),
        ("pandas", _HAS_PANDAS),
        ("Advanced Logger", _ADVANCED_LOGGER_AVAILABLE),
    ]
    for name, available in checks:
        status = "✅" if available else "⚠️ غير متاح"
        print(f"  {name}: {status}")
    print()

    # Create processor
    processor = PDFOCRProcessor(
        output_dir=args.output,
        language=args.language,
        auto_tune=not args.no_auto_tune,
        normalize_images=not args.no_normalize,
    )

    # Override config if manual
    if args.psm is not None:
        processor.best_config["psm"] = args.psm
        processor.auto_tune = False
    if args.dpi is not None:
        processor.best_config["dpi"] = args.dpi

    # Process
    input_path = Path(args.input)

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        result = processor.process_pdf(input_path)
        results = [result]
    elif input_path.is_dir():
        results = processor.process_directory(input_path)
    else:
        print(f"❌ المسار غير صالح: {input_path}")
        print("   استخدم: --input <file.pdf> أو --input <directory/>")
        sys.exit(1)

    # Generate log
    processor.generate_processing_log()

    # Summary
    print()
    print("═══════════════════════════════════════════════════")
    print("  ✅ اكتملت المعالجة!")
    print("═══════════════════════════════════════════════════")
    print(f"  📁 الإخراج: {processor.output_dir}")
    print(f"  📄 ملفات PDF: {len(results)}")
    print(f"  📖 مسارد: {len(processor.combined_glossary)} مُدخلة")
    print(f"  ⚙️  الإعداد: PSM={processor.best_config['psm']}, DPI={processor.best_config['dpi']}")
    print()
    print("  الملفات:")
    for p in sorted(processor.output_dir.iterdir())[:20]:
        if p.is_file():
            size = p.stat().st_size
            print(f"    {p.name} ({size:,} bytes)")


if __name__ == "__main__":
    main()
