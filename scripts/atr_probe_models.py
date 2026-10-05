#!/usr/bin/env python3
"""ATR probe — محاولة تنزيل حقيقية (سجل أحجام + رخص) ثم تحميل كامل (ATR-F1).

يشغَّل من جذر المستودع:
    HF_HOME=<cache> python scripts/atr_probe_models.py

المخرجات: تقرير JSON (stdout + ملف ATR_REPORT، افتراضي atr_model_probe.json).
الخروج 0 عند نجاح كل الخطوات، 2 عند فشل أي خطوة (مثلاً بلا شبكة) — والمرحلة
تُعلَّم PARTIALLY PROVEN؛ مسار dry_run مغطى بالاختبارات. لا fallback صامت.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CACHE = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
os.environ.setdefault("HF_HOME", CACHE)
REPORT_PATH = Path(os.environ.get("ATR_REPORT", "atr_model_probe.json"))

REPORT = {"probe": "atr-models", "steps": [], "ok": False}


def step(name):
    def deco(fn):
        def run(*a, **k):
            t0 = time.time()
            try:
                out = fn(*a, **k)
                REPORT["steps"].append({"step": name, "ok": True,
                                        "seconds": round(time.time() - t0, 1),
                                        "detail": out})
                print(f"[OK] {name}: {out}")
                return out
            except Exception as exc:
                REPORT["steps"].append({"step": name, "ok": False,
                                        "seconds": round(time.time() - t0, 1),
                                        "error": f"{type(exc).__name__}: {exc}"})
                print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
                raise
        return run
    return deco


@step("arabert_tokenizer")
def probe_arabert_tokenizer():
    from transformers import AutoTokenizer
    from ahw.arabic_trocr import DEFAULT_ARABIC
    tok = AutoTokenizer.from_pretrained(DEFAULT_ARABIC, cache_dir=CACHE)
    return {"vocab_size": len(tok), "cls": tok.cls_token_id,
            "sep": tok.sep_token_id, "pad": tok.pad_token_id}


@step("trocr_image_processor")
def probe_trocr_processor():
    from transformers import ViTImageProcessor
    from ahw.arabic_trocr import DEFAULT_BASE
    ip = ViTImageProcessor.from_pretrained(DEFAULT_BASE, cache_dir=CACHE)
    return {"size": ip.size}


@step("trocr_weights_download")
def probe_trocr_weights():
    from huggingface_hub import snapshot_download
    from ahw.arabic_trocr import DEFAULT_BASE
    path = snapshot_download(DEFAULT_BASE, cache_dir=CACHE,
                             allow_patterns=["*.json", "*.txt", "pytorch_model.bin",
                                             "model.safetensors", "*.model"])
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _d, fs in os.walk(path) for f in fs)
    return {"path": path, "bytes": size, "GB": round(size / 1e9, 2)}


@step("full_load_real")
def probe_full_load():
    from ahw.arabic_trocr import load_model_with_arabic_tokenizer
    model, processor, info = load_model_with_arabic_tokenizer(dry_run=False,
                                                              cache_dir=CACHE)
    import torch
    tok = processor.tokenizer
    img_size = model.config.encoder.image_size
    px = torch.zeros(1, 3, img_size, img_size)
    ids = torch.tensor([[tok.cls_token_id]])
    t0 = time.time()
    with torch.no_grad():
        out = model(pixel_values=px, decoder_input_ids=ids)
    return {"vocab_size": info["vocab_size"],
            "resized_from": info["resized_from"],
            "reinit": info["reinit"],
            "one_step_logits": list(out.logits.shape),
            "one_step_seconds": round(time.time() - t0, 1)}


def main() -> int:
    import torch
    import transformers
    REPORT["versions"] = {"transformers": transformers.__version__,
                          "torch": torch.__version__,
                          "cuda": torch.cuda.is_available(),
                          "python": sys.version.split()[0]}
    try:
        probe_arabert_tokenizer()
        probe_trocr_processor()
        probe_trocr_weights()
        probe_full_load()
        REPORT["ok"] = True
    except Exception:
        pass
    print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    REPORT_PATH.write_text(json.dumps(REPORT, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    return 0 if REPORT["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
