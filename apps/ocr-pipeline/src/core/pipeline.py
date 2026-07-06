"""
Core Pipeline — OmniMedicalOCR Orchestrator
============================================

Central class that coordinates image preprocessing, multi-engine OCR,
result fusion via weighted voting, Arabic spell checking, and medical
dictionary corrections.

Designed for medical-grade reliability, full Arabic RTL support, and
production deployment.
"""

from __future__ import annotations

import concurrent.futures
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from config.settings import PipelineConfig, EngineName, SpellCheckStrategy
from src.utils.logger import get_logger, timed

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Axis-aligned bounding box ``(x_min, y_min, x_max, y_max)``."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def iou(self, other: "BBox") -> float:
        """Intersection-over-Union with another BBox."""
        xi1 = max(self.x_min, other.x_min)
        yi1 = max(self.y_min, other.y_min)
        xi2 = min(self.x_max, other.x_max)
        yi2 = min(self.y_max, other.y_max)

        inter = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
        area_a = (self.x_max - self.x_min) * (self.y_max - self.y_min)
        area_b = (other.x_max - other.x_min) * (other.y_max - other.y_min)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0


@dataclass
class EngineResult:
    """Raw result from a single OCR engine for one line/region."""
    text: str
    confidence: float
    engine: str
    bbox: Optional[BBox] = None


@dataclass
class PipelineResult:
    """
    Structured output of :meth:`OmniMedicalOCR.process_image`.

    Attributes
    ----------
    text:
        Final corrected full text (lines joined by ``\\n``).
    lines:
        Per-line details including source engines and confidence.
    overall_confidence:
        Mean confidence of all kept lines.
    engines_used:
        List of engine names that contributed results.
    preprocessing_applied:
        Names of preprocessing steps that were executed.
    spell_corrections:
        Mapping of ``original_word -> corrected_word``.
    elapsed_seconds:
        Total wall-clock time for the pipeline call.
    """
    text: str
    lines: List[LineResult]
    overall_confidence: float
    engines_used: List[str]
    preprocessing_applied: List[str]
    spell_corrections: Dict[str, str]
    elapsed_seconds: float


@dataclass
class LineResult:
    """Result for a single text line / region."""
    text: str
    confidence: float
    engine_sources: Dict[str, float]  # engine -> its confidence
    bbox: Optional[BBox] = None


# ---------------------------------------------------------------------------
# Helper: HybridSpellChecker (stub / fallback implementation)
# ---------------------------------------------------------------------------

class HybridSpellChecker:
    """
    Arabic spell checker that combines:
    1. A curated medical dictionary (exact-match)
    2. Edit-distance lookup against a general Arabic word list
    3. (Optional) LLM fallback for very low-confidence words

    This class is designed to be swappable.  A heavier NLP-based
    implementation can replace it without changing the pipeline.
    """

    def __init__(
        self,
        medical_dict_path: Optional[str] = None,
        arabic_dict_path: Optional[str] = None,
        max_edit_distance: int = 2,
        min_word_length: int = 3,
        llm_fallback: bool = False,
    ) -> None:
        self._medical_words: set[str] = set()
        self._arabic_words: set[str] = set()
        self._max_edit = max_edit_distance
        self._min_len = min_word_length
        self._llm_fallback = llm_fallback

        self._load_dictionaries(medical_dict_path, arabic_dict_path)

    # ---- dictionary loading ------------------------------------------------

    def _load_dictionaries(
        self,
        medical_path: Optional[str],
        arabic_path: Optional[str],
    ) -> None:
        """Load word lists from disk (one word per line, UTF-8)."""
        for path, target in [
            (medical_path, self._medical_words),
            (arabic_path, self._arabic_words),
        ]:
            if path is None:
                continue
            p = Path(path)
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                word = line.strip()
                if word:
                    target.add(word)

    # ---- public API --------------------------------------------------------

    def correct_word(self, word: str) -> tuple[str, bool]:
        """
        Attempt to correct a single Arabic/medical word.

        Returns
        -------
        (corrected_word, was_corrected)
        """
        if len(word) < self._min_len:
            return word, False

        # 1) Exact match in medical dictionary — always trusted
        if word in self._medical_words:
            return word, False

        # 2) Exact match in general Arabic dictionary
        if word in self._arabic_words:
            return word, False

        # 3) Edit-distance search (medical dict first, then general)
        candidate = self._best_edit_distance_candidate(word, self._medical_words)
        if candidate is None:
            candidate = self._best_edit_distance_candidate(word, self._arabic_words)

        if candidate is not None:
            return candidate, True

        # 4) LLM fallback placeholder — logged but not yet wired
        if self._llm_fallback:
            # In a full implementation this would call an Arabic LLM.
            # For now we pass through and log.
            pass

        return word, False

    def correct_text(self, text: str) -> tuple[str, Dict[str, str]]:
        """
        Correct all words in *text*, returning the corrected text and
        a mapping of ``original -> corrected`` for each change.
        """
        corrections: Dict[str, str] = {}
        words = text.split()
        corrected: list[str] = []

        for w in words:
            cw, changed = self.correct_word(w)
            if changed:
                corrections[w] = cw
            corrected.append(cw)

        return " ".join(corrected), corrections

    # ---- internals ---------------------------------------------------------

    def _best_edit_distance_candidate(
        self, word: str, dictionary: set[str],
    ) -> Optional[str]:
        """Return the closest word within *max_edit_distance*, or None."""
        try:
            from Levenshtein import distance as lev_dist
        except ImportError:
            # Pure-python fallback (slower but dependency-free)
            def lev_dist(a: str, b: str) -> int:
                if len(a) < len(b):
                    a, b = b, a
                if not b:
                    return len(a)
                prev = list(range(len(b) + 1))
                for i, ca in enumerate(a, 1):
                    curr = [i]
                    for j, cb in enumerate(b, 1):
                        cost = 0 if ca == cb else 1
                        curr.append(min(prev[j] + 1, curr[j - 1] + 1,
                                        prev[j - 1] + cost))
                    prev = curr
                return prev[-1]

        best_word: Optional[str] = None
        best_dist = self._max_edit + 1

        for candidate in dictionary:
            d = lev_dist(word, candidate)
            if d < best_dist:
                best_dist = d
                best_word = candidate

        return best_word


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------

class OmniMedicalOCR:
    """
    Multi-engine Arabic medical OCR pipeline.

    Combines Tesseract, EasyOCR, PaddleOCR, and TrOCR with weighted
    voting fusion, Arabic spell checking, and medical dictionary
    corrections.

    Parameters
    ----------
    config:
        :class:`PipelineConfig` instance.  Use ``PipelineConfig()`` for
        sensible defaults, or load from YAML/JSON.

    Examples
    --------
    >>> pipeline = OmniMedicalOCR()
    >>> result = pipeline.process_image("prescription.png")
    >>> print(result.text)
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config: PipelineConfig = config or PipelineConfig()
        self.logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # Engine instances (lazy-loaded)
        self._engines: Dict[str, Any] = {}
        self._spell_checker: Optional[HybridSpellChecker] = None

        self.logger.info("OmniMedicalOCR v0.1.0 initialising …")
        self.logger.info("Enabled engines: %s", self.config.enabled_engines)
        self._init_engines()
        self._init_spell_checker()

    # ======================================================================
    # Initialisation helpers
    # ======================================================================

    def _init_engines(self) -> None:
        """Instantiate each enabled OCR engine."""
        cfg = self.config
        model = cfg.model

        for engine_name in cfg.enabled_engines:
            try:
                if engine_name == EngineName.TESSERACT.value:
                    self._init_tesseract(model)
                elif engine_name == EngineName.EASYOCR.value:
                    self._init_easyocr(model)
                elif engine_name == EngineName.PADDLEOCR.value:
                    self._init_paddleocr(model)
                elif engine_name == EngineName.TROCR.value:
                    self._init_trocr(model)
                else:
                    self.logger.warning("Unknown engine '%s' — skipping.", engine_name)
            except Exception as exc:
                self.logger.error(
                    "Failed to initialise engine '%s': %s", engine_name, exc,
                    exc_info=True,
                )

    def _init_tesseract(self, model_cfg: Any) -> None:
        """Initialise the Tesseract OCR engine."""
        import pytesseract
        if model_cfg.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = model_cfg.tesseract_cmd
        # Verify installation
        pytesseract.get_tesseract_version()
        self._engines[EngineName.TESSERACT.value] = pytesseract
        self.logger.info("Tesseract initialised (lang=%s)", model_cfg.tesseract_lang)

    def _init_easyocr(self, model_cfg: Any) -> None:
        """Initialise the EasyOCR engine."""
        import easyocr
        reader = easyocr.Reader(
            model_cfg.easyocr_lang,
            gpu=model_cfg.easyocr_gpu,
            model_storage_directory=model_cfg.easyocr_model_storage,
        )
        self._engines[EngineName.EASYOCR.value] = reader
        self.logger.info("EasyOCR initialised (langs=%s)", model_cfg.easyocr_lang)

    def _init_paddleocr(self, model_cfg: Any) -> None:
        """Initialise the PaddleOCR engine."""
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang=model_cfg.paddleocr_lang,
            use_gpu=model_cfg.paddleocr_use_gpu,
            det_model_dir=model_cfg.paddleocr_det_model_dir,
            rec_model_dir=model_cfg.paddleocr_rec_model_dir,
            cls_model_dir=model_cfg.paddleocr_cls_model_dir,
            show_log=False,
        )
        self._engines[EngineName.PADDLEOCR.value] = ocr
        self.logger.info("PaddleOCR initialised (lang=%s)", model_cfg.paddleocr_lang)

    def _init_trocr(self, model_cfg: Any) -> None:
        """Initialise the TrOCR (Transformer OCR) engine."""
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        device = model_cfg.trocr_use_fp16 and model_cfg.device == "cuda"
        torch_dtype = "float16" if device else "auto"

        processor = TrOCRProcessor.from_pretrained(model_cfg.trocr_processor_name)
        model_obj = VisionEncoderDecoderModel.from_pretrained(
            model_cfg.trocr_model_name, torch_dtype=torch_dtype,
        ).to(model_cfg.device)

        self._engines[EngineName.TROCR.value] = {
            "processor": processor,
            "model": model_obj,
            "device": model_cfg.device,
        }
        self.logger.info("TrOCR initialised (model=%s, device=%s)",
                         model_cfg.trocr_model_name, model_cfg.device)

    def _init_spell_checker(self) -> None:
        """Set up the hybrid spell checker with configured dictionaries."""
        strategy = self.config.spell_check_strategy
        if strategy == SpellCheckStrategy.NONE.value:
            self.logger.info("Spell checking disabled.")
            return

        self._spell_checker = HybridSpellChecker(
            medical_dict_path=self.config.model.medical_dictionary_path,
            arabic_dict_path=self.config.model.arabic_dictionary_path,
            max_edit_distance=self.config.spell_check_max_edit_distance,
            min_word_length=self.config.spell_check_min_word_length,
            llm_fallback=(strategy == SpellCheckStrategy.LLM_FALLBACK.value),
        )
        self.logger.info("Spell checker initialised (strategy=%s)", strategy)

    # ======================================================================
    # Image preprocessing
    # ======================================================================

    @timed()
    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """
        Apply the full preprocessing chain as defined in config.

        Returns
        -------
        (processed_image, list_of_applied_step_names)
        """
        cfg = self.config.preprocessing
        applied: List[str] = []

        img = image.copy()

        # Grayscale
        if cfg.to_grayscale and img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            applied.append("grayscale")

        # Resize to target DPI approximation
        h, w = img.shape[:2]
        max_dim = max(h, w)
        if max_dim > cfg.max_dimension:
            scale = cfg.max_dimension / max_dim
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_AREA)
            applied.append("resize_down")
        elif max_dim < cfg.min_dimension and max_dim > 0:
            scale = cfg.min_dimension / max_dim
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_CUBIC)
            applied.append("resize_up")

        # Denoise
        if cfg.denoise:
            if img.ndim == 2:
                img = cv2.fastNlMeansDenoising(img, None, h=cfg.denoise_h)
            else:
                img = cv2.fastNlMeansDenoisingColored(img, None, h=cfg.denoise_h)
            applied.append("denoise")

        # CLAHE contrast enhancement
        if cfg.enhance_contrast:
            clahe = cv2.createCLAHE(
                clipLimit=cfg.clahe_clip_limit,
                tileGridSize=cfg.clahe_grid_size,
            )
            if img.ndim == 2:
                img = clahe.apply(img)
            else:
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            applied.append("clahe")

        # Binarisation (optional)
        if cfg.binarize:
            if cfg.binarize_threshold == 0:
                _, img = cv2.threshold(img, 0, 255,
                                       cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                _, img = cv2.threshold(img, cfg.binarize_threshold, 255,
                                       cv2.THRESH_BINARY)
            applied.append("binarize")

        # Deskew
        if cfg.deskew:
            img = self._deskew(img)
            applied.append("deskew")

        return img, applied

    @staticmethod
    def _deskew(image: np.ndarray, sigma: float = 3.0) -> np.ndarray:
        """
        Estimate and correct the skew angle of a document image
        using a Hough-transform / min-area-rect approach.
        """
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Threshold
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        # Dilate to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image

        # Pick the largest contour by area
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        largest = contours[0]

        # Minimum area rectangle gives the angle
        rect = cv2.minAreaRect(largest)
        angle = rect[-1]

        # Normalise to [-45, 45]
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle

        # Skip tiny angles
        if abs(angle) < 0.3:
            return image

        (h, w) = image.shape[:2]
        centre = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(centre, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated

    # ======================================================================
    # Per-engine OCR runners
    # ======================================================================

    def _run_tesseract(self, image: np.ndarray) -> List[EngineResult]:
        """Run Tesseract and return normalised results."""
        pytesseract = self._engines[EngineName.TESSERACT.value]
        lang = self.config.model.tesseract_lang

        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        results: List[EngineResult] = []
        for i, txt in enumerate(data["text"]):
            txt = txt.strip()
            if not txt:
                continue
            conf = float(data["conf"][i]) / 100.0
            if conf < 0:
                conf = 0.0
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            results.append(EngineResult(
                text=txt,
                confidence=conf,
                engine=EngineName.TESSERACT.value,
                bbox=BBox(x, y, x + w, y + h),
            ))
        return results

    def _run_easyocr(self, image: np.ndarray) -> List[EngineResult]:
        """Run EasyOCR and return normalised results."""
        reader = self._engines[EngineName.EASYOCR.value]
        # EasyOCR expects RGB
        if image.ndim == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        detections = reader.readtext(rgb)

        results: List[EngineResult] = []
        for (bbox_pts, txt, conf) in detections:
            xs = [p[0] for p in bbox_pts]
            ys = [p[1] for p in bbox_pts]
            results.append(EngineResult(
                text=txt.strip(),
                confidence=float(conf),
                engine=EngineName.EASYOCR.value,
                bbox=BBox(min(xs), min(ys), max(xs), max(ys)),
            ))
        return results

    def _run_paddleocr(self, image: np.ndarray) -> List[EngineResult]:
        """Run PaddleOCR and return normalised results."""
        ocr = self._engines[EngineName.PADDLEOCR.value]
        # PaddleOCR expects BGR numpy array
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image

        result = ocr.ocr(bgr, cls=True)

        results: List[EngineResult] = []
        if result is None:
            return results
        for page in result:
            if page is None:
                continue
            for line in page:
                bbox_pts, (txt, conf) = line[0], line[1]
                xs = [p[0] for p in bbox_pts]
                ys = [p[1] for p in bbox_pts]
                results.append(EngineResult(
                    text=txt.strip(),
                    confidence=float(conf),
                    engine=EngineName.PADDLEOCR.value,
                    bbox=BBox(min(xs), min(ys), max(xs), max(ys)),
                ))
        return results

    def _run_trocr(self, image: np.ndarray) -> List[EngineResult]:
        """Run TrOCR and return normalised results."""
        engine = self._engines[EngineName.TROCR.value]
        processor = engine["processor"]
        model = engine["model"]
        device = engine["device"]

        # Convert to PIL RGB
        if image.ndim == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        import torch
        pixel_values = processor(pil_img, return_tensors="pt").pixel_values.to(device)

        with torch.no_grad():
            generated_ids = model.generate(pixel_values)

        generated_text = processor.batch_decode(
            generated_ids, skip_special_tokens=True,
        )[0].strip()

        # TrOCR produces a single block of text (no per-line bboxes)
        return [EngineResult(
            text=generated_text,
            confidence=1.0,  # TrOCR does not expose per-token confidence
            engine=EngineName.TROCR.value,
            bbox=None,
        )]

    # ======================================================================
    # Result fusion (weighted voting)
    # ======================================================================

    def _run_engine(
        self, engine_name: str, image: np.ndarray,
    ) -> List[EngineResult]:
        """Dispatch to the correct per-engine runner."""
        if engine_name == EngineName.TESSERACT.value:
            return self._run_tesseract(image)
        if engine_name == EngineName.EASYOCR.value:
            return self._run_easyocr(image)
        if engine_name == EngineName.PADDLEOCR.value:
            return self._run_paddleocr(image)
        if engine_name == EngineName.TROCR.value:
            return self._run_trocr(image)
        raise ValueError(f"Unknown engine: {engine_name}")

    def _merge_results(
        self, all_results: Dict[str, List[EngineResult]],
    ) -> List[LineResult]:
        """
        Merge results from multiple engines using weighted voting.

        Strategy:
        1. Cluster overlapping bounding boxes (IoU ≥ threshold).
        2. For each cluster, pick the text with the highest weighted
           confidence score.
        3. Lines without bboxes (e.g. TrOCR full-page) are treated as
           supplemental and blended separately.
        """
        cfg = self.config
        weights = cfg.engine_weights
        iou_threshold = cfg.merge_iou_threshold
        min_conf = cfg.min_confidence

        # Flatten all results that have bounding boxes
        bounded: List[EngineResult] = []
        unbounded: List[EngineResult] = []

        for engine_name, results in all_results.items():
            for r in results:
                if r.bbox is not None:
                    bounded.append(r)
                else:
                    unbounded.append(r)

        # Greedy clustering by IoU
        clusters: List[List[EngineResult]] = []
        used: set[int] = set()

        for i, r in enumerate(bounded):
            if i in used:
                continue
            cluster = [r]
            used.add(i)
            for j in range(i + 1, len(bounded)):
                if j in used:
                    continue
                # If any member overlaps with candidate, merge
                for member in cluster:
                    if member.bbox is not None and bounded[j].bbox is not None:
                        if member.bbox.iou(bounded[j].bbox) >= iou_threshold:
                            cluster.append(bounded[j])
                            used.add(j)
                            break
            clusters.append(cluster)

        # For each cluster, select best text by weighted confidence
        lines: List[LineResult] = []

        for cluster in clusters:
            best: Optional[EngineResult] = None
            best_score = -1.0
            sources: Dict[str, float] = {}

            for r in cluster:
                w = weights.get(r.engine, 0.25)
                score = r.confidence * w
                sources[r.engine] = max(sources.get(r.engine, 0.0), r.confidence)

                if score > best_score:
                    best_score = score
                    best = r

            if best is not None and best.confidence >= min_conf:
                lines.append(LineResult(
                    text=best.text,
                    confidence=best_score,
                    engine_sources=sources,
                    bbox=best.bbox,
                ))

        # Sort lines by vertical position (top-to-bottom reading order)
        lines.sort(key=lambda l: l.bbox.y_min if l.bbox else 0)

        # If there are unbounded results (e.g. TrOCR) and no bounded
        # results were found, use the unbounded text as a fallback.
        if not lines and unbounded:
            for r in unbounded:
                # Split by newlines into per-line results
                for part in r.text.splitlines():
                    part = part.strip()
                    if part:
                        w = weights.get(r.engine, 0.25)
                        lines.append(LineResult(
                            text=part,
                            confidence=r.confidence * w,
                            engine_sources={r.engine: r.confidence},
                            bbox=None,
                        ))

        return lines

    # ======================================================================
    # Public API
    # ======================================================================

    @timed()
    def process_image(self, image_path: str | Path) -> PipelineResult:
        """
        Run the full OCR pipeline on a single image.

        Steps:
        1. Load & preprocess image
        2. Run all enabled engines in parallel
        3. Merge results via weighted voting
        4. Apply spell checking & medical corrections
        5. Return structured result

        Parameters
        ----------
        image_path:
            Path to the input image (PNG, JPG, TIFF, BMP, etc.).

        Returns
        -------
        PipelineResult
        """
        t0 = time.perf_counter()
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        self.logger.info("Processing image: %s", image_path.name)

        # 1. Load image
        raw = cv2.imread(str(image_path))
        if raw is None:
            raise IOError(f"OpenCV could not read image: {image_path}")

        # 2. Preprocess
        processed, prep_steps = self._preprocess(raw)

        # 3. Run engines in parallel
        all_results: Dict[str, List[EngineResult]] = {}
        engines_to_run = [e for e in self.config.enabled_engines
                          if e in self._engines]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(engines_to_run), self.config.max_workers),
        ) as pool:
            future_to_engine = {
                pool.submit(self._run_engine, name, processed): name
                for name in engines_to_run
            }
            for future in concurrent.futures.as_completed(future_to_engine):
                engine_name = future_to_engine[future]
                try:
                    results = future.result()
                    all_results[engine_name] = results
                    self.logger.debug(
                        "Engine %s returned %d results", engine_name, len(results),
                    )
                except Exception as exc:
                    self.logger.error(
                        "Engine %s failed: %s", engine_name, exc, exc_info=True,
                    )

        # 4. Merge
        merged_lines = self._merge_results(all_results)

        # 5. Spell check
        all_corrections: Dict[str, str] = {}
        if self._spell_checker is not None:
            for line in merged_lines:
                corrected_text, corr = self._spell_checker.correct_text(line.text)
                line.text = corrected_text
                all_corrections.update(corr)

        # 6. Compute overall confidence
        if merged_lines:
            overall_conf = sum(l.confidence for l in merged_lines) / len(merged_lines)
        else:
            overall_conf = 0.0

        final_text = "\n".join(l.text for l in merged_lines)

        elapsed = time.perf_counter() - t0
        self.logger.info(
            "Pipeline completed: %d lines, %.1f%% confidence, %.2f s",
            len(merged_lines), overall_conf * 100, elapsed,
        )

        return PipelineResult(
            text=final_text,
            lines=merged_lines,
            overall_confidence=overall_conf,
            engines_used=list(all_results.keys()),
            preprocessing_applied=prep_steps,
            spell_corrections=all_corrections,
            elapsed_seconds=elapsed,
        )

    def process_batch(
        self,
        image_paths: Sequence[str | Path],
        progress_callback: Optional[callable] = None,
    ) -> List[PipelineResult]:
        """
        Process a batch of images sequentially (with per-engine
        parallelism internally).

        Parameters
        ----------
        image_paths:
            Iterable of file paths.
        progress_callback:
            Optional ``callback(index, total, result)`` invoked after
            each image is processed.

        Returns
        -------
        List[PipelineResult]
            One result per input image, in the same order.
        """
        total = len(image_paths)
        self.logger.info("Batch processing %d images …", total)
        results: List[PipelineResult] = []

        for idx, path in enumerate(image_paths):
            result = self.process_image(path)
            results.append(result)
            if progress_callback is not None:
                progress_callback(idx, total, result)

        self.logger.info("Batch complete: %d/%d succeeded.", len(results), total)
        return results

    def process_pdf(
        self,
        pdf_path: str | Path,
        progress_callback: Optional[callable] = None,
    ) -> List[PipelineResult]:
        """
        Convert each page of a PDF to an image and run the pipeline.

        Uses ``PyMuPDF`` (fitz) internally for fast PDF-to-image
        conversion without external poppler dependency.

        Parameters
        ----------
        pdf_path:
            Path to the PDF file.
        progress_callback:
            Optional ``callback(page_num, total_pages, result)``.

        Returns
        -------
        List[PipelineResult]
            One result per PDF page.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self.logger.info("Processing PDF: %s", pdf_path.name)

        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        first = self.config.pdf_first_page or 1
        last = self.config.pdf_last_page or len(doc)
        total_pages = last - first + 1

        results: List[PipelineResult] = []
        dpi = self.config.pdf_dpi
        zoom = dpi / 72.0  # fitz default is 72 dpi

        for page_idx in range(first - 1, min(last, len(doc))):
            page = doc[page_idx]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Write to a temporary file and process
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                pix.save(str(tmp_path))

            try:
                result = self.process_image(tmp_path)
                results.append(result)
                if progress_callback is not None:
                    progress_callback(page_idx + 1, total_pages, result)
            finally:
                tmp_path.unlink(missing_ok=True)

        doc.close()
        self.logger.info("PDF complete: %d pages processed.", len(results))
        return results

    # ======================================================================
    # Lifecycle
    # ======================================================================

    def close(self) -> None:
        """Release resources held by OCR engines."""
        for name, engine in self._engines.items():
            try:
                if name == EngineName.TROCR.value and isinstance(engine, dict):
                    import torch
                    model = engine["model"]
                    del model
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                # EasyOCR / PaddleOCR don't have explicit close methods
            except Exception as exc:
                self.logger.warning("Error releasing %s: %s", name, exc)
        self._engines.clear()
        self.logger.info("Resources released.")

    def __enter__(self) -> "OmniMedicalOCR":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()