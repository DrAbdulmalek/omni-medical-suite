"""TASK 002 - engine registry consistency guard.

Evidence (PHASE 1): packages/core/engine_registry.py and
hf-space/packages/core/engine_registry.py were BYTE-IDENTICAL at base
39640a6d (both sha256 = 63178968028a030911a242e57013e37212ab071d0f75e77ac962d9199d257c4a).

Until the HF Space can safely import the canonical module (standalone
deploy constraint - shim deferred with documented reason in
docs/portfolio/REGISTRY_DEDUP.md), this test fails loudly if the two
copies drift apart.
"""
import hashlib
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[3]
CANONICAL = REPO / "packages" / "core" / "engine_registry.py"
HF_MIRROR = REPO / "hf-space" / "packages" / "core" / "engine_registry.py"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_registry_copies_are_in_sync():
    assert CANONICAL.exists(), f"missing {CANONICAL}"
    assert HF_MIRROR.exists(), f"missing {HF_MIRROR}"
    assert _sha256(CANONICAL) == _sha256(HF_MIRROR), (
        "engine_registry.py copies diverged - "
        "packages/core is canonical; reconcile hf-space mirror"
    )


def test_canonical_engine_ids_present():
    src = CANONICAL.read_text(encoding="utf-8")
    pattern = (
        r"class _(?:EasyOCR|Tesseract|TrOCR|PaddleOCR|QwenHandwritten|QARI|Nougat)"
        r"Adapter\(EngineAdapter\):\s*\n\s*name = \"([^\"]+)\""
    )
    names = set(re.findall(pattern, src))
    expected = {
        "EasyOCR",
        "Tesseract",
        "TrOCR",
        "PaddleOCR",
        "Arabic-handwritten-OCR (Qwen)",
        "QARI",
        "Nougat",
    }
    assert expected <= names, f"missing engine ids: {sorted(expected - names)}"
