#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خادم تدريب تفاعلي مع تحديثات لحظية عبر SocketIO.
"""

import argparse, json, threading, time
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ahw-training-secret'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# حالة التدريب العامة
training_state = {
    'running': False,
    'epoch': 0,
    'total_epochs': 0,
    'step': 0,
    'loss': 0.0,
    'cer': 0.0,
    'wer': 0.0,
    'log': [],
    'output_dir': '',
    'error': None
}

def run_training(data_dir, output_dir, epochs, batch, lr, base_model):
    """يشغّل التدريب في thread منفصل ويبث التحديثات."""
    global training_state
    training_state.update({
        'running': True, 'epoch': 0, 'total_epochs': epochs,
        'step': 0, 'loss': 0.0, 'cer': 0.0, 'log': [],
        'output_dir': output_dir, 'error': None
    })

    try:
        import torch
        from torch.utils.data import Dataset
        from PIL import Image
        from transformers import (
            TrOCRProcessor, VisionEncoderDecoderModel,
            Seq2SeqTrainer, Seq2SeqTrainingArguments
        )
        import pandas as pd
        import evaluate

        data_dir = Path(data_dir)
        crops_dir = data_dir / 'crops'

        # قراءة التصحيحات
        corrections = data_dir / 'corrections.xlsx'
        if not corrections.exists():
            corrections = data_dir / 'corrections.csv'
        df = pd.read_excel(corrections) if corrections.suffix == '.xlsx' \
             else pd.read_csv(corrections)
        df = df[df['text'].notna() & (df['text'].astype(str).str.strip() != '')]
        df['text'] = df['text'].astype(str).str.strip()

        # Split
        n = len(df)
        train_df = df.iloc[:int(n*0.8)]
        val_df = df.iloc[int(n*0.8):int(n*0.9)]

        processor = TrOCRProcessor.from_pretrained(base_model)
        model = VisionEncoderDecoderModel.from_pretrained(base_model)
        model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
        model.config.pad_token_id = processor.tokenizer.pad_token_id
        model.config.eos_token_id = processor.tokenizer.sep_token_id
        model.config.max_length = 32
        model.config.early_stopping = True
        model.config.no_repeat_ngram_size = 3
        model.config.length_penalty = 2.0
        model.config.num_beams = 4

        class WordDataset(Dataset):
            def __init__(self, d):
                self.d = d.reset_index(drop=True)
            def __len__(self): return len(self.d)
            def __getitem__(self, i):
                row = self.d.iloc[i]
                img = Image.open(crops_dir / Path(row['crop_path']).name).convert('RGB')
                pv = processor(images=img, return_tensors='pt').pixel_values.squeeze()
                labels = processor.tokenizer(
                    row['text'], padding='max_length', max_length=32,
                    truncation=True, return_tensors='pt').input_ids.squeeze()
                labels[labels == processor.tokenizer.pad_token_id] = -100
                return {'pixel_values': pv, 'labels': labels}

        cer_metric = evaluate.load('cer')
        def compute_metrics(pred):
            pred_ids = pred.predictions
            label_ids = pred.label_ids
            label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
            ps = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
            ls = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
            return {'cer': cer_metric.compute(predictions=ps, references=ls)}

        # Callback لبث التحديثات
        from transformers import TrainerCallback
        class SocketIOCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if logs and 'loss' in logs:
                    training_state['step'] = state.global_step
                    training_state['loss'] = logs.get('loss', 0.0)
                    socketio.emit('training_update', {
                        'epoch': state.epoch,
                        'step': state.global_step,
                        'loss': logs.get('loss', 0.0),
                        'lr': logs.get('learning_rate', 0.0)
                    })
            def on_evaluate(self, args, state, control, metrics=None, **kwargs):
                if metrics:
                    training_state['cer'] = metrics.get('eval_cer', 0.0)
                    socketio.emit('eval_update', {
                        'epoch': state.epoch,
                        'cer': metrics.get('eval_cer', 0.0),
                        'loss': metrics.get('eval_loss', 0.0)
                    })

        training_args = Seq2SeqTrainingArguments(
            output_dir=output_dir,
            per_device_train_batch_size=batch,
            per_device_eval_batch_size=batch,
            predict_with_generate=True,
            evaluation_strategy='epoch',
            save_strategy='epoch',
            num_train_epochs=epochs,
            learning_rate=lr,
            warmup_steps=100,
            logging_steps=10,
            save_total_limit=3,
            load_best_model_at_end=True,
            metric_for_best_model='cer',
            greater_is_better=False,
            fp16=torch.cuda.is_available(),
            report_to='none'
        )

        trainer = Seq2SeqTrainer(
            model=model, args=training_args,
            train_dataset=WordDataset(train_df),
            eval_dataset=WordDataset(val_df),
            compute_metrics=compute_metrics,
            callbacks=[SocketIOCallback()],
            tokenizer=processor.image_processor
        )

        socketio.emit('training_started', {'epochs': epochs, 'total': len(df)})
        trainer.train()
        trainer.save_model(output_dir)
        processor.save_pretrained(output_dir)

        training_state['running'] = False
        socketio.emit('training_done', {
            'cer': training_state['cer'],
            'output_dir': output_dir
        })

    except Exception as e:
        training_state['running'] = False
        training_state['error'] = str(e)
        socketio.emit('training_error', {'error': str(e)})

@app.route('/')
def index():
    return render_template('train_dashboard.html')

@app.route('/api/start', methods=['POST'])
def start_training():
    if training_state['running']:
        return jsonify({'error': 'Training already running'}), 400
    data = request.get_json()
    thread = threading.Thread(target=run_training, args=(
        data.get('data_dir', 'output/S001'),
        data.get('output_dir', 'models/trocr-arabic'),
        int(data.get('epochs', 20)),
        int(data.get('batch', 8)),
        float(data.get('lr', 5e-5)),
        data.get('base_model', 'microsoft/trocr-base-handwritten')
    ), daemon=True)
    thread.start()
    return jsonify({'ok': True})

@app.route('/api/status')
def status():
    return jsonify(training_state)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=5001)
    args = ap.parse_args()
    print(f"🌐 Training UI: http://{args.host}:{args.port}")
    socketio.run(app, host=args.host, port=args.port, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
