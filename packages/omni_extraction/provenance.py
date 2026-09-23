"""Tri-path provenance records for the omni_extraction package.

Every extraction — whether performed through the Python library, the
``xberg-cli`` binary, or any future path — MUST return a
:class:`ProvenanceRecord`.  Downstream consumers (benchmarks, audit
reports, evaluation harnesses) rely on this record to decide which
truth level a result may be cited at; results without provenance are
treated as UNPROVEN by convention.

The three execution paths currently recognised:

- ``"library"`` — in-process PyO3 library call (``import xberg``)
- ``"cli"``     — subprocess call to the ``xberg-cli`` binary
- ``"package"`` — this wrapper package itself (path composition kept
  explicit so callers can attribute results precisely)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProvenanceRecord:
    """Immutable-ish provenance snapshot for one extraction run.

    Attributes:
        tool: Engine identifier (``"xberg"``).
        tool_version: Version string reported by the engine, when
            obtainable (e.g. ``"1.2.6"``).  ``None`` = not probed.
        path: One of ``"library"``, ``"cli"``, ``"package"``.
        binary_sha256: SHA-256 of the engine binary/CLI when the ``cli``
            path is used (mandatory for CLI citations per the XB-02
            binary-integrity ruling).  ``None`` on the library path.
        allow_network: Whether the engine was permitted to download
            ML assets for this run (upstream default ``True``).
        offline_env: Whether ``HF_HUB_OFFLINE=1``-style offline markers
            were active during the run.
        input_sha256: SHA-256 of the input bytes — computed by this
            package, never trusted from the caller.
        duration_ms: Wall-clock milliseconds of the engine call.
        notes: Free-form, human-readable caveats (e.g. LGPL nuance).
        extra: Opaque engine-specific metadata worth preserving.
    """

    tool: str = "xberg"
    tool_version: Optional[str] = None
    path: str = "library"
    binary_sha256: Optional[str] = None
    allow_network: bool = True
    offline_env: bool = False
    input_sha256: Optional[str] = None
    duration_ms: Optional[float] = None
    notes: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain, JSON-safe dictionary."""
        return {
            "tool": self.tool,
            "tool_version": self.tool_version,
            "path": self.path,
            "binary_sha256": self.binary_sha256,
            "allow_network": self.allow_network,
            "offline_env": self.offline_env,
            "input_sha256": self.input_sha256,
            "duration_ms": self.duration_ms,
            "notes": self.notes,
            "extra": dict(self.extra),
        }


def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 hex digest of *path*'s bytes.

    The digest is always computed here — provenance must never trust a
    caller-supplied hash for the input document.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_binary(path: str) -> str:
    """Alias of :func:`sha256_file` for engine/CLI binary integrity."""
    return sha256_file(path)


def build_provenance(
    path: str,
    input_path: Optional[str] = None,
    started_at: Optional[float] = None,
    tool_version: Optional[str] = None,
    binary_path: Optional[str] = None,
    allow_network: bool = True,
    offline_env: bool = False,
    notes: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> ProvenanceRecord:
    """Build a :class:`ProvenanceRecord` with the timing and hashing done.

    Args:
        path: Execution path identifier (``"library"`` / ``"cli"`` /
            ``"package"``).
        input_path: On-disk input document (hashed here when given).
        started_at: ``time.perf_counter()`` captured before the engine
            call; duration is derived from it.
        tool_version: Engine version probed by the caller.
        binary_path: Engine binary path (hashed for the ``cli`` path —
            binary-integrity ruling makes this mandatory for CLI runs).
        allow_network: Network posture flag for this run.
        offline_env: Whether offline markers were active.
        notes: Human-readable caveats.
        extra: Engine-specific metadata to preserve.
    """
    duration_ms: Optional[float] = None
    if started_at is not None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    input_sha256 = sha256_file(input_path) if input_path else None
    binary_sha256 = sha256_binary(binary_path) if binary_path else None

    return ProvenanceRecord(
        tool="xberg",
        tool_version=tool_version,
        path=path,
        binary_sha256=binary_sha256,
        allow_network=allow_network,
        offline_env=offline_env,
        input_sha256=input_sha256,
        duration_ms=duration_ms,
        notes=notes,
        extra=dict(extra or {}),
    )
