# src/llm/proofreader.py
"""
Post-OCR correction using LLM (Jais) for Arabic medical text.

Combines:
  1. Contextual spelling correction
  2. Medical entity extraction (drug, disease, dosage, symptom)
  3. Structured output (corrected text + entity dict)

Requirements:
    pip install transformers accelerate bitsandbytes

GPU: 24GB+ recommended (uses 8-bit quantization).

Usage:
    proofreader = MedicalProofreader()
    result = proofreader.proofread("المريض ياخذ اموكسيسلين 500مغ لالتهاب اللوزتين")
    print(result["corrected"])
    # "المريض يأخذ أموكسيسيلين 500 ملغ لالتهاب اللوزتين"
    print(result["entities"])
    # {"drug": ["أموكسيسيلين"], "disease": ["التهاب اللوزتين"], "dosage": ["500 ملغ"]}
"""
import logging
import re
from typing import Dict, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


class MedicalProofreader:
    """
    Arabic medical text proofreader using Jais LLM.

    Performs contextual correction and entity extraction in a single pass.
    """

    def __init__(
        self,
        model_name: str = "core42/jais-13b-chat",
        load_in_8bit: bool = True,
    ):
        logger.info(f"Loading Medical Proofreader: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            load_in_8bit=load_in_8bit,
            trust_remote_code=True,
        )
        self.model.eval()

    def proofread(self, ocr_text: str) -> Dict:
        """
        Proofread OCR text: correct errors + extract medical entities.

        Args:
            ocr_text: Raw Arabic text from OCR output.

        Returns:
            Dict with keys:
                - original: the input text
                - corrected: proofread text
                - entities: dict with drug/disease/dosage/symptom lists
                - full_response: raw LLM response
        """
        prompt = f"""أنت مدقق طبي متخصص. قم بالتالي على النص العربي الطبي:

نص OCR: {ocr_text}

1. صحح الأخطاء الإملائية والنحوية مع الحفاظ على المعنى الطبي.
2. استخرج الكيانات الطبية (دواء، مرض، جرعة، عرض).
3. أعد كتابة النص المصحح فقط بدون إضافة معلومات.

أعد النتيجة بالصيغة التالية:

**النص المصحح:**
[النص بعد التصحيح]

**الكيانات:**
- دواء: [قائمة أو -]
- مرض: [قائمة أو -]
- عرض: [قائمة أو -]
- جرعة: [قائمة أو -]

النص الأصلي: {ocr_text}"""

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.3,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Parse structured output
        corrected = self._extract_section(response, "**النص المصحح:**", "**الكيانات:**")
        entities = self._parse_entities(response)

        return {
            "original": ocr_text,
            "corrected": corrected,
            "entities": entities,
            "full_response": response,
        }

    def _extract_section(self, text: str, start: str, end: str) -> str:
        """Extract text between two markdown-style section headers."""
        try:
            section = text.split(start)[1].split(end)[0].strip()
            return section if section else text
        except (IndexError, AttributeError):
            return text

    def _parse_entities(self, text: str) -> Dict[str, list]:
        """Parse entity lists from LLM response."""
        entities: Dict[str, list] = {
            "drug": [],
            "disease": [],
            "dosage": [],
            "symptom": [],
        }

        key_map = {
            "دواء": "drug",
            "مرض": "disease",
            "جرعة": "dosage",
            "عرض": "symptom",
        }

        for line in text.split('\n'):
            line = line.strip().lstrip('-').strip()
            if not line or ':' not in line:
                continue

            for arabic_key, english_key in key_map.items():
                if arabic_key in line:
                    after_colon = line.split(':', 1)[1].strip()
                    items = [
                        item.strip()
                        for item in after_colon.split(',')
                        if item.strip() and item.strip() != '-'
                    ]
                    entities[english_key].extend(items)
                    break

        # Clean
        return {k: [v for v in vs if v] for k, vs in entities.items()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    proofreader = MedicalProofreader()
    result = proofreader.proofread("المريض ياخذ اموكسيسلين 500مغ لالتهاب اللوزتين")
    print(f"Corrected: {result['corrected']}")
    print(f"Entities:  {result['entities']}")