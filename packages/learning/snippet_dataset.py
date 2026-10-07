"""مجموعة قصاصات التدريب — حرف أو كلمة مع النص المقابل.

الصيغة oms.pattern.v1 تُخزَّن JSONL على GitHub لتدريب لاحق.
لا تعتمد OpenCV حتى تبقى قابلة للاستيراد في مسارات الـ API الخفيفة.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Iterable

SCHEMA = "oms.pattern.v1"
KINDS = frozenset({"glyph", "word"})
LANGS = frozenset({"ar", "en", "mixed", "symbol"})


def _b64_png(value: str) -> bytes:
    raw = value.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("image_png_base64 ليس PNG صالحاً") from exc
    if len(blob) < 8 or blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("image_png_base64 ليس PNG صالحاً")
    if len(blob) > 2_000_000:
        raise ValueError("القصاصة أكبر من 2MB")
    return blob


def normalize_record(raw: dict) -> dict:
    """يتحقق من سجل واحد ويعيد النسخة القانونية للأرشيف."""
    if not isinstance(raw, dict):
        raise ValueError("السجل يجب أن يكون كائناً")
    kind = str(raw.get("kind") or "")
    text = str(raw.get("text") or "").strip()
    language = str(raw.get("language") or "")
    image = str(raw.get("image_png_base64") or "")
    if kind not in KINDS:
        raise ValueError("kind يجب أن يكون glyph أو word")
    if not text:
        raise ValueError("text فارغ")
    if len(text) > 80:
        raise ValueError("text أطول من 80 محرفاً")
    if language not in LANGS:
        raise ValueError("language غير مدعومة")
    blob = _b64_png(image)
    digest = hashlib.sha256(blob).hexdigest()
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    channel = str(raw.get("channel") or source.get("channel") or "")[:80]
    file_name = str(raw.get("file_name") or source.get("file") or "")[:160]
    bbox = raw.get("bbox") if isinstance(raw.get("bbox"), list) else []
    bbox_out = []
    for n in bbox[:4]:
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            raise ValueError("bbox يجب أن يكون أرقاماً")
        bbox_out.append(int(n))
    return {
        "schema": SCHEMA,
        "kind": kind,
        "text": text,
        "language": language,
        "image_sha256": digest,
        "image_png_base64": base64.b64encode(blob).decode("ascii"),
        "ocr_guess": str(raw.get("ocr_guess") or "")[:80],
        "source": {"channel": channel, "file": file_name, "bbox": bbox_out},
    }


def dumps_jsonl(records: Iterable[dict]) -> str:
    lines = [json.dumps(normalize_record(r), ensure_ascii=False) for r in records]
    return ("\n".join(lines) + "\n") if lines else ""


def loads_jsonl(text: str) -> list[dict]:
    out: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"سطر {lineno} ليس JSON") from exc
        out.append(normalize_record(raw))
    return out


def summarize(records: Iterable[dict]) -> dict:
    rows = list(records)
    by_kind = {k: 0 for k in sorted(KINDS)}
    for row in rows:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    return {"schema": SCHEMA, "count": len(rows), "by_kind": by_kind}
