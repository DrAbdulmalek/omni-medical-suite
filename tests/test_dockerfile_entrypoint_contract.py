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

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestDockerfileEntrypointContract:
    """Tests for deploy/Dockerfile — the canonical API production image."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile")

    def test_entrypoint_source_file_exists(self):
        assert (ROOT / "deploy" / "docker-entrypoint.sh").exists()

    def test_entrypoint_source_is_not_symlink(self):
        path = ROOT / "deploy" / "docker-entrypoint.sh"
        assert not path.is_symlink()

    def test_entrypoint_has_shebang(self):
        content = _read(ROOT / "deploy" / "docker-entrypoint.sh")
        assert content.startswith("#!")

    def test_entrypoint_uses_correct_post_copy_path(self, dockerfile: str):
        assert 'ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]' in dockerfile

    def test_old_incorrect_path_not_declared(self, dockerfile: str):
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if stripped.startswith("ENTRYPOINT"):
                assert "/app/docker-entrypoint.sh" not in stripped
            if stripped.startswith("RUN") and "docker-entrypoint" in stripped:
                assert "/app/docker-entrypoint.sh" not in stripped

    def test_dockerfile_checks_existence_with_test_f(self, dockerfile: str):
        assert "test -f" in dockerfile

    def test_dockerfile_sets_executable_permission(self, dockerfile: str):
        assert "chmod 0755" in dockerfile or "chmod +x" in dockerfile

    def test_dockerfile_verifies_executability(self, dockerfile: str):
        assert "test -x" in dockerfile

    def test_no_failure_suppression_in_entrypoint_prep(self, dockerfile: str):
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped
                assert "2>/dev/null" not in stripped

    def test_dockerfile_has_copy_all(self, dockerfile: str):
        assert "COPY --chown=omni:omni . ." in dockerfile


class TestDockerfileGradioEntrypointContract:
    """Tests for deploy/Dockerfile.gradio — the Gradio production image."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile.gradio")

    def test_gradio_uses_correct_entrypoint_path(self, dockerfile: str):
        assert 'ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]' in dockerfile

    def test_gradio_makes_entrypoint_executable(self, dockerfile: str):
        assert "chmod" in dockerfile and "docker-entrypoint" in dockerfile

    def test_gradio_no_failure_suppression(self, dockerfile: str):
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped


class TestDockerfileApiEntrypointContract:
    """Tests for deploy/Dockerfile.api — the standalone API image."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return _read(ROOT / "deploy" / "Dockerfile.api")

    def test_api_entrypoint_source_exists(self):
        assert (ROOT / "entrypoint.sh").exists()

    def test_api_entrypoint_is_not_symlink(self):
        assert not (ROOT / "entrypoint.sh").is_symlink()

    def test_api_dockerfile_makes_entrypoint_executable(self, dockerfile: str):
        # Dockerfile.api uses an absolute post-COPY path; matching the actual
        # path avoids coupling the contract to the working directory spelling.
        assert (
            "chmod +x entrypoint.sh" in dockerfile
            or "chmod 0755 entrypoint.sh" in dockerfile
            or "chmod 0755 /app/entrypoint.sh" in dockerfile
        )

    def test_api_dockerfile_uses_correct_entrypoint(self, dockerfile: str):
        assert 'ENTRYPOINT ["./entrypoint.sh"]' in dockerfile

    def test_api_dockerfile_no_failure_suppression(self, dockerfile: str):
        for line in dockerfile.splitlines():
            stripped = line.strip()
            if "entrypoint" in stripped.lower() and stripped.startswith("RUN"):
                assert "|| true" not in stripped


class TestDockerfileConsistency:
    """Verify all production Dockerfiles are internally consistent."""

    def test_all_entrypoint_sources_exist(self):
        assert (ROOT / "deploy" / "docker-entrypoint.sh").exists()
        assert (ROOT / "entrypoint.sh").exists()

    def test_all_entrypoints_are_regular_files(self):
        assert not (ROOT / "deploy" / "docker-entrypoint.sh").is_symlink()
        assert not (ROOT / "entrypoint.sh").is_symlink()

    def test_all_entrypoints_have_shebang(self):
        for path in [
            ROOT / "deploy" / "docker-entrypoint.sh",
            ROOT / "entrypoint.sh",
        ]:
            assert _read(path).startswith("#!"), f"{path.name} must start with #!"
