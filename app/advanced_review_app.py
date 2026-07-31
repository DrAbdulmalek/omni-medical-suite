"""Advanced Gradio review app for Omni Medical Suite.

Tabs:
- Scanner Fixer: Single image Before/After preview with scanner_fixer pipeline
- Batch Process: Directory-level batch processing with previews + ZIP/PDF export
- Dedup: Perceptual-hash duplicate detection across image folders
- Compare: Raw vs preprocessed OCR text comparisons
- Search: Qdrant-backed semantic search with local fallback
- Review: RTL cleanup, field extraction, and routing recommendations

All state uses gr.State — no self. attributes on the Blocks.
"""

from __future__ import annotations

import base64
import io
import json
import os
import random
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import cv2
import gradio as gr
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# scanner_fixer imports (with fallback)
# ---------------------------------------------------------------------------
try:
    from scanner_fixer.pipeline import fix_scan
    from scanner_fixer.batch_pipeline import BatchProcessor, BatchConfig
    from scanner_fixer.dedup import find_duplicate_clusters, export_dedup_report
    from scanner_fixer.normalize import normalize_scanned_image
    from scanner_fixer.deskew import detect_skew_angle
    from scanner_fixer.crop import auto_crop
    from scanner_fixer.enhance import enhance_for_ocr

    SCANNER_FIXER_AVAILABLE = True
except ImportError:
    SCANNER_FIXER_AVAILABLE = False

# ---------------------------------------------------------------------------
# scanner_tab: enhanced scanner UI helpers (manual crop + advanced edges)
# ---------------------------------------------------------------------------
try:
    from app.scanner_tab import (
        process_with_options as _process_with_options,
        save_processed_image as _save_processed_image,
        apply_manual_crop as _apply_manual_crop,
        apply_advanced_edges as _apply_advanced_edges,
        build_zip_from_dir as _build_zip_from_dir,
    )
    SCANNER_TAB_AVAILABLE = True
except ImportError:
    SCANNER_TAB_AVAILABLE = False
    _process_with_options = None  # type: ignore
    _save_processed_image = None  # type: ignore
    _apply_manual_crop = None  # type: ignore
    _apply_advanced_edges = None  # type: ignore
    _build_zip_from_dir = None  # type: ignore

# ---------------------------------------------------------------------------
# Original app imports (with fallback)
# ---------------------------------------------------------------------------
try:
    from omni_medical_suite.preprocessing.compare_raw_vs_printed import compare_raw_vs_printed_text
    from packages.core.engine_router import EngineRouter
    from src.ocr.deduplication import QdrantMedicalSearch
    from src.ocr.field_extractor import ArabicMedicalFieldExtractor
    from src.ocr.rtl_utils import ArabicRTLFixer

    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Optional PDF generation (requires img2pdf or Pillow)
# ---------------------------------------------------------------------------
try:
    import img2pdf  # type: ignore

    HAS_IMG2PDF = True
except ImportError:
    HAS_IMG2PDF = False

# ---------------------------------------------------------------------------
# Service instances (only if core is available)
# ---------------------------------------------------------------------------
if CORE_AVAILABLE:
    _extractor = ArabicMedicalFieldExtractor()
    _rtl_fixer = ArabicRTLFixer()
    _router = EngineRouter(
        profile=os.getenv("ENGINE_PROFILE", "balanced"),
        use_gpu=os.getenv("USE_GPU", "false").lower() == "true",
    )
    _search_service = QdrantMedicalSearch(
        qdrant_url=os.getenv("QDRANT_URL"),
        collection_name=os.getenv("QDRANT_COLLECTION", "omni_medical_suite_records"),
        extractor=_extractor,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pbm", ".pgm"}

CUSTOM_CSS = """
.gradio-container { direction: rtl; }
footer { display: none !important; }
.omni-card { border: 1px solid #dbeafe; border-radius: 14px; padding: 14px; background: #f8fbff; }
.scanner-preview img { max-height: 500px; object-fit: contain; }
.scanner-gallery img { max-height: 300px; object-fit: contain; }
"""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _numpy_to_base64(img: np.ndarray, fmt: str = ".png") -> str:
    """Encode a numpy image (BGR) as a base64 data URI."""
    success, buf = cv2.imencode(fmt, img)
    if not success:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    mime = "image/png" if fmt == ".png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _pil_to_numpy(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to BGR numpy array."""
    return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _numpy_to_pil(img: np.ndarray) -> Image.Image:
    """Convert BGR numpy array to PIL Image."""
    if len(img.shape) == 2:
        return Image.fromarray(img)
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _images_to_pdf(image_paths: list[str], output_path: str) -> str:
    """Combine multiple image files into a single PDF."""
    if HAS_IMG2PDF:
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(image_paths))
    else:
        # Fallback: use Pillow
        pil_images = []
        for p in image_paths:
            img = Image.open(p)
            if img.mode != "RGB":
                img = img.convert("RGB")
            pil_images.append(img)
        if pil_images:
            pil_images[0].save(
                output_path,
                "PDF",
                save_all=True,
                append_images=pil_images[1:],
                resolution=150.0,
            )
    return output_path


def _render_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ===========================================================================
# Tab 1: Scanner Fixer — Single Image Before/After (with manual crop + edges)
# ===========================================================================
def process_single_image(
    input_image: Optional[np.ndarray],
    do_crop: bool,
    do_deskew: bool,
    do_enhance: bool,
    do_rotate: bool,
    binarize: bool,
    crop_padding: int,
    crop_box: Optional[Any] = None,
    use_canny: bool = False,
    use_adaptive: bool = False,
    use_morphology: bool = False,
    use_hough: bool = False,
) -> tuple[Optional[np.ndarray], Optional[np.ndarray], str, Optional[np.ndarray]]:
    """Process a single image through scanner_fixer + advanced edges.

    Returns (before_pil, after_pil, report_md, after_rgb_ndarray).
    The 4th return value is the after-image as a numpy RGB array, used by
    the manual-save button downstream.
    """
    if input_image is None:
        return None, None, "⚠️ لم يتم تحميل صورة", None

    # Delegate to scanner_tab.process_with_options when available
    if SCANNER_TAB_AVAILABLE:
        before_pil, after_pil, report = _process_with_options(
            input_image,
            crop_box=crop_box,
            do_crop=do_crop,
            do_deskew=do_deskew,
            do_enhance=do_enhance,
            do_rotate=do_rotate,
            binarize=binarize,
            crop_padding=crop_padding,
            use_canny=use_canny,
            use_adaptive=use_adaptive,
            use_morphology=use_morphology,
            use_hough=use_hough,
        )
        # Convert after_pil back to numpy RGB for the save button
        after_rgb = None
        if after_pil is not None:
            after_rgb = np.array(after_pil)
        return before_pil, after_pil, report, after_rgb

    # Fallback: original behavior (no manual crop / advanced edges)
    if not SCANNER_FIXER_AVAILABLE:
        return None, None, "❌ scanner_fixer غير متاح — ثبّت الحزمة أولاً", None

    bgr = cv2.cvtColor(input_image, cv2.COLOR_RGB2BGR)
    before_pil = Image.fromarray(input_image)

    try:
        result = fix_scan(
            bgr,
            do_crop=do_crop,
            do_deskew=do_deskew,
            do_enhance=do_enhance,
            do_rotate=do_rotate,
            binarize=binarize,
            crop_padding=crop_padding,
        )
        fixed_bgr = result["image"]
        after_rgb = cv2.cvtColor(fixed_bgr, cv2.COLOR_BGR2RGB)
        after_pil = Image.fromarray(after_rgb)

        # Build metadata report
        report = result.get("report", {})
        lines = [
            "## 📊 تقرير المعالجة",
            f"- **الحجم الأصلي:** {bgr.shape[1]}×{bgr.shape[0]}",
            f"- **الحجم بعد المعالجة:** {fixed_bgr.shape[1]}×{fixed_bgr.shape[0]}",
            f"- **الخطوات المطبقة:** {', '.join(result.get('steps', {}).keys())}",
        ]
        if "skew_angle" in report:
            lines.append(f"- **زاوية الميل:** {report['skew_angle']:.2f}°")
        if "estimated_dpi" in report:
            lines.append(f"- **DPI المقدّر:** {report['estimated_dpi']}")
        if "crop_box" in report:
            l, t, r, b = report["crop_box"]
            lines.append(f"- **حدود القص:** يسار={l}, أعلى={t}, يمين={r}, أسفل={b}")

        return before_pil, after_pil, "\n".join(lines), after_rgb

    except Exception as exc:
        return before_pil, None, f"❌ خطأ في المعالجة: {exc}", None


def save_current_after_image(
    after_rgb: Optional[np.ndarray],
    output_dir: str,
    filename: Optional[str] = None,
) -> str:
    """Save the current 'after' image to disk. Returns a status message."""
    if after_rgb is None:
        return "⚠️ لا توجد صورة معالَجة للحفظ — شغّل المعالجة أولًا"
    if not SCANNER_TAB_AVAILABLE:
        return "❌ scanner_tab غير متاح — لا يمكن الحفظ"
    try:
        bgr = cv2.cvtColor(after_rgb, cv2.COLOR_RGB2BGR)
        path = _save_processed_image(bgr, output_dir, filename)
        return f"✅ تم الحفظ: `{path}`"
    except Exception as exc:
        return f"❌ فشل الحفظ: {exc}"


# ===========================================================================
# Tab 2: Batch Process — Directory + ZIP/PDF Export
# ===========================================================================
def run_batch(
    input_dir: str,
    do_crop: bool,
    do_deskew: bool,
    do_enhance: bool,
    do_rotate: bool,
    binarize: bool,
    crop_padding: int,
    workers: int,
    generate_previews: bool,
    progress=gr.Progress(),
) -> tuple[str, list, Optional[str], Optional[str]]:
    """Run batch processing on a directory of images.

    Returns:
        (summary_md, gallery_images, zip_path, pdf_path)
    """
    if not SCANNER_FIXER_AVAILABLE:
        return "❌ scanner_fixer غير متاح", [], None, None

    if not input_dir or not Path(input_dir).is_dir():
        return "⚠️ حدد مجلد إدخال صالح", [], None, None

    # Count images
    image_files = [
        p for p in Path(input_dir).rglob("*")
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
    ]
    if not image_files:
        return "⚠️ لا توجد صور في المجلد المحدد", [], None, None

    progress(0, desc=f"جاري معالجة {len(image_files)} صورة...")

    # Setup output dir
    output_dir = tempfile.mkdtemp(prefix="scanner_batch_")

    config = BatchConfig(
        workers=workers,
        generate_previews=generate_previews,
        do_crop=do_crop,
        do_deskew=do_deskew,
        do_enhance=do_enhance,
        do_rotate=do_rotate,
        binarize=binarize,
        crop_padding=crop_padding,
        manifest_format="csv",
    )

    try:
        processor = BatchProcessor(input_dir, output_dir, config)
        summary = processor.run()
    except Exception as exc:
        return f"❌ خطأ في المعالجة: {exc}", [], None, None

    progress(0.6, desc="إنشاء المعرض والتصدير...")

    # Collect gallery images (before/after previews)
    gallery_images = []
    previews_dir = Path(output_dir) / "previews"
    if previews_dir.exists():
        for p in sorted(previews_dir.glob("*.png"))[:50]:  # cap at 50 for performance
            gallery_images.append(str(p))

    # If no previews, show fixed images
    if not gallery_images:
        for p in sorted(Path(output_dir).glob("*_fixed.*"))[:50]:
            if p.suffix.lower() in IMAGE_EXTENSIONS:
                gallery_images.append(str(p))

    progress(0.8, desc="إنشاء ZIP و PDF...")

    # Create ZIP
    zip_path = None
    try:
        zip_path = output_dir + ".zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(output_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    arcname = fpath.relative_to(Path(output_dir).parent)
                    zf.write(str(fpath), str(arcname))
    except Exception:
        zip_path = None

    # Create PDF from fixed images
    pdf_path = None
    try:
        fixed_images = sorted(
            p for p in Path(output_dir).glob("*_fixed.*")
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        )
        if fixed_images:
            pdf_path = output_dir + ".pdf"
            _images_to_pdf([str(p) for p in fixed_images], pdf_path)
    except Exception:
        pdf_path = None

    progress(1.0, desc="تم!")

    # Build summary markdown
    lines = [
        "## 📦 نتائج المعالجة الدفعية",
        f"- **إجمالي الصور:** {summary.get('total_images', 0)}",
        f"- **ناجح:** {summary.get('ok', 0)} ✅",
        f"- **فاشل:** {summary.get('failed', 0)} ❌",
        f"- **معزول:** {summary.get('quarantined', 0)} ⚠️",
        f"- **الوقت الكلي:** {summary.get('total_time_seconds', 0):.1f} ثانية",
        f"- **متوسط وقت الصورة:** {summary.get('average_time_per_image_ms', 0):.0f} ميلي ثانية",
        f"- **مجلد الإخراج:** `{output_dir}`",
    ]
    if zip_path:
        lines.append(f"- **ZIP:** `{zip_path}`")
    if pdf_path:
        lines.append(f"- **PDF:** `{pdf_path}`")

    return "\n".join(lines), gallery_images, zip_path, pdf_path


def pick_random_preview(
    gallery_images: list,
) -> tuple[Optional[np.ndarray], str]:
    """Pick a random image from the batch gallery for detailed preview."""
    if not gallery_images:
        return None, "⚠️ لا توجد صور في المعرض"
    chosen = random.choice(gallery_images)
    img = cv2.imread(chosen)
    if img is None:
        return None, f"⚠️ تعذر قراءة: {chosen}"
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return rgb, f"🔍 معاينة عشوائية: `{Path(chosen).name}`"


# ===========================================================================
# Tab 3: Dedup — Perceptual Hash Duplicate Detection
# ===========================================================================
def run_dedup(
    image_folder: str,
    hamming_threshold: int,
    normalize: bool,
    progress=gr.Progress(),
) -> tuple[str, Optional[str]]:
    """Run duplicate detection on a folder of images."""
    if not SCANNER_FIXER_AVAILABLE:
        return "❌ scanner_fixer غير متاح", None

    if not image_folder or not Path(image_folder).is_dir():
        return "⚠️ حدد مجلد صور صالح", None

    progress(0.2, desc="فحص الصور بحثًا عن التكرارات...")

    try:
        clusters = find_duplicate_clusters(
            image_folder,
            hamming_threshold=hamming_threshold,
            normalize=normalize,
        )
    except Exception as exc:
        return f"❌ خطأ: {exc}", None

    progress(0.7, desc="إنشاء التقرير...")

    # Export CSV
    csv_path = tempfile.mktemp(suffix="_dedup_report.csv", prefix="scanner_")
    try:
        export_dedup_report(clusters, csv_path)
    except Exception as exc:
        return f"❌ خطأ في التصدير: {exc}", None

    progress(1.0, desc="تم!")

    # Build summary
    multi = [c for c in clusters if c["cluster_size"] > 1]
    unique = [c for c in clusters if c["cluster_size"] == 1]
    dup_cluster_ids = set(c["cluster_id"] for c in multi)

    lines = [
        "## 🔍 نتائج كشف التكرار",
        f"- **إجمالي الصور:** {len(clusters)}",
        f"- **صور فريدة:** {len(unique)}",
        f"- **صور مكررة:** {len(multi)}",
        f"- **مجموعات التكرار:** {len(dup_cluster_ids)}",
        f"- **عتبة هامينغ:** {hamming_threshold}",
    ]
    if dup_cluster_ids:
        lines.append("\n### مجموعات التكرار:")
        for cid in sorted(dup_cluster_ids):
            members = [c for c in multi if c["cluster_id"] == cid]
            lines.append(f"- **{cid}** ({len(members)} صورة)")
            for m in members[:3]:
                lines.append(f"  - `{Path(m['original_path']).name}` (مسافة={m['hamming_distance_from_representative']})")
            if len(members) > 3:
                lines.append(f"  - ... و{len(members) - 3} أخرى")

    lines.append(f"\n📄 تقرير CSV: `{csv_path}`")

    return "\n".join(lines), csv_path


# ===========================================================================
# Tab 4: Compare (original)
# ===========================================================================
def run_compare(
    raw_text: str,
    processed_text: str,
    reference_text: str,
    force_rtl_fix: bool,
) -> tuple[str, dict[str, Any]]:
    if not CORE_AVAILABLE:
        return "❌ الوحدات الأساسية غير متاحة", {}
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


# ===========================================================================
# Tab 5: Search (original)
# ===========================================================================
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
    if not CORE_AVAILABLE:
        return "❌ خدمة البحث غير متاحة", "{}"
    corpus = _parse_corpus(corpus_text)
    indexing_info = _search_service.upsert_records(corpus)
    hits = _search_service.search(query, top_k=5)
    if not hits:
        return "لا توجد نتائج.", _render_json({"indexing": indexing_info, "hits": []})
    lines = [f"## نتائج البحث ({indexing_info['backend']})"]
    for idx, hit in enumerate(hits, start=1):
        diagnosis = hit["metadata"].get("diagnosis", "—")
        patient = hit["metadata"].get("patient_name", "—")
        lines.append(f"{idx}. **{patient}** — التشخيص: {diagnosis} — score={hit['score']:.2f}")
    return "\n".join(lines), _render_json({"indexing": indexing_info, "hits": hits})


# ===========================================================================
# Tab 6: Review (original)
# ===========================================================================
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
    if not CORE_AVAILABLE:
        return "❌ وحدات المراجعة غير متاحة", {}, ""
    fixed_text = _rtl_fixer.fix_text(text, force=force_rtl_fix)
    fields = _extractor.extract_fields(fixed_text).to_dict()
    engines, reasons = _router.select(
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
        f"- **الوقت التقديري:** {_router.estimate_time(engines)} ثانية",
        *[f"- {reason}" for reason in reasons],
    ])
    return fixed_text, fields, recommendation


# ===========================================================================
# Build the Gradio interface
# ===========================================================================
def build_app() -> gr.Blocks:
    """Construct the full Gradio Blocks application."""

    with gr.Blocks(
        title="Omni Medical Suite — Advanced Review",
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(),
    ) as demo:

        gr.Markdown(
            "# 🏥 Omni Medical Suite — Advanced Review App\n"
            "واجهة مراجعة متقدمة لـ OCR الطبي: معالجة صور، معالجة دفعية، كشف تكرار، مقارنة، بحث، ومراجعة موجّهة.\n\n"
            f"**scanner_fixer:** {'✅ متاح' if SCANNER_FIXER_AVAILABLE else '❌ غير متاح — ثبّت الحزمة'} | "
            f"**img2pdf:** {'✅ متاح' if HAS_IMG2PDF else '⚠️ غير مثبت (سيستخدم Pillow كبديل)'}"
        )

        # ----------------------------------------------------------------
        # Tab 1: Scanner Fixer — Single Image (with manual crop + advanced edges)
        # ----------------------------------------------------------------
        with gr.Tab("🔬 معالج الصور"):
            gr.Markdown("### معالجة صورة واحدة — قبل وبعد (مع قص يدوي وكشف حواف متقدم)")
            with gr.Row():
                with gr.Column(scale=1):
                    scanner_input = gr.Image(
                        label="📷 الصورة الأصلية",
                        type="numpy",
                        elem_classes=["scanner-preview"],
                    )
                    with gr.Row():
                        sc_do_crop = gr.Checkbox(label="قص الحواف", value=True)
                        sc_do_deskew = gr.Checkbox(label="تصحيح الميل", value=True)
                    with gr.Row():
                        sc_do_enhance = gr.Checkbox(label="تحسين التباين", value=True)
                        sc_do_rotate = gr.Checkbox(label="كشف الدوران 180°", value=False)
                    with gr.Row():
                        sc_binarize = gr.Checkbox(label="ثنائية اللون (B&W)", value=False)
                        sc_crop_padding = gr.Slider(
                            minimum=0, maximum=50, value=10, step=1,
                            label="هامش القص (بكسل)",
                        )
                    with gr.Accordion("✂️ قص يدوي (اختياري — اترك 0 لتخطّيه)", open=False):
                        gr.Markdown("أدخل إحداثيات مربع القص يدويًا (بالبكسل):")
                        with gr.Row():
                            sc_crop_x = gr.Number(label="X (يسار)", value=0, minimum=0, precision=0)
                            sc_crop_y = gr.Number(label="Y (أعلى)", value=0, minimum=0, precision=0)
                        with gr.Row():
                            sc_crop_w = gr.Number(label="العرض", value=0, minimum=0, precision=0)
                            sc_crop_h = gr.Number(label="الارتفاع", value=0, minimum=0, precision=0)
                    with gr.Accordion("⚙️ كشف الحواف المتقدم", open=False):
                        gr.Markdown("خيارات إضافية تُطبَّق بعد scanner_fixer الأساسي:")
                        with gr.Row():
                            sc_use_canny = gr.Checkbox(label="Canny", value=False)
                            sc_use_adaptive = gr.Checkbox(label="Adaptive Threshold", value=False)
                        with gr.Row():
                            sc_use_morphology = gr.Checkbox(label="Morphology", value=False)
                            sc_use_hough = gr.Checkbox(label="Hough Lines", value=False)
                    with gr.Row():
                        scanner_btn = gr.Button("🚀 معالجة الصورة", variant="primary")
                        scanner_save_btn = gr.Button("💾 حفظ النتيجة", variant="secondary")
                    sc_output_dir = gr.Textbox(
                        label="مجلد الحفظ",
                        value=os.path.expanduser("~/.omni/scanner_outputs"),
                    )
                    sc_save_status = gr.Markdown(elem_classes=["omni-card"])

                with gr.Column(scale=1):
                    scanner_before = gr.Image(
                        label="قبل المعالجة",
                        type="pil",
                        elem_classes=["scanner-preview"],
                    )
                    scanner_after = gr.Image(
                        label="بعد المعالجة",
                        type="pil",
                        elem_classes=["scanner-preview"],
                    )
                    scanner_report = gr.Markdown(elem_classes=["omni-card"])

            # State for after-image numpy (used by save button)
            sc_after_state = gr.State(value=None)

            # Build crop_box dict from the 4 number inputs at click time
            def _build_crop_box(x, y, w, h):
                if not x or not y or not w or not h:
                    return None
                if w <= 0 or h <= 0:
                    return None
                return {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}

            scanner_btn.click(
                fn=lambda img, dc, dd, de, dr, bi, cp, cx, cy, cw, ch, uc, ua, um, uh: (
                    process_single_image(
                        img, dc, dd, de, dr, bi, cp,
                        _build_crop_box(cx, cy, cw, ch),
                        uc, ua, um, uh,
                    )
                ),
                inputs=[
                    scanner_input,
                    sc_do_crop, sc_do_deskew, sc_do_enhance, sc_do_rotate,
                    sc_binarize, sc_crop_padding,
                    sc_crop_x, sc_crop_y, sc_crop_w, sc_crop_h,
                    sc_use_canny, sc_use_adaptive, sc_use_morphology, sc_use_hough,
                ],
                outputs=[scanner_before, scanner_after, scanner_report, sc_after_state],
            )
            scanner_save_btn.click(
                fn=save_current_after_image,
                inputs=[sc_after_state, sc_output_dir],
                outputs=[sc_save_status],
            )

        # ----------------------------------------------------------------
        # Tab 2: Batch Process
        # ----------------------------------------------------------------
        with gr.Tab("📦 معالجة دفعية"):
            gr.Markdown("### معالجة مجلد كامل من الصور مع تصدير ZIP/PDF")
            with gr.Row():
                batch_input_dir = gr.Textbox(
                    label="📁 مسار مجلد الإدخال",
                    placeholder="/path/to/scanned/images",
                )
                batch_workers = gr.Slider(
                    minimum=1, maximum=8, value=1, step=1,
                    label="عدد العمال (workers)",
                )
            with gr.Row():
                bt_do_crop = gr.Checkbox(label="قص الحواف", value=True)
                bt_do_deskew = gr.Checkbox(label="تصحيح الميل", value=True)
                bt_do_enhance = gr.Checkbox(label="تحسين التباين", value=True)
                bt_do_rotate = gr.Checkbox(label="كشف الدوران", value=False)
                bt_binarize = gr.Checkbox(label="ثنائية اللون", value=False)
            bt_crop_padding = gr.Slider(
                minimum=0, maximum=50, value=10, step=1,
                label="هامش القص (بكسل)",
            )
            bt_generate_previews = gr.Checkbox(label="إنشاء معاينات قبل/بعد", value=True)

            batch_btn = gr.Button("🚀 تشغيل المعالجة الدفعية", variant="primary")
            batch_summary = gr.Markdown(elem_classes=["omni-card"])

            batch_gallery = gr.Gallery(
                label="معاينات النتائج",
                columns=4,
                height="auto",
                elem_classes=["scanner-gallery"],
            )

            with gr.Row():
                batch_zip = gr.File(label="📦 تحميل ZIP")
                batch_pdf = gr.File(label="📄 تحميل PDF")
                random_btn = gr.Button("🎲 معاينة عشوائية")

            # State for gallery images (paths list)
            batch_gallery_state = gr.State([])

            random_preview_img = gr.Image(label="🎲 معاينة عشوائية", type="numpy")
            random_preview_label = gr.Markdown()

            batch_btn.click(
                fn=run_batch,
                inputs=[
                    batch_input_dir,
                    bt_do_crop,
                    bt_do_deskew,
                    bt_do_enhance,
                    bt_do_rotate,
                    bt_binarize,
                    bt_crop_padding,
                    batch_workers,
                    bt_generate_previews,
                ],
                outputs=[batch_summary, batch_gallery, batch_zip, batch_pdf],
            ).then(
                fn=lambda gallery: gallery,
                inputs=[batch_gallery],
                outputs=[batch_gallery_state],
            )

            random_btn.click(
                fn=pick_random_preview,
                inputs=[batch_gallery_state],
                outputs=[random_preview_img, random_preview_label],
            )

        # ----------------------------------------------------------------
        # Tab 3: Dedup
        # ----------------------------------------------------------------
        with gr.Tab("🔍 كشف التكرار"):
            gr.Markdown("### كشف الصور المكررة باستخدام التجزئة الإدراكية (phash)")
            with gr.Row():
                dedup_folder = gr.Textbox(
                    label="📁 مسار مجلد الصور",
                    placeholder="/path/to/scanned/images",
                )
                dedup_threshold = gr.Slider(
                    minimum=1, maximum=20, value=5, step=1,
                    label="عتبة هامينغ (أقل = أكثر صرامة)",
                )
                dedup_normalize = gr.Checkbox(label="تطبيع الصور قبل الفحص", value=True)

            dedup_btn = gr.Button("🔍 فحص التكرار", variant="primary")
            dedup_summary = gr.Markdown(elem_classes=["omni-card"])
            dedup_csv = gr.File(label="📄 تحميل تقرير CSV")

            dedup_btn.click(
                fn=run_dedup,
                inputs=[dedup_folder, dedup_threshold, dedup_normalize],
                outputs=[dedup_summary, dedup_csv],
            )

        # ----------------------------------------------------------------
        # Tab 4: Compare (original)
        # ----------------------------------------------------------------
        with gr.Tab("⚖️ مقارنة"):
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

        # ----------------------------------------------------------------
        # Tab 5: Search (original)
        # ----------------------------------------------------------------
        with gr.Tab("🔎 بحث"):
            query = gr.Textbox(label="استعلام البحث", lines=2)
            corpus = gr.Textbox(
                label="Corpus JSON",
                lines=14,
                placeholder='[{"patient_name":"أحمد","diagnosis":"ارتفاع ضغط","raw_text":"..."}]',
            )
            search_btn = gr.Button("فهرسة ثم بحث", variant="primary")
            search_summary = gr.Markdown(elem_classes=["omni-card"])
            search_json = gr.Code(label="JSON", language="json")
            search_btn.click(
                fn=run_search,
                inputs=[query, corpus],
                outputs=[search_summary, search_json],
            )

        # ----------------------------------------------------------------
        # Tab 6: Review (original)
        # ----------------------------------------------------------------
        with gr.Tab("📋 مراجعة"):
            review_text = gr.Textbox(label="نص OCR للمراجعة", lines=12)
            with gr.Row():
                language = gr.Dropdown(
                    choices=["ar", "mixed", "en", "de"], value="ar", label="اللغة",
                )
                block_type = gr.Dropdown(
                    choices=["paragraph", "table", "form", "handwriting", "header", "footer"],
                    value="paragraph",
                    label="نوع الكتلة",
                )
                document_type = gr.Dropdown(
                    choices=["generic", "report", "article", "book", "markdown"],
                    value="generic",
                    label="نوع المستند",
                )
            with gr.Row():
                image_quality = gr.Slider(
                    minimum=0.0, maximum=1.0, value=0.8, step=0.05,
                    label="جودة الصورة",
                )
                has_diacritics = gr.Checkbox(label="يوجد تشكيل", value=False)
                prefer_structured_output = gr.Checkbox(
                    label="أفضلية لمخرجات هيكلية", value=False,
                )
                force_review_fix = gr.Checkbox(label="فرض إصلاح RTL", value=False)
            review_btn = gr.Button("تحليل ومراجعة", variant="primary")
            normalized_text = gr.Textbox(label="النص بعد إصلاح RTL", lines=10)
            extracted_fields = gr.JSON(label="الحقول المستخرجة")
            routing_advice = gr.Markdown(elem_classes=["omni-card"])
            review_btn.click(
                fn=run_review,
                inputs=[
                    review_text, language, block_type, image_quality,
                    has_diacritics, prefer_structured_output,
                    document_type, force_review_fix,
                ],
                outputs=[normalized_text, extracted_fields, routing_advice],
            )

    return demo


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
demo = build_app()

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
