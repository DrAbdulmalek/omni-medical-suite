"""Parsers for ABBYY FineReader XML exports.

Three dialects are supported and auto-detected from the root element:

* **ALTO XML**  (``http://www.loc.gov/standards/alto/...``) - the standard
  OCR export; word boxes via ``HPOS/VPOS/WIDTH/HEIGHT``, word confidence
  via ``WC`` (0-1).
* **PAGE XML**  (``http://schema.primaresearch.org/PAGE/gts/pagecontent/...``)
  - polygon coordinates via ``Coords points``, text via ``TextEquiv``,
  optional ``conf`` attribute (0-1).
* **FineReader XML** (``http://www.abbyy.com/FineReader_xml/...``) - ABBYY's
  native export; character-level ``charParams`` with ``charConfidence``
  (0-100) and ``suspicious`` flags, aggregated into words/lines here.

All parsers return the unified :class:`~tools.abbyy_teacher.models.PageAnnotation`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import BBox, PageAnnotation, SourceFormat, TextBlock, TextLine, Word, _clamp_confidence

try:  # lxml is faster and more tolerant; stdlib is the fallback
    from lxml import etree as _lxml_etree
except ImportError:  # pragma: no cover
    _lxml_etree = None


_ALTO_NS_RE = re.compile(r"^\{http://www\.loc\.gov/standards/alto")
_PAGE_NS_RE = re.compile(r"^\{http://schema\.primaresearch\.org/PAGE/gts/pagecontent")
_FR_NS_RE = re.compile(r"^\{http://www\.abbyy\.com/FineReader_xml")


class AbbyyXmlError(ValueError):
    """Raised when an export file cannot be identified or parsed."""


def _parse_root(data: bytes) -> ET.Element:
    if _lxml_etree is not None:
        try:
            parser = _lxml_etree.XMLParser(recover=False, resolve_entities=False, huge_tree=True)
            return _lxml_etree.fromstring(data, parser)  # type: ignore[return-value]
        except _lxml_etree.XMLSyntaxError as exc:  # pragma: no cover
            raise AbbyyXmlError(f"XML syntax error: {exc}") from exc
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise AbbyyXmlError(f"XML syntax error: {exc}") from exc


def _children(node: Any, name: str) -> Iterable[Any]:
    """Iterate direct children whose *local* tag name matches (any namespace)."""
    for child in node:
        tag = child.tag
        if isinstance(tag, str) and tag.rsplit("}", 1)[-1] == name:
            yield child


def _find(node: Any, name: str) -> Optional[Any]:
    for child in _children(node, name):
        return child
    return None


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _attr(node: Any, name: str, default: str = "") -> str:
    """Attribute lookup that ignores the namespace prefix if any."""
    if name in node.attrib:
        return node.attrib[name]
    for key, value in node.attrib.items():
        if key.rsplit("}", 1)[-1] == name:
            return value
    return default


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def detect_format(data: bytes) -> SourceFormat:
    """Identify the XML dialect from the root element's namespace."""
    root = _parse_root(data)
    tag = root.tag if isinstance(root.tag, str) else ""
    if _ALTO_NS_RE.match(tag):
        return SourceFormat.ALTO
    if _PAGE_NS_RE.match(tag):
        return SourceFormat.PAGE
    if _FR_NS_RE.match(tag):
        return SourceFormat.FINEREADER
    raise AbbyyXmlError(
        "Unrecognised XML root '<%s>': expected ALTO, PAGE or FineReader XML" % tag
    )


def parse_abbyy_xml(source: str | Path | bytes) -> PageAnnotation:
    """Parse any supported ABBYY export into a unified :class:`PageAnnotation`.

    Note: ABBYY exports one XML file per document batch; multi-page files are
    handled by returning the *first* page's annotation. Use
    :func:`parse_abbyy_xml_all` to iterate over every page.
    """
    pages = parse_abbyy_xml_all(source)
    if not pages:
        raise AbbyyXmlError("No <page> element found in the export")
    return pages[0]


def parse_abbyy_xml_all(source: str | Path | bytes) -> list[PageAnnotation]:
    """Parse every page contained in an ABBYY export file."""
    if isinstance(source, bytes):
        data, path = source, ""
    else:
        path = str(source)
        data = Path(source).read_bytes()

    root = _parse_root(data)
    fmt = detect_format(data)
    parser = {
        SourceFormat.ALTO: _parse_alto,
        SourceFormat.PAGE: _parse_page,
        SourceFormat.FINEREADER: _parse_finereader,
    }[fmt]
    return [ann for ann in parser(root, fmt, path) if ann is not None]


# --------------------------------------------------------------------------- #
# ALTO XML
# --------------------------------------------------------------------------- #
def _parse_alto(root: Any, fmt: SourceFormat, path: str) -> list[PageAnnotation]:
    pages: list[PageAnnotation] = []
    layout = _find(root, "Layout")
    if layout is None:
        return pages
    for page in _children(layout, "Page"):
        width = _to_int(_attr(page, "WIDTH"), 0)
        height = _to_int(_attr(page, "HEIGHT"), 0)
        blocks: list[TextBlock] = []
        for print_space in list(_children(page, "PrintSpace")) or [page]:
            for tb in _children(print_space, "TextBlock"):
                blocks.append(_alto_text_block(tb))
        pages.append(
            PageAnnotation(
                source_format=fmt,
                image_filename=_attr(page, "ID", "page"),
                width=width,
                height=height,
                dpi=None,
                blocks=blocks,
                source_path=path,
            )
        )
    return pages


def _alto_text_block(tb: Any) -> TextBlock:
    block_id = _attr(tb, "ID", "")
    lines: list[TextLine] = []
    for tl in _children(tb, "TextLine"):
        line_id = _attr(tl, "ID", "")
        words: list[Word] = []
        for elem in tl:
            local = _local(elem.tag)
            if local == "String":
                words.append(
                    Word(
                        text=_attr(elem, "CONTENT", ""),
                        bbox=BBox(
                            x=_to_int(_attr(elem, "HPOS")),
                            y=_to_int(_attr(elem, "VPOS")),
                            w=_to_int(_attr(elem, "WIDTH")),
                            h=_to_int(_attr(elem, "HEIGHT")),
                        ),
                        confidence=_clamp_confidence(_attr(elem, "WC", "0")),
                        line_id=line_id,
                    )
                )
        line_bbox = BBox(
            x=_to_int(_attr(tl, "HPOS")),
            y=_to_int(_attr(tl, "VPOS")),
            w=_to_int(_attr(tl, "WIDTH")),
            h=_to_int(_attr(tl, "HEIGHT")),
        )
        if not words:
            text = ""
        else:
            # Rebuild the visual line: SP elements carry gap widths only.
            gaps = [e for e in tl if _local(e.tag) == "SP"]
            joiner = " " if gaps or len(words) > 1 else ""
            text = joiner.join(w.text for w in words).strip()
        conf = _mean([w.confidence for w in words])
        lines.append(
            TextLine(text=text, bbox=line_bbox, confidence=conf, words=words, line_id=line_id, block_id=block_id)
        )
    bbox = BBox(
        x=_to_int(_attr(tb, "HPOS")),
        y=_to_int(_attr(tb, "VPOS")),
        w=_to_int(_attr(tb, "WIDTH")),
        h=_to_int(_attr(tb, "HEIGHT")),
    )
    return TextBlock(block_id=block_id, block_type="paragraph", bbox=bbox, lines=lines)


# --------------------------------------------------------------------------- #
# PAGE XML
# --------------------------------------------------------------------------- #
def _parse_page(root: Any, fmt: SourceFormat, path: str) -> list[PageAnnotation]:
    pages: list[PageAnnotation] = []
    for page in list(_children(root, "Page")) or ([root] if _local(root.tag) == "Page" else []):
        points = _page_coords(page)
        width = _to_int(_attr(page, "imageWidth"), 0)
        height = _to_int(_attr(page, "imageHeight"), 0)
        if not width and points:
            width = max(p[0] for p in points)
        if not height and points:
            height = max(p[1] for p in points)
        blocks: list[TextBlock] = []
        for region in page:
            local = _local(region.tag)
            if local in ("TextRegion", "TableRegion"):
                blocks.append(_page_text_region(region, region_type=local))
        pages.append(
            PageAnnotation(
                source_format=fmt,
                image_filename=_attr(page, "imageFilename", "page"),
                width=width,
                height=height,
                dpi=None,
                blocks=blocks,
                source_path=path,
            )
        )
    return pages


def _page_coords(node: Any) -> list[tuple[int, int]]:
    coords = _find(node, "Coords")
    if coords is None:
        return []
    raw = _attr(coords, "points", "")
    out: list[tuple[int, int]] = []
    for pair in raw.split():
        parts = pair.replace(",", " ").split()
        if len(parts) >= 2:
            out.append((_to_int(parts[0]), _to_int(parts[1])))
    return out


def _page_equiv_conf(node: Any) -> tuple[str, float]:
    """Best (highest index) TextEquiv: text + confidence."""
    equivs = list(_children(node, "TextEquiv"))
    if not equivs:
        return "", 0.0
    best = equivs[-1]
    text_el = _find(best, "Unicode")
    text = (text_el.text or "") if text_el is not None else ""
    conf = _clamp_confidence(_attr(best, "conf", "0"))
    return text.strip(), conf


def _page_text_region(region: Any, region_type: str) -> TextBlock:
    region_id = _attr(region, "id", "")
    region_points = _page_coords(region)
    block_bbox = BBox.from_points(region_points) if region_points else BBox(0, 0, 0, 0)
    block_type = "table" if region_type == "TableRegion" else "paragraph"

    lines: list[TextLine] = []
    for tl in _children(region, "TextLine"):
        line_id = _attr(tl, "id", "")
        line_points = _page_coords(tl)
        words: list[Word] = []
        for w in _children(tl, "Word"):
            w_text, w_conf = _page_equiv_conf(w)
            w_points = _page_coords(w)
            words.append(
                Word(
                    text=w_text,
                    bbox=BBox.from_points(w_points) if w_points else BBox(0, 0, 0, 0),
                    confidence=w_conf,
                    line_id=line_id,
                )
            )
        line_text, line_conf = _page_equiv_conf(tl)
        if not line_text and words:
            line_text = " ".join(w.text for w in words).strip()
        if line_conf == 0.0 and words:
            line_conf = _mean([w.confidence for w in words])
        lines.append(
            TextLine(
                text=line_text,
                bbox=BBox.from_points(line_points) if line_points else BBox(0, 0, 0, 0),
                confidence=line_conf,
                words=words,
                line_id=line_id,
                block_id=region_id,
            )
        )
    return TextBlock(block_id=region_id, block_type=block_type, bbox=block_bbox, lines=lines)


# --------------------------------------------------------------------------- #
# FineReader XML (native ABBYY export)
# --------------------------------------------------------------------------- #
def _parse_finereader(root: Any, fmt: SourceFormat, path: str) -> list[PageAnnotation]:
    pages: list[PageAnnotation] = []
    for page in _children(root, "page"):
        width = _to_int(_attr(page, "width"), 0)
        height = _to_int(_attr(page, "height"), 0)
        resolution = _attr(page, "resolution", "").strip()
        dpi = _to_int(resolution) if resolution else None
        blocks: list[TextBlock] = []
        for idx, block in enumerate(_children(page, "block")):
            if _attr(block, "blockType", "Text") != "Text":
                continue
            blocks.append(_fr_text_block(block, block_id=_attr(block, "blockName", "") or f"b{idx}"))
        pages.append(
            PageAnnotation(
                source_format=fmt,
                image_filename=Path(path).stem or "page",
                width=width,
                height=height,
                dpi=dpi,
                blocks=blocks,
                source_path=path,
            )
        )
    return pages


def _fr_text_block(block: Any, block_id: str) -> TextBlock:
    lines: list[TextLine] = []
    for par in _children(block, "par"):
        for line in _children(par, "line"):
            lines.append(_fr_line(line, block_id=block_id))
    bbox = _fr_region_bbox(block)
    return TextBlock(block_id=block_id, block_type="paragraph", bbox=bbox, lines=lines)


def _fr_line(line: Any, block_id: str) -> TextLine:
    chars: list[tuple[str, BBox, float, bool]] = []
    for formatting in _children(line, "formatting"):
        for cp in _children(formatting, "charParams"):
            raw = cp.text or ""
            if raw.isspace():
                # explicit whitespace char -> close the current word buffer
                chars.append((" ", BBox(0, 0, 0, 0), 1.0, False))
                continue
            text = raw.strip()
            if not text:
                continue
            bbox = BBox(
                x=_to_int(_attr(cp, "left")),
                y=_to_int(_attr(cp, "top")),
                w=max(0, _to_int(_attr(cp, "right")) - _to_int(_attr(cp, "left"))),
                h=max(0, _to_int(_attr(cp, "bottom")) - _to_int(_attr(cp, "top"))),
            )
            conf = _clamp_confidence(_attr(cp, "charConfidence", "0"))
            suspicious = _attr(cp, "suspicious", "0").strip().lower() in ("1", "true")
            chars.append((text, bbox, conf, suspicious))

    # Aggregate characters into words on whitespace boundaries.
    words: list[Word] = []
    buf_text = ""
    boxes: list[BBox] = []
    confs: list[float] = []
    susp = False

    def flush() -> None:
        nonlocal buf_text, boxes, confs, susp
        if buf_text:
            merged = _merge_boxes(boxes)
            words.append(
                Word(
                    text=buf_text,
                    bbox=merged,
                    confidence=_mean(confs) if confs else 0.0,
                    line_id=_attr(line, "lineId", "") or "",
                    suspicious=susp,
                )
            )
        buf_text, boxes, confs, susp = "", [], [], False

    for text, bbox, conf, is_susp in chars:
        if text.isspace():
            flush()
            continue
        buf_text += text
        boxes.append(bbox)
        confs.append(conf)
        susp = susp or is_susp
    flush()

    line_bbox = BBox(
        x=_to_int(_attr(line, "left")),
        y=_to_int(_attr(line, "top")),
        w=max(0, _to_int(_attr(line, "right")) - _to_int(_attr(line, "left"))),
        h=max(0, _to_int(_attr(line, "bottom")) - _to_int(_attr(line, "top"))),
    )
    if line_bbox.w == 0 and line_bbox.h == 0:
        line_bbox = _merge_boxes([w.bbox for w in words]) if words else BBox(0, 0, 0, 0)

    line_conf = _clamp_confidence(_attr(line, "lineConfidence", "0"))
    if line_conf == 0.0:
        line_conf = _mean([w.confidence for w in words]) if words else 0.0
    text = " ".join(w.text for w in words).strip()
    return TextLine(
        text=text,
        bbox=line_bbox,
        confidence=line_conf,
        words=words,
        line_id=_attr(line, "lineId", ""),
        block_id=block_id,
    )


def _fr_region_bbox(block: Any) -> BBox:
    rects: list[BBox] = []
    region = _find(block, "region")
    if region is not None:
        for rect in _children(region, "rect"):
            left, top = _to_int(_attr(rect, "left")), _to_int(_attr(rect, "top"))
            right, bottom = _to_int(_attr(rect, "right")), _to_int(_attr(rect, "bottom"))
            rects.append(BBox(x=left, y=top, w=max(0, right - left), h=max(0, bottom - top)))
    if not rects:
        rects = [
            BBox(
                x=_to_int(_attr(block, "left")),
                y=_to_int(_attr(block, "top")),
                w=max(0, _to_int(_attr(block, "right")) - _to_int(_attr(block, "left"))),
                h=max(0, _to_int(_attr(block, "bottom")) - _to_int(_attr(block, "top"))),
            )
        ]
    return _merge_boxes(rects) if rects else BBox(0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _merge_boxes(boxes: list[BBox]) -> BBox:
    if not boxes:
        return BBox(0, 0, 0, 0)
    x0 = min(b.x for b in boxes)
    y0 = min(b.y for b in boxes)
    x1 = max(b.x1 for b in boxes)
    y1 = max(b.y1 for b in boxes)
    return BBox(x=x0, y=y0, w=max(0, x1 - x0), h=max(0, y1 - y0))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
