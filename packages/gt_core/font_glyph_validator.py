#!/usr/bin/env python3
"""
font_glyph_validator.py — Validate OCR Characters Using Font Glyphs
====================================================================
Uses font data extracted by PDF Grabber to validate OCR output.
Compares extracted characters against known glyphs to detect
and correct OCR errors.

Usage:
    python font_glyph_validator.py --fonts fonts.json --ocr ocr_output.txt
    python font_glyph_validator.py --fonts fonts.json --ocr ocr.txt --output validated.txt
    python font_glyph_validator.py --build-index fonts.json --output glyph_index.json

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import numpy as np


def load_font_data(fonts_path: str) -> Dict:
    """Load font and glyph data from JSON."""
    with open(fonts_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_character_index(fonts_data: Dict) -> Dict[str, List[Dict]]:
    """
    Build an index of characters to their glyph instances.
    Returns: {char: [glyph_info, ...]}
    """
    char_index = defaultdict(list)
    glyphs = fonts_data.get("glyphs", [])

    for glyph in glyphs:
        char = glyph.get("char", "")
        if char:
            char_index[char].append(glyph)

    return dict(char_index)


def get_font_character_set(fonts_data: Dict) -> Set[str]:
    """Get set of all characters supported by fonts."""
    char_index = build_character_index(fonts_data)
    return set(char_index.keys())


def compute_glyph_similarity(glyph1: Dict, glyph2: Dict) -> float:
    """
    Compute similarity between two glyphs based on visual features.
    Returns score between 0 and 1.
    """
    # Compare dimensions
    w1, h1 = glyph1.get("width", 0), glyph1.get("height", 0)
    w2, h2 = glyph2.get("width", 0), glyph2.get("height", 0)

    if w1 == 0 or w2 == 0:
        return 0.0

    size_sim = min(w1, w2) / max(w1, w2) * min(h1, h2) / max(h1, h2)

    # Compare fonts
    font_sim = 1.0 if glyph1.get("font") == glyph2.get("font") else 0.5

    # Compare sizes
    size_diff = abs(glyph1.get("size", 0) - glyph2.get("size", 0))
    size_match = max(0, 1.0 - size_diff / 5.0)

    return (size_sim * 0.4 + font_sim * 0.3 + size_match * 0.3)


def find_similar_chars(char: str, fonts_data: Dict, threshold: float = 0.6) -> List[Tuple[str, float]]:
    """
    Find characters with similar glyph shapes.
    Useful for detecting common OCR confusions:
        ث ↔ ل, ح ↔ خ, د ↔ ذ, ر ↔ ز, س ↔ ش, ص ↔ ض, ط ↔ ظ, ع ↔ غ, ف ↔ ق
    """
    char_index = build_character_index(fonts_data)

    if char not in char_index:
        return []

    char_glyphs = char_index[char]
    similarities = []

    for other_char, other_glyphs in char_index.items():
        if other_char == char:
            continue

        max_sim = 0.0
        for g1 in char_glyphs:
            for g2 in other_glyphs:
                sim = compute_glyph_similarity(g1, g2)
                max_sim = max(max_sim, sim)

        if max_sim >= threshold:
            similarities.append((other_char, max_sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities


def validate_text(text: str, fonts_data: Dict) -> Dict:
    """
    Validate text against font glyphs.
    Returns validation report.
    """
    char_index = build_character_index(fonts_data)
    font_chars = set(char_index.keys())

    issues = []
    validated_chars = 0
    unknown_chars = 0

    for i, char in enumerate(text):
        if char.isspace() or char in '0123456789':
            continue

        if char in font_chars:
            validated_chars += 1
        else:
            unknown_chars += 1
            # Find similar characters
            similar = find_similar_chars(char, fonts_data, threshold=0.5)
            suggestions = [s[0] for s in similar[:3]]

            issues.append({
                "position": i,
                "char": char,
                "issue": "not_in_font",
                "suggestions": suggestions,
                "context": text[max(0, i-3):i+4]
            })

    return {
        "text": text,
        "total_chars": len(text),
        "validated_chars": validated_chars,
        "unknown_chars": unknown_chars,
        "validation_rate": validated_chars / max(len(text), 1),
        "issues": issues
    }


def correct_with_fonts(text: str, fonts_data: Dict,
                        ocr_confidence: Optional[Dict] = None) -> Tuple[str, List[Dict]]:
    """
    Correct text using font glyph validation.
    Returns (corrected_text, corrections_applied).
    """
    char_index = build_character_index(fonts_data)
    corrections = []
    corrected = list(text)

    for i, char in enumerate(text):
        if char.isspace():
            continue

        if char not in char_index:
            # Character not in font — likely OCR error
            similar = find_similar_chars(char, fonts_data, threshold=0.5)

            if similar:
                best_char, score = similar[0]
                corrections.append({
                    "position": i,
                    "original": char,
                    "corrected": best_char,
                    "confidence": score,
                    "reason": "font_glyph_mismatch"
                })
                corrected[i] = best_char

    return ''.join(corrected), corrections


class FontAwareOCRValidator:
    """Main validator that combines font data with OCR output."""

    def __init__(self, fonts_data: Dict):
        self.fonts_data = fonts_data
        self.char_index = build_character_index(fonts_data)
        self.known_confusions = {
            'ث': ['ل', 'ت', 'ب'],
            'ل': ['ث', 'ت', 'ب'],
            'ح': ['خ', 'ج'],
            'خ': ['ح', 'ج'],
            'د': ['ذ', 'ر'],
            'ذ': ['د', 'ر'],
            'ر': ['ز', 'د', 'ذ'],
            'ز': ['ر', 'د'],
            'س': ['ش', 'ص'],
            'ش': ['س', 'ص'],
            'ص': ['ض', 'س', 'ش'],
            'ض': ['ص', 'ظ'],
            'ط': ['ظ', 'ض'],
            'ظ': ['ط', 'ض'],
            'ع': ['غ', 'ح', 'خ'],
            'غ': ['ع', 'ح'],
            'ف': ['ق', 'ك'],
            'ق': ['ف', 'ك'],
            'ك': ['ف', 'ق', 'ل'],
            'ه': ['ة', 'ح'],
            'ة': ['ه', 'ت'],
        }

    def validate_and_correct(self, ocr_text: str) -> Dict:
        """Full validation and correction pipeline."""
        # Step 1: Basic font validation
        validation = validate_text(ocr_text, self.fonts_data)

        # Step 2: Apply font-based corrections
        corrected, font_corrections = correct_with_fonts(ocr_text, self.fonts_data)

        # Step 3: Apply known confusion patterns
        confusion_corrections = self._apply_confusion_patterns(corrected)

        # Step 4: Re-validate
        final_validation = validate_text(confusion_corrections["text"], self.fonts_data)

        return {
            "original": ocr_text,
            "corrected": confusion_corrections["text"],
            "font_corrections": font_corrections,
            "confusion_corrections": confusion_corrections["corrections"],
            "initial_validation": validation,
            "final_validation": final_validation,
            "improvement": final_validation["validation_rate"] - validation["validation_rate"]
        }

    def _apply_confusion_patterns(self, text: str) -> Dict:
        """Apply known Arabic character confusion patterns."""
        corrections = []
        corrected = list(text)

        for i, char in enumerate(text):
            if char in self.known_confusions:
                # Check if this character appears in an unusual context
                context = text[max(0, i-2):i+3]

                # Simple heuristic: if surrounded by medical terms, check dictionary
                # This would be enhanced with actual word context
                pass

        return {
            "text": ''.join(corrected),
            "corrections": corrections
        }


def main():
    parser = argparse.ArgumentParser(
        description="Validate OCR using Font Glyphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python font_glyph_validator.py --fonts fonts.json --ocr ocr.txt
  python font_glyph_validator.py --fonts fonts.json --ocr ocr.txt --output corrected.txt
  python font_glyph_validator.py --build-index fonts.json --output glyph_index.json
        """
    )

    parser.add_argument("--fonts", required=True, help="Font data JSON from PDF Grabber")
    parser.add_argument("--ocr", help="OCR text file to validate")
    parser.add_argument("--output", "-o", help="Output corrected file")
    parser.add_argument("--build-index", action="store_true",
                        help="Build and save character index")

    args = parser.parse_args()

    # Load font data
    fonts_data = load_font_data(args.fonts)
    print(f"📖 Loaded font data: {len(fonts_data.get('glyphs', []))} glyphs")

    if args.build_index:
        index = build_character_index(fonts_data)
        char_set = get_font_character_set(fonts_data)
        print(f"🔤 Character set: {len(char_set)} unique characters")
        print(f"   Sample: {list(char_set)[:20]}")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_chars": len(char_set),
                    "characters": sorted(list(char_set)),
                    "index": {k: len(v) for k, v in index.items()}
                }, f, ensure_ascii=False, indent=2)
            print(f"💾 Index saved to {args.output}")
        return

    if not args.ocr:
        print("❌ --ocr required for validation mode")
        return

    # Load OCR text
    with open(args.ocr, 'r', encoding='utf-8') as f:
        ocr_text = f.read()

    # Validate and correct
    validator = FontAwareOCRValidator(fonts_data)
    result = validator.validate_and_correct(ocr_text)

    print("\n" + "=" * 70)
    print("🔍 Font-Aware OCR Validation Report")
    print("=" * 70)
    print(f"Original length:     {len(result['original'])} chars")
    print(f"Corrected length:    {len(result['corrected'])} chars")
    print(f"Font corrections:    {len(result['font_corrections'])}")
    print(f"Initial validation:  {result['initial_validation']['validation_rate']:.1%}")
    print(f"Final validation:    {result['final_validation']['validation_rate']:.1%}")
    print(f"Improvement:         {result['improvement']:+.1%}")

    if result['font_corrections']:
        print("\n🔧 Font-based corrections:")
        for corr in result['font_corrections'][:10]:
            print(f"  [{corr['position']}] '{corr['original']}' → '{corr['corrected']}' "
                  f"(confidence: {corr['confidence']:.2f})")

    # Show unknown characters
    issues = result['final_validation']['issues']
    if issues:
        print(f"\n⚠️  Remaining unknown characters: {len(issues)}")
        for issue in issues[:5]:
            print(f"  '{issue['char']}' at pos {issue['position']} — context: '{issue['context']}'")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result['corrected'])
        print(f"\n💾 Corrected text saved to {args.output}")


if __name__ == "__main__":
    main()
