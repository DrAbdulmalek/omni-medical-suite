"""
AI Fuel Engine — Root Package

A production-ready pipeline for ingesting, segmenting, classifying,
deduplicating, and exporting Arabic/English healthcare text corpora
for AI model training (RAG, fine-tuning, embeddings).

Quick Start::

    from ai_fuel_engine import AIFuelEngine

    engine = AIFuelEngine()
    result = engine.process_text("Your healthcare text here...")
    print(result.stats.total_chunks)
"""

from engine import AIFuelEngine

__version__ = "0.1.0"
__all__ = ["AIFuelEngine"]
