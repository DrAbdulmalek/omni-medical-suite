"""Tests for the ABBYY FineReader teacher pipeline (tools/abbyy_teacher).

Covers: XML parsing of all three dialects (ALTO / PAGE / FineReader XML),
snippet cropping (قصاصات), text alignment / CER, dataset building (JSONL +
YOLO layout) and hybrid cascade routing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.abbyy_teacher import (
    AbbyyXmlError,
    BBox,
    CascadeRouter,
    CascadeThresholds,
    CropLevel,
    CropRecord,
    PageAnnotation,
    SourceFormat,
    align_texts,
    build_correction_pair,
    build_layout_yolo,
    cer,
    crop_records_to_pairs,
    crop_segments,
    crop_single_box,
    detect_format,
    guess_language,
    levenshtein_distance,
    line_pairs_from_trusted_text,
    load_manifest,
    normalize_for_alignment,
    parse_abbyy_xml,
    parse_abbyy_xml_all,
    write_ocr_jsonl,
)

# --------------------------------------------------------------------------- #
# Fixtures: one realistic export per dialect (Arabic medical flavour)
# --------------------------------------------------------------------------- #
ALTO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v3#">
  <Layout>
    <Page WIDTH="2481" HEIGHT="3510" PHYSICAL_IMG_NR="0" ID="PG1">
      <PrintSpace HPOS="0" VPOS="0" WIDTH="2481" HEIGHT="3510">
        <TextBlock ID="TB1" HPOS="100" VPOS="200" WIDTH="900" HEIGHT="400">
          <TextLine ID="TL1" HPOS="100" VPOS="200" WIDTH="900" HEIGHT="60">
            <String ID="S1" HPOS="100" VPOS="200" WIDTH="200" HEIGHT="60" CONTENT="الجرعة" WC="0.97"/>
            <SP WIDTH="30"/>
            <String ID="S2" HPOS="330" VPOS="200" WIDTH="150" HEIGHT="60" CONTENT="500" WC="0.93"/>
            <SP WIDTH="25"/>
            <String ID="S3" HPOS="505" VPOS="200" WIDTH="220" HEIGHT="60" CONTENT="مليغرام" WC="0.88"/>
          </TextLine>
          <TextLine ID="TL2" HPOS="100" VPOS="300" WIDTH="600" HEIGHT="55">
            <String ID="S4" HPOS="100" VPOS="300" WIDTH="600" HEIGHT="55" CONTENT="مرتين يوميا" WC="0.72"/>
          </TextLine>
        </TextBlock>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
"""

PAGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15">
  <Page imageFilename="page_001.png" imageWidth="2000" imageHeight="2800">
    <TextRegion id="r1" type="paragraph">
      <Coords points="80,150 1200,150 1200,700 80,700"/>
      <TextLine id="l1">
        <Coords points="80,150 1200,150 1200,220 80,220"/>
        <Word id="w1">
          <Coords points="80,150 380,150 380,220 80,220"/>
          <TextEquiv conf="0.96"><Unicode>تحليل</Unicode></TextEquiv>
        </Word>
        <Word id="w2">
          <Coords points="400,150 700,150 700,220 400,220"/>
          <TextEquiv conf="0.91"><Unicode>الدم</Unicode></TextEquiv>
        </Word>
        <TextEquiv conf="0.93"><Unicode>تحليل الدم</Unicode></TextEquiv>
      </TextLine>
      <TextLine id="l2">
        <Coords points="80,260 900,260 900,330 80,330"/>
        <TextEquiv conf="0.58"><Unicode>قبل الافطار</Unicode></TextEquiv>
      </TextLine>
    </TextRegion>
  </Page>
</PcGts>
"""

FINEREADER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="http://www.abbyy.com/FineReader_xml/FineReader10-schema-v1.xml" version="1.0"
          producer="ABBYY FineReader" languages="{Arabic}">
  <page width="2481" height="3510" resolution="300" imageRotation="0">
    <block blockType="Text" blockName="blk1" left="100" top="200" right="1000" bottom="600">
      <region><rect left="100" top="200" right="1000" bottom="600"/></region>
      <par align="Right">
        <line baseline="265" left="100" top="210" right="980" bottom="270" lineConfidence="95" lineId="l1">
          <formatting fontSize="12" lang="Arabic">
            <charParams left="900" top="210" right="980" bottom="270" charConfidence="97" suspicious="0">د</charParams>
            <charParams left="820" top="210" right="890" bottom="270" charConfidence="95" suspicious="0">و</charParams>
            <charParams left="700" top="210" right="810" bottom="270" charConfidence="40" suspicious="1">ر</charParams>
            <charParams left="600" top="210" right="690" bottom="270" charConfidence="0" suspicious="0"> </charParams>
            <charParams left="500" top="210" right="590" bottom="270" charConfidence="92" suspicious="0">ا</charParams>
            <charParams left="100" top="210" right="490" bottom="270" charConfidence="90" suspicious="0">لم</charParams>
          </formatting>
        </line>
      </par>
    </block>
  </page>
</document>
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Parsing: detection + per-dialect correctness
# --------------------------------------------------------------------------- #
class TestDetection:
    def test_detect_alto(self, tmp_path):
        assert detect_format(ALTO_XML.encode()) is SourceFormat.ALTO

    def test_detect_page(self, tmp_path):
        assert detect_format(PAGE_XML.encode()) is SourceFormat.PAGE

    def test_detect_finereader(self, tmp_path):
        assert detect_format(FINEREADER_XML.encode()) is SourceFormat.FINEREADER

    def test_unknown_root_raises(self):
        with pytest.raises(AbbyyXmlError):
            detect_format(b"<html><body/></html>")

    def test_malformed_xml_raises(self, tmp_path):
        p = tmp_path / "broken.xml"
        p.write_text("<alto><Layout>", encoding="utf-8")
        with pytest.raises(AbbyyXmlError):
            parse_abbyy_xml(p)


class TestAltoParser:
    def test_structure(self, tmp_path):
        p = _write(tmp_path, "a.xml", ALTO_XML)
        ann = parse_abbyy_xml(p)
        assert ann.source_format is SourceFormat.ALTO
        assert ann.width == 2481 and ann.height == 3510
        assert len(ann.blocks) == 1
        assert len(ann.lines) == 2
        assert len(ann.words) == 4

    def test_line_text_and_confidence(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "a.xml", ALTO_XML))
        l1 = ann.lines[0]
        assert l1.text == "الجرعة 500 مليغرام"
        assert l1.confidence == pytest.approx((0.97 + 0.93 + 0.88) / 3)
        assert ann.lines[1].text == "مرتين يوميا"
        assert ann.lines[1].confidence == pytest.approx(0.72)

    def test_word_boxes(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "a.xml", ALTO_XML))
        w = ann.words[0]
        assert w.text == "الجرعة"
        assert (w.bbox.x, w.bbox.y, w.bbox.w, w.bbox.h) == (100, 200, 200, 60)


class TestPageParser:
    def test_structure_and_text(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "p.xml", PAGE_XML))
        assert ann.source_format is SourceFormat.PAGE
        assert ann.image_filename == "page_001.png"
        assert ann.width == 2000 and ann.height == 2800
        assert len(ann.lines) == 2
        assert ann.lines[0].text == "تحليل الدم"
        assert ann.lines[0].confidence == pytest.approx(0.93)
        assert len(ann.lines[0].words) == 2
        assert ann.words[0].bbox.w == 300

    def test_line_fallback_to_words(self, tmp_path):
        # line with no own text keeps composed words text
        xml = PAGE_XML.replace('<TextEquiv conf="0.93"><Unicode>تحليل الدم</Unicode></TextEquiv>', "")
        ann = parse_abbyy_xml(_write(tmp_path, "p2.xml", xml))
        assert ann.lines[0].text == "تحليل الدم"
        # confidence falls back to word mean
        assert ann.lines[0].confidence == pytest.approx((0.96 + 0.91) / 2)


class TestFineReaderParser:
    def test_structure(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "f.xml", FINEREADER_XML))
        assert ann.source_format is SourceFormat.FINEREADER
        assert ann.width == 2481 and ann.height == 3510
        assert ann.dpi == 300
        assert len(ann.lines) == 1

    def test_word_splitting_and_suspicious(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "f.xml", FINEREADER_XML))
        line = ann.lines[0]
        # chars: د و ر | ا ل م  (space splits words); "لم" is one charParams pair
        assert [w.text for w in line.words] == ["دور", "الم"]
        assert line.words[0].suspicious is True        # ر was flagged
        assert line.words[1].suspicious is False
        assert line.words[0].confidence == pytest.approx((0.97 + 0.95 + 0.40) / 3)

    def test_line_confidence_normalised(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "f.xml", FINEREADER_XML))
        # lineConfidence=95 on a 0-100 scale -> 0.95
        assert ann.lines[0].confidence == pytest.approx(0.95)

    def test_multi_page(self, tmp_path):
        two = FINEREADER_XML.replace("</document>", "</document>")
        two = FINEREADER_XML.replace(
            "</document>",
            '<page width="100" height="200" resolution="300"></page></document>',
        )
        pages = parse_abbyy_xml_all(_write(tmp_path, "f2.xml", two))
        assert len(pages) == 2
        assert pages[1].width == 100


# --------------------------------------------------------------------------- #
# Cropping (قصاصات)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def page_image(tmp_path):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1200, 800), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([100, 100, 1100, 200], fill="black")
    d.rectangle([100, 400, 700, 500], fill="gray")
    p = tmp_path / "page.png"
    img.save(p)
    return p


@pytest.fixture()
def annotation():
    return PageAnnotation(
        source_format=SourceFormat.ALTO,
        image_filename="page.png",
        width=1200,
        height=800,
        dpi=300,
        blocks=[],
        source_path="page.xml",
    )


def _add_line(ann: PageAnnotation, text: str, x: int, y: int, conf: float = 0.9):
    from tools.abbyy_teacher import TextBlock, TextLine, Word

    bbox = BBox(x, y, 300, 40)
    words = [Word(text=text, bbox=bbox, confidence=conf, line_id="l")]
    line = TextLine(text=text, bbox=bbox, confidence=conf, words=words, block_id=f"b{len(ann.blocks)}")
    ann.blocks.append(
        TextBlock(block_id=line.block_id, block_type="paragraph", bbox=bbox, lines=[line])
    )


class TestCropping:
    def test_line_and_word_crops(self, tmp_path, page_image, annotation):
        _add_line(annotation, "الجرعة 500", 100, 100)
        _add_line(annotation, "مرتين", 100, 400, conf=0.5)
        out = tmp_path / "crops"
        records = crop_segments(annotation, page_image, out, levels=("line",), padding=0.1)
        assert len(records) == 2
        assert (out / "manifest.jsonl").exists()
        manifest = load_manifest(out / "manifest.jsonl")
        assert len(manifest) == 2
        assert manifest[0]["text"] == "الجرعة 500"
        assert manifest[0]["level"] == "line"
        # crop file exists and has expected padded size: 300w, 40h, pad=4
        from PIL import Image

        with Image.open(records[0].crop_path) as im:
            assert im.size == (300 + 8, 40 + 8)

    def test_padding_clamps_to_image_bounds(self, tmp_path, page_image, annotation):
        _add_line(annotation, "edge", 1150, 760)  # box exceeds bottom-right corner
        records = crop_segments(annotation, page_image, tmp_path / "c", levels=("line",))
        (x, y, w, h) = records[0].bbox.to_list()
        assert x >= 0 and y >= 0 and x + w <= 1200 and y + h <= 800

    def test_tiny_boxes_skipped(self, tmp_path, page_image, annotation):
        _add_line(annotation, "x", 100, 100)
        annotation.blocks[-1].lines[-1].bbox = BBox(100, 100, 3, 2)
        annotation.blocks[-1].lines[-1].words[0].bbox = annotation.blocks[-1].lines[-1].bbox
        records = crop_segments(annotation, page_image, tmp_path / "c", levels=("word",), min_size=8)
        assert records == []

    def test_word_level(self, tmp_path, page_image, annotation):
        _add_line(annotation, "كلمة", 100, 100)
        records = crop_segments(annotation, page_image, tmp_path / "c", levels=("word",))
        assert len(records) == 1
        assert records[0].level.value == "word"

    def test_crop_single_box(self, tmp_path, page_image):
        got = crop_single_box(page_image, BBox(100, 100, 300, 40), tmp_path / "one.png")
        # pad = 0.10 * 40 = 4 px per side
        assert got is not None and got[2] == 300 + 8 and got[3] == 40 + 8


# --------------------------------------------------------------------------- #
# Alignment / CER
# --------------------------------------------------------------------------- #
class TestAlignment:
    def test_levenshtein_basics(self):
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("kitten", "sitting") == 3
        assert levenshtein_distance("تحليل", "تحليل") == 0
        assert levenshtein_distance("مليغرام", "مليجرام") == 1

    def test_cer(self):
        assert cer("تحليل الدم", "تحليل الدم") == 0.0
        assert cer("", "") == 0.0
        assert cer("", "abc") == 1.0
        assert cer("مليغرام", "مليجرام") == pytest.approx(1 / 7)

    def test_normalize(self):
        assert normalize_for_alignment("  a \n b  ") == "a b"

    def test_align_ops(self):
        ops = align_texts("مليغرام", "مليجرام")
        kinds = {t for t, _, _ in ops}
        assert "replace" in kinds or "delete" in kinds or "insert" in kinds

    def test_correction_pair_language_guess(self):
        p = build_correction_pair("مليغرام 500", "مليجرام 500", source_file="x.png")
        assert p.language == "arabic"
        assert p.cer is not None and 0 < p.cer < 1

    def test_line_pairs_alignment(self, tmp_path, annotation):
        _add_line(annotation, "الجرعة 500 مليغرام", 100, 100, conf=0.9)
        _add_line(annotation, "مرتين يوميا", 100, 300, conf=0.6)
        trusted = "الجرعة 500 مليجرام\nمرتين يومياً\nسطر جديد غير موجود"
        pairs = line_pairs_from_trusted_text(annotation, trusted)
        # line 1: replace (غرام->جرام), line 2: replace (tanween), line 3: unmatched -> dropped
        assert len(pairs) == 2
        assert pairs[0].ocr_text == "الجرعة 500 مليغرام"
        assert pairs[0].corrected_text == "الجرعة 500 مليجرام"
        assert pairs[0].cer > 0
        # identical lines give CER exactly 0: exercise the 'equal' branch too
        pairs_eq = line_pairs_from_trusted_text(annotation, "الجرعة 500 مليغرام\nمرتين يوميا")
        assert [p.cer for p in pairs_eq] == [0.0, 0.0]

    def test_line_pairs_drops_garbage(self, annotation):
        _add_line(annotation, " totally different ", 0, 0)
        pairs = line_pairs_from_trusted_text(annotation, "نص عربي مؤهل تماما")
        assert pairs == []

    def test_guess_language(self):
        assert guess_language("الجرعة 500") == "arabic"
        assert guess_language("blood test") == "english"
        assert guess_language("Blutprüfung") == "german"
        assert guess_language("12345 !!!") == "unknown"


# --------------------------------------------------------------------------- #
# Dataset building
# --------------------------------------------------------------------------- #
class TestDatasetBuilder:
    def test_write_ocr_jsonl_contract(self, tmp_path):
        pairs = [build_correction_pair("مليغرام", "مليجرام", source_file="p.png", page_num=2)]
        out = tmp_path / "data.jsonl"
        n = write_ocr_jsonl(pairs, out)
        assert n == 1
        row = json.loads(out.read_text(encoding="utf-8"))
        # repo contract fields (training-data/README.md)
        for key in ("ocr_text", "corrected_text", "language", "source_file", "page_num", "confidence", "created_at"):
            assert key in row
        # teacher extras
        assert row["cer"] is not None and row["level"] == "line"

    def test_crop_records_to_pairs(self, tmp_path, annotation):
        rec = CropRecord(
            crop_path="/tmp/c.png", level=CropLevel.LINE,
            text="الجرعة", bbox=BBox(1, 2, 3, 4), confidence=0.9,
            source_image="page.png", page_index=0, source_format=SourceFormat.ALTO,
        )
        rows = crop_records_to_pairs([rec])
        assert rows[0]["ocr_text"] == "الجرعة"
        assert rows[0]["corrected_text"] == "الجرعة"
        assert rows[0]["page_num"] == 1
        assert rows[0]["bbox"] == [1, 2, 3, 4]
        assert rows[0]["language"] == "arabic"

    def test_yolo_block_export(self, tmp_path, annotation):
        from tools.abbyy_teacher import TextBlock

        annotation.blocks.append(TextBlock("b1", "paragraph", BBox(100, 200, 400, 100), []))
        annotation.blocks.append(TextBlock("b2", "table", BBox(0, 0, 200, 50), []))
        out = tmp_path / "layout"
        label = build_layout_yolo(annotation, out, image_path="page.png", level="block")
        lines = label.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        cls, cx, cy, w, h = lines[0].split()
        assert cls == "0"
        # 100+400/2=300 /1200 = 0.25 ; 200+100/2=250 /800 = 0.3125
        assert abs(float(cx) - 300 / 1200) < 1e-6
        assert abs(float(cy) - 250 / 800) < 1e-6
        assert (out / "train.txt").exists()

    def test_yolo_line_export_and_guards(self, tmp_path, annotation):
        from tools.abbyy_teacher import TextBlock, TextLine

        annotation.blocks.append(TextBlock("b", "paragraph", BBox(10, 10, 100, 50), []))
        annotation.blocks[0].lines.append(TextLine("سطر", BBox(10, 10, 100, 50), 0.9))
        label = build_layout_yolo(annotation, tmp_path / "L", level="line")
        assert label is not None and len(label.read_text(encoding="utf-8").strip().splitlines()) == 1
        # empty page -> None
        empty = PageAnnotation(SourceFormat.ALTO, "e", 100, 100, None)
        assert build_layout_yolo(empty, tmp_path / "E") is None


# --------------------------------------------------------------------------- #
# Cascade routing
# --------------------------------------------------------------------------- #
class TestCascade:
    def test_accept_zone(self):
        d = CascadeRouter().decide(0.97)
        assert d.engine == "student"

    def test_fallback_zone(self):
        d = CascadeRouter().decide(0.41)
        assert d.engine == "abbyy_fallback"

    def test_grey_zone_review(self):
        d = CascadeRouter().decide(0.75)
        assert d.engine == "review"

    def test_suspicious_pushes_down(self):
        router = CascadeRouter(CascadeThresholds(accept=0.92, escalate=0.60))
        d = router.decide(0.93, suspicious=True)
        assert d.engine == "review"  # 0.93 - 0.05 = 0.88 -> grey zone

    def test_suspicious_count_penalty_capped(self):
        router = CascadeRouter(CascadeThresholds())
        d = router.decide(0.95, suspicious_count=10)  # cap 0.25
        assert d.confidence == pytest.approx(0.70)
        assert d.engine == "review"

    def test_route_page(self, tmp_path):
        ann = parse_abbyy_xml(_write(tmp_path, "a.xml", ALTO_XML))
        report = CascadeRouter().route_page(ann)
        engines = [d.engine for d in report.decisions]
        # line1 conf = mean(0.97, 0.93, 0.88) = 0.9267 -> student; line2 = 0.72 -> review
        assert engines == ["student", "review"]
        assert report.counts["abbyy_fallback"] == 0

    def test_report_ratio(self):
        from tools.abbyy_teacher import RouteDecision

        r = CascadeRouter().route_student_result([("a", 0.97), ("b", 0.2)])
        assert r.fallback_ratio == pytest.approx(0.5)
        assert "counts" in r.to_dict()

    def test_boundaries(self):
        router = CascadeRouter()
        assert router.decide(0.92).engine == "student"
        assert router.decide(0.5999).engine == "abbyy_fallback"
        assert router.decide(0.60).engine == "review"


# --------------------------------------------------------------------------- #
# CLI end-to-end
# --------------------------------------------------------------------------- #
class TestCli:
    def test_parse_command(self, tmp_path, capsys):
        from tools.abbyy_teacher.cli import main

        p = _write(tmp_path, "a.xml", ALTO_XML)
        out = tmp_path / "s.json"
        rc = main(["parse", "--xml", str(p), "--json", str(out)])
        assert rc == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["lines"] == 2 and data["words"] == 4
        assert "الجرعة" in data["full_text"]

    def test_build_command_full_pipeline(self, tmp_path, page_image):
        from tools.abbyy_teacher.cli import main

        p = _write(tmp_path, "a.xml", ALTO_XML)
        out_dir = tmp_path / "ds"
        rc = main(["build", "--xml", str(p), "--image", str(page_image), "--out-dir", str(out_dir)])
        assert rc == 0
        assert (out_dir / "data.jsonl").exists()
        assert (out_dir / "crops" / "manifest.jsonl").exists()
        assert (out_dir / "layout" / "labels" / "PG1.txt").exists()
        assert (out_dir / "DATASET_CARD.md").exists()
        rows = [json.loads(l) for l in (out_dir / "data.jsonl").read_text(encoding="utf-8").splitlines()]
        assert rows and rows[0]["corrected_text"]

    def test_align_command(self, tmp_path):
        from tools.abbyy_teacher.cli import main

        p = _write(tmp_path, "p.xml", PAGE_XML)
        truth = _write(tmp_path, "truth.txt", "تحليل الدم\nقبل الإفطار\n")
        out = tmp_path / "pairs.jsonl"
        rc = main(["align", "--xml", str(p), "--truth-text", str(truth), "--out", str(out)])
        assert rc == 0
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert rows[0]["corrected_text"] == "تحليل الدم"
        assert rows[1]["ocr_text"] == "قبل الافطار"
        assert rows[1]["corrected_text"] == "قبل الإفطار"

    def test_cascade_command(self, tmp_path, capsys):
        from tools.abbyy_teacher.cli import main

        p = _write(tmp_path, "a.xml", ALTO_XML)
        rc = main(["cascade", "--xml", str(p)])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["counts"]["student"] == 1
        assert data["counts"]["review"] == 1

    def test_error_exit_code(self, tmp_path):
        from tools.abbyy_teacher.cli import main

        bad = tmp_path / "bad.xml"
        bad.write_text("<html></html>", encoding="utf-8")
        rc = main(["parse", "--xml", str(bad)])
        assert rc == 2
