#!/usr/bin/env python3
"""
Omni Medical OCR Pipeline - Gradio Web Application
====================================================
Professional Arabic medical OCR web interface with 5 tabs:
  1. Single OCR - Upload image/PDF and extract text
  2. Batch Processing - Process multiple files at once
  3. Smart Correction - AI-powered Arabic spell checking
  4. Engine Comparison - Compare multiple OCR engines side-by-side
  5. Medical Dictionary - Browse and manage Arabic medical terms
"""

import sys
import os
import json
import time
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import gradio as gr

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Lazy imports (heavy deps loaded on first use) ───────────────────────────
_pipeline_instance = None
_spell_checker_instance = None


def get_pipeline():
    """Lazy-initialize the OCR pipeline (loads models on first call)."""
    global _pipeline_instance
    if _pipeline_instance is None:
        try:
            from src.core.pipeline import OmniMedicalOCR
            _pipeline_instance = OmniMedicalOCR()
        except Exception as e:
            print(f"[WARNING] Failed to initialize full pipeline: {e}")
            print("[INFO] Running in DEMO mode with limited functionality.")
            _pipeline_instance = "demo"
    return _pipeline_instance


def get_spell_checker():
    """Lazy-initialize the spell checker."""
    global _spell_checker_instance
    if _spell_checker_instance is None:
        try:
            from src.spellcheck.hybrid_spell_checker import HybridSpellChecker
            _spell_checker_instance = HybridSpellChecker()
        except Exception as e:
            print(f"[WARNING] Failed to initialize spell checker: {e}")
            _spell_checker_instance = "demo"
    return _spell_checker_instance


def load_medical_dict() -> dict:
    """Load the Arabic medical dictionary from JSON file."""
    dict_path = PROJECT_ROOT / "data" / "arabic_medical_dict.json"
    if dict_path.exists():
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─── Custom CSS ───────────────────────────────────────────────────────────────
CUSTOM_CSS = """
/* ─── Global ────────────────────────────────────── */
.gradio-container {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    max-width: 1200px !important;
}
.medical-header {
    background: linear-gradient(135deg, #1E88E5 0%, #1565C0 100%);
    color: white;
    padding: 20px 30px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 20px;
}
.medical-header h1 {
    margin: 0;
    font-size: 1.8em;
    font-weight: 700;
}
.medical-header p {
    margin: 5px 0 0 0;
    opacity: 0.9;
    font-size: 0.95em;
}
.confidence-high { color: #2E7D32; font-weight: bold; }
.confidence-medium { color: #F57F17; font-weight: bold; }
.confidence-low { color: #C62828; font-weight: bold; }
.correction-card {
    background: #E3F2FD;
    border: 1px solid #90CAF9;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
}
.correction-old { color: #C62828; text-decoration: line-through; }
.correction-new { color: #2E7D32; font-weight: bold; }
.result-box {
    background: #FAFAFA;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 16px;
    min-height: 150px;
    direction: rtl;
    text-align: right;
    font-size: 1.05em;
    line-height: 1.8;
}
.engine-badge {
    display: inline-block;
    background: #E3F2FD;
    color: #1565C0;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.85em;
    margin: 2px;
}
.tab-nav button {
    font-size: 1em !important;
}
"""

# ─── Tab 1: Single OCR ───────────────────────────────────────────────────────

def process_single_ocr(file, engine_choice, language, auto_correct):
    """
    Process a single image or PDF file with selected OCR engine.
    Returns extracted text, confidence score, and processing info.
    """
    if file is None:
        return "الرجاء رفع ملف أولاً", "", ""

    pipeline = get_pipeline()
    start_time = time.time()

    try:
        if pipeline == "demo":
            # Demo mode - simulate OCR
            result_text = "[وضع العرض التوضيحي]\nتم استلام الملف: " + str(file)
            confidence = 0.75
            engine_used = "Demo Engine"
        else:
            engines_map = {
                "الكل (Ensemble)": None,
                "Tesseract": "tesseract",
                "EasyOCR": "easyocr",
                "PaddleOCR": "paddleocr",
                "TrOCR": "trocr",
            }
            selected_engine = engines_map.get(engine_choice, None)

            # Determine if PDF or image
            file_path = file if isinstance(file, str) else file.name
            if file_path.lower().endswith(".pdf"):
                result = pipeline.process_pdf(file_path)
            else:
                result = pipeline.process_image(file_path)

            result_text = result.text if hasattr(result, "text") else str(result)
            confidence = result.confidence if hasattr(result, "confidence") else 0.0
            engine_used = result.engine_name if hasattr(result, "engine_name") else engine_choice

            # Apply spell correction if enabled
            if auto_correct:
                checker = get_spell_checker()
                if checker != "demo":
                    corrected, conf = checker.correct_with_confidence(result_text)
                    if corrected != result_text:
                        result_text = corrected

        elapsed = time.time() - start_time

        # Format confidence
        if confidence >= 0.8:
            conf_class = "confidence-high"
        elif confidence >= 0.5:
            conf_class = "confidence-medium"
        else:
            conf_class = "confidence-low"

        confidence_html = f'<span class="{conf_class}">{confidence:.1%}</span>'
        info_text = f"المحرك: {engine_used} | الوقت: {elapsed:.2f} ثانية"

        return result_text, confidence_html, info_text

    except Exception as e:
        return f"خطأ في المعالجة: {str(e)}", "", ""


# ─── Tab 2: Batch Processing ────────────────────────────────────────────────

def process_batch_ocr(files, engine_choice, progress=gr.Progress()):
    """
    Process multiple files in batch mode.
    Returns a ZIP file containing all results.
    """
    if not files:
        return None, "الرجاء رفع الملفات أولاً"

    pipeline = get_pipeline()
    results = []

    for i, file in enumerate(progress.tqdm(files, desc="معالجة الملفات")):
        try:
            file_path = file if isinstance(file, str) else file.name
            file_name = Path(file_path).name

            if pipeline == "demo":
                text = f"[Demo] Processed: {file_name}"
                confidence = 0.75
            else:
                if file_path.lower().endswith(".pdf"):
                    result = pipeline.process_pdf(file_path)
                else:
                    result = pipeline.process_image(file_path)
                text = result.text if hasattr(result, "text") else str(result)
                confidence = result.confidence if hasattr(result, "confidence") else 0.0

            results.append({"file": file_name, "text": text, "confidence": confidence})

        except Exception as e:
            results.append({"file": Path(file_path).name, "text": f"Error: {e}", "confidence": 0.0})

    # Create ZIP file
    zip_path = PROJECT_ROOT / "batch_results.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            safe_name = r["file"].replace("/", "_")
            # TXT output
            txt_content = f"File: {r['file']}\nConfidence: {r['confidence']:.1%}\n{'='*50}\n{r['text']}\n"
            zf.writestr(f"results/{safe_name}.txt", txt_content.encode("utf-8"))
            # JSON output
            zf.writestr(f"results/{safe_name}.json", json.dumps(r, ensure_ascii=False, indent=2).encode("utf-8"))

    summary = f"تمت معالجة {len(results)} ملف بنجاح\n"
    summary += f"متوسط الثقة: {sum(r['confidence'] for r in results)/len(results):.1%}"

    return str(zip_path), summary


# ─── Tab 3: Smart Correction ────────────────────────────────────────────────

def run_spell_check(input_text):
    """
    Run the hybrid spell checker on Arabic text.
    Shows original text, corrected text, and a diff view.
    """
    if not input_text or not input_text.strip():
        return "", "", "الرجاء إدخال نص أولاً", ""

    checker = get_spell_checker()

    if checker == "demo":
        return input_text, "[Demo Mode] No corrections available.", "", "0.0%"

    try:
        corrected, confidence = checker.correct_with_confidence(input_text)
        diff_html = _generate_diff_html(input_text, corrected)

        # Count corrections
        changes = sum(1 for a, b in zip(input_text.split(), corrected.split()) if a != b)
        changes = max(changes, abs(len(input_text.split()) - len(corrected.split())))

        summary = f"عدد التصحيحات: {changes} | ثقة التصحيح: {confidence:.1%}"

        return corrected, diff_html, summary, f"{confidence:.1%}"

    except Exception as e:
        return input_text, f"خطأ: {str(e)}", "", ""


def _generate_diff_html(original: str, corrected: str) -> str:
    """Generate a simple word-level diff HTML for Arabic text correction visualization."""
    orig_words = original.split()
    corr_words = corrected.split()

    # Simple alignment: if same length, compare word by word
    # For different lengths, show full replacement
    html_parts = ['<div class="result-box">']

    if len(orig_words) == len(corr_words):
        for ow, cw in zip(orig_words, corr_words):
            if ow == cw:
                html_parts.append(f'<span>{ow}</span> ')
            else:
                html_parts.append(
                    f'<span class="correction-old">{ow}</span> '
                    f'<span class="correction-new">{cw}</span> '
                )
    else:
        html_parts.append(f'<span class="correction-old">{original}</span>')
        html_parts.append('<br><br>')
        html_parts.append(f'<span class="correction-new">{corrected}</span>')

    html_parts.append('</div>')
    return "\n".join(html_parts)


# ─── Tab 4: Engine Comparison ────────────────────────────────────────────────

def compare_engines(file):
    """
    Run multiple OCR engines on the same image and display side-by-side comparison.
    """
    if file is None:
        return "الرجاء رفع ملف أولاً"

    pipeline = get_pipeline()
    file_path = file if isinstance(file, str) else file.name

    if pipeline == "demo":
        return (
            "[Demo] Tesseract result...\n",
            "[Demo] EasyOCR result...\n",
            "[Demo] PaddleOCR result...\n",
            "[Demo] TrOCR result...\n",
            "[Demo] Ensemble result...\n",
        )

    try:
        results = {}
        engines = ["tesseract", "easyocr", "paddleocr", "trocr"]

        for engine_name in engines:
            try:
                result = pipeline.process_image(file_path, engines=[engine_name])
                text = result.text if hasattr(result, "text") else f"[{engine_name}] No result"
                conf = result.confidence if hasattr(result, "confidence") else 0.0
                results[engine_name] = f"[{engine_name}] Confidence: {conf:.1%}\n{'─'*40}\n{text}"
            except Exception:
                results[engine_name] = f"[{engine_name}] Engine not available or error occurred."

        # Ensemble
        try:
            result = pipeline.process_image(file_path)
            text = result.text if hasattr(result, "text") else ""
            conf = result.confidence if hasattr(result, "confidence") else 0.0
            results["ensemble"] = f"[Ensemble] Confidence: {conf:.1%}\n{'─'*40}\n{text}"
        except Exception:
            results["ensemble"] = "[Ensemble] Error occurred."

        return (
            results.get("tesseract", ""),
            results.get("easyocr", ""),
            results.get("paddleocr", ""),
            results.get("trocr", ""),
            results.get("ensemble", ""),
        )

    except Exception as e:
        err = f"خطأ في المقارنة: {str(e)}"
        return err, err, err, err, err


# ─── Tab 5: Medical Dictionary ──────────────────────────────────────────────

def search_dictionary(query):
    """Search the Arabic medical dictionary for matching terms."""
    dictionary = load_medical_dict()
    if not dictionary:
        return "القاموس غير متوفر", []

    if not query:
        # Show all entries (first 50)
        entries = list(dictionary.items())[:50]
        table_data = [[k, v] for k, v in entries]
        header = f"إجمالي المدخلات: {len(dictionary)} (يُعرض أول 50)"
        return header, table_data

    # Filter by query
    matches = {k: v for k, v in dictionary.items() if query.lower() in k.lower()}
    if not matches:
        return f"لم يتم العثور على نتائج لـ: {query}", []

    table_data = [[k, v] for k, v in matches.items()]
    header = f"تم العثور على {len(matches)} نتيجة لـ: {query}"
    return header, table_data


def add_dict_entry(term, correction):
    """Add a new entry to the medical dictionary."""
    if not term or not correction:
        return "الرجاء إدخال المصطلح والتصحيح", "", ""

    dict_path = PROJECT_ROOT / "data" / "arabic_medical_dict.json"
    dictionary = load_medical_dict()
    dictionary[term] = correction

    try:
        with open(dict_path, "w", encoding="utf-8") as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        return f"تمت إضافة: {term} → {correction}", "", ""
    except Exception as e:
        return f"خطأ في الحفظ: {str(e)}", "", ""


# ─── Build Gradio Interface ──────────────────────────────────────────────────

def build_app() -> gr.Blocks:
    """Build and return the complete Gradio application."""

    with gr.Blocks(
        title="Omni Medical OCR",
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="cyan"),
        css=CUSTOM_CSS,
    ) as app:

        # ── Header ──
        gr.HTML("""
        <div class="medical-header">
            <h1>نظام القراءة الضوئية الطبي الشامل</h1>
            <p>Omni Medical OCR Pipeline — Tesseract + EasyOCR + PaddleOCR + TrOCR + Jais Spell Check</p>
        </div>
        """)

        with gr.Tabs():
            # ══════════════════════════════════════════════════════════════════
            # Tab 1: Single OCR
            # ══════════════════════════════════════════════════════════════════
            with gr.Tab("قراءة ضوئية فردية"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### رفع الملف")
                        single_file = gr.File(
                            label="اختر صورة أو PDF",
                            file_types=[".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"],
                        )
                        single_engine = gr.Radio(
                            choices=[
                                "الكل (Ensemble)",
                                "Tesseract",
                                "EasyOCR",
                                "PaddleOCR",
                                "TrOCR",
                            ],
                            value="الكل (Ensemble)",
                            label="محرك OCR",
                        )
                        single_lang = gr.Dropdown(
                            choices=["العربية", "English", "تلقائي"],
                            value="العربية",
                            label="اللغة",
                        )
                        single_autocorrect = gr.Checkbox(
                            label="تصحيح ذكي تلقائي", value=True
                        )
                        single_run = gr.Button("تشغيل OCR", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        gr.Markdown("### النتائج")
                        single_confidence = gr.HTML(label="نسبة الثقة")
                        single_info = gr.Textbox(label="معلومات المعالجة", interactive=False)
                        single_output = gr.Textbox(
                            label="النص المستخرج",
                            lines=15,
                            show_copy_button=True,
                            direction="rtl",
                        )
                        single_download = gr.Button("تحميل كـ TXT")

                single_run.click(
                    fn=process_single_ocr,
                    inputs=[single_file, single_engine, single_lang, single_autocorrect],
                    outputs=[single_output, single_confidence, single_info],
                )

            # ══════════════════════════════════════════════════════════════════
            # Tab 2: Batch Processing
            # ══════════════════════════════════════════════════════════════════
            with gr.Tab("معالجة مجمّعة"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### رفع ملفات متعددة")
                        batch_files = gr.File(
                            label="اختر ملفات (صور/PDF)",
                            file_count="multiple",
                            file_types=[".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".pdf"],
                        )
                        batch_engine = gr.Radio(
                            choices=[
                                "الكل (Ensemble)",
                                "Tesseract",
                                "EasyOCR",
                                "PaddleOCR",
                                "TrOCR",
                            ],
                            value="الكل (Ensemble)",
                            label="محرك OCR",
                        )
                        batch_run = gr.Button("معالجة الكل", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        gr.Markdown("### النتائج")
                        batch_summary = gr.Textbox(label="ملخص المعالجة", interactive=False, lines=3)
                        batch_download = gr.File(label="تحميل النتائج (ZIP)")

                batch_run.click(
                    fn=process_batch_ocr,
                    inputs=[batch_files, batch_engine],
                    outputs=[batch_download, batch_summary],
                )

            # ══════════════════════════════════════════════════════════════════
            # Tab 3: Smart Correction
            # ══════════════════════════════════════════════════════════════════
            with gr.Tab("تصحيح ذكي"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### إدخال النص")
                        correct_input = gr.Textbox(
                            label="أدخل النص العربي المراد تصحيحه",
                            lines=10,
                            direction="rtl",
                            placeholder="الصق النص هنا...",
                        )
                        correct_run = gr.Button("تصحيح", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("### النتيجة المصححة")
                        correct_output = gr.Textbox(
                            label="النص المصحح",
                            lines=10,
                            direction="rtl",
                            show_copy_button=True,
                        )

                gr.Markdown("### عرض التصحيحات")
                correct_diff = gr.HTML(label="الفرق بين الأصلي والمصحح")
                correct_summary = gr.Textbox(label="ملخص التصحيح", interactive=False)
                correct_confidence = gr.Textbox(label="ثقة التصحيح", interactive=False)

                correct_run.click(
                    fn=run_spell_check,
                    inputs=[correct_input],
                    outputs=[correct_output, correct_diff, correct_summary, correct_confidence],
                )

            # ══════════════════════════════════════════════════════════════════
            # Tab 4: Engine Comparison
            # ══════════════════════════════════════════════════════════════════
            with gr.Tab("مقارنة المحركات"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### رفع صورة للمقارنة")
                        compare_file = gr.File(
                            label="اختر صورة واحدة",
                            file_types=[".png", ".jpg", ".jpeg", ".tiff", ".bmp"],
                        )
                        compare_run = gr.Button("مقارنة جميع المحركات", variant="primary", size="lg")

                with gr.Row(equal_height=True):
                    with gr.Column():
                        gr.Markdown("#### Tesseract")
                        compare_tesseract = gr.Textbox(lines=8, show_copy_button=True)
                    with gr.Column():
                        gr.Markdown("#### EasyOCR")
                        compare_easyocr = gr.Textbox(lines=8, show_copy_button=True)
                with gr.Row(equal_height=True):
                    with gr.Column():
                        gr.Markdown("#### PaddleOCR")
                        compare_paddleocr = gr.Textbox(lines=8, show_copy_button=True)
                    with gr.Column():
                        gr.Markdown("#### TrOCR")
                        compare_trocr = gr.Textbox(lines=8, show_copy_button=True)
                gr.Markdown("#### Ensemble (الأفضل)")
                compare_ensemble = gr.Textbox(lines=8, show_copy_button=True, direction="rtl")

                compare_run.click(
                    fn=compare_engines,
                    inputs=[compare_file],
                    outputs=[
                        compare_tesseract, compare_easyocr,
                        compare_paddleocr, compare_trocr, compare_ensemble,
                    ],
                )

            # ══════════════════════════════════════════════════════════════════
            # Tab 5: Medical Dictionary
            # ══════════════════════════════════════════════════════════════════
            with gr.Tab("القاموس الطبي"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### بحث في القاموس")
                        dict_search = gr.Textbox(
                            label="ابحث عن مصطلح...",
                            placeholder="أدخل مصطلح عربي للبحث",
                            direction="rtl",
                        )
                        dict_header = gr.Textbox(label="النتائج", interactive=False)
                        dict_table = gr.Dataframe(
                            headers=["المصطلح", "التصحيح"],
                            label="المدخلات المطابقة",
                            interactive=False,
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### إضافة مدخل جديد")
                        dict_term = gr.Textbox(label="المصطلح", direction="rtl")
                        dict_correction = gr.Textbox(label="التصحيح", direction="rtl")
                        dict_add_btn = gr.Button("إضافة", variant="secondary")
                        dict_add_status = gr.Textbox(label="الحالة", interactive=False)

                dict_search.change(
                    fn=search_dictionary,
                    inputs=[dict_search],
                    outputs=[dict_header, dict_table],
                )
                dict_add_btn.click(
                    fn=add_dict_entry,
                    inputs=[dict_term, dict_correction],
                    outputs=[dict_add_status, dict_term, dict_correction],
                )

        # ── Footer ──
        gr.HTML("""
        <div style="text-align: center; padding: 15px; color: #757575; font-size: 0.85em;">
            Omni Medical OCR Pipeline v0.1.0 &mdash; DrAbdulmalek
            <br>Tesseract &bull; EasyOCR &bull; PaddleOCR &bull; TrOCR &bull; Jais
        </div>
        """)

    return app


# ─── Main Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Omni Medical OCR Pipeline - Gradio Web Application")
    print("=" * 60)
    print()

    # Pre-load dictionary
    dictionary = load_medical_dict()
    print(f"[INFO] Medical dictionary loaded: {len(dictionary)} entries")
    print()

    # Build and launch
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        max_threads=4,
    )