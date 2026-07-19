"""
termux_app.py — OmniMedical OCR for Termux (Android ARM64)
============================================================
نسخة مبسطة من Gradio UI تعمل مباشرة في Termux على هاتف Android.
لا تحتاج AppImage ولا APK — فقط Python + Gradio.

الميزات:
  • Handwriting Trainer — OCR + تصحيح + حفظ في SQLite/JSONL
  • Scanner Fixer — deskew + auto-crop + denoise + ZIP export
  • Batch processing — معالجة عدة صور دفعة واحدة
  • Offline mode — كل المعالجة محلية (لا إنترنت بعد التثبيت)
  • Statistics — تتبّع التصحيحات

التشغيل:
  python termux_app.py --port 7860
  # ثم افتح: http://localhost:7860 في متصفح الهاتف

Author: Dr. Abdulmalek <drabdulmalek@proton.me>
License: AGPL-3.0
"""

from __future__ import annotations

import argparse
import cv2
import gradio as gr
import hashlib
import io
import json
import logging
import numpy as np
import os
import pytesseract
import sqlite3
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from PIL import Image
from typing import Optional

try:
    from pdf2image import convert_from_bytes
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ── Setup ───────────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get("HOME", "/tmp")) / "omni_workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
UPLOADS = WORKSPACE / "uploads"
EXPORTS = WORKSPACE / "exports"
DB_DIR = WORKSPACE / "corrections_db"
LOGS_DIR = WORKSPACE / "logs"
for d in (UPLOADS, EXPORTS, DB_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "corrections.db"
JSONL_PATH = EXPORTS / "corrections.jsonl"
LOG_PATH = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
log = logging.getLogger("OmniMedical.Termux")
log.info("=== OmniMedical Termux starting ===")
log.info("Workspace: %s", WORKSPACE)

# ── SQLite DB ───────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT NOT NULL,
        corrected TEXT NOT NULL,
        language TEXT,
        image_path TEXT,
        source TEXT DEFAULT 'termux',
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS processed_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT,
        processed_path TEXT,
        mode TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn

# ── OCR corrections (Arabic medical) ────────────────────────────────────────
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

def apply_corrections(text: str) -> str:
    for wrong, right in OCR_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text

# ── Image processing ────────────────────────────────────────────────────────
def segment_words(image: Image.Image) -> list[tuple[Image.Image, str]]:
    """تقسيم الصورة إلى كلمات منفصلة + OCR لكل كلمة."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    words = []
    for cnt in sorted(contours, key=lambda c: cv2.boundingRect(c)[0]):
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 15 and h > 15:
            word_img = image.crop((x, y, x + w, y + h))
            text = pytesseract.image_to_string(word_img, lang="ara+eng").strip()
            text = apply_corrections(text)
            if text:
                words.append((word_img, text))
    return words

def deskew(image: np.ndarray) -> np.ndarray:
    """تصحيح الميل."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def text_aware_crop(image: np.ndarray, padding: int = 10) -> np.ndarray:
    """اقتصاص تلقائي يحافظ على النص."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(image.shape[1] - x, w + 2 * padding)
    h = min(image.shape[0] - y, h + 2 * padding)
    return image[y:y + h, x:x + w]

def denoise(image: np.ndarray) -> np.ndarray:
    """تنظيف الضوضاء."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    return cv2.fastNlMeansDenoising(gray, h=10)

def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """تحسين التباين (CLAHE)."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)

# ── DB operations ───────────────────────────────────────────────────────────
def save_correction(original: str, corrected: str, lang: str = "ara+eng") -> str:
    if not corrected.strip() or corrected == original:
        return "⚠️ لم يتم التعديل"
    conn = init_db()
    conn.execute(
        "INSERT INTO corrections (original, corrected, language) VALUES (?, ?, ?)",
        (original, corrected, lang),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    conn.close()

    with open(JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "original": original,
            "corrected": corrected,
            "lang": lang,
            "ts": time.time(),
            "source": "termux",
        }, ensure_ascii=False) + "\n")

    return f"✅ تم الحفظ — الإجمالي: {count} تصحيح"

def get_stats() -> str:
    conn = init_db()
    count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
    processed = conn.execute("SELECT COUNT(*) FROM processed_images").fetchone()[0]
    last_corr = conn.execute("SELECT timestamp FROM corrections ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    last_str = last_corr[0] if last_corr else "—"
    return f"📊 الإجمالي: {count} تصحيح | صور معالَجة: {processed} | آخر تصحيح: {last_str}"

# ── Processing handlers ─────────────────────────────────────────────────────
def process_input(file_obj, lang: str = "ara+eng"):
    """معالجة صورة أو PDF."""
    if file_obj is None:
        return [], "❌ لم يتم رفع ملف", "", ""

    file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    suffix = Path(file_path).suffix.lower()
    log.info("Processing: %s (lang=%s)", file_path, lang)

    gallery_items = []
    all_text = []

    try:
        if suffix == ".pdf":
            if not HAS_PDF:
                return [], "❌ pdf2image غير مثبت — شغّل: pip install pdf2image", "", ""
            with open(file_path, "rb") as f:
                pages = convert_from_bytes(f.read())
            for i, page in enumerate(pages):
                words = segment_words(page)
                for j, (word_img, text) in enumerate(words):
                    out = UPLOADS / f"p{i}_w{j}.png"
                    word_img.save(out)
                    gallery_items.append((str(out), text))
                    all_text.append(text)
        else:
            image = Image.open(file_path).convert("RGB")
            words = segment_words(image)
            for j, (word_img, text) in enumerate(words):
                out = UPLOADS / f"w{j}.png"
                word_img.save(out)
                gallery_items.append((str(out), text))
                all_text.append(text)

        full_text = "\n".join(all_text)
        status = f"✅ تم استخراج {len(gallery_items)} كلمة"
        log.info("Done: %d words", len(gallery_items))
        return gallery_items, status, full_text, full_text
    except Exception as e:
        log.error("process_input failed: %s", e, exc_info=True)
        return [], f"❌ خطأ: {e}", "", ""

def process_scanner(image, mode: str = "all"):
    """معالجة صورة Scanner Fixer."""
    if image is None:
        return None, "❌ لا توجد صورة"
    img = np.array(image.convert("RGB"))
    steps = []

    try:
        if mode in ("deskew", "all"):
            img = deskew(img)
            steps.append("deskew")
        if mode in ("denoise", "all"):
            img_proc = denoise(img)
            img = cv2.cvtColor(img_proc, cv2.COLOR_GRAY2RGB)
            steps.append("denoise")
        if mode in ("contrast", "all"):
            img_proc = enhance_contrast(img)
            img = cv2.cvtColor(img_proc, cv2.COLOR_GRAY2RGB)
            steps.append("contrast")
        if mode in ("crop", "all"):
            img = text_aware_crop(img)
            steps.append("text-aware-crop")

        out_path = EXPORTS / f"processed_{int(time.time()*1000)}.png"
        cv2.imwrite(str(out_path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

        # Log to DB
        conn = init_db()
        conn.execute(
            "INSERT INTO processed_images (original_path, processed_path, mode) VALUES (?, ?, ?)",
            ("upload", str(out_path), mode),
        )
        conn.commit()
        conn.close()

        return Image.fromarray(img), f"✅ {', '.join(steps)} → {out_path.name}"
    except Exception as e:
        log.error("process_scanner failed: %s", e, exc_info=True)
        return None, f"❌ خطأ: {e}"

def process_batch(files, mode: str = "all"):
    """معالجة دفعة + ZIP."""
    if not files:
        return [], "❌ لا توجد ملفات"
    results = []
    for f in files:
        try:
            img = Image.open(f.name if hasattr(f, "name") else f)
            processed, _ = process_scanner(img, mode)
            if processed:
                results.append((np.array(processed), Path(f.name).stem))
        except Exception as e:
            log.warning("Batch item failed: %s → %s", f, e)

    zip_path = EXPORTS / f"batch_{int(time.time())}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for img_arr, name in results:
            buf = io.BytesIO()
            Image.fromarray(img_arr).save(buf, format="PNG")
            z.writestr(f"{name}.png", buf.getvalue())

    return [r[0] for r in results], f"✅ {len(results)} صورة → {zip_path.name}"

def export_jsonl():
    """تصدير JSONL."""
    if not JSONL_PATH.exists():
        return None, "❌ لا توجد تصحيحات"
    return str(JSONL_PATH), f"✅ تم التصدير: {JSONL_PATH.stat().st_size} bytes"

def compute_file_hash(file_obj):
    """SHA256 للملف."""
    if file_obj is None:
        return "—"
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# ── Gradio UI ───────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="OmniMedical OCR (Termux)",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 100% !important; padding: 12px !important; }
        footer { display: none !important; }
        """,
    ) as demo:
        gr.Markdown("""
        # 🏥 OmniMedical OCR — Termux
        يعمل مباشرة على هاتفك Android. كل المعالجة محلية (offline).
        """)

        with gr.Tabs():
            # ── Tab 1: Handwriting Trainer ────────────────────────────────
            with gr.Tab("✍️ Trainer"):
                gr.Markdown("### رفع صورة / PDF → OCR → تصحيح → حفظ")
                with gr.Row():
                    file_input = gr.File(
                        label="📤 ارفع صورة / PDF",
                        file_types=[".png", ".jpg", ".jpeg", ".pdf"],
                    )
                    lang_dd = gr.Dropdown(
                        ["ara+eng", "eng", "deu", "fra"],
                        value="ara+eng",
                        label="🌐 اللغة",
                    )
                    process_btn = gr.Button("🔄 معالجة", variant="primary")

                status_box = gr.Textbox(label="الحالة", interactive=False)
                gallery = gr.Gallery(
                    label="🖼️ الكلمات المُستخرجة",
                    columns=4,
                    height=300,
                )

                with gr.Row():
                    full_text = gr.Textbox(
                        label="📝 النص الأصلي (OCR)",
                        lines=5,
                        interactive=True,
                    )
                    corrected_text = gr.Textbox(
                        label="✏️ التصحيح",
                        lines=5,
                        interactive=True,
                    )

                with gr.Row():
                    save_btn = gr.Button("💾 حفظ التصحيح", variant="primary")
                    export_btn = gr.Button("📤 تصدير JSONL")
                    stats_btn = gr.Button("📊 إحصائيات")

                stats_box = gr.Textbox(label="📊 الإحصائيات", interactive=False)
                export_file = gr.File(label="📥 ملف JSONL", visible=False)

                process_btn.click(
                    process_input,
                    [file_input, lang_dd],
                    [gallery, status_box, full_text, corrected_text],
                )
                save_btn.click(
                    save_correction,
                    [full_text, corrected_text, lang_dd],
                    [status_box],
                )
                export_btn.click(
                    export_jsonl,
                    outputs=[export_file, status_box],
                ).then(lambda: gr.update(visible=True), outputs=[export_file])
                stats_btn.click(get_stats, outputs=[stats_box])

            # ── Tab 2: Scanner Fixer ──────────────────────────────────────
            with gr.Tab("📷 Scanner"):
                gr.Markdown("### معالجة الصور الممسوحة: deskew + denoise + auto-crop")

                with gr.Tab("📝 صورة واحدة"):
                    with gr.Row():
                        input_img = gr.Image(label="📥 الأصل", type="pil")
                        output_img = gr.Image(label="📤 المعالَج", type="pil")
                    mode_dd = gr.Dropdown(
                        ["all", "deskew", "denoise", "contrast", "crop"],
                        value="all",
                        label="⚙️ الوضع",
                    )
                    scan_btn = gr.Button("🔄 معالجة", variant="primary")
                    scan_status = gr.Textbox(label="الحالة", interactive=False)
                    scan_btn.click(
                        process_scanner,
                        [input_img, mode_dd],
                        [output_img, scan_status],
                    )

                with gr.Tab("🗂️ Batch + ZIP"):
                    batch_files = gr.Files(
                        label="📁 ارفع عدة صور",
                        file_types=[".png", ".jpg", ".jpeg"],
                    )
                    batch_mode = gr.Dropdown(
                        ["all", "deskew", "denoise", "contrast", "crop"],
                        value="all",
                        label="⚙️ الوضع",
                    )
                    batch_btn = gr.Button("🔄 معالجة Batch", variant="primary")
                    batch_gallery = gr.Gallery(
                        label="🖼️ النتائج",
                        columns=4,
                        height=300,
                    )
                    batch_status = gr.Textbox(label="الحالة", interactive=False)
                    batch_btn.click(
                        process_batch,
                        [batch_files, batch_mode],
                        [batch_gallery, batch_status],
                    )

            # ── Tab 3: Tools ──────────────────────────────────────────────
            with gr.Tab("🛠️ Tools"):
                gr.Markdown("### أدوات مساعدة")
                with gr.Row():
                    hash_file = gr.File(label="📤 ملف لحساب SHA256")
                    hash_btn = gr.Button("🔍 احسب")
                    hash_out = gr.Textbox(label="SHA256", interactive=False)
                hash_btn.click(compute_file_hash, [hash_file], [hash_out])

                gr.Markdown("---")
                gr.Markdown("### معلومات النظام")
                gr.JSON(value={
                    "workspace": str(WORKSPACE),
                    "db_path": str(DB_PATH),
                    "jsonl_path": str(JSONL_PATH),
                    "logs": str(LOG_PATH),
                    "uploads_dir": str(UPLOADS),
                    "exports_dir": str(EXPORTS),
                    "tesseract_langs": "ara+eng" if os.path.exists("/data/data/com.termux/files/usr/share/tessdata/ara.traineddata") or os.path.exists("/usr/share/tesseract-ocr/4.00/tessdata/ara.traineddata") else "eng",
                    "pdf_support": HAS_PDF,
                    "python_version": sys.version.split()[0],
                    "platform": sys.platform,
                })

        gr.Markdown(f"""
        ---
        **OmniMedical v1.1.0** — [GitHub](https://github.com/DrAbdulmalek/omni-medical-suite)
        | Workspace: `{WORKSPACE}`
        """)

    return demo

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OmniMedical Termux App")
    parser.add_argument("--port", type=int, default=7860, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--share", action="store_true", help="Create public Gradio share link")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    log.info("Building UI...")
    demo = build_ui()

    log.info("Launching on %s:%d (share=%s)", args.host, args.port, args.share)
    print(f"\n{'='*60}")
    print(f"  🏥 OmniMedical OCR (Termux)")
    print(f"  🌐 Open in browser: http://localhost:{args.port}")
    print(f"  📁 Workspace: {WORKSPACE}")
    print(f"  📝 Logs: {LOG_PATH}")
    print(f"{'='*60}\n")

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=args.debug,
        show_error=True,
        prevent_thread_lock=False,
        inbrowser=False,
    )


if __name__ == "__main__":
    main()
