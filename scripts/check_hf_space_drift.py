#!/usr/bin/env python3
# scripts/check_hf_space_drift.py
# =============================================================================
# Mirror audit: verify that the frozen HF Space entrypoint (hf-space/app_core.py)
# and the canonical service module (app/services/ocr_service.py) agree on
# the OCR knobs that MUST stay parallel.
#
# Unlike scripts/sync-hf-space.sh (which compares whole directories that
# are auto-synced), this script compares the *contents* of two specific
# files that are intentionally NOT auto-synced:
#
#   - hf-space/app_core.py        (frozen HF application core)
#   - app/services/ocr_service.py (canonical service module; lazy getters)
#
# It extracts four kinds of knobs and compares them as normalized strings:
#   1. PaddleOCR(...) constructor kwargs
#   2. ImagePreprocessor(...) constructor kwargs
#   3. Tesseract invocation parameters (lang, psm)
#   4. OCR_CORRECTIONS dict contents
#
# Exit codes:
#   0 — all four knobs match
#   1 — at least one knob differs (prints diff)
#   2 — could not extract a knob from one of the files (file structure
#       changed — manual review needed)
#
# Used by .github/workflows/hf-space-drift.yml.
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HF_APP = REPO_ROOT / "hf-space" / "app_core.py"
SVC = REPO_ROOT / "app" / "services" / "ocr_service.py"


def _read(path: Path) -> str:
    if not path.is_file():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(2)
    src = path.read_text(encoding="utf-8")
    lines = []
    for ln in src.splitlines():
        out = []
        in_str = None
        i = 0
        while i < len(ln):
            ch = ln[i]
            if in_str:
                out.append(ch)
                if ch == in_str and (i == 0 or ln[i - 1] != "\\"):
                    in_str = None
            elif ch in ('"', "'"):
                in_str = ch
                out.append(ch)
            elif ch == "#":
                break
            else:
                out.append(ch)
            i += 1
        lines.append("".join(out))
    return "\n".join(lines)


def _normalize_kwargs(block: str) -> str:
    block = re.sub(r"#.*$", "", block)
    block = re.sub(r"^\s*\w+\s*=\s*[A-Za-z_]\w*\s*\(", "(", block, flags=re.M)
    block = re.sub(r"^\s*[A-Za-z_]\w*\s*\(", "(", block, flags=re.M)
    lines = [ln.strip().rstrip(",").strip() for ln in block.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def extract_call(src: str, func_name: str) -> str | None:
    pattern = rf"(?:\w+\s*=\s*)?{re.escape(func_name)}\s*\("
    m = re.search(pattern, src)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    end = None
    for i in range(start, len(src)):
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return None
    return _normalize_kwargs(src[start + 1 : end])


def extract_tesseract_calls(src: str) -> list[str]:
    pattern = r"pytesseract\.image_to_\w+\s*\("
    calls: list[str] = []
    for m in re.finditer(pattern, src):
        start = m.end() - 1
        depth = 0
        end = None
        for i in range(start, len(src)):
            ch = src[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            continue
        calls.append(_normalize_kwargs(src[start + 1 : end]))
    return sorted(calls)


def extract_ocr_corrections(src: str) -> str | None:
    m = re.search(r"OCR_CORRECTIONS\s*=\s*\{([^}]+)\}", src, re.S)
    if not m:
        return None
    body = re.sub(r"#.*$", "", m.group(1))
    entries = [ln.strip().rstrip(",").strip() for ln in body.splitlines()]
    return "\n".join(ln for ln in entries if ln)


def compare(label: str, hf_val: str | None, app_val: str | None) -> bool:
    if hf_val is None:
        print(f"❌ {label}: could not extract from hf-space/app_core.py", file=sys.stderr)
        return False
    if app_val is None:
        print(f"❌ {label}: could not extract from app/services/ocr_service.py", file=sys.stderr)
        return False
    if hf_val == app_val:
        print(f"✅ {label}: match")
        return True
    print(f"❌ {label}: DRIFT")
    print("--- hf-space/app_core.py ---")
    print(hf_val)
    print("--- app/services/ocr_service.py ---")
    print(app_val)
    print("--- end ---")
    return False


def main() -> int:
    hf_src = _read(HF_APP)
    app_src = _read(SVC)

    print("=== Mirror audit: hf-space/app_core.py ↔ app/services/ocr_service.py ===")
    print(f"  hf-space/app_core.py          ({HF_APP.stat().st_size} bytes)")
    print(f"  app/services/ocr_service.py   ({SVC.stat().st_size} bytes)")
    print()

    ok = True
    ok &= compare("PaddleOCR kwargs", extract_call(hf_src, "PaddleOCR"), extract_call(app_src, "PaddleOCR"))
    ok &= compare("ImagePreprocessor kwargs", extract_call(hf_src, "ImagePreprocessor"), extract_call(app_src, "ImagePreprocessor"))
    ok &= compare("Tesseract calls", "\n".join(extract_tesseract_calls(hf_src)), "\n".join(extract_tesseract_calls(app_src)))
    ok &= compare("OCR_CORRECTIONS dict", extract_ocr_corrections(hf_src), extract_ocr_corrections(app_src))

    print()
    if ok:
        print("✅ All knobs match — no drift.")
        return 0
    print("❌ Drift detected. See docs/DEPLOYMENT.md § 'HF Space drift control'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
