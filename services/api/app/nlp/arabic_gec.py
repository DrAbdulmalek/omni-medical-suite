# -*- coding: utf-8 -*-
"""Arabic Post-OCR Correction using AraBART GEC.

Integrates CAMeL-Lab/arabart-qalb14-gec-ged-13 model for correcting spelling
and grammatical errors in Arabic text extracted by OCR engines.  Critical for
medical documents where OCR errors can change clinical meaning.

Classes:
    ArabicGEC: Lazy-loaded AraBART seq2seq model for grammar error correction.
    MedicalTermProtector: Shields known medical terms from GEC over-correction.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger("arabic_gec")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


class ArabicGEC:
    """Arabic Grammar Error Correction powered by AraBART.

    Uses CAMeL-Lab/arabart-qalb14-gec-ged-13 to fix spelling and grammar.
    Model/tokenizer are loaded lazily on first use.

    Args:
        model_name: HuggingFace model id or local path.
        device: PyTorch device (``"cuda"``, ``"cpu"``). ``None`` auto-detects.
    """

    def __init__(
        self, model_name: str = "CAMeL-Lab/arabart-qalb14-gec-ged-13",
        device: Optional[str] = None,
    ) -> None:
        self._model_name = model_name
        self._device_override = device
        self._model: Any = None
        self._tokenizer: Any = None
        self._device: Any = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load model and tokenizer on first use."""
        if self._loaded:
            return
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            self._device = self._device_override or (
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            logger.info("Loading AraBART GEC model '%s' on %s ...", self._model_name, self._device)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self._model_name)
            self._model.to(self._device).eval()
            self._loaded = True
            logger.info("AraBART GEC model loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load AraBART model: %s", exc)
            self._loaded = False

    def is_available(self) -> bool:
        """Return ``True`` if transformers and torch are importable."""
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForSeq2SeqLM  # noqa: F401
            return True
        except ImportError:
            return False

    def correct(self, text: str) -> str:
        """Correct spelling/grammar of a single Arabic text.  Falls back to
        the original text on model unavailability or inference failure."""
        if not text or not text.strip():
            return text
        cleaned = self._preprocess(text)
        try:
            self._ensure_loaded()
            if not self._loaded:
                logger.warning("GEC model not loaded – returning original text.")
                return text
            inputs = self._tokenizer(cleaned, return_tensors="pt", truncation=True, max_length=512).to(self._device)
            import torch
            with torch.no_grad():
                generated = self._model.generate(**inputs, max_length=512, num_beams=4, early_stopping=True)
            corrected = self._tokenizer.decode(generated[0], skip_special_tokens=True)
            return self._postprocess(corrected)
        except Exception as exc:
            logger.error("GEC correction failed: %s", exc)
            return text

    def correct_batch(self, texts: List[str]) -> List[str]:
        """Correct a batch of Arabic texts (processed individually)."""
        return [self.correct(t) for t in texts] if texts else []

    @staticmethod
    def get_diff(original: str, corrected: str) -> List[Dict[str, Any]]:
        """Return change dicts between *original* and *corrected*.  Each dict has
        ``type``, ``original``, ``corrected``, ``original_start``, ``original_end``."""
        if original == corrected:
            return []
        changes: List[Dict[str, Any]] = []
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, original, corrected).get_opcodes():
            if tag != "equal":
                changes.append({"type": tag, "original": original[i1:i2],
                                "corrected": corrected[j1:j2],
                                "original_start": i1, "original_end": i2})
        return changes

    @staticmethod
    def _preprocess(text: str) -> str:
        """Normalise: collapse whitespace, strip zero-width chars, normalise alef
        variants, add trailing sentence boundary."""
        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("\u0640", "")  # tatweel
        text = re.sub(r"[\u200B\u200C\u200D\u200E\u200F\uFEFF]", "", text)
        for src, dst in {"\u0622": "\u0627\u0654", "\u0623": "\u0627\u0654", "\u0625": "\u0627\u0655"}.items():
            text = text.replace(src, dst)
        if text and text[-1] not in ".\u061F!؟":
            text += "."
        return text

    @staticmethod
    def _postprocess(text: str) -> str:
        """Strip model-added punctuation and normalise whitespace."""
        text = text.strip()
        if text.endswith("."):
            text = text[:-1]
        return re.sub(r"\s+", " ", text).strip()


class MedicalTermProtector:
    """Shield known medical terms from GEC over-correction.

    Replaces recognised terms with ``__MED_N__`` placeholders before GEC
    and restores them afterward.  Dictionary spans diagnoses, medications,
    anatomy, procedures, units, and clinical vocabulary.
    """

    # -- التشخيصات (diagnoses) --------------------------------------------
    _DIAGNOSES: List[str] = [
        "سكري", "مرض السكري", "السكري النوع الأول", "السكري النوع الثاني",
        "ضغط", "ضغط دموي", "ارتفاع ضغط الدم", "هبوط ضغط الدم",
        "سرطان", "ورم خبيث", "ورم حميد", "سرطان الثدي", "سرطان الرئة",
        "سرطان الكبد", "سرطان القولون", "سرطان الدم", "سرطان البروستاتا",
        "التهاب الربوي", "الربو", "التهاب الشعب الهوائية",
        "فشل كلوي", "قصور كلوي", "التهاب الكلى", "حصوات الكلى",
        "التهاب الكبد", "تليف الكبد", "التهاب المرارة", "حصوات المرارة",
        "قصور قلبي", "فشل قلبي", "احتشاء عضلة القلب", "ذبحة صدرية",
        "جلطة", "سكتة دماغية", "نزيف", "فقر دم",
        "هيموفيليا", "التهاب المفاصل", "التهاب المعدة", "قرحة المعدة",
        "التهاب الرئة", "السل", "التهاب السحايا", "الصرع", "التوحد",
        "الزهايمر", "باركنسون", "تصلب متعدد", "هشاشة العظام",
        "حساسية", "أكزيما", "صدفية", "حمى", "التهاب المسالك البولية",
    ]

    # -- الأدوية (medications) ----------------------------------------------
    _MEDICATIONS: List[str] = [
        "ميتفورمين", "أنسولين", "أنسولين جلارجين", "أنسولين لانتوس",
        "أموكسيسيلين", "دوكساسون", "سالبوتامول", "أسبرين",
        "باراسيتامول", "إيبوبروفين", "ديكلوفيناك", "نابروكسين",
        "أزيثرومايسين", "سيبروفلوكساسين", "ميترونيدازول",
        "أتورفاستاتين", "روزوفاستاتين", "سيمفاستاتين",
        "أملوديبين", "لوسارتان", "إنالابريل", "فالسارتان",
        "كابتوبريل", "هيدروكلوروثيازيد", "فوروسيميد", "سبيرونولاكتون",
        "وارفارين", "هيبارين", "كلوبيدوجرل",
        "أوميبرازول", "لانزوبرازول", "بانتوبرازول",
        "مونتيلوكاست", "سالميتيرول", "بوديسونيد", "فلوتيكازون",
        "كورتيزون", "بريدنيزولون", "دكساميثازون",
        "لوراتادين", "سيتريزين", "فكسوفينادين",
        "جابابنتين", "بريغابالين", "كاربامازيبين", "فينيتوين",
        "سيرترالين", "فلوكسيتين", "باروكستين",
        "الميثوتريكسات", "أزاثيوبرين", "ليفودوبا", "كاربيدوبا",
        "ألندرونات", "كالسيتريول", "فيتامين د",
        "هيدروكسي كلوروكين", "سلفاسالازين",
    ]

    # -- التشريح (anatomy) --------------------------------------------------
    _ANATOMY: List[str] = [
        "القلب", "الرئة", "الرئتان", "الكبد", "الكليتان", "الكلى",
        "المعدة", "الأمعاء", "القولون", "المريء", "المستقيم", "الشرج",
        "البنكرياس", "الطحال", "المرارة", "الزائدة الدودية",
        "المخ", "الدماغ", "النخاع الشوكي", "الأعصاب",
        "العين", "القرنية", "الشبكية", "الجفن", "القزحية",
        "الأذن", "الأنف", "الحنجرة", "البلعوم", "اللوزتان",
        "الفم", "الأسنان", "اللثة", "اللسان", "الجلد", "البشرة",
        "العظام", "العظم", "المفاصل", "العمود الفقري", "الضلوع",
        "الفخذ", "العضد", "الكتف", "الكعبرة", "الزند",
        "الساق", "القدم", "الكاحل", "الركبة", "الورك",
        "العضلات", "الأوتار", "الأربطة",
        "الدم", "الأوعية الدموية", "الشرايين", "الأوردة",
        "الغدة الدرقية", "الغدة النخامية", "الغدة الكظرية",
        "الرحم", "المبيض", "المبيضان", "البروستاتا",
        "الثدي", "الخصية", "الشريان التاجي", "الأبهر",
    ]

    # -- الإجراءات (procedures) ---------------------------------------------
    _PROCEDURES: List[str] = [
        "عملية جراحية", "عملية", "جراحة", "تخدير", "مخدر", "تخدير موضعي",
        "تخدير عام", "تحليل", "تحاليل", "تصوير أشعة",
        "تصوير بالرنين المغناطيسي", "رنين مغناطيسي", "الأشعة السينية",
        "التصوير المقطعي", "تصوير مقطعي محوسب",
        "التصوير بالموجات فوق الصوتية", "سونار", "إيكو",
        "تخطيط قلب", "تخطيط كهربائي للقلب", "تخطيط دماغ",
        "تنظير", "تنظير المعدة", "تنظير القولون",
        "خزعة", "فحص دم", "فحص البول", "فحص سكر",
        "فحص وظائف الكلى", "فحص وظائف الكبد", "فحص دهون",
        "غسيل الكلى", "ديلزة", "قسطرة", "حقن", "نقل دم",
        "تلقيح", "تطعيم", "لقاح", "علاج طبيعي", "علاج وظيفي", "علاج نطق",
    ]

    # -- القيم (measurement units & lab values) -----------------------------
    _VALUES: List[str] = [
        "ملم زئبق", "مليمتر زئبق", "ملم", "مج", "دل",
        "نبض", "درجة حرارة", "ضغط دم انقباضي", "ضغط دم انبساطي",
        "ملي مول", "ملي غرام", "غرام", "كيلو غرام", "مل", "وحدة دولية",
        "نسبة السكر", "مستوى السكر", "الهيموغلوبين",
        "الصفائح الدموية", "كريات الدم البيضاء", "كريات الدم الحمراء",
        "سرعة ترسب الدم", "اختبار CRP", "بروتين سي التفاعلي",
        "إنزيمات الكبد", "الكرياتينين", "اليوريا", "حمض البوليك",
    ]

    # -- المختلطات (general clinical vocabulary) ----------------------------
    _GENERAL: List[str] = [
        "مريض", "مريضة", "المرضى", "المريض", "ألم", "صداع",
        "ألم في الصدر", "ألم في البطن", "ألم في الظهر", "ألم في المفاصل",
        "ألم في الرقبة", "ألم في الركبة",
        "فحص", "كشف", "تشخيص", "علاج", "وصفة طبية", "تقرير طبي",
        "استشارة", "إحالة", "تحويل", "متابعة", "مراقبة",
        "حالة مستقرة", "حالة حرجة", "حالة متوسطة",
        "دخول", "خروج", "إعادة دخول", "تنويم", "طوارئ", "عناية مركزة", "إسعاف",
        "طبيب", "طبيبة", "أطباء", "ممرض", "ممرضة", "صيدلي", "صيدلية",
        "مستشفى", "عيادة", "مختبر",
        "حساسية دوائية", "أعراض جانبية", "جرعة", "مقدار الجرعة",
        "مضاد حيوي", "مضاد للالتهاب", "مسكن", "مهدئ", "منوم",
        "وريد", "عضل", "فم", "تحت اللسان", "موضعي",
        "حقنة", "كبسولة", "قرص", "شراب", "قطرات", "مرهم", "لبوس",
        "مرة واحدة يوميا", "مرتين يوميا", "ثلاث مرات يوميا",
        "كل ثمان ساعات", "كل اثنتي عشرة ساعة",
        "قبل الأكل", "بعد الأكل", "على معدة فارغة",
        "تاريخ المرض", "السوابق المرضية", "التاريخ العائلي",
    ]

    # -- English medical terms in Arabic clinical docs ----------------------
    _ENGLISH_MEDICAL: List[str] = [
        "glucose", "insulin", "metformin", "aspirin", "ibuprofen", "amoxicillin",
        "prednisone", "CT scan", "MRI", "X-ray", "ECG", "CBC", "blood pressure",
        "heart rate", "BMI", "surgery", "biopsy", "dialysis", "transplant",
        "chemotherapy", "radiation", "antibiotic", "antiviral", "vaccine", "diagnosis",
    ]

    def __init__(self) -> None:
        self._terms: List[str] = []
        self._placeholder_map: Dict[str, str] = {}
        self._counter: int = 0
        self._rebuild()

    def _rebuild(self) -> None:
        """Compile a single regex from all term groups (longest-first)."""
        all_terms: List[str] = []
        for group in (self._DIAGNOSES, self._MEDICATIONS, self._ANATOMY,
                      self._PROCEDURES, self._VALUES, self._GENERAL, self._ENGLISH_MEDICAL):
            all_terms.extend(group)
        seen: set = set()
        unique: List[str] = [t for t in all_terms if t not in seen and not seen.add(t)]
        self._terms = sorted(unique, key=len, reverse=True)
        self._pattern = re.compile("|".join(re.escape(t) for t in self._terms), re.UNICODE)

    def protect(self, text: str) -> str:
        """Replace every known medical term with a ``__MED_N__`` placeholder."""
        self._placeholder_map.clear()
        self._counter = 0
        def _replacer(match: re.Match) -> str:
            ph = f"__MED_{self._counter}__"
            self._placeholder_map[ph] = match.group(0)
            self._counter += 1
            return ph
        return self._pattern.sub(_replacer, text)

    def restore(self, text: str) -> str:
        """Re-insert medical terms from ``__MED_N__`` placeholders."""
        result = text
        for ph, original in self._placeholder_map.items():
            result = result.replace(ph, original)
        return result

    def add_terms(self, terms: List[str]) -> None:
        """Extend the built-in dictionary and rebuild the regex."""
        self._ENGLISH_MEDICAL.extend(terms)
        self._rebuild()


def post_process_ocr(
    fused_text: str,
    enable_gec: bool = True,
    enable_medical_protection: bool = True,
) -> Dict[str, Any]:
    """End-to-end OCR post-processing: protect → GEC → restore → diff.

    Args:
        fused_text: Text produced by OCR fusion.
        enable_gec: Skip GEC when ``False``.
        enable_medical_protection: Skip term protection when ``False``.

    Returns:
        Dict with ``original``, ``corrected``, ``changes``, ``medical_terms_protected``.
    """
    protector = MedicalTermProtector()
    gec = ArabicGEC()
    protected_count = 0
    original = fused_text

    if enable_medical_protection:
        working_text = protector.protect(fused_text)
        protected_count = protector._counter
    else:
        working_text = fused_text

    corrected = gec.correct(working_text) if enable_gec else working_text

    if enable_medical_protection:
        corrected = protector.restore(corrected)

    return {
        "original": original,
        "corrected": corrected,
        "changes": gec.get_diff(original, corrected),
        "medical_terms_protected": protected_count,
    }


def correct_ocr_output(fused_result: Any) -> Dict[str, Any]:
    """Apply GEC correction to a ``FusedResult`` from the OCR fusion pipeline.
    Extracts ``final_text``, runs :func:`post_process_ocr`, attaches original
    fusion metadata when available."""
    text = getattr(fused_result, "final_text", str(fused_result))
    result = post_process_ocr(text)
    try:
        if hasattr(fused_result, "model_dump"):
            result["ocr_fusion_result"] = fused_result.model_dump()
        elif hasattr(fused_result, "__dict__"):
            result["ocr_fusion_result"] = fused_result.__dict__
    except Exception:
        pass
    return result
