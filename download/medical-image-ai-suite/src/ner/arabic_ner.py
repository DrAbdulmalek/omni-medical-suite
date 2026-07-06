"""
مستخرج الكيانات الطبية العربية - Arabic Medical NER
استخراج الكيانات المسماة من التقارير الطبية باستخدام النماذج التوليدية
يدعم AraBERT و CAMeL Tools و استخراج مخصص
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import numpy as np

from .medical_entities import MedicalDictionary, MedicalEntityExtractor
from ..utils.logger import get_logger

logger = get_logger("arabic_ner")


class ArabicMedicalNER:
    """
    مستخرج الكيانات الطبية العربية المتقدم

    يجمع بين ثلاثة أساليب:
    1. مطابقة القاموس (Dictionary Matching) - سريع ومضمون
    2. التعرف على الأنماط (Pattern Recognition) - للقياسات والتواريخ
    3. نموذج التعلم العميق (Deep Learning) - AraBERT/CAMeL (اختياري)

    الاستخدام:
        ner = ArabicMedicalNER()
        results = ner.extract("يظهر الفحص وجود التهاب رئوي في الرئة اليمنى مع انصباب جنبي")
        # results = {
        #   "entities": [...],
        #   "relations": [...],
        #   "negated": [...],
        #   "labels": {"pneumonia": 1.0, "pleural_effusion": 1.0}
        # }
    """

    def __init__(
        self,
        use_dictionary: bool = True,
        use_patterns: bool = True,
        use_model: bool = False,
        model_name: str = "aubmindlab/bert-base-arabertv02",
        confidence_threshold: float = 0.75,
        custom_dictionary_path: Optional[str] = None,
    ):
        """
        Args:
            use_dictionary: تفعيل مطابقة القاموس
            use_patterns: تفعيل التعرف على الأنماط
            use_model: تفعيل نموذج التعلم العميق
            model_name: اسم نموذج HuggingFace
            confidence_threshold: حد الثقة الأدنى
            custom_dictionary_path: مسار قاموس مخصص
        """
        self.use_dictionary = use_dictionary
        self.use_patterns = use_patterns
        self.use_model = use_model
        self.confidence_threshold = confidence_threshold

        # تهيئة القاموس
        self.dictionary = MedicalDictionary(custom_path=custom_dictionary_path)
        self.entity_extractor = MedicalEntityExtractor(self.dictionary)

        # تهيئة النموذج (اختياري)
        self.model = None
        self.tokenizer = None
        if use_model:
            self._load_model(model_name)

        # أنماط التعرف على الكيانات
        self.patterns = self._build_patterns()

        logger.info(
            f"تم تهيئة NER (قاموس: {use_dictionary}, أنماط: {use_patterns}, نموذج: {use_model})"
        )

    def _load_model(self, model_name: str):
        """تحميل نموذج NER"""
        try:
            from transformers import AutoTokenizer, AutoModelForTokenClassification
            import torch

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForTokenClassification.from_pretrained(model_name)
            self.model.eval()

            if torch.cuda.is_available():
                self.model = self.model.cuda()

            logger.info(f"تم تحميل نموذج NER: {model_name}")
        except ImportError:
            logger.warning("transformers غير مثبت. سيتم استخدام القاموس فقط.")
            self.use_model = False
        except Exception as e:
            logger.warning(f"فشل تحميل النموذج: {e}. سيتم استخدام القاموس فقط.")
            self.use_model = False

    def _build_patterns(self) -> Dict[str, re.Pattern]:
        """بناء أنماط Regex للتعرف على الكيانات"""
        return {
            "measurement": re.compile(
                r"(\d+(?:\.\d+)?)\s*(?:سم|mm|cm|mL|مل|μg|mg|كغ|kg|%|×)\b"
            ),
            "date": re.compile(
                r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b"
            ),
            "patient_id": re.compile(
                r"\b(?:MRN|ID|رقم المريض)[:\s]*([A-Za-z0-9-]+)"
            ),
            "accession": re.compile(
                r"\b(?:Acc|Accession|رقم الفحص)[:\s]*([A-Za-z0-9-]+)"
            ),
            "age": re.compile(
                r"\b(\d+)\s*(?:سنة|سنين|عام|أعوام|year|years|yo)\b"
            ),
            "sex": re.compile(
                r"\b(?:ذكر|أنثى|male|female|M|F)\b"
            ),
        }

    def extract(self, text: str) -> Dict[str, Any]:
        """
        استخراج جميع الكيانات الطبية من النص

        Args:
            text: النص الطبي (عربي أو إنجليزي أو مختلط)

        Returns:
            قاموس شامل بالنتائج:
            {
                "entities": [...],
                "relations": [...],
                "negated": [...],
                "labels": {فئة: ثقة},
                "measurements": [...],
            }
        """
        results = {
            "entities": [],
            "relations": [],
            "negated": [],
            "labels": {},
            "measurements": [],
            "metadata": {},
        }

        # 1. مطابقة القاموس
        if self.use_dictionary:
            dict_entities = self.entity_extractor.extract_with_context(text)
            results["entities"].extend(dict_entities)

        # 2. التعرف على الأنماط
        if self.use_patterns:
            pattern_results = self._extract_patterns(text)
            results["measurements"] = pattern_results.get("measurements", [])
            results["metadata"] = pattern_results.get("metadata", {})

        # 3. النموذج (إن فُعّل)
        if self.use_model and self.model:
            model_entities = self._extract_with_model(text)
            # دمج مع نتائج القاموس (تجنب التكرار)
            existing_texts = {e["text"] for e in results["entities"]}
            for entity in model_entities:
                if entity["text"] not in existing_texts:
                    results["entities"].append(entity)

        # 4. كشف النفي
        results["negated"] = self._detect_negations(text, results["entities"])

        # 5. استخراج العلاقات
        results["relations"] = self._extract_relations(results["entities"])

        # 6. توليد إشارات تصنيف
        results["labels"] = self._generate_labels(results["entities"], results["negated"])

        return results

    def extract_from_report(self, report: Dict[str, str]) -> Dict[str, Any]:
        """
        استخراج الكيانات من تقرير مقسّم إلى أقسام

        Args:
            report: قاموس {اسم_القسم: محتوى}

        Returns:
            نتائج NER لكل قسم
        """
        full_results = {}
        total_entities = []
        total_negated = set()

        for section_name, section_text in report.items():
            if not section_text or len(section_text) < 3:
                full_results[section_name] = {"entities": [], "labels": {}}
                continue

            section_results = self.extract(section_text)
            full_results[section_name] = section_results

            # تجميع الكيانات
            for entity in section_results.get("entities", []):
                entity["section"] = section_name
                total_entities.append(entity)

            # تجميع المنفيّات
            for negated in section_results.get("negated", []):
                total_negated.add(negated.lower())

        # الإشارات النهائية (مع مراعاة النفي)
        final_labels = self._generate_labels(total_entities, list(total_negated))
        full_results["summary"] = {
            "total_entities": len(total_entities),
            "categories": list(set(e["category"] for e in total_entities)),
            "labels": final_labels,
            "has_negation": len(total_negated) > 0,
        }

        return full_results

    def extract_training_labels(
        self,
        text: str,
        label_schema: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, float]:
        """
        استخراج إشارات تدريب من النص للاستخدام في التعلم شبه الخاضع للإشراف

        Args:
            text: النص الطبي
            label_schema: مخطط التصنيفات (لا شيء = تلقائي)

        Returns:
            قاموس {اسم_الفئة: ثقة (0.0-1.0)}
        """
        results = self.extract(text)
        labels = results.get("labels", {})

        # تصفية حسب الحد الأدنى للثقة
        filtered = {
            k: v for k, v in labels.items()
            if v >= self.confidence_threshold
        }

        return filtered

    def _extract_patterns(self, text: str) -> Dict[str, Any]:
        """استخراج الكيانات باستخدام الأنماط"""
        results = {"measurements": [], "metadata": {}}

        # القياسات
        for match in self.patterns["measurement"].finditer(text):
            value = float(match.group(1))
            unit = match.group(0).split()[-1] if " " in match.group(0) else ""
            context_start = max(0, match.start() - 30)
            context_end = min(len(text), match.end() + 30)
            results["measurements"].append({
                "value": value,
                "unit": unit,
                "full_match": match.group(0),
                "context": text[context_start:context_end],
                "position": match.start(),
            })

        # بيانات التعريف
        for match in self.patterns["patient_id"].finditer(text):
            results["metadata"]["patient_id"] = match.group(1)
        for match in self.patterns["accession"].finditer(text):
            results["metadata"]["accession"] = match.group(1)
        for match in self.patterns["age"].finditer(text):
            results["metadata"]["age"] = int(match.group(1))
        for match in self.patterns["sex"].finditer(text):
            results["metadata"]["sex"] = match.group(0)

        return results

    def _extract_with_model(self, text: str) -> List[Dict[str, Any]]:
        """استخراج الكيانات باستخدام نموذج التعلم العميق"""
        try:
            import torch

            inputs = self.tokenizer(
                text, return_tensors="pt",
                truncation=True, max_length=512,
            )

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            predictions = torch.argmax(outputs.logits, dim=-1)[0]
            tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])

            # تجميع الكيانات من التوكنات
            entities = []
            current_entity = {"tokens": [], "label": None}

            for token, pred_id in zip(tokens, predictions.cpu().numpy()):
                label = self.model.config.id2label[pred_id]

                if label.startswith("B-"):
                    if current_entity["tokens"]:
                        entities.append(self._format_model_entity(current_entity))
                    current_entity = {"tokens": [token], "label": label[2:]}
                elif label.startswith("I-") and current_entity["label"] == label[2:]:
                    current_entity["tokens"].append(token)
                else:
                    if current_entity["tokens"]:
                        entities.append(self._format_model_entity(current_entity))
                    current_entity = {"tokens": [], "label": None}

            if current_entity["tokens"]:
                entities.append(self._format_model_entity(current_entity))

            return entities

        except Exception as e:
            logger.error(f"خطأ في النموذج: {e}")
            return []

    def _format_model_entity(self, entity: Dict) -> Dict[str, Any]:
        """تنسيق كيان من مخرجات النموذج"""
        text = " ".join(t.replace("##", "") for t in entity["tokens"])
        return {
            "text": text,
            "category": entity["label"],
            "source": "model",
            "confidence": 0.8,
        }

    def _detect_negations(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """كشف الكيانات المنفية"""
        negation_words = [
            "لا يوجد", "لا يُظهر", "بدون", "غير موجود", "نفي",
            "سالب", "طبيعي", "within normal", "no evidence",
            "negative", "no", "without", "absent", "normal",
            "unremarkable", "denied", "لا توجد علامات",
        ]

        negated = []
        text_lower = text.lower()

        for entity in entities:
            entity_text = entity.get("text", "")
            if not entity_text:
                continue

            idx = text_lower.find(entity_text.lower())
            if idx < 0:
                continue

            # البحث عن كلمة نفي في النافذة المحيطة
            window_start = max(0, idx - 40)
            window_end = min(len(text), idx + len(entity_text) + 40)
            window = text_lower[window_start:window_end]

            if any(neg in window for neg in negation_words):
                negated.append(entity_text)
                entity["is_negated"] = True
            else:
                entity["is_negated"] = False

        return negated

    def _extract_relations(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """استخراج العلاقات بين الكيانات"""
        relations = []

        # ربط الأمراض بالتشريح
        diseases = [e for e in entities if e.get("category") in ("DISEASE", "FINDING")]
        anatomy = [e for e in entities if e.get("category") == "ANATOMY"]
        lateralities = [e for e in entities if e.get("category") == "LATERALITY"]
        severities = [e for e in entities if e.get("category") == "SEVERITY"]

        for disease in diseases:
            relation = {"subject": disease.get("text", ""), "relations": {}}

            # ربط بالتشريح
            for anat in anatomy:
                if self._are_close(disease, anat):
                    relation["relations"]["location"] = anat.get("text", "")

            # ربط بالجانبية
            for lat in lateralities:
                if self._are_close(disease, lat):
                    relation["relations"]["laterality"] = lat.get("text", "")

            # ربط بالشدة
            for sev in severities:
                if self._are_close(disease, sev):
                    relation["relations"]["severity"] = sev.get("text", "")

            if relation["relations"]:
                relations.append(relation)

        return relations

    def _are_close(self, entity1: Dict, entity2: Dict, max_distance: int = 100) -> bool:
        """التحقق من قرب كيانين في النص"""
        pos1 = entity1.get("position", 0)
        pos2 = entity2.get("position", 0)
        return abs(pos1 - pos2) <= max_distance

    def _generate_labels(
        self, entities: List[Dict[str, Any]], negated: List[str]
    ) -> Dict[str, float]:
        """
        توليد إشارات تصنيف من الكيانات

        يُحوّل الكيانات المستخرجة إلى تصنيفات ثنائية أو متعددة
        مع مراعاة النفي (الكيانات المنفية تحصل على ثقة سالبة)
        """
        labels = {}

        for entity in entities:
            text = entity.get("text", "").strip()
            category = entity.get("category", "")
            confidence = entity.get("confidence", 0.8)
            is_negated = entity.get("is_negated", text.lower() in [n.lower() for n in negated])

            # استخدام الاسم الإنجليزي كتسمية (أكثر موثوقية للنماذج)
            label_key = entity.get("en", text)
            if not label_key:
                label_key = text

            # تعديل الثقة حسب النفي
            if is_negated:
                confidence = -confidence  # إشارة سلبية (لا يوجد مرض)

            # الحفاظ على أعلى ثقة لكل تسمية
            if label_key not in labels or abs(confidence) > abs(labels[label_key]):
                labels[label_key] = confidence

        # إضافة تصنيفات ثنائية عامة
        disease_entities = [e for e in entities if e.get("category") in ("DISEASE", "FINDING")]
        if disease_entities:
            non_negated = [
                e for e in disease_entities
                if not e.get("is_negated", False)
            ]
            labels["abnormal"] = 1.0 if non_negated else 0.0
        else:
            labels["normal"] = 0.8  # الأرجح أنه تقرير طبيعي

        return labels
