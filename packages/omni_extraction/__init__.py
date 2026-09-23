"""Isolated Xberg document-extraction package.

This package wraps the ``xberg`` extraction engine (PyO3 library + CLI)
behind a small, dependency-light API that satisfies the Omni Medical
Suite's governance rules:

- **Isolation**: ``xberg`` is NOT added to the suite's main dependency
  set.  It lives in its own pinned environment (``requirements.txt``).
- **Fail-closed by default**: every entry point raises a clear
  :class:`ExtractionError` when the engine is unavailable — never a
  silent empty result.
- **Provenance everywhere**: every :class:`ExtractionResult` carries a
  :class:`~packages.omni_extraction.provenance.ProvenanceRecord`
  (tool, version, execution path, binary SHA-256, network posture,
  input hash, duration).
- **No PHI in evidence**: the smoke record referenced by the
  integration report used a synthetic file only.

Pins (verified against PyPI metadata 2026-09-23):

- ``xberg==1.2.6`` (MIT) — upstream HEAD ``588401cec14e``
- Wheel bundles ``libheif 1.23.0`` (LGPL) and ``libonnxruntime`` —
  the LGPL ships inside the Python artifact; recorded as license
  nuance OQ-11 in the XB-02 forensic audit.

Network posture nuance (recorded in the integration report): the xberg
*core* extraction path performs no network I/O, while its *ML* model
download defaults to ``allow_network=true``.  This wrapper mirrors that
upstream default explicitly and offers a strict offline mode.

Example::

    from packages.omni_extraction import XbergExtractor

    ex = XbergExtractor()                # library path
    if ex.is_available():
        result = ex.extract_file("scan.pdf")
        print(result.text[:200])
        print(result.provenance.to_dict())
"""

from packages.omni_extraction.extractor import (
    ExtractionError,
    ExtractionResult,
    XbergExtractor,
)
from packages.omni_extraction.provenance import (
    ProvenanceRecord,
    build_provenance,
)

__all__ = [
    "ExtractionError",
    "ExtractionResult",
    "XbergExtractor",
    "ProvenanceRecord",
    "build_provenance",
]

__version__ = "1.0.0"

#: Pinned upstream engine version this package was built and smoked against.
XBERG_PIN = "1.2.6"
