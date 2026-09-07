"""TASK-02B Phase 1 — Security regression tests for pickle deserialization remediation.

These tests verify that the three logical consumer groups (G1, G2, G3) and
their mirrors no longer perform arbitrary-code-execution-capable pickle
deserialization. The new format is JSON (UTF-8) — with zstd/zlib compression
for G1 cache files, and raw LMDB values for G2/G3.

Coverage:

G1 (efficient_learner.py — 2 mirror copies):
  - Positive: producer writes JSON-compressed cache; consumer reads it back
    with the expected CorrectionItem semantics
  - Malicious payload: a pickle-protocol-2 payload with a __reduce__ that
    would execute `subprocess.run([...])` if unpickled — must NOT execute
    when the consumer reads the cache file. Must be treated as invalid data.
  - Contract: malformed/truncated cache file behavior; legacy pickle cache
    files are ignored (not loaded)
  - Mirror parity: both copies implement the same safe behavior

G2 (train_trocr_lora.py + prepare_htr_dataset.py — 2 mirror copies):
  - Positive: producer writes JSON LMDB values; consumer reads them back
  - Malicious payload: pickle-protocol LMDB value with __reduce__ — must
    NOT execute; must be rejected with the explicit "not JSON" ValueError
  - Contract: missing '__len__' key, corrupt LMDB
  - Mirror parity: both copies

G3 (evaluate_checkpoint.py + prepare_htr_dataset.py — 2 mirror copies):
  - Same as G2 (uses the same producer)

Security invariant: ``pickle.loads`` / ``pickle.load`` MUST be absent from
the source of all 6 consumer files (parametrized source-absence assertion).
"""
from __future__ import annotations

import importlib.util
import json
import pickle
import struct
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

ALL_TARGETED_FILES = (
    EFFICIENT_LEARNER_FILES
    + TRAIN_TROCR_LORA_FILES
    + EVALUATE_CHECKPOINT_FILES
    + PREPARE_HTR_DATASET_FILES
)


# ---------------------------------------------------------------------------
# Helper: load a Python module from an arbitrary file path (the targeted
# scripts are not in a single importable package).
# ---------------------------------------------------------------------------

def _load_module(file_path: Path, module_name: str):
    """Load a Python module from an arbitrary file path (the targeted
    scripts are not in a single importable package).

    Some targeted scripts (train_trocr_lora.py, evaluate_checkpoint.py)
    import heavy ML libraries at module level (`peft`, `transformers`,
    `datasets.load_metric`). The installed `datasets` version no longer
    exports `load_metric`, which is a PRE-EXISTING bug unrelated to
    TASK-02B. We stub these imports so we can test the *_load_data /
    *_load_test_data methods in isolation.
    """
    # Pre-register stub modules so that `from X import Y` succeeds at
    # module-load time. The stubs only need to be importable; they are
    # never actually used by the deserialization code paths under test.
    import types
    for stub_name in (
        "peft", "transformers", "datasets",
        "torchvision", "evaluate",
    ):
        if stub_name not in sys.modules:
            sys.modules[stub_name] = types.ModuleType(stub_name)
    # datasets.load_metric was removed in datasets>=3.0 — pre-existing bug
    if not hasattr(sys.modules["datasets"], "load_metric"):
        sys.modules["datasets"].load_metric = lambda _name: mock.MagicMock()
    # transformers specific imports used by the scripts
    if not hasattr(sys.modules["transformers"], "TrOCRProcessor"):
        sys.modules["transformers"].TrOCRProcessor = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "VisionEncoderDecoderModel"):
        sys.modules["transformers"].VisionEncoderDecoderModel = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "default_data_collator"):
        sys.modules["transformers"].default_data_collator = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "Seq2SeqTrainer"):
        sys.modules["transformers"].Seq2SeqTrainer = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "Seq2SeqTrainingArguments"):
        sys.modules["transformers"].Seq2SeqTrainingArguments = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "TrCTCTokenizer"):
        sys.modules["transformers"].TrCTCTokenizer = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "AutoTokenizer"):
        sys.modules["transformers"].AutoTokenizer = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "AutoFeatureExtractor"):
        sys.modules["transformers"].AutoFeatureExtractor = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "AutoProcessor"):
        sys.modules["transformers"].AutoProcessor = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "EarlyStoppingCallback"):
        sys.modules["transformers"].EarlyStoppingCallback = mock.MagicMock()
    if not hasattr(sys.modules["transformers"], "set_seed"):
        sys.modules["transformers"].set_seed = lambda _seed: None
    if not hasattr(sys.modules["transformers"], "pipeline"):
        sys.modules["transformers"].pipeline = mock.MagicMock()
    # peft
    if not hasattr(sys.modules["peft"], "PeftModel"):
        sys.modules["peft"].PeftModel = mock.MagicMock()
    if not hasattr(sys.modules["peft"], "LoraConfig"):
        sys.modules["peft"].LoraConfig = mock.MagicMock()
    if not hasattr(sys.modules["peft"], "get_peft_model"):
        sys.modules["peft"].get_peft_model = mock.MagicMock()
    if not hasattr(sys.modules["peft"], "TaskType"):
        sys.modules["peft"].TaskType = mock.MagicMock()

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 1) Security invariant: no pickle.loads / pickle.load / import pickle in
#    any of the 8 targeted files.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path",
    ALL_TARGETED_FILES,
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_no_pickle_deserialization_in_targeted_files(file_path: Path) -> None:
    """None of the 8 targeted files may contain pickle.loads/pickle.load
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
# 2) G1 — efficient_learner.py: positive round-trip + malicious payload +
#    contract + mirror parity
# ---------------------------------------------------------------------------

class _FakeModel:
    """Minimal stand-in for a torch model so we can construct
    MemoryEfficientLearner without heavy deps."""
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
    """Minimal stand-in for a TrOCR processor."""
    def to_json_string(self):
        return "{}"


def _make_efficient_learner(module, cache_dir: Path):
    """Construct a MemoryEfficientLearner with minimal stubs."""
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
    consumer (_load_from_disk) reads it back and reconstructs the
    CorrectionItem with all original fields intact."""
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, tmp_path)

    # Compressed image bytes — arbitrary binary content
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff" * 3
    item = module.CorrectionItem(
        original_text="hello",
        corrected_text="Hello",
        confidence=0.85,
        compressed_image=img_bytes,
        timestamp=1234567.89,
        weight=1.5,
    )

    # Producer writes the cache file
    learner._offload_to_disk(item)

    # The cache file MUST use the new extension (.json.zst), not .pkl.zst
    cache_files = list(tmp_path.glob("correction_*.json.zst"))
    assert len(cache_files) == 1, f"expected 1 .json.zst cache file, got {cache_files}"
    pkl_files = list(tmp_path.glob("correction_*.pkl.zst"))
    assert pkl_files == [], "legacy pickle cache extension should not be used"

    # Consumer reads it back
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
    file_path: Path, module_name: str, tmp_path: Path, monkeypatch
) -> None:
    """A malicious cache file containing a pickle-protocol payload with a
    __reduce__ that would execute `subprocess.run([...])` MUST NOT execute
    when _load_from_disk reads it. The new consumer uses json.loads, which
    cannot execute arbitrary code.

    This test plants a malicious pickle payload disguised with the new
    .json.zst extension. The consumer must reject it (JSON parse error)
    WITHOUT executing the payload.
    """
    # Sentinel marker that the payload WOULD write if executed. We'll
    # check after the test that this marker was NOT created.
    sentinel = tmp_path / "PWNED_BY_PICKLE"
    assert not sentinel.exists()

    # Build a pickle payload whose __reduce__ would touch the sentinel.
    # We use a simple class with __reduce__ — if pickle.loads runs, the
    # class's __init__ or callable reconstructor runs.
    class _Pwned:
        def __reduce__(self):
            # Write a sentinel file to prove execution occurred.
            # NEVER run a real destructive command — just touch a marker.
            import os
            return (os.makedirs, (str(sentinel),))

    malicious_pickle = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)

    # Plant it as a cache file with the NEW extension to verify the
    # consumer doesn't blindly unpickle anything named *.json.zst.
    learner_cache = tmp_path / "cache"
    learner_cache.mkdir()
    malicious_file = learner_cache / "correction_00000000.json.zst"

    # Compress the pickle payload with zlib (matches consumer's fallback
    # decompression path when zstandard is not installed).
    compressed = zlib.compress(malicious_pickle)
    malicious_file.write_bytes(compressed)

    # Load the module and the cache. The consumer MUST NOT execute the
    # pickle payload. It will try json.loads(zlib.decompress(...)) which
    # will raise a JSONDecodeError (caught by the consumer's try/except).
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, learner_cache)

    # _load_from_disk swallows per-file exceptions and returns whatever
    # it successfully loaded. The malicious file should produce 0 items.
    items = learner._load_from_disk()

    # The malicious payload MUST NOT have executed.
    assert not sentinel.exists(), (
        "PICKLE PAYLOAD EXECUTED — sentinel file was created, "
        "meaning the consumer performed arbitrary-code-execution"
    )
    # The consumer returned 0 valid items (JSON parse failed).
    assert items == [], (
        f"expected empty list (JSON parse should have failed), got {items}"
    )


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EFFICIENT_LEARNER_FILES, [
        "eff_learner_contract_a", "eff_learner_contract_b",
    ])),
    ids=["interactive-learning", "file_processor-mirror"],
)
def test_g1_legacy_pickle_cache_files_are_ignored(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Legacy `correction_*.pkl.zst` files must be silently ignored —
    NOT loaded via pickle. The consumer globs for `*.json.zst` only."""
    module = _load_module(file_path, module_name)
    learner = _make_efficient_learner(module, tmp_path)

    # Write a legacy pickle cache file (would be unsafe if loaded via pickle)
    sentinel = tmp_path / "PWNED_BY_LEGACY"
    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))
    legacy_payload = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    legacy_file = tmp_path / "correction_00000000.pkl.zst"
    legacy_file.write_bytes(zlib.compress(legacy_payload))

    # Consumer should NOT load the legacy file
    items = learner._load_from_disk()
    assert items == [], "consumer should not load legacy .pkl.zst files"
    assert not sentinel.exists(), "legacy pickle payload executed"


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
    # Write a truncated JSON cache file (only 4 bytes of zlib-compressed
    # data — too short to decompress)
    (tmp_path / "correction_00000000.json.zst").write_bytes(b"\x78\x9c\x03\x00")
    items = learner._load_from_disk()
    assert items == [], "truncated cache file should yield 0 items"


# ---------------------------------------------------------------------------
# 3) G2 — train_trocr_lora.py LMDB consumer + prepare_htr_dataset.py producer
# ---------------------------------------------------------------------------

def _build_lmdb(path: Path, entries: list[tuple[bytes, bytes]]) -> None:
    """Build a minimal LMDB at `path` with the given (key, value) entries."""
    import lmdb
    env = lmdb.open(str(path), map_size=1 << 24)
    with env.begin(write=True) as txn:
        for k, v in entries:
            txn.put(k, v)
    env.close()


def _safe_lmdb_value(payload: dict) -> bytes:
    """Encode a dict as the safe JSON LMDB value (matching the new producer)."""
    return json.dumps(payload).encode("utf-8")


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(TRAIN_TROCR_LORA_FILES, [
        "trocr_lora_a", "trocr_lora_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_positive_lmdb_roundtrip(file_path: Path, module_name: str, tmp_path: Path) -> None:
    """Producer writes JSON LMDB values; consumer reads them back as
    dicts with the expected fields (image as bytes, text as str,
    source as str)."""
    module = _load_module(file_path, module_name)
    image_bytes = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    lmdb_path = tmp_path / "test.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", _safe_lmdb_value({
            "image": b64encode(image_bytes).decode("ascii"),
            "text": "hello",
            "source": "test",
        })),
    ])

    # Find the dataset class. The train_trocr_lora.py file defines a
    # class with a _load_data method. We instantiate it directly.
    # The class is named differently across mirrors but always has
    # _load_data. We use the simplest path: directly call _load_data.
    DatasetCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "_load_data"):
            DatasetCls = obj
            break
    assert DatasetCls is not None, "could not find dataset class with _load_data"

    # Construct without invoking __init__ (which requires processor etc.)
    instance = DatasetCls.__new__(DatasetCls)
    samples = instance._load_data(lmdb_path)
    assert len(samples) == 1
    s = samples[0]
    assert s["text"] == "hello"
    assert s["source"] == "test"
    # image was base64-decoded back to bytes
    assert s["image"] == image_bytes


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(TRAIN_TROCR_LORA_FILES, [
        "trocr_lora_mal_a", "trocr_lora_mal_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_malicious_pickle_lmdb_value_does_not_execute(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """A pickle-protocol LMDB value with __reduce__ MUST NOT execute
    when the consumer reads it. The new consumer probes the first byte;
    if it's not `{` (JSON), it raises ValueError without unpickling."""
    sentinel = tmp_path / "PWNED_BY_PICKLE_LMDB"
    assert not sentinel.exists()

    class _Pwned:
        def __reduce__(self):
            import os
            return (os.makedirs, (str(sentinel),))

    malicious_pickle = pickle.dumps(_Pwned(), protocol=pickle.HIGHEST_PROTOCOL)
    # Pickle protocol 2 starts with 0x80 — definitely not '{' (0x7b)
    assert malicious_pickle[0:1] != b"{", "test setup wrong — pickle starts with '{'?"

    lmdb_path = tmp_path / "malicious.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", malicious_pickle),
    ])

    module = _load_module(file_path, module_name)
    DatasetCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "_load_data"):
            DatasetCls = obj
            break
    instance = DatasetCls.__new__(DatasetCls)

    # The consumer MUST raise ValueError (not execute the payload)
    with pytest.raises(ValueError, match="not JSON"):
        instance._load_data(lmdb_path)

    # And the malicious payload MUST NOT have executed
    assert not sentinel.exists(), (
        "PICKLE PAYLOAD EXECUTED — sentinel file was created"
    )


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(TRAIN_TROCR_LORA_FILES, [
        "trocr_lora_len_a", "trocr_lora_len_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g2_missing_len_key_raises(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """If the LMDB is missing the `__len__` key, the consumer must
    fail closed (raise) rather than silently returning empty."""
    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "no_len.lmdb"
    _build_lmdb(lmdb_path, [
        (b"00000000", _safe_lmdb_value({"image": "", "text": "x", "source": "y"})),
    ])

    DatasetCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "_load_data"):
            DatasetCls = obj
            break
    instance = DatasetCls.__new__(DatasetCls)

    # int(None) raises TypeError — consumer must propagate
    with pytest.raises((TypeError, ValueError)):
        instance._load_data(lmdb_path)


# ---------------------------------------------------------------------------
# 4) G3 — evaluate_checkpoint.py LMDB consumer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EVALUATE_CHECKPOINT_FILES, [
        "eval_ckpt_a", "eval_ckpt_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g3_positive_lmdb_roundtrip_with_image(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Producer writes JSON LMDB values with the ORIGINAL image file bytes
    (PNG/JPEG/etc., NOT pre-decoded pixel buffers); consumer reconstructs
    the PIL Image via Image.open(io.BytesIO(...)), letting PIL auto-detect
    the format and dimensions from the byte-stream header.

    This test reflects the ACTUAL producer contract: the producer reads
    image_path and writes the raw file bytes (base64-encoded for JSON
    storage). No ``size`` or ``image_path`` field is serialized — the
    consumer relies on PIL's format auto-detection, exactly as
    Image.open(path) would have done."""
    # Build a small real RGB image and save as PNG (file bytes, not raw pixel buffer)
    from PIL import Image
    img = Image.new("RGB", (50, 30), color=(123, 45, 67))
    img_file = tmp_path / "sample.png"
    img.save(img_file, format="PNG")
    img_file_bytes = img_file.read_bytes()  # PNG file bytes (with header)

    module = _load_module(file_path, module_name)
    lmdb_path = tmp_path / "eval_test.lmdb"
    _build_lmdb(lmdb_path, [
        (b"__len__", b"1"),
        (b"00000000", _safe_lmdb_value({
            "image": b64encode(img_file_bytes).decode("ascii"),
            "text": "hello",
            "source": "test",
            # NOTE: NO 'size' field — the real producer never writes it
            # NOTE: NO 'image_path' field — the real producer never writes it
        })),
    ])

    # Find the evaluator class with _load_test_data
    EvaluatorCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "_load_test_data"):
            EvaluatorCls = obj
            break
    assert EvaluatorCls is not None, "could not find evaluator class with _load_test_data"
    instance = EvaluatorCls.__new__(EvaluatorCls)

    samples = instance._load_test_data(lmdb_path)
    assert len(samples) == 1
    s = samples[0]
    assert s["text"] == "hello"
    # Image was reconstructed via Image.open(io.BytesIO(...))
    assert isinstance(s["image"], Image.Image)
    assert s["image"].mode == "RGB"
    assert s["image"].size == (50, 30), (
        f"expected (50, 30), got {s['image'].size}"
    )
    # Pixel-level equivalence
    assert list(s["image"].getdata()) == list(img.getdata())


@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(EVALUATE_CHECKPOINT_FILES, [
        "eval_ckpt_mal_a", "eval_ckpt_mal_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_g3_malicious_pickle_lmdb_value_does_not_execute(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """Same as G2 malicious test, but for the evaluate_checkpoint consumer."""
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
    EvaluatorCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "_load_test_data"):
            EvaluatorCls = obj
            break
    instance = EvaluatorCls.__new__(EvaluatorCls)

    with pytest.raises(ValueError, match="not JSON"):
        instance._load_test_data(lmdb_path)
    assert not sentinel.exists(), "PICKLE PAYLOAD EXECUTED — sentinel was created"


# ---------------------------------------------------------------------------
# 5) Producer-side: prepare_htr_dataset.py LMDBFormatter writes JSON values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "file_path,module_name",
    list(zip(PREPARE_HTR_DATASET_FILES, [
        "prep_htr_a", "prep_htr_b",
    ])),
    ids=["training-framework", "file_processor-mirror"],
)
def test_producer_writes_json_lmdb_values(
    file_path: Path, module_name: str, tmp_path: Path
) -> None:
    """The LMDBFormatter.format() method must write JSON (UTF-8) values
    to the LMDB, NOT pickle. We verify by reading the raw LMDB value
    and asserting it starts with '{' and parses as JSON."""
    import lmdb

    module = _load_module(file_path, module_name)

    # Find LMDBFormatter
    FormatterCls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and "LMDB" in name and hasattr(obj, "format"):
            FormatterCls = obj
            break
    assert FormatterCls is not None, "could not find LMDB formatter class"

    # Build a tiny "image" file
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"fake-image-bytes")

    # Build samples
    samples = [{"image_path": str(img_file), "text": "hello", "source": "test"}]
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    formatter = FormatterCls(output_dir)
    formatter.format(samples, split="train")

    lmdb_path = output_dir / "train.lmdb"
    assert lmdb_path.exists(), "LMDB file was not created"

    # Read raw value from LMDB
    env = lmdb.open(str(lmdb_path), readonly=True)
    with env.begin() as txn:
        raw = txn.get(b"00000000")
        assert raw is not None, "no value at key 00000000"
        # Must be JSON — first byte is '{'
        assert raw[0:1] == b"{", (
            f"LMDB value is not JSON (first byte={raw[0:1]!r}); "
            f"producer may still be using pickle"
        )
        # Must parse as JSON
        data = json.loads(raw.decode("utf-8"))
        assert data["text"] == "hello"
        assert data["source"] == "test"
        assert "image" in data
        # image is base64-encoded string
        assert isinstance(data["image"], str)
        decoded = b64decode(data["image"])
        assert decoded == b"fake-image-bytes"
    env.close()


# ---------------------------------------------------------------------------
# 6) Mirror parity: both copies of each group produce the same safe behavior
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

    # Producer: module 0 writes a cache file
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

    # Consumer: module 1 reads it back
    learner_b = _make_efficient_learner(modules[1], tmp_path)
    items = learner_b._load_from_disk()
    assert len(items) == 1
    assert items[0].original_text == "parity"
    assert items[0].corrected_text == "PARITY"
    assert items[0].compressed_image == img_bytes


def test_g2_mirror_parity_lmdb_format(tmp_path: Path) -> None:
    """Both G2/G3 producer mirrors must produce the same JSON LMDB
    format — readable by both consumer mirrors."""
    # Producer mirror 0 writes
    prod0 = _load_module(PREPARE_HTR_DATASET_FILES[0], "parity_prod_0")
    img_file = tmp_path / "img.png"
    img_file.write_bytes(b"parity-lmdb-bytes")
    samples = [{"image_path": str(img_file), "text": "abc", "source": "s"}]
    out_dir = tmp_path / "out0"
    out_dir.mkdir()
    # Find LMDBFormatter
    Fmt0 = None
    for name in dir(prod0):
        obj = getattr(prod0, name)
        if isinstance(obj, type) and "LMDB" in name and hasattr(obj, "format"):
            Fmt0 = obj; break
    Fmt0(out_dir).format(samples, split="train")

    # Consumer mirror 1 reads
    cons1 = _load_module(TRAIN_TROCR_LORA_FILES[1], "parity_cons_1")
    DsCls = None
    for name in dir(cons1):
        obj = getattr(cons1, name)
        if isinstance(obj, type) and hasattr(obj, "_load_data"):
            DsCls = obj; break
    inst = DsCls.__new__(DsCls)
    samples_back = inst._load_data(out_dir / "train.lmdb")
    assert len(samples_back) == 1
    assert samples_back[0]["text"] == "abc"
    assert samples_back[0]["image"] == b"parity-lmdb-bytes"
