"""
evaluate.py
Once you have a ground-truth record (from ABBYY+Readiris merge), use this
to measure your own engine's (Tesseract / EasyOCR / scanner-fixer pipeline)
actual accuracy against it — real CER/WER, not invented numbers.
"""

from typing import Dict, Any
from .alignment import tokenize


def levenshtein_distance(a: str, b: str) -> int:
    """
    Computes character-level edit distance between two strings.
    Used as the basis for CER (Character Error Rate).
    """
    if len(a) < len(b):
        return levenshtein_distance(b, a)

    if len(b) == 0:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        current_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (ca != cb)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    Computes WER between a reference (ground truth) and hypothesis
    (your engine's output) using word-level Levenshtein distance.

    Args:
        reference: Ground-truth text
        hypothesis: Your OCR engine's output text

    Returns:
        WER as a float (0.0 = perfect, can exceed 1.0 if hypothesis
        has many extra words)
    """
    ref_words = tokenize(reference)
    hyp_words = tokenize(hypothesis)

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    # Word-level edit distance via dynamic programming
    n, m = len(ref_words), len(hyp_words)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return round(dp[n][m] / len(ref_words), 4)


def character_error_rate(reference: str, hypothesis: str) -> float:
    """
    Computes CER between reference and hypothesis text.

    Args:
        reference: Ground-truth text
        hypothesis: Your OCR engine's output text

    Returns:
        CER as a float (0.0 = perfect)
    """
    ref_clean = "".join(reference.split())
    hyp_clean = "".join(hypothesis.split())

    if not ref_clean:
        return 0.0 if not hyp_clean else 1.0

    distance = levenshtein_distance(ref_clean, hyp_clean)
    return round(distance / len(ref_clean), 4)


def evaluate_engine_output(
    ground_truth_text: str,
    engine_output_text: str,
    engine_name: str = "engine"
) -> Dict[str, Any]:
    """
    Full evaluation of one engine's output against ground truth.

    Args:
        ground_truth_text: The merged/verified ground-truth text
            (from build_ground_truth_record's "merged_text")
        engine_output_text: Your engine's raw OCR output for the same document
        engine_name: Label for reporting

    Returns:
        {
            "engine": str,
            "cer": float,
            "wer": float,
            "ref_word_count": int,
            "hyp_word_count": int,
        }
    """
    cer = character_error_rate(ground_truth_text, engine_output_text)
    wer = word_error_rate(ground_truth_text, engine_output_text)

    return {
        "engine": engine_name,
        "cer": cer,
        "wer": wer,
        "ref_word_count": len(tokenize(ground_truth_text)),
        "hyp_word_count": len(tokenize(engine_output_text)),
    }


def compare_engines(
    ground_truth_text: str,
    engine_outputs: Dict[str, str]
) -> Dict[str, Any]:
    """
    Compares multiple engines against the same ground truth at once.
    Use this to answer: "did scanner-fixer actually improve Tesseract's
    accuracy?"

    Args:
        ground_truth_text: The merged/verified ground-truth text
        engine_outputs: dict of {engine_name: output_text}, e.g.
            {
                "tesseract_raw": "...",
                "tesseract_with_scanner_fixer": "...",
                "easyocr_raw": "...",
            }

    Returns:
        {
            "results": list of evaluate_engine_output() dicts,
            "best_cer": str (engine name with lowest CER),
            "best_wer": str (engine name with lowest WER),
        }
    """
    results = [
        evaluate_engine_output(ground_truth_text, text, name)
        for name, text in engine_outputs.items()
    ]

    best_cer = min(results, key=lambda r: r["cer"])["engine"] if results else None
    best_wer = min(results, key=lambda r: r["wer"])["engine"] if results else None

    return {
        "results": results,
        "best_cer": best_cer,
        "best_wer": best_wer,
    }
