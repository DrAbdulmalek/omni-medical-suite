# src/spellcheck/hybrid_spell_checker.py
import difflib
import json
import re


class HybridSpellChecker:
    def __init__(self, dict_path="data/arabic_medical_dict.json"):
        self.medical_dict = self._load_dict(dict_path)
        self.digit_fixes = {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"}

    def _load_dict(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _try_digit_fix(self, word):
        for k, v in self.digit_fixes.items():
            word = word.replace(k, v)
        return word

    def auto_correct(self, text: str) -> str:
        words = re.findall(r'\w+|[^\w\s]', text)
        corrected = []

        for w in words:
            if not w.isalnum() and not re.match(r'[\u0600-\u06FF]', w):
                corrected.append(w)
                continue

            fixed = self._try_digit_fix(w)

            # Medical dict priority
            if fixed in self.medical_dict:
                corrected.append(self.medical_dict[fixed])
                continue

            # Fuzzy match
            candidates = difflib.get_close_matches(fixed, list(self.medical_dict.values()), n=1, cutoff=0.85)
            corrected.append(candidates[0] if candidates else fixed)

        return " ".join(corrected)
