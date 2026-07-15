# hf-space/app.py — Omni Medical OCR (HF Spaces Optimized)
"""
Omni Medical OCR — Gradio HITL Interface for HuggingFace Spaces.

Pipeline: Upload Image → Preprocess → OCR Ensemble → Spell Check → NER

Features:
  - PaddleOCR + Tesseract ensemble (CPU-optimized)
  - Medical spell checking with protected terms
  - Dictionary-based NER (medications, diseases, symptoms, dosages)
  - CER/WER accuracy calculator
  - Translation (Arabic ↔ English ↔ German, lazy-loaded)
  - Save corrections to HuggingFace Dataset

Optimizations for HF Spaces:
  - No GPU required — runs on free CPU tier
  - Translation models lazy-loaded on first use
  - PaddleOCR models pre-cached in Docker image
  - Minimal memory footprint

Environment Variables:
  ENABLE_LLM=true       Enable Jais proofreader (requires GPU, NOT for free tier)
  HF_TOKEN=hf_xxx       HuggingFace token for dataset upload
"""
import json
import logging
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np
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

if ENABLE_LLM:
    try:
        from src.llm.proofreader import MedicalProofreader
        from src.ner.jais_ner import JaisNER
        HAS_LLM = True
        logger.info("Jais LLM modules loaded (GPU required)")
    except ImportError as e:
        logger.warning(f"LLM modules not available: {e}")

try:
    from datasets import Dataset, load_dataset
    from huggingface_hub import HfApi
    HAS_HF = True
except ImportError:
    logger.warning("HuggingFace libs not available — save disabled")

# ── Initialize OCR Engines ──────────────────────────────────────────────────
logger.info("Initializing OCR engines...")

# ImagePreprocessor
image_preprocessor = None
HAS_PREPROCESSOR = False
try:
    from packages.vision.image_preprocessor import ImagePreprocessor
    image_preprocessor = ImagePreprocessor(
        apply_clahe=True, apply_denoise=True,
        apply_deskew=True, deskew_angle_threshold=5.0,
        apply_binarize=True,
    )
    HAS_PREPROCESSOR = True
    logger.info("ImagePreprocessor loaded (CLAHE+denoise+deskew+binarize)")
except Exception as e:
    logger.warning(f"ImagePreprocessor not available, will use fallback: {e}")

# PaddleOCR (primary — best Arabic support)
paddle_ocr = None
try:
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(
        use_angle_cls=True, lang="ar", show_log=False,
        device="cpu", det_db_thresh=0.3, det_db_box_thresh=0.5,
        det_db_unclip_ratio=1.6, max_text_length=800, use_mp=True,
    )
    logger.info("PaddleOCR initialized successfully")
except Exception as e:
    logger.error(f"PaddleOCR init failed: {e}")

# Tesseract (secondary)
HAS_TESSERACT = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
    logger.info("Tesseract initialized successfully")
except Exception as e:
    logger.warning(f"Tesseract not available: {e}")

# Spell Checker
spell_checker = None
try:
    from packages.core.spell_checker import HybridSpellChecker
    spell_checker = HybridSpellChecker()
    logger.info("HybridSpellChecker loaded")
except Exception as e:
    logger.warning(f"Spell checker not available: {e}")

# Medical dictionary for NER
MEDICAL_TERMS = {
    # Medications
    "باراسيتامول": "medication", "ايبوبروفين": "medication",
    "اموكسيسيلين": "medication", "ازيثرومايسين": "medication",
    "سيفالكسين": "medication", "ميترونيدازول": "medication",
    "اوجمنتين": "medication", "اوميبرازول": "medication",
    "ديكلوفيناك": "medication", "نابروكسين": "medication",
    "ترامادول": "medication", "كوديين": "medication",
    "سالبوتامول": "medication", "لوراتادين": "medication",
    "سيتيريزين": "medication", "رانيتيدين": "medication",
    "فاموتيدين": "medication", "انالجين": "medication",
    "بنادول": "medication", "ادفيل": "medication",
    "كاتافلام": "medication", "فولتارين": "medication",
    "مونتيلوكاست": "medication", "سودوافيدرين": "medication",
    "سيفترياكسون": "medication", "دوكسيسيكلين": "medication",
    "سيبروفلوكساسين": "medication", "لوفلوكساسين": "medication",
    "ميفيناميك": "medication", "انديسيترون": "medication",
    # Diseases
    "سكري": "disease", "ضغط": "disease", "ربو": "disease",
    "التهاب": "disease", "حساسية": "disease", "قرحة": "disease",
    "التهاب رئوي": "disease", "التهاب شعبي": "disease",
    "ارتفاع ضغط": "disease", "سرطان": "disease",
    # Symptoms
    "صداع": "symptom", "حمى": "symptom", "سعال": "symptom",
    "الم": "symptom", "غثيان": "symptom", "اقياء": "symptom",
    "اسهال": "symptom", "دوار": "symptom", "تعب": "symptom",
    "ضيق تنفس": "symptom", "الم بطن": "symptom",
}

# OCR common misrecognition corrections
OCR_CORRECTIONS = {
    "باراسيتبمول": "باراسيتامول", "ايبوروفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين", "اموكسيسلين": "اموكسيسيلين",
    "ازيثروميسين": "ازيثرومايسين", "ميتروندازول": "ميترونيدازول",
    "ديكلوفيناك ": "ديكلوفيناك", "اوجمينتين": "اوجمنتين",
    "اوميبرازول ": "اوميبرازول", "سيليبريكس ": "سيليبريكس",
    "ترامادول ": "ترامادول", "كاتافلام ": "كاتافلام",
    "نوفافين ": "نوفافين", "فلاميكس ": "فلاميكس",
    "بنادول ": "بنادول", "ادفيل ": "ادفيل",
}

# ── Lazy-loaded modules ─────────────────────────────────────────────────────
proofreader = None
ner = None

if HAS_LLM:
    try:
        proofreader = MedicalProofreader()
        ner = JaisNER()
        logger.info("Jais models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jais models: {e}")

# Translation (lazy-loaded on first use to save memory)
_translator_cache: Dict[str, object] = {}
DEVICE = "cpu"
TRANSLATION_MODELS = {
    "Arabic → English": "Helsinki-NLP/opus-mt-ar-en",
    "English → Arabic": "Helsinki-NLP/opus-mt-en-ar",
    "Arabic → German": "Helsinki-NLP/opus-mt-ar-de",
    "German → Arabic": "Helsinki-NLP/opus-mt-de-ar",
}


# ── Processing Functions ────────────────────────────────────────────────────

def _preprocess_image(image: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    """Preprocess image: CLAHE + denoise + deskew + binarize."""
    steps = []
    cleaned = None

    if HAS_PREPROCESSOR and image_preprocessor is not None:
        try:
            cleaned = image_preprocessor.preprocess(image, return_numpy=True)
            if cleaned.ndim == 2:
                cleaned = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
            steps.append("ImagePreprocessor (CLAHE+denoise+deskew+binarize)")
        except Exception as e:
            logger.warning(f"ImagePreprocessor failed, falling back: {e}")
            cleaned = None

    if cleaned is None:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cleaned = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            steps.append("Fallback CLAHE+Otsu")
        except Exception as e:
            logger.debug(f"Basic preprocessing failed: {e}")
            cleaned = image
            steps.append("No preprocessing")

    return cleaned, steps


def _run_paddle_ocr(image: np.ndarray) -> Tuple[str, List[Dict]]:
    """Run PaddleOCR. Returns (full_text, line_details)."""
    if paddle_ocr is None:
        return "", []
    try:
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        result = paddle_ocr.ocr(img_bgr, cls=True)
        lines, details = [], []
        if result and result[0]:
            for idx, line in enumerate(result[0]):
                text = line[1][0].strip()
                conf = line[1][1]
                if text:
                    lines.append(text)
                    details.append({"line": idx + 1, "text": text,
                                    "confidence": round(float(conf), 4)})
        return "\n".join(lines), details
    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return "", []


def _run_tesseract(image: np.ndarray) -> Tuple[str, float]:
    """Run Tesseract. Returns (text, avg_confidence)."""
    if not HAS_TESSERACT:
        return "", 0.0
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray, lang="ara+eng", config="--psm 6")
        try:
            data = pytesseract.image_to_data(gray, lang="ara+eng", output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
        except Exception:
            avg_conf = 0.0
        return text.strip(), round(avg_conf, 2)
    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return "", 0.0


def _auto_correct_ocr(text: str) -> Tuple[str, List[Dict]]:
    """Apply OCR corrections + spell checker. Returns (corrected, changes)."""
    changes = []
    corrected = text
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            count = corrected.count(wrong)
            corrected = corrected.replace(wrong, right)
            changes.append({"type": "ocr_fix", "from": wrong, "to": right, "count": count})
    corrected = re.sub(r'[ \t]+', ' ', corrected)
    corrected = re.sub(r'\n{3,}', '\n\n', corrected).strip()
    return corrected, changes


def _extract_ner(text: str) -> Dict[str, List[str]]:
    """Extract medical entities by dictionary matching."""
    entities = {"medications": [], "diseases": [], "symptoms": [], "dosages": []}
    for term, category in MEDICAL_TERMS.items():
        if term in text:
            entities.setdefault(f"{category}s", []).append(term)
    dosage_re = r'(\d+(?:\.\d+)?)\s*(?:ملغ|mg|مغ|مللي|مل|حبة|كبسولة|قرص|امبول)'
    for m in re.findall(dosage_re, text):
        entities["dosages"].append(m)
    return {k: list(set(v)) for k, v in entities.items() if v}


def _format_ner_table(entities: Dict) -> str:
    """Format NER results as a readable Markdown table."""
    if not entities:
        return "لم يتم اكتشاف كيانات طبية"
    lines = ["## الكيانات المستخرجة\n", "| النوع | الكيانات |", "|-------|---------|"]
    labels = {"medications": "أدوية", "diseases": "أمراض", "symptoms": "أعراض", "dosages": "جرعات"}
    for key, items in entities.items():
        if items:
            label = labels.get(key, key)
            lines.append(f"| {label} | {', '.join(items)} |")
    return "\n".join(lines)


# ── Main Pipeline ───────────────────────────────────────────────────────────

def full_process(image) -> Tuple:
    """
    Complete processing pipeline:
    Image → Preprocess → OCR Ensemble → Spell Check → LLM Proofread → NER
    """
    if image is None:
        return None, None, "لم يتم رفع صورة", "", "", "يرجى رفع صورة طبية"

    t0 = time.time()
    try:
        # 1. Preprocessing
        cleaned, prep_steps = _preprocess_image(image)

        # 2. OCR — run all available engines
        paddle_text, paddle_details = _run_paddle_ocr(cleaned)
        tesseract_text, tess_conf = _run_tesseract(cleaned)

        # 3. Ensemble: PaddleOCR primary, Tesseract supplement
        raw_text = paddle_text if (paddle_text and len(paddle_text.strip()) > 5) else tesseract_text
        if not raw_text.strip():
            raw_text = paddle_text or tesseract_text or "[لم يتم اكتشاف نص]"

        engine_info = {}
        if paddle_text:
            engine_info["PaddleOCR"] = f"{len(paddle_details)} lines"
        if tesseract_text:
            engine_info["Tesseract"] = f"confidence {tess_conf:.0f}%"

        # 4. Auto-correct OCR artifacts
        corrected, corrections = _auto_correct_ocr(raw_text)

        # 4.5 Spell check
        spell_info = ""
        if spell_checker:
            try:
                before_spell = corrected
                corrected = spell_checker.correct_text(corrected)
                if before_spell != corrected:
                    spell_info = f"SpellChecker: modifications applied"
            except Exception as e:
                logger.warning(f"Spell check failed: {e}")

        # 5. LLM Proofreading (optional, GPU required)
        if proofreader:
            try:
                proof_result = proofreader.proofread(corrected)
                corrected = proof_result["corrected"]
                logger.info("Proofread applied")
            except Exception as e:
                logger.warning(f"Proofreading failed: {e}")

        # 6. NER
        entities = {}
        if ner:
            try:
                entities = ner.extract_entities(corrected)
            except Exception as e:
                logger.warning(f"LLM NER failed: {e}")
        if not entities:
            entities = _extract_ner(corrected)

        # Build status
        elapsed = time.time() - t0
        parts = [f"Preprocess: {' + '.join(prep_steps)}"]

        if not HAS_TESSERACT and paddle_ocr is None:
            parts.append("No OCR engine available")
        elif not raw_text.strip():
            parts.append("No text detected (check image quality)")

        parts.extend(f"{k}: {v}" for k, v in engine_info.items())
        parts.append(f"OCR corrections: {len(corrections)}")
        if spell_info:
            parts.append(spell_info)
        parts.append(f"Entities found: {sum(len(v) for v in entities.values())}")
        parts.append(f"Time: {elapsed:.1f}s")

        if not HAS_LLM:
            parts.append("(Basic mode — LLM not enabled)")

        ner_markdown = _format_ner_table(entities)

        return cleaned, image, corrected, raw_text, ner_markdown, "\n".join(parts)

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return None, None, f"Error: {str(e)}", "", "", f"An error occurred: {str(e)}"


# ── Save to HuggingFace ────────────────────────────────────────────────────

def save_to_hf(corrected_text: str, original_text: str, ner_text: str, category: str) -> str:
    """Save correction pair to HuggingFace Dataset."""
    if not HAS_HF:
        return "HuggingFace libraries not available. Install datasets and huggingface_hub."

    if not corrected_text or not corrected_text.strip():
        return "No text to save"

    try:
        row = {
            "incorrect_ocr_output": str(original_text or ""),
            "correct_text": str(corrected_text),
            "category": str(category),
            "ner_entities": ner_text,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            existing = load_dataset(HF_DATASET, split="train")
            existing_dict = {k: existing[k] + [v] for k, v in row.items()}
            new_ds = Dataset.from_dict(existing_dict)
        except Exception:
            new_ds = Dataset.from_dict({k: [v] for k, v in row.items()})

        push_kwargs = {"repo_id": HF_DATASET, "private": False}
        if HF_TOKEN:
            push_kwargs["token"] = HF_TOKEN
        new_ds.push_to_hub(**push_kwargs)

        total = len(new_ds)
        logger.info(f"Saved to HF: {total} total samples")
        return f"Saved successfully! Total samples: {total}"
    except Exception as e:
        logger.error(f"Save error: {e}")
        return f"Save error: {str(e)}"


# ── Translation (lazy-loaded) ─────────────────────────────────────────────

def _load_translator(model_name: str):
    """Lazy-load MarianMT translator on first use."""
    cache_key = f"translator_{model_name}"
    if cache_key in _translator_cache:
        return _translator_cache[cache_key]
    try:
        from transformers import MarianMTModel, MarianTokenizer
        logger.info(f"Loading translation model: {model_name} (this may take a moment...)")
        tok = MarianTokenizer.from_pretrained(model_name)
        mdl = MarianMTModel.from_pretrained(model_name)
        _translator_cache[cache_key] = (tok, mdl)
        return tok, mdl
    except Exception as e:
        logger.error(f"Failed to load translator {model_name}: {e}")
        return None, None


def translate_text(text: str, direction: str, progress=gr.Progress()) -> str:
    """Translate text between Arabic, English, and German (lazy-loaded)."""
    if not text or not text.strip():
        return "Please enter text to translate."

    model_name = TRANSLATION_MODELS.get(direction)
    if not model_name:
        return f"Unsupported direction: {direction}"

    progress(0.2, desc=f"Loading model ({direction})...")
    tok, mdl = _load_translator(model_name)
    if tok is None or mdl is None:
        return f"Failed to load translation model: {model_name}"

    try:
        import torch
        chunks = []
        cur = ""
        for para in re.split(r"\n\s*\n", text.strip()):
            if len(cur) + len(para) + 2 <= 400:
                cur += ("\n\n" if cur else "") + para
            else:
                if cur:
                    chunks.append(cur)
                cur = para
        if cur:
            chunks.append(cur)

        parts = []
        for i, chunk in enumerate(chunks):
            progress(0.3 + 0.7 * ((i + 1) / len(chunks)), desc=f"Translating part {i+1}/{len(chunks)}...")
            inputs = tok(chunk, return_tensors="pt", truncation=True, max_length=512, padding=True)
            with torch.no_grad():
                gen = mdl.generate(**inputs, max_length=512)
            parts.append(tok.decode(gen[0], skip_special_tokens=True))

        translated = "\n\n".join(parts)
        return (
            f"{translated}\n\n---\n"
            f"**Model**: `{model_name}` | "
            f"**Characters**: {len(text)} -> {len(translated)}"
        )
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"Translation failed: {e}"


# ── CER/WER Calculator ────────────────────────────────────────────────────

def _normalize_text_metrics(text: str) -> str:
    """Normalize text for comparison (remove diacritics, normalize hamza)."""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'[إأآا]', 'ا', text)
    return text.strip()


def _levenshtein(s1, s2) -> int:
    m, n = len(s1), len(s2)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def calculate_metrics(reference: str, hypothesis: str) -> str:
    """Calculate CER/WER between reference and hypothesis text."""
    if not reference or not hypothesis:
        return "Please enter both reference and hypothesis texts."

    ref = _normalize_text_metrics(reference)
    hyp = _normalize_text_metrics(hypothesis)
    ref_w = ref.split()
    hyp_w = hyp.split()

    cer_val = _levenshtein(ref, hyp) / max(len(ref), 1)
    wer_val = _levenshtein(ref_w, hyp_w) / max(len(ref_w), 1)

    if cer_val < 0.05:
        grade = "A (Excellent)"
    elif cer_val < 0.15:
        grade = "B (Good)"
    elif cer_val < 0.30:
        grade = "C (Fair)"
    else:
        grade = "D (Poor)"

    out = "## OCR Accuracy Results\n\n"
    out += "| Metric | Value |\n|---|---|\n"
    out += f"| **CER** (Character Error Rate) | **{cer_val:.2%}** |\n"
    out += f"| **WER** (Word Error Rate) | **{wer_val:.2%}** |\n"
    out += f"| **Character Accuracy** | **{(1 - cer_val) * 100:.1f}%** |\n"
    out += f"| **Grade** | **{grade}** |\n\n"
    out += "| Detail | Value |\n|---|---|\n"
    out += f"| Reference chars | {len(ref)} |\n"
    out += f"| Reference words | {len(ref_w)} |\n"
    out += f"| Edit distance (chars) | {_levenshtein(ref, hyp)} |\n"
    out += f"| Edit distance (words) | {_levenshtein(ref_w, hyp_w)} |\n"

    try:
        import jiwer
        out += "\n### Independent verification (jiwer)\n"
        out += "| Metric | Value |\n|---|---|\n"
        out += f"| CER | {jiwer.cer(reference, hypothesis):.2%} |\n"
        out += f"| WER | {jiwer.wer(reference, hypothesis):.2%} |\n"
    except ImportError:
        pass

    return out


# ── Gradio UI ───────────────────────────────────────────────────────────────

custom_css = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
.main-title { text-align: center; margin-bottom: 1rem; }
"""

with gr.Blocks(
    title="Omni Medical OCR — Arabic Medical Text Extraction",
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="green"),
    css=custom_css,
) as demo:

    gr.Markdown(
        "# Omni Medical OCR\n"
        "**Arabic Medical Document Intelligence System**\n\n"
        "Upload → Preprocess → OCR → Spell Check → NER"
    )

    with gr.Tabs():
        # ── Tab 1: OCR Processing ──────────────────────────────────────
        with gr.Tab("OCR Processing"):
            with gr.Row():
                input_image = gr.Image(type="numpy", label="Upload Medical Image")
                with gr.Column():
                    process_btn = gr.Button("Full Processing", variant="primary", size="lg")
                    status = gr.Textbox(label="Status", interactive=False, lines=3)

            with gr.Row():
                with gr.Column(scale=1):
                    cleaned_img = gr.Image(label="After Preprocessing")
                    before_img = gr.Image(label="Original Image")
                with gr.Column(scale=2):
                    raw_ocr = gr.Textbox(label="Raw OCR Output", lines=4)
                    corrected = gr.Textbox(label="Corrected Text", lines=6)

            ner_output = gr.Markdown(label="Extracted Entities (NER)")

            with gr.Row():
                category = gr.Dropdown(
                    choices=["prescription", "report", "handwriting", "lab_result", "other"],
                    value="prescription", label="Document Type",
                )
                save_btn = gr.Button("Save Correction to HF Dataset", variant="secondary")
                save_status = gr.Textbox(label="Save Status", interactive=False)

            process_btn.click(
                fn=full_process,
                inputs=[input_image],
                outputs=[cleaned_img, before_img, corrected, raw_ocr, ner_output, status],
            )
            save_btn.click(
                fn=save_to_hf,
                inputs=[corrected, raw_ocr, ner_output, category],
                outputs=[save_status],
            )

        # ── Tab 2: Translation ─────────────────────────────────────────
        with gr.Tab("Translation"):
            gr.Markdown("### Translate medical text (models loaded on first use)")
            with gr.Row():
                with gr.Column():
                    translate_input = gr.Textbox(label="Source Text", lines=6, placeholder="Enter Arabic, English, or German text...")
                    translate_direction = gr.Dropdown(
                        choices=list(TRANSLATION_MODELS.keys()),
                        value="Arabic → English",
                        label="Direction",
                    )
                    translate_btn = gr.Button("Translate", variant="primary")
                with gr.Column():
                    translate_output = gr.Textbox(label="Translation", lines=8, interactive=False)

            translate_btn.click(
                fn=translate_text,
                inputs=[translate_input, translate_direction],
                outputs=[translate_output],
            )

        # ── Tab 3: CER/WER Calculator ─────────────────────────────────
        with gr.Tab("Accuracy Metrics"):
            gr.Markdown("### Calculate OCR accuracy (CER/WER)")
            with gr.Row():
                with gr.Column():
                    metrics_ref = gr.Textbox(label="Reference Text (correct)", lines=4, placeholder="Enter the correct text...")
                    metrics_hyp = gr.Textbox(label="OCR Output (hypothesis)", lines=4, placeholder="Enter the OCR output...")
                    metrics_btn = gr.Button("Calculate", variant="primary")
                with gr.Column():
                    metrics_output = gr.Markdown()

            metrics_btn.click(
                fn=calculate_metrics,
                inputs=[metrics_ref, metrics_hyp],
                outputs=[metrics_output],
            )


if __name__ == "__main__":
    logger.info("Starting Omni Medical OCR on port 7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)