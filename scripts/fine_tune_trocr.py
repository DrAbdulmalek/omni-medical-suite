# scripts/fine_tune_trocr.py
"""
Fine-tune TrOCR (Microsoft) on Arabic medical OCR dataset.
Uses the DrAbdulmalek/arabic-medical-ocr-corrections dataset from HuggingFace.

Usage:
    python scripts/fine_tune_trocr.py --epochs 5 --batch_size 8
    python scripts/fine_tune_trocr.py --push_to_hub  # push to HF after training

Requirements:
    pip install transformers datasets torch jiwer accelerate
"""
import argparse
import logging
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    TrOCRProcessor,
    VisionEncoderDecoderModel,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    default_data_collator
)
from PIL import Image

from jiwer import cer, wer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_metrics(pred):
    """Compute CER and WER for evaluation."""
    labels = pred.label_ids
    pred_ids = pred.predictions

    pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
    label_str = processor.batch_decode(labels, skip_special_tokens=True)

    pred_str = [p.strip() for p in pred_str]
    label_str = [l.strip() for l in label_str]

    try:
        total_cer = cer(label_str, pred_str)
        total_wer = wer(label_str, pred_str)
    except Exception:
        total_cer = total_wer = 1.0

    exact_matches = sum(1 for p, l in zip(pred_str, label_str) if p == l)
    match_rate = exact_matches / len(label_str) if label_str else 0

    logger.info(f"CER: {total_cer:.4f} | WER: {total_wer:.4f} | Match: {match_rate:.2%}")

    return {
        "cer": total_cer,
        "wer": total_wer,
        "match_rate": match_rate,
    }


def preprocess_function(examples, processor, max_length=128):
    """Prepare images and text for TrOCR training."""
    # Handle image column (might be PIL Image or file path)
    images = []
    for img in examples["image"]:
        if isinstance(img, Image.Image):
            images.append(img.convert("RGB"))
        elif isinstance(img, str):
            images.append(Image.open(img).convert("RGB"))
        else:
            images.append(Image.open(img["path"]).convert("RGB"))

    pixel_values = processor(images, return_tensors="pt").pixel_values

    # Tokenize text labels
    labels = processor.tokenizer(
        examples["correct_text"],
        padding="max_length",
        max_length=max_length,
        truncation=True
    ).input_ids

    # Replace padding token id with -100 (ignored by loss)
    labels = [
        [(l if l != processor.tokenizer.pad_token_id else -100) for l in label]
        for label in labels
    ]

    return {"pixel_values": pixel_values, "labels": labels}


def main():
    parser = argparse.ArgumentParser(description="Fine-tune TrOCR on Arabic medical OCR data")
    parser.add_argument("--dataset", default="DrAbdulmalek/arabic-medical-ocr-corrections",
                        help="HF dataset name")
    parser.add_argument("--model", default="microsoft/trocr-base-handwritten",
                        help="Base TrOCR model")
    parser.add_argument("--output_dir", default="./outputs/trocr_arabic_medical",
                        help="Output directory")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--push_to_hub", action="store_true",
                        help="Push model to HuggingFace after training")
    parser.add_argument("--hf_model_name", default="DrAbdulmalek/trocr-arabic-medical",
                        help="HF model name for push")
    args = parser.parse_args()

    global processor
    processor = TrOCRProcessor.from_pretrained(args.model)

    # Load dataset
    logger.info(f"Loading dataset: {args.dataset}")
    try:
        dataset = load_dataset(args.dataset, split="train")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        logger.info("Creating small synthetic dataset for testing...")
        # Fallback: create a tiny synthetic dataset for testing
        from datasets import Dataset as HFDS
        dataset = HFDS.from_dict({
            "image": [Image.new("RGB", (256, 64), "white") for _ in range(10)],
            "correct_text": ["test text"] * 10
        })

    logger.info(f"Dataset size: {len(dataset)}")

    # Check required columns
    if "image" not in dataset.column_names or "correct_text" not in dataset.column_names:
        logger.error("Dataset must have 'image' and 'correct_text' columns")
        return

    # Preprocess
    logger.info("Preprocessing dataset...")
    processed = dataset.map(
        lambda x: preprocess_function(x, processor, args.max_length),
        batched=True,
        remove_columns=dataset.column_names,
        desc="Preprocessing"
    )

    # Split into train/eval
    split = processed.train_test_split(test_size=0.1, seed=42)
    train_ds = split["train"]
    eval_ds = split["test"]

    logger.info(f"Train: {len(train_ds)} | Eval: {len(eval_ds)}")

    # Load model
    model = VisionEncoderDecoderModel.from_pretrained(args.model)
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    # Set beam search parameters for generation
    model.config.vocab_size = model.config.decoder.vocab_size
    model.config.eos_token_id = processor.tokenizer.sep_token_id
    model.config.max_length = args.max_length
    model.config.early_stopping = True
    model.config.no_repeat_ngram_size = 3
    model.config.length_penalty = 2.0

    # Training arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        weight_decay=0.01,
        save_strategy="epoch",
        evaluation_strategy="epoch",
        logging_steps=50,
        predict_with_generate=True,
        fp16=torch.cuda.is_available(),
        gradient_accumulation_steps=2,
        load_best_model_at_end=True,
        metric_for_best_model="cer",
        greater_is_better=False,
        report_to="none",
        remove_unused_columns=False,
    )

    # Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=processor.feature_extractor,
        compute_metrics=compute_metrics,
    )

    # Train
    logger.info("Starting TrOCR fine-tuning...")
    trainer.train()

    # Save
    trainer.save_model(args.output_dir)
    processor.save_pretrained(args.output_dir)
    logger.info(f"Model saved to {args.output_dir}")

    # Push to Hub
    if args.push_to_hub:
        logger.info(f"Pushing to HuggingFace: {args.hf_model_name}")
        model.push_to_hub(args.hf_model_name)
        processor.push_to_hub(args.hf_model_name)
        logger.info("Push complete!")

    # Final evaluation
    logger.info("Running final evaluation...")
    metrics = trainer.evaluate()
    logger.info(f"Final metrics: {metrics}")


if __name__ == "__main__":
    main()