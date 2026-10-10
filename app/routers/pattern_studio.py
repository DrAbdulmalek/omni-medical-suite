"""واجهة تدريب الأنماط: قصاصة حرف/كلمة + جلب ملف تيليجرام.

رمز البوت يُقرأ من البيئة فقط ولا يُعاد في أي استجابة.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.security import get_current_user
from app.db.models.auth import User
from packages.learning.confusions_ar import suggest
from packages.learning.pattern_db import PatternDB
from packages.learning.snippet_dataset import export_confirmed, normalize_record

router = APIRouter()
_FILE_ID = re.compile(r"^[A-Za-z0-9_:\-]{8,256}$")
_MAX_BYTES = 8_000_000


class SnippetIn(BaseModel):
    # Unknown client fields (including "review") are ignored. Review state is
    # owned exclusively by the server-side PatternDB workflow.
    model_config = ConfigDict(extra="ignore")

    kind: str
    text: str = Field(min_length=1, max_length=80)
    language: str
    image_png_base64: str = Field(min_length=8, max_length=2_800_000)
    ocr_guess: str = Field(default="", max_length=80)
    channel: str = Field(default="", max_length=80)
    file_name: str = Field(default="", max_length=160)
    bbox: list[int] = Field(default_factory=list, max_length=4)
    role: str = Field(default="", max_length=16)


class ExportIn(BaseModel):
    # Kept for request compatibility; submitted records are never the export
    # source. Only server-persisted, explicitly confirmed rows are exported.
    records: list[SnippetIn] = Field(default_factory=list, max_length=100)


class TelegramFileIn(BaseModel):
    file_id: str = Field(min_length=8, max_length=256)


class ConfusionIn(BaseModel):
    guess: str = Field(min_length=1, max_length=80)


def _require_reviewer(user: User | None) -> None:
    """Fail closed using the existing authenticated superuser control.

    A dedicated reviewer permission is not proven to be seeded in the live
    RBAC database, so do not invent or silently assume a permission codename.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser review authorization required")


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _api(method: str, token: str, params: dict | None = None) -> dict:
    query = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"https://api.telegram.org/bot{token}/{method}{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "omni-pattern-studio"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail="تعذّر الاتصال بتيليجرام") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail="تعذّر الاتصال بتيليجرام") from exc
    if not payload.get("ok"):
        raise HTTPException(status_code=502, detail="رفض تيليجرام الطلب")
    return payload["result"]


@router.get("/schema")
def schema():
    return {
        "schema": "oms.pattern.v1",
        "kinds": ["glyph", "word"],
        "languages": ["ar", "en", "mixed", "symbol"],
        "telegram": "TELEGRAM_BOT_TOKEN على الخادم، لا في المتصفح",
    }


@router.post("/confusions/suggest")
def confusion_suggestion(body: ConfusionIn):
    """Return a candidate only; never auto-correct or confirm it."""
    return {
        "suggestion": suggest(body.guess),
        "review": "open",
        "auto_apply": False,
    }


def _server_review_rows(db: PatternDB) -> list[dict]:
    """Read only persisted rows with server-owned review='confirmed'."""
    rows: list[dict] = []
    with db.connection() as conn:
        cursor = conn.execute(
            """
            SELECT image_blob, predicted_text, corrected_text, language,
                   category, review, context_json
            FROM patterns
            WHERE review = 'confirmed'
            ORDER BY id
            """
        )
        for image_blob, predicted, corrected, language, category, review, context_json in cursor.fetchall():
            if not image_blob or review != "confirmed":
                continue
            try:
                context = json.loads(context_json) if context_json else {}
            except (TypeError, json.JSONDecodeError):
                try:
                    context = ast.literal_eval(context_json) if context_json else {}
                except (ValueError, SyntaxError):
                    context = {}
            if not isinstance(context, dict):
                context = {}
            kind = context.get("kind", category)
            if kind not in {"glyph", "word"}:
                kind = "word"
            rows.append({
                "kind": kind,
                "text": corrected,
                "language": language or "mixed",
                "image_png_base64": base64.b64encode(bytes(image_blob)).decode("ascii"),
                "ocr_guess": predicted or "",
                "channel": str(context.get("channel") or "")[:80],
                "file_name": str(context.get("file_name") or "")[:160],
                "bbox": context.get("bbox") if isinstance(context.get("bbox"), list) else [],
                "role": str(context.get("role") or "")[:16],
                # This state came from the server database, not the request.
                "review": "confirmed",
            })
    return rows


@router.post("/snippets")
async def save_snippet(
    body: SnippetIn,
    current_user: User = Depends(get_current_user),
):
    """Persist a new snippet as open; client-supplied review is ignored."""
    try:
        raw = body.model_dump()
        raw["review"] = "open"
        record = normalize_record(raw)
        image_bytes = base64.b64decode(record["image_png_base64"], validate=True)
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("تعذّر فك ترميز القصاصة")
        context = {
            "kind": record["kind"],
            "role": record.get("role", ""),
            "channel": record["source"]["channel"],
            "file_name": record["source"]["file"],
            "bbox": record["source"]["bbox"],
            "image_sha256": record["image_sha256"],
            "submitted_by": str(current_user.id),
        }
        pattern_id = PatternDB().save_pattern(
            image=image,
            predicted=record["ocr_guess"],
            corrected=record["text"],
            language=record["language"],
            confidence=0.0,
            category=record["kind"],
            writer_id="default",
            context=context,
        )
        return {"id": pattern_id, "review": "open", "trainable": False}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/snippets/{snippet_id}/confirm")
async def confirm_snippet(
    snippet_id: int,
    current_user: User = Depends(get_current_user),
):
    """Explicit reviewer-only confirmation for an existing persisted pattern."""
    _require_reviewer(current_user)
    if isinstance(snippet_id, bool) or snippet_id <= 0:
        raise HTTPException(status_code=422, detail="snippet_id غير صالح")
    if not PatternDB().confirm_pattern(snippet_id):
        raise HTTPException(status_code=404, detail="القصاصة غير موجودة")
    return {"id": snippet_id, "review": "confirmed", "trainable": True}


@router.post("/snippets/{snippet_id}/reject")
async def reject_snippet(
    snippet_id: int,
    current_user: User = Depends(get_current_user),
):
    """Explicit reviewer-only rejection for an existing persisted pattern."""
    _require_reviewer(current_user)
    if isinstance(snippet_id, bool) or snippet_id <= 0:
        raise HTTPException(status_code=422, detail="snippet_id غير صالح")
    if not PatternDB().reject_pattern(snippet_id):
        raise HTTPException(status_code=404, detail="القصاصة غير موجودة")
    return {"id": snippet_id, "review": "rejected", "trainable": False}


@router.post("/dataset/export")
async def export_dataset(
    body: ExportIn | None = None,
    current_user: User = Depends(get_current_user),
):
    # Never export client-supplied records: even a forged review="confirmed"
    # is ignored. The only export source is the server-side reviewed database.
    _require_reviewer(current_user)
    try:
        return export_confirmed(_server_review_rows(PatternDB()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/telegram/file")
def fetch_telegram_file(body: TelegramFileIn):
    """يجلب ملفاً وصل للبوت (مستند/صورة قناة أُعيد توجيهها أو أُرسلت للبوت)."""
    token = _token()
    if not token:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "needs_token",
                "message": "عيّن TELEGRAM_BOT_TOKEN على الخادم. الاستوديو يعمل على صندوق الوارد المحلي بدون الرمز.",
            },
        )
    if not _FILE_ID.fullmatch(body.file_id):
        raise HTTPException(status_code=400, detail="file_id غير صالح")
    meta = _api("getFile", token, {"file_id": body.file_id})
    path = str(meta.get("file_path") or "")
    if not path or ".." in path or path.startswith("/"):
        raise HTTPException(status_code=502, detail="مسار الملف مرفوض")
    size = int(meta.get("file_size") or 0)
    if size > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="الملف أكبر من 8MB")
    url = f"https://api.telegram.org/file/bot{token}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "omni-pattern-studio"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read(_MAX_BYTES + 1)
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail="تعذّر تنزيل الملف") from exc
    if len(blob) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="الملف أكبر من 8MB")
    name = path.rsplit("/", 1)[-1]
    lower = name.lower()
    inline = None
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) and len(blob) <= 2_000_000:
        inline = base64.b64encode(blob).decode("ascii")
    return {
        "file_name": name,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "image_base64": inline,
        "note": "إن وُجدت image_base64 فاعرضها في الاستوديو ثم قصّ الكلمات واحفظ النص المقابل.",
    }
