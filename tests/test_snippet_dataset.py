"""اختبارات صيغة قصاصات التدريب — بلا شبكة وبلا صور خارجية."""

import base64
import struct
import zlib

from packages.learning.confusions_ar import suggest
from packages.learning.snippet_dataset import dumps_jsonl, export_confirmed, loads_jsonl, normalize_record, summarize


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
            {"kind": "word", "text": "هيموغلوبين", "language": "ar", "image_png_base64": png, "channel": "@c", "file_name": "a.png", "ocr_guess": "هيموعلوبين", "review": "confirmed"},
            {"kind": "glyph", "text": "ه", "language": "ar", "image_png_base64": png},
        ]
    )
    rows = loads_jsonl(text)
    assert len(rows) == 2
    assert rows[0]["schema"] == "oms.pattern.v1"
    assert rows[0]["source"]["channel"] == "@c"
    assert rows[0]["image_sha256"]
    assert rows[0]["review"] == "confirmed"
    assert rows[1]["review"] == "open"
    summary = summarize(rows)
    assert summary["count"] == 2
    assert summary["trainable"] == 1
    assert summary["by_kind"]["word"] == 1
    assert summary["by_kind"]["glyph"] == 1


def test_review_gate_keeps_open_out_of_trainable():
    png = _png()
    rows = loads_jsonl(
        dumps_jsonl(
            [
                {"kind": "word", "text": "أموكسيسيلين", "language": "ar", "image_png_base64": png, "review": "open", "role": "drug"},
                {"kind": "word", "text": "500 مجم", "language": "mixed", "image_png_base64": png, "review": "rejected", "role": "dose"},
                {"kind": "word", "text": "هيموغلوبين", "language": "ar", "image_png_base64": png, "review": "confirmed", "role": "drug"},
            ]
        )
    )
    assert rows[0]["review"] == "open" and rows[0]["role"] == "drug"
    assert summarize(rows)["trainable"] == 1
    try:
        normalize_record({"kind": "word", "text": "س", "language": "ar", "image_png_base64": png, "review": "maybe"})
        raise AssertionError("expected review")
    except ValueError as exc:
        assert "review" in str(exc)


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


def test_suggest_known_and_unknown():
    hit = suggest("هيموعلوبين")
    assert hit is not None and hit["text"] == "هيموغلوبين"
    assert suggest("نص سليم") is None


def test_export_includes_only_explicitly_confirmed_records():
    image = base64.b64encode(_png()).decode("ascii")
    records = [
        {"kind": "word", "text": "نص معلّق", "language": "ar", "image_png_base64": image, "review": "open"},
        {"kind": "word", "text": "نص مؤكد", "language": "ar", "image_png_base64": image, "review": "confirmed"},
        {"kind": "glyph", "text": "✗", "language": "symbol", "image_png_base64": image, "review": "rejected"},
    ]
    result = export_confirmed(records)
    exported = loads_jsonl(result["jsonl"])
    assert len(exported) == 1
    assert exported[0]["text"] == "نص مؤكد"
    assert exported[0]["review"] == "confirmed"
    assert result["summary"]["trainable"] == 1
    assert result["input_summary"]["count"] == 3
    assert result["excluded"] == {"open": 1, "rejected": 1}


def test_export_with_no_confirmed_records_is_empty():
    image = base64.b64encode(_png()).decode("ascii")
    result = export_confirmed([
        {"kind": "word", "text": "نص مفتوح", "language": "ar", "image_png_base64": image}
    ])
    assert result["jsonl"] == ""
    assert result["summary"]["count"] == 0
    assert result["excluded"]["open"] == 1


def test_confusion_suggestion_is_advisory_not_approval():
    from app.routers.pattern_studio import ConfusionIn, confusion_suggestion

    result = confusion_suggestion(ConfusionIn(guess="هيموعلوبين"))
    assert result["suggestion"]["text"] == "هيموغلوبين"
    assert result["review"] == "open"
    assert result["auto_apply"] is False
