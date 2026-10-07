#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fine-tuning TrOCR على خط اليد العربي.

الاستخدام:
    python train_trocr.py --data output/S001 --epochs 20 --batch 8

⚠️ يحتاج GPU. على CPU سيكون بطيئاً جداً.
⚠️ راجع الترخيص: trocr-base-handwritten (MIT) — آمن تجارياً.
"""

import argparse, json
from pathlib import Path
import pandas as pd
import torch
from torch.utils.data import Dataset
from PIL import Image
from transformers import (
    TrOCRProcessor, VisionEncoderDecoderModel,
    Seq2SeqTrainer, Seq2SeqTrainingArguments
)
import evaluate

# ==================================================
# Dataset
# ==================================================
class ArabicWordDataset(Dataset):
    def __init__(self, df, crops_dir, processor, max_target=32):
        self.df = df.reset_index(drop=True)
        self.crops_dir = Path(crops_dir)
        self.processor = processor
        self.max_target = max_target

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        row = self.df.iloc[i]
        img_path = self.crops_dir / Path(row['crop_path']).name
        image = Image.open(img_path).convert('RGB')

        pixel_values = self.processor(
            images=image, return_tensors='pt').pixel_values.squeeze()

        labels = self.processor.tokenizer(
            row['text'],
            padding='max_length',
            max_length=self.max_target,
            truncation=True,
            return_tensors='pt'
        ).input_ids.squeeze()

        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        return {'pixel_values': pixel_values, 'labels': labels}

# ==================================================
# Metrics
# ==================================================
cer_metric = evaluate.load('cer')

def compute_metrics(pred):
    pred_ids = pred.predictions
    label_ids = pred.label_ids
    label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
    pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
    label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
    cer = cer_metric.compute(predictions=pred_str, references=label_str)
    return {'cer': cer}

# ==================================================
# Main
# ==================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='مجلد العينة')
    ap.add_argument('--base', default='microsoft/trocr-base-handwritten',
                    help='النموذج الأساسي')
    ap.add_argument('--output', default='./trocr-arabic-finetuned')
    ap.add_argument('--epochs', type=int, default=20)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--lr', type=float, default=5e-5)
    ap.add_argument('--max-target', type=int, default=32)
    args = ap.parse_args()

    global processor
    data_dir = Path(args.data)
    crops_dir = data_dir / 'crops'

    # قراءة التصحيحات
    corrections_file = data_dir / 'corrections.xlsx'
    if not corrections_file.exists():
        corrections_file = data_dir / 'corrections.csv'
    if not corrections_file.exists():
        print("❌ لم أجد corrections.csv أو corrections.xlsx")
        return

    df = pd.read_csv(corrections_file) if corrections_file.suffix=='.csv' \
         else pd.read_excel(corrections_file)

    # نحتفظ فقط بالأسطر التي فيها نص
    df = df[df['text'].notna() & (df['text'].astype(str).str.strip() != '')]
    df['text'] = df['text'].astype(str).str.strip()

    if len(df) < 50:
        print(f"⚠️ فقط {len(df)} عينة. يُنصح بـ500+ للتدريب الفعلي.")

    # Split: 80/10/10
    n = len(df)
    train_df = df.iloc[:int(n*0.8)]
    val_df = df.iloc[int(n*0.8):int(n*0.9)]
    test_df = df.iloc[int(n*0.9):]

    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # تحميل النموذج
    processor = TrOCRProcessor.from_pretrained(args.base)
    model = VisionEncoderDecoderModel.from_pretrained(args.base)

    # إعداد tokenizer للنص العربي
    # مهم: نحتاج تعيين فاصل جديد + pad token
    if model.config.decoder_start_token_id is None:
        model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    if model.config.pad_token_id is None:
        model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.vocab_size = model.config.decoder.vocab_size

    model.config.eos_token_id = processor.tokenizer.sep_token_id
    model.config.max_length = args.max_target
    model.config.early_stopping = True
    model.config.no_repeat_ngram_size = 3
    model.config.length_penalty = 2.0
    model.config.num_beams = 4

    # Datasets
    train_ds = ArabicWordDataset(train_df, crops_dir, processor, args.max_target)
    val_ds = ArabicWordDataset(val_df, crops_dir, processor, args.max_target)
    test_ds = ArabicWordDataset(test_df, crops_dir, processor, args.max_target)

    # Training args
    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        predict_with_generate=True,
        evaluation_strategy='epoch',
        save_strategy='epoch',
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        warmup_steps=100,
        logging_steps=20,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model='cer',
        greater_is_better=False,
        fp16=torch.cuda.is_available(),
        report_to='none'
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        tokenizer=processor.image_processor
    )

    print("\n🚀 بدء التدريب...")
    trainer.train()

    print("\n📊 التقييم على test set...")
    results = trainer.evaluate(test_ds)
    print(json.dumps(results, indent=2))

    # حفظ
    trainer.save_model(args.output)
    processor.save_pretrained(args.output)
    print(f"\n✅ محفوظ في: {args.output}")

    # سجل النتائج
    log = {
        'base_model': args.base,
        'train_size': len(train_df),
        'val_size': len(val_df),
        'test_size': len(test_df),
        'epochs': args.epochs,
        'final_cer': results.get('eval_cer'),
        'final_loss': results.get('eval_loss')
    }
    Path(args.output, 'training_log.json').write_text(
        json.dumps(log, indent=2))

if __name__ == '__main__':
    main()
