#!/usr/bin/env python3
"""
ocr_snippet_trainer.py — Interactive OCR Snippet Learning System
=================================================================
Converts OCR images into text snippets, allows user correction,
and learns from corrections to improve future OCR accuracy.

Architecture:
    Image → Segmentation → OCR per snippet → User Review →
    Correction Store → Pattern Learning → Auto-Correction

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import re
import os
import sqlite3
import hashlib
import pickle
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Any, Callable
from datetime import datetime
import logging
from collections import defaultdict

# Optional imports with graceful fallback
try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    print("WARNING: OpenCV not available. Image processing disabled.")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_UI = True
except ImportError:
    ARABIC_UI = False

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# Data Models
# ============================================================

@dataclass
class TextSnippet:
    """Represents a single text region (snippet) from an image."""
    id: str
    image_path: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    ocr_text: str
    corrected_text: str = ""
    confidence: float = 0.0
    engine: str = "unknown"
    is_reviewed: bool = False
    is_correct: bool = False
    correction_type: str = ""  # "spelling", "formatting", "omission", "insertion"
    user_id: str = "anonymous"
    created_at: str = ""
    corrected_at: str = ""
    image_hash: str = ""
    snippet_hash: str = ""  # hash of bbox + image_hash
    context_before: str = ""
    context_after: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.corrected_text:
            self.corrected_text = self.ocr_text
        if not self.snippet_hash:
            self.snippet_hash = self._compute_snippet_hash()

    def _compute_snippet_hash(self) -> str:
        """Compute unique hash for this snippet."""
        data = f"{self.image_hash}:{self.bbox}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "TextSnippet":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CorrectionPattern:
    """A learned pattern from user corrections."""
    id: str
    original_pattern: str
    corrected_pattern: str
    pattern_type: str  # "exact", "regex", "context", "visual"
    frequency: int = 1
    confidence_score: float = 0.5
    first_seen: str = ""
    last_seen: str = ""
    source_snippets: List[str] = None
    context_examples: List[str] = None
    is_auto_promoted: bool = False
    promotion_threshold: float = 0.85

    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat()
        if not self.last_seen:
            self.last_seen = self.first_seen
        if self.source_snippets is None:
            self.source_snippets = []
        if self.context_examples is None:
            self.context_examples = []

    def update(self, snippet_id: str, context: str = ""):
        """Update pattern with new observation."""
        self.frequency += 1
        self.last_seen = datetime.now().isoformat()
        if snippet_id not in self.source_snippets:
            self.source_snippets.append(snippet_id)
        if context and len(self.context_examples) < 10:
            self.context_examples.append(context)
        # Update confidence based on frequency
        self.confidence_score = min(0.99, 0.5 + (self.frequency - 1) * 0.05)
        if self.confidence_score >= self.promotion_threshold:
            self.is_auto_promoted = True

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# Database Manager
# ============================================================

class SnippetDatabase:
    """SQLite-backed storage for snippets, corrections, and patterns."""

    def __init__(self, db_path: str = "ocr_snippets.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snippets (
                id TEXT PRIMARY KEY,
                image_path TEXT,
                bbox TEXT,
                ocr_text TEXT,
                corrected_text TEXT,
                confidence REAL,
                engine TEXT,
                is_reviewed INTEGER DEFAULT 0,
                is_correct INTEGER DEFAULT 0,
                correction_type TEXT,
                user_id TEXT,
                created_at TEXT,
                corrected_at TEXT,
                image_hash TEXT,
                snippet_hash TEXT UNIQUE,
                context_before TEXT,
                context_after TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                original_pattern TEXT,
                corrected_pattern TEXT,
                pattern_type TEXT,
                frequency INTEGER DEFAULT 1,
                confidence_score REAL DEFAULT 0.5,
                first_seen TEXT,
                last_seen TEXT,
                source_snippets TEXT,
                context_examples TEXT,
                is_auto_promoted INTEGER DEFAULT 0,
                promotion_threshold REAL DEFAULT 0.85
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                snippet_id TEXT,
                pattern_id TEXT,
                details TEXT
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snippet_hash ON snippets(snippet_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_hash ON snippets(image_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_original ON patterns(original_pattern)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_promoted ON patterns(is_auto_promoted)")

        self.conn.commit()

    def save_snippet(self, snippet: TextSnippet) -> bool:
        """Save or update a snippet."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO snippets VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                snippet.id, snippet.image_path, str(snippet.bbox),
                snippet.ocr_text, snippet.corrected_text,
                snippet.confidence, snippet.engine,
                int(snippet.is_reviewed), int(snippet.is_correct),
                snippet.correction_type, snippet.user_id,
                snippet.created_at, snippet.corrected_at,
                snippet.image_hash, snippet.snippet_hash,
                snippet.context_before, snippet.context_after
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save snippet: {e}")
            return False

    def get_snippet(self, snippet_id: str) -> Optional[TextSnippet]:
        """Retrieve a snippet by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data['bbox'] = eval(data['bbox'])
            data['is_reviewed'] = bool(data['is_reviewed'])
            data['is_correct'] = bool(data['is_correct'])
            return TextSnippet.from_dict(data)
        return None

    def get_snippets_by_image(self, image_hash: str) -> List[TextSnippet]:
        """Get all snippets for an image."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM snippets WHERE image_hash = ? ORDER BY created_at", (image_hash,))
        snippets = []
        for row in cursor.fetchall():
            data = dict(row)
            data['bbox'] = eval(data['bbox'])
            data['is_reviewed'] = bool(data['is_reviewed'])
            data['is_correct'] = bool(data['is_correct'])
            snippets.append(TextSnippet.from_dict(data))
        return snippets

    def get_unreviewed_snippets(self, limit: int = 50) -> List[TextSnippet]:
        """Get snippets pending review."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM snippets 
            WHERE is_reviewed = 0 
            ORDER BY confidence ASC 
            LIMIT ?
        """, (limit,))
        snippets = []
        for row in cursor.fetchall():
            data = dict(row)
            data['bbox'] = eval(data['bbox'])
            data['is_reviewed'] = bool(data['is_reviewed'])
            data['is_correct'] = bool(data['is_correct'])
            snippets.append(TextSnippet.from_dict(data))
        return snippets

    def save_pattern(self, pattern: CorrectionPattern) -> bool:
        """Save or update a learned pattern."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO patterns VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                pattern.id, pattern.original_pattern, pattern.corrected_pattern,
                pattern.pattern_type, pattern.frequency, pattern.confidence_score,
                pattern.first_seen, pattern.last_seen,
                json.dumps(pattern.source_snippets),
                json.dumps(pattern.context_examples),
                int(pattern.is_auto_promoted), pattern.promotion_threshold
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save pattern: {e}")
            return False

    def get_pattern(self, original: str, pattern_type: str = "exact") -> Optional[CorrectionPattern]:
        """Find a pattern by original text."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM patterns 
            WHERE original_pattern = ? AND pattern_type = ?
        """, (original, pattern_type))
        row = cursor.fetchone()
        if row:
            return self._row_to_pattern(row)
        return None

    def get_all_patterns(self, promoted_only: bool = False) -> List[CorrectionPattern]:
        """Get all patterns, optionally only auto-promoted ones."""
        cursor = self.conn.cursor()
        if promoted_only:
            cursor.execute("SELECT * FROM patterns WHERE is_auto_promoted = 1 ORDER BY frequency DESC")
        else:
            cursor.execute("SELECT * FROM patterns ORDER BY frequency DESC")
        return [self._row_to_pattern(row) for row in cursor.fetchall()]

    def _row_to_pattern(self, row) -> CorrectionPattern:
        data = dict(row)
        data['source_snippets'] = json.loads(data.get('source_snippets', '[]'))
        data['context_examples'] = json.loads(data.get('context_examples', '[]'))
        data['is_auto_promoted'] = bool(data['is_auto_promoted'])
        return CorrectionPattern(**{k: v for k, v in data.items() if k in CorrectionPattern.__dataclass_fields__})

    def log_event(self, event_type: str, snippet_id: str = "", pattern_id: str = "", details: str = ""):
        """Log a learning event."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO learning_log (timestamp, event_type, snippet_id, pattern_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), event_type, snippet_id, pattern_id, details))
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Get database statistics."""
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute("SELECT COUNT(*) FROM snippets")
        stats['total_snippets'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM snippets WHERE is_reviewed = 1")
        stats['reviewed_snippets'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM snippets WHERE is_correct = 1")
        stats['correct_snippets'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM patterns")
        stats['total_patterns'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM patterns WHERE is_auto_promoted = 1")
        stats['promoted_patterns'] = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(confidence) FROM snippets WHERE is_reviewed = 1")
        avg = cursor.fetchone()[0]
        stats['avg_confidence_after_review'] = round(avg, 3) if avg else 0

        return stats

    def close(self):
        self.conn.close()


# ============================================================
# Image Segmenter
# ============================================================

class ImageSegmenter:
    """Segments document images into text regions (snippets)."""

    def __init__(self):
        if not CV_AVAILABLE:
            raise RuntimeError("OpenCV required for image segmentation")

    def segment(self, image_path: str, 
                method: str = "contour",
                min_area: int = 500,
                padding: int = 5) -> List[Dict]:
        """
        Segment image into text regions.

        Args:
            image_path: Path to image file
            method: "contour" (default), "projection", or "line"
            min_area: Minimum contour area
            padding: Padding around detected regions

        Returns:
            List of dicts with 'bbox' (x,y,w,h) and 'image_crop_path'
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        if method == "contour":
            return self._segment_by_contour(img, image_path, min_area, padding)
        elif method == "projection":
            return self._segment_by_projection(img, image_path, padding)
        elif method == "line":
            return self._segment_by_lines(img, image_path, padding)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _segment_by_contour(self, img: np.ndarray, image_path: str, 
                            min_area: int, padding: int) -> List[Dict]:
        """Segment using contour detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Adaptive threshold for Arabic text
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 10
        )

        # Morphological operations to connect nearby text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        base_name = Path(image_path).stem
        output_dir = Path(image_path).parent / "snippets"
        output_dir.mkdir(exist_ok=True)

        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Add padding
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(img.shape[1] - x, w + 2 * padding)
            h = min(img.shape[0] - y, h + 2 * padding)

            # Aspect ratio filter (reject very thin/tall regions)
            aspect = w / h if h > 0 else 0
            if aspect < 0.05 or aspect > 20:
                continue

            # Save crop
            crop = img[y:y+h, x:x+w]
            crop_path = output_dir / f"{base_name}_snippet_{i:03d}.png"
            cv2.imwrite(str(crop_path), crop)

            regions.append({
                'bbox': (x, y, w, h),
                'image_crop_path': str(crop_path),
                'area': area,
                'aspect_ratio': aspect
            })

        # Sort top-to-bottom, left-to-right (for RTL Arabic: right-to-left)
        regions.sort(key=lambda r: (r['bbox'][1], -r['bbox'][0]))

        return regions

    def _segment_by_projection(self, img: np.ndarray, image_path: str, 
                             padding: int) -> List[Dict]:
        """Segment using horizontal projection (for line-based text)."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Horizontal projection
        h_proj = np.sum(binary, axis=1)

        # Find text lines
        threshold = np.mean(h_proj) * 0.1
        in_line = False
        line_start = 0
        lines = []

        for i, val in enumerate(h_proj):
            if val > threshold and not in_line:
                in_line = True
                line_start = i
            elif val <= threshold and in_line:
                in_line = False
                lines.append((line_start, i))

        regions = []
        base_name = Path(image_path).stem
        output_dir = Path(image_path).parent / "snippets"
        output_dir.mkdir(exist_ok=True)

        for i, (y1, y2) in enumerate(lines):
            y1 = max(0, y1 - padding)
            y2 = min(img.shape[0], y2 + padding)

            crop = img[y1:y2, :]
            crop_path = output_dir / f"{base_name}_line_{i:03d}.png"
            cv2.imwrite(str(crop_path), crop)

            regions.append({
                'bbox': (0, y1, img.shape[1], y2 - y1),
                'image_crop_path': str(crop_path),
                'area': (y2 - y1) * img.shape[1],
                'aspect_ratio': img.shape[1] / (y2 - y1)
            })

        return regions

    def _segment_by_lines(self, img: np.ndarray, image_path: str, 
                          padding: int) -> List[Dict]:
        """Segment into individual text lines using improved method."""
        return self._segment_by_projection(img, image_path, padding)


# ============================================================
# OCR Engine Wrapper
# ============================================================

class OCREngine:
    """Wrapper for multiple OCR engines with Arabic support."""

    def __init__(self, preferred_engine: str = "auto"):
        self.preferred = preferred_engine
        self.engines = {}
        self._init_engines()

    def _init_engines(self):
        """Initialize available OCR engines."""
        # Try EasyOCR
        try:
            import easyocr
            self.engines['easyocr'] = easyocr.Reader(['ar', 'en'], gpu=False)
            logger.info("EasyOCR initialized (ar+en)")
        except ImportError:
            pass

        # Try Tesseract
        try:
            import pytesseract
            self.engines['tesseract'] = pytesseract
            logger.info("Tesseract initialized")
        except ImportError:
            pass

        # Try PaddleOCR
        try:
            from paddleocr import PaddleOCR
            self.engines['paddleocr'] = PaddleOCR(
                use_angle_cls=True,
                lang='ar',
                show_log=False
            )
            logger.info("PaddleOCR initialized (ar)")
        except ImportError:
            pass

        if not self.engines:
            logger.warning("No OCR engines available!")

    def recognize(self, image_path: str, engine: str = "auto") -> Dict:
        """
        Run OCR on an image.

        Returns:
            Dict with 'text', 'confidence', 'engine', 'boxes'
        """
        if engine == "auto":
            engine = self._select_engine(image_path)

        if engine not in self.engines:
            available = list(self.engines.keys())
            engine = available[0] if available else None

        if not engine:
            return {"text": "", "confidence": 0, "engine": "none", "boxes": []}

        if engine == 'easyocr':
            return self._run_easyocr(image_path)
        elif engine == 'tesseract':
            return self._run_tesseract(image_path)
        elif engine == 'paddleocr':
            return self._run_paddleocr(image_path)

        return {"text": "", "confidence": 0, "engine": "unknown", "boxes": []}

    def _select_engine(self, image_path: str) -> str:
        """Select best engine based on image characteristics."""
        # Prefer PaddleOCR for Arabic printed text
        if 'paddleocr' in self.engines:
            return 'paddleocr'
        if 'easyocr' in self.engines:
            return 'easyocr'
        return 'tesseract'

    def _run_easyocr(self, image_path: str) -> Dict:
        reader = self.engines['easyocr']
        results = reader.readtext(image_path, detail=1)

        texts = []
        confidences = []
        boxes = []

        for (bbox, text, conf) in results:
            texts.append(text)
            confidences.append(conf)
            boxes.append(bbox)

        full_text = ' '.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "text": full_text,
            "confidence": round(avg_conf, 3),
            "engine": "easyocr",
            "boxes": boxes
        }

    def _run_tesseract(self, image_path: str) -> Dict:
        pytesseract = self.engines['tesseract']

        # Get data with bounding boxes
        data = pytesseract.image_to_data(
            image_path, lang='ara+eng',
            output_type=pytesseract.Output.DICT
        )

        texts = []
        confidences = []
        boxes = []

        for i in range(len(data['text'])):
            if int(data['conf'][i]) > 0:
                texts.append(data['text'][i])
                confidences.append(int(data['conf'][i]) / 100)
                boxes.append((
                    data['left'][i], data['top'][i],
                    data['width'][i], data['height'][i]
                ))

        full_text = ' '.join(t for t in texts if t.strip())
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "text": full_text,
            "confidence": round(avg_conf, 3),
            "engine": "tesseract",
            "boxes": boxes
        }

    def _run_paddleocr(self, image_path: str) -> Dict:
        ocr = self.engines['paddleocr']
        result = ocr.ocr(image_path, cls=True)

        texts = []
        confidences = []
        boxes = []

        if result and result[0]:
            for line in result[0]:
                bbox, (text, conf) = line
                texts.append(text)
                confidences.append(conf)
                boxes.append(bbox)

        full_text = ' '.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return {
            "text": full_text,
            "confidence": round(avg_conf, 3),
            "engine": "paddleocr",
            "boxes": boxes
        }


# ============================================================
# Pattern Learner
# ============================================================

class PatternLearner:
    """Learns correction patterns from user feedback."""

    def __init__(self, db: SnippetDatabase):
        self.db = db
        self.pattern_cache = {}
        self._load_patterns()

    def _load_patterns(self):
        """Load promoted patterns into cache."""
        patterns = self.db.get_all_patterns(promoted_only=True)
        for p in patterns:
            self.pattern_cache[p.original_pattern] = p

    def learn_from_correction(self, snippet: TextSnippet) -> List[CorrectionPattern]:
        """
        Learn patterns from a user-corrected snippet.

        Returns:
            List of new/updated patterns
        """
        if snippet.ocr_text == snippet.corrected_text:
            return []

        patterns = []

        # Pattern 1: Exact word substitution
        ocr_words = snippet.ocr_text.split()
        corr_words = snippet.corrected_text.split()

        for ow, cw in zip(ocr_words, corr_words):
            if ow != cw:
                p = self._create_or_update_pattern(
                    original=ow,
                    corrected=cw,
                    pattern_type="exact",
                    snippet_id=snippet.id,
                    context=snippet.ocr_text
                )
                patterns.append(p)

        # Pattern 2: Phrase-level (multi-word)
        if len(ocr_words) >= 2 and len(corr_words) >= 2:
            for n in range(2, min(5, len(ocr_words) + 1)):
                for i in range(len(ocr_words) - n + 1):
                    ocr_phrase = ' '.join(ocr_words[i:i+n])
                    if i < len(corr_words) - n + 1:
                        corr_phrase = ' '.join(corr_words[i:i+n])
                        if ocr_phrase != corr_phrase:
                            p = self._create_or_update_pattern(
                                original=ocr_phrase,
                                corrected=corr_phrase,
                                pattern_type="phrase",
                                snippet_id=snippet.id,
                                context=snippet.ocr_text
                            )
                            patterns.append(p)

        # Pattern 3: Character-level (for single character errors)
        if len(ocr_words) == len(corr_words):
            for ow, cw in zip(ocr_words, corr_words):
                if len(ow) == len(cw) and sum(a != b for a, b in zip(ow, cw)) == 1:
                    # Single character substitution
                    for a, b in zip(ow, cw):
                        if a != b:
                            p = self._create_or_update_pattern(
                                original=a,
                                corrected=b,
                                pattern_type="char",
                                snippet_id=snippet.id,
                                context=f"{ow} → {cw}"
                            )
                            patterns.append(p)

        # Log learning event
        self.db.log_event(
            "pattern_learned",
            snippet_id=snippet.id,
            details=f"Learned {len(patterns)} patterns from correction"
        )

        return patterns

    def _create_or_update_pattern(self, original: str, corrected: str,
                                   pattern_type: str, snippet_id: str,
                                   context: str) -> CorrectionPattern:
        """Create new or update existing pattern."""
        existing = self.db.get_pattern(original, pattern_type)

        if existing:
            existing.update(snippet_id, context)
            self.db.save_pattern(existing)
            self.pattern_cache[original] = existing
            return existing

        pattern_id = hashlib.sha256(f"{original}:{corrected}:{pattern_type}".encode()).hexdigest()[:16]
        pattern = CorrectionPattern(
            id=pattern_id,
            original_pattern=original,
            corrected_pattern=corrected,
            pattern_type=pattern_type,
            source_snippets=[snippet_id],
            context_examples=[context]
        )
        self.db.save_pattern(pattern)
        self.pattern_cache[original] = pattern
        return pattern

    def apply_learned_patterns(self, text: str, min_confidence: float = 0.7) -> Tuple[str, List[Dict]]:
        """
        Apply learned patterns to new OCR text.

        Returns:
            (corrected_text, applied_corrections)
        """
        corrections = []
        corrected = text

        # Sort patterns by length (longest first) to avoid partial replacements
        sorted_patterns = sorted(
            self.pattern_cache.values(),
            key=lambda p: len(p.original_pattern),
            reverse=True
        )

        for pattern in sorted_patterns:
            if pattern.confidence_score < min_confidence:
                continue

            if pattern.original_pattern in corrected:
                count = corrected.count(pattern.original_pattern)
                corrected = corrected.replace(
                    pattern.original_pattern,
                    pattern.corrected_pattern
                )
                corrections.append({
                    "pattern_id": pattern.id,
                    "original": pattern.original_pattern,
                    "corrected": pattern.corrected_pattern,
                    "type": pattern.pattern_type,
                    "confidence": pattern.confidence_score,
                    "frequency": pattern.frequency,
                    "count": count
                })

        return corrected, corrections

    def get_suggestions(self, text: str, max_suggestions: int = 5) -> List[Dict]:
        """Get correction suggestions for a text."""
        suggestions = []
        words = text.split()

        for word in words:
            for pattern in self.pattern_cache.values():
                if pattern.original_pattern in word:
                    suggestions.append({
                        "word": word,
                        "suggestion": word.replace(
                            pattern.original_pattern,
                            pattern.corrected_pattern
                        ),
                        "confidence": pattern.confidence_score,
                        "frequency": pattern.frequency
                    })

        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:max_suggestions]


# ============================================================
# Main Trainer Class
# ============================================================

class OCRSnippetTrainer:
    """
    Main class for interactive OCR snippet training.

    Usage:
        trainer = OCRSnippetTrainer()

        # Process new image
        snippets = trainer.process_image("document.jpg")

        # User reviews and corrects
        for snippet in snippets:
            trainer.submit_correction(snippet.id, "corrected text")

        # Apply learning to new text
        corrected = trainer.auto_correct(new_ocr_text)
    """

    def __init__(self, db_path: str = "ocr_snippets.db",
                 dictionary_path: Optional[str] = None):
        self.db = SnippetDatabase(db_path)
        self.segmenter = ImageSegmenter() if CV_AVAILABLE else None
        self.ocr = OCREngine()
        self.learner = PatternLearner(self.db)
        self.dictionary_path = dictionary_path

        # Load medical dictionary if available
        self.medical_dict = {}
        if dictionary_path and os.path.exists(dictionary_path):
            with open(dictionary_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.medical_dict = data.get("corrections", {})

    def process_image(self, image_path: str,
                      segmentation_method: str = "contour",
                      engine: str = "auto") -> List[TextSnippet]:
        """
        Process an image: segment → OCR → create snippets.

        Returns:
            List of TextSnippet objects ready for review
        """
        image_path = str(Path(image_path).resolve())

        # Compute image hash
        if PIL_AVAILABLE:
            with open(image_path, 'rb') as f:
                image_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        else:
            image_hash = hashlib.sha256(image_path.encode()).hexdigest()[:16]

        # Check if already processed
        existing = self.db.get_snippets_by_image(image_hash)
        if existing:
            logger.info(f"Image already processed. Returning {len(existing)} existing snippets.")
            return existing

        # Segment image
        if not self.segmenter:
            # Fallback: treat entire image as one snippet
            regions = [{
                'bbox': (0, 0, 0, 0),
                'image_crop_path': image_path,
                'area': 0,
                'aspect_ratio': 1.0
            }]
        else:
            regions = self.segmenter.segment(image_path, method=segmentation_method)

        logger.info(f"Segmented into {len(regions)} regions")

        # OCR each region
        snippets = []
        for i, region in enumerate(regions):
            ocr_result = self.ocr.recognize(region['image_crop_path'], engine=engine)

            # Get context from neighboring regions
            context_before = snippets[-1].ocr_text if snippets else ""
            context_after = ""

            snippet = TextSnippet(
                id=f"{image_hash}_{i:04d}",
                image_path=image_path,
                bbox=region['bbox'],
                ocr_text=ocr_result['text'],
                corrected_text=ocr_result['text'],
                confidence=ocr_result['confidence'],
                engine=ocr_result['engine'],
                image_hash=image_hash,
                context_before=context_before,
                context_after=context_after
            )

            # Apply medical dictionary pre-correction
            if self.medical_dict:
                snippet.corrected_text = self._apply_dictionary(snippet.ocr_text)

            # Apply learned patterns
            auto_corrected, patterns = self.learner.apply_learned_patterns(
                snippet.corrected_text
            )
            if patterns:
                snippet.corrected_text = auto_corrected
                logger.info(f"Applied {len(patterns)} learned patterns to snippet {snippet.id}")

            self.db.save_snippet(snippet)
            snippets.append(snippet)

            # Update context_after for previous snippet
            if i > 0:
                snippets[i-1].context_after = snippet.ocr_text
                self.db.save_snippet(snippets[i-1])

        self.db.log_event("image_processed", details=f"Created {len(snippets)} snippets")
        return snippets

    def _apply_dictionary(self, text: str) -> str:
        """Apply medical dictionary corrections."""
        corrected = text
        for wrong, correct in self.medical_dict.items():
            corrected = corrected.replace(wrong, correct)
        return corrected

    def submit_correction(self, snippet_id: str, corrected_text: str,
                          user_id: str = "anonymous",
                          correction_type: str = "") -> Dict:
        """
        Submit a user correction for a snippet.

        Returns:
            Dict with learning results
        """
        snippet = self.db.get_snippet(snippet_id)
        if not snippet:
            return {"error": "Snippet not found"}

        # Update snippet
        snippet.corrected_text = corrected_text
        snippet.is_reviewed = True
        snippet.is_correct = (snippet.ocr_text == corrected_text)
        snippet.user_id = user_id
        snippet.corrected_at = datetime.now().isoformat()

        if not correction_type:
            correction_type = self._detect_correction_type(snippet.ocr_text, corrected_text)
        snippet.correction_type = correction_type

        self.db.save_snippet(snippet)

        # Learn from correction
        patterns = self.learner.learn_from_correction(snippet)

        # Log
        self.db.log_event(
            "correction_submitted",
            snippet_id=snippet_id,
            details=f"Type: {correction_type}, Patterns learned: {len(patterns)}"
        )

        return {
            "success": True,
            "snippet_id": snippet_id,
            "patterns_learned": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
            "correction_type": correction_type
        }

    def _detect_correction_type(self, original: str, corrected: str) -> str:
        """Auto-detect the type of correction."""
        orig_words = original.split()
        corr_words = corrected.split()

        if len(corr_words) > len(orig_words):
            return "insertion"
        elif len(corr_words) < len(orig_words):
            return "omission"
        elif len(original) == len(corrected):
            diff_count = sum(a != b for a, b in zip(original, corrected))
            if diff_count <= 2:
                return "spelling"
            return "formatting"
        return "mixed"

    def auto_correct(self, text: str, apply_dictionary: bool = True,
                     apply_patterns: bool = True) -> Dict:
        """
        Auto-correct OCR text using learned patterns and dictionary.

        Returns:
            Dict with corrected text and metadata
        """
        original = text
        corrections = []

        # Step 1: Dictionary
        if apply_dictionary and self.medical_dict:
            dict_corrected = self._apply_dictionary(text)
            if dict_corrected != text:
                corrections.append({"type": "dictionary", "original": text, "corrected": dict_corrected})
                text = dict_corrected

        # Step 2: Learned patterns
        if apply_patterns:
            pattern_corrected, pattern_corrs = self.learner.apply_learned_patterns(text)
            if pattern_corrected != text:
                corrections.extend(pattern_corrs)
                text = pattern_corrected

        return {
            "original": original,
            "corrected": text,
            "corrections": corrections,
            "correction_count": len(corrections),
            "was_corrected": text != original
        }

    def get_review_queue(self, limit: int = 50) -> List[TextSnippet]:
        """Get snippets pending review, sorted by confidence (lowest first)."""
        return self.db.get_unreviewed_snippets(limit)

    def get_stats(self) -> Dict:
        """Get training statistics."""
        return self.db.get_stats()

    def export_training_data(self, output_path: str, format: str = "json"):
        """Export training data for model fine-tuning."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, image_path, bbox, ocr_text, corrected_text, 
                   confidence, engine, correction_type, snippet_hash
            FROM snippets WHERE is_reviewed = 1
        """)

        data = []
        for row in cursor.fetchall():
            data.append({
                "id": row[0],
                "image_path": row[1],
                "bbox": eval(row[2]),
                "ocr_text": row[3],
                "corrected_text": row[4],
                "confidence": row[5],
                "engine": row[6],
                "correction_type": row[7],
                "snippet_hash": row[8]
            })

        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif format == "csv":
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys() if data else [])
                writer.writeheader()
                writer.writerows(data)

        logger.info(f"Exported {len(data)} training examples to {output_path}")
        return len(data)

    def close(self):
        self.db.close()


if __name__ == "__main__":
    # Demo
    print("=" * 60)
    print("OCR Snippet Trainer — Demo")
    print("=" * 60)

    trainer = OCRSnippetTrainer()

    # Simulate processing
    print(f"\nDatabase stats: {trainer.get_stats()}")
    print("\nTo use:")
    print("  trainer = OCRSnippetTrainer()")
    print("  snippets = trainer.process_image('document.jpg')")
    print("  trainer.submit_correction(snippets[0].id, 'corrected text')")
    print("  result = trainer.auto_correct('new ocr text')")
