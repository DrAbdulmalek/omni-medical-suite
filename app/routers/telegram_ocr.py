# app/routers/telegram_ocr.py
"""Telegram OCR + Training-DB Router — واجهة القنوات والتعرف وقاعدة التدريب

Endpoints (prefix /api/telegram-ocr):
    GET  /status              engine + telegram credential availability
    GET  /probe               live Telegram session check (slow, ~3-6s)
    GET  /files?channel=&limit=          list OCR-able channel media
    POST /files/download      {channel, msg_id} -> download into inbox
    POST /files/download-latest {channel, count}
    POST /ocr/run             {path, lang?, psm?, use_patterns?}
    GET  /inbox               local inbox files ready for OCR
    GET  /slices?limit=       annotated slices manifest (manifest only)
    POST /slices              {path, bbox, text, level, lang?, source?}
    GET  /patterns            pattern library metadata
    POST /patterns/learn      {slices?: [ids]} learn patterns from slices
    GET  /trainingdb/stats    slices/patterns sync statistics
    POST /trainingdb/sync     push pending data to GitHub DB repo (subprocess)

Heavy work is delegated to services; this layer stays thin.
Telethon/OCR imports happen lazily inside handlers.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

_SUITE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _services():
    sys.path.insert(0, _SUITE_ROOT)  # ensure src/ocr importable for pattern store
    from app.services import telegram_ingest, telegram_ocr_service
    return telegram_ingest, telegram_ocr_service


def _stores():
    sys.path.insert(0, os.path.join(_SUITE_ROOT, "src", "ocr"))
    from pattern_store import PatternStore
    from slice_store import SliceStore
    return PatternStore, SliceStore


# ------------------------------------------------------------------ models
class DownloadBody(BaseModel):
    channel: str
    msg_id: int


class DownloadLatestBody(BaseModel):
    channel: str
    count: int = Field(default=5, ge=1, le=20)


class OcrRunBody(BaseModel):
    path: str
    lang: str = "ara+eng"
    psm: int = Field(default=6, ge=3, le=8)
    use_patterns: bool = True


class SliceBody(BaseModel):
    path: str
    bbox: List[int] = Field(..., min_length=4, max_length=4)
    text: str
    level: str = "word"
    lang: str = "ar"
    source: Dict[str, Any] = Field(default_factory=dict)


class LearnBody(BaseModel):
    slices: Optional[List[str]] = None  # slice ids; None => all slices


# ------------------------------------------------------------------ status
@router.get("/status")
async def status() -> Dict[str, Any]:
    ingest, ocr = _services()
    return {"telegram": ingest.credentials_status(), "engine": ocr.engine_status()}


@router.get("/probe")
async def probe() -> Dict[str, Any]:
    ingest, _ = _services()

    def _probe() -> Dict[str, Any]:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        creds = ingest._load_credentials()

        async def inner() -> Dict[str, Any]:
            async with TelegramClient(StringSession(creds["session"]), creds["api_id"],
                                      creds["api_hash"], connection_retries=2, timeout=20) as c:
                me = await c.get_me()
                return {"authorized": True, "name": me.first_name, "id": me.id}
        return asyncio.run(inner())

    try:
        return _probe()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"telegram probe failed: {type(exc).__name__}")


# ------------------------------------------------------------------- files
@router.get("/files")
async def files(channel: str, limit: int = 50) -> List[Dict[str, Any]]:
    ingest, _ = _services()
    try:
        return ingest.list_channel_files(channel, limit=max(1, min(limit, 200)))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"telegram list failed: {type(exc).__name__}: {exc}")


@router.post("/files/download")
async def files_download(body: DownloadBody) -> Dict[str, Any]:
    ingest, _ = _services()
    try:
        return ingest.download_channel_file(body.channel, body.msg_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"download failed: {type(exc).__name__}: {exc}")


@router.post("/files/download-latest")
async def files_download_latest(body: DownloadLatestBody) -> List[Dict[str, Any]]:
    ingest, _ = _services()
    try:
        return ingest.download_latest(body.channel, body.count)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"download failed: {type(exc).__name__}: {exc}")


@router.get("/inbox")
async def inbox() -> List[Dict[str, Any]]:
    ingest, ocr = _services()
    base = ingest.inbox_dir()
    out: List[Dict[str, Any]] = []
    for root, _dirs, names in os.walk(base):
        for name in names:
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in ocr.SUPPORTED_IMAGE_EXT or ext == ".pdf":
                out.append({"path": path, "name": name, "size": os.path.getsize(path),
                            "kind": "pdf" if ext == ".pdf" else "image"})
    out.sort(key=lambda f: -f["size"])
    return out[:200]


# --------------------------------------------------------------------- ocr
@router.post("/ocr/run")
async def ocr_run(body: OcrRunBody) -> Dict[str, Any]:
    _ingest, ocr = _services()
    path = os.path.abspath(body.path)
    inbox_root = os.path.abspath(_ingest.inbox_dir())
    if not (path.startswith(inbox_root) or os.path.dirname(path).startswith("/tmp")):
        # allow inbox files or explicit /tmp paths only (defensive path scoping)
        raise HTTPException(status_code=400, detail="path must be inside the OCR inbox")
    try:
        return ocr.run_ocr(path, lang=body.lang, psm=body.psm, use_patterns=body.use_patterns)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="file not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ocr failed: {type(exc).__name__}: {exc}")


# ------------------------------------------------------------------ slices
@router.get("/slices")
async def slices(limit: int = 50) -> List[Dict[str, Any]]:
    _PatternStore, SliceStore = _stores()
    return SliceStore().list_slices(limit=max(1, min(limit, 500)))


@router.post("/slices")
async def add_slice(body: SliceBody) -> Dict[str, Any]:
    _ingest, ocr = _services()
    _PatternStore, SliceStore = _stores()
    path = os.path.abspath(body.path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="source image not found")
    try:
        img = ocr.load_image(path)
        store = SliceStore()
        record = store.add_slice(img, body.bbox, body.text, level=body.level,
                                 lang=body.lang, source_meta=body.source)
        return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- patterns
@router.get("/patterns")
async def patterns() -> Dict[str, Any]:
    PatternStore, _SliceStore = _stores()
    store = PatternStore()
    return {"patterns": store.list_patterns(), "stats": store.stats()}


@router.post("/patterns/learn")
async def patterns_learn(body: LearnBody) -> Dict[str, Any]:
    _ingest, ocr = _services()
    PatternStore, SliceStore = _stores()
    slices_store = SliceStore()
    pattern_store = PatternStore()
    rows = slices_store.list_slices(limit=10_000)
    if body.slices is not None:
        wanted = set(body.slices)
        rows = [r for r in rows if r["id"] in wanted]
    learned, skipped = 0, 0
    for rec in rows:
        img = slices_store.image_of(rec)
        if img is None:
            skipped += 1
            continue
        try:
            pattern_store.add_pattern(rec["text"], img, level=rec.get("level", "word"),
                                      script="ar" if rec.get("lang", "ar") == "ar" else "en",
                                      source_ref=f"slices/{rec['id']}")
            learned += 1
        except ValueError:
            skipped += 1
    return {"learned": learned, "skipped": skipped, "total_patterns": pattern_store.count()}


# -------------------------------------------------------------- training db
@router.get("/trainingdb/stats")
async def trainingdb_stats() -> Dict[str, Any]:
    PatternStore, SliceStore = _stores()
    slice_stats = SliceStore().stats()
    pattern_stats = PatternStore().stats()
    repo = os.getenv("OMNI_TRAINING_DB_REPO", "DrAbdulmalek/omni-ocr-training-db")
    return {"repo": repo, "slices": slice_stats, "patterns": pattern_stats}


@router.post("/trainingdb/sync")
async def trainingdb_sync() -> Dict[str, Any]:
    script = os.path.join(_SUITE_ROOT, "scripts", "trainingdb_sync.py")
    if not os.path.exists(script):
        raise HTTPException(status_code=500, detail="sync script missing")
    proc = await __import__("asyncio").create_subprocess_exec(
        sys.executable, script,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=_SUITE_ROOT)
    out, _ = await proc.communicate()
    ok = proc.returncode == 0
    return {"ok": ok, "returncode": proc.returncode,
            "log": out.decode("utf-8", errors="replace")[-4000:]}
