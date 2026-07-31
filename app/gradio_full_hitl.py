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

Business logic is delegated to service modules under ``app/services/``.
This file contains only the UI composition layer and thin orchestration.
"""
import logging
import re
import time

import gradio as gr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Service Imports ─────────────────────────────────────────────────────────
# Note: ``paddle_ocr`` / ``spell_checker`` / ``HAS_TESSERACT`` / ``HAS_PREPROCESSOR``
# / ``proofreader`` / ``ner`` / ``HAS_LLM`` are resolved lazily via PEP 562
# ``__getattr__`` on the service modules — importing them here triggers no
# engine construction. Where they are used inside a function body we now
# call the explicit getters (``get_paddle_ocr()`` etc.) to avoid repeated
# lookups; the module-level imports are kept for backward compatibility.
from app.services.ocr_service import (          # noqa: E402
    _auto_correct_ocr,
    _preprocess_image,
    _run_paddle_ocr,
    _run_tesseract,
)
from app.services.review_service import (        # noqa: E402
    _extract_ner,
    jais_proofread_only,
)
from app.services.hf_dataset_service import (    # noqa: E402
    retrain_now,
    save_to_hf,
    update_medical_dictionary,
)
from app.services.translation_service import (  # noqa: E402
    DEVICE,
    TRANSLATION_MODELS,
    translate_text,
)

# ====================================================================
# منقول من OmniFile_Processor/hf_app.py (اندماج مؤكَّد الجودة — 6 يوليو 2026)
# ملاحظة: correct_text()/pyspellchecker الخاصة بـhf_app.py لم تُنقَل عمداً —
# اختبار فعلي أظهر أنها تُفسد أرقام الجرعات ("5OO"→"TOO")، بينما
# HybridSpellChecker أعلاه يحمي منها عبر _try_digit_fix(). لا داعي لمصحّح
# ثانٍ أضعف بجانب الأقوى.
# ====================================================================
# Translation logic (model cache, MarianMT loader, post-MT correction,
# chunking, translate_text()) was extracted to
# ``app/services/translation_service.py`` in v1.1.0-rc (P0 hardening) so
# this UI file stays focused on orchestration. The names above
# (``DEVICE``, ``TRANSLATION_MODELS``, ``translate_text``) are re-exported
# here for backward compatibility with the rest of this file's UI bindings.


def _normalize_text_metrics(text: str) -> str:
    """تطبيع بسيط للمقارنة (تشكيل + همزات فقط، بلا تحيّز ة/ه)."""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)  # إزالة التشكيل
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
    """حساب CER/WER بين نص مرجعي ونص فعلي — مُختبَرة (مطابقة لـjiwer)."""
    if not reference or not hypothesis:
        return "⚠️ الرجاء إدخال النصين المرجعي والفعلي."

    ref = _normalize_text_metrics(reference)
    hyp = _normalize_text_metrics(hypothesis)
    ref_w = ref.split()
    hyp_w = hyp.split()

    cer_val = _levenshtein(ref, hyp) / max(len(ref), 1)
    wer_val = _levenshtein(ref_w, hyp_w) / max(len(ref_w), 1)

    if cer_val < 0.05:
        grade = "A (ممتاز) ✅"
    elif cer_val < 0.15:
        grade = "B (جيد) 🟢"
    elif cer_val < 0.30:
        grade = "C (متوسط) 🟡"
    else:
        grade = "D (ضعيف) ❌"

    out = "## 📊 نتائج تقييم OCR\n\n"
    out += "| المقياس | القيمة |\n|---|---|\n"
    out += f"| **CER** (معدل خطأ الأحرف) | **{cer_val:.2%}** |\n"
    out += f"| **WER** (معدل خطأ الكلمات) | **{wer_val:.2%}** |\n"
    out += f"| **دقة الأحرف** | **{(1 - cer_val) * 100:.1f}%** |\n"
    out += f"| **التقييم** | **{grade}** |\n\n"
    out += "| تفصيل | القيمة |\n|---|---|\n"
    out += f"| أحرف مرجعية | {len(ref)} |\n"
    out += f"| كلمات مرجعية | {len(ref_w)} |\n"
    out += f"| مسافة تحرير الأحرف | {_levenshtein(ref, hyp)} |\n"
    out += f"| مسافة تحرير الكلمات | {_levenshtein(ref_w, hyp_w)} |\n"

    try:
        import jiwer
        out += "\n### تحقق مستقل عبر jiwer\n"
        out += "| المقياس | القيمة |\n|---|---|\n"
        out += f"| CER | {jiwer.cer(reference, hypothesis):.2%} |\n"
        out += f"| WER | {jiwer.wer(reference, hypothesis):.2%} |\n"
    except ImportError:
        out += "\n> ℹ️ ثبّت `jiwer` للتحقق المستقل."
    except Exception:
        pass

    return out


def full_process(image):
    """
    Complete processing pipeline:
    Image → Preprocess → OCR Ensemble → Spell Check → LLM Proofread → NER
    """
    if image is None:
        return None, "لم يتم رفع صورة", "", {}, "يرجى رفع صورة طبية"

    # Resolve lazy singletons once for the whole call
    from app.services.ocr_service import (
        get_paddle_ocr,
        get_spell_checker,
        has_tesseract,
    )
    from app.services.review_service import get_ner, get_proofreader

    paddle = get_paddle_ocr()
    checker = get_spell_checker()
    tess_ok = has_tesseract()
    proof = get_proofreader()
    ner_inst = get_ner()

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
            engine_info["PaddleOCR"] = f"{len(paddle_details)} سطر"
        if tesseract_text:
            engine_info["Tesseract"] = f"ثقة {tess_conf:.0f}%"

        # 4. Auto-correct OCR artifacts (now also applies spell checker internally)
        corrected, corrections = _auto_correct_ocr(raw_text)

        # 4.5 Spell check info (the checker was already applied inside _auto_correct_ocr
        # since v1.1.0-rc; we keep this block only for the status message).
        spell_info = ""
        if checker is not None:
            spell_info = "SpellChecker: applied via _auto_correct_ocr"

        # 5. LLM Proofreading (optional, GPU required)
        if proof is not None:
            try:
                proof_result = proof.proofread(corrected)
                corrected = proof_result["corrected"]
                logger.info("Proofread applied")
            except Exception as e:
                logger.warning(f"Proofreading failed: {e}")

        # 6. NER
        entities = {}
        if ner_inst is not None:
            try:
                entities = ner_inst.extract_entities(corrected)
            except Exception as e:
                logger.warning(f"LLM NER failed: {e}")
        # Fallback: dictionary-based NER
        if not entities:
            entities = _extract_ner(corrected)

        # Build status
        elapsed = time.time() - t0
        parts = [f"✅ معالجة مسبقة: {' + '.join(prep_steps)}"]

        if not tess_ok and paddle is None:
            parts.append("❌ لا يوجد محرك OCR مثبت — ثبّت pytesseract أو paddleocr")
        elif not raw_text.strip():
            parts.append("⚠️ لم يُستخرَج أي نص (تحقق من جودة الصورة)")

        parts.extend(f"✅ {k}: {v}" for k, v in engine_info.items())
        parts.append(f"✅ تصحيح OCR: {len(corrections)} تعديل")
        if spell_info:
            parts.append(f"✅ {spell_info}")
        parts.append(f"✅ كيانات: {sum(len(v) for v in entities.values())}")
        parts.append(f"⏱️ {elapsed:.1f} ثانية")

        if proof is None and ner_inst is None:
            parts.append("(وضع أساسي — LLM غير مفعّل)")

        return cleaned, corrected, raw_text, entities, "\n".join(parts)

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        return None, f"خطأ: {e!s}", "", {}, f"حدث خطأ: {e!s}"


def copy_to_clipboard(text: str) -> str:
    """Return text for Gradio clipboard copy via browser."""
    return text


# ── Gradio UI ───────────────────────────────────────────────────────────────

# RTL CSS for Arabic + UI
custom_css = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
.jais-banner { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 16px; border-radius: 12px; margin: 8px 0; }
.jais-banner h3 { color: #e2e8f0; margin: 0 0 8px 0; }
.jais-banner p { color: #94a3b8; margin: 0; font-size: 14px; }
.before-after-row { display: flex; gap: 16px; }
.before-after-row > div { flex: 1; }
.comparison-label { font-weight: bold; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 4px; }
.label-before { background: #fee2e2; color: #991b1b; }
.label-after { background: #dcfce7; color: #166534; }
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

    with gr.Row():
        copy_btn = gr.Button("📋 نسخ النص المصحح")
        copy_status = gr.Textbox(label="", interactive=False, max_lines=1)

    entities_output = gr.JSON(label="الكيانات المستخرجة (NER)")

    # ── Jais Proofread Section (prominent) ─────────────────────────────
    with gr.Group(visible=True):
        gr.Markdown(
            "### 🧠 Proofread with Jais LLM\n"
            "استخدم نموذج Jais اللغوي لتصحيح أخطاء OCR تلقائياً. "
            "يتطلب **GPU** و **ENABLE_LLM=true**."
        )
        with gr.Row():
            jais_input = gr.Textbox(
                label="أدخل النص للتدقيق (أو استخدم النص الخام من OCR أعلاه)",
                lines=4,
                placeholder="الصق النص هنا أو شغّل المعالجة الكاملة أولاً...",
            )
            jais_output = gr.Textbox(
                label="النص بعد تدقيق Jais ✨",
                lines=4,
                interactive=False,
            )
        with gr.Row():
            jais_btn = gr.Button(
                "🧠 Proofread with Jais — تدقيق بالذكاء الاصطناعي",
                variant="primary",
                size="lg",
            )
            jais_copy_btn = gr.Button("📋 نسخ النتيجة")
        jais_status = gr.Markdown()

    # ── Before / After Comparison ────────────────────────────────────────
    with gr.Accordion("🔍 Before / After Comparison — مقارنة قبل وبعد", open=False):
        gr.Markdown("قارن النص الخام مع النص المصحح لتقييم جودة التصحيح")
        with gr.Row():
            with gr.Column():
                gr.Markdown('<span class="comparison-label label-before">BEFORE — قبل التصحيح</span>')
                before_text = gr.Textbox(
                    label="النص الخام",
                    lines=6,
                    interactive=False,
                )
            with gr.Column():
                gr.Markdown('<span class="comparison-label label-after">AFTER — بعد التصحيح</span>')
                after_text = gr.Textbox(
                    label="النص المصحح",
                    lines=6,
                    interactive=False,
                )
        compare_btn = gr.Button("🔄 مقارنة (ملء من نتائج المعالجة)", variant="secondary")
        compare_output = gr.Markdown()

    # ── Save ────────────────────────────────────────────────────────────
    with gr.Row():
        category = gr.Dropdown(
            choices=["prescription", "report", "handwriting", "lab_result", "other"],
            value="prescription",
            label="نوع الوثيقة",
        )
        save_btn = gr.Button("💾 حفظ التصحيح في HF Dataset", variant="secondary")

    status = gr.Textbox(label="الحالة", interactive=False)

    # ── Advanced Actions ────────────────────────────────────────────────
    with gr.Accordion("أدوات متقدمة", open=False), gr.Row():
        with gr.Column():
            retrain_btn = gr.Button("إعادة تدريب Jais NER", variant="stop")
            retrain_status = gr.Textbox(label="حالة التدريب", lines=8, interactive=False)

        with gr.Column():
            dict_btn = gr.Button("تحديث القاموس الطبي", variant="primary")
            dict_status = gr.Textbox(label="حالة القاموس", lines=8, interactive=False)

    # ── الترجمة ────────────────────────────────────────────────────────
    with gr.Accordion("🌐 ترجمة النصوص", open=False), gr.Row():
        with gr.Column():
            translate_input = gr.Textbox(label="النص المصدر", lines=6)
            translate_direction = gr.Dropdown(
                choices=list(TRANSLATION_MODELS.keys()),
                value="Arabic → English",
                label="اتجاه الترجمة",
            )
            translate_correct = gr.Checkbox(value=True, label="تصحيح ما بعد الترجمة (للعربية)")
            translate_btn = gr.Button("ترجم", variant="primary")
        with gr.Column():
            translate_output = gr.Textbox(label="النص المترجَم", lines=8, interactive=False)

    # ── حاسبة CER/WER ─────────────────────────────────────────────────
    with gr.Accordion("📊 حاسبة دقة OCR (CER/WER)", open=False), gr.Row():
        with gr.Column():
            metrics_ref = gr.Textbox(label="النص المرجعي (الصحيح)", lines=4)
            metrics_hyp = gr.Textbox(label="نص OCR الفعلي", lines=4)
            metrics_btn = gr.Button("احسب المقاييس", variant="primary")
        with gr.Column():
            metrics_output = gr.Markdown()

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

    copy_btn.click(
        fn=copy_to_clipboard,
        inputs=[corrected],
        outputs=[copy_status],
    )

    jais_btn.click(
        fn=jais_proofread_only,
        inputs=[jais_input],
        outputs=[jais_output],
    )

    jais_copy_btn.click(
        fn=copy_to_clipboard,
        inputs=[jais_output],
        outputs=[jais_status],
    )

    def _fill_comparison(raw: str, corr: str) -> tuple[str, str, str]:
        """Fill before/after textboxes and generate diff summary."""
        before_text_out = raw or "(لا يوجد نص خام)"
        after_text_out = corr or "(لا يوجد نص مصحح)"
        summary = "### ملخص المقارنة\n"
        if raw and corr and raw != corr:
            from rapidfuzz import fuzz
            ratio = fuzz.ratio(raw, corr) / 100.0
            summary += f"- نسبة التطابق: **{ratio:.1%}**\\n"
            summary += f"- عدد الأحرف (قبل): {len(raw)} | (بعد): {len(corr)}\n"
        elif raw and corr and raw == corr:
            summary = "### ✅ النصان متطابقان — لا تغييرات"
        else:
            summary = "### ⚠️ شغّل المعالجة الكاملة أولاً لملء المقارنة"
        return before_text_out, after_text_out, summary

    compare_btn.click(
        fn=_fill_comparison,
        inputs=[raw_ocr, corrected],
        outputs=[before_text, after_text, compare_output],
    )

    dict_btn.click(
        fn=update_medical_dictionary,
        outputs=[dict_status],
    )

    retrain_btn.click(
        fn=retrain_now,
        outputs=[retrain_status],
    )

    translate_btn.click(
        fn=translate_text,
        inputs=[translate_input, translate_direction, translate_correct],
        outputs=[translate_output],
    )

    metrics_btn.click(
        fn=calculate_metrics,
        inputs=[metrics_ref, metrics_hyp],
        outputs=[metrics_output],
    )


if __name__ == "__main__":
    logger.info("Starting Omni Medical OCR Gradio on port 7860")
    demo.launch(server_name="0.0.0.0", server_port=7860)