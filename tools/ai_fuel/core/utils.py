"""
AI Fuel Engine - Utility Functions

A collection of pure-function helpers used across the pipeline:
token counting, language detection, text normalization, hashing,
similarity computation, logging setup, and filename sanitization.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import unicodedata
from math import sqrt
from typing import Dict, List, Optional, Tuple

# Optional import — tiktoken is used when available for accurate GPT token
# counting; otherwise we fall back to a fast word-level heuristic.
try:
    import tiktoken
    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False

logger = logging.getLogger(__name__)


# ======================================================================
# Token Counting
# ======================================================================

_tiktoken_cache: Dict[str, Any] = {}


def _get_encoding(model: str):
    """Retrieve (and cache) a tiktoken Encoding for *model*."""
    if model not in _tiktoken_cache:
        try:
            _tiktoken_cache[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base (GPT-4 family)
            _tiktoken_cache[model] = tiktoken.get_encoding("cl100k_base")
    return _tiktoken_cache[model]


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in *text* for a given model.

    When ``tiktoken`` is installed the count is exact for OpenAI models.
    Otherwise a word-level heuristic is used (≈ 1.3 tokens per word for
    English, ≈ 1.5 tokens per word for Arabic).

    Args:
        text: The input text.
        model: The model name whose tokenizer to use.

    Returns:
        Estimated or exact token count.
    """
    if not text:
        return 0

    if _HAS_TIKTOKEN:
        try:
            enc = _get_encoding(model)
            return len(enc.encode(text))
        except Exception as exc:
            logger.warning("tiktoken failed (%s), falling back to heuristic", exc)

    # Heuristic: split on whitespace
    words = text.split()
    if not words:
        return 0
    # Arabic words tend to tokenize to more tokens
    avg_tok_per_word = 1.5 if _is_arabic_heuristic(text) else 1.3
    return max(1, int(len(words) * avg_tok_per_word))


def _is_arabic_heuristic(text: str) -> bool:
    """Quick heuristic: does the text contain a significant proportion of Arabic characters?"""
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return arabic_chars > len(text) * 0.3


# ======================================================================
# Language Detection
# ======================================================================

# Basic Arabic character range
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def detect_language(text: str) -> str:
    """Detect the primary language of *text*.

    Returns one of: ``"ar"`` (Arabic), ``"en"`` (English), ``"mixed"``,
    or ``"unknown"``.

    The detection is script-based and works well for Arabic/English content
    typical of Middle Eastern healthcare documents.

    Args:
        text: Input text to analyze.

    Returns:
        Language code string.
    """
    if not text or not text.strip():
        return "unknown"

    arabic_matches = len(_ARABIC_RE.findall(text))
    latin_matches = len(_LATIN_RE.findall(text))
    total_chars = max(len(text), 1)

    arabic_ratio = arabic_matches / total_chars
    latin_ratio = latin_matches / total_chars

    if arabic_ratio > 0.3 and latin_ratio > 0.3:
        return "mixed"
    if arabic_ratio > latin_ratio and arabic_ratio > 0.1:
        return "ar"
    if latin_ratio > arabic_ratio and latin_ratio > 0.1:
        return "en"

    return "unknown"


# ======================================================================
# Arabic Normalization
# ======================================================================

_ARABIC_NORMALIZATION_MAP = {
    "\u0621": "\u0627",  # Hamza on alef → Alef
    "\u0623": "\u0627",  # Alef with hamza above → Alef
    "\u0624": "\u0627",  # Alef with hamza below → Alef
    "\u0625": "\u0627",  # Alef with madda above → Alef
    "\u0626": "\u0647",  # Alef with hamza on waw ya → Ha
}

# Tashkeel (diacritics) Unicode range
_TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670]")
_TATWEEL_RE = re.compile(r"\u0640")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for consistent processing.

    Applies the following transformations:
    - Normalize alef variants (hamza, madda) to plain alef (ا).
    - Normalize alef maqsura (ى) to ya (ي).
    - Normalize taa marbuta (ة) to haa (ه).
    - Strip tashkeel (diacritics).
    - Strip tatweel (kashida).

    Args:
        text: Raw Arabic text.

    Returns:
        Normalized text.
    """
    if not text:
        return text

    normalized = list(text)

    for idx, char in enumerate(normalized):
        normalized[idx] = _ARABIC_NORMALIZATION_MAP.get(char, char)

    text = "".join(normalized)
    text = _TASHKEEL_RE.sub("", text)
    text = _TATWEEL_RE.sub("", text)

    # Normalize taa marbuta and alef maqsura
    text = text.replace("\u0629", "\u0647")  # ة → ه
    text = text.replace("\u0649", "\u064A")  # ى → ي

    return text


# ======================================================================
# OCR Artifact Cleaning
# ======================================================================

_OCR_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Multiple spaces → single space
    (re.compile(r" {2,}"), " "),
    # Lines that are all dashes/dots/underscores (page-break artifacts)
    (re.compile(r"\n[-._]{3,}\n"), "\n"),
    # Standalone page numbers like "— 42 —" or "- 42 -"
    (re.compile(r"\n\s*[-–—]\s*\d{1,4}\s*[-–—]\s*\n"), "\n"),
    # Trailing hyphens from line breaks (e.g. "exam-\nple")
    (re.compile(r"(\w)-\n(\w)"), r"\1\2"),
    # Zero-width / non-printing characters
    (re.compile(r"[\u200B-\u200D\uFEFF]"), ""),
    # Control characters except newline/tab
    (re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"), ""),
]


def clean_ocr_artifacts(text: str) -> str:
    """Remove common OCR scanning artifacts from text.

    Handles extra whitespace, page-break lines, line-break hyphens,
    zero-width characters, and control characters.

    Args:
        text: Raw OCR-extracted text.

    Returns:
        Cleaned text.
    """
    if not text:
        return text

    for pattern, replacement in _OCR_PATTERNS:
        text = pattern.sub(replacement, text)

    # Collapse multiple newlines to at most two
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ======================================================================
# Hashing
# ======================================================================


def compute_hash(text: str, algorithm: str = "md5") -> str:
    """Compute a cryptographic hash of *text*.

    Supported algorithms: ``"md5"`` (default) and ``"sha256"``.

    Args:
        text: The text to hash.
        algorithm: Hash algorithm name.

    Returns:
        Hexadecimal digest string.

    Raises:
        ValueError: If *algorithm* is not supported.
    """
    algorithm = algorithm.lower().strip()
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm!r}. Use 'md5' or 'sha256'.")

    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


# ======================================================================
# Similarity Computation
# ======================================================================


def _tokenize_simple(text: str) -> Dict[str, int]:
    """Whitespace tokenization → frequency dict."""
    tokens: Dict[str, int] = {}
    for word in text.lower().split():
        tokens[word] = tokens.get(word, 0) + 1
    return tokens


def _cosine_sim(vec_a: Dict[str, int], vec_b: Dict[str, int]) -> float:
    """Compute cosine similarity between two term-frequency dicts."""
    # Dot product
    dot = sum(vec_a[k] * vec_b[k] for k in vec_a if k in vec_b)
    if dot == 0:
        return 0.0

    # Magnitudes
    mag_a = sqrt(sum(v * v for v in vec_a.values()))
    mag_b = sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate cosine similarity between two texts using bag-of-words.

    For production semantic similarity, replace this with a
    sentence-transformers encoder.  This function provides a fast,
    dependency-free baseline.

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Cosine similarity in [0, 1].
    """
    if not text1 or not text2:
        return 0.0
    if text1 == text2:
        return 1.0

    vec1 = _tokenize_simple(text1)
    vec2 = _tokenize_simple(text2)
    return round(_cosine_sim(vec1, vec2), 6)


# ======================================================================
# Time Formatting
# ======================================================================


def format_processing_time(seconds: float) -> str:
    """Format a duration in seconds into a human-readable string.

    Examples:
        >>> format_processing_time(0.045)
        '45.0 ms'
        >>> format_processing_time(72.5)
        '1m 12s'
        >>> format_processing_time(3723)
        '1h 2m 3s'

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted time string.
    """
    if seconds < 0:
        return "0 ms"

    if seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts: List[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


# ======================================================================
# Logging Setup
# ======================================================================


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """Configure the root logger for the AI Fuel Engine.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to a file handler.  If ``None`` only console
            output is produced.
        format_string: Optional custom format string.  Defaults to a
            production-friendly format with timestamp, level, logger name,
            and message.

    Returns:
        The configured root logger.
    """
    fmt = format_string or "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger("ai_fuel_engine")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


# ======================================================================
# Filename Sanitization
# ======================================================================

_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def safe_filename(name: str, max_length: int = 200) -> str:
    """Sanitize *name* into a safe filesystem filename.

    - Replaces unsafe characters with underscores.
    - Collapses consecutive underscores.
    - Strips leading/trailing dots and whitespace.
    - Truncates to *max_length* characters.

    Args:
        name: Desired filename.
        max_length: Maximum allowed length.

    Returns:
        A sanitized, safe filename string.
    """
    if not name:
        return "unnamed"

    name = _UNSAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip(". ")
    name = name[:max_length]

    return name or "unnamed"


# ======================================================================
# Chunk Overlap Helper
# ======================================================================


def chunk_overlap_text(text: str, overlap: int) -> str:
    """Extract the overlapping tail portion of *text* for chunk continuity.

    The overlap is measured in characters.  If *overlap* exceeds the text
    length the entire text is returned.

    Args:
        text: Source text from which to extract the overlap.
        overlap: Number of characters of overlap to retrieve.

    Returns:
        The overlapping substring (or empty string if *text* is empty).
    """
    if not text or overlap <= 0:
        return ""

    overlap = min(overlap, len(text))
    return text[-overlap:]
