"""AHW-02E / AHW-02G — Security regression tests (test-first).

E1 — every ``torch.load(...)`` in the three PROVEN unsafe sites must pass
     ``weights_only=True`` (AST-level check: no source-grep fragility).
E2 — ``.gitignore`` must carry model-weight patterns (latent-risk guard).
E3 — the canonical cloud path must be ``cloud disabled by default`` and
     ``explicitly opt-in``; no automatic cloud fallback without opt-in.
"""

import ast
from pathlib import Path

import pytest

MONOREPO_ROOT = Path(__file__).resolve().parent.parent

UNSAFE_LOAD_SITES = [
    # (file, description) — the three sites PROVEN by AHW-01 §M-1 [LIVE]
    MONOREPO_ROOT / "packages/interactive-learning/learning/online_learner.py",
    MONOREPO_ROOT / "packages/file_processor/interactive_learning/learning/online_learner.py",
    MONOREPO_ROOT / "apps/handwriting-demo/training/continual_trainer.py",
]

SAFE_REFERENCE_SITE = MONOREPO_ROOT / "packages/vision/htr/line_segmenter.py"


def _torch_load_calls_missing_weights_only(path: Path):
    """Return line numbers of torch.load(...) calls lacking weights_only=True."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_torch_load = (
            isinstance(func, ast.Attribute)
            and func.attr == "load"
            and isinstance(func.value, ast.Name)
            and func.value.id == "torch"
        )
        if not is_torch_load:
            continue
        has_weights_only_true = any(
            kw.arg == "weights_only"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
        if not has_weights_only_true:
            offenders.append(node.lineno)
    return offenders


# ---------------------------------------------------------------------------
# E1 — unsafe deserialization regression
# ---------------------------------------------------------------------------
class TestTorchLoadHardening:
    @pytest.mark.parametrize("site", UNSAFE_LOAD_SITES, ids=lambda p: str(p.relative_to(MONOREPO_ROOT)))
    def test_torch_load_uses_weights_only_true(self, site):
        assert site.exists(), f"site disappeared: {site}"
        offenders = _torch_load_calls_missing_weights_only(site)
        assert offenders == [], (
            f"{site.relative_to(MONOREPO_ROOT)}: torch.load without "
            f"weights_only=True at line(s) {offenders}"
        )

    def test_safe_reference_site_remains_safe(self):
        """Guard the existing safe pattern against accidental regression."""
        assert _torch_load_calls_missing_weights_only(SAFE_REFERENCE_SITE) == []

    def test_repo_wide_no_new_unsafe_torch_load_in_learning_packages(self):
        """Sweep the interactive-learning packages (both copies) so a future
        copy-paste cannot reintroduce the unsafe pattern silently."""
        for base in [
            MONOREPO_ROOT / "packages/interactive-learning",
            MONOREPO_ROOT / "packages/file_processor/interactive_learning",
        ]:
            for py in base.rglob("*.py"):
                assert _torch_load_calls_missing_weights_only(py) == [], py


# ---------------------------------------------------------------------------
# E2 — model weight hygiene
# ---------------------------------------------------------------------------
class TestGitignoreWeightPatterns:
    @pytest.mark.parametrize(
        "pattern",
        ["*.pt", "*.pth", "*.bin", "*.ckpt", "*.safetensors", "*.onnx"],
    )
    def test_gitignore_covers_weight_extensions(self, pattern):
        gitignore = (MONOREPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert pattern in gitignore.split("# ")[0] or pattern in gitignore, (
            f".gitignore missing weight pattern {pattern}"
        )


# ---------------------------------------------------------------------------
# Canonical module resolution (AHW-02G regression guard)
# ---------------------------------------------------------------------------
class TestCanonicalModuleResolution:
    """AHW-02G guard: some legacy test modules put ``hf-space`` on sys.path.

    If hf-space is inserted BEFORE the repo root, the ``packages`` namespace
    resolves ``packages.core`` to the hf-space COPY — which has no
    ``router_executor`` and an UNPATCHED ``mistral_integration`` — silently
    running AHW-02 tests against the wrong module.  These tests pin canonical
    resolution regardless of collection order.
    """

    def test_router_executor_resolves_to_canonical_copy(self):
        import packages.core.router_executor as rexec

        assert "hf-space" not in Path(rexec.__file__).resolve().parts, (
            f"packages.core.router_executor resolved to the hf-space shadow: {rexec.__file__}"
        )

    def test_mistral_integration_resolves_to_canonical_patched_copy(self):
        import packages.core.mistral_integration as mi

        assert "hf-space" not in Path(mi.__file__).resolve().parts, (
            f"packages.core.mistral_integration resolved to the hf-space shadow: {mi.__file__}"
        )
        # the canonical copy must carry the AHW-02E3 opt-in gate
        assert hasattr(mi, "_cloud_opt_in_enabled"), (
            "canonical mistral_integration lost the E3 cloud opt-in gate"
        )

    def test_repo_root_namespace_portion_precedes_hf_space(self):
        import packages

        portion = Path(list(packages.__path__)[0]).resolve()
        assert "hf-space" not in portion.parts, (
            f"first packages namespace portion is the hf-space shadow: {portion}"
        )


# ---------------------------------------------------------------------------
# E3 — cloud / PHI default behaviour
# ---------------------------------------------------------------------------
class TestCloudDisabledByDefault:
    def test_mistral_client_requires_opt_in_even_with_api_key(self, monkeypatch):
        """THE regression: with an API key present but no explicit opt-in,
        the canonical MistralOCR client must NOT be created."""
        import packages.core.mistral_integration as mi

        class FakeMistral:
            def __init__(self, api_key=None):
                self.api_key = api_key

        monkeypatch.setattr(mi, "HAS_MISTRAL", True)
        monkeypatch.setattr(mi, "Mistral", FakeMistral, raising=False)
        monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key-for-unit-test")
        monkeypatch.delenv("OMNI_ENABLE_CLOUD_OCR", raising=False)

        assert mi.MistralOCR().is_available() is False

    @pytest.mark.parametrize("opt_in", ["1", "true", "yes", "TRUE"])
    def test_opt_in_enables_client(self, monkeypatch, opt_in):
        import packages.core.mistral_integration as mi

        class FakeMistral:
            def __init__(self, api_key=None):
                self.api_key = api_key

        monkeypatch.setattr(mi, "HAS_MISTRAL", True)
        monkeypatch.setattr(mi, "Mistral", FakeMistral, raising=False)
        monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key-for-unit-test")
        monkeypatch.setenv("OMNI_ENABLE_CLOUD_OCR", opt_in)

        client = mi.MistralOCR()
        assert client.is_available() is True
        assert isinstance(client.client, FakeMistral)

    @pytest.mark.parametrize("opt_in", ["false", "0", "no", "", "junk-value"])
    def test_opt_in_rejects_non_truthful_values(self, monkeypatch, opt_in):
        import packages.core.mistral_integration as mi

        class FakeMistral:
            def __init__(self, api_key=None):
                self.api_key = api_key

        monkeypatch.setattr(mi, "HAS_MISTRAL", True)
        monkeypatch.setattr(mi, "Mistral", FakeMistral, raising=False)
        monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key-for-unit-test")
        monkeypatch.setenv("OMNI_ENABLE_CLOUD_OCR", opt_in)

        assert mi.MistralOCR().is_available() is False

    def test_unifiedocr_default_chain_never_reaches_cloud_here(self):
        """In the default environment (no key, no opt-in) the UnifiedOCR
        chain must report the mistral engine as unavailable."""
        import os

        os.environ.pop("MISTRAL_API_KEY", None)
        os.environ.pop("OMNI_ENABLE_CLOUD_OCR", None)

        from packages.omni_ocr.adapter import UnifiedOCR

        available = UnifiedOCR().get_available_engines()
        assert "mistral" not in available

    def test_executor_chain_has_no_cloud_engine(self):
        from packages.core.router_executor import build_default_executor

        executor = build_default_executor()
        cloud_names = {"mistral", "MISTRAL", "MistralOCR", "MistralIntegration"}
        assert cloud_names.isdisjoint(executor._adapters.keys())
