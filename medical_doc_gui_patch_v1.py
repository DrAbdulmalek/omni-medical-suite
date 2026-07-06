"""
medical_doc_gui_patch.py — Integration Patch for Medical OCR Postprocessor v13.2
================================================================================
This patch integrates medical-ocr-postprocessor into medical_doc_gui workflow.
Drop-in replacement/addition for the OCR result processing pipeline.

Author: Dr. Abdulmalek
Version: 13.2-patch (Final)
Date: 2026-06-04
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ArabicMedicalOCRPostprocessor:
    """
    Post-processor for Arabic medical OCR output.
    Integrates dictionary-based correction, regex patterns, and medical term validation.
    """

    def __init__(self, dictionary_path: Optional[str] = None):
        self.dictionary = {"corrections": {}, "phrases": {}, "regex_patterns": []}
        self.correction_log = []
        self.stats = {"total_corrections": 0, "phrase_corrections": 0, "regex_corrections": 0}

        # Load dictionary
        if dictionary_path and os.path.exists(dictionary_path):
            self.load_dictionary(dictionary_path)
        else:
            for path in [
                "arabic_medical_dict.json",
                "data/arabic_medical_dict.json",
                "/mnt/agents/output/arabic_medical_dict.json",
                os.path.join(os.path.dirname(__file__), "arabic_medical_dict.json")
            ]:
                if os.path.exists(path):
                    self.load_dictionary(path)
                    break

    def load_dictionary(self, path: str):
        """Load correction dictionary from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.dictionary = json.load(f)
            meta = self.dictionary.get("_meta", {})
            logger.info(f"Loaded dictionary: {meta.get('name', 'Unknown')} v{meta.get('version', '?')} — {meta.get('total_entries', 0)} entries")
        except Exception as e:
            logger.error(f"Failed to load dictionary: {e}")

    def normalize_arabic(self, text: str) -> str:
        """Normalize Arabic text for better matching."""
        text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        text = text.replace('ة', 'ه')
        text = text.replace('ى', 'ي')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def apply_word_corrections(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply word-level dictionary corrections."""
        corrections = self.dictionary.get("corrections", {})
        applied = []
        words = text.split()
        new_words = []

        for word in words:
            original = word
            # Try exact match
            if word in corrections:
                corrected = corrections[word]
                if corrected != original:
                    applied.append({
                        "type": "word",
                        "original": original,
                        "corrected": corrected,
                        "position": len(new_words)
                    })
                    word = corrected
            else:
                # Try normalized match
                norm = self.normalize_arabic(word)
                for key, val in corrections.items():
                    if self.normalize_arabic(key) == norm and key != word:
                        applied.append({
                            "type": "word_normalized",
                            "original": original,
                            "corrected": val,
                            "position": len(new_words)
                        })
                        word = val
                        break

            new_words.append(word)

        return ' '.join(new_words), applied

    def apply_phrase_corrections(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply phrase-level corrections (multi-word)."""
        phrases = self.dictionary.get("phrases", {})
        applied = []

        # Sort by length descending to avoid partial replacements
        sorted_phrases = sorted(phrases.items(), key=lambda x: len(x[0]), reverse=True)

        for wrong, correct in sorted_phrases:
            if wrong in text and wrong != correct:
                count = text.count(wrong)
                text = text.replace(wrong, correct)
                applied.append({
                    "type": "phrase",
                    "original": wrong,
                    "corrected": correct,
                    "count": count
                })

        return text, applied

    def apply_regex_corrections(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply regex-based corrections."""
        patterns = self.dictionary.get("regex_patterns", [])
        applied = []

        for pattern_def in patterns:
            pattern = pattern_def.get("pattern", "")
            replacement = pattern_def.get("replacement", "")
            desc = pattern_def.get("description", "")

            try:
                matches = list(re.finditer(pattern, text, re.MULTILINE))
                if matches:
                    text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
                    applied.append({
                        "type": "regex",
                        "pattern": pattern,
                        "replacement": replacement,
                        "description": desc,
                        "matches": len(matches)
                    })
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

        return text, applied

    def correct(self, text: str) -> Tuple[str, List[Dict], Dict]:
        """Main correction pipeline."""
        if not text or not text.strip():
            return text, [], {"total": 0}

        original = text
        all_corrections = []

        # Phase 1: Phrase corrections (highest priority)
        text, phrase_corrs = self.apply_phrase_corrections(text)
        all_corrections.extend(phrase_corrs)

        # Phase 2: Regex corrections
        text, regex_corrs = self.apply_regex_corrections(text)
        all_corrections.extend(regex_corrs)

        # Phase 3: Word-level corrections
        text, word_corrs = self.apply_word_corrections(text)
        all_corrections.extend(word_corrs)

        # Phase 4: Post-processing cleanup
        text = self._post_cleanup(text)

        stats = {
            "total": len(all_corrections),
            "phrase": len(phrase_corrs),
            "regex": len(regex_corrs),
            "word": len(word_corrs),
            "original_length": len(original),
            "corrected_length": len(text),
            "change_ratio": round((len(original) - len(text)) / max(len(original), 1), 3)
        }

        self.correction_log.append({
            "original": original,
            "corrected": text,
            "corrections": all_corrections,
            "stats": stats
        })

        logger.info(f"Applied {stats['total']} corrections: {stats['phrase']} phrases, {stats['regex']} regex, {stats['word']} words")

        return text, all_corrections, stats

    def _post_cleanup(self, text: str) -> str:
        """Final text cleanup."""
        # Fix spacing around Arabic punctuation
        text = re.sub(r'\s*([،\.])\s*', r'\1 ', text)

        # Fix multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Handle mixed western-eastern numerals and artifacts
        # Remove underscore before eastern numerals: _٢ → ٢
        text = re.sub(r'_([٠١٢٣٤٥٦٧٨٩])', r'\1', text)

        # Handle page numbers like "ذ59" → "-593-" (specific pattern)
        text = re.sub(r'^ذ(\d+)$', lambda m: f"-{m.group(1)}-", text, flags=re.MULTILINE)

        # Convert western numerals at line starts to eastern (only if standalone)
        def convert_line_start(match):
            num = match.group(1)
            eastern = num.translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))
            return f"{eastern}- "

        text = re.sub(r'^(\d+)-\s*', convert_line_start, text, flags=re.MULTILINE)

        # Trim
        text = text.strip()
        return text

    def validate_medical_terms(self, text: str) -> List[Dict]:
        """Validate extracted text against known medical terms."""
        issues = []

        # Check for common OCR artifacts (ignore pure numbers and short tokens that are numbers)
        artifacts = [
            (r'[_\^\&\%\$\#\@\!]+', "Special character artifact"),
        ]

        for pattern, desc in artifacts:
            matches = re.finditer(pattern, text)
            for m in matches:
                issues.append({
                    "type": "artifact",
                    "description": desc,
                    "text": m.group(),
                    "position": m.start()
                })

        # Check for uncorrected known misspellings (only check full words)
        known_bad = ["المعتويات", "القبنة", "الشثل", "الشن", "الشنل", "العضنية", 
                     "الورث", "=رية", "انناك", "القفدا", "انقدم", "شازكو", "Rickels"]

        for bad in known_bad:
            # Use word boundary check to avoid partial matches
            if re.search(r'\b' + re.escape(bad) + r'\b', text):
                issues.append({
                    "type": "uncorrected_misspelling",
                    "description": f"Known misspelling still present: {bad}",
                    "text": bad,
                    "suggestion": self.dictionary.get("corrections", {}).get(bad, "?")
                })

        return issues


def patch_ocr_result(ocr_result: Dict[str, Any], 
                     dictionary_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Drop-in function to patch an OCR result dict.

    Usage in medical_doc_gui:
        from medical_doc_gui_patch import patch_ocr_result
        result = run_ocr(image)
        patched = patch_ocr_result(result)
    """
    if not isinstance(ocr_result, dict):
        return ocr_result

    raw_text = ocr_result.get("raw_text", "")
    if not raw_text:
        return ocr_result

    pp = ArabicMedicalOCRPostprocessor(dictionary_path)
    corrected, corrections, stats = pp.correct(raw_text)
    issues = pp.validate_medical_terms(corrected)

    enhanced = dict(ocr_result)
    enhanced["corrected_text"] = corrected
    enhanced["corrections"] = corrections
    enhanced["correction_count"] = len(corrections)
    enhanced["postprocessor_stats"] = stats
    enhanced["validation_issues"] = issues
    enhanced["validation_issue_count"] = len(issues)
    enhanced["confidence_post_corrected"] = _estimate_confidence(raw_text, corrected, stats, issues)

    enhanced["postprocessor"] = {
        "version": "13.2-patch",
        "dictionary_loaded": bool(pp.dictionary.get("corrections")),
        "dictionary_entries": pp.dictionary.get("_meta", {}).get("total_entries", 0)
    }

    logger.info(f"Post-processed: {stats['total']} corrections, {len(issues)} issues remaining")

    return enhanced


def _estimate_confidence(raw: str, corrected: str, stats: Dict, issues: List) -> float:
    """Estimate realistic confidence after correction."""
    base = 0.85

    if stats["total"] > 20:
        base -= 0.15
    elif stats["total"] > 10:
        base -= 0.08
    elif stats["total"] > 5:
        base -= 0.03

    if len(issues) > 10:
        base -= 0.15
    elif len(issues) > 5:
        base -= 0.08
    elif len(issues) > 0:
        base -= 0.03

    if abs(stats.get("change_ratio", 0)) > 0.1:
        base -= 0.05

    if len(corrected) > len(raw) * 0.8 and len(corrected) > 50:
        base += 0.05

    return max(0.0, min(1.0, round(base, 3)))


if __name__ == "__main__":
    test_input = {
        "raw_text": "ذ59\nجدول المعتويات\nا- أذيات المشاش واضطرابات\nالنمو\nRickels ع\n- الخر\n_٢\n٣- التهاب المفاصل\nالقيحى\nانناك\n٤- خلع الداغصة\nمتلازمة داء بر\nتن\nالفخذ\n٦- انزلاق مثاش ر\nان\n٧- المتلازمات فى الجراحة العطمية\nالهيكنية\nالتصفع\n٨- عسرات\nاف الخلق\nالاطر\nغياب\nالروحاء\nانقدم القفدا\n- الأوزام العطمية\nمفصل شازكو\nد الفقري\nالعمو\nتشوهات\nهات الخلقية فى الزنار الكتف\n التشو\n-١٤\nو عقابيله\nدا - الشثل\nالدماغي\nن }\n١٦- القبنة السحانية\n١٧- شن الأطفال\n٧٣\n٨ا- شنل الضفيرة العضنية\nاليد الشنية\n٢- الحثول العضنية\n=رية\n٢١- عسرة تصنع الورث التطو",
        "language": "ar",
        "engine": "auto",
        "confidence": 0.609,
        "filename": "Scanned Document-588.jpg"
    }

    print("=" * 70)
    print("MEDICAL OCR POSTPROCESSOR PATCH v13.2 — FINAL TEST")
    print("=" * 70)

    result = patch_ocr_result(test_input)

    print("\n📄 ORIGINAL (raw_text):")
    print(result["raw_text"])

    print("\n✅ CORRECTED (corrected_text):")
    print(result["corrected_text"])

    print("\n🔧 CORRECTIONS APPLIED:")
    for c in result["corrections"]:
        print(f"  • [{c['type']}] '{c.get('original', c.get('pattern', '?'))}' → '{c.get('corrected', c.get('replacement', '?'))}'")

    print("\n⚠️  VALIDATION ISSUES:")
    for issue in result["validation_issues"]:
        print(f"  • [{issue['type']}] {issue['description']}: '{issue['text']}'")

    print("\n📊 STATS:")
    print(json.dumps(result["postprocessor_stats"], ensure_ascii=False, indent=2))

    print(f"\n🎯 NEW CONFIDENCE: {result['confidence_post_corrected']}")
    print(f"📋 CORRECTION COUNT: {result['correction_count']}")
    print(f"⚠️  REMAINING ISSUES: {result['validation_issue_count']}")
