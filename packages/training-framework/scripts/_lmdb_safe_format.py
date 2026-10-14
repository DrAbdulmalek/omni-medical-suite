"""Safe (non-pickle) LMDB serialization for HTR training samples.

This module isolates the JSON+base64 LMDB producer/consumer so it can be
imported and tested WITHOUT the heavy ML stack (torch, transformers,
peft, datasets, cv2, numpy, PIL) that the surrounding training scripts
require at module-load time. The serialization boundary is intentionally
narrow: only stdlib (``json``, ``base64``, ``shutil``, ``pathlib``) and
``lmdb`` are imported here.

Producer contract (matches the historical schema established in
commit ``ef1d168``):

    LMDB keys:
        ``{idx:08d}`` (UTF-8 encoded string of zero-padded 8-digit index)
        ``b'__len__'`` (UTF-8 encoded decimal sample count)

    LMDB value (per sample, UTF-8 JSON bytes):
        {
            "image":  "<base64-encoded image-file bytes (PNG/JPEG/etc.)>",
            "text":   "<str>",
            "source": "<str>"
        }

Consumer behavior:

    - Reads ``__len__`` to determine sample count.
    - For each index key, reads the raw LMDB value.
    - Rejects any value whose first byte is not ``{`` (the JSON marker).
      Legacy pickle-based LMDBs are rejected with an explicit
      ``ValueError`` directing the operator to regenerate the dataset
      via ``prepare_htr_dataset.py``. NO pickle fallback.
    - Parses the value as JSON (UTF-8).
    - Base64-decodes the ``image`` field back to raw bytes.

The consumer returns the decoded ``dict`` per sample, leaving the
caller free to interpret the ``image`` bytes (e.g., ``Image.open`` for
PIL reconstruction in G3, or pass through as-is for G2).

Security invariants (verified by ``tests/security/test_no_pickle_deserialization.py``):

    - This module NEVER imports ``pickle`` or any deserialization API
      capable of arbitrary code execution.
    - This module NEVER imports ``torch``, ``transformers``, ``peft``,
      ``datasets``, ``cv2``, ``numpy``, or ``PIL`` — those heavy ML
      deps belong to the surrounding training scripts, not the
      serialization boundary. (A static source-check test enforces this.)
    - This module performs no ``eval`` / ``exec`` / AST execution /
      ``__reduce__`` invocation. JSON is non-executable by construction.
"""
from __future__ import annotations

import json
import shutil
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Iterator

import lmdb

# Match the historical producer map size (1 TB) so LMDBFormatter.format()
# delegation preserves the exact on-disk layout that operators may have
# produced with prior versions of prepare_htr_dataset.py.
LMDB_MAP_SIZE = 1099511627776  # 1TB


def write_sample_lmdb(
    output_path: Path,
    samples: list[dict],
    split: str = "train",
    *,
    map_size: int = LMDB_MAP_SIZE,
    progress_callback=None,
) -> Path:
    """Write training samples to an LMDB file using the safe JSON+base64
    format.

    Each sample must be a dict with the keys:

        - ``image_path`` (str): path to an image file on disk. The raw
          file bytes are read and base64-encoded into the LMDB value.
        - ``text`` (str): the transcription/label.
        - ``source`` (str, optional): provenance string. Defaults to
          ``"unknown"`` if not present.

    Args:
        output_path: directory that will contain ``{split}.lmdb``.
        samples: list of sample dicts.
        split: split name (e.g., ``"train"``, ``"val"``).
        map_size: LMDB map size (default 1 TB).
        progress_callback: optional callable invoked once per sample
            with ``(idx, total)``. Replaces ``tqdm`` so this module
            does not depend on it.

    Returns:
        The path to the created ``{split}.lmdb`` directory.

    Raises:
        OSError: if any ``sample['image_path']`` cannot be read.
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    lmdb_file = output_path / f"{split}.lmdb"

    # Remove any prior LMDB at this path — matches the historical behavior.
    if lmdb_file.exists():
        shutil.rmtree(lmdb_file)

    env = lmdb.open(str(lmdb_file), map_size=map_size)

    try:
        with env.begin(write=True) as txn:
            for idx, sample in enumerate(samples):
                if progress_callback is not None:
                    progress_callback(idx, len(samples))

                # Read the raw image file bytes.
                with open(sample["image_path"], "rb") as f:
                    image_bytes = f.read()

                # JSON + base64 (non-executable format).
                key = f"{idx:08d}".encode()
                value = json.dumps({
                    "image": b64encode(image_bytes).decode("ascii"),
                    "text": sample["text"],
                    "source": sample.get("source", "unknown"),
                }).encode("utf-8")
                txn.put(key, value)

            # Store the sample count.
            txn.put(b"__len__", str(len(samples)).encode())
    finally:
        env.close()

    return lmdb_file


def read_sample_lmdb(input_path: Path, *, map_size: int = LMDB_MAP_SIZE) -> Iterator[dict]:
    """Read training samples from an LMDB file produced by
    :func:`write_sample_lmdb`.

    Yields one dict per sample with the schema:

        {
            "image":  bytes (raw image-file bytes, e.g., PNG/JPEG),
            "text":   str,
            "source": str,
        }

    Security: only JSON values are accepted. Any value whose first byte
    is not ``{`` (the JSON marker) raises ``ValueError``. There is NO
    pickle fallback — legacy pickle-based LMDBs must be regenerated via
    ``prepare_htr_dataset.py``.

    Args:
        input_path: path to the ``*.lmdb`` directory.
        map_size: LMDB map size (default 1 TB; only used to open the env).

    Yields:
        dict per sample (see schema above).

    Raises:
        ValueError: if a value is not JSON (e.g., legacy pickle LMDB) or
            the ``__len__`` key is missing.
        KeyError: if a per-index key is missing.
    """
    env = lmdb.open(str(input_path), readonly=True, map_size=map_size)
    try:
        with env.begin() as txn:
            len_raw = txn.get(b"__len__")
            if len_raw is None:
                raise ValueError(
                    f"LMDB at {input_path} is missing the '__len__' key — "
                    f"the dataset may be corrupt or empty."
                )
            n = int(len_raw)
            for i in range(n):
                key = f"{i:08d}".encode()
                raw = txn.get(key)
                if raw is None:
                    # Match the historical behavior: skip missing keys
                    # rather than raising (defensive against partial writes).
                    continue
                # Security: only JSON is accepted. If the value does
                # not start with '{', it is either corrupt or a legacy
                # pickle LMDB — reject explicitly. No pickle fallback.
                if not raw or raw[0:1] != b"{":
                    raise ValueError(
                        f"LMDB value at key {key!r} is not JSON "
                        f"(first byte={raw[0:1]!r}). Legacy pickle-based "
                        f"LMDBs are no longer supported; regenerate the "
                        f"dataset via prepare_htr_dataset.py."
                    )
                data = json.loads(raw.decode("utf-8"))
                # ``image`` was base64-encoded by the producer.
                if "image" in data and isinstance(data["image"], str):
                    data["image"] = b64decode(data["image"])
                yield data
    finally:
        env.close()
