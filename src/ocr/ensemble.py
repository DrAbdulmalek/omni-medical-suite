"""
OCR Ensemble - تجميع محركات التعرف الضوئي
=============================================

This module orchestrates multiple OCR engines (PaddleOCR, EasyOCR,
Tesseract, Surya) and provides ensemble strategies for improved
text extraction from Arabic medical documents.

هذه الوحدة تنسق بين عدة محركات OCR (PaddleOCR و EasyOCR
و Tesseract و Surya) وتوفر استراتيجيات تجميع لتحسين
استخراج النص من المستندات الطبية العربية.
"""

import logging
import subprocess
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "جارٍ تهيئة مجموعة محركات OCR | Initializing OCR engine ensemble"
_MSG_COUNT = "تم تحميل {n} من {total} محرك | Loaded {n} of {total} engines"
_MSG_RUN_ALL = "تشغيل جميع المحركات المتاحة | Running all available engines"
_MSG_ENSEMBLE = "جارٍ اختيار أفضل نص من التجميع | Selecting best text from ensemble"
_MSG_WEIGHTED = "جارٍ حساب النص المرجح بالثقة | Computing confidence-weighted text"
_MSG_COMPARISON = "جارٍ إنشاء جدول المقارنة | Generating comparison table"
_MSG_ENGINE_OK = "تم تحميل المحرك: {name} | Engine loaded: {name}"
_MSG_ENGINE_SKIP = "تخطي المحرك: {name} - {reason} | Skipping engine: {name} - {reason}"
_MSG_TESSERACT_CHECK = "التحقق من توفر Tesseract | Checking Tesseract availability"
_MSG_TESSERECT_FAIL = "Tesseract غير متاح | Tesseract not available"


class OCREnsemble:
    """
    Ensemble OCR orchestrator that manages multiple engines and
    provides strategies for combining their results.

    منسق تجميع OCR يدير عدة محركات ويوفر استراتيجيات لدمج نتائجها.

    Supported engines:
        - paddleocr: Best for printed Arabic text with optimized params
        - easyocr: Good multilingual support
        - tesseract: Fast and reliable baseline
        - surya: Advanced layout analysis with OCR

    المحركات المدعومة:
        - paddleocr: الأفضل للنصوص العربية المطبوعة
        - easyocr: دعم جيد متعدد اللغات
        - tesseract: سريع وموثوق كخط أساس
        - surya: تحليل تخطيط متقدم مع OCR
    """

    def __init__(self) -> None:
        """
        Initialize all available OCR engines.

        تهيئة جميع محركات OCR المتاحة.

        Each engine is loaded in a try/except block. Engines that
        are not installed or fail to initialize are skipped gracefully.
        """
        logger.info(_MSG_INIT)

        self.engines: dict[str, Any] = {}
        total_expected = 4  # paddle, easyocr, tesseract, surya

        # --- PaddleOCR ---
        try:
            from src.ocr.paddle_engine import PaddleOCREngine

            self.engines["paddleocr"] = PaddleOCREngine(
                lang="ar",
                use_gpu=True,
            )
            if self.engines["paddleocr"].is_available:
                logger.info(_MSG_ENGINE_OK.format(name="paddleocr"))
            else:
                del self.engines["paddleocr"]
                logger.warning(
                    _MSG_ENGINE_SKIP.format(
                        name="paddleocr", reason="not available after init"
                    )
                )
        except Exception as e:
            logger.debug(
                _MSG_ENGINE_SKIP.format(name="paddleocr", reason=str(e))
            )

        # --- EasyOCR ---
        try:
            from src.ocr.easyocr_engine import EasyOCREngine

            self.engines["easyocr"] = EasyOCREngine(
                languages=["ar", "en"],
                gpu=True,
            )
            if self.engines["easyocr"].is_available:
                logger.info(_MSG_ENGINE_OK.format(name="easyocr"))
            else:
                del self.engines["easyocr"]
                logger.warning(
                    _MSG_ENGINE_SKIP.format(
                        name="easyocr", reason="not available after init"
                    )
                )
        except Exception as e:
            logger.debug(
                _MSG_ENGINE_SKIP.format(name="easyocr", reason=str(e))
            )

        # --- Tesseract ---
        try:
            tesseract_available = self._check_tesseract()
            if tesseract_available:
                self.engines["tesseract"] = _TesseractAdapter()
                logger.info(_MSG_ENGINE_OK.format(name="tesseract"))
            else:
                logger.debug(
                    _MSG_ENGINE_SKIP.format(
                        name="tesseract", reason="binary not found"
                    )
                )
        except Exception as e:
            logger.debug(
                _MSG_ENGINE_SKIP.format(name="tesseract", reason=str(e))
            )

        # --- Surya ---
        try:
            from src.layout.surya_analyzer import SuryaLayoutAnalyzer

            analyzer = SuryaLayoutAnalyzer()
            if analyzer.is_available:
                self.engines["surya"] = _SuryaOCRExtractor(analyzer)
                logger.info(_MSG_ENGINE_OK.format(name="surya"))
            else:
                logger.debug(
                    _MSG_ENGINE_SKIP.format(
                        name="surya", reason="not available after init"
                    )
                )
        except Exception as e:
            logger.debug(
                _MSG_ENGINE_SKIP.format(name="surya", reason=str(e))
            )

        loaded = len(self.engines)
        logger.info(_MSG_COUNT.format(n=loaded, total=total_expected))

        if loaded == 0:
            logger.error(
                "لم يتم تحميل أي محرك! | No engines loaded! "
                "تثبيت paddleocr أو easyocr على الأقل | "
                "Install at least paddleocr or easyocr"
            )

    @property
    def available_engines(self) -> list[str]:
        """Return list of loaded engine names."""
        return list(self.engines.keys())

    def run_all(self, image: np.ndarray) -> dict[str, Any]:
        """
        Run all available OCR engines on an image and return combined results.

        تشغيل جميع محركات OCR المتاحة على صورة وإرجاع النتائج المجمعة.

        Args:
            image: Input image as numpy array.

        Returns:
            Dictionary with:
                - results (Dict[str, Dict]): Per-engine results
                - num_engines (int): Number of engines that ran
                - engines_used (List[str]): Names of engines used
        """
        logger.info(_MSG_RUN_ALL)

        all_results: dict[str, dict] = {}

        for name, engine in self.engines.items():
            try:
                logger.debug(
                    f"تشغيل: {name} | Running: {name}"
                )
                if hasattr(engine, "extract_text"):
                    result = engine.extract_text(image)
                elif hasattr(engine, "analyze"):
                    # Surya adapter
                    result = engine.extract_text(image)
                else:
                    continue

                all_results[name] = result
                lines_count = result.get("num_lines", 0)
                text_len = len(result.get("text", result.get("full_text", "")))
                logger.debug(
                    f"{name}: {lines_count} سطر، {text_len} حرف "
                    f"| {name}: {lines_count} lines, {text_len} chars"
                )

            except Exception as e:
                logger.error(
                    f"خطأ في {name}: {e} | Error in {name}: {e}",
                    exc_info=True,
                )
                all_results[name] = {
                    "text": "",
                    "full_text": "",
                    "lines": [],
                    "num_lines": 0,
                    "engine": name,
                    "error": str(e),
                }

        return {
            "results": all_results,
            "num_engines": len(all_results),
            "engines_used": list(all_results.keys()),
        }

    def get_ensemble_text(self, image: np.ndarray) -> str:
        """
        Get the best text using a simple longest-result heuristic.

        الحصول على أفضل نص باستخدام بسيط: الأطول هو الأفضل.

        The heuristic selects the result with the most non-whitespace
        characters, which tends to favor engines that captured more text.

        Args:
            image: Input image as numpy array.

        Returns:
            Best text string from the ensemble.
        """
        logger.info(_MSG_ENSEMBLE)

        all_results = self.run_all(image)

        best_text = ""
        best_len = 0
        best_engine = ""

        for name, result in all_results["results"].items():
            # Get text from either 'text' or 'full_text' key
            text = result.get("text", result.get("full_text", ""))
            clean_len = len(text.strip())

            if clean_len > best_len:
                best_len = clean_len
                best_text = text
                best_engine = name

        logger.info(
            f"أفضل نتيجة من: {best_engine} ({best_len} حرف) "
            f"| Best result from: {best_engine} ({best_len} chars)"
        )
        return best_text

    def get_confidence_weighted_text(
        self, image: np.ndarray
    ) -> str:
        """
        Get text weighted by confidence scores across engines.

        الحصول على النص المرجح بدرجات الثقة عبر المحركات.

        Strategy:
            1. Collect all lines from all engines
            2. Group similar lines (by position overlap or text similarity)
            3. For each group, select the line with highest average confidence
            4. Merge selected lines into final text

        Currently implements a simplified version that picks the engine
        with the highest average confidence per line.

        Args:
            image: Input image as numpy array.

        Returns:
            Confidence-weighted text string.
        """
        logger.info(_MSG_WEIGHTED)

        all_results = self.run_all(image)

        # Collect all lines with their engine and confidence
        engine_lines: dict[str, list[dict]] = {}

        for name, result in all_results["results"].items():
            lines = result.get("lines", [])
            if lines:
                engine_lines[name] = lines

        if not engine_lines:
            return ""

        # Find engine with highest average confidence
        best_engine = ""
        best_avg_conf = -1.0

        for name, lines in engine_lines.items():
            if not lines:
                continue

            total_conf = sum(line.get("confidence", 0.0) for line in lines)
            avg_conf = total_conf / len(lines)

            if avg_conf > best_avg_conf:
                best_avg_conf = avg_conf
                best_engine = name

        if best_engine and best_engine in all_results["results"]:
            text = all_results["results"][best_engine].get(
                "text",
                all_results["results"][best_engine].get("full_text", ""),
            )
            logger.info(
                f"المحرك الأعلى ثقة: {best_engine} "
                f"(متوسط الثقة: {best_avg_conf:.3f}) "
                f"| Highest confidence engine: {best_engine} "
                f"(avg confidence: {best_avg_conf:.3f})"
            )
            return text

        return ""

    def get_comparison_table(self, image: np.ndarray) -> str:
        """
        Generate a formatted comparison table of all engine results.

        إنشاء جدول مقارنة منسق لنتائج جميع المحركات.

        Args:
            image: Input image as numpy array.

        Returns:
            Formatted string table comparing engines.
        """
        logger.info(_MSG_COMPARISON)

        all_results = self.run_all(image)
        separator = "=" * 80

        lines: list[str] = [
            separator,
            f"{'جدول مقارنة محركات OCR | OCR Engine Comparison Table':^80}",
            separator,
            "",
            f"{'المحرك | Engine':<18} "
            f"{'الأسطر | Lines':>12} "
            f"{'الأحرف | Chars':>12} "
            f"{'متوسط الثقة | Avg Conf':>16} "
            f"{'الحالة | Status':>12}",
            "-" * 80,
        ]

        for name, result in all_results["results"].items():
            num_lines = result.get("num_lines", 0)
            text = result.get("text", result.get("full_text", ""))
            char_count = len(text.strip())
            error = result.get("error", None)

            # Calculate average confidence
            result_lines = result.get("lines", [])
            if result_lines:
                avg_conf = sum(
                    l.get("confidence", 0.0) for l in result_lines
                ) / len(result_lines)
            else:
                avg_conf = 0.0

            status = "✓" if not error else "✗"
            conf_str = f"{avg_conf:.3f}" if result_lines else "N/A"

            lines.append(
                f"{name:<18} "
                f"{num_lines:>12} "
                f"{char_count:>12} "
                f"{conf_str:>16} "
                f"{status:>12}"
            )

        lines.append("-" * 80)
        lines.append(f"المحركات المستخدمة: {all_results['num_engines']}")
        lines.append(f"Engines used: {all_results['num_engines']}")
        lines.append(separator)

        # Append text previews
        lines.append("")
        lines.append("معاينة النصوص | Text Previews:")
        lines.append("-" * 80)

        for name, result in all_results["results"].items():
            text = result.get("text", result.get("full_text", ""))
            preview = text.strip()[:120] + ("..." if len(text.strip()) > 120 else "")
            lines.append(f"\n[{name}]:")
            lines.append(f"  {preview}")

        lines.append(separator)

        return "\n".join(lines)

    @staticmethod
    def _check_tesseract() -> bool:
        """
        Check if Tesseract OCR binary is available on the system.

        التحقق من توفر ثنائية Tesseract على النظام.

        Returns:
            True if tesseract is found in PATH, False otherwise.
        """
        logger.debug(_MSG_TESSERACT_CHECK)
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                timeout=5,
            )
            available = result.returncode == 0
            if not available:
                logger.debug(_MSG_TESSERECT_FAIL)
            return available
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug(_MSG_TESSERECT_FAIL)
            return False


class _TesseractAdapter:
    """
    Minimal adapter for Tesseract OCR via subprocess.

    محول بسيط لـ Tesseract عبر العمليات الفرعية.
    """

    def __init__(self) -> None:
        """Initialize Tesseract adapter with pytesseract if available."""
        self._available = False
        try:
            import pytesseract  # type: ignore
            self.pytesseract = pytesseract
            self._available = True
        except ImportError:
            logger.debug(
                "pytesseract غير متاح | pytesseract not available"
            )

    @property
    def is_available(self) -> bool:
        return self._available

    def extract_text(self, image: np.ndarray) -> dict[str, Any]:
        """Extract text using Tesseract."""
        try:
            # Ensure RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                b_avg = float(np.mean(image[:, :, 0]))
                r_avg = float(np.mean(image[:, :, 2]))
                if b_avg > r_avg * 1.15:
                    image = image[:, :, ::-1]

            # Run OCR with Arabic + English
            data = self.pytesseract.image_to_data(
                image,
                lang="ara+eng",
                output_type=self.pytesseract.Output.DICT,
            )

            lines: list[dict] = []
            current_line: list[dict] = []
            current_line_num = -1

            for i in range(len(data["text"])):
                line_num = data["line_num"][i]
                text = data["text"][i].strip()
                conf = int(data["conf"][i]) / 100.0

                if conf <= 0:
                    continue

                if line_num != current_line_num:
                    if current_line:
                        merged = self._merge_line(current_line)
                        lines.append(merged)
                    current_line = []
                    current_line_num = line_num

                current_line.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "confidence": conf,
                })

            if current_line:
                merged = self._merge_line(current_line)
                lines.append(merged)

            full_text = "\n".join(l["text"] for l in lines if l["text"])

            return {
                "text": full_text,
                "lines": lines,
                "num_lines": len(lines),
                "engine": "tesseract",
            }

        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            return {"text": "", "lines": [], "num_lines": 0, "engine": "tesseract"}

    @staticmethod
    def _merge_line(words: list[dict]) -> dict:
        """Merge word-level results into a line result."""
        if not words:
            return {"text": "", "bbox": [], "confidence": 0.0}

        texts = [w["text"] for w in words]
        merged_text = " ".join(texts)
        avg_conf = sum(w["confidence"] for w in words) / len(words)

        min_x = min(w["x"] for w in words)
        min_y = min(w["y"] for w in words)
        max_x = max(w["x"] + w["w"] for w in words)
        max_y = max(w["y"] + w["h"] for w in words)

        return {
            "text": merged_text,
            "bbox": [[min_x, min_y], [max_x, min_y],
                     [max_x, max_y], [min_x, max_y]],
            "confidence": round(avg_conf, 4),
        }


class _SuryaOCRExtractor:
    """
    Adapter to use SuryaLayoutAnalyzer as an OCR engine.

    محول لاستخدام SuryaLayoutAnalyzer كمحرك OCR.
    """

    def __init__(self, analyzer) -> None:
        self._analyzer = analyzer

    @property
    def is_available(self) -> bool:
        return self._analyzer.is_available

    def extract_text(self, image: np.ndarray) -> dict[str, Any]:
        """Extract text using Surya."""
        result = self._analyzer.analyze(image)
        # Normalize keys to match other engines
        return {
            "text": result.get("full_text", ""),
            "full_text": result.get("full_text", ""),
            "lines": result.get("lines", []),
            "num_lines": result.get("num_lines", 0),
            "engine": "surya",
        }
