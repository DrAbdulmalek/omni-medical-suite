"""
Tests for KeywordRouter — classify sample medical text, verify category and confidence.
"""

import pytest
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Minimal KeywordRouter replica for standalone testing
# ---------------------------------------------------------------------------

# Medical category keyword definitions
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "anatomy": [
        "anatomical", "organ", "tissue", "cell", "bone", "muscle",
        "nerve", "vessel", "artery", "vein", "ligament", "tendon",
        "解剖", "عضو", "نسيج", "خلية", "عظم", "عضلة", "عصب", "شريان",
    ],
    "pharmacology": [
        "drug", "medication", "dose", "pharmacokinetic", "interaction",
        "contraindication", "side effect", "prescription", "tablet",
        "دواء", "جرعة", "تفاعل", "موانع", "وصفة", "أعراض جانبية",
    ],
    "pathology": [
        "disease", "diagnosis", "symptom", "lesion", "tumor", "cancer",
        "inflammation", "infection", "malignant", "benign",
        "مرض", "تشخيص", "عرض", "ورم", "سرطان", "التهاب", "عدوى",
    ],
    "surgery": [
        "surgical", "operation", "incision", "procedure", "anesthesia",
        "scalpel", "suture", "transplant", "resection",
        "جراحة", "عملية", "شق", "تخدير", "خياطة", "زراعة",
    ],
    "cardiology": [
        "heart", "cardiac", "coronary", "arrhythmia", "ecg", "echocardiogram",
        "myocardial", "valve", "stent", "bypass",
        "قلب", "أذينة", "تخطيط", "صمام", "قسطرة",
    ],
    "neurology": [
        "brain", "neural", "neuron", "synapse", "cortex", "cerebral",
        "epilepsy", "stroke", "migraine", "neurodegenerative",
        "دماغ", "عصبي", "خلايا عصبية", "صرع", "سكتة",
    ],
}


class ClassificationResult:
    """Lightweight classification result."""

    __slots__ = ("chunk_id", "category", "confidence", "matched_keywords", "method")

    def __init__(
        self,
        chunk_id: str,
        category: str,
        confidence: float,
        matched_keywords: List[str],
        method: str = "keyword",
    ):
        self.chunk_id = chunk_id
        self.category = category
        self.confidence = confidence
        self.matched_keywords = matched_keywords
        self.method = method


class KeywordRouter:
    """Classify text chunks using keyword matching."""

    def __init__(self, keywords: Optional[Dict[str, List[str]]] = None):
        self.keywords = keywords or CATEGORY_KEYWORDS

    def classify(self, text: str, chunk_id: str = "unknown") -> ClassificationResult:
        """Classify a text string by keyword overlap."""
        if not text or not text.strip():
            return ClassificationResult(
                chunk_id=chunk_id,
                category="unclassified",
                confidence=0.0,
                matched_keywords=[],
            )

        text_lower = text.lower()
        scores: Dict[str, int] = {}
        keyword_matches: Dict[str, List[str]] = {}

        for category, kws in self.keywords.items():
            matched = [kw for kw in kws if kw.lower() in text_lower]
            if matched:
                scores[category] = len(matched)
                keyword_matches[category] = matched

        if not scores:
            return ClassificationResult(
                chunk_id=chunk_id,
                category="unclassified",
                confidence=0.0,
                matched_keywords=[],
            )

        # Pick category with the most keyword hits
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        # Confidence: fraction of matched keywords vs. total keywords for category
        total_kws = len(self.keywords[best_category])
        confidence = min(best_score / max(total_kws, 1), 1.0)
        # Boost confidence slightly if multiple categories matched
        if len(scores) > 1:
            confidence = min(confidence + 0.1, 1.0)

        return ClassificationResult(
            chunk_id=chunk_id,
            category=best_category,
            confidence=round(confidence, 4),
            matched_keywords=keyword_matches[best_category],
            method="keyword",
        )


# ── Tests ──────────────────────────────────────────────────────────────────

class TestKeywordRouterInit:
    """Test classifier initialization."""

    def test_default_keywords(self):
        router = KeywordRouter()
        assert "anatomy" in router.keywords
        assert "pharmacology" in router.keywords
        assert "cardiology" in router.keywords

    def test_custom_keywords(self):
        custom = {"cat_a": ["alpha", "beta"], "cat_b": ["gamma"]}
        router = KeywordRouter(keywords=custom)
        assert router.keywords == custom


class TestKeywordRouterClassify:
    """Test classification of medical text samples."""

    def test_classify_cardiology(self):
        router = KeywordRouter()
        text = "The patient presented with cardiac arrhythmia and coronary artery disease. An ECG showed abnormal rhythms."
        result = router.classify(text, chunk_id="c1")
        assert result.category == "cardiology"
        assert result.confidence > 0.0
        assert result.method == "keyword"
        assert len(result.matched_keywords) > 0
        assert result.chunk_id == "c1"

    def test_classify_pharmacology(self):
        router = KeywordRouter()
        text = "The prescribed medication includes a daily dose of beta-blockers. Side effects may include fatigue."
        result = router.classify(text, chunk_id="c2")
        assert result.category == "pharmacology"
        assert result.confidence > 0.0
        assert any("drug" in kw or "medication" in kw or "dose" in kw or "side effect" in kw
                    for kw in result.matched_keywords)

    def test_classify_anatomy(self):
        router = KeywordRouter()
        text = "The heart muscle contains cardiac muscle tissue, supplied by the coronary artery and nerve fibers."
        result = router.classify(text, chunk_id="c3")
        # Heart + muscle + tissue should hit anatomy or cardiology
        assert result.category in ("anatomy", "cardiology")
        assert result.confidence > 0.0

    def test_classify_empty_text(self):
        router = KeywordRouter()
        result = router.classify("", chunk_id="c_empty")
        assert result.category == "unclassified"
        assert result.confidence == 0.0
        assert result.matched_keywords == []

    def test_classify_whitespace_only(self):
        router = KeywordRouter()
        result = router.classify("   \n\t  ", chunk_id="c_ws")
        assert result.category == "unclassified"
        assert result.confidence == 0.0

    def test_classify_no_match(self):
        router = KeywordRouter()
        text = "The weather today is sunny with clear skies and mild temperatures."
        result = router.classify(text, chunk_id="c_none")
        assert result.category == "unclassified"
        assert result.confidence == 0.0

    def test_confidence_within_bounds(self):
        router = KeywordRouter()
        for text in [
            "heart cardiac coronary",
            "drug medication dose interaction",
            "brain neural neuron synapse cortex",
            "disease diagnosis symptom inflammation",
            "surgical operation incision procedure",
        ]:
            result = router.classify(text)
            assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range for: {text}"

    def test_matched_keywords_are_from_category(self):
        router = KeywordRouter()
        text = "The cardiac muscle tissue showed inflammation and infection."
        result = router.classify(text)
        if result.category != "unclassified":
            cat_keywords = set(kw.lower() for kw in router.keywords[result.category])
            for kw in result.matched_keywords:
                assert kw.lower() in cat_keywords, f"Keyword '{kw}' not in category '{result.category}'"

    def test_batch_classify(self):
        router = KeywordRouter()
        texts = [
            "The patient needs a cardiac stent procedure.",
            "Prescribe 50mg dose of the drug.",
            "Brain stroke symptoms include sudden weakness.",
            "The bone fracture requires surgical repair.",
        ]
        results = [router.classify(t, chunk_id=f"batch_{i}") for i, t in enumerate(texts)]
        categories = [r.category for r in results]
        assert "cardiology" in categories
        assert "pharmacology" in categories
        assert "neurology" in categories
        assert "surgery" in categories
