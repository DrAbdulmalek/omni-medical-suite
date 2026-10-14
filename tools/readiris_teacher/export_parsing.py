"""Parsers for Readiris text exports (TXT / HTML / RTF).

Readiris (IRIS/Canon) is proprietary: no code, SDK or weights of it live in
this repository. These parsers only read the *export files* a locally
licensed copy of Readiris writes for the owner's own documents:

- ``TXT``  : one text file per page; lines only, no geometry, no confidence.
- ``HTML`` : may carry positioned blocks (inline ``left/top/width/height``
  styles) and ``<img src>`` references; parsed with the stdlib
  ``html.parser`` (no third-party dependency).
- ``RTF``  : a minimal stdlib RTF tokenizer (control-word skipping, ``\\'hh``
  byte escapes decoded with a configurable codepage - default cp1256 for
  Arabic Windows exports - and ``\\uN`` unicode escapes).

All confidences absent from the export are recorded as ``0.0`` (unknown);
layout geometry is zero for text-only formats and ``PageAnnotation.has_geometry``
reports whether YOLO layout export / cropping is possible at all.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Union

from .models import BBox, PageAnnotation, SourceFormat, TextBlock, TextLine, Word

__all__ = [
    "ReadirisExportError",
    "detect_format",
    "parse_readiris_export",
    "parse_readiris_export_all",
]

DEFAULT_RTF_CODEPAGE = "cp1256"


class ReadirisExportError(ValueError):
    """Raised when an export file cannot be parsed as any Readiris dialect."""


# --------------------------------------------------------------------------- #
# Format detection
# --------------------------------------------------------------------------- #
_RTF_MAGIC_RE = re.compile(rb"^\{\s*\\rtf")
_HTML_MAGIC_RE = re.compile(
    rb"(?:<!DOCTYPE\s+html|<html[\s>]|<body[\s>]|<p[\s>]|<div[\s>]|<br\s*/?>)",
    re.IGNORECASE,
)


def detect_format(content: Union[bytes, str]) -> SourceFormat:
    """Sniff the export dialect from raw content (bytes or decoded text).

    Raises :class:`ReadirisExportError` when the content matches none of the
    three supported dialects.
    """
    if isinstance(content, str):
        raw = content[:4096].encode("utf-8", errors="replace")
    else:
        raw = content[:4096]
    if _RTF_MAGIC_RE.match(raw.lstrip()):
        return SourceFormat.RTF
    if _HTML_MAGIC_RE.search(raw):
        return SourceFormat.HTML
    # TXT is the permissive fallback: any decodable text is accepted.
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ReadirisExportError(
            "content is not RTF, not HTML, and not valid UTF-8 text; "
            "refusing to guess a Readiris export format"
        )
    return SourceFormat.TXT


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# TXT parser (one file == one page)
# --------------------------------------------------------------------------- #
def _parse_txt(text: str) -> list[TextBlock]:
    """TXT exports have lines only: zero boxes, unknown confidence."""
    lines: list[TextLine] = []
    for i, raw_line in enumerate(text.splitlines(), start=1):
        clean = raw_line.strip()
        if not clean:
            continue
        words = [
            Word(text=w, bbox=BBox(0, 0, 0, 0), confidence=0.0, line_id=f"l{i}")
            for w in clean.split()
        ]
        lines.append(
            TextLine(
                text=clean,
                bbox=BBox(0, 0, 0, 0),
                confidence=0.0,
                words=words,
                line_id=f"l{i}",
                block_id="b1",
            )
        )
    return [TextBlock(block_id="b1", block_type="paragraph", bbox=BBox(0, 0, 0, 0), lines=lines)]


# --------------------------------------------------------------------------- #
# HTML parser (stdlib html.parser; positioned blocks when present)
# --------------------------------------------------------------------------- #
_STYLE_POS_RE = re.compile(
    r"(?P<key>left|top|width|height)\s*:\s*(-?[\d.]+)\s*(?:px|pt)?", re.IGNORECASE
)
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote"}
_SKIP_TAGS = {"script", "style", "head", "title"}


class _ReadirisHtmlParser(HTMLParser):
    """Collect text lines per block element, with boxes from inline styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[TextBlock] = []
        self.image_filename: str = ""
        self._skip_depth = 0
        self._block_counter = 0
        # stack of (block_id, block_type, bbox, current_line_text, line_bbox)
        self._open: list[dict] = []

    # -- helpers ---------------------------------------------------------- #
    @staticmethod
    def _style_box(attrs: dict[str, str]) -> Optional[BBox]:
        style = attrs.get("style", "") or ""
        found = {m.group("key").lower(): float(m.group(2)) for m in _STYLE_POS_RE.finditer(style)}
        if not {"left", "top", "width", "height"} <= found.keys():
            return None
        return BBox(
            x=int(round(found["left"])),
            y=int(round(found["top"])),
            w=int(round(found["width"])),
            h=int(round(found["height"])),
        )

    def _ensure_block(self, block_type: str, bbox: BBox) -> dict:
        if self._open:
            return self._open[-1]
        self._block_counter += 1
        entry = {
            "block_id": f"b{self._block_counter}",
            "block_type": block_type,
            "bbox": bbox,
            "line_parts": [],
            "line_bbox": bbox,
        }
        self._open.append(entry)
        return entry

    # -- HTMLParser hooks -------------------------------------------------- #
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        adict = {k: (v or "") for k, v in attrs}
        if tag == "img" and not self.image_filename:
            self.image_filename = adict.get("src", "") or ""
        if tag in _BLOCK_TAGS:
            box = self._style_box(adict) or BBox(0, 0, 0, 0)
            self._ensure_block(tag, box)
        if tag in ("br", "p", "li", "tr") and self._open:
            # explicit line break closes the current line
            self._flush_line()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in _BLOCK_TAGS and self._open:
            self._flush_line()
            entry = self._open.pop()
            text = " ".join(p.strip() for p in entry["line_parts"] if p.strip())
            if text:
                self.blocks.append(self._materialise(entry, [text]))

    def handle_data(self, data):
        if self._skip_depth or not self._open:
            return
        chunk = data.strip()
        if chunk:
            self._open[-1]["line_parts"].append(chunk)

    # -- materialisation ---------------------------------------------------- #
    def _flush_line(self) -> None:
        if not self._open:
            return
        entry = self._open[-1]
        if entry["line_parts"]:
            text = " ".join(p.strip() for p in entry["line_parts"] if p.strip())
            if text:
                self.blocks.append(self._materialise(entry, [text]))
            entry["line_parts"] = []

    def _materialise(self, entry: dict, texts: list[str]) -> TextBlock:
        lines: list[TextLine] = []
        for k, text in enumerate(texts, start=1):
            words = [
                Word(text=w, bbox=BBox(0, 0, 0, 0), confidence=0.0, line_id=f"{entry['block_id']}l{k}")
                for w in text.split()
            ]
            lines.append(
                TextLine(
                    text=text,
                    bbox=entry["line_bbox"],
                    confidence=0.0,
                    words=words,
                    line_id=f"{entry['block_id']}l{k}",
                    block_id=entry["block_id"],
                )
            )
        return TextBlock(
            block_id=entry["block_id"],
            block_type=entry["block_type"],
            bbox=entry["bbox"],
            lines=lines,
        )

    def close(self) -> None:  # flush any unterminated trailing block
        super().close()
        while self._open:
            self._flush_line()
            entry = self._open.pop()
            text = " ".join(p.strip() for p in entry["line_parts"] if p.strip())
            if text:
                self.blocks.append(self._materialise(entry, [text]))


_PAGE_BREAK_RE = re.compile(
    r"<div[^>]*class=\"[^\"]*(?:page-break|pagebreak)[^\"]*\"[^>]*>"
    r"|<!--\s*page\s*break\s*-->"
    r"|<hr[^>]*>",
    re.IGNORECASE,
)


def _parse_html(html_text: str) -> tuple[list[TextBlock], str]:
    parser = _ReadirisHtmlParser()
    parser.feed(html_text)
    parser.close()
    blocks = parser.blocks
    if not blocks:
        # Degenerate fragment (no block tags): fall back to plain text lines.
        stripped = re.sub(r"<[^>]+>", "\n", html_text)
        blocks = _parse_txt(stripped)
    return blocks, parser.image_filename


# --------------------------------------------------------------------------- #
# RTF parser (minimal stdlib tokenizer)
# --------------------------------------------------------------------------- #
_SKIP_DESTINATIONS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
    "header", "footer", "listtable", "listoverridetable", "rsidtbl",
    "generator", "themedata", "colorschememapping", "latentstyles",
    "datastore", "xmlnstbl",
}


class _RtfTokenizer:
    """Extract plain text lines from an RTF document (Arabic-friendly).

    Skips destination groups (fonttbl/colortbl/stylesheet/info/pict/... and
    every ``{\\*...}`` extended group), decodes ``\\'hh`` byte escapes with a
    configurable codepage and ``\\uN`` unicode escapes (dropping the
    ``\\ucN`` alternate-representation bytes that follow).
    """

    def __init__(self, codepage: str = DEFAULT_RTF_CODEPAGE) -> None:
        self.codepage = codepage
        self.lines: list[list[str]] = [[]]
        self.uc_skip_count = 1  # value of the last seen \ucN (spec default 1)
        self.pending_skip = 0   # alternate bytes left to skip after a \uN

    # -- helpers ---------------------------------------------------------- #
    def _emit(self, ch: str) -> None:
        self.lines[-1].append(ch)

    def _newline(self) -> None:
        if self.lines[-1]:
            self.lines.append([])

    # -- main scan --------------------------------------------------------- #
    def parse(self, raw: str) -> list[str]:
        i, n = 0, len(raw)
        group_depth = 0
        dest_depth: Optional[int] = None  # skipping a destination group opened at this depth
        while i < n:
            ch = raw[i]
            if ch == "{":
                group_depth += 1
                if dest_depth is None:
                    if raw.startswith("{\\*", i):
                        dest_depth = group_depth  # unknown extended group: discard
                    else:
                        m = re.match(r"\{\s*(?:\\\*)?\\([a-zA-Z]+)", raw[i:])
                        if m and m.group(1).lower() in _SKIP_DESTINATIONS:
                            dest_depth = group_depth
                i += 1
                continue
            if ch == "}":
                if dest_depth is not None and group_depth == dest_depth:
                    dest_depth = None
                group_depth = max(0, group_depth - 1)
                i += 1
                continue
            if dest_depth is not None:
                i += 1
                continue
            if ch == "\\":
                i = self._control_word(raw, i)
                continue
            if self.pending_skip > 0:
                # alternate-representation bytes of a \uN escape: skip one item
                if ch == "\\":
                    m = re.match(r"\\'[0-9a-fA-F]{2}|\\[a-zA-Z]+-?\d* ?|\\.", raw[i:])
                    i += m.end() if m else 1
                else:
                    i += 1
                self.pending_skip -= 1
                continue
            if ch in "\r\n":
                i += 1
                continue
            self._emit(ch)
            i += 1
        out: list[str] = []
        for parts in self.lines:
            text = "".join(parts).strip()
            if text:
                out.append(text)
        return out

    def _control_word(self, raw: str, i: int) -> int:
        """Handle one control word / escaped char starting at raw[i] == '\\'."""
        n = len(raw)
        if i + 1 >= n:
            return i + 1
        nxt = raw[i + 1]
        # hex byte escape \'hh
        if nxt == "'":
            hex_pair = raw[i + 2:i + 4]
            try:
                byte = bytes([int(hex_pair, 16)])
                self._emit(byte.decode(self.codepage, errors="replace"))
            except ValueError:
                pass
            return i + 4
        # escaped symbols
        if nxt in "{}\\":
            self._emit(nxt)
            return i + 2
        if nxt == "~":
            self._emit("\u00a0")
            return i + 2
        if nxt == "*":  # extended-destination marker: the brace handler skips it
            return i + 2
        m = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?", raw[i:])
        if not m:
            return i + 2
        word, num = m.group(1).lower(), m.group(2)
        end = i + m.end()
        if word == "u" and num is not None:
            cp = int(num)
            if cp < 0:
                cp += 65536
            self._emit(chr(cp))
            self.pending_skip = max(0, self.uc_skip_count)
            return end
        if word == "uc" and num is not None:
            self.uc_skip_count = int(num)
            return end
        if word in ("par", "sect", "page", "line"):
            self._newline()
            return end
        if word == "tab":
            self._emit("\t")
            return end
        # any other control word (formatting, font refs) -> ignore
        return end


def _parse_rtf(rtf_text: str, codepage: str = DEFAULT_RTF_CODEPAGE) -> list[TextBlock]:
    tok = _RtfTokenizer(codepage)
    lines_text = tok.parse(rtf_text)
    blocks: list[TextBlock] = []
    block = TextBlock(block_id="b1", block_type="paragraph", bbox=BBox(0, 0, 0, 0))
    for i, text in enumerate(lines_text, start=1):
        words = [
            Word(text=w, bbox=BBox(0, 0, 0, 0), confidence=0.0, line_id=f"l{i}")
            for w in text.split()
        ]
        block.lines.append(
            TextLine(text=text, bbox=BBox(0, 0, 0, 0), confidence=0.0, words=words,
                     line_id=f"l{i}", block_id="b1")
        )
    if block.lines:
        blocks.append(block)
    return blocks


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def _read_source(path: Union[str, Path]) -> tuple[str, bytes, str]:
    p = Path(path)
    if not p.is_file():
        raise ReadirisExportError(f"export file not found: {p}")
    data = p.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return text, data, str(p)


def parse_readiris_export(
    path: Union[str, Path],
    rtf_codepage: str = DEFAULT_RTF_CODEPAGE,
) -> PageAnnotation:
    """Parse one Readiris export file into a :class:`PageAnnotation`.

    Multi-page HTML exports are reduced to their first page here; use
    :func:`parse_readiris_export_all` to get every page.
    """
    return parse_readiris_export_all(path, rtf_codepage=rtf_codepage)[0]


def parse_readiris_export_all(
    path: Union[str, Path],
    rtf_codepage: str = DEFAULT_RTF_CODEPAGE,
) -> list[PageAnnotation]:
    """Parse a Readiris export file into one annotation per page.

    - TXT / RTF: a single annotation per file.
    - HTML: split at common page-break markers, else a single annotation.

    Format detection sniffs the content; a ``.html/.htm`` extension acts as a
    hint so tag-less HTML fragments still go through the HTML path.
    """
    text, data, source = _read_source(path)
    digest = _sha256_of_bytes(data)
    fmt = detect_format(text)
    if fmt is SourceFormat.TXT and Path(source.split("#", 1)[0]).suffix.lower() in (".html", ".htm"):
        fmt = SourceFormat.HTML
    pages_html = [text]

    if fmt is SourceFormat.HTML:
        pages_html = [p for p in _PAGE_BREAK_RE.split(text) if p and re.search(r"\S", re.sub(r"<[^>]+>", " ", p))]
        if not pages_html:
            pages_html = [text]

    annotations: list[PageAnnotation] = []
    for page_index, page_text in enumerate(pages_html, start=1):
        if fmt is SourceFormat.HTML:
            blocks, image_filename = _parse_html(page_text)
        elif fmt is SourceFormat.RTF:
            blocks, image_filename = _parse_rtf(page_text, codepage=rtf_codepage), ""
        else:
            blocks, image_filename = _parse_txt(page_text), ""

        width = max((b.bbox.x1 for b in blocks), default=0)
        height = max((b.bbox.y1 for b in blocks), default=0)
        for b in blocks:
            if not b.bbox.has_geometry:
                b.bbox = BBox(0, 0, 0, 0)

        annotations.append(
            PageAnnotation(
                source_format=fmt,
                image_filename=image_filename,
                width=width,
                height=height,
                dpi=None,
                blocks=blocks,
                source_path=f"{source}#page={page_index}" if len(pages_html) > 1 else source,
                export_sha256=digest,
            )
        )
    if not annotations:
        raise ReadirisExportError(f"no pages could be parsed from {source}")
    return annotations
