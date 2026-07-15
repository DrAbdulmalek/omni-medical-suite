# app/services/hf_dataset_service.py
"""HuggingFace Dataset Service — Save, upload, and manage HF datasets.

Provides:
  - ``save_to_hf()`` — persist OCR correction pairs to a HuggingFace Dataset
  - ``update_medical_dictionary()`` — auto-expand medical dictionary from
    accumulated corrections (generator for Gradio streaming output)
  - ``retrain_now()`` — regenerate Jais NER dataset and start fine-tuning
    (generator for Gradio streaming output)
"""

import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_DATASET = "DrAbdulmalek/arabic-medical-ocr-corrections"

# ── Conditional Imports ─────────────────────────────────────────────────────
HAS_HF = False
try:
    import pandas as pd
    from datasets import Dataset, load_dataset
    HAS_HF = True
except ImportError:
    logger.warning("HuggingFace libs not available — save disabled")


# ── Public Functions ────────────────────────────────────────────────────────

def save_to_hf(corrected_text: str, original_text: str, entities, category: str) -> str:
    """Save correction pair to HuggingFace Dataset."""
    if not HAS_HF:
        return "❌ مكتبات HuggingFace غير متاحة"

    if not corrected_text or not corrected_text.strip():
        return "⚠️ لا يوجد نص مصحح للحفظ. الرجاء معالجة صورة أولاً."

    try:
        previous_count = 0
        try:
            existing = load_dataset(HF_DATASET, split="train")
            previous_count = len(existing)
        except Exception:
            pass

        # Image hash for deduplication hint
        content_hash = hashlib.md5(
            (str(original_text or "") + str(corrected_text)).encode()
        ).hexdigest()[:12]

        row = {
            "incorrect_ocr_output": str(original_text or ""),
            "correct_text": str(corrected_text),
            "category": str(category),
            "entities": json.dumps(entities, ensure_ascii=False) if isinstance(entities, dict) else str(entities),
            "timestamp": datetime.now().isoformat(),
            "content_hash": content_hash,
        }

        new_row = pd.DataFrame([row])

        # Load existing and append
        try:
            existing = load_dataset(HF_DATASET, split="train").to_pandas()
            df = pd.concat([existing, new_row], ignore_index=True)
        except Exception:
            df = new_row

        # Upload
        new_ds = Dataset.from_pandas(df)
        push_kwargs = {"repo_id": HF_DATASET, "private": False}
        if HF_TOKEN:
            push_kwargs["token"] = HF_TOKEN
        new_ds.push_to_hub(**push_kwargs)

        total = len(df)
        logger.info("Saved to HF: total %d samples (hash=%s)", total, content_hash)
        return (
            f"✅ تم الحفظ بنجاح!\n\n"
            f"📊 التفاصيل:\n"
            f"  • العينات السابقة: {previous_count}\n"
            f"  • الإجمالي بعد الحفظ: {total}\n"
            f"  • بصمة المحتوى: {content_hash}\n"
            f"  • النوع: {category}\n"
            f"  • الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as e:
        logger.error(f"Save error: {e}")
        return f"❌ خطأ في الحفظ: {e!s}"


def update_medical_dictionary():
    """Generator: auto-expand medical dictionary from accumulated corrections."""
    try:
        yield "جاري تحليل التصحيحات من HF Dataset..."
        from src.ocr.build_medical_dict import build_and_expand_dict
        medical_dict = build_and_expand_dict(min_freq=2)
        yield f"تم تحديث القاموس الطبي!\nعدد المصطلحات: {len(medical_dict)}"
        examples = list(medical_dict.keys())[:10]
        yield f"تم التحديث بنجاح!\nالمصطلحات ({len(medical_dict)}):\n" + "\n".join(f"  - {e}" for e in examples)
    except Exception as e:
        logger.error(f"Dict update error: {e}")
        yield f"خطأ في تحديث القاموس: {e!s}"


def retrain_now():
    """Generator: regenerate Jais NER dataset and start fine-tuning."""
    try:
        yield "المرحلة 1/2: جاري إنشاء dataset للتدريب..."

        # 1. Generate prompt dataset
        try:
            from scripts.create_jais_prompt_dataset import generate_jais_dataset
            ds = generate_jais_dataset(output_dir="jais_ner_data")
            yield f"تم إنشاء {len(ds)} عينة\n\nالمرحلة 2/2: جاري التدريب..."
        except Exception as e:
            yield f"خطأ في إنشاء Dataset: {e}"
            return

        # 2. Fine-tuning (subprocess — non-blocking would need Celery in production)
        try:
            result = subprocess.run(
                ["python", "src/ner/fine_tune_jais_ner.py", "--epochs", "2"],
                capture_output=True, text=True, timeout=1800,
            )
            if result.returncode == 0:
                last_lines = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
                yield f"اكتمل التدريب بنجاح!\n\n{last_lines}"
            else:
                yield f"فشل التدريب (code {result.returncode}):\n{result.stderr[-500:]}"
        except subprocess.TimeoutExpired:
            yield "انتهت مهلة التدريب (30 دقيقة)"
        except Exception as e:
            yield f"خطأ في التدريب: {e}"

    except Exception as e:
        logger.error(f"Retrain error: {e}")
        yield f"خطأ: {e!s}"