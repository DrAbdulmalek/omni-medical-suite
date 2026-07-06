"""
معالج النصوص الطبية - Text Handler
تنظيف وتوحيد ومعالجة التقارير الطبية العربية والإنجليزية
يدعم التشكيل والنصوص المختلطة والعلامات الطبية
"""

import re
import unicodedata
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union, Any

from ..utils.logger import get_logger

logger = get_logger("text_handler")


class TextHandler:
    """
    معالج نصوص طبية متكامل للغتين العربية والإنجليزية

    يدعم:
    - إزالة التشكيل العربي والتطبيع
    - تنظيف النصوص من الرموز الزائدة
    - استخراج أرقام المرضى والتواريخ
    - تقسيم التقارير إلى أقسام
    - التعامل مع النصوص المختلطة (عربي/إنجليزي/أرقام)

    الاستخدام:
        handler = TextHandler(language="ar")
        clean_text = handler.clean("التقرير يُظهر وجود ارتشاح رئوي...")
        sections = handler.split_report(report_text)
    """

    # أنماط التشكيل العربي
    ARABIC_DIACRITICS = re.compile(
        r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]"
    )

    # أنماط علامات الترقيم الزائدة
    PUNCTUATION_PATTERN = re.compile(r"[^\w\s\u0600-\u06FF\u0750-\u077F\.،؛:!؟\-\(\)/]")

    # الأرقام العربية والفارسية
    ARABIC_NUMERALS = "٠١٢٣٤٥٦٧٨٩"
    PERSIAN_NUMERALS = "۰۱۲۳۴۵۶۷۸۹"
    WESTERN_NUMERALS = "0123456789"

    # عناوين أقسام التقرير الشائعة
    REPORT_SECTIONS = {
        "ar": {
            "findings": [
                "النتائج", "الموجودات", "الوصف", "الفحص السريري",
                "الفحص الشعاعي", "الصورة الشعاعية", "النتيجة",
            ],
            "impression": [
                "الاستنتاج", "التشخيص", "الرأي", "الخلاصة",
                "التوصية", "الاقتراح",
            ],
            "history": [
                "القصة المرضية", "التاريخ المرضي", "الشكوى",
                "الاستطباب", "سبب المراجعة", "الأعراض",
            ],
            "technique": [
                "الطريقة", "التقنية", "البروتوكول", "المعدات",
            ],
        },
        "en": {
            "findings": [
                "Findings", "Description", "Observations", "Results",
                "Radiographic Findings",
            ],
            "impression": [
                "Impression", "Conclusion", "Diagnosis", "Recommendation",
                "Summary",
            ],
            "history": [
                "History", "Clinical History", "Indication", "Reason for Exam",
            ],
            "technique": [
                "Technique", "Protocol", "Equipment",
            ],
        },
    }

    # الكيانات الطبية الشائعة (أنماط Regex)
    MEDICAL_PATTERNS = {
        "measurements": {
            "pattern": r"(\d+(?:\.\d+)?)\s*(?:سم|mm|cm|mL|مل|μg|mg|كغ|kg|%)\b",
            "description": "القياسات والأبعاد",
        },
        "laterality": {
            "pattern": r"\b(?:الأيمن|الأيسر|يمين|يسار|بيلاتيرال|ثنائي الجانب|Bilateral|Right|Left|laterality)\b",
            "description": "الجانبية",
        },
        "severity": {
            "pattern": r"\b(?:خفيف|متوسط|شديد|حاد|مزمن|صغير|كبير|مبكر|متقدم|mild|moderate|severe|acute|chronic)\b",
            "description": "درجة الشدة",
        },
        "negation": {
            "pattern": r"\b(?:لا|غير|بدون|نفي|سالب|يمكن نفي|لا يوجد|no|without|negative|absent|denied)\b",
            "description": "النفي",
        },
        "uncertainty": {
            "pattern": r"\b(?:ربما|محتمل|يشتبه|غير مؤكد|يحتمل|probable|possible|suspected|uncertain|suggestive)\b",
            "description": "عدم اليقين",
        },
    }

    def __init__(self, language: str = "ar", normalize_arabic: bool = True):
        """
        Args:
            language: اللغة الرئيسية (ar, en, both)
            normalize_arabic: تطبيع الأحرف العربية
        """
        self.language = language
        self.normalize_arabic = normalize_arabic

    def clean(self, text: str) -> str:
        """
        تنظيف النص الطبي وإعداده للمعالجة

        الخطوات:
        1. إزالة التشكيل العربي
        2. توحيد الأرقام العربية إلى غربية
        3. إزالة الرموز الزائدة
        4. توحيد المسافات المتعددة
        5. إزالة الأسطر الفارغة المتكررة

        Args:
            text: النص الخام

        Returns:
            النص المنظّف
        """
        if not text:
            return ""

        cleaned = text

        # إزالة التشكيل العربي
        if self.normalize_arabic:
            cleaned = self.ARABIC_DIACRITICS.sub("", cleaned)
            cleaned = self._normalize_arabic_chars(cleaned)

        # توحيد الأرقام
        cleaned = self._normalize_numerals(cleaned)

        # إزالة الرموز الزائدة (مع الحفاظ على علامات الترقيم المهمة)
        cleaned = self.PUNCTUATION_PATTERN.sub(" ", cleaned)

        # توحيد المسافات
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # إزالة الأسطر الفارغة
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # إزالة أحرف التحكم
        cleaned = "".join(
            c for c in cleaned
            if not unicodedata.category(c).startswith("C") or c in "\n\r\t"
        )

        return cleaned.strip()

    def split_report(self, text: str) -> Dict[str, str]:
        """
        تقسيم التقرير الطبي إلى أقسام منطقية

        Args:
            text: نص التقرير الكامل

        Returns:
            قاموس {اسم_القسم: محتوى_القسم}
        """
        sections = {
            "header": "",
            "history": "",
            "technique": "",
            "findings": "",
            "impression": "",
            "recommendations": "",
        }

        lines = text.split("\n")
        current_section = "header"
        section_content = {k: [] for k in sections}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # محاولة التعرف على عنوان قسم
            detected = self._detect_section(stripped)
            if detected:
                current_section = detected
                # إزالة عنوان القسم من المحتوى
                section_title = stripped
                # محاولة إزالة الرموز الزخرفية من العنوان
                section_title = re.sub(r"^[\-=#*]+\s*", "", section_title)
                section_title = re.sub(r"\s*[\-=#*]+$", "", section_title)
                if len(section_title) > 50:
                    # ليس عنواناً بل سطر عادي
                    section_content[current_section].append(stripped)
            else:
                section_content[current_section].append(stripped)

        # تجميع الأقسام
        for key in sections:
            sections[key] = "\n".join(section_content[key]).strip()

        return sections

    def extract_medical_patterns(self, text: str) -> Dict[str, List[str]]:
        """
        استخراج الأنماط الطبية من النص باستخدام التعبيرات النمطية

        Args:
            text: النص الطبي

        Returns:
            قاموس {نوع_النمط: قائمة_المطابقات}
        """
        results = {}
        for pattern_name, pattern_info in self.MEDICAL_PATTERNS.items():
            matches = re.findall(pattern_info["pattern"], text, re.IGNORECASE)
            results[pattern_name] = matches
            if matches:
                logger.debug(f"  {pattern_info['description']}: {matches}")
        return results

    def detect_negation(self, text: str) -> Dict[str, Any]:
        """
        كشف الجمل المنفية في التقرير الطبي
        حيوي لتجنب تدريب النموذج على نتائج سلبية كإيجابية

        Args:
            text: النص الطبي

        Returns:
            قاموس {النص: {is_negated: bool, negation_scope: str}}
        """
        sentences = re.split(r"[.！。!؟?؛;]", text)
        results = {}

        negation_words = [
            "لا يوجد", "لا يُظهر", "بدون", "غير موجود", "نفي",
            "سالب", "طبيعي", "within normal", "no evidence", "negative",
            "no", "without", "absent", "normal", "unremarkable",
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 5:
                continue

            is_negated = any(
                neg in sentence.lower()
                for neg in negation_words
            )

            results[sentence] = {
                "is_negated": is_negated,
                "negation_words": [
                    neg for neg in negation_words if neg in sentence.lower()
                ],
            }

        return results

    def extract_measurements(self, text: str) -> List[Dict[str, Any]]:
        """
        استخراج القياسات الطبية من النص

        Args:
            text: النص الطبي

        Returns:
            قائمة بالقياسات {القيمة, الوحدة, السياق}
        """
        results = []
        pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(سم|mm|cm|mL|مل|μg|mg|كغ|kg|%)\b")

        for match in pattern.finditer(text):
            value = float(match.group(1))
            unit = match.group(2)

            # استخراج السياق (الجملة المحيطة)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()

            results.append({
                "value": value,
                "unit": unit,
                "context": context,
                "position": match.start(),
            })

        return results

    def batch_process_reports(
        self,
        directory: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        extensions: Tuple[str, ...] = (".txt", ".text", ".report"),
    ) -> List[Dict[str, Any]]:
        """
        معالجة مجموعة تقارير بشكل جماعي

        Args:
            directory: مجلد التقارير
            output_dir: مجلد حفظ النتائج (لا شيء = لا حفظ)
            extensions: صيغ الملفات

        Returns:
            قائمة بالنتائج
        """
        directory = Path(directory)
        results = []

        files = []
        for ext in extensions:
            files.extend(directory.rglob(f"*{ext}"))
        files = sorted(set(files))

        logger.info(f"معالجة {len(files)} تقرير من {directory.name}")

        for f in files:
            try:
                raw_text = f.read_text(encoding="utf-8")
                cleaned = self.clean(raw_text)
                sections = self.split_report(cleaned)
                patterns = self.extract_medical_patterns(cleaned)
                negations = self.detect_negation(cleaned)
                measurements = self.extract_measurements(cleaned)

                result = {
                    "file": str(f),
                    "raw_text": raw_text,
                    "cleaned_text": cleaned,
                    "sections": sections,
                    "patterns": patterns,
                    "negations": negations,
                    "measurements": measurements,
                    "text_length": len(cleaned),
                }
                results.append(result)

                # حفظ الملف المنظف
                if output_dir:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    out_path = output_dir / f"{f.stem}_cleaned.txt"
                    out_path.write_text(cleaned, encoding="utf-8")

            except Exception as e:
                logger.error(f"فشل معالجة {f.name}: {e}")
                results.append({"file": str(f), "error": str(e)})

        logger.info(f"تمت معالجة {len([r for r in results if 'error' not in r])} تقرير بنجاح")
        return results

    # ===== دوال مساعدة داخلية =====

    def _normalize_arabic_chars(self, text: str) -> str:
        """توحيد الأحرف العربية"""
        # توحيد الألف
        text = text.replace("إ", "ا").replace("أ", "ا").replace("آ", "ا").replace("ٱ", "ا")
        # توحيد التاء المربوطة والهاء
        text = text.replace("ة", "ه")
        # توحيد الياء
        text = text.replace("ئ", "ي").replace("ى", "ي")
        # توحيد الواو
        text = text.replace("ؤ", "و")
        return text

    def _normalize_numerals(self, text: str) -> str:
        """تحويل الأرقام العربية والفارسية إلى غربية"""
        result = text
        for i, arabic_num in enumerate(self.ARABIC_NUMERALS):
            result = result.replace(arabic_num, self.WESTERN_NUMERALS[i])
        for i, persian_num in enumerate(self.PERSIAN_NUMERALS):
            result = result.replace(persian_num, self.WESTERN_NUMERALS[i])
        return result

    def _detect_section(self, line: str) -> Optional[str]:
        """كشف عنوان قسم في التقرير"""
        line_lower = line.strip().lower()

        for lang in ["ar", "en"]:
            if self.language != "both" and self.language != lang:
                continue
            for section_name, keywords in self.REPORT_SECTIONS[lang].items():
                for keyword in keywords:
                    if keyword.lower() in line_lower and len(line.strip()) < 60:
                        return section_name

        return None
