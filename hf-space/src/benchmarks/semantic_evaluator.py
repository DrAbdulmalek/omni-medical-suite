"""
Semantic Medical Evaluator - التقييم الدلالي الطبي لـ OCR
=============================================================

This module addresses the critical concern about semantic medical accuracy
in OCR evaluation. Standard Character Error Rate (CER) treats all errors
equally, but in medical documents, misrecognizing a drug name or dosage
is far more serious than misrecognizing a common word.

This evaluator computes a Medical-Aware CER that penalizes errors in
medical terminology (drug names, anatomical terms, lab tests) with
a 3x multiplier, providing a more clinically relevant accuracy metric.

هذه الوحدة تعالج القلق الحاسم حول الدقة الدلالية الطبية في تقييم OCR.
معدل خطأ الأحرف (CER) القياسي يعامل جميع الأخطاء بالتساوي، لكن في
المستندات الطبية، الخطأ في اسم دواء أو جرعة أخطر بكثير من الخطأ
في كلمة عادية. يقوم هذا المقيّم بحساب CER واعٍ طبياً يعاقب أخطاء
المصطلحات الطبية بمعامل 3x، مما يوفر مقياس دقة أكثر صلة سريرياً.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "تهيئة المقيم الدلالي الطبي | Initializing semantic medical evaluator"
_MSG_DICTS = "تم تحميل {n_drugs} دواء و {n_anatomy} مصطلح تشريحي و {n_lab} تحليل"
_MSG_EVAL = "جارٍ التقييم الدلالي | Running semantic evaluation"
_MSG_CER = "CER القياسي: {cer:.4f} | Standard CER: {cer:.4f}"
_MSG_MED_CER = "CER الطبي (معزز): {cer:.4f} | Medical CER (penalized): {cer:.4f}"
_MSG_MED_TERMS = "تم العثور على {n} مصطلح طبي في النص | Found {n} medical terms in text"
_MSG_REPORT = "جارٍ إنشاء التقرير | Generating evaluation report"
_MSG_NO_MED = "لم يتم تحميل القواميس الطبية | Medical dictionaries not loaded"


class SemanticMedicalEvaluator:
    """
    Semantic evaluator for medical OCR accuracy.

    مقيم دلالي لدقة OCR الطبية.

    Key concept: In medical OCR, not all errors are equal.
    Misrecognizing "500 ملغ" (500 mg) as "500 مل" (500 ml) is a
    critical error, while misrecognizing "والتي" as "والت" is trivial.

    This evaluator:
        1. Identifies medical terms in reference and hypothesis texts
        2. Computes standard CER
        3. Computes Medical-Aware CER with 3x penalty on medical term errors
        4. Generates detailed reports with per-term analysis

    المفهوم الرئيسي: في OCR الطبي، ليست كل الأخطاء متساوية.
    الخطأ في "500 ملغ" كـ "500 مل" خطأ حرج، بينما الخطأ في
    "والتي" كـ "والت" تافه.
    """

    # Penalty multiplier for medical term errors
    MEDICAL_PENALTY = 3.0

    def __init__(self) -> None:
        """
        Initialize the evaluator and load medical dictionaries.

        تهيئة المقيم وتحميل القواميس الطبية.
        """
        logger.info(_MSG_INIT)

        self.drug_names: Set[str] = set()
        self.anatomy_terms: Set[str] = set()
        self.lab_test_names: Set[str] = set()
        self.dosage_units: Set[str] = set()

        self._load_medical_dictionaries()

        total = (
            len(self.drug_names)
            + len(self.anatomy_terms)
            + len(self.lab_test_names)
        )
        logger.info(
            _MSG_DICTS.format(
                n_drugs=len(self.drug_names),
                n_anatomy=len(self.anatomy_terms),
                n_lab=len(self.lab_test_names),
            )
        )

    def evaluate(
        self,
        hypothesis: str,
        reference: str,
    ) -> Dict:
        """
        Perform full semantic evaluation of OCR output.

        إجراء تقييم دلالي كامل لمخرجات OCR.

        Computes both standard CER and Medical-Aware CER, along
        with detailed medical term analysis.

        Args:
            hypothesis: The OCR-extracted text to evaluate.
            reference: The ground truth / reference text.

        Returns:
            Dictionary containing:
                - standard_cer (float): Standard Character Error Rate
                - medical_aware_cer (float): CER with medical penalty
                - medical_terms_in_reference (int): Count of medical terms in ref
                - medical_terms_in_hypothesis (int): Count in hypothesis
                - medical_term_match_rate (float): Fraction of ref terms found
                - medical_errors (List[Dict]): Details of medical term errors
                - total_chars_ref (int): Character count in reference
                - total_insertions (int)
                - total_deletions (int)
                - total_substitutions (int)
        """
        logger.info(_MSG_EVAL)

        if not reference:
            return {
                "standard_cer": 1.0,
                "medical_aware_cer": 1.0,
                "medical_terms_in_reference": 0,
                "medical_terms_in_hypothesis": 0,
                "medical_term_match_rate": 0.0,
                "medical_errors": [],
                "total_chars_ref": 0,
                "total_insertions": 0,
                "total_deletions": 0,
                "total_substitutions": 0,
            }

        # Normalize texts for comparison
        norm_hyp = self._normalize_text(hypothesis)
        norm_ref = self._normalize_text(reference)

        # Standard CER using edit distance
        std_cer, edits = self._compute_edit_distance_cer(norm_hyp, norm_ref)

        # Medical-Aware CER
        med_cer, medical_errors = self.compute_medical_aware_cer(
            norm_hyp, norm_ref
        )

        # Find medical terms in both texts
        ref_med_terms = self._find_medical_terms(norm_ref)
        hyp_med_terms = self._find_medical_terms(norm_hyp)

        # Compute term match rate
        match_rate = 0.0
        if ref_med_terms:
            matches = sum(
                1 for term in ref_med_terms
                if any(term in h or h in term for h in hyp_med_terms)
            )
            match_rate = matches / len(ref_med_terms)

        logger.info(_MSG_CER.format(cer=std_cer))
        logger.info(_MSG_MED_CER.format(cer=med_cer))
        logger.info(
            _MSG_MED_TERMS.format(n=len(ref_med_terms))
        )

        result = {
            "standard_cer": round(std_cer, 6),
            "medical_aware_cer": round(med_cer, 6),
            "medical_terms_in_reference": len(ref_med_terms),
            "medical_terms_in_hypothesis": len(hyp_med_terms),
            "medical_term_match_rate": round(match_rate, 4),
            "medical_errors": medical_errors,
            "total_chars_ref": len(norm_ref),
            "total_insertions": edits.get("insertions", 0),
            "total_deletions": edits.get("deletions", 0),
            "total_substitutions": edits.get("substitutions", 0),
        }

        return result

    def compute_medical_aware_cer(
        self,
        hypothesis: str,
        reference: str,
        penalty: Optional[float] = None,
    ) -> Tuple[float, List[Dict]]:
        """
        Compute CER with enhanced penalty for medical term errors.

        حساب CER مع عقوبة معززة لأخطاء المصطلحات الطبية.

        The algorithm:
            1. Identify spans of medical terms in the reference text
            2. Compute standard edit distance
            3. For each edit operation that falls within a medical term span,
               multiply its cost by the penalty factor (default 3x)
            4. The weighted error count divided by reference length
               gives the Medical-Aware CER

        Args:
            hypothesis: OCR output text.
            reference: Ground truth text.
            penalty: Multiplier for medical term errors. Defaults to 3.0.

        Returns:
            Tuple of (medical_aware_cer, list_of_medical_errors).
        """
        if penalty is None:
            penalty = self.MEDICAL_PENALTY

        if not reference:
            return 1.0, []

        # Find medical term spans in reference
        med_spans = self._find_medical_term_spans(reference)
        medical_errors: List[Dict] = []

        # Compute character-level edit distance with position tracking
        # Using dynamic programming
        h = hypothesis
        r = reference
        n = len(h)
        m = len(r)

        # DP table: dp[i][j] = (min_cost, operations)
        # operations tracks (type, hyp_pos, ref_pos)
        dp: List[List[Tuple[float, List]]] = [
            [(0.0, [])] * (m + 1) for _ in range(n + 1)
        ]

        # Initialize
        for i in range(1, n + 1):
            cost = self._char_cost(hyp_pos=i - 1, ref_pos=-1, ref_spans=med_spans)
            dp[i][0] = (dp[i - 1][0][0] + cost, dp[i - 1][0][1] + [("insertion", i - 1, -1)])

        for j in range(1, m + 1):
            cost = self._char_cost(hyp_pos=-1, ref_pos=j - 1, ref_spans=med_spans)
            dp[0][j] = (dp[0][j - 1][0] + cost, dp[0][j - 1][1] + [("deletion", -1, j - 1)])

        # Fill DP table
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if h[i - 1] == r[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    # Substitution
                    sub_cost = self._char_cost(i - 1, j - 1, med_spans)
                    sub_total = dp[i - 1][j - 1][0] + sub_cost
                    sub_ops = dp[i - 1][j - 1][1] + [
                        ("substitution", i - 1, j - 1)
                    ]

                    # Deletion
                    del_cost = self._char_cost(-1, j - 1, med_spans)
                    del_total = dp[i][j - 1][0] + del_cost
                    del_ops = dp[i][j - 1][1] + [
                        ("deletion", -1, j - 1)
                    ]

                    # Insertion
                    ins_cost = self._char_cost(i - 1, -1, med_spans)
                    ins_total = dp[i - 1][j][0] + ins_cost
                    ins_ops = dp[i - 1][j][1] + [
                        ("insertion", i - 1, -1)
                    ]

                    # Pick minimum cost
                    if sub_total <= del_total and sub_total <= ins_total:
                        dp[i][j] = (sub_total, sub_ops)
                    elif del_total <= ins_total:
                        dp[i][j] = (del_total, del_ops)
                    else:
                        dp[i][j] = (ins_total, ins_ops)

        total_cost, operations = dp[n][m]
        med_cer = total_cost / m if m > 0 else 0.0

        # Extract medical-specific errors for reporting
        for op_type, h_pos, r_pos in operations:
            is_medical = False
            if r_pos >= 0:
                is_medical = self._pos_in_medical_span(r_pos, med_spans)
            elif h_pos >= 0:
                # For insertions, check surrounding reference context
                is_medical = self._pos_near_medical_span(h_pos, med_spans, h, r)

            if is_medical:
                error_detail = {
                    "type": op_type,
                    "penalty": penalty,
                }
                if h_pos >= 0 and h_pos < len(h):
                    error_detail["hypothesis_char"] = h[h_pos]
                if r_pos >= 0 and r_pos < len(r):
                    error_detail["reference_char"] = r[r_pos]
                    # Get the medical term this belongs to
                    for span in med_spans:
                        if span[0] <= r_pos < span[1]:
                            error_detail["medical_term"] = r[span[0]:span[1]]
                            break

                medical_errors.append(error_detail)

        return med_cer, medical_errors

    def generate_report(self, results: Dict) -> str:
        """
        Generate a formatted evaluation report.

        إنشاء تقرير تقييم منسق.

        Args:
            results: Evaluation results from the evaluate() method.

        Returns:
            Formatted multi-line report string.
        """
        logger.info(_MSG_REPORT)

        separator = "=" * 72
        lines: List[str] = [
            separator,
            f"{'تقرير التقييم الدلالي الطبي | Semantic Medical Evaluation Report':^72}",
            separator,
            "",
            "  ╔══════════════════════════════════════════════════════════════╗",
            "  ║  المقاييس الرئيسية | Key Metrics                            ║",
            "  ╠══════════════════════════════════════════════════════════════╣",
            f"  ║  CER القياسي (Standard CER):        {results.get('standard_cer', 0):.4f}              ║",
            f"  ║  CER الطبي (Medical-Aware CER):     {results.get('medical_aware_cer', 0):.4f}              ║",
            f"  ║  الفرق (Gap):                        {abs(results.get('medical_aware_cer', 0) - results.get('standard_cer', 0)):.4f}              ║",
            "  ╠══════════════════════════════════════════════════════════════╣",
            f"  ║  المصطلحات الطبية في المرجع:        {results.get('medical_terms_in_reference', 0):>4}                  ║",
            f"  ║  المصطلحات الطبية في الناتج:        {results.get('medical_terms_in_hypothesis', 0):>4}                  ║",
            f"  ║  معدل تطابق المصطلحات:              {results.get('medical_term_match_rate', 0):.2%}              ║",
            "  ╠══════════════════════════════════════════════════════════════╣",
            f"  ║  إجمالي أحرف المرجع:                {results.get('total_chars_ref', 0):>4}                  ║",
            f"  ║  الإدراجات (Insertions):             {results.get('total_insertions', 0):>4}                  ║",
            f"  ║  الحذوفات (Deletions):               {results.get('total_deletions', 0):>4}                  ║",
            f"  ║  الاستبدالات (Substitutions):        {results.get('total_substitutions', 0):>4}                  ║",
            "  ╚══════════════════════════════════════════════════════════════╝",
        ]

        # Medical errors detail
        med_errors = results.get("medical_errors", [])
        if med_errors:
            lines.extend([
                "",
                separator,
                "  أخطاء المصطلحات الطبية | Medical Term Errors:",
                "-" * 72,
            ])

            for idx, err in enumerate(med_errors[:20], 1):  # Limit to 20
                err_type = err.get("type", "unknown")
                ref_char = err.get("reference_char", "")
                hyp_char = err.get("hypothesis_char", "")
                med_term = err.get("medical_term", "N/A")
                penalty = err.get("penalty", self.MEDICAL_PENALTY)

                if err_type == "substitution":
                    detail = f"'{ref_char}' → '{hyp_char}'"
                elif err_type == "deletion":
                    detail = f"حذف '{ref_char}' | deleted '{ref_char}'"
                elif err_type == "insertion":
                    detail = f"إدراج '{hyp_char}' | inserted '{hyp_char}'"
                else:
                    detail = err_type

                lines.append(
                    f"  {idx:>2}. [{err_type}] {detail} "
                    f"| في: {med_term} | ×{penalty:.0f}"
                )

            if len(med_errors) > 20:
                lines.append(
                    f"  ... و {len(med_errors) - 20} خطأ آخر "
                    f"| and {len(med_errors) - 20} more errors"
                )

        # Interpretation
        lines.extend([
            "",
            separator,
            "  التفسير | Interpretation:",
            "-" * 72,
        ])

        med_cer = results.get("medical_aware_cer", 1.0)
        std_cer = results.get("standard_cer", 1.0)
        gap = med_cer - std_cer

        if gap > 0.05:
            lines.append(
                "  ⚠ تحذير: الفرق بين CER القياسي والطبي كبير (> 5%). "
                "هذا يشير إلى أن الأخطاء تتركز في المصطلحات الطبية."
            )
            lines.append(
                "  ⚠ Warning: Significant gap between standard and medical CER (> 5%). "
                "Errors are concentrated in medical terminology."
            )
        elif gap > 0.02:
            lines.append(
                "  ⚡ انتباه: فرق معتدل في CER الطبي. بعض أخطاء المصطلحات الطبية موجودة."
            )
            lines.append(
                "  ⚡ Note: Moderate medical CER gap. Some medical term errors present."
            )
        else:
            lines.append(
                "  ✓ جيد: أداء OCR جيد على المصطلحات الطبية."
            )
            lines.append(
                "  ✓ Good: OCR performs well on medical terminology."
            )

        lines.append(separator)

        return "\n".join(lines)

    def _load_medical_dictionaries(self) -> None:
        """
        Load built-in medical dictionaries for Arabic medical terms.

        تحميل القواميس الطبية المدمجة للمصطلحات الطبية العربية.
        """
        # ============================================================
        # Drug names - أسماء الأدوية
        # ============================================================
        self.drug_names = {
            "باراسيتامول", "بنادول", "أموكسيسيلين", "أموكسل",
            "ميتفورمين", "جلوكوفاج", "أسيكلوفير", "زوفيراكس",
            "أوميبرازول", "لوسيك", "سيتالوبرام", "سيبراليكس",
            "إنسولين", "لانتوس", "نوفوميكس", "وارفارين", "كومادين",
            "أسبرين", "إيبوبروفين", "بروفين", "أدفيل",
            "كيتورولاك", "تورادول", "ترامادول",
            "أملوديبين", "نورفاسك", "لوسارتان", "لوزار",
            "أتورفاستاتين", "ليبيتور", "سيليكوكسيب", "كليبريكس",
            "أزيثرومايسين", "زيثروماكس", "سيفالكسين", "كيفليكس",
            "ميترونيدازول", "فلاجيل", "ديكلوفيناك", "فولتارين",
            "سالبيوتامول", "فنتولين", "بوديسونيد", "بولميكورت",
            "فليوتيكاسون", "مونتيلوكاست", "سنغولار",
            "لوراتادين", "كلاريتين", "سيتيريزين", "زيرتك",
            "فكسوفينادين", "أليغرا", "فاموتيدين", "بيبسيد",
            "رانيديدين", "زانتاك", "ألوبورينول", "زيلوريك",
            "بريدنيزولون", "بريدنيزون", "هيدروكورتيزون", "كورتيزون",
            "دكساميثازون", "فوروسيميد", "لازيكس", "سبيرونولاكتون",
            "كابتوبريل", "إنالابريل", "دومبيريدون", "موتيليوم",
            "أوندانسيترون", "زوفيران", "لوبيراميد", "إيموديوم",
            "ديفينهيدرامين", "بينادريل", "أموكسيدبين",
            # English names commonly appearing in Arabic medical texts
            "paracetamol", "amoxicillin", "metformin", "insulin",
            "aspirin", "ibuprofen", "omeprazole", "warfarin",
            "atorvastatin", "amlodipine", "losartan", "prednisolone",
            "hydrocortisone", "dexamethasone", "furosemide",
            "captopril", "enalapril", "azithromycin",
        }

        # ============================================================
        # Anatomy terms - المصطلحات التشريحية
        # ============================================================
        self.anatomy_terms = {
            "الرأس", "الرقبة", "الوجه", "الأنف", "الأذن", "العين",
            "الصدر", "القلب", "الرئة", "الرئتان", "القصبة الهوائية",
            "البطن", "المعدة", "الكبد", "الطحال", "البنكرياس",
            "الأمعاء", "القولون", "المستقيم", "الكلى", "الكليتان",
            "المثانة", "البروستاتا", "الحالب",
            "الظهر", "العمود الفقري", "الفقرات",
            "الكتف", "الذراع", "اليد", "الرسغ", "الكف", "الأصابع",
            "الحوض", "الورك", "الفخذ", "الركبة", "الساق",
            "الكاحل", "القدم", "الجلد", "البشرة", "الشعر",
            "الدماغ", "الأعصاب", "النخاع الشوكي",
            "العضلات", "المفاصل", "العظام", "الأوتار",
            "الغدة الدرقية", "الغدد اللمفاوية",
            "الأوعية الدموية", "الأوردة", "الشرايين",
            "الحلق", "اللوزتان", "اللسان", "اللثة", "الأسنان",
            # English anatomy in Arabic texts
            "heart", "liver", "kidney", "lung", "brain",
            "stomach", "pancreas", "spleen", "bladder",
        }

        # ============================================================
        # Lab test names - أسماء التحاليل
        # ============================================================
        self.lab_test_names = {
            "صورة دم كاملة", "CBC",
            "السكر التراكمي", "HbA1c", "الهيموغلوبين السكري",
            "الكرياتينين", "اليوريا", "البولينا",
            "الكوليسترول", "الدهون الثلاثية",
            "وظائف الكبد", "ALT", "AST", "GGT", "ALP",
            "وظائف الكلى", "الوظائف الكلوية",
            "البروستاتا", "PSA",
            "الغدة الدرقية", "TSH", "T3", "T4",
            "سرعة ترسب", "ESR", "CRP",
            "الصفيحات", "الصفائح الدموية",
            "فيتامين د", "فيتامين D", "فيتامين ب12",
            "الحديد", "الفيريتين", "Ferritin",
            "زمن البروثرومبين", "PT", "INR", "APTT",
            "السكر", "الجلوكوز", "الغلوكوز",
            "تحليل البول", "تحليل البراز",
            "hemoglobin", "glucose", "cholesterol", "triglycerides",
            "creatinine", "urea", "bilirubin",
        }

        # ============================================================
        # Dosage units - وحدات الجرعات
        # ============================================================
        self.dosage_units = {
            "ملغ", "مجم", "جم", "مللي", "م.م", "غ", "مكغ",
            "ميكروغرام", "وحدة عالمية", "و.د", "وحدة",
            "mg", "g", "ml", "mcg", "IU", "unit",
        }

    def _find_medical_terms(self, text: str) -> List[str]:
        """
        Find all medical terms present in the text.

        البحث عن جميع المصطلحات الطبية الموجودة في النص.

        Args:
            text: Input text to search.

        Returns:
            List of found medical term strings.
        """
        found: List[str] = []
        text_lower = text.lower()

        for term_set in [self.drug_names, self.anatomy_terms, self.lab_test_names]:
            for term in term_set:
                if term.lower() in text_lower and term not in found:
                    found.append(term)

        return found

    def _find_medical_term_spans(self, text: str) -> List[Tuple[int, int]]:
        """
        Find character-level spans of medical terms in the text.

        البحث عن امتدادات الأحرف للمصطلحات الطبية في النص.

        Args:
            text: Reference text.

        Returns:
            List of (start, end) tuples for each medical term found.
        """
        spans: List[Tuple[int, int]] = []

        for term_set in [self.drug_names, self.anatomy_terms, self.lab_test_names]:
            for term in term_set:
                # Case-insensitive search
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                for match in pattern.finditer(text):
                    spans.append((match.start(), match.end()))

        # Remove overlapping spans (keep the first/larger one)
        if not spans:
            return []

        spans.sort()
        merged: List[Tuple[int, int]] = [spans[0]]

        for start, end in spans[1:]:
            if start < merged[-1][1]:
                # Overlap - extend the previous span
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        return merged

    @staticmethod
    def _pos_in_medical_span(
        pos: int,
        spans: List[Tuple[int, int]],
    ) -> bool:
        """Check if a position falls within any medical term span."""
        for start, end in spans:
            if start <= pos < end:
                return True
        return False

    @staticmethod
    def _pos_near_medical_span(
        pos: int,
        spans: List[Tuple[int, int]],
        hyp: str,
        ref: str,
    ) -> bool:
        """
        Check if a hypothesis position is near a medical span
        (for inserted characters that might be part of a medical term).
        """
        for start, end in spans:
            if abs(pos - start) <= 3 or abs(pos - end) <= 3:
                return True
        return False

    def _char_cost(
        self,
        hyp_pos: int,
        ref_pos: int,
        ref_spans: List[Tuple[int, int]],
    ) -> float:
        """
        Compute the cost of a character edit operation.

        حساب تكلفة عملية تحرير حرف.

        Args:
            hyp_pos: Position in hypothesis (-1 for deletion).
            ref_pos: Position in reference (-1 for insertion).
            ref_spans: Medical term spans in reference.

        Returns:
            Cost: 1.0 for normal chars, MEDICAL_PENALTY for medical chars.
        """
        if ref_pos >= 0 and self._pos_in_medical_span(ref_pos, ref_spans):
            return self.MEDICAL_PENALTY

        # For insertions, we can't easily determine if they're in medical spans
        # Use heuristic: if nearby chars in reference are medical, treat as medical
        if hyp_pos >= 0 and ref_pos == -1:
            # This is a deletion from reference perspective
            for start, end in ref_spans:
                # Check if the hypothesis position roughly aligns with a medical span
                if abs(hyp_pos - start) <= 2 or abs(hyp_pos - end) <= 2:
                    return self.MEDICAL_PENALTY

        return 1.0

    def _compute_edit_distance_cer(
        self,
        hypothesis: str,
        reference: str,
    ) -> Tuple[float, Dict[str, int]]:
        """
        Compute standard Character Error Rate using edit distance.

        حساب معدل خطأ الأحرف القياسي باستخدام مسافة التحرير.

        Args:
            hypothesis: OCR output.
            reference: Ground truth.

        Returns:
            Tuple of (CER, edit_operations_count).
        """
        h = hypothesis
        r = reference
        n = len(h)
        m = len(r)

        if m == 0:
            return (0.0 if n == 0 else 1.0), {"insertions": n, "deletions": 0, "substitutions": 0}

        # DP for edit distance
        dp = [[0] * (m + 1) for _ in range(n + 1)]

        for i in range(n + 1):
            dp[i][0] = i
        for j in range(m + 1):
            dp[0][j] = j

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if h[i - 1] == r[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],       # deletion
                        dp[i][j - 1],       # insertion
                        dp[i - 1][j - 1],   # substitution
                    )

        # Backtrack to count operation types
        edits = {"insertions": 0, "deletions": 0, "substitutions": 0}
        i, j = n, m
        while i > 0 or j > 0:
            if i > 0 and j > 0 and h[i - 1] == r[j - 1]:
                i -= 1
                j -= 1
            elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
                edits["substitutions"] += 1
                i -= 1
                j -= 1
            elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
                edits["insertions"] += 1
                j -= 1
            elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
                edits["deletions"] += 1
                i -= 1
            else:
                # Shouldn't happen, but safety
                i -= 1
                j -= 1

        cer = dp[n][m] / m
        return cer, edits

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text for comparison.

        توحيد النص للمقارنة.

        Removes extra whitespace, normalizes Arabic characters,
        and standardizes punctuation.

        Args:
            text: Input text.

        Returns:
            Normalized text string.
        """
        if not text:
            return ""

        # Normalize Arabic characters
        normalized = (
            text
            # Normalize alef variants to bare alef
            .replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            # Normalize taa marbuta to haa
            .replace("ة", "ه")
            # Normalize yaa variants
            .replace("ى", "ي")
            # Normalize eastern arabic numerals
            .translate(EASTERN_ARABIC)
            # Remove diacritics (tashkeel)
        )

        # Remove Arabic diacritics (Unicode range 0610-061A, 064B-065F)
        normalized = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670]", "", normalized)

        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized


# Reuse eastern arabic translation table
EASTERN_ARABIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")