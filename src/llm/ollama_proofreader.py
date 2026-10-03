"""
Ollama Proofreader - مصحح OCR باستخدام نموذج لغوي محلي
===========================================================

This module provides LLM-based OCR correction using a locally running
Ollama server. It sends OCR-extracted text to the model for
proofreading, with special attention to Arabic medical terminology.

هذه الوحدة توفر تصحيح OCR باستخدام نموذج لغوي محلي عبر Ollama.
ترسل النص المستخرج إلى النموذج للتدقيق مع اهتمام خاص
بالمصطلحات الطبية العربية.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "تهيئة مصحح Ollama - النموذج: {model} | Initializing Ollama proofreader - model: {model}"
_MSG_CHECK = "التحقق من خادم Ollama: {host} | Checking Ollama server: {host}"
_MSG_ONLINE = "خادم Ollama متاح | Ollama server is available"
_MSG_OFFLINE = "خادم Ollama غير متاح - سيعمل بدون تصحيح | Ollama server unavailable - will work without correction"
_MSG_PROOFING = "جارٍ تدقيق النص عبر Ollama | Proofreading text via Ollama"
_MSG_PROOFED = "اكتمل التدقيق | Proofreading complete"
_MSG_PROOF_FAIL = "فشل التدقيق: {err} | Proofreading failed: {err}"
_MSG_BATCH = "جارٍ تدقيق دفعة من {n} نصوص | Batch proofreading {n} texts"
_MSG_FALLBACK = "استخدام النص الأصلي (بدون تصحيح) | Using original text (uncorrected)"

# Medical Arabic system prompt for OCR correction
MEDICAL_ARABIC_SYSTEM_PROMPT = """أنت خبير في تصحيح النصوص الطبية العربية والإنجليزية المستخرجة بواسطة OCR.

You are an expert in proofreading Arabic and English medical text extracted by OCR.

مهمتك:
- تصحيح الأخطاء الإملائية والنحوية في النص الطبي
- تصحيح المصطلحات الطبية العربية المكتشفة بشكل خاطئ
- الحفاظ على الأرقام والجرعات كما هي
- الحفاظ على التنسيق والترتيب
- عدم إضافة معلومات غير موجودة في النص الأصلي
- تصحيح الحروف العربية المتشابهة (ت/ة، ي/ى، ا/أ/إ، د/ذ، ر/ز، س/ش، ص/ض، ط/ظ، ع/غ، ف/ق، ك/ق)

Your task:
- Fix spelling and grammar errors in the medical text
- Correct misrecognized Arabic medical terms
- Keep numbers and dosages unchanged
- Preserve formatting and order
- Do not add information not present in the original text
- Correct visually similar Arabic characters

أجب فقط بالنص المصحح بدون أي شرح إضافي.
Answer only with the corrected text without any additional explanation."""

MEDICAL_CONTEXT_NOTE = """
ملاحظة: هذا نص طبي. انتبه بشكل خاص للمصطلحات التالية:
- أسماء الأدوية (مثل: باراسيتامول، أموكسيسيلين، ميتفورمين)
- الجرعات (مثل: 500 ملغ، مرتين يومياً، بعد الأكل)
- التشخيصات (مثل: ارتفاع ضغط الدم، السكري النوع الثاني)
- التحاليل المخبرية (مثل: CBC، HbA1c،Creatinine)
Note: This is medical text. Pay special attention to drug names, dosages,
diagnoses, and lab test names.
"""


class OllamaProofreader:
    """
    LLM-based OCR proofreader using Ollama for Arabic medical text.

    مصحح OCR يعتمد على نموذج لغوي عبر Ollama للنصوص الطبية العربية.

    This class sends OCR-extracted text to a local Ollama server for
    intelligent correction. It handles:
        - Medical Arabic character confusion correction
        - Drug name and dosage verification
        - Medical terminology normalization
        - Batch processing of multiple text segments

    Features:
        - Automatic server availability check
        - Medical-context-aware prompting
        - Graceful fallback to uncorrected text
        - Batch processing support
    """

    def __init__(
        self,
        model: str = "gemma2:2b",
        host: str = "http://localhost:11434",
    ) -> None:
        """
        Initialize Ollama proofreader.

        تهيئة مصحح Ollama.

        Args:
            model: Ollama model name to use for proofreading.
                   Defaults to 'gemma2:2b' (good balance of speed/quality).
            host: Ollama server URL. Defaults to 'http://localhost:11434'.
        """
        self.model = model
        self.host = host.rstrip("/")
        self._available = False

        logger.info(_MSG_INIT.format(model=model))

        # Check if requests is available
        try:
            import requests  # type: ignore
            self._requests = requests
        except ImportError:
            logger.error(
                "مكتبة requests غير متاحة - يرجى تثبيتها "
                "| requests library not available - please install it"
            )
            return

        # Check if Ollama server is running
        self._available = self._check_ollama()

    @property
    def is_available(self) -> bool:
        """Check if Ollama proofreader is ready."""
        return self._available

    def _check_ollama(self) -> bool:
        """
        Check if the Ollama server is running and accessible.

        التحقق من أن خادم Ollama يعمل ويمكن الوصول إليه.

        Returns:
            True if Ollama is running, False otherwise.
        """
        logger.info(_MSG_CHECK.format(host=self.host))

        try:
            response = self._requests.get(
                f"{self.host}/api/tags",
                timeout=5,
            )

            if response.status_code == 200:
                logger.info(_MSG_ONLINE)

                # Optionally check if the model is available
                models = response.json().get("models", [])
                model_names = [
                    m.get("name", "") for m in models
                ]
                if self.model not in model_names:
                    logger.warning(
                        f"النموذج '{self.model}' غير مثبت. "
                        f"النماذج المتاحة: {model_names[:5]} "
                        f"| Model '{self.model}' not installed. "
                        f"Available: {model_names[:5]}"
                    )

                return True

        except self._requests.exceptions.ConnectionError:
            logger.warning(_MSG_OFFLINE)
        except self._requests.exceptions.Timeout:
            logger.warning(
                "انتهت مهلة الاتصال بـ Ollama | Ollama connection timed out"
            )
        except Exception as e:
            logger.warning(
                f"خطأ في فحص Ollama: {e} | Ollama check error: {e}"
            )

        logger.warning(_MSG_OFFLINE)
        return False

    def proofread(
        self,
        ocr_text: str,
        medical_context: bool = True,
    ) -> dict[str, Any]:
        """
        Proofread OCR-extracted text using Ollama.

        تدقيق النص المستخرج من OCR باستخدام Ollama.

        Args:
            ocr_text: The raw text extracted by OCR.
            medical_context: Whether to include medical context in the
                            prompt. Defaults to True.

        Returns:
            Dictionary containing:
                - corrected_text (str): The proofread text
                - original_text (str): The original OCR text
                - model (str): Model used for correction
                - corrected (bool): Whether correction was applied
                - engine (str): 'ollama'
        """
        if not ocr_text or not ocr_text.strip():
            return {
                "corrected_text": "",
                "original_text": ocr_text,
                "model": self.model,
                "corrected": False,
                "engine": "ollama",
            }

        if not self._available:
            logger.warning(_MSG_FALLBACK)
            return {
                "corrected_text": ocr_text,
                "original_text": ocr_text,
                "model": None,
                "corrected": False,
                "engine": "ollama",
                "fallback_reason": "Ollama not available",
            }

        logger.info(_MSG_PROOFING)

        try:
            # Build the prompt
            system_prompt = MEDICAL_ARABIC_SYSTEM_PROMPT
            if medical_context:
                system_prompt += MEDICAL_CONTEXT_NOTE

            # Call Ollama API
            response = self._requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": ocr_text,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for conservative corrections
                        "top_p": 0.9,
                        "num_predict": max(len(ocr_text) * 2, 2048),
                    },
                },
                timeout=120,  # Long timeout for medical text
            )

            if response.status_code == 200:
                result = response.json()
                corrected = result.get("response", "").strip()

                if corrected:
                    logger.info(_MSG_PROOFED)
                    return {
                        "corrected_text": corrected,
                        "original_text": ocr_text,
                        "model": self.model,
                        "corrected": True,
                        "engine": "ollama",
                        "eval_count": result.get("eval_count", 0),
                        "eval_duration_ms": result.get("eval_duration", 0) // 1_000_000,
                    }
                else:
                    logger.warning("النص المصحح فارغ | Corrected text is empty")

            else:
                logger.error(
                    f"خطأ HTTP من Ollama: {response.status_code} "
                    f"| HTTP error from Ollama: {response.status_code}"
                )

        except self._requests.exceptions.Timeout:
            logger.error("انتهت مهلة تصحيح Ollama | Ollama proofreading timed out")
        except self._requests.exceptions.ConnectionError:
            logger.error("فقد الاتصال بـ Ollama | Lost connection to Ollama")
        except Exception as e:
            logger.error(_MSG_PROOF_FAIL.format(err=e), exc_info=True)

        # Fallback: return original text
        logger.warning(_MSG_FALLBACK)
        return {
            "corrected_text": ocr_text,
            "original_text": ocr_text,
            "model": self.model,
            "corrected": False,
            "engine": "ollama",
            "fallback_reason": "Error during proofreading",
        }

    def batch_proofread(
        self,
        texts: list[str],
        medical_context: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Proofread multiple texts in sequence.

        تدقيق عدة نصوص بشكل متتالي.

        Each text is sent to Ollama independently. For large batches,
        consider implementing async processing.

        Args:
            texts: List of OCR-extracted text strings.
            medical_context: Whether to use medical context prompting.

        Returns:
            List of proofreading result dictionaries, one per input text.
        """
        logger.info(_MSG_BATCH.format(n=len(texts)))

        results: list[dict[str, Any]] = []

        for idx, text in enumerate(texts):
            logger.debug(
                f"تدقيق النص {idx + 1}/{len(texts)} "
                f"| Proofreading text {idx + 1}/{len(texts)}"
            )

            result = self.proofread(text, medical_context=medical_context)
            result["batch_index"] = idx
            results.append(result)

        corrected_count = sum(1 for r in results if r.get("corrected", False))
        logger.info(
            f"اكتمل الدفعي: {corrected_count}/{len(texts)} تم تصحيحها "
            f"| Batch complete: {corrected_count}/{len(texts)} corrected"
        )

        return results
