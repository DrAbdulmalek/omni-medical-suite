from src.ocr.rtl_utils import ArabicRTLFixer


class TestArabicRTLFixer:
    def test_normalizes_presentation_forms(self):
        fixer = ArabicRTLFixer()
        assert fixer.normalize_presentation_forms("ﺍﻟﺴﻼﻡ") == "السلام"

    def test_fixes_reversed_arabic_tokens_when_forced(self):
        fixer = ArabicRTLFixer()
        text = "ضيرملا مسا"
        assert fixer.fix_text(text, force=True) == "اسم المريض"

    def test_preserves_numbers_while_fixing_arabic(self):
        fixer = ArabicRTLFixer()
        text = "2026/07/12 خيرات"
        assert fixer.fix_text(text, force=True) == "2026/07/12 تاريخ"
