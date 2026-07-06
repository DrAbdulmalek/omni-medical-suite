"""
Jais Arabic LLM spell checker.

Wraps a large language model (Jais-family or lightweight fallback) to provide
**contextual** spell correction for Arabic medical OCR output.  When a GPU is
available the model runs with 8-bit quantisation to keep VRAM usage manageable;
otherwise it falls back gracefully, returning the input text unchanged with a
warning.

The checker uses prompt engineering to instruct the model to correct OCR errors
while preserving medical terminology meaning.
"""

from __future__ import annotations

import logging
import warnings
from typing import List, Optional, Tuple

import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

# Preferred Jais model (requires ~24 GB VRAM in 8-bit mode)
JAIS_MODEL_ID = "jais-family/jais-13b"

# Lightweight fallback model (fits in ~8 GB VRAM in 8-bit mode)
FALLBACK_MODEL_ID = "instructlab/merlinite-7b"


class JaisSpellChecker:
    """LLM-based Arabic spell checker backed by Jais or a fallback model.

    Parameters
    ----------
    model_name : str | None
        Hugging Face model identifier.  If *None*, the class attempts to load
        ``jais-family/jais-13b`` first, then falls back to
        ``instructlab/merlinite-7b``.
    device : str | None
        Torch device string (e.g. ``"cuda"``, ``"cpu"``, ``"auto"``).
        Defaults to auto-detection.
    use_8bit : bool
        Whether to load the model in 8-bit quantised mode (requires
        ``bitsandbytes``).  Recommended when GPU memory is limited.
    temperature : float
        Sampling temperature for text generation.  Lower values produce more
        deterministic output.
    max_tokens : int
        Maximum number of new tokens to generate per correction request.
    batch_size : int
        Number of texts to process in a single forward pass during batch
        correction.

    Notes
    -----
    If neither ``transformers`` nor a compatible model can be loaded, the
    checker enters a *degraded* mode where :meth:`correct` returns the input
    text unchanged and logs a warning.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        use_8bit: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 512,
        batch_size: int = 4,
    ) -> None:
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._batch_size = batch_size
        self._pipeline = None
        self._model_available = False
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self._load_model(model_name=model_name, use_8bit=use_8bit)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(
        self,
        model_name: Optional[str] = None,
        use_8bit: bool = True,
    ) -> None:
        """Attempt to load the model pipeline."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            # Determine which model to attempt
            candidates: List[str] = []
            if model_name:
                candidates.append(model_name)
            candidates.extend([JAIS_MODEL_ID, FALLBACK_MODEL_ID])

            loaded_model_id: Optional[str] = None
            model = None
            tokenizer = None

            for candidate_id in candidates:
                try:
                    load_kwargs: dict = {
                        "torch_dtype": torch.float16 if self._device != "cpu" else torch.float32,
                    }
                    if use_8bit and self._device != "cpu":
                        load_kwargs["load_in_8bit"] = True

                    logger.info("Attempting to load model '%s' ...", candidate_id)
                    tokenizer = AutoTokenizer.from_pretrained(candidate_id, trust_remote_code=True)
                    model = AutoModelForCausalLM.from_pretrained(
                        candidate_id,
                        device_map="auto" if self._device != "cpu" else None,
                        trust_remote_code=True,
                        **load_kwargs,
                    )
                    loaded_model_id = candidate_id
                    logger.info("Successfully loaded model '%s'.", candidate_id)
                    break
                except Exception as exc:
                    logger.debug(
                        "Failed to load model '%s': %s", candidate_id, exc
                    )
                    continue

            if model is None or tokenizer is None:
                raise RuntimeError("No suitable model could be loaded.")

            # Determine pipeline type based on model config
            pipeline_task = "text-generation"

            self._pipeline = pipeline(
                pipeline_task,
                model=model,
                tokenizer=tokenizer,
                device_map="auto" if self._device != "cpu" else None,
            )
            self._model_available = True
            self._loaded_model_id = loaded_model_id
            logger.info("JaisSpellChecker initialised with '%s'.", loaded_model_id)

        except ImportError:
            warnings.warn(
                "The 'transformers' package is not installed. "
                "JaisSpellChecker will operate in degraded mode (no correction). "
                "Install with: pip install transformers torch",
                stacklevel=2,
            )
            self._model_available = False

        except Exception as exc:
            warnings.warn(
                f"Could not load any LLM for spell checking: {exc}. "
                "JaisSpellChecker will operate in degraded mode (no correction).",
                stacklevel=2,
            )
            self._model_available = False

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_correction_prompt(text: str) -> str:
        """Build a prompt that instructs the model to correct OCR errors.

        The prompt is kept in English but specifies Arabic medical text to
        maintain consistent instruction following across model families.
        """
        prompt = (
            "You are an expert in Arabic medical document OCR correction. "
            "Correct the Arabic medical OCR errors in the following text. "
            "Apply these corrections:\n"
            "1. Fix character confusion caused by OCR (e.g., ة ↔ ه, ى ↔ ي, "
            "dot placement errors in ب/ت/ث/ن/ي, shape confusion in ح/خ/ج).\n"
            "2. Preserve all medical terminology, drug names, and dosages.\n"
            "3. Do NOT translate any Arabic text — only correct spelling errors.\n"
            "4. Return ONLY the corrected Arabic text with no explanations.\n\n"
            f"Text to correct:\n{text}\n\n"
            "Corrected text:"
        )
        return prompt

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def correct(self, text: str) -> str:
        """Correct OCR errors in *text* using the LLM.

        Parameters
        ----------
        text : str
            Raw Arabic text from OCR.

        Returns
        -------
        str
            Corrected text, or the original text if the model is unavailable.
        """
        if not text or not text.strip():
            return text

        if not self._model_available:
            logger.warning(
                "JaisSpellChecker: model not available — returning text unchanged."
            )
            return text

        try:
            prompt = self._build_correction_prompt(text)
            output = self._pipeline(
                prompt,
                max_new_tokens=self._max_tokens,
                temperature=self._temperature,
                do_sample=self._temperature > 0,
                num_return_sequences=1,
                truncation=True,
            )

            # Extract generated text after the prompt
            generated = output[0]["generated_text"]
            corrected = self._extract_correction(generated, prompt)
            return corrected if corrected else text

        except Exception as exc:
            logger.error("JaisSpellChecker correction failed: %s", exc)
            return text

    def correct_batch(self, texts: List[str]) -> List[str]:
        """Correct a batch of texts.

        Parameters
        ----------
        texts : list[str]
            List of raw Arabic OCR texts.

        Returns
        -------
        list[str]
            List of corrected texts (or originals on failure).
        """
        if not self._model_available:
            logger.warning(
                "JaisSpellChecker: model not available — returning texts unchanged."
            )
            return list(texts)

        results: List[str] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            batch_results = [self.correct(t) for t in batch]
            results.extend(batch_results)
        return results

    def is_available(self) -> bool:
        """Return ``True`` if the model was loaded successfully."""
        return self._model_available

    @property
    def loaded_model_id(self) -> Optional[str]:
        """Identifier of the loaded model, or ``None`` if unavailable."""
        return getattr(self, "_loaded_model_id", None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_correction(generated: str, prompt: str) -> Optional[str]:
        """Extract the corrected text from the model's full output.

        Attempts several heuristics to locate the correction after the
        prompt marker.
        """
        # Strategy 1: everything after "Corrected text:" label
        marker = "Corrected text:"
        if marker in generated:
            correction = generated.split(marker, 1)[1].strip()
            # Strip any trailing explanation
            for stop in ["\n\n", "Explanation:", "Note:"]:
                if stop in correction:
                    correction = correction.split(stop, 1)[0].strip()
            if correction:
                return correction

        # Strategy 2: everything after the last newline following the prompt
        if generated.startswith(prompt):
            remainder = generated[len(prompt) :].strip()
            if remainder:
                return remainder.split("\n")[0].strip()

        # Strategy 3: return the whole generated text (last resort)
        cleaned = generated.strip()
        if cleaned and cleaned != prompt.strip():
            return cleaned

        return None