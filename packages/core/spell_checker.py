"""
modules/core/spell_checker.py — Hybrid Spell Checker v7.0
مدقق إملائي هجين يكتشف اللغة تلقائياً ويدعم العربية/الإنجليزية/الألمانية

v7.0 changes:
- إضافة enhance_digit_recognition() (من src/correction.py)
- إضافة spell_correct_word() (تصحيح كلمة واحدة مع digit recognition)
- الملف هو الآن Backend الموحّد — src/correction.py يُفوّض إليه بالكامل

v6.0 changes:
- دمج TECHNICAL_KEYWORDS + PYTHON_KEYWORDS من src/correction.py مباشرة
- حماية المصطلحات البرمجية من التصحيح الخاطئ (المراجعة المعمارية)
- إضافة _is_protected_word() مع دعم الكلمات المخصصة
- get_suggestions/auto_correct/check_text تتجاوز الكلمات المحمية

PR #92 runtime integration:
- OCR maps are resolved through SpecialtyDictionaryRouter.
- The production spell checker classifies the current document when no
  specialty is supplied and activates only the applicable OCR resources.
- Protected technical vocabulary is imported as protection only; terminology
  and TMX are never converted into arbitrary replacement rules.
"""
import json
import logging
import re
from difflib import get_close_matches
from pathlib import Path

logger = logging.getLogger(__name__)
ARABIC_FIXES_PATH = "data/dictionaries/ocr_corrections_safe.json"
_AR_RE = re.compile(r'[\u0600-\u06ff]')
_EN_RE = re.compile(r'[a-zA-Z]')

_DECIMAL_RE = re.compile(r"(?:\d+[.,]\d+|[٠-٩]+[٫٬،][٠-٩]+)")
_DOSE_RE = re.compile(r"(?:\d+(?:[.,]\d+)?|[٠-٩]+(?:[٫٬،][٠-٩]+)?)\s*(?:mg|ml|g|mcg|µg|ug|IU|units?|ملغ|مغ|مل|جم|مجم)\b", re.IGNORECASE)
_NEGATION_RE = re.compile(r"(?:^|\s)(?:لا\s+يعطى|لا\s+يوجد|ليس\s+لديه|لم\s+|لن\s+|غير\s+|بدون\s+)")


def _is_medical_safety_token(word: str) -> bool:
    stripped = word.strip(".,;:!?\"'()-")
    return bool(stripped and (_DECIMAL_RE.fullmatch(stripped) or _DOSE_RE.fullmatch(stripped)))


def _has_negated_statement(text: str) -> bool:
    return bool(text and _NEGATION_RE.search(text.strip()))


TECHNICAL_KEYWORDS = {
    "python", "pythonistas", "scraping", "parsing", "ocr",
    "batch", "programming", "script", "database", "configure",
    "setup", "env", "immutable", "concatenation", "tuples",
    "dictionaries", "debugging", "programmatically", "spreadsheet",
    "integers", "float", "boolean", "syntax", "web",
    "etl", "dataframe", "json", "csv", "yaml", "markdown",
    "mermaid", "repository", "clone", "commit", "push",
    "repl", "dpi", "api", "gpu", "cpu", "ram", "rom",
    "lora", "huggingface", "transformers", "pytorch", "tensorboard",
    "printouts", "involve", "scattered", "skyrocketed", "stacked",
    "affectionately", "serpentine", "cryptic", "sophisticated",
    "intricate", "throwaway", "surreal", "conventions",
    "trade", "off", "boot", "camps",
    "comprehensions", "replication", "precedence", "modulo",
    "exponent", "traceback", "overriding",
}

PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
    "try", "while", "with", "yield",
    "print", "input", "len", "range", "type", "int", "str", "float",
    "list", "dict", "set", "tuple", "bool", "open", "file", "super",
    "self", "cls", "init", "repr", "main", "name", "args", "kwargs",
    "append", "extend", "pop", "sort", "join", "split", "strip",
    "format", "replace", "lower", "upper", "title", "capitalize",
    "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr",
    "module", "package",
}

_PROTECTED_WORDS_LOWER: set = set()


def _rebuild_protected_set():
    global _PROTECTED_WORDS_LOWER
    _PROTECTED_WORDS_LOWER = {k.lower() for k in TECHNICAL_KEYWORDS} | {k.lower() for k in PYTHON_KEYWORDS}


_rebuild_protected_set()


class HybridSpellChecker:
    """مدقق إملائي هجين مع توجيه القواميس حسب التخصص."""

    def __init__(self, arabic_fixes_path: str = ARABIC_FIXES_PATH, specialty: str | None = None) -> None:
        from packages.medical.dictionary_router import SpecialtyDictionaryRouter

        self._fixes_path = Path(arabic_fixes_path)
        self._specialty = specialty
        self._router = SpecialtyDictionaryRouter(specialty or "general_medical")
        self._arabic_fixes: dict = {}
        self._spell_en = self._spell_ar = self._spell_de = None
        self._custom_protected: set = set()
        self._load_fixes()
        # General/technical vocabulary is a protected lexicon, never a
        # replacement map. It is small enough to load eagerly.
        self.add_protected_words(list(self._router.protected_lexicon()))

    def _load_fixes(self) -> None:
        try:
            # The router determines which audited OCR sources are applicable.
            # An explicit constructor path remains supported and wins on key
            # conflicts for backward compatibility.
            self._arabic_fixes = self._router.ocr_corrections()
            if self._fixes_path.exists():
                with open(self._fixes_path, encoding="utf-8") as f:
                    explicit = json.load(f)
                if isinstance(explicit, dict):
                    self._arabic_fixes.update(explicit)
        except Exception as e:
            logger.warning("arabic_fixes: %s", e)

    def _activate_specialty(self, text: str) -> None:
        """Select a registry namespace from explicit or classified specialty."""
        if self._specialty:
            self._router.set_specialty(self._specialty)
            self._load_fixes()
            return
        try:
            from packages.core.classifier import MedicalClassifier
            result = MedicalClassifier().classify_with_fallback(text, min_confidence=0.15)
            self._router.set_specialty(result.get("category", "general_medical"))
            self._load_fixes()
        except Exception as e:
            logger.debug("specialty classification unavailable: %s", e)
            self._router.set_specialty("general_medical")

    def set_specialty(self, specialty: str | None) -> None:
        self._specialty = specialty
        self._router.set_specialty(specialty or "general_medical")
        self._load_fixes()

    @property
    def specialty(self) -> str:
        return self._router.specialty

    def active_dictionary_names(self) -> list[str]:
        """Return registry resources actually active for this checker instance."""
        return [spec.name for spec in self._router.specs if spec.path.exists()]

    def reload_fixes(self) -> None:
        self._load_fixes()

    def _sc(self, lang: str):
        attr = f"_spell_{lang}"
        if getattr(self, attr) is None:
            try:
                from spellchecker import SpellChecker
                sc = SpellChecker(language=lang, distance=1)
                all_protected = list(TECHNICAL_KEYWORDS | PYTHON_KEYWORDS)
                if all_protected:
                    sc.word_frequency.load_words(all_protected)
                setattr(self, attr, sc)
            except Exception:
                setattr(self, attr, False)
        obj = getattr(self, attr)
        return obj if obj else None

    @staticmethod
    def is_protected_word(word: str) -> bool:
        if not word:
            return False
        return word.lower() in _PROTECTED_WORDS_LOWER

    def add_protected_words(self, words: list[str]) -> None:
        new_words = [w.strip().lower() for w in words if w.strip()]
        if new_words:
            self._custom_protected.update(new_words)
            global _PROTECTED_WORDS_LOWER
            _PROTECTED_WORDS_LOWER = _PROTECTED_WORDS_LOWER | self._custom_protected
            logger.debug("تم إضافة %d كلمة محمية مخصصة (المجموع: %d)", len(new_words), len(_PROTECTED_WORDS_LOWER))

    def _is_protected(self, word: str) -> bool:
        if not word:
            return False
        return word.lower() in (_PROTECTED_WORDS_LOWER | self._custom_protected)

    def detect_language(self, text: str) -> str:
        if not text or not text.strip():
            return "en"
        clean = text.replace(" ", "")
        ar = len(_AR_RE.findall(clean)) / max(len(clean), 1)
        en = len(_EN_RE.findall(clean)) / max(len(clean), 1)
        if ar > 0.50:
            return "ar"
        if en > 0.50:
            de_chars = len(re.findall(r'[äöüßÄÖÜ]', text))
            de_words = sum(1 for w in ["der", "die", "das", "und", "ist", "nicht"] if w in text.lower())
            return "de" if (de_chars > 0 or de_words >= 2) else "en"
        if ar > 0.15 or en > 0.15:
            return "mixed"
        return "en"

    def get_suggestions(self, word: str, lang: str | None = None, n: int = 5) -> list:
        if not word or not word.strip():
            return []
        if self._is_protected(word) or _is_medical_safety_token(word) or _has_negated_statement(word):
            return []

        if lang is None:
            lang = self.detect_language(word)
        suggestions = []

        if lang in ("ar", "mixed") and word in self._arabic_fixes:
            fixed = self._arabic_fixes[word]
            if fixed != word:
                suggestions.append(fixed)

        try:
            from packages.core.word_trainer import WordCorrectionDB
            db = WordCorrectionDB()
            best = db.get_best_correction(word, lang=lang)
            if best and best != word and best not in suggestions:
                suggestions.insert(0, best)
            for s in db.get_suggestions(word, lang=lang, n=n):
                if s != word and s not in suggestions:
                    suggestions.append(s)
        except Exception:
            pass

        lang_map = {"ar": "ar", "en": "en", "de": "de", "mixed": "en"}
        sc_lang = lang_map.get(lang, "en")
        sc = self._sc(sc_lang)
        if sc:
            try:
                if word.lower() not in sc:
                    for c in list(sc.candidates(word) or [])[:n]:
                        if c != word and c not in suggestions:
                            suggestions.append(c)
            except Exception:
                pass

        _is_known_correct = word in self._arabic_fixes.values()
        if (not suggestions and lang in ("ar", "mixed")
                and not _is_known_correct and len(word) >= 4):
            pool = list(self._arabic_fixes.keys())
            for c in get_close_matches(word, pool, n=n, cutoff=0.85):
                if c not in suggestions and c in self._arabic_fixes:
                    suggestions.append(self._arabic_fixes[c])

        seen, unique = set(), []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique[:n]

    _DIGIT_CORRECTIONS = {
        "O": "0", "o": "0", "I": "1", "l": "1", "|": "1",
        "Z": "2", "z": "2", "S": "5", "s": "5", "G": "6",
        "T": "7", "t": "7", "B": "8",
    }

    def _try_digit_fix(self, word: str):
        clean = word.strip(".,;:!?\"'()-")
        if not clean or not all(c.isalnum() or c in "_-/" for c in clean):
            return None
        if not any(c.isdigit() for c in clean):
            return None
        fixed = clean
        for letter, digit in self._DIGIT_CORRECTIONS.items():
            fixed = fixed.replace(letter, digit)
        if fixed != clean and fixed.isdigit():
            return fixed
        return None

    def auto_correct(self, word: str) -> tuple:
        if _is_medical_safety_token(word) or _has_negated_statement(word):
            return word, self.detect_language(word)
        digit_fix = self._try_digit_fix(word)
        if digit_fix is not None:
            return digit_fix, "en"

        lang = self.detect_language(word)
        if self._is_protected(word):
            return word, lang
        if lang in ("ar", "mixed") and word in self._arabic_fixes:
            return self._arabic_fixes[word], lang
        sugg = self.get_suggestions(word, lang=lang, n=1)
        return (sugg[0] if sugg else word), lang

    def check_text(self, text: str) -> dict:
        self._activate_specialty(text)
        lang = self.detect_language(text)
        results = []
        for w in text.split():
            corrected, _ = self.auto_correct(w)
            results.append({
                "word": w, "corrected": corrected,
                "suggestions": self.get_suggestions(w, lang=lang, n=3),
                "changed": corrected != w,
                "protected": self._is_protected(w),
            })
        return {"lang": lang, "words": results, "total": len(results), "specialty": self.specialty,
                "active_dictionaries": self.active_dictionary_names()}

    def enhance_digit_recognition(self, text: str) -> str:
        if not text:
            return text
        words = text.split()
        corrected = []
        for word in words:
            clean = word.strip(".,;:!?\"'()-")
            if clean and all(c.isalnum() or c in "_-/" for c in clean) and any(c.isdigit() for c in clean):
                fixed = clean
                for letter, digit in self._DIGIT_CORRECTIONS.items():
                    fixed = fixed.replace(letter, digit)
                if fixed != clean and fixed.isdigit():
                    corrected.append(word.replace(clean, fixed))
                    continue
            corrected.append(word)
        return " ".join(corrected)

    def _looks_like_digit_corruption(self, word: str) -> bool:
        if not word:
            return False
        has_digit = any(c.isdigit() for c in word)
        has_letter_digit = any(c in self._DIGIT_CORRECTIONS for c in word)
        return has_digit and has_letter_digit

    def correct_text(self, text: str) -> str:
        if not text or not text.strip():
            return text
        self._activate_specialty(text)
        if _has_negated_statement(text):
            return text
        words = text.split()
        corrected = []
        for w in words:
            clean = w.strip(".,;:!?\"'()-")
            if clean and self._is_protected(clean):
                corrected.append(w)
                continue
            if not clean or _is_medical_safety_token(clean):
                corrected.append(w)
                continue

            if self._looks_like_digit_corruption(clean):
                digit_fixed = self.enhance_digit_recognition(clean)
                stripped = digit_fixed.strip(".,;:!?\"'()-")
                if stripped and stripped.isdigit():
                    corrected.append(w.replace(clean, digit_fixed))
                    continue
                clean = digit_fixed

            c, _ = self.auto_correct(clean)
            corrected.append(w.replace(clean, c))
        return self.enhance_digit_recognition(" ".join(corrected))

    def spell_correct_word(self, word: str) -> str:
        word = word.strip()
        if not word:
            return ""
        if _is_medical_safety_token(word) or _has_negated_statement(word) or self._is_protected(word):
            return word
        if self._looks_like_digit_corruption(word):
            digit_fixed = self.enhance_digit_recognition(word)
            stripped = digit_fixed.strip(".,;:!?\"'()-")
            if stripped and stripped.isdigit():
                return digit_fixed
            word = digit_fixed
        corrected, _ = self.auto_correct(word)
        return self.enhance_digit_recognition(corrected)

    def get_protected_count(self) -> dict:
        return {
            "technical_keywords": len(TECHNICAL_KEYWORDS),
            "python_keywords": len(PYTHON_KEYWORDS),
            "custom_words": len(self._custom_protected),
            "total_protected": len(_PROTECTED_WORDS_LOWER),
        }
