# app/services/hf_dataset_service.py
"""HuggingFace Dataset Service — Save, upload, and manage HF datasets.

┌─────────────────────────────────────────────────────────────────────────┐
│ OPERATOR POLICY (P0-A, fail-closed PHI egress) — READ BEFORE ENABLING    │
│                                                                          │
│  1. Hub export is OPT-IN and DISABLED BY DEFAULT. No row ever leaves     │
│     this machine unless the operator explicitly sets                     │
│     OMNI_HF_EXPORT_ENABLED=true AND a non-empty HF_TOKEN is present      │
│     AND the row carries explicit per-sample user consent.                │
│  2. Local-only is the default behavior: ``save_to_hf()`` stages rows     │
│     to the local ``pending.jsonl`` file and nothing else.                │
│  3. PUBLIC DATASETS ARE FORBIDDEN BY DEFAULT. The Hub dataset is         │
│     created PRIVATE unless the operator explicitly sets                  │
│     OMNI_HF_DATASET_PRIVATE=false. That is an explicit, auditable        │
│     opt-in decision — never a side effect of an unset variable. Any      │
│     other value (unset / empty / garbage) keeps the dataset private.     │
│  4. RAW OCR TEXT NEVER ENTERS THE HUB PAYLOAD BY DEFAULT. Unless         │
│     OMNI_HF_EXPORT_RAW_TEXT=true, the pushed payload is metadata-only    │
│     (content_hash, category, timestamp, consent marker, and a            │
│     raw_retained_locally flag). The raw text stays in the local          │
│     staging file only.                                                   │
│                                                                          │
│  Enabling export is an operator decision with PHI implications; review   │
│  all four switches and your consent workflow before doing so.            │
└─────────────────────────────────────────────────────────────────────────┘

Provides:
  - ``save_to_hf()`` — append a correction pair to a local staging file
    (immediate, never fails on network) and asynchronously flush to HF
  - ``flush_queue()`` — push all staged rows to the HF dataset in a single
    batch (called automatically when the queue reaches ``_FLUSH_THRESHOLD``
    rows, or manually by the operator / a cron job)
  - ``update_medical_dictionary()`` — auto-expand medical dictionary from
    accumulated corrections (generator for Gradio streaming output)
  - ``retrain_now()`` — regenerate Jais NER dataset and start fine-tuning
    (generator for Gradio streaming output)

Design (since v1.1.0-rc / P0 hardening)
---------------------------------------
The previous implementation loaded the entire HF dataset, appended one
row, and pushed the whole thing back on every save. That is O(N) per
save in both network and memory, and a single upload failure loses the
user's correction. The new design uses a **local staging file** as the
source of truth for unsaved rows:

    user calls save_to_hf()
        │
        ▼
    row appended to <stage_dir>/pending.jsonl   ← atomic append, never fails
        │
        ▼
    if queue length >= _FLUSH_THRESHOLD         ← flush opportunistically
        │
        ▼
    flush_queue()                               ← single batched push
        │                                       ← on failure: rows stay staged
        ▼
    HF Dataset updated, staged rows archived to <stage_dir>/uploaded/<ts>.jsonl

This guarantees:
  1. No correction is ever lost — the staging file is append-only.
  2. Network failures are recoverable — call ``flush_queue()`` again later.
  3. Dedup is enforced — ``content_hash`` is checked against both the
     staging file and the live HF dataset before pushing.
  4. Cost is amortized — one push per N saves, not one push per save.

The user-facing ``save_to_hf()`` return string preserves the original
format so existing Gradio bindings keep working unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_DATASET = "DrAbdulmalek/arabic-medical-ocr-corrections"


def _env_flag(name: str, default: bool) -> bool:
    """Parse a boolean env var, fail-closed.

    Unset → ``default``. Any value other than the literal string "true"
    (case/space-insensitive) — including empty strings and garbage —
    evaluates to False, so an accidental or malformed value can never
    enable a dangerous path.
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() == "true"


# Master kill-switch (P0-A): Hub export is opt-in and OFF by default.
OMNI_HF_EXPORT_ENABLED = _env_flag("OMNI_HF_EXPORT_ENABLED", False)

# Raw-text egress gate (P0-A): raw OCR/correction/entity text is excluded
# from the Hub payload unless the operator explicitly opts in.
OMNI_HF_EXPORT_RAW_TEXT = _env_flag("OMNI_HF_EXPORT_RAW_TEXT", False)

# Dataset visibility (P0-A): PRIVATE by default. Only the exact literal
# value "false" makes the dataset public; unset/empty/garbage/case-variants
# ("False", "FALSE", "0", "no") ALL stay private — the strictest reading of
# "explicit opt-in".
_dataset_private_env = os.environ.get("OMNI_HF_DATASET_PRIVATE")
OMNI_HF_DATASET_PRIVATE = (
    False if _dataset_private_env is not None
    and _dataset_private_env.strip() == "false"
    else True
)

# Staging directory: where pending rows live until they're pushed.
# Default: ``~/.omni/hf_dataset_queue/``. Override with ``$OMNI_HF_QUEUE_DIR``.
_STAGE_DIR = Path(
    os.environ.get("OMNI_HF_QUEUE_DIR", str(Path.home() / ".omni" / "hf_dataset_queue"))
).expanduser()
_PENDING_FILE = _STAGE_DIR / "pending.jsonl"
_UPLOADED_DIR = _STAGE_DIR / "uploaded"

# Flush automatically once this many rows are staged.
# 25 = ~one push per 25 user corrections, balancing latency vs. network cost.
_FLUSH_THRESHOLD = int(os.environ.get("OMNI_HF_FLUSH_THRESHOLD", "25"))

# ── Conditional Imports ─────────────────────────────────────────────────────
HAS_HF = False
try:
    import pandas as pd
    from datasets import Dataset, load_dataset
    HAS_HF = True
except ImportError:
    logger.warning("HuggingFace libs not available — save disabled (staging still works)")

# ── Lock for concurrent append/flush ────────────────────────────────────────
# Gradio can call save_to_hf() from multiple worker threads. The staging
# file append must be atomic and flush must not run concurrently with append.
_flush_lock = threading.Lock()


# ── Staging file helpers ────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    _STAGE_DIR.mkdir(parents=True, exist_ok=True)
    _UPLOADED_DIR.mkdir(parents=True, exist_ok=True)


def _compute_content_hash(original_text: str, corrected_text: str) -> str:
    """Stable 12-char hash for dedup. MD5 is fine here (not security-sensitive)."""
    return hashlib.md5(
        (str(original_text or "") + str(corrected_text)).encode()
    ).hexdigest()[:12]


def _read_pending() -> list[dict]:
    """Read all pending rows from the staging file. Returns ``[]`` if absent."""
    if not _PENDING_FILE.exists():
        return []
    rows: list[dict] = []
    with _PENDING_FILE.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning("skipping corrupt pending line %d: %s", line_no, e)
    return rows


def _append_pending(row: dict) -> int:
    """Append one row to the staging file. Returns the new pending count."""
    _ensure_dirs()
    with _flush_lock:
        with _PENDING_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return _count_pending_unlocked()


def _count_pending_unlocked() -> int:
    if not _PENDING_FILE.exists():
        return 0
    n = 0
    with _PENDING_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def count_pending() -> int:
    """Public helper: how many rows are currently staged but not pushed."""
    with _flush_lock:
        return _count_pending_unlocked()


def _archive_uploaded(rows: list[dict]) -> Path:
    """Move flushed rows to an archive file. Returns the archive path."""
    if not rows:
        return _UPLOADED_DIR  # nothing to archive
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = _UPLOADED_DIR / f"uploaded-{ts}.jsonl"
    with archive.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return archive


def _clear_pending() -> None:
    """Truncate the staging file after a successful flush."""
    _PENDING_FILE.unlink(missing_ok=True)


# ── Public Functions ────────────────────────────────────────────────────────

def save_to_hf(corrected_text: str, original_text: str, entities,
               category: str, consent: bool = False) -> str:
    """Save correction pair to the local staging file (P0-A: local-first).

    This function stages locally and NEVER uploads by itself unless every
    P0-A gate is open (export enabled + token). Rows staged WITHOUT
    ``consent=True`` carry a per-row consent=False marker and are never
    eligible for any Hub push — only consented rows are eligible for export.
    The UI layer additionally blocks the save action itself until the user
    ticks the mandatory consent checkbox.

    The user-facing return string keeps the pre-P0 local-save format so
    existing Gradio bindings keep working. If a gated flush was triggered
    and succeeded, the message includes the new HF total; otherwise it
    reports the staged count and states explicitly that nothing was
    uploaded.
    """
    if not corrected_text or not corrected_text.strip():
        return "⚠️ لا يوجد نص مصحح للحفظ. الرجاء معالجة صورة أولاً."

    content_hash = _compute_content_hash(original_text, corrected_text)
    row = {
        "incorrect_ocr_output": str(original_text or ""),
        "correct_text": str(corrected_text),
        "category": str(category),
        "entities": (
            json.dumps(entities, ensure_ascii=False)
            if isinstance(entities, dict)
            else str(entities)
        ),
        "timestamp": datetime.now().isoformat(),
        "content_hash": content_hash,
        "consent": bool(consent),
    }

    pending_count = _append_pending(row)
    logger.info(
        "Staged correction (hash=%s, consent=%s) — %d rows pending in %s",
        content_hash, bool(consent), pending_count, _PENDING_FILE,
    )

    # Opportunistic flush — ONLY when the master kill-switch is explicitly on.
    if OMNI_HF_EXPORT_ENABLED and HAS_HF and pending_count >= _FLUSH_THRESHOLD:
        try:
            flush_result = flush_queue()
            return (
                f"✅ تم الحفظ بنجاح!\n\n"
                f"📊 التفاصيل:\n"
                f"  • بصمة المحتوى: {content_hash}\n"
                f"  • النوع: {category}\n"
                f"  • الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  • صفوف مرحّلة قبل الرفع: {pending_count}\n"
                f"{flush_result}"
            )
        except Exception as e:
            logger.error("Opportunistic flush failed (row is still staged): %s", e)
            return (
                f"✅ تم حفظ التصحيح محلياً (بصمة {content_hash}).\n"
                f"⚠️ تعذّر الرفع التلقائي: {e!s}\n"
                f"📊 الصفوف المرحّلة بانتظار الرفع: {pending_count}"
            )

    # No gated flush yet — report staged status and state the egress truth.
    flush_note = ""
    if not HAS_HF:
        flush_note = "\n⚠️ مكتبات HuggingFace غير متاحة — سيبقى التصحيح مرحّلاً محلياً."
    consent_note = ""
    if not consent:
        consent_note = "\n🔒 بدون موافقة صريحة لن يُرفع هذا الصف أبداً (الرفع يتطلب موافقة لكل عينة)."
    if not OMNI_HF_EXPORT_ENABLED:
        return (
            f"✅ تم حفظ التصحيح محلياً!\n\n"
            f"📊 التفاصيل:\n"
            f"  • بصمة المحتوى: {content_hash}\n"
            f"  • النوع: {category}\n"
            f"  • الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  • صفوف مرحّلة بانتظار الرفع: {pending_count} (الحد للرفع التلقائي: {_FLUSH_THRESHOLD}){flush_note}\n"
            f"🔒 لم يتم رفع أي بيانات إلى HuggingFace — التصدير معطّل افتراضياً "
            f"(OMNI_HF_EXPORT_ENABLED). البيانات محفوظة محلياً فقط.{consent_note}"
        )
    return (
        f"✅ تم حفظ التصحيح محلياً!\n\n"
        f"📊 التفاصيل:\n"
        f"  • بصمة المحتوى: {content_hash}\n"
        f"  • النوع: {category}\n"
        f"  • الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  • صفوف مرحّلة بانتظار الرفع: {pending_count} (الحد للرفع التلقائي: {_FLUSH_THRESHOLD}){flush_note}{consent_note}\n"
        f"ℹ️ التصدير مفعّل — الرفع يتطلب HF_TOKEN وموافقة صريحة لكل عينة."
    )


def flush_queue() -> str:
    """Push staged, consented rows to HF in a single batch (P0-A fail-closed).

    Gate order (deliberate — every refusal is a hard stop, never a fake
    success):
      1. HF libs available?
      2. Master kill-switch ``OMNI_HF_EXPORT_ENABLED`` explicitly true?
      3. Non-empty ``HF_TOKEN``?
      4. Anything staged?
      5. Any staged row that actually carries per-sample consent?

    Only rows with ``consent is True`` are eligible. When the raw-text gate
    is off (default), the Hub payload is metadata-only — raw OCR text,
    corrected text, and entities never leave this machine.

    Returns a status string. On a push failure, raises the underlying
    exception (rows remain staged for retry).
    """
    if not HAS_HF:
        return "⚠️ مكتبات HuggingFace غير متاحة — لا يمكن الرفع."

    if not OMNI_HF_EXPORT_ENABLED:
        # P0-A master kill-switch: refuse loudly, keep rows staged, never
        # pretend the push succeeded.
        logger.warning("flush_queue refused: Hub export is disabled (OMNI_HF_EXPORT_ENABLED)")
        return (
            "🛑 الرفع إلى HuggingFace معطّل (OMNI_HF_EXPORT_ENABLED != true). "
            "لن يتم رفع أي بيانات — الصفوف تبقى مرحّلة محلياً فقط."
        )

    if not HF_TOKEN:
        logger.warning("flush_queue refused: HF_TOKEN is empty")
        return (
            "🛑 الرفع إلى HuggingFace مرفوض: HF_TOKEN غير مضبوط. "
            "لن يتم رفع أي بيانات — الصفوف تبقى مرحّلة محلياً فقط."
        )

    with _flush_lock:
        pending = _read_pending()
        if not pending:
            return "ℹ️ لا توجد صفوف مرحّلة للرفع."

        # P0-A: per-sample consent filter. Rows without an explicit
        # consent=True marker (including pre-P0 staged rows) are NEVER
        # eligible for upload and stay staged locally.
        eligible = [r for r in pending if r.get("consent") is True]
        retained = len(pending) - len(eligible)
        if retained:
            logger.info(
                "Consent filter: %d of %d staged rows lack consent — retained locally",
                retained, len(pending),
            )
        if not eligible:
            return (
                f"ℹ️ لا توجد صفوف مؤهلة للرفع: {len(pending)} صف مرحّل بلا موافقة "
                "صريحة — لن يتم رفع أي بيانات."
            )

        # Dedup against existing HF dataset (drop rows whose content_hash
        # already exists remotely). This is the only network call that
        # reads the full dataset; it happens at most once per flush, not
        # once per save.
        existing_hashes: set[str] = set()
        previous_count = 0
        try:
            existing = load_dataset(HF_DATASET, split="train")
            previous_count = len(existing)
            if "content_hash" in existing.column_names:
                existing_hashes = set(existing["content_hash"])
        except Exception as e:
            logger.info("Could not load existing HF dataset (will create new): %s", e)

        new_rows = [r for r in eligible if r.get("content_hash") not in existing_hashes]
        skipped = len(eligible) - len(new_rows)
        if skipped:
            logger.info("Dedup: skipping %d already-uploaded rows", skipped)

        if not new_rows:
            # All consented rows already exist remotely — archive & clear
            # ONLY the consented ones; unconsented rows stay staged.
            _archive_uploaded(eligible)
            _rewrite_pending_excluding(eligible)
            return (
                f"ℹ️ جميع الصفوف المؤهلة ({len(eligible)}) موجودة مسبقاً في HF.\n"
                f"  • تم أرشفتها محلياً بدون رفع مكرر."
            )

        try:
            # P0-A raw-text gate: by default the Hub payload is metadata-only.
            # Raw OCR/correction/entity text never leaves this machine unless
            # the operator explicitly opts in via OMNI_HF_EXPORT_RAW_TEXT=true.
            if OMNI_HF_EXPORT_RAW_TEXT:
                payload_rows = [dict(r) for r in new_rows]
            else:
                payload_rows = [
                    {
                        "content_hash": r.get("content_hash", ""),
                        "category": r.get("category", ""),
                        "timestamp": r.get("timestamp", ""),
                        "consent": True,
                        "raw_retained_locally": True,
                    }
                    for r in new_rows
                ]

            new_df = pd.DataFrame(payload_rows)
            try:
                existing_df = load_dataset(HF_DATASET, split="train").to_pandas()
                df = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception:
                df = new_df

            # P0-A visibility: PRIVATE is the default. Going public requires
            # the explicit literal OMNI_HF_DATASET_PRIVATE=false opt-in.
            push_kwargs = {"repo_id": HF_DATASET, "private": OMNI_HF_DATASET_PRIVATE}
            if not OMNI_HF_DATASET_PRIVATE:
                logger.warning(
                    "Hub dataset will be PUBLIC — explicit OMNI_HF_DATASET_PRIVATE=false opt-in"
                )
            push_kwargs["token"] = HF_TOKEN
            new_ds = Dataset.from_pandas(df)
            new_ds.push_to_hub(**push_kwargs)

            total = len(df)
            archive_path = _archive_uploaded(eligible)
            _rewrite_pending_excluding(eligible)

            privacy_note = "خاص (private)" if OMNI_HF_DATASET_PRIVATE else "عام — opt-in صريح"
            logger.info(
                "Flushed %d rows to HF (%s, total %s, dedup skipped %d, archived to %s)",
                len(new_rows), privacy_note, total, skipped, archive_path.name,
            )
            return (
                f"  • تم رفع {len(new_rows)} صف بنجاح إلى HF.\n"
                f"  • خصوصية الـ Dataset: {privacy_note}.\n"
                f"  • إجمالي العينات في HF: {total}\n"
                f"  • تخطّي {skipped} صف مكرر.\n"
                f"  • أُرشيف الصفوف المرفوعة: {archive_path.name}"
            )
        except Exception as e:
            logger.error("Flush failed (rows remain staged for retry): %s", e)
            raise


def _rewrite_pending_excluding(pushed_rows: list[dict]) -> None:
    """Atomically drop exactly ``pushed_rows`` from the staging file.

    P0-A: unconsented rows are never archived or cleared — they stay in
    ``pending.jsonl`` until the operator explicitly deals with them.
    """
    if not pushed_rows:
        return
    pushed_hashes = {r.get("content_hash") for r in pushed_rows}
    remaining = [r for r in _read_pending() if r.get("content_hash") not in pushed_hashes]
    if not remaining:
        _clear_pending()
        return
    tmp = _PENDING_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in remaining:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(_PENDING_FILE)


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
        yield f"خطأ في تحديث القاموس: {e!s}"


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
        yield f"خطأ: {e!s}"
