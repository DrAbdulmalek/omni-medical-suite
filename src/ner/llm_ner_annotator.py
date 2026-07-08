# src/ner/llm_ner_annotator.py
"""
LLM-based NER annotation using pre-trained Arabic BERT (AraBERT).

Provides zero-shot / few-shot NER annotation for converting
HITL correction text into NER training data format.

Usage:
    annotator = LLMNERAnnotator()
    tokens, tags = annotator.annotate("المريض يأخذ أموكسيسيلين 500 ملغ")
    print(list(zip(tokens, tags)))
"""
import logging
import re

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

logger = logging.getLogger(__name__)

LABEL_MAP = {
    0: "O",
    1: "B-DRUG",    2: "I-DRUG",
    3: "B-DISEASE", 4: "I-DISEASE",
    5: "B-SYMPTOM", 6: "I-SYMPTOM",
    7: "B-DOSAGE",  8: "I-DOSAGE",
    9: "B-DATE",   10: "I-DATE",
}
ID2LABEL = {v: k for k, v in LABEL_MAP.items()}


class LLMNERAnnotator:
    """
    Zero-shot NER annotation using AraBERT.
    Maps pipeline entity groups to our label schema.
    """

    def __init__(
        self,
        model_name: str = "aubmindlab/bert-base-arabertv02",
        device: str | None = None,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading NER annotator: {model_name} on {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name,
            num_labels=len(LABEL_MAP),
            id2label=ID2LABEL,
            label2id=LABEL_MAP,
        ).to(self.device)

        self.ner_pipeline = pipeline(
            "ner",
            model=self.model,
            tokenizer=self.tokenizer,
            aggregation_strategy="simple",
            device=0 if self.device == "cuda" else -1,
        )

    def annotate(self, text: str) -> tuple[list[str], list[int]]:
        """
        Annotate text with NER tags.

        Returns:
            Tuple of (tokens, ner_tags) where ner_tags uses LABEL_MAP ids.
        """
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return [], []

        # Run NER pipeline
        results = self.ner_pipeline(text)

        # Tokenize for alignment
        tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
        ner_tags = [0] * len(tokens)

        # Map entities to token positions
        entity_label_map = {
            "DRUG": 1, "DISEASE": 3, "SYMPTOM": 5,
            "DOSAGE": 7, "DATE": 9,
        }

        for ent in results:
            ent_text = ent.get('word', '')
            ent_group = ent.get('entity_group', '')

            for label_name, label_id in entity_label_map.items():
                if label_name in ent_group.upper():
                    for i, tok in enumerate(tokens):
                        if ent_text.lower() in tok.lower() or tok.lower() in ent_text.lower():
                            ner_tags[i] = label_id
                    break

        return tokens, ner_tags

    def batch_annotate(self, texts: list[str]) -> list[tuple[list[str], list[int]]]:
        """Annotate a batch of texts."""
        return [self.annotate(text) for text in texts]

    def annotate_with_labels(self, text: str) -> list[tuple[str, str]]:
        """
        Annotate and return (token, label_string) pairs.
        Useful for inspection and debugging.
        """
        tokens, tags = self.annotate(text)
        return [(tok, LABEL_MAP.get(tag, "O")) for tok, tag in zip(tokens, tags, strict=False)]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    annotator = LLMNERAnnotator()
    tokens, tags = annotator.annotate("المريض يأخذ أموكسيسيلين 500 ملغ لالتهاب اللوزتين")
    print(f"Tokens: {tokens}")
    print(f"Tags:   {tags}")
    print(f"Labeled: {annotator.annotate_with_labels('المريض يأخذ أموكسيسيلين 500 ملغ لالتهاب اللوزتين')}")
