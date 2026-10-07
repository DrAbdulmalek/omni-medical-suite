"""اختبارات صيغة قصاصات التدريب — بلا شبكة وبلا صور خارجية."""

import base64
import struct
import zlib

from packages.learning.snippet_dataset import dumps_jsonl, loads_jsonl, normalize_record, summarize


def _png(w: int = 2, h: int = 2) -> str:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    blob = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(blob).decode()


def test_roundtrip_word_and_glyph():
    png = _png()
    text = dumps_jsonl(
        [
            {"kind": "word", "text": "هيموغلوبين", "language": "ar", "image_png_base64": png, "channel": "@c", "file_name": "a.png", "ocr_guess": "هيموعلوبين"},
            {"kind": "glyph", "text": "ه", "language": "ar", "image_png_base64": png},
        ]
    )
    rows = loads_jsonl(text)
    assert len(rows) == 2
    assert rows[0]["schema"] == "oms.pattern.v1"
    assert rows[0]["source"]["channel"] == "@c"
    assert rows[0]["image_sha256"]
    summary = summarize(rows)
    assert summary["count"] == 2
    assert summary["by_kind"]["word"] == 1
    assert summary["by_kind"]["glyph"] == 1


def test_rejects_empty_text_and_bad_kind():
    png = _png()
    try:
        normalize_record({"kind": "word", "text": "  ", "language": "ar", "image_png_base64": png})
        raise AssertionError("expected empty text")
    except ValueError as exc:
        assert "text" in str(exc)
    try:
        normalize_record({"kind": "page", "text": "س", "language": "ar", "image_png_base64": png})
        raise AssertionError("expected kind")
    except ValueError as exc:
        assert "kind" in str(exc)


def test_rejects_non_png():
    try:
        normalize_record(
            {"kind": "glyph", "text": "ا", "language": "ar", "image_png_base64": base64.b64encode(b"notpng!!").decode()}
        )
        raise AssertionError("expected png")
    except ValueError as exc:
        assert "PNG" in str(exc)
