# src/ner/medical_ner.py
"""
Medical Named Entity Recognition (NER) using AraBERT.

Supports fine-tuning AraBERT for Arabic medical text to extract:
  DRUG, DISEASE, SYMPTOM, DOSAGE, DATE

Usage:
    # Training
    ner = MedicalNER()
    ner.train(tokenized_dataset, eval_dataset=eval_ds, epochs=5)

    # Inference (after training)
    from transformers import pipeline
    ner_pipe = pipeline("ner", model="outputs/medical_ner",
                        tokenizer="aubmindlab/bert-base-arabertv02",
                        aggregation_strategy="simple")
    result = ner_pipe("وصفة أموكسيسيلين 500 ملغ لالتهاب اللوزتين")
"""
import logging

import numpy as np
import torch
from datasets import Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

logger = logging.getLogger(__name__)

# ── Label Schema ────────────────────────────────────────────────────────────
LABEL_LIST = [
    "O",                # 0  Outside
    "B-DRUG",   "I-DRUG",     # 1, 2
    "B-DISEASE", "I-DISEASE", # 3, 4
    "B-SYMPTOM", "I-SYMPTOM", # 5, 6
    "B-DOSAGE",  "I-DOSAGE",  # 7, 8
    "B-DATE",    "I-DATE",    # 9, 10
]
ID2LABEL = {i: label for i, label in enumerate(LABEL_LIST)}
LABEL2ID = {label: i for i, label in enumerate(LABEL_LIST)}
NUM_LABELS = len(LABEL_LIST)


class MedicalNER:
    """Fine-tune AraBERT for Arabic medical NER."""

    def __init__(self, model_name: str = "aubmindlab/bert-base-arabertv02"):
        self.model_name = model_name
        logger.info(f"Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name,
            num_labels=NUM_LABELS,
            id2label=ID2LABEL,
            label2id=LABEL2ID,
        )

    def tokenize_and_align_labels(self, examples: dict) -> dict:
        """
        Tokenize input tokens and align NER labels with subword tokens.
        Subwords within the same word get label -100 (ignored in loss).
        """
        tokenized = self.tokenizer(
            examples["tokens"],
            truncation=True,
            is_split_into_words=True,
        )
        labels = []
        for i, label in enumerate(examples["ner_tags"]):
            word_ids = tokenized.word_ids(batch_index=i)
            previous_word_idx = None
            label_ids = []
            for word_idx in word_ids:
                if word_idx is None:
                    label_ids.append(-100)
                elif word_idx != previous_word_idx:
                    label_ids.append(label[word_idx])
                else:
                    label_ids.append(-100)  # subword continuation
                previous_word_idx = word_idx
            labels.append(label_ids)
        tokenized["labels"] = labels
        return tokenized

    def compute_metrics(self, p) -> dict:
        """Compute token-level accuracy on non-padding tokens."""
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Mask padding tokens
        true_labels = [[LABEL_LIST[l] for l in label if l != -100] for label in labels]
        true_preds = [
            [LABEL_LIST[p_] for (p_, l_) in zip(pred, label) if l_ != -100]
            for pred, label in zip(predictions, labels)
        ]

        # Simple token-level accuracy
        correct = sum(
            1 for t, p_ in zip(true_labels, true_preds) for tl, pl in zip(t, p_) if tl == pl
        )
        total = sum(len(t) for t in true_labels)
        accuracy = correct / total if total > 0 else 0.0

        # Try seqeval for proper NER metrics
        try:
            from seqeval.metrics import classification_report
            report = classification_report(true_labels, true_preds, output_dict=True)
            f1 = report.get("micro avg", {}).get("f1-score", 0.0)
        except ImportError:
            f1 = 0.0

        return {"accuracy": accuracy, "f1": f1}

    def train(
        self,
        train_dataset: Dataset,
        eval_dataset: Dataset = None,
        epochs: int = 5,
        output_dir: str = "outputs/medical_ner",
        batch_size: int = 8,
    ):
        """
        Fine-tune AraBERT on NER dataset.

        Args:
            train_dataset: Tokenized training dataset (tokens + ner_tags).
            eval_dataset: Optional tokenized eval dataset.
            epochs: Number of training epochs.
            output_dir: Where to save the model.
            batch_size: Per-device batch size.
        """
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            fp16=torch.cuda.is_available(),
            logging_steps=10,
            report_to="none",
            warmup_ratio=0.1,
            weight_decay=0.01,
            learning_rate=2e-5,
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
            compute_metrics=self.compute_metrics,
        )

        logger.info("Starting Medical NER training...")
        trainer.train()
        trainer.save_model(output_dir)
        logger.info(f"Model saved to {output_dir}")
        return trainer


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example: create tiny dataset and train
    ner = MedicalNER()
    example_data = {
        "tokens": [
            ["المريض", "يأخذ", "أموكسيسيلين", "500", "ملغ", "لالتهاب", "اللوزتين"],
            ["وصفة", "باراسيتامول", "2", "حبة"],
        ],
        "ner_tags": [
            [0, 0, 1, 7, 8, 3, 4],  # B-DRUG, B-DOSAGE, I-DOSAGE, B-DISEASE, I-DISEASE
            [0, 1, 7, 8],            # B-DRUG, B-DOSAGE, I-DOSAGE
        ],
    }
    dataset = Dataset.from_dict(example_data)
    tokenized = dataset.map(ner.tokenize_and_align_labels, batched=True)
    ner.train(tokenized, epochs=3)