"""Advanced Gradio review app for Omni Medical Suite.

Tabs:
- Compare: raw vs preprocessed OCR comparisons
- Search: Qdrant-backed semantic search with local fallback
- Review: RTL cleanup, field extraction, and routing recommendations
"""

from __future__ import annotations

import json
import os
from typing import Any

import gradio as gr

from omni_medical_suite.preprocessing.compare_raw_vs_printed import compare_raw_vs_printed_text
from packages.core.engine_router import EngineRouter
from src.ocr.deduplication import QdrantMedicalSearch
from src.ocr.field_extractor import ArabicMedicalFieldExtractor
from src.ocr.rtl_utils import ArabicRTLFixer

extractor = ArabicMedicalFieldExtractor()
rtl_fixer = ArabicRTLFixer()
router = EngineRouter(profile=os.getenv("ENGINE_PROFILE", "balanced"), use_gpu=os.getenv("USE_GPU", "false").lower() == "true")
search_service = QdrantMedicalSearch(
    qdrant_url=os.getenv("QDRANT_URL"),
    collection_name=os.getenv("QDRANT_COLLECTION", "omni_medical_suite_records"),
    extractor=extractor,
)

CUSTOM_CSS = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
.omni-card { border: 1px solid #dbeafe; border-radius: 14px; padding: 14px; background: #f8fbff; }
"""


def _render_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def run_compare(raw_text: str, processed_text: str, reference_text: str, force_rtl_fix: bool) -> tuple[str, dict[str, Any]]:
    result = compare_raw_vs_printed_text(
        raw_text,
        processed_text,
        reference_text or None,
        force_rtl_fix=force_rtl_fix,
    )
    field_similarity = result["field_aware_similarity"]
    summary = [
        "## ملخص المقارنة",
        f"- **تشابه النص الخام مع النص المعالج:** {result['raw_vs_processed_similarity']:.1%}",
        f"- **Field-aware similarity:** {field_similarity['score']:.1%}",
        f"- **قرار نفس المريض:** {'نعم' if field_similarity['is_same_patient'] else 'لا'}",
        f"- **تفسير:** {field_similarity['explanation']}",
    ]
    if result["raw_vs_reference_similarity"] is not None:
        summary.append(f"- **تشابه الخام مع المرجع:** {result['raw_vs_reference_similarity']:.1%}")
        summary.append(f"- **تشابه المعالج مع المرجع:** {result['processed_vs_reference_similarity']:.1%}")
        summary.append(f"- **التحسن مقابل المرجع:** {result['improvement_vs_reference']:+.1%}")
    return "\n".join(summary), result


def _parse_corpus(corpus_text: str) -> list[dict[str, Any]]:
    if not corpus_text.strip():
        return []
    parsed = json.loads(corpus_text)
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    raise ValueError("Corpus must be a JSON object or a list of objects.")


def run_search(query: str, corpus_text: str) -> tuple[str, str]:
    corpus = _parse_corpus(corpus_text)
    indexing_info = search_service.upsert_records(corpus)
    hits = search_service.search(query, top_k=5)
    if not hits:
        return "لا توجد نتائج.", _render_json({"indexing": indexing_info, "hits": []})
    lines = [f"## نتائج البحث ({indexing_info['backend']})"]
    for idx, hit in enumerate(hits, start=1):
        diagnosis = hit["metadata"].get("diagnosis", "—")
        patient = hit["metadata"].get("patient_name", "—")
        lines.append(f"{idx}. **{patient}** — التشخيص: {diagnosis} — score={hit['score']:.2f}")
    return "\n".join(lines), _render_json({"indexing": indexing_info, "hits": hits})


def run_review(
    text: str,
    language: str,
    block_type: str,
    image_quality: float,
    has_diacritics: bool,
    prefer_structured_output: bool,
    document_type: str,
    force_rtl_fix: bool,
) -> tuple[str, dict[str, Any], str]:
    fixed_text = rtl_fixer.fix_text(text, force=force_rtl_fix)
    fields = extractor.extract_fields(fixed_text).to_dict()
    engines, reasons = router.select(
        language=language,
        block_type=block_type,
        image_quality=image_quality,
        has_diacritics=has_diacritics,
        prefer_structured_output=prefer_structured_output,
        document_type=document_type,
    )
    recommendation = "\n".join([
        "## توصية التوجيه",
        f"- **المحركات المقترحة:** {', '.join(engines)}",
        f"- **الوقت التقديري:** {router.estimate_time(engines)} ثانية",
        *[f"- {reason}" for reason in reasons],
    ])
    return fixed_text, fields, recommendation


with gr.Blocks(title="Omni Medical Suite — Advanced Review", css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# Omni Medical Suite — Advanced Review App\n"
        "واجهة مراجعة متقدمة لـ OCR الطبي: مقارنة، بحث، ومراجعة موجّهة.")

    with gr.Tab("Compare"):
        with gr.Row():
            raw_text = gr.Textbox(label="النص الخام", lines=10)
            processed_text = gr.Textbox(label="النص بعد المعالجة / الطباعة", lines=10)
        reference_text = gr.Textbox(label="النص المرجعي (اختياري)", lines=6)
        force_compare_fix = gr.Checkbox(label="فرض إصلاح RTL", value=False)
        compare_btn = gr.Button("تنفيذ المقارنة", variant="primary")
        compare_summary = gr.Markdown(elem_classes=["omni-card"])
        compare_json = gr.JSON(label="تفاصيل المقارنة")
        compare_btn.click(
            fn=run_compare,
            inputs=[raw_text, processed_text, reference_text, force_compare_fix],
            outputs=[compare_summary, compare_json],
        )

    with gr.Tab("Search"):
        query = gr.Textbox(label="استعلام البحث", lines=2)
        corpus = gr.Textbox(
            label="Corpus JSON",
            lines=14,
            placeholder='[{"patient_name":"أحمد","diagnosis":"ارتفاع ضغط","raw_text":"..."}]',
        )
        search_btn = gr.Button("فهرسة ثم بحث", variant="primary")
        search_summary = gr.Markdown(elem_classes=["omni-card"])
        search_json = gr.Code(label="JSON", language="json")
        search_btn.click(fn=run_search, inputs=[query, corpus], outputs=[search_summary, search_json])

    with gr.Tab("Review"):
        review_text = gr.Textbox(label="نص OCR للمراجعة", lines=12)
        with gr.Row():
            language = gr.Dropdown(choices=["ar", "mixed", "en", "de"], value="ar", label="اللغة")
            block_type = gr.Dropdown(choices=["paragraph", "table", "form", "handwriting", "header", "footer"], value="paragraph", label="نوع الكتلة")
            document_type = gr.Dropdown(choices=["generic", "report", "article", "book", "markdown"], value="generic", label="نوع المستند")
        with gr.Row():
            image_quality = gr.Slider(minimum=0.0, maximum=1.0, value=0.8, step=0.05, label="جودة الصورة")
            has_diacritics = gr.Checkbox(label="يوجد تشكيل", value=False)
            prefer_structured_output = gr.Checkbox(label="أفضلية لمخرجات هيكلية", value=False)
            force_review_fix = gr.Checkbox(label="فرض إصلاح RTL", value=False)
        review_btn = gr.Button("تحليل ومراجعة", variant="primary")
        normalized_text = gr.Textbox(label="النص بعد إصلاح RTL", lines=10)
        extracted_fields = gr.JSON(label="الحقول المستخرجة")
        routing_advice = gr.Markdown(elem_classes=["omni-card"])
        review_btn.click(
            fn=run_review,
            inputs=[review_text, language, block_type, image_quality, has_diacritics, prefer_structured_output, document_type, force_review_fix],
            outputs=[normalized_text, extracted_fields, routing_advice],
        )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
