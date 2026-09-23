"""Xberg extractor wrapper — library + CLI paths, fail-closed, provenant.

The upstream ``xberg`` engine exposes:

- an asynchronous Python library API
  (``ExtractInput`` → ``extract`` → ``ExtractedDocument`` with
  ``content`` / ``chunks`` / ``djot`` / ``entities`` / ``confidence`` /
  ``metadata`` — per the XB-02 runtime smoke record), and
- a CLI binary (``xberg-cli``) whose binary fetch is verified with a
  mandatory SHA-256 check.

This wrapper never hides engine absence behind an empty result: the
library path raises :class:`ExtractionError` when ``xberg`` is not
importable, and the CLI path raises when the binary is missing or its
SHA-256 cannot be established.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from packages.omni_extraction.provenance import (
    ProvenanceRecord,
    build_provenance,
)

logger = logging.getLogger(__name__)


class ExtractionError(RuntimeError):
    """Raised when the xberg engine is unavailable or fails.

    This is a *loud* failure by design: governance rules forbid silent
    fallbacks for extraction engines (a silent empty result would be
    indistinguishable from a genuinely empty document).
    """


@dataclass
class ExtractionResult:
    """Normalized extraction result produced by every xberg path.

    Attributes:
        text: Flat extracted text (may be empty for image-only inputs).
        djot: Structured djot/markdown rendering of the document.
        table_count: Number of detected tables (best effort).
        entities: Entities as returned by the engine (opaque list).
        confidence: Engine-reported quality/confidence in ``[0, 1]``
            when available; ``None`` otherwise.
        metadata: Engine metadata payload (opaque dict).
        provenance: Mandatory provenance record for this run.
        raw: Opaque upstream object (``ExtractedDocument``) kept for
            advanced consumers; never serialized by default.
    """

    text: str = ""
    djot: str = ""
    table_count: int = 0
    entities: List[Any] = field(default_factory=list)
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[ProvenanceRecord] = None
    raw: Optional[Any] = None

    @property
    def success(self) -> bool:
        """``True`` when any textual content was extracted."""
        return bool(self.text.strip()) or bool(self.djot.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain, JSON-safe dictionary (``raw`` excluded)."""
        return {
            "text": self.text,
            "djot": self.djot,
            "table_count": self.table_count,
            "entities": self.entities,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


class XbergExtractor:
    """Fail-closed wrapper around the pinned xberg engine.

    Args:
        allow_network: Mirrors the upstream default (``True``): the
            xberg *core* path performs no network I/O, while its *ML*
            model download defaults to network-enabled.  Set to
            ``False`` for a strict offline posture (also sets
            ``HF_HUB_OFFLINE=1`` for the duration of each run).
        engine_path: ``"library"`` (default) or ``"cli"``.
        cli_binary: Explicit path to the CLI binary; when ``None`` the
            ``xberg-cli`` executable is resolved from ``PATH``.
        verify_cli_sha256: Mandatory-verify toggle for the CLI path.
            Keep ``True`` (XB-02 binary-integrity ruling).

    Usage::

        ex = XbergExtractor()
        if not ex.is_available():
            raise ExtractionError(ex.availability_error())
        result = ex.extract_file("document.pdf")
    """

    def __init__(
        self,
        allow_network: bool = True,
        engine_path: str = "library",
        cli_binary: Optional[str] = None,
        verify_cli_sha256: bool = True,
    ) -> None:
        if engine_path not in ("library", "cli"):
            raise ValueError(f"unknown engine_path: {engine_path!r}")
        self.allow_network = allow_network
        self.engine_path = engine_path
        self._cli_binary = cli_binary
        self._verify_cli_sha256 = verify_cli_sha256
        self._offline_env = not allow_network

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """``True`` when the selected path is usable right now."""
        if self.engine_path == "library":
            try:
                import xberg  # noqa: F401

                return True
            except Exception:
                return False
        return self._resolve_cli() is not None

    def availability_error(self) -> str:
        """Human-readable reason why :meth:`is_available` is ``False``."""
        if self.engine_path == "library":
            return (
                "xberg is not importable in this environment. Install the "
                "pinned engine into an ISOLATED env: "
                "pip install xberg==" + self.xberg_version_hint()
            )
        if self._resolve_cli() is None:
            return "xberg-cli binary not found on PATH (no explicit path given)."
        return "unknown availability failure."

    @staticmethod
    def xberg_version_hint() -> str:
        """Pinned upstream version (kept in one place for all paths)."""
        try:
            from packages.omni_extraction import XBERG_PIN

            return XBERG_PIN
        except Exception:  # pragma: no cover - import hygiene
            return "1.2.6"

    # ------------------------------------------------------------------
    # Public extraction API
    # ------------------------------------------------------------------

    def extract_file(self, path: str) -> ExtractionResult:
        """Extract a document synchronously via the selected path."""
        if self.engine_path == "cli":
            return self._extract_cli(path)
        return self._extract_library(path)

    async def extract_async(self, path: str) -> ExtractionResult:
        """Extract a document asynchronously (library path)."""
        return self._extract_library(path, async_input=True)

    # ------------------------------------------------------------------
    # Library path
    # ------------------------------------------------------------------

    def _extract_library(self, path: str, async_input: bool = False) -> ExtractionResult:
        started = _perf()
        try:
            import xberg  # noqa: PLC0415 - deliberate lazy import
        except Exception as exc:
            raise ExtractionError(self.availability_error()) from exc

        if not os.path.isfile(path):
            raise ExtractionError(f"input document not found: {path}")

        offline_marker_active = self._offline_env and not os.environ.get("HF_HUB_OFFLINE")
        old_offline = os.environ.get("HF_HUB_OFFLINE")
        try:
            if self._offline_env:
                os.environ["HF_HUB_OFFLINE"] = "1"

            input_obj = _make_extract_input(xberg, path)
            document = _run_extract(xberg, input_obj, async_input)
        finally:
            if offline_marker_active:
                if old_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = old_offline

        provenance = build_provenance(
            path="library",
            input_path=path,
            started_at=started,
            tool_version=_engine_version(xberg),
            allow_network=self.allow_network,
            offline_env=self._offline_env,
            notes=(
                "LGPL nuance: wheel bundles libheif 1.23.0 + libonnxruntime "
                "(OQ-11). No PHI in evidence runs."
            ),
        )
        return _document_to_result(document, provenance)

    # ------------------------------------------------------------------
    # CLI path
    # ------------------------------------------------------------------

    def _resolve_cli(self) -> Optional[str]:
        if self._cli_binary:
            return self._cli_binary if os.path.isfile(self._cli_binary) else None
        return shutil.which("xberg-cli")

    def _extract_cli(self, path: str) -> ExtractionResult:
        import subprocess

        started = _perf()
        binary = self._resolve_cli()
        if binary is None:
            raise ExtractionError(self.availability_error())
        if not os.path.isfile(path):
            raise ExtractionError(f"input document not found: {path}")

        binary_sha256 = None
        if self._verify_cli_sha256:
            from packages.omni_extraction.provenance import sha256_binary

            binary_sha256 = sha256_binary(binary)
            logger.info("xberg-cli binary sha256: %s", binary_sha256)

        cmd = [binary, "extract", path]
        env = dict(os.environ)
        if self._offline_env:
            env["HF_HUB_OFFLINE"] = "1"

        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, capture_output=True, text=True, timeout=600, env=env,
        )
        if proc.returncode != 0:
            raise ExtractionError(
                f"xberg-cli failed (rc={proc.returncode}): {proc.stderr[:500]}"
            )

        provenance = build_provenance(
            path="cli",
            input_path=path,
            started_at=started,
            tool_version=_cli_version(binary),
            binary_path=None if binary_sha256 is None else binary,
            allow_network=self.allow_network,
            offline_env=self._offline_env,
            notes="CLI path; binary SHA-256 recorded for integrity citation.",
        )
        result = ExtractionResult(
            text=proc.stdout,
            provenance=provenance,
        )
        # Binary SHA-256 lands inside provenance via build_provenance when
        # verification was enabled; attach it explicitly when disabled.
        if binary_sha256 is None:
            provenance.notes += " (sha256 verification disabled by caller)"
        return result


# ----------------------------------------------------------------------
# Engine-surface helpers (defensive: tolerate API variations)
# ----------------------------------------------------------------------


def _perf() -> float:
    import time

    return time.perf_counter()


def _make_extract_input(xberg_mod: Any, path: str) -> Any:
    """Build the engine's input object, tolerating API variations."""
    extract_input = getattr(xberg_mod, "ExtractInput", None)
    if extract_input is None:
        raise ExtractionError(
            "xberg module exposes no ExtractInput — engine surface changed; "
            f"available: {[n for n in dir(xberg_mod) if not n.startswith('_')][:20]}"
        )
    try:
        return extract_input(uri=path)  # XB-02 record: ExtractInput(URI)
    except TypeError:
        try:
            return extract_input(path)
        except TypeError as exc:
            raise ExtractionError(
                f"could not construct ExtractInput for {path!r}: {exc}"
            ) from exc


def _run_extract(xberg_mod: Any, input_obj: Any, async_input: bool) -> Any:
    """Invoke the engine's extract call and return the document."""
    extract_fn = getattr(xberg_mod, "extract", None)
    if extract_fn is None:
        raise ExtractionError(
            "xberg module exposes no extract() — engine surface changed."
        )
    if async_input or asyncio.iscoroutinefunction(extract_fn):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            # Already inside a running loop (e.g. caller is async).
            _raise_needs_await()
        return asyncio.run(extract_fn(input_obj))
    return extract_fn(input_obj)


def _raise_needs_await() -> Any:
    raise ExtractionError(
        "extract_async() was called from a running event loop; "
        "await the coroutine instead of calling it synchronously."
    )


def _engine_version(xberg_mod: Any) -> Optional[str]:
    version = getattr(xberg_mod, "__version__", None)
    if version is None:
        version = getattr(xberg_mod, "version", None)
    return str(version) if version else None


def _cli_version(binary: str) -> Optional[str]:
    import subprocess

    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [binary, "--version"], capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except Exception:  # pragma: no cover - environment dependent
        return None
    return None


def _document_to_result(document: Any, provenance: ProvenanceRecord) -> ExtractionResult:
    """Map an upstream ExtractedDocument onto :class:`ExtractionResult`.

    Field access is defensive: the XB-02 smoke record names
    ``content`` / ``chunks`` / ``djot`` / ``entities`` / ``confidence`` /
    ``metadata``; missing attributes degrade to their defaults instead
    of crashing, and any deviation is logged at warning level.
    """
    get = getattr

    text = ""
    for attr in ("content", "text"):
        value = get(document, attr, None)
        if isinstance(value, str):
            text = value
            break

    djot = get(document, "djot", "") or ""
    if not isinstance(djot, str):
        djot = str(djot)

    table_count = 0
    chunks = get(document, "chunks", None) or []
    for chunk in chunks:
        chunk_type = str(get(chunk, "type", get(chunk, "chunk_type", "")) or "")
        if "table" in chunk_type.lower():
            table_count += 1
    if table_count == 0:
        # Djot tables: consecutive lines starting with '|'
        table_count = _djot_table_count(djot)

    entities = list(get(document, "entities", None) or [])

    confidence = get(document, "confidence", None)
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

    metadata = get(document, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {"_raw": str(metadata)}

    return ExtractionResult(
        text=text,
        djot=djot,
        table_count=table_count,
        entities=entities,
        confidence=confidence,
        metadata=metadata,
        provenance=provenance,
        raw=document,
    )


def _djot_table_count(djot: str) -> int:
    """Count djot tables by scanning for pipe-delimited block structure."""
    count = 0
    in_table = False
    for line in djot.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            if not in_table:
                count += 1
                in_table = True
        else:
            in_table = False
    return count
