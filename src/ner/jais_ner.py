# src/ner/jais_ner.py
"""Zero-shot Medical NER using Jais LLM. Requires GPU 24GB+."""
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch, re
from typing import List, Dict, Tuple

class JaisNER:
    def __init__(self, model_name="core42/jais-13b-chat", load_in_8bit=True):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto", torch_dtype=torch.bfloat16,
            load_in_8bit=load_in_8bit, trust_remote_code=True)
        self.model.eval()

    def extract_entities(self, text: str) -> Dict:
        prompt = f"""أنت مساعد طبي. استخرج الكيانات من: {text}
أخرج فقط: دواء: [] مرض: [] عرض: [] جرعة: []"""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=512, temperature=0.1,
                do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> Dict:
        result = {"drug":[], "disease":[], "symptom":[], "dosage":[]}
        current = None
        for line in response.split('\n'):
            line = line.strip()
            if "دواء" in line: current="drug"
            elif "مرض" in line: current="disease"
            elif "عرض" in line: current="symptom"
            elif "جرعة" in line: current="dosage"
            elif current and line and not line.startswith('-'):
                result[current].extend([x.strip() for x in line.split(',') if x.strip()])
        return result

    def annotate_tokens(self, text: str) -> Tuple[List[str], List[int]]:
        entities = self.extract_entities(text)
        tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
        ner_tags = [0]*len(tokens)
        for i,tok in enumerate(tokens):
            for etype,lid in [("drug",1),("disease",3),("symptom",5)]:
                if any(tok.lower() in e.lower() for e in entities.get(etype,[])):
                    ner_tags[i]=lid; break
        return tokens, ner_tags