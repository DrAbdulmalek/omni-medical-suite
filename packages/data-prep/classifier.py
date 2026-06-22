"""
Medical Document Classifier
============================
Two-layer classification: keyword routing (fast) → semantic matching (optional).

Adapted from ai-fuel-engine classifier module for the data preparation pipeline.

Author: Dr. Abdulmalek
Version: 1.0.0
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


# Built-in medical taxonomy
MEDICAL_TAXONOMY = {
    "cardiology": {
        "keywords_en": [
            "heart", "cardiac", "coronary", "angina", "myocardial", "arrhythmia",
            "ecg", "ekg", "echocardiogram", "stent", "bypass", "valve", "aortic",
            "mitral", "tricuspid", "pulmonary", "hypertension", "cholesterol",
            "ldl", "hdl", "troponin", "bnp", "heart failure", "cabg", "pci",
            "afib", "atrial fibrillation", "ventricular", "tachycardia", "bradycardia",
        ],
        "keywords_ar": [
            "قلب", "تاجي", "ذبحة", "صمام", "أذين", "بطين", "رجفان", "قصور",
            "احتشاء", "تصلب", "شرايين", "ضغط الدم", "كوليسترول", "نوبة قلبية",
            "خثرة", "انصمام", "تنظير قلب", "قسطرة", "داعم", "مجازة",
        ],
    },
    "radiology": {
        "keywords_en": [
            "x-ray", "xray", "ct scan", "mri", "ultrasound", "sonography",
            "radiograph", "fluoroscopy", "angiography", "pet scan", "mammogram",
            "lesion", "mass", "nodule", "fracture", "opacity", "effusion",
            "contrast", "radiology", "imaging", "scan",
        ],
        "keywords_ar": [
            "أشعة", "صورة شعاعية", "رنين مغناطيسي", "موجات فوق صوتية",
            "طبقي محوري", "تصوير", "ظل", "كسر", "انصباب", "ورم",
            "عقدة", "آفة", "صورة", "مقطعية",
        ],
    },
    "laboratory": {
        "keywords_en": [
            "lab", "laboratory", "blood test", "urinalysis", "culture",
            "sensitivity", "hemoglobin", "wbc", "rbc", "platelet", "glucose",
            "creatinine", "bun", "electrolyte", "liver function", "kidney function",
            "thyroid", "tsh", "hba1c", "lipid panel", "coagulation", "inr", "pt",
        ],
        "keywords_ar": [
            "مختبر", "تحليل", "دم", "بول", "زراعة", "حساسية",
            "هيموغلوبين", "كريات", "صفيحات", "سكر", "كرياتينين",
            "وظائف كبد", "وظائف كلية", "درقي", "شحوم",
        ],
    },
    "prescriptions": {
        "keywords_en": [
            "prescription", "rx", "dosage", "dose", "medication", "drug",
            "tablet", "capsule", "syrup", "injection", "cream", "ointment",
            "twice daily", "once daily", "three times", "before meals", "after meals",
            "mg", "ml", "iu", "refill", "dispense", "pharmacy",
        ],
        "keywords_ar": [
            "وصفة", "دواء", "جرعة", "قرص", "كبسولة", "شراب", "حقنة",
            "مرتين يوميا", "مرة يوميا", "قبل الأكل", "بعد الأكل",
            "ملغ", "ملي", "صيدلية", "إعادة", "كمية",
        ],
    },
    "surgery": {
        "keywords_en": [
            "surgery", "operation", "procedure", "incision", "excision",
            "resection", "anastomosis", "laparoscopy", "arthroscopy", "biopsy",
            "pre-operative", "post-operative", "intra-operative", "anesthesia",
            "suture", "drain", "wound", "scar", "complication",
        ],
        "keywords_ar": [
            "عملية", "جراحة", "شق", "استئصال", "ربط", "تنظير بطني",
            "تنظير مفصل", "خزعة", "قبل العملية", "بعد العملية",
            "تخدير", "غرزة", "تصريف", "جرح", "مضاعفة",
        ],
    },
    "orthopedics": {
        "keywords_en": [
            "fracture", "dislocation", "sprain", "ligament", "tendon",
            "acl", "mcl", "meniscus", "cartilage", "joint", "spine",
            "vertebra", "disc", "herniation", "arthroplasty", "osteotomy",
            "bone", "femur", "tibia", "humerus", "radius", "ulna",
            "cast", "splint", "fixation", "plate", "screw",
        ],
        "keywords_ar": [
            "كسر", "خلع", "إصابة", "رباط", "وتر", "غضروف",
            "مفصل", "عمود فقري", "فقرات", "قرص", "فتق",
            "استبدال مفصل", "عظم", "فخذ", "ساق", "كتف",
            "جبس", "تثبيت", "لوح", "مسمار",
        ],
    },
    "pathology": {
        "keywords_en": [
            "biopsy", "histology", "cytology", "pathology", "malignant",
            "benign", "tumor", "carcinoma", "sarcoma", "lymphoma",
            "adenocarcinoma", "metastasis", "grade", "stage", "margin",
            "immunohistochemistry", "ihc", "marker",
        ],
        "keywords_ar": [
            "خزعة", "نسيج", "خلايا", "أمراض", "خبيث", "حميد",
            "ورم", "سرطان", "غدد", "انبثاث", "درجة", "مرحلة",
            "هامش", "مناعة", "نسيجي",
        ],
    },
}


@dataclass
class ClassificationResult:
    """Result of document classification."""
    text: str
    category: str
    confidence: float
    method: str  # "keyword", "semantic", "fallback"
    top_categories: List[Tuple[str, float]] = field(default_factory=list)


class MedicalDocumentClassifier:
    """
    Two-layer medical document classifier for data preparation.
    
    Layer 1: Keyword routing (< 1ms) — inverted index with weighted voting
    Layer 2: Semantic matching (~50ms, optional) — vector similarity
    
    This is a DATA PREPARATION tool, not part of the live OCR pipeline.
    Use it when organizing corpus data or building datasets.
    """
    
    def __init__(self, taxonomy: Optional[Dict] = None, confidence_threshold: float = 0.7):
        self.taxonomy = taxonomy or MEDICAL_TAXONOMY
        self.confidence_threshold = confidence_threshold
        self._inverted_index = self._build_inverted_index()
        self._semantic_model = None
        self._taxonomy_embeddings = {}
    
    def _normalize_arabic(self, text: str) -> str:
        """Normalize Arabic text for matching."""
        # Remove diacritics
        for i in range(0x064B, 0x065F):
            text = text.replace(chr(i), '')
        # Normalize alef variants
        text = text.replace('\u0623', '\u0627').replace('\u0625', '\u0627')
        text = text.replace('\u0622', '\u0627')
        text = text.replace('\u0649', '\u064a')
        return text.lower()
    
    def _build_inverted_index(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build inverted index: keyword → [(category, weight)]."""
        index = defaultdict(list)
        
        for category, data in self.taxonomy.items():
            # English keywords
            for kw in data.get("keywords_en", []):
                weight = 1.0
                # Longer keywords are more specific
                if len(kw.split()) > 1:
                    weight = 1.5
                index[kw.lower()].append((category, weight))
            
            # Arabic keywords
            for kw in data.get("keywords_ar", []):
                normalized = self._normalize_arabic(kw)
                weight = 1.0
                if len(kw.split()) > 1:
                    weight = 1.5
                index[normalized].append((category, weight))
        
        return dict(index)
    
    def classify(self, text: str) -> ClassificationResult:
        """Classify a medical document text."""
        # Layer 1: Keyword routing
        result = self._keyword_classify(text)
        
        if result and result.confidence >= self.confidence_threshold:
            return result
        
        # Layer 2: Semantic (if available)
        semantic_result = self._semantic_classify(text)
        if semantic_result:
            return semantic_result
        
        # Fallback
        return ClassificationResult(
            text=text,
            category="unclassified",
            confidence=0.0,
            method="fallback",
            top_categories=result.top_categories if result else [],
        )
    
    def _keyword_classify(self, text: str) -> Optional[ClassificationResult]:
        """Layer 1: Fast keyword-based classification."""
        text_lower = text.lower()
        text_ar = self._normalize_arabic(text)
        
        scores = defaultdict(float)
        total_weight = 0.0
        
        # Check all keywords
        for keyword, entries in self._inverted_index.items():
            if keyword in text_lower or keyword in text_ar:
                for category, weight in entries:
                    scores[category] += weight
                    total_weight += weight
        
        if not scores:
            return None
        
        # Normalize scores
        for cat in scores:
            scores[cat] /= max(total_weight, 1)
        
        # Sort by score
        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_category, best_score = sorted_cats[0]
        
        return ClassificationResult(
            text=text,
            category=best_category,
            confidence=best_score,
            method="keyword",
            top_categories=sorted_cats[:5],
        )
    
    def _semantic_classify(self, text: str) -> Optional[ClassificationResult]:
        """Layer 2: Semantic classification using sentence embeddings."""
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            if self._semantic_model is None:
                self._semantic_model = SentenceTransformer(
                    'paraphrase-multilingual-mpnet-base-v2'
                )
                # Pre-compute taxonomy embeddings
                for category, data in self.taxonomy.items():
                    all_terms = data.get("keywords_en", []) + data.get("keywords_ar", [])
                    combined = ' '.join(all_terms)
                    self._taxonomy_embeddings[category] = self._semantic_model.encode(combined)
            
            text_embedding = self._semantic_model.encode(text)
            
            similarities = {}
            for category, cat_embedding in self._taxonomy_embeddings.items():
                sim = float(np.dot(text_embedding, cat_embedding) /
                           (np.linalg.norm(text_embedding) * np.linalg.norm(cat_embedding) + 1e-8))
                similarities[category] = sim
            
            sorted_cats = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
            best_category, best_score = sorted_cats[0]
            
            if best_score < self.confidence_threshold:
                return None
            
            return ClassificationResult(
                text=text,
                category=best_category,
                confidence=best_score,
                method="semantic",
                top_categories=sorted_cats[:5],
            )
            
        except ImportError:
            logger.debug("sentence-transformers not available, skipping semantic classification")
            return None
        except Exception as e:
            logger.warning(f"Semantic classification failed: {e}")
            return None
    
    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """Classify multiple texts."""
        return [self.classify(text) for text in texts]


# Ensure the package directory structure is correct
# The __init__.py, segmenter.py, dedup.py, classifier.py should all be in the same directory.