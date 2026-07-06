"""
القاموس الطبي - Medical Entities Dictionary
قاموس شامل للكيانات الطبية العربية والإنجليزية مع التصنيفات
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..utils.logger import get_logger

logger = get_logger("medical_entities")


class MedicalDictionary:
    """
    قاموس طبي ثنائي اللغة (عربي/إنجليزي) مع دعم المرادفات والتصنيفات

    يدعم:
    - أمراض الجهاز التنفسي
    - أمراض القلب والأوعية
    - الأمراض العصبية
    - الأورام والسرطانات
    - الإصابات والكسور
    - الأدوية الشائعة
    - التشريح البشري

    الاستخدام:
        dictionary = MedicalDictionary()
        matches = dictionary.search("ارتشاح رئوي")
    """

    def __init__(self, custom_path: Optional[str] = None):
        self.entities: Dict[str, List[Dict[str, str]]] = {}
        self._load_default_entities()
        if custom_path:
            self._load_custom(custom_path)

    def _load_default_entities(self):
        """تحميل الكيانات الطبية الافتراضية"""
        # ===== أمراض الجهاز التنفسي =====
        self.entities["DISEASE_RESPIRATORY"] = [
            {"ar": "التهاب رئوي", "en": "pneumonia", "category": "DISEASE"},
            {"ar": "ارتشاح رئوي", "en": "pulmonary infiltration", "category": "DISEASE"},
            {"ar": "انصباب جنبي", "en": "pleural effusion", "category": "DISEASE"},
            {"ar": "استرواح صدر", "en": "pneumothorax", "category": "DISEASE"},
            {"ar": "نفاخ رئوي", "en": "emphysema", "category": "DISEASE"},
            {"ar": "ربو", "en": "asthma", "category": "DISEASE"},
            {"ar": "انسداد رئوي مزمن", "en": "COPD", "category": "DISEASE"},
            {"ar": "تليف رئوي", "en": "pulmonary fibrosis", "category": "DISEASE"},
            {"ar": "خراج رئوي", "en": "lung abscess", "category": "DISEASE"},
            {"ar": "وذمة رئوية", "en": "pulmonary edema", "category": "DISEASE"},
            {"ar": "تجلط رئوي", "en": "pulmonary embolism", "category": "DISEASE"},
            {"ar": "سرطان الرئة", "en": "lung cancer", "category": "DISEASE"},
            {"ar": "سل", "en": "tuberculosis", "category": "DISEASE"},
            {"ar": "درن", "en": "TB", "category": "DISEASE"},
            {"ar": "قصور تنفسي", "en": "respiratory failure", "category": "DISEASE"},
        ]

        # ===== أمراض القلب والأوعية =====
        self.entities["DISEASE_CARDIAC"] = [
            {"ar": "تضخم القلب", "en": "cardiomegaly", "category": "DISEASE"},
            {"ar": "قصور قلب", "en": "heart failure", "category": "DISEASE"},
            {"ar": "احتشاء عضلة قلبية", "en": "myocardial infarction", "category": "DISEASE"},
            {"ar": "قصور تاجي", "en": "mitral regurgitation", "category": "DISEASE"},
            {"ar": "تصلب شرايين", "en": "atherosclerosis", "category": "DISEASE"},
            {"ar": "أتساع الشريان الأبهر", "en": "aortic aneurysm", "category": "DISEASE"},
            {"ar": "تامور قلبي", "en": "pericardial effusion", "category": "DISEASE"},
            {"ar": "اعتلال عضلة قلبية", "en": "cardiomyopathy", "category": "DISEASE"},
        ]

        # ===== الأمراض العصبية =====
        self.entities["DISEASE_NEUROLOGICAL"] = [
            {"ar": "سكتة دماغية", "en": "stroke", "category": "DISEASE"},
            {"ar": "ورم دماغي", "en": "brain tumor", "category": "DISEASE"},
            {"ar": "اعتلال دماغي", "en": "encephalopathy", "category": "DISEASE"},
            {"ar": "نزيف دماغي", "en": "intracranial hemorrhage", "category": "DISEASE"},
            {"ar": "صداع نصفي", "en": "migraine", "category": "DISEASE"},
            {"ar": "تصلب متعدد", "en": "multiple sclerosis", "category": "DISEASE"},
            {"ar": "صرع", "en": "epilepsy", "category": "DISEASE"},
            {"ar": "شلل", "en": "paralysis", "category": "DISEASE"},
        ]

        # ===== الإصابات والكسور =====
        self.entities["INJURY"] = [
            {"ar": "كسر", "en": "fracture", "category": "FINDING"},
            {"ar": "كسر مضاعف", "en": "comminuted fracture", "category": "FINDING"},
            {"ar": "كسر مفتوح", "en": "open fracture", "category": "FINDING"},
            {"ar": "خلع", "en": "dislocation", "category": "FINDING"},
            {"ar": "تمزق", "en": "tear", "category": "FINDING"},
            {"ar": "نزيف", "en": "hemorrhage", "category": "FINDING"},
            {"ar": "كدمة", "en": "contusion", "category": "FINDING"},
            {"ar": "إصابة", "en": "injury", "category": "FINDING"},
            {"ar": "رضح", "en": "trauma", "category": "FINDING"},
            {"ar": "ورم دموي", "en": "hematoma", "category": "FINDING"},
        ]

        # ===== الأورام =====
        self.entities["TUMOR"] = [
            {"ar": "ورم حميد", "en": "benign tumor", "category": "FINDING"},
            {"ar": "ورم خبيث", "en": "malignant tumor", "category": "FINDING"},
            {"ar": "سرطان", "en": "cancer", "category": "FISEASE"},
            {"ar": "ورم خلايا غير صغيرة", "en": "NSCLC", "category": "DISEASE"},
            {"ar": "سرطان القولون", "en": "colon cancer", "category": "DISEASE"},
            {"ar": "سرطان الثدي", "en": "breast cancer", "category": "DISEASE"},
            {"ar": "لمفوما", "en": "lymphoma", "category": "DISEASE"},
            {"ar": "ساركوما", "en": "sarcoma", "category": "DISEASE"},
            {"ar": "نقائل", "en": "metastasis", "category": "FINDING"},
            {"ar": "انتقالات ورمية", "en": "metastases", "category": "FINDING"},
        ]

        # ===== الأدوية =====
        self.entities["MEDICATION"] = [
            {"ar": "أسبرين", "en": "aspirin", "category": "MEDICATION"},
            {"ar": "باراسيتامول", "en": "paracetamol", "category": "MEDICATION"},
            {"ar": "أموكسيسيلين", "en": "amoxicillin", "category": "MEDICATION"},
            {"ar": "ميتفورمين", "en": "metformin", "category": "MEDICATION"},
            {"ar": "أنالجين", "en": "metamizole", "category": "MEDICATION"},
            {"ar": "إيبوبروفين", "en": "ibuprofen", "category": "MEDICATION"},
            {"ar": "أموكسيسيللاف", "en": "amoxicillin-clavulanate", "category": "MEDICATION"},
            {"ar": "سيبروفلوكساسين", "en": "ciprofloxacin", "category": "MEDICATION"},
            {"ar": "أزيثرومايسين", "en": "azithromycin", "category": "MEDICATION"},
            {"ar": "دكساميتازون", "en": "dexamethasone", "category": "MEDICATION"},
            {"ar": "بريدنيزولون", "en": "prednisolone", "category": "MEDICATION"},
            {"ar": "هيبارين", "en": "heparin", "category": "MEDICATION"},
            {"ar": "وارفارين", "en": "warfarin", "category": "MEDICATION"},
            {"ar": "أنسولين", "en": "insulin", "category": "MEDICATION"},
            {"ar": "أملوديبين", "en": "amlodipine", "category": "MEDICATION"},
        ]

        # ===== التشريح =====
        self.entities["ANATOMY"] = [
            {"ar": "رئة", "en": "lung", "category": "ANATOMY"},
            {"ar": "قلب", "en": "heart", "category": "ANATOMY"},
            {"ar": "كبد", "en": "liver", "category": "ANATOMY"},
            {"ar": "كلية", "en": "kidney", "category": "ANATOMY"},
            {"ar": "طحال", "en": "spleen", "category": "ANATOMY"},
            {"ar": "بنكرياس", "en": "pancreas", "category": "ANATOMY"},
            {"ar": "معدة", "en": "stomach", "category": "ANATOMY"},
            {"ar": "أمعاء", "en": "intestine", "category": "ANATOMY"},
            {"ar": "عمود فقري", "en": "spine", "category": "ANATOMY"},
            {"ar": "جمجمة", "en": "skull", "category": "ANATOMY"},
            {"ar": "ضلع", "en": "rib", "category": "ANATOMY"},
            {"ar": "ترقوة", "en": "clavicle", "category": "ANATOMY"},
            {"ar": "كتف", "en": "shoulder", "category": "ANATOMY"},
            {"ar": "ورك", "en": "hip", "category": "ANATOMY"},
            {"ar": "ركبة", "en": "knee", "category": "ANATOMY"},
            {"ar": "عظم فخذ", "en": "femur", "category": "ANATOMY"},
            {"ar": "عظم ساق", "en": "tibia", "category": "ANATOMY"},
            {"ar": "عظم عضد", "en": "humerus", "category": "ANATOMY"},
            {"ar": "ساعد", "en": "forearm", "category": "ANATOMY"},
            {"ar": "شريان أبهر", "en": "aorta", "category": "ANATOMY"},
            {"ar": "منصف", "en": "mediastinum", "category": "ANATOMY"},
            {"ar": "غشاء جنبي", "en": "pleura", "category": "ANATOMY"},
            {"ar": "قصبة هوائية", "en": "trachea", "category": "ANATOMY"},
            {"ar": "قصبات هوائية", "en": "bronchi", "category": "ANATOMY"},
        ]

        # ===== الجانبية =====
        self.entities["LATERALITY"] = [
            {"ar": "أيمن", "en": "right", "category": "LATERALITY"},
            {"ar": "أيسر", "en": "left", "category": "LATERALITY"},
            {"ar": "ثنائي الجانب", "en": "bilateral", "category": "LATERALITY"},
            {"ar": "يمين", "en": "right side", "category": "LATERALITY"},
            {"ar": "يسار", "en": "left side", "category": "LATERALITY"},
        ]

        # ===== الشدة =====
        self.entities["SEVERITY"] = [
            {"ar": "خفيف", "en": "mild", "category": "SEVERITY"},
            {"ar": "متوسط", "en": "moderate", "category": "SEVERITY"},
            {"ar": "شديد", "en": "severe", "category": "SEVERITY"},
            {"ar": "حاد", "en": "acute", "category": "SEVERITY"},
            {"ar": "مزمن", "en": "chronic", "category": "SEVERITY"},
            {"ar": "مبكر", "en": "early", "category": "SEVERITY"},
            {"ar": "متقدم", "en": "advanced", "category": "SEVERITY"},
        ]

    def _load_custom(self, path: str):
        """تحميل قاموس مخصص من ملف JSON"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                custom_data = json.load(f)
            for key, entities in custom_data.items():
                if key not in self.entities:
                    self.entities[key] = []
                self.entities[key].extend(entities)
            logger.info(f"تم تحميل قاموس مخصص: {path}")
        except Exception as e:
            logger.error(f"فشل تحميل القاموس المخصص: {e}")

    def search(self, text: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        البحث في القاموس عن كيانات طبية في النص

        Args:
            text: النص المطلوب البحث فيه
            threshold: حد أدنى لمستوى التطابق

        Returns:
            قائمة بالكيانات المطابقة
        """
        results = []
        text_lower = text.lower()

        for category, entities in self.entities.items():
            for entity in entities:
                for lang in ["ar", "en"]:
                    term = entity.get(lang, "")
                    if not term:
                        continue
                    if term.lower() in text_lower:
                        results.append({
                            "text": term,
                            "category": entity.get("category", category),
                            "subcategory": category,
                            "ar": entity.get("ar", ""),
                            "en": entity.get("en", ""),
                            "confidence": 1.0 if term.lower() in text_lower else 0.9,
                        })
                        break  # تجنب التكرار

        return results

    def get_categories(self) -> List[str]:
        """إرجاع قائمة التصنيفات المتاحة"""
        return list(self.entities.keys())

    def export_json(self, filepath: str):
        """تصدير القاموس إلى ملف JSON"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.entities, f, ensure_ascii=False, indent=2)
        logger.info(f"تم تصدير القاموس: {filepath}")


class MedicalEntityExtractor:
    """
    مستخرج الكيانات الطبية المتقدم
    يجمع بين البحث في القاموس والتعرف على الأنماط
    """

    def __init__(self, dictionary: Optional[MedicalDictionary] = None):
        self.dictionary = dictionary or MedicalDictionary()

    def extract(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        استخراج جميع الكيانات الطبية من النص

        Args:
            text: النص الطبي

        Returns:
            قاموس مرتب حسب التصنيف
        """
        entities = self.dictionary.search(text)

        # تنظيم النتائج حسب التصنيف
        organized = {}
        for entity in entities:
            cat = entity["category"]
            if cat not in organized:
                organized[cat] = []
            organized[cat].append(entity)

        return organized

    def extract_with_context(
        self, text: str, context_window: int = 50
    ) -> List[Dict[str, Any]]:
        """
        استخراج الكيانات مع السياق المحيطي

        Args:
            text: النص الطبي
            context_window: عدد الأحرف المحيطة

        Returns:
            قائمة بالكيانات والسياق
        """
        entities = self.dictionary.search(text)
        results = []

        for entity in entities:
            term = entity["text"]
            idx = text.lower().find(term.lower())
            if idx >= 0:
                start = max(0, idx - context_window)
                end = min(len(text), idx + len(term) + context_window)
                entity["context"] = text[start:end]
                entity["position"] = idx
                results.append(entity)

        return results
