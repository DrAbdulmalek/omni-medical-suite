"""DEPRECATED compatibility shim — canonical: packages/omnifile/modules/nlp/arabic_rtl.py.

All five byte-identical copies of ``arabic_rtl.py`` were consolidated onto the
omnifile canonical module (branch ``gs/t3-canonical-arabic-rtl``).  This file
re-exports the canonical API so existing import paths keep working, and will
be REMOVED in a future release.

Migrate root-context imports:

    from packages.nlp.arabic_rtl import RTLFixer
    # becomes:
    from packages.arabic_rtl_canonical import RTLFixer

Standalone bundle contexts (``modules.nlp.arabic_rtl`` with a package
directory on ``sys.path``) keep working unchanged; they now transparently
receive the canonical implementation.
"""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

_CANONICAL_RELATIVE = ("packages", "omnifile", "modules", "nlp", "arabic_rtl.py")
_CANONICAL_SYSMODULE_NAME = "packages.omnifile.modules.nlp.arabic_rtl"

warnings.warn(
    "This arabic_rtl compatibility shim is deprecated; import the canonical "
    "module instead: 'from packages.arabic_rtl_canonical import ...' "
    "(canonical file: packages/omnifile/modules/nlp/arabic_rtl.py). "
    "The shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)


def _load_canonical():
    """Return the shared canonical module instance (file-location loading)."""
    cached = sys.modules.get(_CANONICAL_SYSMODULE_NAME)
    if cached is not None:
        return cached
    for parent in Path(__file__).resolve().parents:
        candidate = parent.joinpath(*_CANONICAL_RELATIVE)
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(
                _CANONICAL_SYSMODULE_NAME, candidate
            )
            if spec is None or spec.loader is None:  # pragma: no cover - defensive
                raise ImportError(f"Cannot build an import spec for {candidate}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[_CANONICAL_SYSMODULE_NAME] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        "Cannot locate the canonical arabic_rtl.py "
        f"({'/'.join(_CANONICAL_RELATIVE)}) starting from {__file__}"
    )


_canonical = _load_canonical()

# Re-export the canonical public API (everything public except the
# ``from __future__`` flag and module-level plumbing).
globals().update(
    {
        name: value
        for name, value in vars(_canonical).items()
        if not name.startswith("_") and name != "annotations"
    }
)

__all__ = [
    name
    for name in vars(_canonical)
    if not name.startswith("_") and name not in ("annotations", "logging", "logger")
]
