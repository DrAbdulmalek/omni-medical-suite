"""
AI Fuel Engine - LLM Classifier Module

LLM-based classification — Layer 3 of the hierarchical classifier.
Used for uncertain cases where keyword and semantic methods have
low confidence.  Supports multiple LLM providers (Gemini, OpenAI,
local models) via a unified interface.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMClassifier:
    """LLM-based classification — Layer 3, for uncertain cases.

    Constructs a classification prompt with the full category list and
    sends it to an LLM for analysis.  The LLM is expected to return a
    JSON response containing the predicted category, confidence score,
    and reasoning.

    Supported providers:
        - ``gemini`` (default) — Google Gemini via ``google-generativeai``.
        - ``openai`` — OpenAI GPT models.
        - ``local`` — Any OpenAI-compatible local endpoint (e.g. Ollama,
          vLLM).

    Args:
        provider: LLM provider identifier (``"gemini"``, ``"openai"``,
            or ``"local"``).
        api_key: API key for the chosen provider.  When ``None`` the key
            is read from the ``GEMINI_API_KEY``, ``OPENAI_API_KEY``, or
            ``LOCAL_LLM_URL`` environment variable as appropriate.
        model_name: Specific model to use.  Provider-dependent defaults
            apply when ``None``.
        taxonomy_path: Path to the medical taxonomy JSON for building
            the category list in the prompt.
        temperature: Sampling temperature (default ``0.1`` for deterministic
            classification).
        max_tokens: Maximum tokens in the LLM response.
    """

    _DEFAULT_TAXONOMY_PATH = os.path.join(
        os.path.dirname(__file__), "medical_taxonomy.json"
    )

    # Provider → default model mapping
    _DEFAULT_MODELS: Dict[str, str] = {
        "gemini": "gemini-2.0-flash",
        "openai": "gpt-4o-mini",
        "local": "llama3",
    }

    # Provider → env var for API key
    _API_KEY_ENV: Dict[str, str] = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "local": "LOCAL_LLM_URL",
    }

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        taxonomy_path: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> None:
        self.provider: str = provider.lower().strip()
        self.model_name: str = model_name or self._DEFAULT_MODELS.get(
            self.provider, "unknown"
        )
        self.taxonomy_path: str = taxonomy_path or self._DEFAULT_TAXONOMY_PATH
        self.temperature: float = temperature
        self.max_tokens: int = max_tokens

        # Resolve API key
        env_var = self._API_KEY_ENV.get(self.provider)
        self.api_key: Optional[str] = api_key or (
            os.environ.get(env_var) if env_var else None
        )

        # Lazy-loaded client
        self._client: Any = None
        self._categories: List[Dict] = []

        # Stats
        self._call_count: int = 0
        self._error_count: int = 0

        logger.info(
            "LLMClassifier initialised: provider=%s model=%s api_key_set=%s",
            self.provider,
            self.model_name,
            self.api_key is not None,
        )

    # ── Lazy client initialisation ────────────────────────────────────

    def _ensure_client(self) -> None:
        """Initialise the LLM client on first use."""
        if self._client is not None:
            return

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "local":
            self._init_local()
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.provider!r}. "
                f"Supported: gemini, openai, local"
            )

    def _init_gemini(self) -> None:
        """Initialise Google Gemini client."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError(
                "google-generativeai is required for Gemini provider. "
                "Install with: pip install google-generativeai"
            )

        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        genai.configure(api_key=self.api_key)
        self._client = genai.GenerativeModel(self.model_name)
        logger.info("Gemini client initialised with model %s", self.model_name)

    def _init_openai(self) -> None:
        """Initialise OpenAI client."""
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai is required for OpenAI provider. "
                "Install with: pip install openai"
            )

        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._client = OpenAI(api_key=self.api_key)
        logger.info("OpenAI client initialised with model %s", self.model_name)

    def _init_local(self) -> None:
        """Initialise local LLM client (OpenAI-compatible endpoint)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai is required for local provider. "
                "Install with: pip install openai"
            )

        base_url = self.api_key  # For local, api_key holds the URL
        if not base_url:
            raise ValueError(
                "Local LLM URL required. Set LOCAL_LLM_URL environment variable "
                "or pass api_key parameter with the base URL."
            )

        self._client = OpenAI(
            base_url=base_url,
            api_key="local",  # placeholder key for local models
        )
        logger.info("Local LLM client initialised at %s", base_url)

    # ── Category loading ──────────────────────────────────────────────

    def _load_categories(self) -> List[Dict]:
        """Load category list from taxonomy JSON."""
        if self._categories:
            return self._categories

        if not os.path.exists(self.taxonomy_path):
            logger.warning(
                "Taxonomy file not found at %s — using empty category list",
                self.taxonomy_path,
            )
            return []

        with open(self.taxonomy_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._categories = data.get("categories", [])
        return self._categories

    # ── Classification ────────────────────────────────────────────────

    def classify(self, text: str, chunk_id: str = "unknown") -> "ClassificationResult":
        """Classify text using LLM analysis.

        Always returns a result (even with low confidence) since this is
        the last layer in the hierarchical classifier.

        Args:
            text: The text to classify.
            chunk_id: Identifier for the text chunk.

        Returns:
            A :class:`ClassificationResult` with ``method=LLM``.
        """
        from core.schemas import ClassificationMethod, ClassificationResult

        start = time.perf_counter()

        categories = self._load_categories()
        if not categories:
            # Fallback to "unknown" if no taxonomy available
            return ClassificationResult(
                chunk_id=chunk_id,
                category="unknown",
                subcategory=None,
                confidence=0.0,
                method=ClassificationMethod.LLM,
                alternatives=[],
                processing_time_ms=0.0,
            )

        try:
            prompt = self._build_prompt(text, categories)
            response_text = self._call_llm(prompt)
            result = self._parse_response(response_text, chunk_id)

        except Exception as exc:
            self._error_count += 1
            logger.error(
                "LLM classification failed for chunk %s: %s", chunk_id, exc
            )
            # Return low-confidence fallback
            result = ClassificationResult(
                chunk_id=chunk_id,
                category="unknown",
                subcategory=None,
                confidence=0.1,
                method=ClassificationMethod.LLM,
                alternatives=[],
                processing_time_ms=(time.perf_counter() - start) * 1000.0,
            )

        # Override processing time with actual measured time
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result.processing_time_ms = round(elapsed_ms, 2)

        logger.info(
            "LLM classification: chunk=%s category=%s confidence=%.3f (%.1fms)",
            chunk_id,
            result.category,
            result.confidence,
            elapsed_ms,
        )
        return result

    # ── Prompt construction ───────────────────────────────────────────

    def _build_prompt(self, text: str, categories: List[Dict]) -> str:
        """Build a classification prompt with the category list.

        Constructs a structured prompt that instructs the LLM to classify
        the text and return a JSON response.

        Args:
            text: The text to classify.
            categories: List of category dictionaries from the taxonomy.

        Returns:
            The complete prompt string.
        """
        # Build category list
        cat_lines: List[str] = []
        for cat in categories:
            cat_id = cat["id"]
            name_en = cat.get("name_en", cat_id)
            name_ar = cat.get("name_ar", "")
            desc_en = cat.get("description_en", "")
            line = f'- "{cat_id}": {name_en}'
            if name_ar:
                line += f" ({name_ar})"
            if desc_en:
                line += f" — {desc_en}"
            cat_lines.append(line)

        category_list = "\n".join(cat_lines)

        prompt = f"""You are an expert medical text classifier specializing in Arabic and English healthcare documents.

## Task
Classify the following text into exactly ONE category from the provided list.

## Categories
{category_list}

## Text to Classify
---
{text[:3000]}
---

## Instructions
1. Read the text carefully, noting medical terminology in both English and Arabic.
2. Choose the SINGLE most appropriate category.
3. Assign a confidence score between 0.0 and 1.0.
4. Provide brief reasoning.

## Response Format (JSON only, no markdown)
{{
    "category": "<category_id>",
    "subcategory": "<English name or Arabic name>",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<brief explanation>"
}}

Respond ONLY with the JSON object. No additional text."""

        return prompt

    # ── LLM invocation ──────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM and return the raw text response.

        Args:
            prompt: The classification prompt.

        Returns:
            Raw text response from the LLM.

        Raises:
            RuntimeError: If the client is not initialised.
            Exception: If the LLM call fails.
        """
        self._ensure_client()
        self._call_count += 1

        if self.provider == "gemini":
            response = self._client.generate_content(
                prompt,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                },
            )
            return response.text

        elif self.provider in ("openai", "local"):
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical text classification expert. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""

        raise RuntimeError(f"Unsupported provider: {self.provider}")

    # ── Response parsing ─────────────────────────────────────────────

    def _parse_response(
        self, response_text: str, chunk_id: str
    ) -> "ClassificationResult":
        """Parse the LLM's JSON response into a ClassificationResult.

        Handles common formatting issues such as markdown code fences
        and partial JSON gracefully.

        Args:
            response_text: Raw text from the LLM.
            chunk_id: ID of the classified chunk.

        Returns:
            A :class:`ClassificationResult`.
        """
        from core.schemas import ClassificationMethod, ClassificationResult

        # Clean response — strip markdown code fences
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Attempt JSON parsing
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from surrounding text
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    data = json.loads(cleaned[json_start:json_end])
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse LLM response as JSON: %s",
                        cleaned[:200],
                    )
                    return self._fallback_result(chunk_id)
            else:
                return self._fallback_result(chunk_id)

        # Extract fields with defaults
        category = str(data.get("category", "unknown")).strip()
        subcategory = data.get("subcategory")
        if subcategory is not None:
            subcategory = str(subcategory).strip() or None

        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        return ClassificationResult(
            chunk_id=chunk_id,
            category=category if category else "unknown",
            subcategory=subcategory,
            confidence=round(confidence, 4),
            method=ClassificationMethod.LLM,
            alternatives=[],
            processing_time_ms=0.0,  # will be set by caller
        )

    def _fallback_result(self, chunk_id: str) -> "ClassificationResult":
        """Create a low-confidence fallback result when parsing fails."""
        from core.schemas import ClassificationMethod, ClassificationResult

        return ClassificationResult(
            chunk_id=chunk_id,
            category="unknown",
            subcategory=None,
            confidence=0.2,  # Low but not zero — indicates LLM was used
            method=ClassificationMethod.LLM,
            alternatives=[],
            processing_time_ms=0.0,  # will be set by caller
        )

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return usage statistics for the LLM classifier.

        Returns:
            Dictionary with call_count and error_count.
        """
        return {
            "provider": self.provider,
            "model": self.model_name,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "error_rate": (
                self._error_count / self._call_count
                if self._call_count > 0
                else 0.0
            ),
        }
