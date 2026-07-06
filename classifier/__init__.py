"""
AI Fuel Engine - Hierarchical Classifier Module

Provides a 3-layer hierarchical text classification system for the
AI Fuel Engine pipeline.  Classification flows through increasingly
sophisticated (and expensive) layers until a confident result is found:

    **Layer 1 — Keyword Router** (``<1ms``)
        Fast inverted-index keyword matching with weighted voting.
        Handles Arabic and English medical terminology.

    **Layer 2 — Semantic Matcher** (``~50ms``)
        Vector-similarity search against a reference embedding index.
        Uses multilingual sentence-transformers + Qdrant / FAISS.

    **Layer 3 — LLM Classifier** (``~2s``)
        Large-language-model analysis for uncertain cases.
        Supports Gemini, OpenAI, and local (Ollama/vLLM) providers.

Quick Start::

    from classifier import ClassificationOrchestrator

    orchestrator = ClassificationOrchestrator()
    result = orchestrator.classify("Patient with acute myocardial infarction...")
    print(result.category)        # "cardiology"
    print(result.confidence)      # 0.92
    print(result.method)          # ClassificationMethod.KEYWORD
"""

from classifier.keyword_router import KeywordRouter
from classifier.semantic_matcher import SemanticMatcher
from classifier.llm_classifier import LLMClassifier
from classifier.orchestrator import ClassificationOrchestrator

__all__ = [
    "KeywordRouter",
    "SemanticMatcher",
    "LLMClassifier",
    "ClassificationOrchestrator",
]
