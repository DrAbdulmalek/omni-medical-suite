#!/usr/bin/env python3
"""
ocr_benchmark.py — OCR Quality Benchmark Tool (CER / WER / Medical Term Accuracy)
================================================================================
Measures Character Error Rate (CER), Word Error Rate (WER), and medical term
accuracy before and after applying the Arabic Medical OCR Postprocessor.

Usage:
    python ocr_benchmark.py --before ocr_result.json --after ocr_result_patched.json
    python ocr_benchmark.py --ground-truth ground_truth.txt --ocr ocr_output.txt
    python ocr_benchmark.py --json ocr_result.json --ground-truth-file gt.txt

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from collections import Counter
import unicodedata


@dataclass
class BenchmarkResult:
    """Container for benchmark metrics."""
    cer: float  # Character Error Rate (0-1)
    wer: float  # Word Error Rate (0-1)
    cer_percent: float
    wer_percent: float
    char_errors: int
    char_total: int
    word_errors: int
    word_total: int
    medical_terms_found: int
    medical_terms_total: int
    medical_accuracy: float
    confidence: Optional[float] = None
    processing_time: Optional[float] = None


def normalize_text(text: str, for_cer: bool = False) -> str:
    """
    Normalize Arabic text for fair comparison.

    Args:
        text: Input text
        for_cer: If True, preserve spaces for character-level comparison
    """
    if not text:
        return ""

    # Unicode normalization (NFC)
    text = unicodedata.normalize('NFC', text)

    # Replace Arabic letter variants
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ى', 'ي')
    text = text.replace('ة', 'ه')  # Normalize ta marbuta for comparison

    # Remove diacritics (tashkeel)
    diacritics = ''.join(chr(i) for i in range(0x064B, 0x065F))  # Tashkeel range
    for d in diacritics:
        text = text.replace(d, '')

    # Remove zero-width characters
    text = text.replace('‌', '').replace('‍', '')  # ZWNJ, ZWJ
    text = text.replace('﻿', '')  # BOM

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    if not for_cer:
        # For WER: also normalize punctuation
        text = re.sub(r'[،.,;:!?\-\_\=\*\+\/\|\'"\`\~\@\#\$\%\^\&\(\)\[\]\{\}]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

    return text.strip()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def calculate_cer(reference: str, hypothesis: str) -> Tuple[float, int, int]:
    """
    Calculate Character Error Rate (CER).

    CER = (S + D + I) / N
    where S=substitutions, D=deletions, I=insertions, N=reference length

    Returns:
        (cer_value, errors, total_chars)
    """
    ref = normalize_text(reference, for_cer=True).replace(' ', '')
    hyp = normalize_text(hypothesis, for_cer=True).replace(' ', '')

    if len(ref) == 0:
        return 1.0 if len(hyp) > 0 else 0.0, len(hyp), 0

    distance = levenshtein_distance(ref, hyp)
    cer = distance / len(ref)

    return cer, distance, len(ref)


def calculate_wer(reference: str, hypothesis: str) -> Tuple[float, int, int]:
    """
    Calculate Word Error Rate (WER).

    WER = (S + D + I) / N_words
    """
    ref_words = normalize_text(reference, for_cer=False).split()
    hyp_words = normalize_text(hypothesis, for_cer=False).split()

    if len(ref_words) == 0:
        return 1.0 if len(hyp_words) > 0 else 0.0, len(hyp_words), 0

    # Word-level Levenshtein
    distance = levenshtein_distance(ref_words, hyp_words)
    wer = distance / len(ref_words)

    return wer, distance, len(ref_words)


def extract_medical_terms(text: str) -> List[str]:
    """Extract potential medical terms from Arabic text."""
    # Common medical term patterns in Arabic
    patterns = [
        r'(?:ال)?(?:تهاب|خلع|متلازمة|داء|انزلاق|تشوه|شلل|قيلة|ورم|عسرة|حثول|ضفيرة|مفصل|عظم|عضل|فقار|قفداء|روحاء|خرع|برتن|شاركو)\w*',
        r'(?:ال)?(?:مشاش|مثاش|فخذ|كتف|يد|قدم|دماغ|عصب|عظم|فقرات|عمود)\w*',
        r'(?:ال)?(?:خلقي|عضلي|عظمي|فقاري|سحائي|دماغي|قيحي|تطوري)\w*',
        r'Rickets',
        r'Perthes',
        r'Charcot',
    ]

    terms = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            term = m.group().strip()
            if len(term) >= 3:
                terms.append(term)

    return terms


def calculate_medical_accuracy(reference: str, hypothesis: str) -> Tuple[float, int, int]:
    """
    Calculate medical term accuracy.

    Returns:
        (accuracy, found, total)
    """
    ref_terms = set(extract_medical_terms(reference))
    hyp_terms = set(extract_medical_terms(hypothesis))

    if not ref_terms:
        return 1.0, 0, 0

    # Normalize terms for comparison
    ref_norm = {normalize_text(t) for t in ref_terms}
    hyp_norm = {normalize_text(t) for t in hyp_terms}

    found = len(ref_norm & hyp_norm)
    total = len(ref_norm)

    accuracy = found / total if total > 0 else 1.0
    return accuracy, found, total


def run_benchmark(reference: str, hypothesis: str, 
                  confidence: Optional[float] = None,
                  processing_time: Optional[float] = None) -> BenchmarkResult:
    """Run full benchmark suite."""
    cer, cer_errors, cer_total = calculate_cer(reference, hypothesis)
    wer, wer_errors, wer_total = calculate_wer(reference, hypothesis)
    med_acc, med_found, med_total = calculate_medical_accuracy(reference, hypothesis)

    return BenchmarkResult(
        cer=cer,
        wer=wer,
        cer_percent=cer * 100,
        wer_percent=wer * 100,
        char_errors=cer_errors,
        char_total=cer_total,
        word_errors=wer_errors,
        word_total=wer_total,
        medical_terms_found=med_found,
        medical_terms_total=med_total,
        medical_accuracy=med_acc,
        confidence=confidence,
        processing_time=processing_time
    )


def format_result(result: BenchmarkResult, label: str = "Result") -> str:
    """Format benchmark result for display."""
    lines = [
        f"\n{'='*60}",
        f"📊 {label}",
        f"{'='*60}",
        f"  CER (Character Error Rate):     {result.cer:.4f}  ({result.cer_percent:.2f}%)",
        f"    └─ Errors: {result.char_errors} / {result.char_total} characters",
        f"  WER (Word Error Rate):          {result.wer:.4f}  ({result.wer_percent:.2f}%)",
        f"    └─ Errors: {result.word_errors} / {result.word_total} words",
        f"  Medical Term Accuracy:          {result.medical_accuracy:.4f}  ({result.medical_accuracy*100:.1f}%)",
        f"    └─ Found: {result.medical_terms_found} / {result.medical_terms_total} terms",
    ]

    if result.confidence is not None:
        lines.append(f"  Reported Confidence:            {result.confidence:.3f}")

    if result.processing_time is not None:
        lines.append(f"  Processing Time:                {result.processing_time:.2f}s")
        if result.char_total > 0:
            cps = result.char_total / result.processing_time
            lines.append(f"    └─ Speed: {cps:.1f} chars/sec")

    lines.append(f"{'='*60}")

    return "\n".join(lines)


def load_json_result(path: str) -> Dict:
    """Load OCR result from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_text_file(path: str) -> str:
    """Load text from file."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def compare_before_after(before_json: str, after_json: str, ground_truth_file: Optional[str] = None):
    """Compare OCR results before and after postprocessing."""
    before = load_json_result(before_json)
    after = load_json_result(after_json)

    # Use ground truth if provided, otherwise use corrected_text from 'after' as best-effort reference
    if ground_truth_file:
        ground_truth = load_text_file(ground_truth_file)
    else:
        # Fallback: use the corrected_text from after as pseudo-ground-truth
        # (This is for demonstration; real evaluation needs human ground truth)
        ground_truth = after.get("corrected_text", after.get("raw_text", ""))
        print("⚠️  No ground truth provided. Using corrected_text as reference (not ideal for CER/WER).")
        print("   For accurate benchmarking, provide --ground-truth-file with manually verified text.\n")

    raw_text = before.get("raw_text", "")
    corrected_text = after.get("corrected_text", after.get("raw_text", ""))

    # Before
    before_result = run_benchmark(
        ground_truth, raw_text,
        confidence=before.get("confidence"),
        processing_time=before.get("processing_time")
    )

    # After
    after_result = run_benchmark(
        ground_truth, corrected_text,
        confidence=after.get("confidence_post_corrected", after.get("confidence")),
        processing_time=after.get("processing_time")
    )

    # Print results
    print(format_result(before_result, "BEFORE Postprocessing (Raw OCR)"))
    print(format_result(after_result, "AFTER Postprocessing (Corrected)"))

    # Improvement summary
    cer_improvement = before_result.cer - after_result.cer
    wer_improvement = before_result.wer - after_result.wer
    med_improvement = after_result.medical_accuracy - before_result.medical_accuracy

    print(f"\n📈 IMPROVEMENT SUMMARY")
    print(f"{'='*60}")
    print(f"  CER Improvement:  {cer_improvement:+.4f}  ({cer_improvement*100:+.2f}%)")
    print(f"  WER Improvement:  {wer_improvement:+.4f}  ({wer_improvement*100:+.2f}%)")
    print(f"  Medical Accuracy: {med_improvement:+.4f}  ({med_improvement*100:+.1f}%)")

    if cer_improvement > 0:
        print(f"  ✅ CER reduced by {cer_improvement/before_result.cer*100:.1f}% (relative)")
    if wer_improvement > 0:
        print(f"  ✅ WER reduced by {wer_improvement/before_result.wer*100:.1f}% (relative)")

    print(f"{'='*60}\n")

    # Detailed error analysis
    print("🔍 DETAILED ERROR ANALYSIS (Before vs After)")
    print(f"{'='*60}")

    ref_words = normalize_text(ground_truth, for_cer=False).split()
    raw_words = normalize_text(raw_text, for_cer=False).split()
    corr_words = normalize_text(corrected_text, for_cer=False).split()

    # Find word-level differences
    before_errors = _find_word_errors(ref_words, raw_words)
    after_errors = _find_word_errors(ref_words, corr_words)

    print(f"\nWord errors BEFORE: {len(before_errors)}")
    for err in before_errors[:10]:  # Show first 10
        print(f"  ❌ [{err['type']}] ref='{err['ref']}' | hyp='{err['hyp']}'")
    if len(before_errors) > 10:
        print(f"  ... and {len(before_errors)-10} more")

    print(f"\nWord errors AFTER: {len(after_errors)}")
    for err in after_errors[:10]:
        print(f"  ❌ [{err['type']}] ref='{err['ref']}' | hyp='{err['hyp']}'")
    if len(after_errors) > 10:
        print(f"  ... and {len(after_errors)-10} more")

    # Fixed errors
    fixed = [e for e in before_errors if e not in after_errors]
    new_errors = [e for e in after_errors if e not in before_errors]

    print(f"\n✅ ERRORS FIXED: {len(fixed)}")
    for err in fixed[:10]:
        print(f"     '{err['hyp']}' → '{err['ref']}'")

    print(f"\n⚠️  NEW ERRORS INTRODUCED: {len(new_errors)}")
    for err in new_errors[:10]:
        print(f"     '{err['ref']}' | got '{err['hyp']}'")

    print(f"\n{'='*60}\n")

    return before_result, after_result


def _find_word_errors(ref_words: List[str], hyp_words: List[str]) -> List[Dict]:
    """Find word-level errors using simple alignment."""
    errors = []

    # Simple alignment (not optimal but sufficient for analysis)
    max_len = max(len(ref_words), len(hyp_words))
    for i in range(max_len):
        ref = ref_words[i] if i < len(ref_words) else "<MISSING>"
        hyp = hyp_words[i] if i < len(hyp_words) else "<MISSING>"

        if normalize_text(ref) != normalize_text(hyp):
            err_type = "substitution"
            if ref == "<MISSING>":
                err_type = "insertion"
            elif hyp == "<MISSING>":
                err_type = "deletion"

            errors.append({
                "type": err_type,
                "ref": ref,
                "hyp": hyp,
                "position": i
            })

    return errors


def benchmark_single(ground_truth: str, ocr_text: str, 
                     confidence: Optional[float] = None,
                     processing_time: Optional[float] = None,
                     label: str = "OCR Result") -> BenchmarkResult:
    """Benchmark a single OCR output against ground truth."""
    result = run_benchmark(ground_truth, ocr_text, confidence, processing_time)
    print(format_result(result, label))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="OCR Quality Benchmark Tool (CER/WER/Medical Accuracy)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare before/after JSON results
  python ocr_benchmark.py --before ocr_result.json --after ocr_result_patched.json

  # With ground truth file
  python ocr_benchmark.py --before ocr_result.json --after ocr_result_patched.json --ground-truth-file gt.txt

  # Single file benchmark
  python ocr_benchmark.py --ground-truth-file gt.txt --ocr-file ocr_output.txt

  # Direct text comparison
  python ocr_benchmark.py --ground-truth "الشلل الدماغي" --ocr "الشثل الدماغي"
        """
    )

    parser.add_argument("--before", type=str, help="JSON file with raw OCR result")
    parser.add_argument("--after", type=str, help="JSON file with postprocessed OCR result")
    parser.add_argument("--ground-truth-file", type=str, help="Text file with ground truth")
    parser.add_argument("--ocr-file", type=str, help="Text file with OCR output")
    parser.add_argument("--ground-truth", type=str, help="Ground truth text (direct)")
    parser.add_argument("--ocr", type=str, help="OCR text (direct)")
    parser.add_argument("--json", type=str, help="Single JSON file to benchmark (uses corrected_text vs raw_text)")
    parser.add_argument("--output", type=str, help="Output JSON file for results")

    args = parser.parse_args()

    # Mode 1: Before/After comparison
    if args.before and args.after:
        before_result, after_result = compare_before_after(
            args.before, args.after, args.ground_truth_file
        )

        if args.output:
            output_data = {
                "before": {
                    "cer": before_result.cer,
                    "wer": before_result.wer,
                    "medical_accuracy": before_result.medical_accuracy,
                    "confidence": before_result.confidence,
                    "processing_time": before_result.processing_time
                },
                "after": {
                    "cer": after_result.cer,
                    "wer": after_result.wer,
                    "medical_accuracy": after_result.medical_accuracy,
                    "confidence": after_result.confidence,
                    "processing_time": after_result.processing_time
                },
                "improvement": {
                    "cer_delta": before_result.cer - after_result.cer,
                    "wer_delta": before_result.wer - after_result.wer,
                    "medical_delta": after_result.medical_accuracy - before_result.medical_accuracy
                }
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Results saved to: {args.output}")

        return

    # Mode 2: Single file benchmark
    if args.ground_truth_file and args.ocr_file:
        gt = load_text_file(args.ground_truth_file)
        ocr = load_text_file(args.ocr_file)
        benchmark_single(gt, ocr, label="OCR vs Ground Truth")
        return

    # Mode 3: Direct text
    if args.ground_truth and args.ocr:
        benchmark_single(args.ground_truth, args.ocr, label="Direct Comparison")
        return

    # Mode 4: Single JSON (internal comparison)
    if args.json:
        data = load_json_result(args.json)
        raw = data.get("raw_text", "")
        corrected = data.get("corrected_text", raw)

        # If corrected == raw, run postprocessor demo
        if corrected == raw:
            print("⚠️  corrected_text == raw_text in JSON. Running demo with built-in postprocessor...")
            try:
                from medical_doc_gui_patch import patch_ocr_result
                data = patch_ocr_result(data)
                corrected = data.get("corrected_text", raw)
            except ImportError:
                print("❌ medical_doc_gui_patch.py not found. Install it first.")
                return

        print("📊 Benchmarking raw_text vs corrected_text (pseudo-ground-truth)")
        print("   Note: For true CER/WER, provide external ground truth.\n")

        # Use corrected as pseudo-ground-truth for raw
        raw_result = run_benchmark(corrected, raw, 
                                   confidence=data.get("confidence"),
                                   processing_time=data.get("processing_time"))
        print(format_result(raw_result, "RAW OCR (vs Corrected as Reference)"))

        # Perfect score for corrected vs itself
        print(format_result(
            BenchmarkResult(0.0, 0.0, 0.0, 0.0, 0, len(corrected), 0, len(corrected.split()),
                          0, 0, 1.0),
            "CORRECTED (Perfect by definition)"
        ))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
