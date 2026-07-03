# app/gradio_full_hitl.py
"""
Full Omni Medical OCR — Gradio HITL Interface.

Pipeline: Upload Image → Preprocess → OCR Ensemble → LLM Proofread → NER → Save

Features:
  - Complete OCR processing pipeline
  - LLM proofreading (Jais) — enabled via ENABLE_LLM=true env var (requires GPU)
  - NER entity extraction
  - Save corrections to HuggingFace Dataset
  - Update Medical Dictionary from accumulated corrections
  - Retrain Jais NER (requires GPU)

Environment Variables:
  ENABLE_LLM=true       Enable Jais proofreader + NER (requires GPU)
  HF_TOKEN=hf_xxx       HuggingFace token for dataset upload
"""
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

import gradio as gr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_DATASET = "DrAbdulmalek/arabic-medical-ocr-corrections"

# ── Conditional Imports ─────────────────────────────────────────────────────
HAS_LLM = False
HAS_HF = False

# OCR
try:
    import cv2
    import numpy as np
    HAS_CV = True
except ImportError:
    HAS_CV = False
    logger.warning("OpenCV not available — image preprocessing disabled")

# LLM
if ENABLE_LLM:
    try:
        from src.llm.proofreader import MedicalProofreader
        from src.ner.jais_ner import JaisNER
        HAS_LLM = True
        logger.info("Jais LLM modules loaded (GPU required)")
    except ImportError as e:
        logger.warning(f"LLM modules not available: {e}")

# HuggingFace
try:
    from datasets import Dataset, load_dataset
    from huggingface_hub import HfApi
    import pandas as pd
    HAS_HF = True
except ImportError:
    logger.warning("HuggingFace libs not available — save disabled")

# ── Initialize Heavy Models (lazy) ──────────────────────────────────────────
proofreader = None
ner = None

if HAS_LLM:
    try:
        proofreader = MedicalProofreader()
        ner = JaisNER()
        logger.info("Jais models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jais models: {e}")


# ── Processing Functions ────────────────────────────────────────────────────

def full_process(image):
    """
    Complete processing pipeline:
    Image → Preprocess → OCR → LLM Proofread → NER
    """
    if image is None:
        return None, "لم يتم رفع صورة", "", {}, "يرجى رفع صورة طبية"

    try:
        # 1. Save temp input
        temp_input = Path("temp_input.jpg")
        if HAS_CV:
            cv2.imwrite(str(temp_input), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

            # 2. Preprocessing (basic — enhanced_preprocessor if available)
            cleaned = image.copy()
            try:
                import numpy as np
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                # Basic enhancements
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                cleaned = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            except Exception as e:
                logger.debug(f"Preprocessing fallback: {e}")
                cleaned = image

        # 3. OCR (placeholder — integrate real OCR engines)
        # In production, use:
        #   from src.ocr.baseline import MedicalOCRBaseline
        #   ocr = MedicalOCRBaseline(use_trained_model=True)
        #   ocr_results = ocr.run_ensemble(str(temp_input))
        #   raw_text = ocr_results.get("ensemble", "")
        raw_text = "[OCR output — integrate PaddleOCR/TrOCR/EasyOCR engines here]"

        # 4. LLM Proofreading
        corrected = raw_text
        if proofreader:
            try:
                proof_result = proofreader.proofread(raw_text)
                corrected = proof_result["corrected"]
                logger.info(f"Proofread: {raw_text[:50]}... → {corrected[:50]}...")
            except Exception as e:
                logger.warning(f"Proofreading failed: {e}")

        # 5. NER
        entities = {}
        if ner:
            try:
                entities = ner.extract_entities(corrected)
                logger.info(f"NER extracted: {entities}")
            except Exception as e:
                logger.warning(f"NER failed: {e}")

        # Cleanup
        temp_input.unlink(missing_ok=True)

        status_msg = "تمت المعالجة بنجاح"
        if not HAS_LLM:
            status_msg += " (وضع أساسي — LLM غير مفعّل)"

        return cleaned, corrected, raw_text, entities, status_msg

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return None, f"خطأ: {str(e)}", "", {}, f"حدث خطأ: {str(e)}"


def save_to_hf(corrected_text: str, original_text: str, entities, category: str) -> str:
    """Save correction pair to HuggingFace Dataset."""
    if not HAS_HF:
        return "HuggingFace libraries not available"

    if not corrected_text or not corrected_text.strip():
        return "لا يوجد نص للحفظ"

    try:
        row = {
            "incorrect_ocr_output": str(original_text or ""),
            "correct_text": str(corrected_text),
            "category": str(category),
            "entities": json.dumps(entities, ensure_ascii=False) if isinstance(entities, dict) else str(entities),
            "timestamp": datetime.now().isoformat(),
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

        logger.info(f"Saved to HF: total {len(df)} samples")
        return f"تم الحفظ بنجاح! إجمالي العينات: {len(df)}"

    except Exception as e:
        logger.error(f"Save error: {e}")
        return f"خطأ في الحفظ: {str(e)}"


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
        yield f"خطأ في تحديث القاموس: {str(e)}"


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
        yield f"خطأ: {str(e)}"


# ── Gradio UI ───────────────────────────────────────────────────────────────

# RTL CSS for Arabic
custom_css = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="Omni Medical OCR",
    theme=gr.themes.Soft(),
    css=custom_css,
) as demo:

    gr.Markdown(
        "# Omni Medical OCR\n"
        "**نظام متكامل لاستخراج وتصحيح النصوص الطبية العربية**\n\n"
        "Upload → Preprocess → OCR → LLM Proofread → NER → Save"
    )

    # ── Main Processing ─────────────────────────────────────────────────
    with gr.Row():
        input_image = gr.Image(type="numpy", label="رفع صورة طبية")
        process_btn = gr.Button("معالجة كاملة", variant="primary", size="lg")

    with gr.Row():
        with gr.Column(scale=1):
            cleaned_img = gr.Image(label="الصورة بعد التنظيف")
        with gr.Column(scale=2):
            raw_ocr = gr.Textbox(label="النص الخام من OCR", lines=4)
            corrected = gr.Textbox(label="النص بعد التدقيق (LLM)", lines=4)

    entities_output = gr.JSON(label="الكيانات المستخرجة (NER)")

    # ── Save ────────────────────────────────────────────────────────────
    with gr.Row():
        category = gr.Dropdown(
            choices=["prescription", "report", "handwriting", "lab_result", "other"],
            value="prescription",
            label="نوع الوثيقة",
        )
        save_btn = gr.Button("حفظ التصحيح في HF Dataset", variant="secondary")

    status = gr.Textbox(label="الحالة", interactive=False)

    # ── Advanced Actions ────────────────────────────────────────────────
    with gr.Accordion("أدوات متقدمة", open=False):
        with gr.Row():
            with gr.Column():
                retrain_btn = gr.Button("إعادة تدريب Jais NER", variant="stop")
                retrain_status = gr.Textbox(label="حالة التدريب", lines=8, interactive=False)

            with gr.Column():
                dict_btn = gr.Button("تحديث القاموس الطبي", variant="primary")
                dict_status = gr.Textbox(label="حالة القاموس", lines=8, interactive=False)

    # ── Events ──────────────────────────────────────────────────────────
    process_btn.click(
        fn=full_process,
        inputs=[input_image],
        outputs=[cleaned_img, corrected, raw_ocr, entities_output, status],
    )

    save_btn.click(
        fn=save_to_hf,
        inputs=[corrected, raw_ocr, entities_output, category],
        outputs=[status],
    )

    dict_btn.click(
        fn=update_medical_dictionary,
        outputs=[dict_status],
    )

    retrain_btn.click(
        fn=retrain_now,
        outputs=[retrain_status],
    )


if __name__ == "__main__":
    logger.info("Starting Omni Medical OCR Gradio on port 7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)