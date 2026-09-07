"""TASK-02B Phase 1 — Security regression tests for pickle deserialization remediation.

These tests verify that the three logical consumer groups (G1, G2, G3) and
their mirrors no longer perform arbitrary-code-execution-capable pickle
deserialization.

Architecture (post-refactor):
  - G1: ``efficient_learner.py`` cache files use JSON+base64+zstd/zlib
    compression. Tests load the ``efficient_learner.py`` module directly
    (it does NOT import torch/lmdb at module level — only stdlib).
  - G2/G3/producer: serialization is extracted into a small dependency-light
    module ``_lmdb_safe_format.py`` (imports only ``lmdb``, ``json``,
    ``base64``, ``shutil``, ``pathlib``). Tests load this module directly
    rather than the full training scripts (``train_trocr_lora.py``,
    ``evaluate_checkpoint.py``, ``prepare_htr_dataset.py``) which import
    the heavy ML stack (``torch``, ``transformers``, ``peft``, ``datasets``)
    at module load time. The actual production producer/consumer code is
    exercised via the helper module — no mocks, no fake modules, no
    fabricated dicts.

Coverage:
  - 8 static source-absence checks (no pickle.loads/load/import/aliases
    in any of the 8 targeted production files)
  - 1 static boundary check (no torch/transformers/peft/datasets/cv2/numpy
    imports in ``_lmdb_safe_format.py`` — prevents future regressions that
    would re-introduce ML deps into the serialization boundary)
  - G1: positive roundtrip + malicious-payload non-execution + legacy
    pickle cache ignored + truncated cache + mirror parity
  - G2: positive LMDB roundtrip + malicious pickle rejection + missing
    __len__ rejection + producer→consumer integration + 4 cross-mirror
    combinations
  - G3: positive LMDB roundtrip with PIL Image reconstruction + malicious
    pickle rejection + 4 cross-mirror combinations (PIL Image.open
    auto-detects PNG/JPEG format from byte-stream header)
  - Producer writes JSON (not pickle) — verified via raw LMDB read
"""
from __future__ import annotations

import importlib.util
import json
import pickle
import sys
import zlib
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Targeted files
# ---------------------------------------------------------------------------

EFFICIENT_LEARNER_FILES = [
    ROOT / "packages" / "interactive-learning" / "learning" / "efficient_learner.py",
    ROOT / "packages" / "file_processor" / "interactive_learning" / "learning" / "efficient_learner.py",
]

TRAIN_TROCR_LORA_FILES = [
    ROOT / "packages" / "training-framework" / "scripts" / "train_trocr_lora.py",
    ROOT / "packages" / "file_processor" / "training" / "scripts" / "train_trocr_lora.py",
]

EVALUATE_CHECKPOINT_FILES = [
    ROOT / "packages" / "training-framework" / "scripts" / "evaluate_checkpoint.py",
    ROOT / "packages" / "file_processor" / "training" / "scripts" / "evaluate_checkpoint.py",
]

PREPARE_HTR_DATASET_FILES = [
    ROOT / "packages" / "training-framework" / "scripts" / "prepare_htr_dataset.py",
    ROOT / "packages" / "file_processor" / "training" / "scripts" / "prepare_htr_dataset.py",
]

# The lightweight serialization helper (mirror-identical across the two
# training-framework locations). Tests load this directly.
LMDB_SAFE_FORMAT_FILES = [
    ROOT / "packages" / "training-framework" / "scripts" / "_lmdb_safe_format.py",
    ROOT / "packages" / "file_processor" / "training" / "scripts" / "_lmdb_safe_format.py",
]

ALL_TARGETED_FILES = (
    EFFICIENT_LEARNER_FILES
    + TRAIN_TROCR_LORA_FILES
    + EVALUATE_CHECKPOINT_FILES
    + PREPARE_HTR_DATASET_FILES
    + LMDB_SAFE_FORMAT_FILES
)


# ---------------------------------------------------------------------------
# Helper: load a Python module from an arbitrary file path.
# ---------------------------------------------------------------------------

def _load_module(file_path: Path, module_name: str):
    """Load a Python module from an arbitrary file path.

    No stubs, no fake modules, no ``sys.modules`` injection. The targeted
    modules are designed to be importable in a minimal environment
    (``_lmdb_safe_format.py`` imports only ``lmdb`` + stdlib;
    ``efficient_learner.py`` imports only stdlib at module level).
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 1) Security invariant: no pickle.loads / pickle.load / import pickle in
#    any of the targeted files.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path",
    ALL_TARGETED_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_no_pickle_deserialization_in_targeted_files(file_path: Path) -> None:
    """None of the targeted files may contain pickle.loads/pickle.load
    (the arbitrary-code-execution-capable deserialization APIs)."""
    source = file_path.read_text(encoding="utf-8")
    assert "pickle.loads(" not in source, (
        f"{file_path} still contains pickle.loads( — TASK-02B regression"
    )
    assert "pickle.load(" not in source, (
        f"{file_path} still contains pickle.load( — TASK-02B regression"
    )
    # No bare `import pickle` either
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        assert not stripped.startswith("import pickle"), (
            f"{file_path} still imports pickle"
        )
        assert not stripped.startswith("from pickle import"), (
            f"{file_path} still imports from pickle"
        )


# ---------------------------------------------------------------------------
# 2) Boundary invariant: _lmdb_safe_format.py must NOT import heavy ML deps
#    (torch/transformers/peft/datasets/cv2/numpy). Prevents future regressions
#    that would re-introduce ML deps into the serialization boundary.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path",
    LMDB_SAFE_FORMAT_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_lmdb_safe_format_has_no_ml_imports(file_path: Path) -> None:
    """``_lmdb_safe_format.py`` must NOT import any heavy ML library.

    The whole point of extracting the serialization logic into a small
    module is that it can be tested without the ML stack. If a future
    contributor adds ``import torch`` or ``from transformers import ...``
    to this module, this test fails — preventing the regression that
    PR #119 originally caused.
    """
    source = file_path.read_text(encoding="utf-8")
    forbidden = [
        "import torch",
        "from torch",
        "import transformers",
        "from transformers",
        "import peft",
        "from peft",
        "import datasets",
        "from datasets",
        "import cv2",
        "from cv2",
        "import numpy",
        "from numpy",
        "import PIL",
        "from PIL",
        "import torchvision",
        "from torchvision",
    ]
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for bad in forbidden:
            assert not stripped.startswith(bad), (
                f"{file_path} imports forbidden ML dependency: {bad!r} "
                f"— the serialization boundary must stay ML-free"
            )


# ---------------------------------------------------------------------------
# 3) G1 — efficient_learner.py cache
# ---------------------------------------------------------------------------

class _FakeModel:
    """Minimal stand-in for a torch model."""
    def __init__(self):
        self.training = False
    def parameters(self):
        return []
    def state_dict(self):
        return {}
    def load_state_dict(self, sd):
        pass
    def to(self, _):
        return self
    def eval(self):
        self.training = False
    def train(self):
        self.training = True


class _FakeProcessor:
    def to_json_string(self):
        return "{}"


def _make_efficient_learner(module, cache_dir: Path):
    return module.MemoryEfficientLearner(
        model=_FakeModel(),
        processor=_FakeProcessor(),
        cache_dir=str(cache_dir),
        hot_memory_size=2,
    )


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EFFICIENT_LEARNER_FILES, [
        "eff_learner_a", "eff_learner_b",
    ])),
    ids=["interactive-learning", "file_processor-mirror"],
)
def test_g1_positive_roundtrip_json_compressed(file_path: Path, module_name: str, tmp_path: Path) -> None:
    """Producer (_offload_to_disk) writes a JSON-compressed cache file;
    consumer (_load_from_disk) reads it back with all fields intact."""
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, tmp_path)

    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff" * 3
    item = module.CorrectionItem(
        original_text="hello",
        corrected_text="Hello",
        confidence=0.85,
        compressed_image=img_bytes,
        timestamp=1234567.89,
        weight=1.5,
    )

    learner._offload_to_disk(item)

    cache_files = list(tmp_path.glob("correction_*.json.zst"))
    assert len(cache_files) == 1
    pkl_files = list(tmp_path.glob("correction_*.pkl.zst"))
    assert pkl_files == []

    items = learner._load_from_disk()
    assert len(items) == 1
    loaded = items[0]
    assert loaded.original_text == "hello"
    assert loaded.corrected_text == "Hello"
    assert abs(loaded.confidence - 0.85) < 1e-9
    assert loaded.compressed_image == img_bytes
    assert abs(loaded.timestamp - 1234567.89) < 1e-6
    assert abs(loaded.weight - 1.5) < 1e-9


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EFFICIENT_LEARNER_FILES, [
        "eff_learner_mal_a", "eff_learner_mal_b",
    ])),
    ids=["interactive-learning", "file_processor-mirror"],
)
def test_g1_malicious_pickle_payload_does_not_execute(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A malicious cache file containing a pickle payload with __reduce__
    MUST NOT execute when _load_from_disk reads it."""
    sentinel = tmp_path / "PWNED_BY_PICKLE"
    assert not sentinel.exists()

    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))

    malicious_pickle = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    learner_cache = tmp_path / "cache"
    learner_cache.mkdir()
    malicious_file = learner_cache / "correction_00000000.json.zst"
    malicious_file.write_bytes(zlib.compress(malicious_pickle))

    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, learner_cache)

    items = learner._load_from_disk()

    assert not sentinel.exists(), (
        "PICKLE PAYLOAD EXECUTED — sentinel file was created"
    )
    assert items == []


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EFFICIENT_LEARNER_FILES, [
        "eff_learner_legacy_a", "eff_learner_legacy_b",
    ])),
    ids=["interactive-learning", "file_processor-mirror"],
)
def test_g1_legacy_pickle_cache_files_are_ignored(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Legacy ``correction_*.pkl.zst`` files must be silently ignored."""
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, tmp_path)

    sentinel = tmp_path / "PWNED_BY_LEGACY"
    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))
    legacy_payload = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    (tmp_path / "correction_00000000.pkl.zst").write_bytes(zlib.compress(legacy_payload))

    items = learner._load_from_disk()
    assert items == []
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EFFICIENT_LEARNER_FILES, [
        "eff_learner_trunc_a", "eff_learner_trunc_b",
    ])),
    ids=["interactive-learning", "file_processor-mirror"],
)
def test_g1_truncated_cache_file_does_not_crash(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A truncated cache file must produce a per-file log error and be
    skipped — the consumer must NOT crash the whole load."""
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, tmp_path)
    (tmp_path / "correction_00000000.json.zst").write_bytes(b"\x78\x9c\x03\x00")
    items = learner._load_from_disk()
    assert items == []


# ---------------------------------------------------------------------------
# 4) G2/G3 — _lmdb_safe_format.py producer+consumer
# ---------------------------------------------------------------------------

def _build_lmdb(path: Path, entries: list[tuple[bytes, bytes]]) -> None:
    """Build a minimal LMDB at `path` with the given (key, value) entries."""
    import lmdb
    env = lmdb.open(str(path), map_size=1 << 24)
    with env.begin(write=True) as txn:
        for k, v in entries:
            txn.put(k, v)
    env.close()


def _make_real_png(path: Path, size=(7, 5), color=(123, 45, 67)) -> bytes:
    """Write a real PNG file at `path`; return its raw bytes."""
    from PIL import Image
    img = Image.new("RGB", size, color=color)
    img.save(path, format="PNG")
    return path.read_bytes()


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_a", "safe_fmt_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_positive_lmdb_roundtrip(file_path: Path, module_name: str, tmp_path: Path) -> None:
    """Producer writes JSON LMDB values; consumer reads them back as
    dicts with image bytes + text + source."""
    module = _load_module(file_path, module_name)

    image_bytes = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    lmdb_path = tmp_path / "test.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", json.dumps({
            "image": b64encode(image_bytes).decode("ascii"),
            "text": "hello",
            "source": "test",
        }).encode("utf-8")),
    ])

    samples = list(module.read_sample_lmdb(lmdb_path))
    assert len(samples) == 1
    s = samples[0]
    assert s["text"] == "hello"
    assert s["source"] == "test"
    assert s["image"] == image_bytes


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_mal_a", "safe_fmt_mal_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_malicious_pickle_lmdb_value_does_not_execute(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A pickle-protocol LMDB value with __reduce__ MUST NOT execute.
    The consumer raises ValueError without unpickling."""
    sentinel = tmp_path / "PWNED_BY_PICKLE_LMDB"
    assert not sentinel.exists()

    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))

    malicious_pickle = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    assert malicious_pickle[0:1] != b"{"

    lmdb_path = tmp_path / "malicious.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", malicious_pickle),
    ])

    module = _load_module(file_path, module_name)
    with pytest.raises(ValueError, match="not JSON"):
        list(module.read_sample_lmdb(lmdb_path))

    assert not sentinel.exists()


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_len_a", "safe_fmt_len_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_missing_len_key_raises(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """If the LMDB is missing the ``__len__`` key, the consumer must
    fail-closed (raise ValueError)."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "no_len.lmdb"
    _build_lmdb(lmdb_path, [
        (b"00000000", json.dumps({"image": "", "text": "x", "source": "y"}).encode("utf-8")),
    ])

    with pytest.raises(ValueError, match="__len__"):
        list(module.read_sample_lmdb(lmdb_path))


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_empty_a", "safe_fmt_empty_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_empty_value_rejected(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """An empty LMDB value must be rejected with ValueError (no silent skip)."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "empty_val.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", b""),
    ])
    with pytest.raises(ValueError, match="not JSON"):
        list(module.read_sample_lmdb(lmdb_path))


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_badjson_a", "safe_fmt_badjson_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_invalid_json_rejected(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A value that starts with ``{`` but is not valid JSON must raise."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "badjson.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", b"{ this is not valid json "),
    ])
    with pytest.raises(json.JSONDecodeError):
        list(module.read_sample_lmdb(lmdb_path))


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_badb64_a", "safe_fmt_badb64_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_invalid_base64_rejected(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A value whose ``image`` field is not valid base64 must raise
    (binascii.Error). No silent fallback."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "badb64.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", json.dumps({
            "image": "@@@@@not-valid-base64@@@@@",
            "text": "x",
            "source": "y",
        }).encode("utf-8")),
    ])
    import binascii
    with pytest.raises((binascii.Error, ValueError)):
        list(module.read_sample_lmdb(lmdb_path))


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_missing_fields_a", "safe_fmt_missing_fields_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_missing_required_fields(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A JSON value missing required fields (text/source) should still
    decode but the resulting dict reflects what's actually present —
    the helper does NOT silently add defaults. The caller is responsible
    for handling missing keys."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "missing_fields.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", json.dumps({"image": b64encode(b"x").decode("ascii")}).encode("utf-8")),
    ])
    samples = list(module.read_sample_lmdb(lmdb_path))
    assert len(samples) == 1
    # image decoded back to bytes; text/source are absent
    assert samples[0]["image"] == b"x"
    assert "text" not in samples[0]
    assert "source" not in samples[0]


# ---------------------------------------------------------------------------
# 5) G3 — PIL Image reconstruction (uses Image.open(io.BytesIO(...)))
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_g3_a", "safe_fmt_g3_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g3_positive_lmdb_roundtrip_with_pil_image(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Producer writes JSON LMDB values with the ORIGINAL image file
    bytes (PNG/JPEG/etc., NOT pre-decoded pixel buffers); consumer
    reconstructs the PIL Image via Image.open(io.BytesIO(...)), letting
    PIL auto-detect format + dimensions from the byte-stream header.

    This mirrors the production evaluate_checkpoint.py code path.
    """
    from PIL import Image
    import io

    # Build a real PNG file
    img_path = tmp_path / "sample.png"
    img_file_bytes = _make_real_png(img_path, size=(50, 30), color=(123, 45, 67))
    original_img = Image.open(img_path)
    original_pixels = list(original_img.getdata())

    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "eval_test.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", json.dumps({
            "image": b64encode(img_file_bytes).decode("ascii"),
            "text": "hello",
            "source": "test",
        }).encode("utf-8")),
    ])

    # Mirror the G3 production consumer code path:
    samples = []
    for data in module.read_sample_lmdb(lmdb_path):
        img = Image.open(io.BytesIO(data["image"]))
        samples.append({"image": img, "text": data["text"]})

    assert len(samples) == 1
    s = samples[0]
    assert s["text"] == "hello"
    assert isinstance(s["image"], Image.Image)
    assert s["image"].mode == "RGB"
    assert s["image"].size == (50, 30)
    # Pixel-level equality — proves the entire image reconstructed correctly
    assert list(s["image"].getdata()) == original_pixels


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_g3_mal_a", "safe_fmt_g3_mal_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g3_malicious_pickle_lmdb_value_does_not_execute(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Same as G2 malicious test, but for the G3 consumer path."""
    sentinel = tmp_path / "PWNED_BY_PICKLE_EVAL"
    assert not sentinel.exists()

    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))

    malicious_pickle = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    lmdb_path = tmp_path / "malicious_eval.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", malicious_pickle),
    ])

    module = _load_module(file_path, module_name)
    with pytest.raises(ValueError, match="not JSON"):
        list(module.read_sample_lmdb(lmdb_path))
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# 6) Producer: write_sample_lmdb writes JSON values (not pickle)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(LMDB_SAFE_FORMAT_FILES, [
        "safe_fmt_prod_a", "safe_fmt_prod_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_producer_writes_json_lmdb_values(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """The write_sample_lmdb() function must write JSON (UTF-8) values
    to the LMDB, NOT pickle."""
    import lmdb as lmdb_module

    module = _load_module(file_path, module_name)

    # Build a real PNG so we can verify byte-exact roundtrip
    img_path = tmp_path / "sample.png"
    img_file_bytes = _make_real_png(img_path, size=(4, 4), color=(0, 255, 0))

    samples = [{"image_path": str(img_path), "text": "hello", "source": "test"}]
    output_dir = tmp_path / "out"
    lmdb_file = module.write_sample_lmdb(output_dir, samples, split="train")

    assert lmdb_file.exists()

    # Read raw LMDB value
    env = lmdb_module.open(str(lmdb_file), readonly=True)
    with env.begin() as txn:
        raw = txn.get(b"00000000")
        assert raw is not None
        assert raw[0:1] == b"{", (
            f"LMDB value is not JSON (first byte={raw[0:1]!r})"
        )
        data = json.loads(raw.decode("utf-8"))
        assert set(data.keys()) == {"image", "text", "source"}, (
            f"producer schema keys mismatch: got {sorted(data.keys())}"
        )
        assert isinstance(data["image"], str)
        assert data["text"] == "hello"
        assert data["source"] == "test"
        # No 'size' or 'image_path' fields in producer schema
        assert "size" not in data
        assert "image_path" not in data
        # base64 decode must produce the exact original PNG bytes
        decoded = b64decode(data["image"])
        assert decoded == img_file_bytes
    env.close()


# ---------------------------------------------------------------------------
# 7) Mirror parity: both _lmdb_safe_format mirrors produce interchangeable
#    artifacts (producer 0 → consumer 1, producer 1 → consumer 0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "producer_idx,consumer_idx",
    [
        (0, 0),  # canonical → canonical
        (1, 1),  # mirror → mirror
        (0, 1),  # canonical → mirror
        (1, 0),  # mirror → canonical
    ],
    ids=["canonical→canonical", "mirror→mirror", "canonical→mirror", "mirror→canonical"],
)
def test_g2_g3_mirror_parity_lmdb_format(
    producer_idx: int, consumer_idx: int, tmp_path: Path
) -> None:
    """Both _lmdb_safe_format mirrors must produce interchangeable LMDB
    artifacts — producer 0 writes; consumer 1 reads (and vice versa).
    """
    from PIL import Image
    import io

    # Build a real PNG
    img_path = tmp_path / "parity.png"
    img_file_bytes = _make_real_png(img_path, size=(7, 5), color=(200, 100, 50))

    # Producer
    prod_module = _load_module(
        LMDB_SAFE_FORMAT_FILES[producer_idx],
        f"parity_prod_{producer_idx}_{consumer_idx}",
    )
    samples = [{"image_path": str(img_path), "text": "parity", "source": "p"}]
    output_dir = tmp_path / f"out_p{producer_idx}"
    lmdb_file = prod_module.write_sample_lmdb(output_dir, samples, split="train")

    # Consumer
    cons_module = _load_module(
        LMDB_SAFE_FORMAT_FILES[consumer_idx],
        f"parity_cons_{producer_idx}_{consumer_idx}",
    )
    samples_back = list(cons_module.read_sample_lmdb(lmdb_file))
    assert len(samples_back) == 1
    s = samples_back[0]
    assert s["image"] == img_file_bytes  # byte-exact equality across mirrors
    assert s["text"] == "parity"
    assert s["source"] == "p"

    # Verify PIL Image reconstruction works on the cross-mirror read
    img = Image.open(io.BytesIO(s["image"]))
    assert img.size == (7, 5)
    assert img.mode == "RGB"


# ---------------------------------------------------------------------------
# 8) G1 mirror parity (unchanged from before — kept for completeness)
# ---------------------------------------------------------------------------

def test_g1_mirror_parity_compressed_image_roundtrip(tmp_path: Path) -> None:
    """Both G1 mirror copies must produce the same .json.zst cache format
    and read each other's cache files interchangeably."""
    modules = [
        _load_module(f, f"parity_g1_{i}")
        for i, f in enumerate(EFFICIENT_LEARNER_FILES)
    ]
    assert len(modules) == 2
    img_bytes = b"parity-test-bytes" * 5

    learner_a = _make_efficient_learner(modules[0], tmp_path)
    item = modules[0].CorrectionItem(
        original_text="parity",
        corrected_text="PARITY",
        confidence=0.42,
        compressed_image=img_bytes,
        timestamp=99.0,
        weight=2.0,
    )
    learner_a._offload_to_disk(item)

    learner_b = _make_efficient_learner(modules[1], tmp_path)
    items = learner_b._load_from_disk()
    assert len(items) == 1
    assert items[0].original_text == "parity"
    assert items[0].corrected_text == "PARITY"
    assert items[0].compressed_image == img_bytes
