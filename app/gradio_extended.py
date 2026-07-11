"""
Extended Gradio App — Optional Experimental Tabs
==================================================
Extends the official app (gradio_full_hitl.py) with additional
optional tabs. The official app is NOT modified.

Run this file instead of gradio_full_hitl.py to access optional tabs.

Optional tabs (disabled by default, enable via env vars):
  EXTENDED_ALT_ENGINES=1  → محركات بديلة (EasyOCR/TrOCR + PDF support)
  EXTENDED_TRAINER=1      → مدرّب التصحيح (Spell correction trainer)
  EXTENDED_PIPELINE=1     → خط أنابيب OCR (Batch OCR + engine comparison + dictionary)
  EXTENDED_BATCH_CORR=1   → مراجعة مجمّعة (Batch correction UI)
  EXTENDED_DUAL_OCR=1     → تحقق مزدوج OCR (Dual-OCR verification)
  EXTENDED_ALL=1          → Enable all optional tabs

Usage:
  python app/gradio_extended.py                        # Official app only
  EXTENDED_ALT_ENGINES=1 python app/gradio_extended.py # + Alternative engines
  EXTENDED_ALL=1 python app/gradio_extended.py         # All tabs
"""

import importlib
import logging
import os
import sys

import gradio as gr

logger = logging.getLogger(__name__)

# ── Feature Flags ────────────────────────────────────────────────────────────
ENABLE_ALL = os.getenv("EXTENDED_ALL", "0").lower() in ("1", "true", "yes")


def _flag(name: str) -> bool:
    return ENABLE_ALL or os.getenv(name, "0").lower() in ("1", "true", "yes")


ENABLE_ALT_ENGINES = _flag("EXTENDED_ALT_ENGINES")
ENABLE_TRAINER = _flag("EXTENDED_TRAINER")
ENABLE_PIPELINE = _flag("EXTENDED_PIPELINE")
ENABLE_BATCH_CORR = _flag("EXTENDED_BATCH_CORR")
ENABLE_DUAL_OCR = _flag("EXTENDED_DUAL_OCR")

_ACTIVE_TABS = []
if ENABLE_ALT_ENGINES:
    _ACTIVE_TABS.append("محركات بديلة")
if ENABLE_TRAINER:
    _ACTIVE_TABS.append("مدرّب التصحيح")
if ENABLE_PIPELINE:
    _ACTIVE_TABS.append("خط أنابيب OCR")
if ENABLE_BATCH_CORR:
    _ACTIVE_TABS.append("مراجعة مجمّعة")
if ENABLE_DUAL_OCR:
    _ACTIVE_TABS.append("تحقق مزدوج OCR")

if _ACTIVE_TABS:
    logger.info("Extended tabs enabled: %s", ", ".join(_ACTIVE_TABS))
else:
    logger.info("No extended tabs enabled. Set EXTENDED_ALL=1 or individual flags.")


# ════════════════════════════════════════════════════════════════════════════
# Optional Tab: محركات بديلة (Alternative Engines)
# Source: app/hf_app.py — EasyOCR/TrOCR ensemble + PDF processing
# ════════════════════════════════════════════════════════════════════════════

def _build_alt_engines_tab():
    """Build the alternative OCR engines tab (EasyOCR/TrOCR + PDF)."""
    gr.Markdown(
        "### محركات بديلة — EasyOCR / TrOCR / PDF\n"
        "Alternative OCR engines and PDF page-by-page extraction.\n"
        "Source: `app/hf_app.py`"
    )
    gr.HTML(
        '<div style="background:#1a1a2e;border:1px solid #30363d;border-radius:8px;'
        'padding:16px;color:#8b949e;text-align:center">'
        '<p>This tab provides EasyOCR + TrOCR ensemble and PDF OCR.</p>'
        '<p>Enable by importing functions from <code>app.hf_app</code>.</p>'
        '<p>Key functions: <code>_ocr_ensemble()</code>, '
        '<code>process_pdf()</code>, <code>detect_language()</code></p></div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# Optional Tab: مدرّب التصحيح (Correction Trainer)
# Source: packages/file_processor/src/correction_trainer_ui.py
# ════════════════════════════════════════════════════════════════════════════

def _build_trainer_tab():
    """Build the word-level spell correction trainer tab."""
    gr.Markdown(
        "### مدرّب التصحيح التدريجي — Word-by-Word Correction Trainer\n"
        "Upload image → OCR → correct word-by-word → save to DB.\n"
        "Source: `packages/file_processor/src/correction_trainer_ui.py`"
    )
    gr.HTML(
        '<div style="background:#1a1a2e;border:1px solid #30363d;border-radius:8px;'
        'padding:16px;color:#8b949e;text-align:center">'
        '<p>This tab provides word-level correction training with:</p>'
        '<ul style="text-align:left;display:inline-block">'
        '<li>Word cards with confidence, language detection</li>'
        '<li>Spell suggestions from HybridSpellChecker</li>'
        '<li>DB persistence via WordCorrectionDB</li>'
        '<li>Batch undo, export, GitHub sync</li></ul>'
        '<p>Enable by calling <code>build_trainer_tabs(use_gpu)</code> '
        'from <code>packages.file_processor.src.correction_trainer_ui</code>.</p></div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# Optional Tab: خط أنابيب OCR (OCR Pipeline)
# Source: apps/ocr-pipeline/app.py
# ════════════════════════════════════════════════════════════════════════════

def _build_pipeline_tab():
    """Build the batch OCR + engine comparison + dictionary tab."""
    gr.Markdown(
        "### خط أنابيب OCR — Batch Processing, Engine Comparison, Dictionary\n"
        "Source: `apps/ocr-pipeline/app.py`"
    )
    gr.HTML(
        '<div style="background:#1a1a2e;border:1px solid #30363d;border-radius:8px;'
        'padding:16px;color:#8b949e;text-align:center">'
        '<p>5-tab professional pipeline:</p>'
        '<ul style="text-align:left;display:inline-block">'
        '<li>Single OCR (Tesseract/EasyOCR/PaddleOCR/TrOCR/Ensemble)</li>'
        '<li>Batch Processing (ZIP output)</li>'
        '<li>Smart Correction (hybrid spell checker with diff view)</li>'
        '<li>Engine Comparison (side-by-side 5 engines)</li>'
        '<li>Medical Dictionary (search + add terms)</li></ul>'
        '<p>Enable by calling <code>build_app()</code> '
        'from <code>apps.ocr_pipeline.app</code>.</p></div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# Optional Tab: مراجعة مجمّعة (Batch Correction)
# Source: packages/file_processor/modules/ui/batch_correction_ui.py
# ════════════════════════════════════════════════════════════════════════════

def _build_batch_correction_tab():
    """Build the batch correction review tab."""
    gr.Markdown(
        "### مراجعة مجمّعة — Batch Correction UI\n"
        "Review and correct OCR results line by line with image crops.\n"
        "Source: `packages/file_processor/modules/ui/batch_correction_ui.py`"
    )
    gr.HTML(
        '<div style="background:#1a1a2e;border:1px solid #30363d;border-radius:8px;'
        'padding:16px;color:#8b949e;text-align:center">'
        '<p>Interactive line-by-line correction with:</p>'
        '<ul style="text-align:left;display:inline-block">'
        '<li>Load from JSON or BatchMedicalOCR results</li>'
        '<li>Line image crop display</li>'
        '<li>Navigate pages/lines, save & next</li>'
        '<li>Final JSON export</li></ul>'
        '<p>Enable by calling <code>BatchCorrectionUI().build_ui()</code> '
        'from <code>packages.file_processor.modules.ui.batch_correction_ui</code>.</p></div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# Optional Tab: تحقق مزدوج OCR (Dual-OCR Verification)
# Source: packages/file_processor/modules/ui/dual_ocr_interface.py
# ════════════════════════════════════════════════════════════════════════════

def _build_dual_ocr_tab():
    """Build the dual-OCR verification tab."""
    gr.Markdown(
        "### تحقق مزدوج OCR — Dual-OCR Verification System\n"
        "Side-by-side TrOCR vs EasyOCR with critical mismatch detection.\n"
        "Source: `packages/file_processor/modules/ui/dual_ocr_interface.py`"
    )
    gr.HTML(
        '<div style="background:#1a1a2e;border:1px solid #30363d;border-radius:8px;'
        'padding:16px;color:#8b949e;text-align:center">'
        '<p>Dual-engine verification with:</p>'
        '<ul style="text-align:left;display:inline-block">'
        '<li>TrOCR (trained model) vs EasyOCR (external reference)</li>'
        '<li>Line-by-line navigation with diff highlighting</li>'
        '<li>Critical content detection & mismatch alerts</li>'
        '<li>User confirmation/override with audit logging</li></ul>'
        '<p>Enable by calling <code>build_dual_ocr_ui()</code> '
        'from <code>packages.file_processor.modules.ui.dual_ocr_interface</code>.</p></div>'
    )


# ════════════════════════════════════════════════════════════════════════════
# Main Application
# ════════════════════════════════════════════════════════════════════════════

def build_extended_app():
    """Build the extended Gradio application with optional tabs."""

    with gr.Blocks(
        title="Omni Medical OCR — Extended",
        theme=gr.themes.Soft(primary_hue="blue"),
    ) as demo:

        gr.HTML("""
        <div style="background:linear-gradient(135deg,#1E88E5 0%,#1565C0 100%);
                    color:white;padding:16px 24px;border-radius:12px;
                    text-align:center;margin-bottom:12px">
          <h1 style="margin:0">Omni Medical OCR — Extended Edition</h1>
          <p style="margin:4px 0 0;opacity:0.9">
            Official app + optional experimental tabs
            &nbsp;|&nbsp;
            <a href="https://github.com/DrAbdulmalek/omni-medical-suite" style="color:#bbdefb">
              GitHub
            </a>
          </p>
        </div>
        """)

        with gr.Tabs():
            # ── Main Tab: Link to Official App ────────────────────────────
            with gr.Tab("الرئيسية (Main)"):
                gr.Markdown(
                    "## Official App\n\n"
                    "The canonical Gradio HITL interface is at "
                    "`app/gradio_full_hitl.py`. This extended version adds "
                    "optional experimental tabs alongside it.\n\n"
                    "### How to use\n"
                    "1. **Default**: Run `python app/gradio_full_hitl.py` for the "
                    "official production app.\n"
                    "2. **Extended**: Set environment variables to enable optional "
                    "tabs and run this file.\n\n"
                    "### Available optional tabs"
                )
                # Show status of each optional tab
                tabs_info = []
                for name, flag, desc in [
                    ("محركات بديلة", "EXTENDED_ALT_ENGINES",
                     "EasyOCR/TrOCR ensemble + PDF support (from `app/hf_app.py`)"),
                    ("مدرّب التصحيح", "EXTENDED_TRAINER",
                     "Word-level correction trainer (from `packages/file_processor/src/correction_trainer_ui.py`)"),
                    ("خط أنابيب OCR", "EXTENDED_PIPELINE",
                     "Batch OCR + engine comparison + dictionary (from `apps/ocr-pipeline/app.py`)"),
                    ("مراجعة مجمّعة", "EXTENDED_BATCH_CORR",
                     "Batch correction UI (from `packages/file_processor/modules/ui/batch_correction_ui.py`)"),
                    ("تحقق مزدوج OCR", "EXTENDED_DUAL_OCR",
                     "Dual-OCR verification (from `packages/file_processor/modules/ui/dual_ocr_interface.py`)"),
                ]:
                    active = os.getenv(flag, "0").lower() in ("1", "true", "yes") or ENABLE_ALL
                    status = "🟢 ON" if active else "⚪ OFF"
                    tabs_info.append(f"| {name} | `{flag}=1` | {desc} | {status} |")
                gr.Markdown(
                    "| Tab | Env Var | Description | Status |\n"
                    "|-----|---------|-------------|--------|\n"
                    + "\n".join(tabs_info)
                )
                gr.Markdown(
                    "### Quick start with all tabs\n"
                    "```bash\n"
                    "EXTENDED_ALL=1 python app/gradio_extended.py\n"
                    "```"
                )

            # ── Optional Tabs (only added when enabled) ────────────────────
            if ENABLE_ALT_ENGINES:
                with gr.Tab("محركات بديلة"):
                    _build_alt_engines_tab()

            if ENABLE_TRAINER:
                with gr.Tab("مدرّب التصحيح"):
                    _build_trainer_tab()

            if ENABLE_PIPELINE:
                with gr.Tab("خط أنابيب OCR"):
                    _build_pipeline_tab()

            if ENABLE_BATCH_CORR:
                with gr.Tab("مراجعة مجمّعة"):
                    _build_batch_correction_tab()

            if ENABLE_DUAL_OCR:
                with gr.Tab("تحقق مزدوج OCR"):
                    _build_dual_ocr_tab()

    return demo


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    app = build_extended_app()
    app.launch(server_name="0.0.0.0", server_port=7860, show_error=True)