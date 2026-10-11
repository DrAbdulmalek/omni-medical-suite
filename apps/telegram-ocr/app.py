# apps/telegram-ocr/app.py
"""
Telegram OCR Studio — استوديو التعرف الضوئي لملفات تيليجرام
=============================================================
واجهة Gradio عربية (RTL) تدمج:

  1) جلب ملفات القنوات (صور/PDF) عبر جلسة Telethon الخاصة بالمالك
  2) تشغيل خط OCR محلي بالكامل (Tesseract ara+eng + معالجة مسبقة)
  3) نظام قصاصات بأسلوب ABBYY FineReader: اقتطاع حرف/كلمة/سطر وتعليقه بنصه الصحيح
  4) مكتبة أنماط (字模) تتعلم من القصاصات وتُستخدم لتحسين التعرف لاحقاً
  5) قاعدة بيانات تدريب على GitHub: مزامنة القصاصات والأنماط إلى مستودع خاص

التشغيل:
    python apps/telegram-ocr/app.py          # المنفذ 7861 افتراضياً
بيئة اختيارية:
    OMNI_TG_OCR_PORT=7861  OMNI_TRAINING_DB_DIR=...  OMNI_TESSDATA_PREFIX=...
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

import cv2
import gradio as gr
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram-ocr-ui")

# ── bootstrap suite imports ─────────────────────────────────────────────────
SUITE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SUITE_ROOT not in sys.path:
    sys.path.insert(0, SUITE_ROOT)

from app.services import telegram_ingest as tgi          # noqa: E402
from app.services import telegram_ocr_service as tgo     # noqa: E402
from src.ocr.pattern_store import PatternStore           # noqa: E402
from src.ocr.slice_store import SliceStore               # noqa: E402
from src.ocr.training_export import export_all           # noqa: E402

REPO_URL = "https://github.com/DrAbdulmalek/omni-ocr-training-db"

CSS = """
.gradio-container {direction: rtl; text-align: right;}
.num, .prose {direction: rtl;}
table {direction: rtl;}
footer {visibility: hidden;}
"""


# ── helpers ──────────────────────────────────────────────────────────────────
def _training_db() -> str:
    return os.getenv("OMNI_TRAINING_DB_DIR") or os.path.join(SUITE_ROOT, "data", "training_db")


def inbox_files() -> list:
    base = tgi.inbox_dir()
    out = []
    for root, _d, names in os.walk(base):
        for name in sorted(names):
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in tgo.SUPPORTED_IMAGE_EXT or ext == ".pdf":
                out.append(path)
    return out


def status_block() -> str:
    tg = tgi.credentials_status()
    eng = tgo.engine_status()
    try:
        slices = SliceStore(_training_db()).stats()
        patterns = PatternStore(_training_db()).stats()
    except Exception:
        slices, patterns = {}, {}
    arrow = "✅" if tg.get("credentials") else "❌"
    ara = "✅" if eng.get("arabic") else "❌"
    pdf = "✅" if eng.get("pdf") else "❌"
    return (
        f"### حالة النظام\n"
        f"| المكوّن | الحالة |\n|---|---|\n"
        f"| بيانات تيليجرام | {arrow} |\n"
        f"| محرك Tesseract | {'✅' if eng.get('tesseract') else '❌'} |\n"
        f"| اللغة العربية | {ara} |\n"
        f"| معالجة PDF | {pdf} |\n"
        f"| القصاصات | {slices.get('slices', 0)} (متزامنة {slices.get('synced', 0)}) |\n"
        f"| الأنماط | {patterns.get('patterns', 0)} |"
    )


def probe_telegram() -> str:
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        creds = tgi._load_credentials()

        async def inner():
            async with TelegramClient(StringSession(creds["session"]), creds["api_id"],
                                      creds["api_hash"], connection_retries=2, timeout=20) as c:
                me = await c.get_me()
                return me.first_name or str(me.id)
        name = asyncio.run(inner())
        return f"✅ الجلسة حية — الحساب: **{name}**"
    except Exception as exc:
        return f"❌ فشل الاتصال: {type(exc).__name__}: {str(exc)[:120]}"


def list_files(channel: str, limit: int):
    if not channel.strip():
        raise gr.Error("أدخل معرف القناة (@username أو الرابط أو الـ id)")
    rows = tgi.list_channel_files(channel.strip(), limit=int(limit))
    if not rows:
        return [["—", "لا توجد ملفات صور/PDF في آخر الرسائل", "—", "—", "—"]]
    return [[r["msg_id"], r["name"], r["kind"], f"{r['size']:,}",
             time.strftime("%Y-%m-%d %H:%M", time.localtime(r["date"])) if r["date"] else "—"]
            for r in rows]


def download_one(channel: str, msg_id: float):
    if not channel.strip() or not msg_id:
        raise gr.Error("حدّد القناة ورقم الرسالة (msg_id)")
    info = tgi.download_channel_file(channel.strip(), int(msg_id))
    files = inbox_files()
    return (f"✅ نُزّل: `{info['path']}`", gr.update(choices=files, value=info["path"]))


def download_newest(channel: str, count: float):
    if not channel.strip():
        raise gr.Error("أدخل معرف القناة أولاً")
    results = tgi.download_latest(channel.strip(), int(count))
    files = inbox_files()
    last = results[-1]["path"] if results else None
    return (f"✅ نُزّل {len(results)} ملفاً إلى صندوق الاستلام",
            gr.update(choices=files, value=last))


def refresh_inbox():
    files = inbox_files()
    return gr.update(choices=files, value=(files[0] if files else None))


# ── OCR tab handlers ─────────────────────────────────────────────────────────
def run_ocr(path: str, lang: str, use_patterns: bool):
    if not path:
        raise gr.Error("اختر ملفاً من صندوق الاستلام (نزّل واحداً من تبويب القناة)")
    result = tgo.run_ocr(path, lang=lang, use_patterns=use_patterns)
    page_img = tgo.load_image(path) if not tgo.is_pdf(path) else tgo.pdf_to_images(path)[0]
    annotated = tgo.draw_boxes(page_img, result["words"])
    stats = result["stats"]
    stats_txt = (f"⏱️ {stats['elapsed_s']} ثانية | "
                 f"كلمات: {stats['words']} | "
                 f"مُصحّحة بالأنماط: {stats['pattern_refined']}")
    return annotated, result["text"], stats_txt, result


def bbox_editor_rows(path: str, ocr_result):
    """Build editable rows from actual OCR word boxes; never fabricate boxes."""
    if not path or not ocr_result:
        raise gr.Error("شغّل OCR على ملف من صندوق الاستلام أولاً")
    rows = []
    for index, word in enumerate(ocr_result.get("words", [])[:500], start=1):
        if word.get("page", 1) != 1:
            continue
        bbox = word.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x, y, width, height = bbox
        rows.append([str(index), int(x), int(y), int(width), int(height),
                     str(word.get("text", "")), "word"])
    if not rows:
        raise gr.Error("لم يعثر OCR على مربعات كلمات صالحة في الصفحة الأولى")
    return rows


def save_bbox_editor_rows(path, rows, reviewed, lang):
    """Persist only rows explicitly reviewed by a human in the editable table."""
    if not reviewed:
        raise gr.Error("يجب تأكيد مراجعة النصوص والإحداثيات قبل حفظ بيانات التدريب")
    if not path:
        raise gr.Error("اختر ملفاً من صندوق الاستلام أولاً")
    if rows is None:
        raise gr.Error("لا توجد صفوف للحفظ")
    if hasattr(rows, "to_numpy"):
        rows = rows.to_numpy().tolist()
    if not isinstance(rows, (list, tuple)) or not rows:
        raise gr.Error("أضف صفاً واحداً على الأقل")
    # Resolve the selected source against the actual inbox, rejecting traversal
    # and symlink escapes even if the UI input is tampered with.
    inbox_root = os.path.realpath(os.path.abspath(tgi.inbox_dir()))
    source_path = os.path.realpath(os.path.abspath(path))
    try:
        inside = os.path.commonpath([inbox_root, source_path]) == inbox_root
    except ValueError:
        inside = False
    if not inside or not os.path.isfile(source_path):
        raise gr.Error("مصدر الصورة يجب أن يكون ملفاً عادياً داخل صندوق الاستلام")
    image = tgo.load_image(source_path) if not tgo.is_pdf(source_path) else tgo.pdf_to_images(source_path)[0]
    height, width = image.shape[:2]
    store = SliceStore(_training_db())
    saved = 0
    for line_no, row in enumerate(rows, start=1):
        if not row or len(row) < 7:
            raise gr.Error(f"الصف {line_no}: الأعمدة المطلوبة هي ID وX وY وW وH والنص والمستوى")
        _row_id, x, y, box_w, box_h, text, level = row[:7]
        if not str(text or "").strip():
            continue
        try:
            x, y, box_w, box_h = (int(float(value)) for value in (x, y, box_w, box_h))
        except (TypeError, ValueError, OverflowError):
            raise gr.Error(f"الصف {line_no}: الإحداثيات يجب أن تكون أعداداً صحيحة")
        if x < 0 or y < 0 or box_w <= 0 or box_h <= 0 or x >= width or y >= height:
            raise gr.Error(f"الصف {line_no}: الإحداثيات خارج حدود الصورة")
        if x + box_w > width or y + box_h > height:
            raise gr.Error(f"الصف {line_no}: المربع يتجاوز حدود الصورة")
        level = str(level or "").strip().lower()
        if level not in {"char", "word", "line"}:
            raise gr.Error(f"الصف {line_no}: المستوى يجب أن يكون char أو word أو line")
        store.add_slice(
            image, [x, y, box_w, box_h], str(text).strip(),
            level=level, lang=lang,
            source_meta={"kind": "human_reviewed_gradio_bbox_editor",
                         "file": os.path.basename(source_path),
                         "human_reviewed": True},
        )
        saved += 1
    if saved == 0:
        raise gr.Error("لم تُحفظ أي قصاصة: تحقق من النصوص في الجدول")
    return f"✅ حُفظت {saved} قصاصة بعد تأكيد المراجعة البشرية", recent_slices_rows()


def suggest_slices(path: str, ocr_result):
    """Word-level candidate crops from tesseract boxes (or last OCR result)."""
    if not path:
        raise gr.Error("اختر ملفاً أولاً")
    page_img = tgo.load_image(path) if not tgo.is_pdf(path) else tgo.pdf_to_images(path)[0]
    if ocr_result and ocr_result.get("words"):
        words = [w for w in ocr_result["words"] if w.get("page", 1) == 1]
    else:
        gray = tgo.preprocess(page_img)
        data = tgo._image_to_data(gray, "ara+eng", 6)
        _, words = tgo._group_lines(data)
    crops = []
    meta = []
    for w in words[:60]:
        x, y, ww, hh = w["bbox"]
        if ww < 6 or hh < 6:
            continue
        crops.append(page_img[max(0, y - 2):y + hh + 2, max(0, x - 2):x + ww + 2])
        meta.append({"bbox": w["bbox"], "suggested": w["text"]})
    if not crops:
        raise gr.Error("لم يُعثر على مقاطع كلمات — جرّب الاقتطاع اليدوي")
    gallery = [(c, f"{m['suggested']}") for c, m in zip(crops, meta)]
    return gallery, meta, page_img


def on_candidate_select(evt: gr.SelectData, candidates):
    idx = evt.index or 0
    if not candidates or idx >= len(candidates):
        return gr.update(), gr.update(), "—"
    bbox = candidates[idx]["bbox"]
    return bbox[0], bbox[1], f"{bbox[2]}×{bbox[3]}"


def preview_crop(path, x, y, wh):
    if not path or not wh or "×" not in str(wh):
        return None
    try:
        w, h = [int(v) for v in str(wh).split("×")]
        img = tgo.load_image(path) if not tgo.is_pdf(path) else tgo.pdf_to_images(path)[0]
        x, y = int(x or 0), int(y or 0)
        return img[y:y + h, x:x + w]
    except Exception:
        return None


def save_slice(path, ocr_result, x, y, wh, text, level, lang):
    if not path:
        raise gr.Error("اختر الملف المصدر أولاً")
    if not text.strip():
        raise gr.Error("اكتب النص الصحيح للقصاصة")
    if not wh or "×" not in str(wh):
        raise gr.Error("حدّد الأبعاد (w×h) — اختر مقطعاً من المعرض أو أدخلها يدوياً")
    w, h = [int(v) for v in str(wh).split("×")]
    src = {"kind": "upload", "file": os.path.basename(path)}
    if ocr_result and ocr_result.get("source"):
        src = dict(ocr_result["source"])
        src["file"] = os.path.basename(path)
    store = SliceStore(_training_db())
    rec = store.add_slice(tgo.load_image(path) if not tgo.is_pdf(path)
                          else tgo.pdf_to_images(path)[0],
                          [int(x or 0), int(y or 0), w, h],
                          text.strip(), level=level, lang=lang, source_meta=src)
    rows = recent_slices_rows()
    return (f"✅ حُفظت القصاصة `{rec['id']}` — المستوى: {level}", rows,
            gr.update(value=None))


def recent_slices_rows(limit: int = 25):
    store = SliceStore(_training_db())
    rows = []
    for r in store.list_slices(limit=limit):
        rows.append([r["id"], r["text"][:40], r["level"], r["lang"],
                     time.strftime("%m-%d %H:%M", time.localtime(r["created_at"]))])
    return rows


# ── patterns handlers ────────────────────────────────────────────────────────
def learn_patterns():
    db = _training_db()
    s_store = SliceStore(db)
    p_store = PatternStore(db)
    learned = skipped = 0
    for rec in s_store.list_slices(limit=10_000):
        img = s_store.image_of(rec)
        if img is None:
            skipped += 1
            continue
        try:
            p_store.add_pattern(rec["text"], img, level=rec.get("level", "word"),
                                script="ar" if rec.get("lang", "ar") == "ar" else "en",
                                source_ref=f"slices/{rec['id']}")
            learned += 1
        except ValueError:
            skipped += 1
    stats = p_store.stats()
    return (f"✅ تعلّم من القصاصات: {learned} نمطاً (تم تخطي {skipped}) — "
            f"الإجمالي الآن {stats['patterns']} نمطاً", patterns_rows(), patterns_gallery())


def patterns_rows(limit: int = 60):
    store = PatternStore(_training_db())
    return [[p["label"], p["level"], p["script"], p["count"], p["key"]]
            for p in store.list_patterns()[:limit]]


def patterns_gallery(limit: int = 40):
    store = PatternStore(_training_db())
    items = []
    for p in store.list_patterns()[:limit]:
        bmp = store.bitmap_of(p["key"])
        if bmp is not None:
            items.append((cv2.cvtColor(bmp, cv2.COLOR_GRAY2RGB), f"{p['label']} (×{p['count']})"))
    return items


def test_pattern(path, x, y, wh):
    if not path or not wh or "×" not in str(wh):
        raise gr.Error("اختر ملفاً وحدّد الأبعاد أولاً")
    w, h = [int(v) for v in str(wh).split("×")]
    img = tgo.load_image(path) if not tgo.is_pdf(path) else tgo.pdf_to_images(path)[0]
    crop = img[int(y or 0):int(y or 0) + h, int(x or 0):int(x or 0) + w]
    hits = PatternStore(_training_db()).match(crop, top_k=5, min_score=0.5)
    if not hits:
        return "لا توجد مطابقات قريبة — تعلّم نمطاً جديداً من القصاصات أولاً"
    return "\n".join(f"- **{h['label']}** — ثقة {h['score']:.2f}" for h in hits)


# ── training-db handlers ─────────────────────────────────────────────────────
def db_stats():
    s = SliceStore(_training_db()).stats()
    p = PatternStore(_training_db()).stats()
    return (f"### قاعدة بيانات التدريب\n"
            f"| المؤشر | القيمة |\n|---|---|\n"
            f"| القصاصات | {s.get('slices', 0)} |\n"
            f"| متزامنة مع GitHub | {s.get('synced', 0)} |\n"
            f"| بانتظار المزامنة | {s.get('pending', 0)} |\n"
            f"| الأنماط | {p.get('patterns', 0)} |\n"
            f"| استخدامات الأنماط | {p.get('occurrences', 0)} |")


def privacy_review_choices(limit: int = 500):
    """List training samples for explicit one-at-a-time privacy review."""
    rows = SliceStore(_training_db()).list_slices(limit=limit)
    return [row["id"] for row in rows if row.get("id")]


def preview_privacy_sample(sample_id):
    if not sample_id:
        raise gr.Error("اختر عينة تدريب لمراجعتها")
    store = SliceStore(_training_db())
    record = next((r for r in store.list_slices(limit=10000)
                   if r.get("id") == sample_id), None)
    if record is None:
        raise gr.Error("العينة غير موجودة في قاعدة التدريب")
    image = store.image_of(record)
    if image is None:
        raise gr.Error("ملف صورة العينة غير موجود")
    return image, (
        f"**المعرّف:** `{record['id']}`\n\n"
        f"**النص المراد تدريبه:** {record.get('text', '')}\n\n"
        f"**المستوى/اللغة:** {record.get('level', '?')} / {record.get('lang', '?')}\n\n"
        "افحص الصورة والنص معاً قبل اعتماد هذه العينة."
    )


def record_privacy_review(sample_id, deidentified, consent_confirmed, reviewer):
    """Append an explicit review decision for one exact sample ID."""
    if not sample_id:
        raise gr.Error("اختر عينة محددة أولاً")
    reviewer = str(reviewer or "").strip()
    if not reviewer:
        raise gr.Error("أدخل معرّف المراجع أو اسم حسابه")
    approved = bool(deidentified and consent_confirmed)
    store = SliceStore(_training_db())
    record = next((r for r in store.list_slices(limit=10000)
                   if r.get("id") == sample_id), None)
    if record is None:
        raise gr.Error("العينة غير موجودة؛ حدّث القائمة")
    review = {
        "sample_id": sample_id,
        "approved": approved,
        "deidentified": bool(deidentified),
        "consent_confirmed": bool(consent_confirmed),
        "reviewer": reviewer,
        "reviewed_at": int(time.time()),
    }
    ledger_path = os.path.join(_training_db(), "privacy_reviews.jsonl")
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(review, ensure_ascii=False) + "\n")
    return (
        (f"✅ اعتُمدت العينة `{sample_id}` بعد مراجعتها." if approved else
         f"⛔ سُجل رفض العينة `{sample_id}`؛ ستظل المزامنة محظورة ما لم تُراجع وتُعتمد لاحقاً."),
        gr.update(choices=privacy_review_choices(), value=None),
    )


def run_export():
    summary = export_all(_training_db())
    meta = summary["slices"]
    return (f"✅ صُدّرت {meta['total']} قصاصة إلى `{summary['out_dir']}` "
            f"(train {meta['splits']['train']} / val {meta['splits']['val']} / "
            f"test {meta['splits']['test']})")


def run_sync(confirmed: bool = False):
    if not confirmed:
        return ("⛔ لم تبدأ المزامنة. راجع البيانات وأكّد صراحةً خلو الدفعة من المعلومات الشخصية غير المصرح بها.", db_stats(), False)
    script = os.path.join(SUITE_ROOT, "scripts", "trainingdb_sync.py")
    import subprocess
    proc = subprocess.run([sys.executable, script], capture_output=True, text=True,
                          cwd=SUITE_ROOT, timeout=600)
    log = (proc.stdout + proc.stderr)[-3000:]
    return f"رمز الخروج: {proc.returncode}\n```\n{log}\n```", db_stats(), False


# ── UI composition ───────────────────────────────────────────────────────────
def build_ui() -> gr.Blocks:
    with gr.Blocks(title="استوديو التعرف الضوئي — تيليجرام", css=CSS) as demo:
        gr.Markdown(
            "# 📄 استوديو التعرف الضوئي لتيليجرام\n"
            "جلب ملفات القنوات → تعرف ضوئي محلي → قصاصات معلّقة → أنماط متعلمة → "
            "قاعدة بيانات تدريب على GitHub (بأسلوب ABBYY FineReader)")
        ocr_state = gr.State(None)
        candidates_state = gr.State([])
        page_state = gr.State(None)
        status_md = gr.Markdown(status_block())

        with gr.Tab("📡 القناة"):
            gr.Markdown("اربط القناة التي تنشر فيها المستندات الممسوحة ضوئياً. "
                        "يقبل الحقل: `@username` أو رابط `t.me/...` أو المعرف الرقمي.")
            with gr.Row():
                channel_in = gr.Textbox(label="معرف القناة", placeholder="@my_channel",
                                        scale=3)
                limit_in = gr.Slider(5, 200, value=50, step=5, label="أقصى عدد رسائل",
                                     scale=1)
            with gr.Row():
                probe_btn = gr.Button("🔌 فحص الجلسة", variant="secondary")
                list_btn = gr.Button("📂 عرض الملفات القابلة للتعرف", variant="primary")
            probe_out = gr.Markdown()
            files_df = gr.Dataframe(headers=["msg_id", "الاسم", "النوع", "الحجم (بايت)",
                                             "التاريخ"],
                                    label="ملفات القناة", interactive=False)
            with gr.Row():
                msg_id_in = gr.Number(label="رقم رسالة الملف (msg_id)", precision=0)
                dl_one_btn = gr.Button("⬇️ تنزيل هذا الملف")
                dl_n_in = gr.Slider(1, 20, value=5, step=1, label="تنزيل أحدث N ملفاً")
                dl_n_btn = gr.Button("⬇️ تنزيل الأحدث", variant="primary")
            dl_out = gr.Markdown()

            probe_btn.click(probe_telegram, None, probe_out)
            list_btn.click(list_files, [channel_in, limit_in], files_df)
            # NOTE: download button .click registrations happen after file_dd is
            # defined (OCR tab) — see register_cross_tab_handlers() below.

        with gr.Tab("🔍 التعرف الضوئي"):
            with gr.Row():
                file_dd = gr.Dropdown(label="ملفات صندوق الاستلام", choices=inbox_files(),
                                      interactive=True, scale=4)
                inbox_refresh = gr.Button("🔄 تحديث القائمة", scale=1)
            with gr.Row():
                lang_in = gr.Radio(["ara+eng", "ara", "eng"], value="ara+eng",
                                   label="اللغات")
                patterns_in = gr.Checkbox(value=True,
                                          label="تحسين بالأنماط المتعلمة (字模)")
                ocr_btn = gr.Button("▶️ تشغيل التعرف", variant="primary", scale=1)
            ocr_stats = gr.Markdown()
            with gr.Row():
                ocr_image = gr.Image(label="الصورة مع حدود الكلمات "
                                           "(البرتقالي = مُصحّح بالأنماط)", height=420)
                ocr_text = gr.Textbox(label="النص المستخرج (قابل للتحرير)", lines=14,
                                      interactive=True)
            inbox_refresh.click(refresh_inbox, None, file_dd)
            ocr_btn.click(run_ocr, [file_dd, lang_in, patterns_in],
                          [ocr_image, ocr_text, ocr_stats, ocr_state])

            gr.Markdown("### مراجعة مربعات الكلمات وتعديلها")
            gr.Markdown("يعرض الجدول مربعات OCR الحقيقية للصفحة الأولى. عدّل X/Y/W/H أو النص أو أضف صفاً؛ الحفظ يتطلب تأكيد المراجعة البشرية.")
            bbox_load_btn = gr.Button("📋 تحميل مربعات OCR إلى الجدول")
            bbox_table = gr.Dataframe(
                headers=["ID", "X", "Y", "W", "H", "النص الصحيح", "المستوى"],
                datatype=["str", "number", "number", "number", "number", "str", "str"],
                label="جدول تعديل المربعات (إحداثيات الصورة بالبكسل)",
                interactive=True, row_count=(1, "dynamic"), col_count=(7, "fixed"),
            )
            bbox_lang = gr.Radio(["ar", "en"], value="ar", label="لغة بيانات التدريب")
            bbox_reviewed = gr.Checkbox(
                label="أؤكد أنني راجعت النصوص والإحداثيات، وأوافق على حفظ هذه القصاصات محلياً لأغراض التدريب",
                value=False,
            )
            bbox_save_btn = gr.Button("💾 حفظ القصاصات التي راجعتها", variant="primary")
            bbox_save_status = gr.Markdown()
            bbox_recent = gr.Dataframe(
                headers=["المعرف", "النص", "المستوى", "اللغة", "التاريخ"],
                label="أحدث القصاصات بعد الحفظ", value=recent_slices_rows(), interactive=False,
            )
            bbox_load_btn.click(bbox_editor_rows, [file_dd, ocr_state], bbox_table)
            bbox_save_btn.click(
                save_bbox_editor_rows, [file_dd, bbox_table, bbox_reviewed, bbox_lang],
                [bbox_save_status, bbox_recent],
            )

        with gr.Tab("✂️ القصاصات"):
            gr.Markdown("### اقتطاع حرف/كلمة/سطر وتعليقه بنصه الصحيح (قصاصات ABBYY)\n"
                        "اختر مقطعاً من المعرض المقترح أو أدخل الموضع يدوياً، صحّح النص "
                        "المقترح، ثم احفظ. كل قصاصة تصبح بذرة معرفة للنظام.")
            with gr.Row():
                with gr.Column(scale=3):
                    suggest_btn = gr.Button("🧩 توليد مقاطع مقترحة (كلمات)",
                                            variant="primary")
                    cand_gallery = gr.Gallery(label="المقاطع المقترحة (اختر واحداً)",
                                              columns=6, height=220)
                with gr.Column(scale=2):
                    slice_x = gr.Number(label="x", precision=0, value=0)
                    slice_y = gr.Number(label="y", precision=0, value=0)
                    slice_wh = gr.Textbox(label="الأبعاد w×h", value="—")
                    preview_btn = gr.Button("👁️ معاينة القصاصة")
                    crop_preview = gr.Image(label="معاينة", height=140)
            with gr.Row():
                slice_text = gr.Textbox(label="النص الصحيح (عدّل المقترح إن كان خاطئاً)",
                                        scale=3)
                slice_level = gr.Radio(["char", "word", "line"], value="word",
                                       label="المستوى", scale=1)
                slice_lang = gr.Radio(["ar", "en"], value="ar", label="اللغة", scale=1)
                save_slice_btn = gr.Button("💾 حفظ القصاصة", variant="primary", scale=1)
            slice_out = gr.Markdown()
            slices_df = gr.Dataframe(headers=["المعرف", "النص", "المستوى", "اللغة",
                                              "التاريخ"],
                                     label="أحدث القصاصات", value=recent_slices_rows(),
                                     interactive=False)

            suggest_btn.click(suggest_slices, [file_dd, ocr_state],
                              [cand_gallery, candidates_state, page_state])
            cand_gallery.select(on_candidate_select, [candidates_state],
                                [slice_x, slice_y, slice_wh])
            preview_btn.click(preview_crop, [file_dd, slice_x, slice_y, slice_wh],
                              crop_preview)
            save_slice_btn.click(save_slice,
                                 [file_dd, ocr_state, slice_x, slice_y, slice_wh,
                                  slice_text, slice_level, slice_lang],
                                 [slice_out, slices_df, crop_preview])

        with gr.Tab("🧠 الأنماط"):
            gr.Markdown("### مكتبة الأنماط (字模)\n"
                        "النمط = قالب ثنائي 96×48 لنص معروف. عند ظهور الشكل نفسه في "
                        "مسح جديد يستبدله النظام بالنص المتعلم تلقائياً.")
            learn_btn = gr.Button("🎓 تعلّم من كل القصاصات", variant="primary")
            learn_out = gr.Markdown()
            with gr.Row():
                pat_gallery = gr.Gallery(label="الأنماط المتعلمة", columns=8, height=200)
            pat_df = gr.Dataframe(headers=["النص", "المستوى", "اللغة", "التكرار",
                                           "المعرف"],
                                  label="جدول الأنماط", interactive=False)
            gr.Markdown("#### تجربة مطابقة: حدّد مقطعاً من تبويب القصاصات ثم جرّب هنا")
            test_btn = gr.Button("🔎 مطابقة المقطع الحالي مع المكتبة")
            test_out = gr.Markdown()

            learn_btn.click(learn_patterns, None, [learn_out, pat_df, pat_gallery])
            test_btn.click(test_pattern, [file_dd, slice_x, slice_y, slice_wh], test_out)

        with gr.Tab("🗄️ قاعدة بيانات GitHub"):
            gr.Markdown(f"المستودع الخاص: [{REPO_URL.split('/')[-1]}]({REPO_URL}) — "
                        "يُحدَّث بـ git push من هذا الجهاز، ويُستخدم لاحقاً لتدريب نموذج "
                        "تعرف ضوئي عربي مخصص.")
            stats_md = gr.Markdown(db_stats())
            gr.Markdown(
                "### مراجعة الخصوصية لكل عينة قبل المزامنة\n"
                "افتح كل قصاصة على حدة، وتحقق من الصورة والنص. لا تعتمدها إلا إذا "
                "تحققت من إزالة بيانات التعريف ووجود الموافقة المناسبة.")
            with gr.Row():
                privacy_slice_id = gr.Dropdown(
                    choices=privacy_review_choices(), label="معرّف العينة", value=None)
                privacy_reviewer = gr.Textbox(
                    label="معرّف المراجع / حسابه", placeholder="reviewer-id")
            with gr.Row():
                privacy_deidentified = gr.Checkbox(
                    label="تحققت من خلو هذه العينة من معلومات تعريف المريض", value=False)
                privacy_consent = gr.Checkbox(
                    label="تأكدت من وجود الموافقة المناسبة لاستخدام هذه العينة", value=False)
            privacy_preview_btn = gr.Button("🔎 عرض العينة المختارة")
            privacy_image = gr.Image(label="صورة العينة", interactive=False)
            privacy_details = gr.Markdown()
            privacy_review_btn = gr.Button("✅ تسجيل مراجعة هذه العينة")
            privacy_review_status = gr.Markdown()
            privacy_preview_btn.click(
                preview_privacy_sample, [privacy_slice_id], [privacy_image, privacy_details])
            privacy_review_btn.click(
                record_privacy_review,
                [privacy_slice_id, privacy_deidentified, privacy_consent, privacy_reviewer],
                [privacy_review_status, privacy_slice_id],
            )
            sync_confirm = gr.Checkbox(
                label="أؤكد أنني راجعت دفعة البيانات المراد رفعها، وأزلت أو أخفيت هوية المرضى، ولدي الموافقة اللازمة لمشاركتها في مستودع التدريب الخاص",
                value=False,
            )
            with gr.Row():
                export_btn = gr.Button("📦 تجهيز حزمة تدريب (train/val/test)")
                sync_btn = gr.Button("☁️ مزامنة مع GitHub الآن", variant="primary")
            export_out = gr.Markdown()
            sync_log = gr.Textbox(label="سجل المزامنة", lines=8, interactive=False)

            export_btn.click(run_export, None, export_out)
            sync_btn.click(run_sync, [sync_confirm], [sync_log, stats_md, sync_confirm])

        # ── cross-tab wiring (needs file_dd from the OCR tab) ──
        dl_one_btn.click(download_one, [channel_in, msg_id_in], [dl_out, file_dd])
        dl_n_btn.click(download_newest, [channel_in, dl_n_in], [dl_out, file_dd])

        def initial_state():
            files = inbox_files()
            return status_block(), gr.update(choices=files, value=(files[0] if files else None))

        demo.load(initial_state, None, [status_md, file_dd])
    return demo


if __name__ == "__main__":
    demo = build_ui()
    port = int(os.getenv("OMNI_TG_OCR_PORT", "7861"))
    logger.info("launching Telegram OCR Studio on port %s", port)
    demo.launch(server_name=os.getenv("OMNI_TG_OCR_HOST", "127.0.0.1"), server_port=port, share=False)
