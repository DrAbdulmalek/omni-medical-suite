"""LLM provider routing with automatic fallback.

Routes natural-language tasks to the best available LLM provider (Mistral,
Gemini, or a local model).  When the primary provider fails, the router
transparently falls back to the next available option.

Usage
-----

>>> from app.core.config import settings
>>> from app.ai.llm_router import LLMRouter
>>> router = LLMRouter(settings)
>>> result = await router.route("Summarise this report.", "summarize")
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Any

import httpx

__all__ = ["LLMProvider", "LLMRouter", "LLMError"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class LLMError(Exception):
    """Raised when all LLM providers fail to produce a result."""


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------
class LLMProvider(enum.StrEnum):
    """Supported LLM backends."""

    MISTRAL = "mistral"
    GEMINI = "gemini"
    LOCAL = "local"


# ---------------------------------------------------------------------------
# Task metadata – used to build provider-specific prompts
# ---------------------------------------------------------------------------
_TASK_SYSTEM_PROMPTS: dict[str, str] = {
    "summarize": (
        "You are a medical document summariser.  Produce a concise, accurate "
        "summary of the provided text.  Preserve all clinically significant "
        "details including diagnoses, medications, and measurements."
    ),
    "translate": (
        "You are a professional medical translator.  Translate the provided "
        "text accurately, preserving medical terminology and clinical intent."
    ),
    "extract_entities": (
        "You are a medical named-entity recognition system.  Extract and "
        "return a structured list of entities (diagnoses, medications, "
        "procedures, body parts, lab values) from the provided text."
    ),
    "medical_analysis": (
        "You are an AI medical document analyst.  Analyse the provided text "
        "and return a structured report covering: key findings, potential "
        "abnormalities, recommended follow-up actions, and confidence scores."
    ),
    "general": (
        "You are a helpful assistant specialised in medical document processing.  "
        "Answer the user's query accurately and concisely."
    ),
}

_VALID_TASKS = set(_TASK_SYSTEM_PROMPTS)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
class LLMRouter:
    """Intelligent LLM request router with fallback support.

    Parameters
    ----------
    config:
        Application settings (``app.core.config.Settings``).  The router
        inspects ``MISTRAL_API_KEY`` and ``GEMINI_API_KEY`` to determine
        which providers are available.
    timeout:
        HTTP request timeout in seconds for each provider call.
    """

    def __init__(self, config: Any, timeout: float = 60.0) -> None:
        self._mistral_key: str | None = getattr(config, "MISTRAL_API_KEY", None)
        self._gemini_key: str | None = getattr(config, "GEMINI_API_KEY", None)
        self._timeout = timeout

        # Build the ordered list of available providers
        self._providers: list[LLMProvider] = []
        if self._mistral_key:
            self._providers.append(LLMProvider.MISTRAL)
        if self._gemini_key:
            self._providers.append(LLMProvider.GEMINI)
        if not self._providers:
            logger.warning("No LLM API keys configured – all requests will fail.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def route(self, text: str, task: str) -> str:
        """Send *text* to the best available provider for *task*.

        Selects the first available provider based on provider priority and
        task type, then returns its response.

        Raises
        ------
        LLMError
            If no providers are configured or the request fails.
        """
        if not self._providers:
            raise LLMError("No LLM providers configured. Set MISTRAL_API_KEY or GEMINI_API_KEY.")

        provider = self._select_provider(task)
        try:
            return await self._dispatch(provider, text, task)
        except Exception as exc:
            raise LLMError(
                f"Provider '{provider}' failed for task '{task}': {exc}"
            ) from exc

    async def route_with_fallback(self, text: str, task: str) -> str:
        """Try all configured providers in order until one succeeds.

        Raises
        ------
        LLMError
            If every provider fails.
        """
        if not self._providers:
            raise LLMError("No LLM providers configured. Set MISTRAL_API_KEY or GEMINI_API_KEY.")

        errors: list[str] = []
        for provider in self._providers:
            try:
                return await self._dispatch(provider, text, task)
            except Exception as exc:
                msg = f"{provider}: {exc}"
                errors.append(msg)
                logger.warning("LLM fallback – %s failed: %s", provider, exc)

        raise LLMError(
            f"All LLM providers failed for task '{task}': {'; '.join(errors)}"
        )

    async def health_check(self) -> dict[str, Any]:
        """Run lightweight health checks against each configured provider.

        Returns a mapping of ``{provider_name: {"status": bool, "latency_ms": float}}``.
        """
        results: dict[str, Any] = {}
        for provider in self._providers:
            try:
                start = time.monotonic()
                await self._dispatch(provider, "ping", "general")
                latency = (time.monotonic() - start) * 1000
                results[provider] = {"status": True, "latency_ms": round(latency, 1)}
            except Exception as exc:
                results[provider] = {"status": False, "error": str(exc)}
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _select_provider(self, task: str) -> LLMProvider:
        """Pick the best provider for *task*.

        Currently returns the first configured provider.  This can be
        extended with task-specific routing logic.
        """
        if not self._providers:
            raise LLMError("No providers available")
        return self._providers[0]

    async def _dispatch(self, provider: LLMProvider, text: str, task: str) -> str:
        """Route the request to the correct provider method."""
        match provider:
            case LLMProvider.MISTRAL:
                return await self._call_mistral(text, task)
            case LLMProvider.GEMINI:
                return await self._call_gemini(text, task)
            case _:
                raise LLMError(f"Unsupported provider: {provider}")

    # ── Mistral ──────────────────────────────────────────────────────
    async def _call_mistral(self, text: str, task: str) -> str:
        """Call the Mistral AI chat-completion API.

        API reference: https://docs.mistral.ai/api/#tag/chat
        """
        if not self._mistral_key:
            raise LLMError("Mistral API key not configured.")

        system_prompt = _TASK_SYSTEM_PROMPTS.get(task, _TASK_SYSTEM_PROMPTS["general"])

        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._mistral_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "mistral-medium-latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2 if task in ("extract_entities", "medical_analysis") else 0.5,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    # ── Gemini ───────────────────────────────────────────────────────
    async def _call_gemini(self, text: str, task: str) -> str:
        """Call the Google Gemini generate-content API.

        API reference: https://ai.google.dev/docs/api_reference
        """
        if not self._gemini_key:
            raise LLMError("Gemini API key not configured.")

        system_prompt = _TASK_SYSTEM_PROMPTS.get(task, _TASK_SYSTEM_PROMPTS["general"])

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={self._gemini_key}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"System instructions: {system_prompt}\n\n{text}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2 if task in ("extract_entities", "medical_analysis") else 0.5,
                "maxOutputTokens": 2048,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return (
                data["candidates"][0]["content"]["parts"][0]["text"].strip()
            )
