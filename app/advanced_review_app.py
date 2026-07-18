"""
advanced_review_app.py
======================

Minimal Gradio 4.x app exposing the scanner_fixer pipeline.

Tabs:
  - 🖼️ تصحيح السكانر: single image, batch folder, ZIP export, random preview
  - ℹ️ حول: short description

Run:
    python app/advanced_review_app.py
"""

from __future__ import annotations

import random
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import cv2
import gradio as gr
import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "packages" / "scanner_fixer" / "src"))

from scanner_fixer import batch_fix_folder, fix_scanned_image  # noqa: E402

STATE: dict = {"batch_images": {}, "last_report": []}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def process_single(img: Image.Image | None) -> tuple[Image.Image | None, str]:
    if img is None:
        return None, "❌ ارفع صورة أولاً."
    try:
        fixed_rgb, meta = fix_scanned_image(img)
    except Exception as exc:
        return None, f"❌ خطأ: {exc}"
    out = Image.fromarray(fixed_rgb, mode="RGB")
    return out, f"✅ تم التصحيح — {meta.get('final_shape')}"


def save_single(img: Image.Image | None) -> str:
    if img is None:
        return "❌ لا توجد صورة للحفظ."
    path = Path.home() / f"fixed_{datetime.now():%Y%m%d_%H%M%S}.png"
    img.save(path)
    return f"💾 تم الحفظ: {path}"


def process_batch(folder_path: str | None) -> tuple[list[list[str]], str]:
    if not folder_path:
        return [], "❌ اختر مجلداً."
    folder = Path(folder_path)
    if not folder.is_dir():
        return [], f"❌ ليس مجلداً: {folder}"

    out_dir = folder / "_fixed"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = batch_fix_folder(folder, output_dir=out_dir)

    # Cache results for ZIP / preview
    STATE["batch_images"].clear()
    STATE["last_report"] = report
    for r in report:
        if r.get("status") == "success" and r.get("output_path"):
            p = Path(r["output_path"])
            if p.exists():
                STATE["batch_images"][p.name] = Image.open(p).convert("RGB")

    # Build a simple table
    table = [
        [Path(r.get("file", "")).name, r.get("status", ""), str(r.get("final_shape", ""))]
        for r in report
    ]
    n_ok = sum(1 for r in report if r.get("status") == "success")
    return table, f"✅ Batch: {n_ok}/{len(report)} نجح — النتائج في {out_dir}"


def random_preview() -> tuple[Image.Image | None, str]:
    if not STATE["batch_images"]:
        return None, "لا توجد نتائج."
    name = random.choice(list(STATE["batch_images"].keys()))
    return STATE["batch_images"][name], f"معاينة: {name}"


def save_zip() -> str:
    if not STATE["batch_images"]:
        return "لا توجد نتائج لتنظيمها في ZIP."
    zip_path = Path.home() / f"batch_fixed_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, img in STATE["batch_images"].items():
            tmp = Path("/tmp") / name
            img.save(tmp)
            z.write(tmp, arcname=name)
            tmp.unlink(missing_ok=True)
    return f"📦 ZIP: {zip_path}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(title="OmniMedical — Scanner Fixer") as demo:
        gr.Markdown("# 🩺 OmniMedical — Scanner Fixer")
        with gr.Tab("🖼️ تصحيح السكانر"):
            with gr.Tabs():
                with gr.Tab("صورة واحدة"):
                    with gr.Row():
                        single_in = gr.Image(type="pil", label="الصورة الأصلية")
                        single_out = gr.Image(type="pil", label="بعد التصحيح")
                    process_btn = gr.Button("🔄 معالجة", variant="primary")
                    save_btn = gr.Button("💾 حفظ")
                    single_status = gr.Textbox(label="الحالة")

                with gr.Tab("📁 Batch"):
                    batch_in = gr.File(
                        label="اختر مجلد صور",
                        file_count="directory",
                        file_types=["image"],
                    )
                    batch_btn = gr.Button("🚀 معالجة Batch", variant="primary")
                    batch_df = gr.Dataframe(
                        headers=["ملف", "حالة", "الشكل النهائي"],
                        label="نتائج المعالجة",
                    )
                    with gr.Row():
                        random_btn = gr.Button("🎲 معاينة عشوائية")
                        preview = gr.Image(label="معاينة")
                    zip_btn = gr.Button("📦 حفظ الكل كـ ZIP", variant="primary")
                    batch_status = gr.Textbox(label="الحالة")

            process_btn.click(process_single, inputs=single_in, outputs=[single_out, single_status])
            save_btn.click(save_single, inputs=single_out, outputs=single_status)
            batch_btn.click(process_batch, inputs=batch_in, outputs=[batch_df, batch_status])
            random_btn.click(random_preview, outputs=[preview, batch_status])
            zip_btn.click(save_zip, outputs=batch_status)

        with gr.Tab("ℹ️ حول"):
            gr.Markdown(
                """
                **Scanner Fixer v2.1**

                Pipeline: text-aware crop → Hough deskew → CLAHE → fastNlMeans denoise.

                - المصدر: `packages/scanner_fixer/`
                - الواجهة: `packages/desktop/medical_doc_gui_final_v2.py` (PySide6)
                - هذا التبويب: `app/advanced_review_app.py` (Gradio 4.x)
                """
            )
    return demo


if __name__ == "__main__":
    build_ui().launch()
