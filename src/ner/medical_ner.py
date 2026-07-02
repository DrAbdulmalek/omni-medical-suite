# src/ner/medical_ner.py
"""Medical NER using AraBERT. Extracts drugs, diseases, symptoms, dosages from Arabic medical text."""
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, Trainer, TrainingArguments
from datasets import Dataset
import numpy as np
import logging

logger = logging.getLogger(__name__)

LABEL_LIST = ["O", "B-DRUG","I-DRUG", "B-DISEASE","I-DISEASE", "B-SYMPTOM","I-SYMPTOM", "B-DOSAGE","I-DOSAGE", "B-DATE","I-DATE"]
ID2LABEL = {i: l for i, l in enumerate(LABEL_LIST)}
LABEL2ID = {l: i for i, l in enumerate(LABEL_LIST)}

class MedicalNER:
    def __init__(self, model_name="aubmindlab/bert-base-arabertv02"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name, num_labels=len(LABEL_LIST), id2label=ID2LABEL, label2id=LABEL2ID)

    def tokenize_and_align_labels(self, examples):
        tokenized = self.tokenizer(examples["tokens"], truncation=True, is_split_into_words=True)
        labels = []
        for i, label in enumerate(examples["ner_tags"]):
            word_ids = tokenized.word_ids(batch_index=i)
            prev = None; label_ids = []
            for wid in word_ids:
                if wid is None: label_ids.append(-100)
                elif wid != prev: label_ids.append(label[wid])
                else: label_ids.append(-100)
                prev = wid
            labels.append(label_ids)
        tokenized["labels"] = labels
        return tokenized

    def compute_metrics(self, p):
        preds = np.argmax(p.predictions, axis=2)
        mask = p.label_ids != -100
        return {"accuracy": float((preds == p.label_ids)[mask].mean())}

    def train(self, train_dataset, eval_dataset=None, epochs=5, output_dir="outputs/medical_ner"):
        args = TrainingArguments(output_dir=output_dir, num_train_epochs=epochs,
            per_device_train_batch_size=8, evaluation_strategy="epoch", save_strategy="epoch",
            load_best_model_at_end=True, metric_for_best_model="accuracy", greater_is_better=True,
            fp16=torch.cuda.is_available(), logging_steps=10, report_to="none")
        trainer = Trainer(model=self.model, args=args, train_dataset=train_dataset,
            eval_dataset=eval_dataset, tokenizer=self.tokenizer, compute_metrics=self.compute_metrics)
        trainer.train(); trainer.save_model(output_dir)
        return trainer