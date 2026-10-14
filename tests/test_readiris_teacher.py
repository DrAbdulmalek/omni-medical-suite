"""Tests for the Readiris teacher pipeline (tools/readiris_teacher).

Covers: export parsing of all three dialects (TXT / HTML / RTF), the
license gate, snippet cropping (قصاصات), text alignment / CER, dataset
building (JSONL + YOLO layout) and hybrid cascade routing.

Mirrors tests/test_abbyy_teacher.py (PR #168).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.readiris_teacher import (
    BBox,
    CascadeRouter,
    CascadeThresholds,
    CropLevel,
    CropRecord,
    LICENSE_ENV_VAR,
    LicenseGateError,
    PageAnnotation,
    ReadirisExportError,
    SourceFormat,
    align_texts,
    build_correction_pair,
    build_layout_yolo,
    cer,
    crop_records_to_pairs,
    detect_format,
    guess_language,
    levenshtein_distance,
    line_pairs_from_trusted_text,
    lines_to_pairs,
    normalize_for_alignment,
    parse_readiris_export,
    parse_readiris_export_all,
    require_license,
    write_ocr_jsonl,
)

# --------------------------------------------------------------------------- #
# Fixtures: one realistic export per dialect (Arabic medical flavour)
# --------------------------------------------------------------------------- #
READIRIS_TXT = """تحليل الدم قبل الافطار
الجرعة 500 مليغرام
"""

READIRIS_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>readiris export</title></head>
<body>
<img src="page_001.png">
<div style="left:100px;top:200px;width:900px;height:400px">
<p style="left:100px;top:210px;width:880px;height:60px">تحليل الدم</p>
<p style="left:100px;top:300px;width:600px;height:55px">قبل الافطار</p>
</div>
<hr>
<div style="left:100px;top:50px;width:900px;height:100px"><p>مرتين يوميا</p></div>
</body>
</html>
"""

# cp1256 byte escapes: \'c7=ا \'e1=ل \'cc=ج \'d1=ر \'ed=ي \'e3=م \'ca=ت \'e4=ن
# \'e6=و;  \u1605=م \u1604=ل \u1610=ي ; \tab -> tab; {\fonttbl}/{\*\...} skipped
READIRIS_RTF = (
    r"{\rtf1\ansi\ansicpg1256{\fonttbl{\f0 Arial;}}{\*\generator Readiris 25}" "\n"
    + r"\pard\rtl\'c7\'e1\'cc\'d1\'ed\'c7 \tab \u1605?\u1604?\u1610?\'cc\'d1\'c7\'e3\par" "\n"
    + r"\pard\'e3\'d1\'ca\'ed\'e4 \'ed\'e6\'e3\'ed\'c7\par" "\n"
    + "}"
)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture()
def gated(monkeypatch):
    """Environment that satisfies the license gate."""
    monkeypatch.setenv(LICENSE_ENV_VAR, "1")
    return True


# --------------------------------------------------------------------------- #
# Parsing: detection + per-dialect correctness
# --------------------------------------------------------------------------- #
class TestDetection:
    def test_detect_txt(self):
        assert detect_format(READIRIS_TXT.encode()) is SourceFormat.TXT

    def test_detect_html(self):
        assert detect_format(READIRIS_HTML.encode()) is SourceFormat.HTML

    def test_detect_html_no_doctype(self):
        assert detect_format(b'<div style="left:1px">x</div>') is SourceFormat.HTML

    def test_detect_rtf(self):
        assert detect_format(READIRIS_RTF.encode()) is SourceFormat.RTF

    def test_detect_garbage_raises(self):
        with pytest.raises(ReadirisExportError):
            detect_format(b"\x00\x01\x02binary\xff")


class TestTxtParser:
    def test_parse_lines_words(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        ann = parse_readiris_export(p)
        assert ann.source_format is SourceFormat.TXT
        assert [l.text for l in ann.lines] == ["تحليل الدم قبل الافطار", "الجرعة 500 مليغرام"]
        assert len(ann.words) == 7
        assert not ann.has_geometry
        assert ann.width == 0 and ann.height == 0
        assert all(l.confidence == 0.0 for l in ann.lines)

    def test_sha256_provenance(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        ann = parse_readiris_export(p)
        assert len(ann.export_sha256) == 64
        import hashlib

        assert ann.export_sha256 == hashlib.sha256(p.read_bytes()).hexdigest()

    def test_empty_lines_skipped(self, tmp_path):
        p = _write(tmp_path, "page_02.txt", "\n\nسطر\n\n\n")
        ann = parse_readiris_export(p)
        assert [l.text for l in ann.lines] == ["سطر"]

    def test_summary_keys(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        s = parse_readiris_export(p).summary()
        assert s["source_format"] == "txt"
        assert s["has_geometry"] is False
        assert s["export_sha256"]


class TestHtmlParser:
    def test_two_pages_split_on_hr(self, tmp_path):
        p = _write(tmp_path, "export.html", READIRIS_HTML)
        anns = parse_readiris_export_all(p)
        assert len(anns) == 2
        assert [l.text for l in anns[0].lines] == ["تحليل الدم", "قبل الافطار"]
        assert [l.text for l in anns[1].lines] == ["مرتين يوميا"]
        assert "#page=1" in anns[0].source_path and "#page=2" in anns[1].source_path

    def test_geometry_and_image(self, tmp_path):
        p = _write(tmp_path, "export.html", READIRIS_HTML)
        ann = parse_readiris_export(p)
        assert ann.image_filename == "page_001.png"
        assert ann.has_geometry
        assert ann.width == 1000 and ann.height == 600  # max extents of boxes

    def test_page_break_comment_split(self, tmp_path):
        html = "<html><body><p>أولا</p><!-- page break --><p>ثانيا</p></body></html>"
        p = _write(tmp_path, "e.html", html)
        anns = parse_readiris_export_all(p)
        assert [l.text for a in anns for l in a.lines] == ["أولا", "ثانيا"]
        assert len(anns) == 2

    def test_plain_fragment_fallback(self, tmp_path):
        p = _write(tmp_path, "frag.html", "سطر بلا وسوم\nسطر ثان")
        ann = parse_readiris_export(p)
        assert ann.source_format is SourceFormat.HTML
        assert [l.text for l in ann.lines] == ["سطر بلا وسوم", "سطر ثان"]
        assert not ann.has_geometry

    def test_first_page_entrypoint(self, tmp_path):
        p = _write(tmp_path, "export.html", READIRIS_HTML)
        ann = parse_readiris_export(p)
        assert [l.text for l in ann.lines] == ["تحليل الدم", "قبل الافطار"]


class TestRtfParser:
    def test_parse_arabic_cp1256_and_unicode(self, tmp_path):
        p = _write(tmp_path, "page_01.rtf", READIRIS_RTF)
        ann = parse_readiris_export(p)
        assert ann.source_format is SourceFormat.RTF
        assert [l.text for l in ann.lines] == ["الجريا \tمليجرام", "مرتين يوميا"]

    def test_destinations_skipped(self, tmp_path):
        # fonttbl / generator content must never leak into the text
        p = _write(tmp_path, "page_01.rtf", READIRIS_RTF)
        text = parse_readiris_export(p).full_text()
        assert "Arial" not in text and "Readiris 25" not in text and "ansicpg" not in text

    def test_codepage_override(self, tmp_path):
        # \'c7 with latin-1 decode is 'Ç' - proves the codepage hook is used
        rtf = r"{\rtf1\ansi\'c7\par}"
        p = _write(tmp_path, "x.rtf", rtf)
        ann = parse_readiris_export(p, rtf_codepage="latin-1")
        assert ann.lines[0].text == "Ç"


# --------------------------------------------------------------------------- #
# License gate
# --------------------------------------------------------------------------- #
class TestLicenseGate:
    def test_refuses_without_flag(self, monkeypatch):
        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        with pytest.raises(LicenseGateError):
            require_license(False)

    def test_refuses_without_env(self, monkeypatch):
        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        with pytest.raises(LicenseGateError):
            require_license(True)

    def test_refuses_without_flag_even_with_env(self, monkeypatch):
        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        with pytest.raises(LicenseGateError):
            require_license(False)

    def test_accepts_flag_plus_env(self, monkeypatch):
        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        assert require_license(True) is None

    def test_notice_mentions_iris_official_site(self):
        from tools.readiris_teacher import LICENSE_NOTICE

        assert "irislink.com" in LICENSE_NOTICE
        assert "لا تُشحن" in LICENSE_NOTICE or "no such artefact" in LICENSE_NOTICE


# --------------------------------------------------------------------------- #
# Alignment / CER
# --------------------------------------------------------------------------- #
class TestAlignment:
    def test_levenshtein_basics(self):
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("كتاب", "كتاب") == 0
        assert levenshtein_distance("كتاب", "كتب") == 1  # delete 'ا'
        assert levenshtein_distance("abc", "") == 3

    def test_cer_bounds(self):
        assert cer("", "") == 0.0
        assert cer("abc", "abc") == 0.0
        assert cer("", "abc") == 1.0
        assert cer("ضبط", "ضبط ") == 0.0  # whitespace normalised away

    def test_normalize_keeps_diacritics(self):
        assert normalize_for_alignment("مُحَمَّد") == "مُحَمَّد"
        assert normalize_for_alignment("  a \n b  ") == "a b"

    def test_align_texts_opcodes(self):
        ops = dict((t, (a, b)) for t, a, b in align_texts("ضبط الدم", "ضبط الدمع"))
        assert ops["equal"] == ("ضبط الدم", "ضبط الدم")
        assert ops["insert"] == ("", "ع")

    def test_guess_language(self):
        assert guess_language("تحليل الدم") == "arabic"
        assert guess_language("blood test") == "english"
        assert guess_language("Straße und über") == "german"
        assert guess_language("123 456") == "unknown"
        assert guess_language("") == "unknown"

    def test_build_correction_pair_fields(self):
        pair = build_correction_pair("ضبت الدم", "ضبط الدم", source_file="p.txt", source_format="txt")
        assert pair.ocr_text == "ضبت الدم"
        assert pair.corrected_text == "ضبط الدم"
        assert pair.cer == round(cer("ضبط الدم", "ضبت الدم"), 4)
        assert pair.language == "arabic"
        assert pair.source_format == "txt"

    def test_line_pairs_from_trusted_text(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        ann = parse_readiris_export(p)
        truth = "تحليل الدم قبل الأفطار\nالجرعة 500 مليغرام\n"
        pairs = line_pairs_from_trusted_text(ann, truth, source_file="page_01.txt")
        assert len(pairs) == 2
        assert pairs[0].ocr_text == "تحليل الدم قبل الافطار"
        assert pairs[0].corrected_text == "تحليل الدم قبل الأفطار"
        assert pairs[0].cer > 0  # hamza difference is a real edit
        assert pairs[1].cer == 0.0
        assert pairs[0].export_sha256 == ann.export_sha256  # provenance propagates

    def test_line_pairs_drop_misalignments(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", "أبجد هوز\n")
        ann = parse_readiris_export(p)
        pairs = line_pairs_from_trusted_text(ann, "نص مختلف تماما عن السطر", min_similarity=0.9)
        assert pairs == []

    def test_pairs_to_jsonl_superset(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        ann = parse_readiris_export(p)
        from tools.readiris_teacher import pairs_to_jsonl

        rows = [json.loads(x) for x in pairs_to_jsonl(
            line_pairs_from_trusted_text(ann, "تحليل الدم قبل الافطار\nالجرعة 500 مليغرام\n")
        )]
        contract = {"ocr_text", "corrected_text", "language", "source_file", "page_num",
                    "confidence", "created_at"}
        assert contract <= set(rows[0].keys())          # repo contract present
        assert "export_sha256" in rows[0]               # additive provenance


# --------------------------------------------------------------------------- #
# Dataset building
# --------------------------------------------------------------------------- #
class TestDatasetBuilder:
    def _crop_record(self):
        return CropRecord(
            crop_path="/tmp/line_0000.png", level=CropLevel.LINE, text="تحليل الدم",
            bbox=BBox(100, 210, 880, 60), confidence=0.0, source_image="page_001.png",
            page_index=0, source_format=SourceFormat.HTML,
        )

    def test_crop_records_to_pairs_contract(self):
        row = crop_records_to_pairs([self._crop_record()])[0]
        assert row["ocr_text"] == row["corrected_text"] == "تحليل الدم"
        assert row["bbox"] == [100, 210, 880, 60]
        assert row["language"] == "arabic"
        for key in ("ocr_text", "corrected_text", "language", "source_file",
                    "page_num", "confidence", "created_at"):
            assert key in row

    def test_lines_to_pairs_text_only(self, tmp_path):
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        ann = parse_readiris_export(p)
        rows = lines_to_pairs(ann, source_file="page_01.txt")
        assert len(rows) == 2
        assert rows[0]["level"] == "line" and rows[0]["bbox"] is None
        assert rows[0]["export_sha256"] == ann.export_sha256
        assert rows[0]["source_format"] == "txt"

    def test_write_ocr_jsonl(self, tmp_path):
        out = tmp_path / "data.jsonl"
        n = write_ocr_jsonl(lines_to_pairs(
            parse_readiris_export(_write(tmp_path, "page_01.txt", READIRIS_TXT))), out)
        assert n == 2
        loaded = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
        assert len(loaded) == 2 and loaded[0]["ocr_text"] == "تحليل الدم قبل الافطار"

    def test_yolo_from_html(self, tmp_path):
        from tools.readiris_teacher.dataset_builder import YOLO_CLASS_NAMES

        ann = parse_readiris_export(_write(tmp_path, "export.html", READIRIS_HTML))
        label = build_layout_yolo(ann, tmp_path / "layout", image_path="page_001.png", level="block")
        assert label is not None and label.name == "page_001.txt"
        lines = label.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for ln in lines:
            parts = ln.split()
            assert len(parts) == 5
            assert 0 <= int(parts[0]) < len(YOLO_CLASS_NAMES)
            assert all(0.0 <= float(v) <= 1.0 for v in parts[1:])

    def test_yolo_none_for_text_only(self, tmp_path):
        ann = parse_readiris_export(_write(tmp_path, "page_01.txt", READIRIS_TXT))
        assert build_layout_yolo(ann, tmp_path / "layout", level="block") is None
        assert build_layout_yolo(ann, tmp_path / "layout", level="line") is None

    def test_yolo_bad_level_raises(self, tmp_path):
        ann = parse_readiris_export(_write(tmp_path, "export.html", READIRIS_HTML))
        with pytest.raises(ValueError):
            build_layout_yolo(ann, tmp_path / "layout", level="word")

    def test_dataset_card(self, tmp_path):
        from tools.readiris_teacher.dataset_builder import write_dataset_card

        card = write_dataset_card(tmp_path, 7, source_note="teacher format: txt")
        assert card.name == "DATASET_CARD.md"
        assert "Records: 7" in card.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Cascade routing
# --------------------------------------------------------------------------- #
class TestCascade:
    def test_thresholds_semantics(self):
        router = CascadeRouter(CascadeThresholds(accept=0.92, escalate=0.60))
        assert router.decide(0.97).engine == "student"
        assert router.decide(0.75).engine == "review"
        assert router.decide(0.50).engine == "readiris_fallback"

    def test_suspicious_penalty(self):
        router = CascadeRouter()
        d = router.decide(0.95, suspicious=True)
        assert d.engine == "review" and d.suspicious
        d2 = router.decide(0.95, suspicious_count=10)
        assert d2.confidence == round(0.95 - 0.25, 4)  # capped at max_penalty

    def test_text_only_pages_all_fallback(self, tmp_path):
        ann = parse_readiris_export(_write(tmp_path, "page_01.txt", READIRIS_TXT))
        report = CascadeRouter().route_page(ann)
        assert report.counts == {"student": 0, "review": 0, "readiris_fallback": 2}
        assert report.fallback_ratio == 1.0

    def test_route_student_result(self):
        report = CascadeRouter().route_student_result([("نص", 0.97), ("غامض", 0.41)])
        assert report.counts["student"] == 1 and report.counts["readiris_fallback"] == 1

    def test_report_serialisation(self):
        payload = CascadeRouter().route_student_result([("نص", 0.97)]).to_dict()
        assert payload["counts"] == {"student": 1, "review": 0, "readiris_fallback": 0}
        assert payload["decisions"][0]["engine"] == "student"


# --------------------------------------------------------------------------- #
# CLI (license gate + happy paths)
# --------------------------------------------------------------------------- #
class TestCli:
    def test_gate_blocks_every_command(self, tmp_path, monkeypatch):
        from tools.readiris_teacher.cli import main

        monkeypatch.delenv(LICENSE_ENV_VAR, raising=False)
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        for argv in (
            ["parse", "--export", str(p)],
            ["align", "--export", str(p), "--truth-text", str(p), "--out", str(tmp_path / "o.jsonl")],
            ["build", "--export", str(p), "--out-dir", str(tmp_path / "ds")],
            ["cascade", "--export", str(p)],
        ):
            assert main(argv) == 2, argv

    def test_parse_txt(self, tmp_path, monkeypatch, capsys):
        from tools.readiris_teacher.cli import main

        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        assert main(["parse", "--export", str(p), "--i-own-license"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["source_format"] == "txt" and payload["lines"] == 2

    def test_align_document_level_for_text_only(self, tmp_path, monkeypatch):
        from tools.readiris_teacher.cli import main

        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        truth = _write(tmp_path, "truth.txt", "تحليل الدم قبل الافطار\nالجرعة 500 مليغرام\n")
        out = tmp_path / "pairs.jsonl"
        assert main(["align", "--export", str(p), "--truth-text", str(truth),
                     "--out", str(out), "--i-own-license"]) == 0
        rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1 and rows[0]["level"] == "document"

    def test_build_text_only_skips_yolo(self, tmp_path, monkeypatch):
        from tools.readiris_teacher.cli import main

        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        p = _write(tmp_path, "page_01.txt", READIRIS_TXT)
        out_dir = tmp_path / "ds"
        assert main(["build", "--export", str(p), "--out-dir", str(out_dir),
                     "--i-own-license"]) == 0
        data = [json.loads(x) for x in (out_dir / "data.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(data) == 2
        assert (out_dir / "DATASET_CARD.md").exists()
        assert not (out_dir / "layout" / "labels").exists()  # no geometry -> skipped

    def test_build_html_full_pipeline(self, tmp_path, monkeypatch):
        from tools.readiris_teacher.cli import main

        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        p = _write(tmp_path, "export.html", READIRIS_HTML)
        out_dir = tmp_path / "ds_html"
        assert main(["build", "--export", str(p), "--out-dir", str(out_dir),
                     "--i-own-license"]) == 0
        assert (out_dir / "layout" / "labels" / "page_001.txt").exists()

    def test_missing_export_file(self, tmp_path, monkeypatch):
        from tools.readiris_teacher.cli import main

        monkeypatch.setenv(LICENSE_ENV_VAR, "1")
        assert main(["parse", "--export", str(tmp_path / "nope.txt"), "--i-own-license"]) == 2


# --------------------------------------------------------------------------- #
# Cropping (needs Pillow; HTML only - text-only exports are refused)
# --------------------------------------------------------------------------- #
class TestCropping:
    def test_crop_segments_and_manifest(self, tmp_path):
        pytest.importorskip("PIL")
        from PIL import Image

        from tools.readiris_teacher import crop_segments, load_manifest

        img_path = tmp_path / "page_001.png"
        Image.new("RGB", (1000, 600), "white").save(img_path)
        ann = parse_readiris_export(_write(tmp_path, "export.html", READIRIS_HTML))
        out_dir = tmp_path / "crops"
        records = crop_segments(ann, img_path, out_dir, levels=("line",), padding=0.05)
        assert len(records) == 2
        assert all(r.source_format is SourceFormat.HTML for r in records)
        manifest = load_manifest(out_dir / "manifest.jsonl")
        assert len(manifest) == 2 and manifest[0]["text"] == "تحليل الدم"

    def test_text_only_refused(self, tmp_path):
        ann = parse_readiris_export(_write(tmp_path, "page_01.txt", READIRIS_TXT))
        with pytest.raises(ReadirisExportError):
            from tools.readiris_teacher import crop_segments

            crop_segments(ann, tmp_path / "whatever.png", tmp_path / "crops")

    def test_crop_single_box_clamps(self, tmp_path):
        pytest.importorskip("PIL")
        from PIL import Image

        from tools.readiris_teacher import crop_single_box

        img_path = tmp_path / "page.png"
        Image.new("RGB", (100, 80), "white").save(img_path)
        applied = crop_single_box(img_path, BBox(90, 70, 50, 50), tmp_path / "s.png", padding=0.5)
        # pad=25 -> box (65,45,100,100) clamped into the 100x80 image
        assert applied == (65, 45, 35, 35)
