"""واجهة تدريب الأنماط: قصاصة حرف/كلمة + جلب ملف تيليجرام.

رمز البوت يُقرأ من البيئة فقط ولا يُعاد في أي استجابة.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.learning.snippet_dataset import dumps_jsonl, summarize

router = APIRouter()
_FILE_ID = re.compile(r"^[A-Za-z0-9_:\-]{8,256}$")
_MAX_BYTES = 8_000_000


class SnippetIn(BaseModel):
    kind: str
    text: str
    language: str
    image_png_base64: str
    ocr_guess: str = ""
    channel: str = ""
    file_name: str = ""
    bbox: list[int] = Field(default_factory=list)


class ExportIn(BaseModel):
    records: list[SnippetIn]


class TelegramFileIn(BaseModel):
    file_id: str


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


@router.post("/dataset/export")
def export_dataset(body: ExportIn):
    try:
        text = dumps_jsonl(r.model_dump() for r in body.records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    from packages.learning.snippet_dataset import loads_jsonl

    rows = loads_jsonl(text) if text else []
    return {"jsonl": text, "summary": summarize(rows)}


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
