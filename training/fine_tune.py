#!/usr/bin/env python3
"""
Fine-Tuning Script for Arabic Handwriting OCR
==============================================
Uses corrections collected via the Handwriting Trainer HF Space (corrections.db / corrections.jsonl)
to fine-tune TrOCR or Qwen2-VL for improved Arabic medical handwriting recognition.

Usage:
    python fine_tune.py --data /path/to/corrections.jsonl --model trocr --epochs 3
    python fine_tune.py --data /app/data/corrections.db  --model qwen --epochs 1
    python fine_tune.py --data ./data --export-hf ./hf-dataset --export-repo DrAbdulmalek/arabic-ocr-corrections

Requirements:
    pip install torch transformers datasets accelerate peft
    # For Qwen2-VL with LoRA: pip install bitsandbytes
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_from_jsonl(path: str) -> list[dict]:
    """Load correction pairs from JSONL file produced by the HF Space."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    logger.info(f"Loaded {len(records)} records from {path}")
    return records


def load_from_db(path: str) -> list[dict]:
    """Load correction pairs from the SQLite DB used by the HF Space."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT image_hash, original_text, corrected_text, confidence, created_at
        FROM corrections
        WHERE corrected_text IS NOT NULL
          AND corrected_text != ''
          AND corrected_text != original_text
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    records = []
    for r in rows:
        records.append({
            "image_hash": r["image_hash"],
            "original_text": r["original_text"],
            "corrected_text": r["corrected_text"],
            "confidence": r["confidence"],
        })
    logger.info(f"Loaded {len(records)} corrections from {path}")
    return records


def load_training_data(source: str) -> list[dict]:
    """Auto-detect format (JSONL or SQLite) and load corrections."""
    if source.endswith(".jsonl"):
        return load_from_jsonl(source)
    elif source.endswith(".db") or source.endswith(".sqlite") or source.endswith(".sqlite3"):
        return load_from_db(source)
    elif os.path.isdir(source):
        jsonl = os.path.join(source, "corrections.jsonl")
        db = os.path.join(source, "corrections.db")
        if os.path.exists(jsonl):
            return load_from_jsonl(jsonl)
        elif os.path.exists(db):
            return load_from_db(db)
        else:
            raise FileNotFoundError(f"No corrections.jsonl or corrections.db in {source}")
    else:
        raise ValueError(f"Unknown data source format: {source}")


# ── Synthetic Image Generation ────────────────────────────────────────────────

def _render_arabic_text(text: str, width: int = 384, height: int = 64) -> "Image.Image":
    """Render Arabic text on a white background for synthetic training data.
    In production, replace with actual word crops from the Space's segmentation pipeline."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    font_paths = [
        "/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size=32)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = max(0, (width - tw) // 2)
    y = max(0, (height - th) // 2 - bbox[1])
    draw.text((x, y), text, fill="black", font=font)
    return img


# ── Dataset Preparation ───────────────────────────────────────────────────────

def prepare_trocr_dataset(records: list[dict], image_dir: Optional[str] = None) -> list[dict]:
    """
    Prepare dataset for TrOCR fine-tuning.
    TrOCR expects: {"image": PIL.Image, "text": str}
    """
    from PIL import Image

    dataset = []
    for rec in records:
        text = rec.get("corrected_text") or rec.get("target_text", "")
        if not text or len(text.strip()) < 1:
            continue

        # Try to load actual word crop image
        if image_dir and rec.get("image_hash"):
            hash_prefix = rec["image_hash"][:8]
            for ext in [".png", ".jpg", ".jpeg"]:
                candidate = os.path.join(image_dir, f"{hash_prefix}{ext}")
                if os.path.exists(candidate):
                    img = Image.open(candidate).convert("RGB")
                    break
            else:
                img = _render_arabic_text(text)
        else:
            img = _render_arabic_text(text)

        dataset.append({"image": img, "text": text.strip()})

    logger.info(f"Prepared {len(dataset)} training samples for TrOCR")
    return dataset


def prepare_qwen_dataset(records: list[dict]) -> list[dict]:
    """
    Prepare dataset for Qwen2-VL fine-tuning.
    Qwen expects conversation format with image + text prompt.
    """
    dataset = []
    for rec in records:
        text = rec.get("corrected_text") or rec.get("target_text", "")
        if not text or len(text.strip()) < 1:
            continue

        img = _render_arabic_text(text)

        dataset.append({
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": "\u0627\u0642\u0631\u0623 \u0627\u0644\u0646\u0635 \u0627\u0644\u0639\u0631\u0628\u064a \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0635\u0648\u0631\u0629 \u0628\u062f\u0642\u0629."},
                    ],
                },
                {
                    "role": "assistant",
                    "content": text.strip(),
                },
            ]
        })

    logger.info(f"Prepared {len(dataset)} training samples for Qwen2-VL")
    return dataset


# ── TrOCR Fine-Tuning ────────────────────────────────────────────────────────

def finetune_trocr(
    records: list[dict],
    model_name: str = "microsoft/trocr-base-handwritten",
    output_dir: str = "./trocr-finetuned",
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 5e-5,
    image_dir: Optional[str] = None,
    max_samples: Optional[int] = None,
):
    """Fine-tune TrOCR on collected corrections."""
    import torch
    from transformers import (
        TrOCRProcessor,
        VisionEncoderDecoderModel,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )
    from datasets import Dataset

    # Prepare dataset
    raw_data = prepare_trocr_dataset(records, image_dir)
    if max_samples:
        raw_data = raw_data[:max_samples]

    if len(raw_data) < 2:
        logger.error(f"Need at least 2 samples, got {len(raw_data)}")
        return None

    # Split train/eval
    random.shuffle(raw_data)
    split_idx = max(1, int(len(raw_data) * 0.9))
    train_data = raw_data[:split_idx]
    eval_data = raw_data[split_idx:]

    # Process into HF Dataset format
    def make_hf_items(data):
        items = []
        for d in data:
            items.append({"_image": d["image"], "_text": d["text"]})
        return items

    train_items = make_hf_items(train_data)
    eval_items = make_hf_items(eval_data)

    # Load model + processor
    logger.info(f"Loading model: {model_name}")
    processor = TrOCRProcessor.from_pretrained(model_name)
    model = VisionEncoderDecoderModel.from_pretrained(model_name)

    # Configure for Arabic
    processor.tokenizer.pad_token = processor.tokenizer.eos_token
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.vocab_size = model.config.decoder.vocab_size
    model.config.eos_token_id = processor.tokenizer.sep_token_id

    def process_single(item):
        encoding = processor(
            images=[item["_image"]], text=[item["_text"]],
            padding="max_length", max_length=128, truncation=True, return_tensors="pt"
        )
        labels = encoding.input_ids.clone()
        labels[labels == processor.tokenizer.pad_token_id] = -100
        return {
            "pixel_values": encoding.pixel_values.squeeze(0).numpy(),
            "labels": labels.squeeze(0).numpy(),
        }

    logger.info("Processing datasets...")
    train_processed = [process_single(item) for item in train_items]
    eval_processed = [process_single(item) for item in eval_items]
    train_ds = Dataset.from_list(train_processed)
    eval_ds = Dataset.from_list(eval_processed)

    # Cast to torch tensors
    train_ds = train_ds.with_format("torch")
    eval_ds = eval_ds.with_format("torch")

    # Training
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        predict_with_generate=True,
        generation_max_length=128,
        logging_steps=10,
        push_to_hub=False,
        remove_unused_columns=False,
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=processor.feature_extractor,
    )

    logger.info(f"Training TrOCR: {len(train_ds)} train, {len(eval_ds)} eval, {epochs} epochs")
    trainer.train()

    # Save
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    logger.info(f"Model saved to {output_dir}")

    metrics = trainer.evaluate()
    logger.info(f"Eval metrics: {metrics}")
    return output_dir


# ── Qwen2-VL Fine-Tuning (LoRA) ─────────────────────────────────────────────

def finetune_qwen(
    records: list[dict],
    model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
    output_dir: str = "./qwen-finetuned",
    epochs: int = 1,
    batch_size: int = 1,
    learning_rate: float = 2e-4,
    lora_r: int = 16,
    lora_alpha: int = 32,
    max_samples: Optional[int] = None,
):
    """Fine-tune Qwen2-VL with LoRA on collected corrections."""
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoProcessor, AutoModelForVision2Seq,
        Trainer, TrainingArguments, BitsAndBytesConfig,
    )
    from datasets import Dataset

    raw_data = prepare_qwen_dataset(records)
    if max_samples:
        raw_data = raw_data[:max_samples]

    if len(raw_data) < 2:
        logger.error(f"Need at least 2 samples, got {len(raw_data)}")
        return None

    random.shuffle(raw_data)
    split_idx = max(1, int(len(raw_data) * 0.9))
    train_data = raw_data[:split_idx]
    eval_data = raw_data[split_idx:]

    train_ds = Dataset.from_list(train_data)
    eval_ds = Dataset.from_list(eval_data)

    logger.info(f"Loading model: {model_name}")
    processor = AutoProcessor.from_pretrained(model_name)

    # 4-bit quantization for memory efficiency
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForVision2Seq.from_pretrained(
        model_name, quantization_config=bnb_config, device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=5,
        push_to_hub=False,
        fp16=torch.cuda.is_available(),
        report_to="none",
        gradient_accumulation_steps=4,
        warmup_ratio=0.1,
    )

    def collate_fn(batch):
        texts = []
        images = []
        for item in batch:
            messages = item["messages"]
            prompt_text = processor.apply_chat_template(
                messages[:-1], tokenize=False, add_generation_prompt=True
            )
            texts.append(prompt_text)
            for content in messages[0]["content"]:
                if content["type"] == "image":
                    images.append(content["image"])
                    break

        inputs = processor(text=texts, images=images, padding=True, return_tensors="pt")

        labels = []
        for item in batch:
            target = item["messages"][-1]["content"]
            label_ids = processor.tokenizer(target, return_tensors="pt").input_ids[0]
            labels.append(label_ids)
        inputs["labels"] = torch.nn.utils.rnn.pad_sequence(
            labels, batch_first=True, padding_value=-100
        )
        return inputs

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collate_fn,
    )

    logger.info(f"Training Qwen2-VL LoRA: {len(train_ds)} train, {len(eval_ds)} eval")
    trainer.train()

    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    logger.info(f"LoRA adapter saved to {output_dir}")
    return output_dir


# ── Export for HF Dataset Integration ─────────────────────────────────────────

def export_to_hf_dataset(
    records: list[dict],
    output_path: str = "./arabic_ocr_corrections",
    repo_id: Optional[str] = None,
):
    """Export corrections as a HuggingFace Dataset for sharing or further training."""
    from datasets import Dataset, DatasetDict

    dataset = Dataset.from_list([
        {
            "original_text": r.get("original_text", ""),
            "corrected_text": r.get("corrected_text", ""),
            "confidence": r.get("confidence", 0.0),
            "image_hash": r.get("image_hash", ""),
        }
        for r in records
    ])

    split = dataset.train_test_split(test_size=0.1, seed=42)
    ds = DatasetDict({"train": split["train"], "test": split["test"]})
    ds.save_to_disk(output_path)
    logger.info(f"Dataset saved to {output_path}")

    if repo_id:
        try:
            ds.push_to_hub(repo_id, private=True)
            logger.info(f"Pushed to HF Hub: {repo_id}")
        except Exception as e:
            logger.warning(f"Failed to push to Hub: {e}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune Arabic OCR model on corrections from Handwriting Trainer"
    )
    parser.add_argument("--data", required=True,
                        help="Path to corrections.jsonl, corrections.db, or data directory")
    parser.add_argument("--model", default="trocr", choices=["trocr", "qwen"],
                        help="Model type (default: trocr)")
    parser.add_argument("--model-name", default=None,
                        help="Override model name (default: auto)")
    parser.add_argument("--output", default="./finetuned-model",
                        help="Output directory for the fine-tuned model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--max-samples", type=int, default=None,
                        help="Limit training samples (useful for testing)")
    parser.add_argument("--image-dir", default=None,
                        help="Directory with word crop images")
    parser.add_argument("--export-hf", default=None,
                        help="Export dataset to HF format at this path")
    parser.add_argument("--export-repo", default=None,
                        help="Push dataset to this HF Hub repo ID")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank (Qwen)")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha (Qwen)")
    args = parser.parse_args()

    # Load
    records = load_training_data(args.data)
    if not records:
        logger.error("No training data. Collect corrections via the HF Space first.")
        sys.exit(1)
    logger.info(f"Loaded {len(records)} correction records")

    # Optional export
    if args.export_hf or args.export_repo:
        export_to_hf_dataset(records, args.export_hf or "./hf-dataset", args.export_repo)

    # Fine-tune
    if args.model == "trocr":
        model_name = args.model_name or "microsoft/trocr-base-handwritten"
        finetune_trocr(
            records, model_name=model_name, output_dir=args.output,
            epochs=args.epochs, batch_size=args.batch_size,
            learning_rate=args.lr, image_dir=args.image_dir,
            max_samples=args.max_samples,
        )
    elif args.model == "qwen":
        model_name = args.model_name or "Qwen/Qwen2-VL-7B-Instruct"
        finetune_qwen(
            records, model_name=model_name, output_dir=args.output,
            epochs=args.epochs, batch_size=args.batch_size,
            learning_rate=args.lr, lora_r=args.lora_r,
            lora_alpha=args.lora_alpha, max_samples=args.max_samples,
        )


if __name__ == "__main__":
    main()