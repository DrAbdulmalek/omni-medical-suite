# src/core/jais_proofreader.py
import logging

logger = logging.getLogger(__name__)

class JaisProofreader:
    """Jais Arabic LLM proofreader for medical OCR text."""

    def __init__(self, model_name=None, use_8bit=True):
        self.model = None
        self.tokenizer = None
        self._available = False

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            model_id = model_name or "instructlab/merlinite-7b"

            if use_8bit and torch.cuda.is_available():
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True,
                )
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                )

            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            self._available = True
            logger.info("JaisProofreader loaded successfully.")

        except Exception as e:
            logger.warning("JaisProofreader failed to load: %s", e)
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def proofread(self, text: str) -> tuple:
        """Proofread Arabic medical text and extract entities.

        Args:
            text: Arabic OCR text to proofread.

        Returns:
            Tuple of (corrected_text, entities_dict).
        """
        if not self._available or not text:
            return text, {}

        try:
            prompt = (
                "أنت مدقق لغوي متخصص في النصوص الطبية العربية.\n"
                "صحح الأخطاء في النص التالي وأعد النص المصحح فقط:\n"
                f"{text}"
            )

            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=len(text) + 50,
                temperature=0.1,
                do_sample=False,
            )
            corrected = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Remove the prompt prefix if present
            if prompt in corrected:
                corrected = corrected.replace(prompt, "").strip()

            entities = self._extract_entities(corrected)
            return corrected, entities

        except Exception as e:
            logger.error("Jais proofreading failed: %s", e)
            return text, {}

    def _extract_entities(self, text: str) -> dict:
        """Extract medical entities from corrected text.

        Returns a dict with keys: medications, dosages, dates, lab_tests.
        """
        entities = {
            "medications": [],
            "dosages": [],
            "dates": [],
            "lab_tests": [],
        }

        import re

        # Medication patterns (Arabic)
        med_patterns = [
            r'[\u0600-\u06FF]+\s+\d+\s*(ملغ|mg|جم|g|وحدة)',
            r'[\u0600-\u06FF]+(?:اب|ول|ام|ين)\s+[\u0600-\u06FF]+',
        ]
        for pat in med_patterns:
            matches = re.findall(pat, text)
            entities["medications"].extend(matches)

        # Dosage patterns
        dosage_patterns = [
            r'\d+\s*(ملغ|mg|جم|g|مل|ml|وحدة|international units)',
            r'(\d+)\s*×\s*(\d+)',
            r'(\d+)-(\d+)-(\d+)',  # dates
        ]
        for pat in dosage_patterns:
            matches = re.findall(pat, text)
            entities["dosages"].extend([str(m) for m in matches])

        return entities
