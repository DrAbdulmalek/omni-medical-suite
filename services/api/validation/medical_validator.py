"""LLM-based medical validation for OCR-extracted entities.

Provides pluggable validation for drug dosages, medical entity plausibility,
and clinical reasoning checks.  Supports both local HuggingFace models and
cloud-based LLM APIs (OpenAI, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a medical validation check."""

    is_valid: bool
    reasoning: str
    confidence: float = 1.0
    validator: str = "unknown"


class MedicalValidator:
    """Validate OCR-extracted medical entities for clinical plausibility.

    Parameters
    ----------
    use_openai:
        If ``True``, use OpenAI GPT API for validation.
    openai_key:
        OpenAI API key (required when *use_openai* is ``True``).
    model_name:
        HuggingFace model name for local validation (used when *use_openai*
        is ``False``).
    """

    def __init__(
        self,
        use_openai: bool = False,
        openai_key: Optional[str] = None,
        model_name: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
    ) -> None:
        self.use_openai = use_openai
        self._openai_key = openai_key
        self._model_name = model_name
        self._tokenizer = None
        self._model = None

        if not use_openai:
            try:
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(model_name)
                logger.info("MedicalValidator: loaded local model '%s'", model_name)
            except Exception as exc:
                logger.warning("MedicalValidator: failed to load local model: %s", exc)
        else:
            logger.info("MedicalValidator: using OpenAI API for validation")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def validate_dosage(
        self,
        drug_name: str,
        dosage: str,
        route: str = "oral",
    ) -> ValidationResult:
        """Check whether a drug dosage is clinically reasonable.

        Parameters
        ----------
        drug_name:
            Name of the drug (e.g., "Paracetamol").
        dosage:
            Dosage string (e.g., "500 mg").
        route:
            Administration route (e.g., "oral", "IV").

        Returns
        -------
        ValidationResult with ``is_valid``, ``reasoning``, and ``confidence``.
        """
        prompt = (
            f"Is the dosage '{dosage}' of drug '{drug_name}' via {route} "
            f"clinically reasonable? Answer yes/no and explain briefly."
        )

        if self.use_openai and self._openai_key:
            return await self._validate_via_openai(prompt)
        else:
            return self._validate_via_local_model(
                f"{drug_name} [SEP] {dosage} {route}"
            )

    async def validate_medical_entity(
        self,
        entity_type: str,
        entity_value: str,
        context: str = "",
    ) -> ValidationResult:
        """Check whether a medical entity is plausible in the given context.

        Examples:
        - entity_type="temperature", entity_value="42 C" -> not plausible
        - entity_type="blood_pressure", entity_value="120/80 mmHg" -> plausible
        """
        prompt = (
            f"In medical context '{context}', is the {entity_type} "
            f"'{entity_value}' plausible? Answer yes/no and explain briefly."
        )

        if self.use_openai and self._openai_key:
            return await self._validate_via_openai(prompt)
        else:
            return self._validate_via_local_model(
                f"{entity_type} [SEP] {entity_value} [SEP] {context}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _validate_via_openai(self, prompt: str) -> ValidationResult:
        """Validate using OpenAI ChatCompletion API."""
        try:
            import openai

            openai.api_key = self._openai_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            answer = response.choices[0].message.content
            is_valid = "yes" in answer.lower().split(".")[0]
            return ValidationResult(
                is_valid=is_valid,
                reasoning=answer.strip(),
                confidence=0.85,
                validator="openai_gpt35",
            )
        except Exception as exc:
            logger.error("MedicalValidator OpenAI call failed: %s", exc)
            return ValidationResult(
                is_valid=True,  # Default to valid on error (fail-open)
                reasoning=f"Validation skipped due to API error: {exc}",
                confidence=0.0,
                validator="openai_gpt35",
            )

    def _validate_via_local_model(self, text: str) -> ValidationResult:
        """Validate using a local HuggingFace sequence classification model."""
        if self._tokenizer is None or self._model is None:
            return ValidationResult(
                is_valid=True,
                reasoning="Validation skipped (no model loaded)",
                confidence=0.0,
                validator="local_model_unavailable",
            )

        try:
            import torch

            inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            outputs = self._model(**inputs)
            logits = outputs.logits
            predicted_class = torch.argmax(logits).item()
            is_valid = predicted_class == 1
            confidence = torch.softmax(logits, dim=-1)[0][predicted_class].item()

            return ValidationResult(
                is_valid=is_valid,
                reasoning=f"Local model prediction (class={predicted_class}, conf={confidence:.2f})",
                confidence=confidence,
                validator=self._model_name,
            )
        except Exception as exc:
            logger.error("MedicalValidator local model inference failed: %s", exc)
            return ValidationResult(
                is_valid=True,
                reasoning=f"Validation skipped due to model error: {exc}",
                confidence=0.0,
                validator=self._model_name,
            )
