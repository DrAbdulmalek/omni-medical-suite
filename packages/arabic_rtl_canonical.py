"""Stable root-context accessor for the canonical Arabic RTL module.

The single canonical implementation lives at
``packages/omnifile/modules/nlp/arabic_rtl.py``.  The five former
byte-identical copies of that file were consolidated onto the omnifile
canonical module (branch ``gs/t3-canonical-arabic-rtl``).

Because ``packages/omnifile/modules/nlp/__init__.py`` imports its siblings
through the standalone ``modules.*`` namespace, the canonical package cannot
be imported hierarchically from the repository root.  This accessor therefore
loads the canonical file directly (importlib file-location loading) and
re-exports its public API *without* triggering any deprecation warning.

Root-context code should import from here:

    from packages.arabic_rtl_canonical import (
        RTLFixer,
        is_rtl_text,
        get_text_direction,
        ARABIC_NORMALIZATION_MAP,
    )

The loaded module is cached in ``sys.modules`` under
``packages.omnifile.modules.nlp.arabic_rtl`` so every access path (this
accessor and the deprecated shims) shares one module instance and therefore
one identity for every exported object.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

__all__ = [
    "ARABIC_NORMALIZATION_MAP",
    "RTLFixer",
    "get_text_direction",
    "is_rtl_text",
    "load_canonical_arabic_rtl",
]

_CANONICAL_RELATIVE = ("packages", "omnifile", "modules", "nlp", "arabic_rtl.py")
_CANONICAL_SYSMODULE_NAME = "packages.omnifile.modules.nlp.arabic_rtl"


def _find_canonical_path() -> Path:
    """Walk upwards from this file until the canonical module is found."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent.joinpath(*_CANONICAL_RELATIVE)
        if candidate.is_file():
            return candidate
    raise ImportError(
        "Cannot locate the canonical Arabic RTL module "
        f"({'/'.join(_CANONICAL_RELATIVE)}) starting from {__file__}"
    )


def load_canonical_arabic_rtl() -> ModuleType:
    """Return the canonical ``arabic_rtl`` module, loading it once if needed."""
    cached = sys.modules.get(_CANONICAL_SYSMODULE_NAME)
    if cached is not None:
        return cached
    canonical_path = _find_canonical_path()
    spec = importlib.util.spec_from_file_location(_CANONICAL_SYSMODULE_NAME, canonical_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Cannot build an import spec for {canonical_path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so intra-module references resolve consistently.
    sys.modules[_CANONICAL_SYSMODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_canonical = load_canonical_arabic_rtl()

RTLFixer = _canonical.RTLFixer
is_rtl_text = _canonical.is_rtl_text
get_text_direction = _canonical.get_text_direction
ARABIC_NORMALIZATION_MAP = _canonical.ARABIC_NORMALIZATION_MAP
