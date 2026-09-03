#!/usr/bin/env python3
"""
tests/test_dockerfile_entrypoint_contract.py

Behavioral contract tests for Docker entrypoint paths.

Verifies that:
1. Repository entrypoint file exists (deploy/docker-entrypoint.sh)
2. It is not a symlink
3. Dockerfile ENTRYPOINT points to the real post-COPY path (/app/deploy/...)
4. Old incorrect path (/app/docker-entrypoint.sh) is not declared
5. Dockerfile uses `test -f` to check existence
6. Dockerfile sets executable permission explicitly (chmod)
7. Dockerfile verifies executability (test -x)
8. No `|| true` or failure suppression in entrypoint preparation
9. deploy/Dockerfile.gradio contract is consistent
10. deploy/Dockerfile.api uses its own entrypoint correctly
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── Helpers ──────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── deploy/Dockerfile (API/omni production image) ────────────────────────

class TestDockerfileEntrypointContract:
    """Tests for deploy/Dockerfile — the canonical API production image."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile")

    def test_entrypoint_source_file_exists(self):
        """The entrypoint script must exist in the repository."""
        assert (ROOT / "deploy" / "docker-entrypoint.sh").exists(), (
            "deploy/docker-entrypoint.sh must exist in the repository"
        )

    def test_entrypoint_source_is_not_symlink(self):
        """The entrypoint must be a real file, not a symlink."""
        path = ROOT / "deploy" / "docker-entrypoint.sh"
        assert not path.is_symlink(), (
            f"{path} must not be a symlink — symlinks can be exploited "
            f"for path traversal in Docker build contexts"
        )

    def test_entrypoint_has_shebang(self):
        """The entrypoint must start with a valid shebang."""
        content = _read(ROOT / "deploy" / "docker-entrypoint.sh")
        assert content.startswith("#!"), (
            "deploy/docker-entrypoint.sh must start with a shebang (#!/...)"
        )

    def test_entrypoint_uses_correct_post_copy_path(self, dockerfile: str):
        """ENTRYPOINT must point to /app/deploy/docker-entrypoint.sh
        (the real path after `COPY --chown=omni:omni . .` copies the
        repository into /app/)."""
        assert 'ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]' in dockerfile, (
            "ENTRYPOINT must be /app/deploy/docker-entrypoint.sh — "
            "the repository's deploy/docker-entrypoint.sh becomes "
            "/app/deploy/docker-entrypoint.sh after COPY . ."
        )

    def test_old_incorrect_path_not_declared(self, dockerfile: str):
        """The old incorrect path /app/docker-entrypoint.sh must NOT appear
        in ENTRYPOINT or RUN commands."""
        # Check ENTRYPOINT lines
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if stripped.startswith("ENTRYPOINT"):
                assert "/app/docker-entrypoint.sh" not in stripped, (
                    f"ENTRYPOINT must not reference old path: {stripped}"
                )
            if stripped.startswith("RUN") and "docker-entrypoint" in stripped:
                assert "/app/docker-entrypoint.sh" not in stripped, (
                    f"RUN must not reference old path: {stripped}"
                )

    def test_dockerfile_checks_existence_with_test_f(self, dockerfile: str):
        """Dockerfile must use `test -f` to verify the entrypoint exists."""
        assert "test -f" in dockerfile, (
            "Dockerfile must use `test -f` to verify entrypoint existence"
        )

    def test_dockerfile_sets_executable_permission(self, dockerfile: str):
        """Dockerfile must explicitly set executable permission via chmod."""
        assert "chmod 0755" in dockerfile or "chmod +x" in dockerfile, (
            "Dockerfile must set executable permission on entrypoint"
        )

    def test_dockerfile_verifies_executability(self, dockerfile: str):
        """Dockerfile must verify the entrypoint is executable via `test -x`."""
        assert "test -x" in dockerfile, (
            "Dockerfile must use `test -x` to verify entrypoint is executable"
        )

    def test_no_failure_suppression_in_entrypoint_prep(self, dockerfile: str):
        """No `|| true` or equivalent failure suppression in entrypoint
        preparation commands."""
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped, (
                    f"Failure suppression `|| true` found in: {stripped}"
                )
                assert "2>/dev/null" not in stripped, (
                    f"Stderr suppression found in: {stripped}"
                )

    def test_dockerfile_has_copy_all(self, dockerfile: str):
        """Dockerfile must have `COPY --chown=omni:omni . .` to copy
        the full repository (including deploy/docker-entrypoint.sh)."""
        assert "COPY --chown=omni:omni . ." in dockerfile, (
            "Dockerfile must copy the full repository with --chown"
        )


# ── deploy/Dockerfile.gradio (Gradio HITL production image) ──────────────

class TestDockerfileGradioEntrypointContract:
    """Tests for deploy/Dockerfile.gradio — the Gradio production image."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile.gradio")

    def test_gradio_uses_correct_entrypoint_path(self, dockerfile: str):
        """Gradio Dockerfile must also use /app/deploy/docker-entrypoint.sh."""
        assert 'ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]' in dockerfile

    def test_gradio_makes_entrypoint_executable(self, dockerfile: str):
        """Gradio Dockerfile must make the entrypoint executable."""
        assert "chmod" in dockerfile and "docker-entrypoint" in dockerfile

    def test_gradio_no_failure_suppression(self, dockerfile: str):
        """No `|| true` in gradio Dockerfile entrypoint preparation."""
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped


# ── deploy/Dockerfile.api (FastAPI standalone image) ─────────────────────

class TestDockerfileApiEntrypointContract:
    """Tests for deploy/Dockerfile.api — the standalone API image.

    This Dockerfile uses a DIFFERENT entrypoint (entrypoint.sh at repo root)
    because it has a simpler build that doesn't use the multi-stage deploy/
    directory structure. This is tested separately to avoid confusion.
    """

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile.api")

    def test_api_entrypoint_source_exists(self):
        """entrypoint.sh must exist at repository root for Dockerfile.api."""
        assert (ROOT / "entrypoint.sh").exists(), (
            "entrypoint.sh must exist at repository root for Dockerfile.api"
        )

    def test_api_entrypoint_is_not_symlink(self):
        """entrypoint.sh must not be a symlink."""
        path = ROOT / "entrypoint.sh"
        assert not path.is_symlink()

    def test_api_dockerfile_makes_entrypoint_executable(self, dockerfile: str):
        """Dockerfile.api must make entrypoint.sh executable."""
        assert "chmod +x entrypoint.sh" in dockerfile or "chmod 0755 entrypoint.sh" in dockerfile

    def test_api_dockerfile_uses_correct_entrypoint(self, dockerfile: str):
        """Dockerfile.api must use ./entrypoint.sh as ENTRYPOINT."""
        assert 'ENTRYPOINT ["./entrypoint.sh"]' in dockerfile

    def test_api_dockerfile_no_failure_suppression(self, dockerfile: str):
        """No `|| true` in API Dockerfile."""
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped


# ── Cross-Dockerfile consistency ──────────────────────────────────────────

class TestDockerfileConsistency:
    """Verify all production Dockerfiles are internally consistent."""

    def test_all_entrypoint_sources_exist(self):
        """All referenced entrypoint scripts must exist in the repo."""
        assert (ROOT / "deploy" / "docker-entrypoint.sh").exists()
        assert (ROOT / "entrypoint.sh").exists()

    def test_all_entrypoints_are_regular_files(self):
        """No entrypoint may be a symlink."""
        assert not (ROOT / "deploy" / "docker-entrypoint.sh").is_symlink()
        assert not (ROOT / "entrypoint.sh").is_symlink()

    def test_all_entrypoints_have_shebang(self):
        """All entrypoint scripts must start with a shebang."""
        for path in [
            ROOT / "deploy" / "docker-entrypoint.sh",
            ROOT / "entrypoint.sh",
        ]:
            content = _read(path)
            assert content.startswith("#!"), f"{path.name} must start with #!"
