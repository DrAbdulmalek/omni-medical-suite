# src/ner/llm_ner_annotator.py
"""Zero-shot NER annotation using pre-trained Arabic BERT."""
from transformers import pipeline, AutoModelForTokenClassification, AutoTokenizer
import torch, re
from typing import List, Tuple

LABEL_MAP = {0:"O", 1:"B-DRUG",2:"I-DRUG", 3:"B-DISEASE",4:"I-DISEASE",
             5:"B-SYMPTOM",6:"I-SYMPTOM", 7:"B-DOSAGE",8:"I-DOSAGE"}

class LLMNERAnnotator:
    def __init__(self, model_name="aubmindlab/bert-base-arabertv02", device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name, num_labels=len(LABEL_MAP),
            id2label={v:k for k,v in LABEL_MAP.items()}, label2id=LABEL_MAP).to(self.device)
        self.ner_pipeline = pipeline("ner", model=self.model, tokenizer=self.tokenizer,
            aggregation_strategy="simple", device=0 if self.device=="cuda" else -1)

    def annotate(self, text: str) -> Tuple[List[str], List[int]]:
        text = re.sub(r'\s+', ' ', text).strip()
        results = self.ner_pipeline(text)
        tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
        ner_tags = [0]*len(tokens)
        for ent in results:
            et = ent.get('word',''); eg = ent.get('entity_group','')
            for i,tok in enumerate(tokens):
                if et.lower() in tok.lower() or tok.lower() in et.lower():
                    if 'DRUG' in eg: ner_tags[i]=1
                    elif 'DISEASE' in eg: ner_tags[i]=3
                    elif 'SYMPTOM' in eg: ner_tags[i]=5
                    elif 'DOSAGE' in eg: ner_tags[i]=7
                    break
        return tokens, ner_tags