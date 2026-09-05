# src/ml/ocr_tuner.py
"""
Self-tuner for image-preprocessing parameters used upstream of OCR.

Tries combinations of:
  * CLAHE clipLimit
  * Adaptive threshold block size
  * Adaptive threshold constant
  * Denoise strength (h parameter of fastNlMeansDenoising)

Scoring:
  * If ``ground_truth`` text is provided, score = fraction of ground-truth
    words that appear in the extracted text (word-level recall).
  * Otherwise, score = min(extracted_word_count / 50, 1.0) — a simple
    proxy that rewards extracting more (and longer-than-1-char) words.

The search is reproducible: ``random.Random(42)`` picks a stable subset
of the grid when ``max_trials < total combinations``.
"""
from __future__ import annotations

import itertools
import random
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np


class OCRTuner:
    """Grid-search tuner for medical-image preprocessing parameters."""

    def __init__(
        self,
        image_path: str | Path,
        ground_truth: Optional[str] = None,
    ) -> None:
        self.image_path = Path(image_path)
        self.ground_truth = ground_truth

        self.original = cv2.imread(str(self.image_path), cv2.IMREAD_GRAYSCALE)
        if self.original is None:
            raise ValueError(f"Cannot read image: {self.image_path}")

        self.best_params: Optional[Dict] = None
        self.best_score = -1.0

    # ── Image pipeline (parameterised) ─────────────────────────────────

    def _apply_params(self, params: Dict) -> np.ndarray:
        img = self.original.copy()
        img = cv2.fastNlMeansDenoising(
            img,
            None,
            h=params["denoise_h"],
            templateWindowSize=7,
            searchWindowSize=21,
        )
        clahe = cv2.createCLAHE(
            clipLimit=params["clip_limit"],
            tileGridSize=(8, 8),
        )
        img = clahe.apply(img)
        block_size = params["block_size"]
        if block_size % 2 == 0:
            block_size += 1
        img = cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            params["constant"],
        )
        return img

    # ── Scoring ────────────────────────────────────────────────────────

    def _score_text(self, text: str) -> float:
        words = [w for w in text.split() if len(w) > 1]
        if self.ground_truth:
            ground_words = set(self.ground_truth.split())
            extracted_words = set(words)
            if not ground_words:
                return 0.0
            intersection = ground_words.intersection(extracted_words)
            return len(intersection) / len(ground_words)
        return min(len(words) / 50.0, 1.0)

    def _evaluate(self, params: Dict) -> float:
        img = self._apply_params(params)
        try:
            import pytesseract

            text = pytesseract.image_to_string(
                img,
                lang="ara+eng",
                config="--oem 3 --psm 6",
            )
        except Exception:
            return 0.0
        return self._score_text(text)

    # ── Public API ─────────────────────────────────────────────────────

    def tune(self, max_trials: int = 12) -> Dict:
        grid = {
            "clip_limit": [1.5, 2.5, 3.5],
            "block_size": [11, 21, 31],
            "constant": [2, 5, 10],
            "denoise_h": [5, 10, 20],
        }
        keys = list(grid.keys())
        combinations = list(itertools.product(*grid.values()))
        rng = random.Random(42)
        if len(combinations) > max_trials:
            combinations = rng.sample(combinations, max_trials)

        for combination in combinations:
            params = dict(zip(keys, combination))
            score = self._evaluate(params)
            if score > self.best_score:
                self.best_score = score
                self.best_params = params
        return self.best_params or {}

    def get_optimized_image(self) -> np.ndarray:
        if not self.best_params:
            raise RuntimeError("You must call tune() before get_optimized_image()")
        return self._apply_params(self.best_params)
