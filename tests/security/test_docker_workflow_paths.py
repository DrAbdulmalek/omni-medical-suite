"""Regression test: docker workflow must reference real production Dockerfile paths.

Prevents stale/nonexistent paths (infrastructure/docker/Dockerfile.web,
infrastructure/docker/Dockerfile.api, apps/web/) from returning to the
Docker build workflow.

The production Dockerfiles live in deploy/:
  - deploy/Dockerfile.gradio  (Gradio HITL interface, production target)
  - deploy/Dockerfile.api     (FastAPI production image)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker.yml"
HARDENING_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "production-hardening.yml"

# Paths that MUST NOT appear in docker.yml (they are stale/nonexistent).
STALE_PATHS = [
    "infrastructure/docker/Dockerfile.web",
    "infrastructure/docker/Dockerfile.api",
    "infrastructure/docker/",
    "apps/web/",
]

# Paths that MUST appear in docker.yml (the real production Dockerfiles).
REQUIRED_PATHS = [
    "deploy/Dockerfile.gradio",
    "deploy/Dockerfile.api",
]


class TestDockerWorkflowPaths:
    """Verify docker.yml uses real production Dockerfile paths."""

    def test_docker_workflow_exists(self):
        assert DOCKER_WORKFLOW.exists(), f"Missing: {DOCKER_WORKFLOW}"

    def test_docker_workflow_references_real_dockerfiles(self):
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        for required in REQUIRED_PATHS:
            assert required in content, (
                f"docker.yml must reference '{required}' — not found in workflow"
            )

    def test_docker_workflow_does_not_reference_stale_paths(self):
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        for stale in STALE_PATHS:
            assert stale not in content, (
                f"docker.yml must NOT reference stale path '{stale}' — "
                f"these paths do not exist in the repository"
            )

    def test_checkout_uses_recursive_submodules(self):
        """All checkout steps must use submodules: recursive because
        data/arabic-medical-glossary is a submodule needed at build time."""
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        # Count checkout steps and verify each has submodules: recursive
        checkout_blocks = re.findall(
            r"uses:\s*actions/checkout@v\d+\n(.*?)(?=\s+-\s*name:|\s*-\s*name:|$)",
            content,
            re.DOTALL,
        )
        assert len(checkout_blocks) >= 2, (
            f"Expected at least 2 checkout steps, found {len(checkout_blocks)}"
        )
        for i, block in enumerate(checkout_blocks):
            assert "submodules: recursive" in block, (
                f"Checkout step #{i+1} does not use 'submodules: recursive'"
            )

    def test_gradio_build_uses_production_target(self):
        """The Gradio image build must use target=production to match
        the production-hardening gate's docker build command."""
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        # Find the gradio build step
        gradio_section = re.search(
            r"docker-gradio:.*?Build and push Gradio image.*?with:\s*\n(.*?)(?:\n\s*-\s*name:|$)",
            content,
            re.DOTALL,
        )
        assert gradio_section, "Could not find Gradio build section"
        assert "target: production" in gradio_section.group(1), (
            "Gradio build must use 'target: production'"
        )

    def test_production_hardening_includes_regression_test(self):
        """The production-hardening workflow must run this regression test."""
        content = HARDENING_WORKFLOW.read_text(encoding="utf-8")
        assert "test_docker_workflow_paths" in content, (
            "production-hardening.yml must run tests/security/test_docker_workflow_paths.py"
        )
