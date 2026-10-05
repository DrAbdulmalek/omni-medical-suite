# app/services/telegram_ingest.py
"""Telegram Channel Ingestion — جلب الملفات من قنوات تيليجرام

Bridges the owner's Telegram account (Telethon user session) into the OCR
pipeline: list media files posted in a channel and download them into the
local inbox for recognition.

Credentials resolution order (never logged, never committed):
    1. env:  TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SESSION
    2. file: $ZAI_SECRETS_DIR/telegram_api.json + tg_string_session.txt
             (ZAI_SECRETS_DIR defaults to /home/z/my-project/.secrets)

Only photos and image/pdf documents are considered OCR-able media.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

IMAGE_MIMES_PREFIX = "image/"
OCR_DOC_MIMES = ("application/pdf",)
MAX_FILE_BYTES = 60 * 1024 * 1024  # 60 MB guard

_SECRETS_DIR = os.getenv("ZAI_SECRETS_DIR", "/home/z/my-project/.secrets")


class TelegramConfigError(RuntimeError):
    pass


class TelegramNotAuthorized(RuntimeError):
    pass


def _load_credentials() -> Dict[str, Any]:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = os.getenv("TELEGRAM_SESSION")
    if api_id and api_hash and session:
        return {"api_id": int(api_id), "api_hash": api_hash, "session": session.strip()}
    cfg_path = os.path.join(_SECRETS_DIR, "telegram_api.json")
    sess_path = os.path.join(_SECRETS_DIR, "tg_string_session.txt")
    if os.path.exists(cfg_path) and os.path.exists(sess_path):
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        with open(sess_path, encoding="utf-8") as fh:
            session = fh.read().strip()
        if cfg.get("api_id") and cfg.get("api_hash") and session:
            return {"api_id": int(cfg["api_id"]), "api_hash": cfg["api_hash"], "session": session}
    raise TelegramConfigError(
        "Telegram credentials not found (env TELEGRAM_* or secrets dir)")


def credentials_status() -> Dict[str, Any]:
    """Non-sensitive report of credential availability."""
    try:
        _load_credentials()
        return {"credentials": True, "secrets_dir": os.path.isdir(_SECRETS_DIR)}
    except TelegramConfigError:
        return {"credentials": False, "secrets_dir": os.path.isdir(_SECRETS_DIR)}


async def resolve_channel(client: Any, channel: str) -> Any:
    """Accept @username, https://t.me/<name>, or numeric -100... id (async — Telethon)."""
    ch = (channel or "").strip()
    if not ch:
        raise ValueError("channel is required")
    m = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]+)", ch)
    if m and not ch.lstrip("-").isdigit():
        return await client.get_entity(m.group(1))
    if ch.lstrip("-").isdigit():
        return await client.get_entity(int(ch))
    return await client.get_entity(ch)


def _run_async(coro: Any) -> Any:
    """Run a coroutine from sync context (Gradio handlers / FastAPI def endpoints)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # we are inside a running loop (e.g. FastAPI async context) -> spawn a
        # dedicated thread with its own loop to avoid nested-loop errors
        result: Dict[str, Any] = {}

        def runner() -> None:
            result["value"] = asyncio.run(coro)

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        return result["value"]
    return asyncio.run(coro)


async def _list_media_async(channel: str, limit: int) -> List[Dict[str, Any]]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    creds = _load_credentials()
    out: List[Dict[str, Any]] = []
    async with TelegramClient(StringSession(creds["session"]), creds["api_id"],
                              creds["api_hash"], connection_retries=2, timeout=25) as client:
        entity = await resolve_channel(client, channel)
        async for msg in client.iter_messages(entity, limit=limit):
            kind, name, mime, size = None, None, None, 0
            if msg.photo and not msg.document:
                kind, mime = "photo", "image/jpeg"
                size = getattr(msg.file, "size", 0) or 0
                name = f"photo_{msg.id}.jpg"
            elif msg.document:
                doc = msg.document
                mime = doc.mime_type or ""
                size = getattr(doc, "size", 0) or 0
                name = None
                for attr in doc.attributes:
                    file_name = getattr(attr, "file_name", None)
                    if file_name:
                        name = file_name
                        break
                if mime.startswith(IMAGE_MIMES_PREFIX):
                    kind = "image"
                elif mime in OCR_DOC_MIMES:
                    kind = "pdf"
                else:
                    continue  # videos/archives/etc are not OCR targets
            else:
                continue
            if size > MAX_FILE_BYTES:
                logger.info("skip oversized %s (%s bytes)", name, size)
                continue
            out.append({
                "msg_id": msg.id,
                "kind": kind,
                "name": name or f"file_{msg.id}",
                "mime": mime,
                "size": int(size or 0),
                "date": int(msg.date.timestamp()) if msg.date else None,
            })
    return out


def list_channel_files(channel: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List OCR-able media files in a channel (newest first)."""
    return _run_async(_list_media_async(channel, limit))


def inbox_dir() -> str:
    base = os.getenv("OMNI_TRAINING_DB_DIR") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "training_db"))
    return os.path.join(base, "inbox")


async def _download_async(channel: str, msg_id: int) -> Dict[str, Any]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    creds = _load_credentials()
    async with TelegramClient(StringSession(creds["session"]), creds["api_id"],
                              creds["api_hash"], connection_retries=2, timeout=60) as client:
        entity = await resolve_channel(client, channel)
        msg = await client.get_messages(entity, ids=int(msg_id))
        if msg is None:
            raise ValueError(f"message {msg_id} not found in {channel}")
        dest_dir = os.path.join(inbox_dir(), re.sub(r"[^\w\-]+", "_", channel.strip("@")) or "channel")
        os.makedirs(dest_dir, exist_ok=True)
        path = await client.download_media(msg, file=os.path.join(dest_dir))
        if not path:
            raise ValueError("message has no downloadable media")
        return {"path": os.path.abspath(path), "msg_id": msg.id, "channel": channel,
                "size": os.path.getsize(path)}


def download_channel_file(channel: str, msg_id: int) -> Dict[str, Any]:
    """Download one media message into the OCR inbox. Returns local path info."""
    return _run_async(_download_async(channel, int(msg_id)))


def download_latest(channel: str, count: int = 5) -> List[Dict[str, Any]]:
    """Download the newest N OCR-able media files."""
    files = list_channel_files(channel, limit=max(count * 4, 20))[:count]
    results = []
    for f in files:
        try:
            results.append(download_channel_file(channel, f["msg_id"]))
        except Exception as exc:
            logger.warning("download failed msg=%s: %s", f["msg_id"], exc)
    return results
