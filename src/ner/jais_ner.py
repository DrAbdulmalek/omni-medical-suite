# src/ner/jais_ner.py
"""
Zero-shot Medical NER using Jais (G42/Cerebras) — strongest open Arabic LLM.

Extracts medical entities (drugs, diseases, symptoms, dosages, dates)
from Arabic medical text using prompt-based generation.

Requirements:
    pip install transformers accelerate bitsandbytes

GPU: 24GB+ recommended (uses 8-bit quantization).
For limited resources, consider aubmindlab/bert-base-arabertv02 instead.

Usage:
    ner = JaisNER()
    entities = ner.extract_entities("وصفة أموكسيسيلين 500 ملغ لالتهاب اللوزتين")
    print(entities)
    # {"drug": ["أموكسيسيلين"], "disease": ["التهاب اللوزتين"], "dosage": ["500 ملغ"]}

    tokens, tags = ner.annotate_tokens("المريض يأخذ أموكسيسيلين 500 ملغ")
"""
import logging
import re

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)


class JaisNER:
    """Zero-shot medical NER using Jais-13B-Chat."""

    def __init__(
        self,
        model_name: str = "core42/jais-13b-chat",
        load_in_8bit: bool = True,
    ):
        logger.info(f"Loading Jais NER: {model_name} (8bit={load_in_8bit})")
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            load_in_8bit=load_in_8bit,
            trust_remote_code=True,
        )
        self.model.eval()

    def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """
        Extract medical entities from Arabic text using zero-shot prompting.

        Args:
            text: Arabic medical text.
            entity_types: Entity types to extract. Defaults to medical set.

        Returns:
            Dict with keys: drug, disease, symptom, dosage, date.
        """
        if entity_types is None:
            entity_types = ["دواء", "مرض", "عرض", "جرعة", "تاريخ"]

        prompt = f"""أنت مساعد طبي متخصص في استخراج الكيانات من النصوص العربية الطبية.

نص: {text}

أخرج الكيانات بالصيغة التالية فقط:
- دواء: [قائمة]
- مرض: [قائمة]
- عرض: [قائمة]
- جرعة: [قائمة]
- تاريخ: [قائمة]

الإجابة:"""

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> dict[str, list[str]]:
        """Parse Jais response into structured entity dict."""
        result: dict[str, list[str]] = {
            "drug": [],
            "disease": [],
            "symptom": [],
            "dosage": [],
            "date": [],
        }

        type_map = {
            "دواء": "drug",
            "مرض": "disease",
            "عرض": "symptom",
            "جرعة": "dosage",
            "تاريخ": "date",
        }

        lines = response.split('\n')
        current_key: str = None

        for line in lines:
            line = line.strip().lstrip('-').strip()
            if not line:
                continue

            # Detect entity type header
            matched = False
            for arabic_key, english_key in type_map.items():
                if arabic_key in line and (':' in line or '：' in line):
                    current_key = english_key
                    # Check if items are on the same line
                    if ':' in line:
                        after_colon = line.split(':', 1)[1].strip()
                        if after_colon and after_colon != '-':
                            items = [x.strip() for x in after_colon.split(',') if x.strip()]
                            result[current_key].extend(items)
                    matched = True
                    break

            # If we're in a section and line has content, add it
            if not matched and current_key and ':' not in line:
                items = [x.strip() for x in line.split(',') if x.strip() and x.strip() != '-']
                result[current_key].extend(items)

        # Clean empty strings
        return {k: [v for v in vs if v] for k, vs in result.items()}

    def annotate_tokens(self, text: str) -> tuple[list[str], list[int]]:
        """
        Convert extract_entities output to (tokens, ner_tags) format.
        Compatible with MedicalNER training data format.
        """
        entities = self.extract_entities(text)
        tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
        ner_tags = [0] * len(tokens)

        # Map entity types to label IDs (matching LABEL_LIST in medical_ner.py)
        entity_label_map = {
            "drug": 1,    # B-DRUG
            "disease": 3, # B-DISEASE
            "symptom": 5, # B-SYMPTOM
            "dosage": 7,  # B-DOSAGE
            "date": 9,    # B-DATE
        }

        for i, token in enumerate(tokens):
            for ent_type, label_id in entity_label_map.items():
                entity_list = entities.get(ent_type, [])
                if any(token.lower() in e.lower() or e.lower() in token.lower() for e in entity_list):
                    ner_tags[i] = label_id
                    break

        return tokens, ner_tags


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ner = JaisNER()
    text = "المريض يأخذ أموكسيسيلين 500 ملغ لالتهاب اللوزتين"
    print("Entities:", ner.extract_entities(text))
    tokens, tags = ner.annotate_tokens(text)
    print(f"Tokens: {tokens}")
    print(f"Tags:   {tags}")
