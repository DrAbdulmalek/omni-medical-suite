# src/llm/proofreader.py
"""Post-OCR correction using LLM for Arabic medical text. Requires GPU 24GB+."""
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from typing import Dict

class MedicalProofreader:
    def __init__(self, model_name="core42/jais-13b-chat", load_in_8bit=True):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto", torch_dtype=torch.bfloat16,
            load_in_8bit=load_in_8bit, trust_remote_code=True)
        self.model.eval()

    def proofread(self, ocr_text: str) -> Dict:
        prompt = f"""أنت مدقق طبي. صحح الأخطاء واستخرج الكيانات:
نص: {ocr_text}
**النص المصحح:**
**الكيانات:**
- دواء: ...
- مرض: ...
- جرعة: ..."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=512, temperature=0.3,
                do_sample=True, top_p=0.9, pad_token_id=self.tokenizer.eos_token_id)
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        corrected = self._extract_section(response, "**النص المصحح:**", "**الكيانات:**")
        return {"original": ocr_text, "corrected": corrected, "entities": self._parse_entities(response)}

    def _extract_section(self, text, start, end):
        try: return text.split(start)[1].split(end)[0].strip()
        except: return text

    def _parse_entities(self, text):
        entities = {"drug":[], "disease":[], "dosage":[], "symptom":[]}
        for line in text.split('\n'):
            for key in ["دواء","مرض","جرعة","عرض"]:
                if key in line and ':' in line:
                    items = [x.strip() for x in line.split(':')[-1].split(',') if x.strip() and x.strip()!='-']
                    k = {"دواء":"drug","مرض":"disease","جرعة":"dosage","عرض":"symptom"}.get(key)
                    if k: entities[k] = items
        return entities