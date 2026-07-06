#!/usr/bin/env python3
"""
gt_comparison_engine.py — Compare OCR Output with Ground Truth
=================================================================
Compares OCR results (from any engine) against imported ground truth
from ABBYY, ReadIRIS, or PDF Grabber. Generates detailed diff reports
and training data for model improvement.

Usage:
    python gt_comparison_engine.py --gt ground_truth.txt --ocr ocr_output.txt
    python gt_comparison_engine.py --gt gt.json --ocr ocr_result.json --output report.json
    python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --mode char --visual

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import difflib
import unicodedata


@dataclass
class ComparisonResult:
    """Result of comparing OCR with ground truth."""
    gt_text: str
    ocr_text: str
    cer: float
    wer: float
    char_errors: int
    char_total: int
    word_errors: int
    word_total: int
    aligned_pairs: List[Tuple[str, str]]
    error_details: List[Dict]
    medical_terms: Dict[str, Any]


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for comparison."""
    text = unicodedata.normalize('NFC', text)
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ى', 'ي')
    text = text.replace('ة', 'ه')
    # Remove diacritics
    for i in range(0x064B, 0x065F):
        text = text.replace(chr(i), '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def levenshtein_matrix(s1: str, s2: str) -> Tuple[int, List[List[int]]]:
    """Compute full Levenshtein matrix for alignment."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,      # deletion
                dp[i][j-1] + 1,      # insertion
                dp[i-1][j-1] + cost  # substitution
            )

    return dp[m][n], dp


def align_sequences(s1: str, s2: str) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Align two sequences using backtracking through Levenshtein matrix.
    Returns list of (char_from_s1, char_from_s2) pairs.
    """
    _, dp = levenshtein_matrix(s1, s2)
    i, j = len(s1), len(s2)
    alignment = []

    while i > 0 or j > 0:
        if i == 0:
            alignment.append((None, s2[j-1]))
            j -= 1
        elif j == 0:
            alignment.append((s1[i-1], None))
            i -= 1
        else:
            cost = 0 if s1[i-1] == s2[j-1] else 1
            if dp[i][j] == dp[i-1][j-1] + cost:
                alignment.append((s1[i-1], s2[j-1]))
                i -= 1
                j -= 1
            elif dp[i][j] == dp[i-1][j] + 1:
                alignment.append((s1[i-1], None))
                i -= 1
            else:
                alignment.append((None, s2[j-1]))
                j -= 1

    alignment.reverse()
    return alignment


def compare_line(gt_line: str, ocr_line: str) -> ComparisonResult:
    """Compare a single line of GT with OCR."""
    # Normalize
    gt_norm = normalize_arabic(gt_line)
    ocr_norm = normalize_arabic(ocr_line)

    # Character-level
    gt_chars = gt_norm.replace(' ', '')
    ocr_chars = ocr_norm.replace(' ', '')
    char_dist, _ = levenshtein_matrix(gt_chars, ocr_chars)
    cer = char_dist / max(len(gt_chars), 1)

    # Word-level
    gt_words = gt_norm.split()
    ocr_words = ocr_norm.split()
    word_dist, _ = levenshtein_matrix(gt_words, ocr_words)
    wer = word_dist / max(len(gt_words), 1)

    # Character alignment for visualization
    alignment = align_sequences(gt_chars, ocr_chars)

    # Error details
    errors = []
    for gt_char, ocr_char in alignment:
        if gt_char != ocr_char:
            errors.append({
                "gt": gt_char,
                "ocr": ocr_char,
                "type": "substitution" if gt_char and ocr_char else (
                    "deletion" if gt_char else "insertion"
                )
            })

    # Medical terms analysis
    medical = analyze_medical_terms(gt_norm, ocr_norm)

    return ComparisonResult(
        gt_text=gt_line,
        ocr_text=ocr_line,
        cer=cer,
        wer=wer,
        char_errors=char_dist,
        char_total=len(gt_chars),
        word_errors=word_dist,
        word_total=len(gt_words),
        aligned_pairs=alignment,
        error_details=errors,
        medical_terms=medical
    )


def analyze_medical_terms(gt_text: str, ocr_text: str) -> Dict:
    """Analyze medical term accuracy."""
    # Common medical patterns
    patterns = [
        r'(?:ال)?(?:تهاب|خلع|متلازمة|داء|انزلاق|تشوه|شلل|قيلة|ورم|عسرة|حثول|ضفيرة|مفصل|عظم|عضل|فقار|قفداء|روحاء|خرع|برتن|شاركو)\w*',
        r'(?:ال)?(?:مشاش|مثاش|فخذ|كتف|يد|قدم|دماغ|عصب|عظم|فقرات|عمود)\w*',
        r'(?:ال)?(?:خلقي|عضلي|عظمي|فقاري|سحائي|دماغي|قيحي|تطوري)\w*',
        r'Rickets', r'Perthes', r'Charcot',
    ]

    gt_terms = set()
    ocr_terms = set()

    for pattern in patterns:
        for m in re.finditer(pattern, gt_text, re.IGNORECASE):
            gt_terms.add(normalize_arabic(m.group()))
        for m in re.finditer(pattern, ocr_text, re.IGNORECASE):
            ocr_terms.add(normalize_arabic(m.group()))

    found = gt_terms & ocr_terms
    missed = gt_terms - ocr_terms
    extra = ocr_terms - gt_terms

    return {
        "total_gt": len(gt_terms),
        "found": len(found),
        "missed": list(missed),
        "extra": list(extra),
        "accuracy": len(found) / max(len(gt_terms), 1)
    }


def generate_visual_diff(alignment: List[Tuple[Optional[str], Optional[str]]]) -> str:
    """Generate visual diff showing aligned characters."""
    gt_line = []
    ocr_line = []
    marker_line = []

    for gt_char, ocr_char in alignment:
        # Pad to same width
        gt_str = gt_char if gt_char else ' '
        ocr_str = ocr_char if ocr_char else ' '
        max_len = max(len(gt_str), len(ocr_str))

        gt_line.append(gt_str.ljust(max_len))
        ocr_line.append(ocr_str.ljust(max_len))

        if gt_char == ocr_char:
            marker_line.append('│'.ljust(max_len))
        else:
            marker_line.append('✗'.ljust(max_len))

    return '\n'.join([
        'GT:  ' + ''.join(gt_line),
        '     ' + ''.join(marker_line),
        'OCR: ' + ''.join(ocr_line)
    ])


def generate_training_data(results: List[ComparisonResult]) -> List[Dict]:
    """Generate training pairs from comparison results."""
    training_data = []

    for result in results:
        if result.cer > 0 and result.cer < 0.5:  # Not too bad, worth training
            training_data.append({
                "input": result.ocr_text,
                "target": result.gt_text,
                "cer": result.cer,
                "error_types": list(set(e["type"] for e in result.error_details)),
                "medical_terms": result.medical_terms
            })

    return training_data


def generate_correction_dictionary(results: List[ComparisonResult],
                                    min_frequency: int = 2) -> Dict[str, str]:
    """Generate auto-correction dictionary from frequent errors."""
    error_counts = defaultdict(lambda: {"count": 0, "correction": ""})

    for result in results:
        for error in result.error_details:
            if error["type"] == "substitution" and error["ocr"] and error["gt"]:
                key = error["ocr"]
                error_counts[key]["count"] += 1
                error_counts[key]["correction"] = error["gt"]

    # Filter by frequency
    dictionary = {}
    for wrong, data in error_counts.items():
        if data["count"] >= min_frequency:
            dictionary[wrong] = data["correction"]

    return dictionary


def main():
    parser = argparse.ArgumentParser(
        description="Compare OCR with Ground Truth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt
  python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --output report.json
  python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --visual --output diff.txt
  python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --generate-dict --output dict.json
        """
    )

    parser.add_argument("--gt", required=True, help="Ground truth file")
    parser.add_argument("--ocr", required=True, help="OCR output file")
    parser.add_argument("--output", "-o", help="Output report file")
    parser.add_argument("--visual", action="store_true", help="Generate visual diff")
    parser.add_argument("--generate-dict", action="store_true",
                        help="Generate correction dictionary from errors")
    parser.add_argument("--generate-training", action="store_true",
                        help="Generate training data pairs")
    parser.add_argument("--min-freq", type=int, default=2,
                        help="Minimum error frequency for dictionary")

    args = parser.parse_args()

    # Load files
    with open(args.gt, 'r', encoding='utf-8') as f:
        gt_lines = [line.strip() for line in f if line.strip()]

    with open(args.ocr, 'r', encoding='utf-8') as f:
        ocr_lines = [line.strip() for line in f if line.strip()]

    # Compare line by line
    results = []
    for i in range(max(len(gt_lines), len(ocr_lines))):
        gt = gt_lines[i] if i < len(gt_lines) else ""
        ocr = ocr_lines[i] if i < len(ocr_lines) else ""
        result = compare_line(gt, ocr)
        results.append(result)

    # Summary statistics
    avg_cer = sum(r.cer for r in results) / len(results)
    avg_wer = sum(r.wer for r in results) / len(results)
    total_char_errors = sum(r.char_errors for r in results)
    total_char_total = sum(r.char_total for r in results)
    total_word_errors = sum(r.word_errors for r in results)
    total_word_total = sum(r.word_total for r in results)

    # Medical terms
    all_medical_found = sum(r.medical_terms["found"] for r in results)
    all_medical_total = sum(r.medical_terms["total_gt"] for r in results)

    print("=" * 70)
    print("📊 OCR vs Ground Truth Comparison Report")
    print("=" * 70)
    print(f"Lines compared:     {len(results)}")
    print(f"Average CER:        {avg_cer:.2%}")
    print(f"Average WER:        {avg_wer:.2%}")
    print(f"Total char errors:  {total_char_errors} / {total_char_total}")
    print(f"Total word errors:  {total_word_errors} / {total_word_total}")
    print(f"Medical terms:      {all_medical_found} / {all_medical_total} ({all_medical_found/max(all_medical_total,1):.1%})")
    print("=" * 70)

    # Per-line details
    for i, result in enumerate(results):
        if result.cer > 0:
            print(f"\nLine {i+1} — CER: {result.cer:.1%} | WER: {result.wer:.1%}")
            print(f"  GT:  {result.gt_text[:80]}")
            print(f"  OCR: {result.ocr_text[:80]}")
            if result.medical_terms["missed"]:
                print(f"  ❌ Missed terms: {', '.join(result.medical_terms['missed'])}")

    # Visual diff
    if args.visual:
        print("\n" + "=" * 70)
        print("🔍 Visual Character Alignment")
        print("=" * 70)
        for i, result in enumerate(results[:10]):  # Show first 10
            if result.cer > 0:
                print(f"\n--- Line {i+1} ---")
                print(generate_visual_diff(result.aligned_pairs))

    # Output generation
    output_data = {
        "summary": {
            "lines_compared": len(results),
            "avg_cer": avg_cer,
            "avg_wer": avg_wer,
            "total_char_errors": total_char_errors,
            "total_char_total": total_char_total,
            "total_word_errors": total_word_errors,
            "total_word_total": total_word_total,
            "medical_accuracy": all_medical_found / max(all_medical_total, 1)
        },
        "line_results": [{
            "line": i+1,
            "gt": r.gt_text,
            "ocr": r.ocr_text,
            "cer": r.cer,
            "wer": r.wer,
            "medical_terms": r.medical_terms
        } for i, r in enumerate(results)]
    }

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Report saved to: {args.output}")

    if args.generate_dict:
        dictionary = generate_correction_dictionary(results, args.min_freq)
        dict_path = args.output.replace('.json', '_dict.json') if args.output else 'correction_dict.json'
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        print(f"📖 Correction dictionary ({len(dictionary)} entries) saved to: {dict_path}")

    if args.generate_training:
        training = generate_training_data(results)
        train_path = args.output.replace('.json', '_training.json') if args.output else 'training_data.json'
        with open(train_path, 'w', encoding='utf-8') as f:
            json.dump(training, f, ensure_ascii=False, indent=2)
        print(f"🎓 Training data ({len(training)} pairs) saved to: {train_path}")


if __name__ == "__main__":
    main()
