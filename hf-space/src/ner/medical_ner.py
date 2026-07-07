"""
Arabic Medical NER - استخراج الكيانات الطبية المسماة من النصوص العربية
========================================================================

This module provides rule-based Named Entity Recognition (NER) for
Arabic medical text. It uses compiled regex patterns to extract
medical entities such as drug names, dosages, diagnoses, body parts,
lab tests, frequencies, and durations.

هذه الوحدة توفر التعرف على الكيانات المسماة القائم على القواعد
للنصوص الطبية العربية. تستخدم أنماط regex مُجمّعة لاستخراج
الكيانات الطبية مثل أسماء الأدوية والجرعات والتشخيصات
وأجزاء الجسم والتحاليل والتكرار والمدد الزمنية.

Pure Python - no external dependencies required.
Python نقي - لا تتطلب مكتبات خارجية.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Pattern

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "تهيئة مستخرج الكيانات الطبية | Initializing medical NER"
_MSG_PATTERNS = "تم تجميع {n} نمط regex | Compiled {n} regex patterns"
_MSG_EXTRACTING = "جارٍ استخراج الكيانات من النص ({len} حرف) | Extracting entities from text ({len} chars)"
_MSG_FOUND = "تم العثور على {n} كيان | Found {n} entities"
_MSG_EMPTY = "النص فارغ | Text is empty"


class ArabicMedicalNER:
    """
    Rule-based Named Entity Recognition for Arabic medical text.

    التعرف على الكيانات المسماة القائم على القواعد للنصوص الطبية العربية.

    Supported entity types:
        - DRUG: Drug/medication names (أسماء الأدوية)
        - DOSAGE: Dosage amounts and units (الجرعات)
        - DIAGNOSIS: Medical diagnoses (التشخيصات)
        - BODY_PART: Anatomical terms (أجزاء الجسم)
        - LAB_TEST: Laboratory test names (التحاليل المخبرية)
        - FREQUENCY: Administration frequency (التكرار)
        - DURATION: Treatment duration (المدة الزمنية)

    This is a pure Python implementation using regex patterns.
    No ML models or external NLP libraries are required.
    """

    # Entity type labels
    DRUG = "DRUG"
    DOSAGE = "DOSAGE"
    DIAGNOSIS = "DIAGNOSIS"
    BODY_PART = "BODY_PART"
    LAB_TEST = "LAB_TEST"
    FREQUENCY = "FREQUENCY"
    DURATION = "DURATION"

    def __init__(self) -> None:
        """
        Initialize the NER system by building medical entity patterns.

        تهيئة نظام التعرف على الكيانات ببناء أنماط الكيانات الطبية.
        """
        logger.info(_MSG_INIT)
        self.patterns: Dict[str, List[Pattern]] = self._build_patterns()

        total_patterns = sum(len(p) for p in self.patterns.values())
        logger.info(_MSG_PATTERNS.format(n=total_patterns))

    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract medical entities from Arabic text.

        استخراج الكيانات الطبية من النص العربي.

        Args:
            text: Input text (typically OCR-extracted medical text).

        Returns:
            List of entity dictionaries, each with:
                - type (str): Entity type (DRUG, DOSAGE, etc.)
                - value (str): The matched text
                - start (int): Start character index in text
                - end (int): End character index in text
                - confidence (float): Confidence score (1.0 for regex matches)
        """
        if not text or not text.strip():
            logger.debug(_MSG_EMPTY)
            return []

        text_len = len(text)
        logger.info(_MSG_EXTRACTING.format(len=text_len))

        entities: List[Dict] = []
        seen_spans: List[Tuple[int, int]] = []  # Avoid overlapping entities

        for entity_type, pattern_list in self.patterns.items():
            for pattern in pattern_list:
                for match in pattern.finditer(text):
                    start = match.start()
                    end = match.end()
                    value = match.group()

                    # Skip overlapping entities (keep first match)
                    overlaps = any(
                        not (end <= s or start >= e)
                        for s, e in seen_spans
                    )
                    if overlaps:
                        continue

                    # Skip very short matches (likely false positives)
                    if len(value.strip()) < 2:
                        continue

                    seen_spans.append((start, end))

                    # Assign confidence based on match quality
                    confidence = self._compute_confidence(
                        entity_type, value, match
                    )

                    entities.append({
                        "type": entity_type,
                        "value": value,
                        "start": start,
                        "end": end,
                        "confidence": round(confidence, 3),
                    })

        # Sort by position in text
        entities.sort(key=lambda e: e["start"])

        logger.info(_MSG_FOUND.format(n=len(entities)))
        return entities

    def _build_patterns(self) -> Dict[str, List[Pattern]]:
        """
        Compile regex patterns for Arabic medical entity extraction.

        تجميع أنماط regex لاستخراج الكيانات الطبية العربية.

        Returns:
            Dictionary mapping entity types to lists of compiled patterns.
        """
        patterns: Dict[str, List[Pattern]] = {}

        # ============================================================
        # DRUG patterns - أسماء الأدوية
        # ============================================================
        # Common Arabic drug names with variations
        drug_names = [
            r"باراسيتامول", r"باراسيتامول", r"بنادول", r"بنادول",
            r"أموكسيسيلين", r"أموكسل", r"أموكسيسل",
            r"ميتفورمين", r"جلوكوفاج", r"جلوكوفاج",
            r"أسيكلوفير", r"زوفيراكس",
            r"أوميبرازول", r"لوسيك", r"أوميبرازول",
            r"سيتالوبرام", r"سيبراليكس", r"سيبرالكس",
            r"إنسولين", r"لانتوس", r"نوفوميكس", r"همالوج",
            r"وارفارين", r"كومادين",
            r"أسبرين", r"الأسبرين",
            r"إيبوبروفين", r"بروفين", r"أدفيل",
            r"كيتورولاك", r"تورادول",
            r"ترامادول", r"الترامادول",
            r"أموكسيدبين", r"نورفاسك",
            r"لوسارتان", r"لوزار",
            r"أملوديبين", r"نورفاسك",
            r"أتورفاستاتين", r"ليبيتور", r"ليبتور",
            r"كليبريكس", r"سيليكوكسيب", r"سيليبريكس",
            r"أزيثرومايسين", r"زيثروماكس", r"زيثروماكس",
            r"سيفالكسين", r"كيفليكس",
            r"ميترونيدازول", r"فلاجيل",
            r"ديكلوفيناك", r"فولتارين", r"فولتارين",
            r"أسيكلوفير", r"زوفيراكس",
            r"فالاسيكلوفير", r"فالتrex",
            r"سالبيوتامول", r"فنتولين", r"فينتولين",
            r"بوديسونيد", r"بولميكورت",
            r"فليوتيكاسون", r"فليكسوتايد",
            r"مونتيلوكاست", r"سنغولار", r"سنقلاير",
            r"لوراتادين", r"كلاريتين", r"كلاريتين",
            r"سيتيريزين", r"زيرتك", r"زيرتِك",
            r"فكسوفينادين", r"أليغرا",
            r"أوميبرازول", r"لوسيك",
            r"فاموتيدين", r"بيبسيد",
            r"رانيديدين", r"زانتاك",
            r"ألوبورينول", r"زيلوريك",
            r"كولشيسين",
            r"بريدنيزولون", r"بريدنيزون", r"دلتاسون",
            r"هيدروكورتيزون", r"كورتيزون",
            r"دكساميثازون", r"ديكورتان",
            r"فوروسيميد", r"لازيكس", r"لانسيكس",
            r"سبيرونولاكتون", r"ألداكتون",
            r"كابتوبريل", r"كابوتين",
            r"إنالابريل", r"إنابريل",
            r"فينكارمين", r"زانتاكس",
            r"دومبيريدون", r"موتيليوم",
            r"أوندانسيترون", r"زوفيران",
            r"ل operاميد", r"إيموديوم", r"إيموديوم",
            r"كروبوفين", r"لوبراميد", r"إيموديوم",
            r"ديفينهيدرامين", r"بينادريل",
            r"سيتريزين", r"زيرتك",
        ]

        # Also match drug names with common prefixes
        drug_prefix_patterns = [
            r"(?:قرص|حبة|كبسولة|أمبولة|شراب|معلق|كريم|مرهم|قطرة|بخاخ|لبوس|تحاميلة|حقنة)\s+[\u0600-\u06FF\s]{2,20}",
            r"[\u0600-\u06FF]{2,25}\s+(?:مغلف|ملغ|جم|ملي|وحدة)",
        ]

        # Generic drug pattern: Arabic text followed by mg/g/ml
        drug_generic = [
            r"[\u0600-\u06FF]{2,20}\s+\d+\s*(?:ملغ|مجم|جم|مللي|م\.م|وحدة عالمية|و\.د)",
        ]

        all_drug_patterns = drug_names + drug_prefix_patterns + drug_generic
        patterns[self.DRUG] = self._compile_patterns(all_drug_patterns)

        # ============================================================
        # DOSAGE patterns - الجرعات
        # ============================================================
        dosage_patterns = [
            # Number + unit
            r"\d+(?:\.\d+)?\s*(?:ملغ|مجم|جم|مللي|م\.م|غ|مكغ|ميكروغرام)",
            r"\d+\s*(?:وحدة عالمية|و\.د|وحدة)",
            # Fraction dosages
            r"(?:نصف|ربع|ثلاثة أرباع)\s*(?:قرص|حبة|كبسولة|أمبولة)",
            # Range dosages
            r"\d+\s*[-–-]\s*\d+\s*(?:ملغ|مجم|جم|مللي|م\.م)",
            # Dosage per kg
            r"\d+(?:\.\d+)?\s*(?:ملغ|مجم)\s*(?:لكل|لكل كيلو|/)\s*(?:كجم|كيلو|كغ|كج)",
            # Dose frequency combos
            r"\d+(?:\.\d+)?\s*(?:ملغ|مجم|جم)\s*(?:×|ضرب)\s*\d+",
            # Drops / teaspoons
            r"\d+\s*(?:قطرة|قطرات|معلقة|ملعقة|ملعقة صغيرة|ملعقة كبيرة)",
        ]
        patterns[self.DOSAGE] = self._compile_patterns(dosage_patterns)

        # ============================================================
        # DIAGNOSIS patterns - التشخيصات
        # ============================================================
        diagnosis_patterns = [
            # Common diseases
            r"(?:مرض|إصابة|حالة)\s+[\u0600-\u06FF\s]{2,25}",
            r"ارتفاع\s+(?:ضغط\s+)?(?:الدم|الضغط)",
            r"انخفاض\s+(?:ضغط\s+)?(?:الدم|الضغط)",
            r"السكري(?:\s+(?:النوع|نوع)\s+(?:الأول|الثاني|الاول|الثانى|2|1|II|I))?",
            r"داء\s+[\u0600-\u06FF\s]{2,15}",
            r"التهاب\s+[\u0600-\u06FF\s]{2,20}",
            r"انسداد\s+[\u0600-\u06FF\s]{2,20}",
            r"ارتخاء\s+[\u0600-\u06FF\s]{2,15}",
            r"تصلب\s+[\u0600-\u06FF\s]{2,15}",
            r"قرحة\s+[\u0600-\u06FF\s]{2,15}",
            r"حص(?:وة|يات)\s+[\u0600-\u06FF\s]{2,15}",
            r"كسور?\s+[\u0600-\u06FF\s]{0,15}",
            r"إصابة\s+[\u0600-\u06FF\s]{2,20}",
            r"نزيف\s+[\u0600-\u06FF\s]{2,15}",
            r"وذمة\s+[\u0600-\u06FF\s]{2,15}",
            r"فشل\s+[\u0600-\u06FF\s]{2,15}",
            r"ربو|الربو",
            r"حساسية\s+[\u0600-\u06FF\s]{2,15}",
            r"أنيميا|فقر\s+الدم",
            r"سرطان\s+[\u0600-\u06FF\s]{2,15}",
            r"ورم\s+[\u0600-\u06FF\s]{2,15}",
            r"تجلط|جلطة\s+[\u0600-\u06FF\s]{2,15}",
            r"هربس|حلأ",
            r"التهاب\s+(?:الكبد|المعدة|المفاصل|الرئتين|الأذن|الحلق|الجيوب|المثانة|الكلى)",
            r"ارتفاع\s+(?:السكر|السكر في الدم)",
            r"نقص\s+(?:المناعة|الفيتامين|الحديد|الكالسيوم)",
            r"ضيق\s+(?:التنفس|النفس)",
            r"آلام?\s+(?:الصدر|البطن|الظهر|المفاصل|الرأس|الركبة)",
            r"التهاب\s+مسلك\s+(?:البول|التنفس)",
        ]
        patterns[self.DIAGNOSIS] = self._compile_patterns(diagnosis_patterns)

        # ============================================================
        # BODY_PART patterns - أجزاء الجسم
        # ============================================================
        body_part_patterns = [
            r"(?:الرأس|الرأس والرقبة|الرقبة|الوجه|الجبهة|الأنف|الأذن|الأذنان|العين|العينان)",
            r"(?:الصدر|القلب|الرئة|الرئتان|القصبة الهوائية)",
            r"(?:البطن|المعدة|الكبد|الطحال|البنكرياس|الأمعاء|القولون|المستقيم)",
            r"(?:الكلى|الكليتان|المثانة|البروستاتا|الحالب)",
            r"(?:الظهر|العمود الفقري|الفقرات)",
            r"(?:الكتف|الكتفان|الذراع|اليد|الرسغ|الكف|الأصابع)",
            r"(?:الحوض|الورك|الفخذ|الركبة|الساق|الكاحل|القدم|القدمان)",
            r"(?:الجلد|البشرة|الأظافر|الشعر)",
            r"(?:الدماغ|الأعصاب|الأعصاب المحيطية|النخاع الشوكي)",
            r"(?:العضلات|المفاصل|العظام|الأوتار|الأربطة)",
            r"(?:الغدة الدرقية|الغدد اللمفاوية|الغدة النخامية)",
            r"(?:الأوعية الدموية|الأوردة|الشرايين)",
            r"(?:الحلق|اللوزتان|اللسان|اللثة|الأسنان)",
        ]
        patterns[self.BODY_PART] = self._compile_patterns(body_part_patterns)

        # ============================================================
        # LAB_TEST patterns - التحاليل المخبرية
        # ============================================================
        lab_test_patterns = [
            r"(?:تحليل|فحص|إجراء)\s+(?:?:الدم|الدم|البول|البراز)[\s\u0600-\u06FF]{0,15}",
            r"(?:CBC|سي\.بي\.سي|صورة دم كاملة)",
            r"(?:HbA1c|إتش\.بي\.إيه\.1سي|السكر التراكمي|الهيموغلوبين السكري)",
            r"(?:فحص|تحليل)\s+(?:السكر|الجلوكوز|الغلوكوز)",
            r"(?:الكرياتينين|الكرياتنين|Creatinine)",
            r"(?:اليوريا|البولينا|Urea|BUN)",
            r"(?:نسبة|مستوى)\s+(?:الكوليسترول|الدهون الثلاثية|الشحوم)",
            r"(?:الإنزيمات الكبدية|وظائف الكبد|ALT|AST|GGT|ALP)",
            r"(?:وظائف الكلى|الوظائف الكلوية|Kidney function)",
            r"(?:تحليل|فحص)\s+(?:البروستاتا|PSA)",
            r"(?:الهرمونات|الغدة الدرقية|TSH|T3|T4)",
            r"(?:غازات\s+)?(?:الدم\s+)?(?:الشرياني|الوريدي)",
            r"(?:سرعة ترسب|ESR|CRP)",
            r"(?:تعداد\s+)?(?:الصفيحات|الصفائح الدموية|الصفائح)",
            r"(?:البروتين\s+)?(?:التفاعلي|C-reaktive)",
            r"(?:فيتامين\s+(?:د|D|ب|B|ب12|B12|أ|A|ك|K))",
            r"(?:الحديد|Ferritin|الفيريتين|TIBC)",
            r"(?:تخثر|تجلط)\s+(?:الدم|الدماوي)",
            r"(?:زمن\s+)?(?:البروثرومبين|PT|INR|APTT)",
        ]
        patterns[self.LAB_TEST] = self._compile_patterns(lab_test_patterns)

        # ============================================================
        # FREQUENCY patterns - التكرار
        # ============================================================
        frequency_patterns = [
            r"(?:مرة|مرتين|ثلاث|أربع|خمس)\s+(?:يومياً|يوميا|باليوم|أسبوعياً|أسبوعيا|بالأسبوع|شهرياً|شهريا|بالشهر)",
            r"يومياً|يوميا|كل يوم|يوميا بعد يوم",
            r"(?:مرتين|مرتين)\s+(?:في اليوم|يومياً|يوميا)",
            r"كل\s+\d+\s+(?:ساعة|ساعات|يوم|أيام|أسبوع|أسابيع|ساعة)",
            r"عند\s+(?:الحاجة|الضرورة|اللزوم)",
            r"حسب\s+(?:الحاجة|الطلب|الإرشادات)",
            r"قبل\s+(?:الأكل|الوجبة|الطعام|النوم)",
            r"بعد\s+(?:الأكل|الوجبة|الطعام)",
            r"(?:صباحاً|مساءً|ليلاً|صباحا|مساءً|ليلا)",
            r"(?:أسبوعياً|أسبوعيا|بشكل أسبوعي)",
            r"(?:شهرياً|شهريا|بشكل شهري)",
        ]
        patterns[self.FREQUENCY] = self._compile_patterns(frequency_patterns)

        # ============================================================
        # DURATION patterns - المدة الزمنية
        # ============================================================
        duration_patterns = [
            r"(?:لمدة|لمدّة|لمده|لمده)\s+\d+\s+(?:يوم|أيام|أسبوع|أسابيع|شهر|أشهر|سنة|سنوات)",
            r"(?:لمدة|لمدّة|لمده)\s+(?:أسبوع|أسبوعين|شهر|شهرين|ثلاثة أشهر|ستة أشهر)",
            r"(?:لمدة|لمدّة|لمده)\s+(?:علاج|المسار|الاستخدام|المداواة)",
            r"\d+\s+(?:يوم|أيام|أسبوع|أسابيع|شهر|أشهر|سنة|سنوات)",
            r"(?:كورس|دورة|موعة)\s+(?:علاجية|علاج)\s+\d+\s+(?:يوم|أيام|أسبوع)",
            r"شهر\s+(?:كامل|واحد|واحدة|ثانٍ|ثاني|ثلاثة|ستة)",
            r"أسبوع(?:ان|ين)?",
            r"يوم(?:ان|ين)?",
        ]
        patterns[self.DURATION] = self._compile_patterns(duration_patterns)

        return patterns

    def _compute_confidence(
        self,
        entity_type: str,
        value: str,
        match: re.Match,
    ) -> float:
        """
        Compute a confidence score for a regex match.

        حساب درجة الثقة لتطابق regex.

        Longer, more specific matches get higher confidence.
        Dosage and drug patterns with numbers get bonus confidence.

        Args:
            entity_type: The entity type label.
            value: The matched text.
            match: The regex match object.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Base confidence for regex matches
        base_confidence = 0.85

        # Length bonus: longer matches are more likely correct
        length_bonus = min(len(value.strip()) / 50.0, 0.1)

        # Specificity bonus for patterns with numbers
        number_bonus = 0.0
        if re.search(r"\d", value):
            number_bonus = 0.03

        # Entity-type specific adjustments
        type_bonus = 0.0
        if entity_type == self.DRUG:
            # Known drug names get higher confidence
            known_drugs = [
                "باراسيتامول", "أموكسيسيلين", "ميتفورمين", "إنسولين",
                "أسبرين", "إيبوبروفين", "أوميبرازول", "وارفارين",
            ]
            if any(drug in value for drug in known_drugs):
                type_bonus = 0.05

        elif entity_type == self.DOSAGE:
            # Patterns with both number and unit are very confident
            if re.search(r"\d+.*(?:ملغ|مجم|جم|مل)", value):
                type_bonus = 0.05

        elif entity_type == self.LAB_TEST:
            # Abbreviation-based patterns are reliable
            if re.search(r"[A-Z]{2,}", value):
                type_bonus = 0.05

        confidence = base_confidence + length_bonus + number_bonus + type_bonus
        return min(confidence, 1.0)

    @staticmethod
    def _compile_patterns(pattern_strings: List[str]) -> List[Pattern]:
        """
        Compile a list of regex pattern strings.

        تجميع قائمة من أنماط regex.

        Args:
            pattern_strings: List of regex pattern strings.

        Returns:
            List of compiled regex Pattern objects.
        """
        compiled = []
        for ps in pattern_strings:
            try:
                compiled.append(re.compile(ps, re.UNICODE | re.IGNORECASE))
            except re.error as e:
                logger.warning(
                    f"نمط regex غير صالح: '{ps}' - {e} "
                    f"| Invalid regex pattern: '{ps}' - {e}"
                )
        return compiled