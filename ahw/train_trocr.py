"""ATR-F3 — نواة التدريب لـ TrOCR العربي (بدون اقتران بالخادم).

يعيش منطق التدريب هنا كي يبقى قابلًا للاختبار headless؛ ``train_server.py``
يمرر دوال بث (callbacks) ولا يستورد هذا الملف flask/socketio.

الوضعان:
    mode="smoke" : epoch واحد على 10 عينات اصطناعية بنموذج dry_run صغير
                   (بلا أي تنزيل أوزان) — لإثبات خط الأنابيب كاملًا.
    mode="full"  : تدريب حقيقي من corrections.xlsx/.csv بأوزان
                   TrOCR+AraBERT (تنزيل ≤ سقف 4GB الموثق في PROGRESS.md).

قواعد البيانات (من مخطط AHW):
    - عمود text          : التصحيح المعتمد
    - عمود crop_path     : مسار القصاصة (يُحل نسبيًا لـ data_dir ثم crops/)
    - عمود source_page   : ضمان عدم تقاطع الصفحات بين train/val/test (80/10/10)

بلا شبكة في وضع smoke إطلاقًا. CER عبر jiwer محليًا (لا مكتبة evaluate).
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# نوع دوال البث: (payload: dict) -> None — يتجاهلها None الافتراضي
ProgressCb = Optional[Callable[[Dict[str, Any]], None]]

TRAIN_RATIO = 0.8
VAL_RATIO = 0.1  # والباقي test
MAX_LABEL_LEN = 32


class TrainingAborted(RuntimeError):
    """أُلغي التدريب تعاونيًا عبر stop_event."""


@dataclass
class TrainConfig:
    data_dir: str = "output/S001"
    output_dir: str = "models/trocr-arabic"
    epochs: int = 1
    batch: int = 2
    lr: float = 5e-5
    base_model: str = "microsoft/trocr-base-handwritten"
    arabic_tokenizer: str = "aubmindlab/bert-base-arabertv02"
    mode: str = "smoke"          # smoke | full
    seed: int = 42
    dry_run_model: bool = True   # full=False → تنزيل أوزان حقيقية
    max_steps: int = -1
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# بيانات
# ---------------------------------------------------------------------------
def _resolve_crop(data_dir: Path, crop_path: str) -> Optional[Path]:
    """يحل مسار القصاصة بعدة محاولات (نسبي/مطلق/داخل crops/)."""
    p = Path(crop_path)
    candidates = [p if p.is_absolute() else data_dir / p,
                  data_dir / "crops" / p.name]
    for c in candidates:
        if c.exists():
            return c
    return None


def load_corrections(data_dir: Path) -> "Any":
    """يقرأ corrections.xlsx أو corrections.csv من مجلد البيانات (DataFrame)."""
    import pandas as pd

    xlsx = data_dir / "corrections.xlsx"
    csv = data_dir / "corrections.csv"
    if xlsx.exists():
        df = pd.read_excel(xlsx)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        raise FileNotFoundError(
            f"لا يوجد corrections.xlsx أو corrections.csv في {data_dir}")
    if "text" not in df.columns or "crop_path" not in df.columns:
        raise ValueError("corrections يجب أن يحوي عمودي text و crop_path")
    df = df[df["text"].notna() & (df["text"].astype(str).str.strip() != "")]
    df["text"] = df["text"].astype(str).str.strip()
    if "source_page" not in df.columns:
        # fallback موثق: اشتقاق الصفحة من اسم القصاصة (…_P##_…) أو من مسارها
        import re

        def _page(row: Any) -> str:
            m = re.search(r"_P(\d+)_", str(row.get("crop_path", "")))
            return f"page-{m.group(1)}" if m else "page-unknown"

        df["source_page"] = df.apply(_page, axis=1)
    return df.reset_index(drop=True)


def split_by_source_page(df: "Any", seed: int = 42
                         ) -> Tuple["Any", "Any", "Any"]:
    """80/10/10 بحيث لا تتقاطع source_page نفسها بين الأقسام."""
    pages = sorted(df["source_page"].astype(str).unique())
    rng = random.Random(seed)
    rng.shuffle(pages)
    n = len(pages)
    n_train = max(1, int(round(n * TRAIN_RATIO)))
    n_val = max(1, int(round(n * VAL_RATIO))) if n >= 3 else 0
    train_pages = set(pages[:n_train])
    val_pages = set(pages[n_train:n_train + n_val])
    test_pages = set(pages[n_train + n_val:])
    # صفحات الاختبار قد تصبح val إن لم يبقَ شيء (مجموعات صغيرة)
    if not test_pages and val_pages and n >= 10:
        test_pages = {val_pages.pop()}
    part = df["source_page"].astype(str)
    train_df = df[part.isin(train_pages)]
    val_df = df[part.isin(val_pages)]
    test_df = df[part.isin(test_pages)]
    if len(val_df) == 0:  # مجموعة صغيرة جدًا: val من train (موثق)
        val_df = train_df.tail(max(1, len(train_df) // 5))
    return (train_df.reset_index(drop=True), val_df.reset_index(drop=True),
            test_df.reset_index(drop=True))


def make_synthetic_samples(n: int = 10, seed: int = 42
                           ) -> List[Dict[str, Any]]:
    """n عينات اصطناعية (صور + تسميات) — صفر PHI، بلا ملفات خارجية."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    words = ["المريض", "ألم", "ضغط", "الدواء", "الجراحة", "العظمية"]
    samples: List[Dict[str, Any]] = []
    for i in range(n):
        arr = rng.integers(200, 256, size=(32, 96, 3), dtype=np.uint8)
        # خطوط عشوائية تحاكي وجود حبر (لا نص حقيقي)
        for _ in range(6):
            x0, y0 = rng.integers(2, 90), rng.integers(4, 28)
            arr[y0:y0 + 2, x0:x0 + int(rng.integers(4, 12))] = 30
        samples.append({
            "image": Image.fromarray(arr),
            "text": words[i % len(words)],
            "source_page": f"synthetic-{i:03d}",
        })
    return samples


class WordCropDataset:
    """Dataset لصور القصاصات + التسميات النصية."""

    def __init__(self, records: List[Dict[str, Any]], processor: Any):
        import torch
        from torch.utils.data import Dataset

        self._torch = torch
        self.records = records
        self.processor = processor
        self.pad_id = processor.tokenizer.pad_token_id
        # تحقق مبكر: كل القصاصات قابلة للحل
        self.missing = [r for r in records if r.get("image") is None
                        and not r.get("image_path")]
        if self.missing:
            raise FileNotFoundError(
                f"{len(self.missing)} قصاصة غير موجودة (أولها: "
                f"{self.missing[0].get('crop_path', '?')})")

        class _DS(Dataset):
            def __init__(self, outer: "WordCropDataset"):
                self.outer = outer

            def __len__(self):
                return len(self.outer.records)

            def __getitem__(self, idx):
                from PIL import Image

                r = self.outer.records[idx]
                img = r.get("image")
                if img is None:
                    img = Image.open(r["image_path"]).convert("RGB")
                pv = self.outer.processor(
                    images=img, return_tensors="pt").pixel_values.squeeze(0)
                enc = self.outer.processor.tokenizer(
                    r["text"], padding="max_length", max_length=MAX_LABEL_LEN,
                    truncation=True, return_tensors="pt")
                labels = enc.input_ids.squeeze(0)
                labels[labels == self.outer.pad_id] = -100
                return {"pixel_values": pv, "labels": labels}

        self.torch_dataset = _DS(self)

    def __len__(self):
        return len(self.records)


def records_from_df(df: "Any", data_dir: Path) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        path = _resolve_crop(data_dir, str(row["crop_path"]))
        if path is None:
            logger.warning("قصاصة مفقودة تُستبعد: %s", row["crop_path"])
            continue
        recs.append({"image": None, "image_path": path,
                     "text": str(row["text"]),
                     "source_page": str(row.get("source_page", "unknown"))})
    return recs


# ---------------------------------------------------------------------------
# callbacks للجسر مع Trainer
# ---------------------------------------------------------------------------
def _make_trainer_callback(progress_cb: ProgressCb, eval_cb: ProgressCb,
                           log_cb: ProgressCb, stop_event: Any):
    from transformers import TrainerCallback

    class BroadcastCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if not logs:
                return
            payload = {"epoch": float(state.epoch or 0.0),
                       "step": int(state.global_step),
                       "max_steps": int(state.max_steps or 0),
                       "loss": float(logs.get("loss", logs.get("eval_loss", 0.0))),
                       "lr": float(logs.get("learning_rate", 0.0) or 0.0)}
            if progress_cb:
                progress_cb(payload)

        def on_evaluate(self, args, state, control, metrics=None, **kwargs):
            if not metrics or not eval_cb:
                return
            eval_cb({"epoch": float(state.epoch or 0.0),
                     "cer": float(metrics.get("eval_cer", -1.0)),
                     "loss": float(metrics.get("eval_loss", 0.0))})

        def on_step_end(self, args, state, control, **kwargs):
            if stop_event is not None and stop_event.is_set():
                if log_cb:
                    log_cb({"message": "إيقاف تعاوني مطلوب — إنهاء التدريب"})
                control.should_training_stop = True

    return BroadcastCallback()


def _compute_metrics_factory(tokenizer: Any):
    import jiwer

    def compute_metrics(pred):
        import numpy as np

        label_ids = np.array(pred.label_ids)
        pred_ids = np.array(pred.predictions)
        label_ids[label_ids == -100] = tokenizer.pad_token_id
        preds = tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        labels = tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        pairs = [(l, p) for l, p in zip(labels, preds) if l.strip()]
        if not pairs:
            return {"cer": 1.0}
        cer = jiwer.cer([l for l, _ in pairs], [p for _, p in pairs])
        return {"cer": float(cer)}

    return compute_metrics


# ---------------------------------------------------------------------------
# نقطة الدخول
# ---------------------------------------------------------------------------
def run_training(cfg: TrainConfig,
                 progress_cb: ProgressCb = None,
                 eval_cb: ProgressCb = None,
                 log_cb: ProgressCb = None,
                 done_cb: ProgressCb = None,
                 stop_event: Any = None) -> Dict[str, Any]:
    """يشغّل التدريب (blocking — الخادم يستدعيه في Thread). يُرجع ملخصًا."""
    import torch
    from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments,
                              VisionEncoderDecoderModel)

    from ahw.arabic_trocr import load_model_with_arabic_tokenizer

    t0 = time.time()

    def _log(msg: str):
        logger.info(msg)
        if log_cb:
            log_cb({"message": msg})

    if cfg.mode not in ("smoke", "full"):
        raise ValueError(f"mode غير معروف: {cfg.mode}")
    torch.manual_seed(cfg.seed)

    data_dir = Path(cfg.data_dir)
    if cfg.output_dir:
        output_dir = Path(cfg.output_dir)
    else:
        import tempfile

        output_dir = Path(tempfile.mkdtemp(prefix="atr-train-"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) النموذج + المعالج
    dry = bool(cfg.dry_run_model) or cfg.mode == "smoke"
    _log(f"تحميل النموذج (dry_run={dry}, mode={cfg.mode})…")
    model, processor, model_info = load_model_with_arabic_tokenizer(
        base=cfg.base_model,
        arabic=cfg.arabic_tokenizer,
        dry_run=dry)
    tokenizer = processor.tokenizer

    # 2) البيانات
    if cfg.mode == "smoke":
        samples = make_synthetic_samples(n=10, seed=cfg.seed)
        train_recs = samples[:8]
        val_recs = samples[8:]
        _log("smoke: 10 عينات اصطناعية (8 train / 2 val) — صفر PHI")
    else:
        if not data_dir.exists():
            raise FileNotFoundError(f"مجلد البيانات غير موجود: {data_dir}")
        df = load_corrections(data_dir)
        train_df, val_df, test_df = split_by_source_page(df, seed=cfg.seed)
        if len(test_df):
            test_df.to_csv(output_dir / "test_split.csv", index=False,
                           encoding="utf-8-sig")
        train_recs = records_from_df(train_df, data_dir)
        val_recs = records_from_df(val_df, data_dir)
        _log(f"full: {len(df)} تصحيحًا → train={len(train_recs)} "
             f"val={len(val_recs)} test={len(test_df)} (split بالصفحات)")
        if not train_recs:
            raise ValueError("لا قصاصات قابلة للحل في train split")

    train_ds = WordCropDataset(train_recs, processor)
    val_ds = WordCropDataset(val_recs, processor) if val_recs else None

    # 3) Trainer
    gen = (cfg.mode == "full") and not dry
    args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        per_device_train_batch_size=cfg.batch,
        per_device_eval_batch_size=cfg.batch,
        num_train_epochs=cfg.epochs,
        max_steps=cfg.max_steps,
        learning_rate=cfg.lr,
        warmup_steps=0 if cfg.mode == "smoke" else min(100, cfg.epochs * 10),
        logging_steps=1 if cfg.mode == "smoke" else 10,
        eval_strategy="epoch" if val_ds is not None else "no",
        save_strategy="no" if cfg.mode == "smoke" else "epoch",
        save_total_limit=2,
        predict_with_generate=gen,
        prediction_loss_only=not gen,
        report_to="none",
        use_cpu=not torch.cuda.is_available(),
        fp16=bool(torch.cuda.is_available()),
        dataloader_num_workers=0,
        seed=cfg.seed,
    )
    trainer = Seq2SeqTrainer(
        model=model, args=args,
        train_dataset=train_ds.torch_dataset,
        eval_dataset=val_ds.torch_dataset if val_ds is not None else None,
        compute_metrics=_compute_metrics_factory(tokenizer) if gen else None,
        callbacks=[_make_trainer_callback(progress_cb, eval_cb, log_cb,
                                          stop_event)],
        processing_class=processor.image_processor,
    )

    if progress_cb:
        progress_cb({"event": "started", "epochs": cfg.epochs,
                     "total_samples": len(train_recs), "mode": cfg.mode,
                     "model_info": model_info})
    _log("بدء التدريب…")
    train_result = trainer.train()
    final_loss = float(train_result.training_loss)

    cer: Optional[float] = None
    if gen and val_ds is not None:
        metrics = trainer.evaluate()
        cer = float(metrics.get("eval_cer", -1.0))
        if eval_cb:
            eval_cb({"epoch": cfg.epochs, "cer": cer,
                     "loss": float(metrics.get("eval_loss", 0.0))})

    if stop_event is not None and stop_event.is_set():
        raise TrainingAborted("أوقف المستخدم التدريب")

    # 4) حفظ النموذج (full فقط — smoke لا يلوث models/)
    saved_to = None
    if cfg.mode == "full":
        trainer.save_model(str(output_dir))
        processor.save_pretrained(str(output_dir))
        saved_to = str(output_dir)

    summary = {"mode": cfg.mode, "final_loss": final_loss, "cer": cer,
               "train_samples": len(train_recs), "val_samples": len(val_recs),
               "epochs": cfg.epochs, "output_dir": saved_to,
               "model_info": model_info,
               "duration_s": round(time.time() - t0, 2)}
    _log(f"اكتمل: loss={final_loss:.4f} cer={cer} "
         f"({summary['duration_s']}s)")
    if done_cb:
        done_cb(summary)
    return summary
