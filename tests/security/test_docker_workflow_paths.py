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

    def test_docker_workflow_triggers_on_pull_request(self):
        """The Docker workflow MUST run on pull_request so that both
        production Dockerfiles are validated BEFORE merge (not only
        after merge to main). Without this, a broken Dockerfile would
        only be discovered post-merge."""
        import yaml
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        # YAML 1.1 parses 'on' as boolean True; handle both
        on_key = parsed.get("on") or parsed.get(True)
        assert on_key is not None, "docker.yml must have an 'on:' trigger section"
        assert "pull_request" in on_key, (
            "docker.yml must trigger on pull_request (currently only triggers "
            "on push to main, which means broken Dockerfiles are only caught "
            "post-merge)"
        )

    def test_docker_workflow_does_not_push_on_pull_request(self):
        """On pull_request, the Docker build MUST use push:false to avoid
        polluting GHCR with unmerged images. Push should only happen on
        push to main."""
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        # Find all 'push:' settings in build steps (the build-push-action 'push' field)
        # We look for lines that set push: with a value
        push_lines = re.findall(r"^\s+push:\s*(.+)$", content, re.MULTILINE)
        # Filter out the trigger 'push:' (which is at column 2, not 4+)
        build_push_lines = [p for p in push_lines if "${{" in p or p.strip() in ("true", "false")]
        assert len(build_push_lines) >= 2, (
            f"Expected at least 2 build push: settings (gradio + api), found {len(build_push_lines)}: {build_push_lines}"
        )
        for i, push_val in enumerate(build_push_lines):
            push_val = push_val.strip()
            # Must be conditional (not a hardcoded 'true')
            assert push_val != "true", (
                f"Build step #{i+1} has push: true (hardcoded) — must be "
                f"conditional: push: ${{{{ github.event_name == 'push' }}}}"
            )
            assert "github.event_name" in push_val and "push" in push_val, (
                f"Build step #{i+1} push setting must be conditional on "
                f"github.event_name == 'push', got: {push_val}"
            )

    def test_docker_workflow_yaml_syntax_is_valid(self):
        """Verify docker.yml has no YAML syntax corruption and parses cleanly."""
        import yaml
        content = DOCKER_WORKFLOW.read_text(encoding="utf-8")
        # Should parse without error
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "docker.yml must parse to a dict"
        # 'on' key must exist and be a dict
        on_key = parsed.get("on") or parsed.get(True)  # YAML 1.1 parses 'on' as True
        assert on_key is not None, "docker.yml must have an 'on:' trigger section"
        assert isinstance(on_key, dict), (
            f"docker.yml 'on:' must be a dict, got {type(on_key).__name__}"
        )
        # Check branches is a list, not a corrupted string
        if "push" in on_key:
            push_config = on_key["push"]
            if isinstance(push_config, dict) and "branches" in push_config:
                branches = push_config["branches"]
                assert isinstance(branches, list), (
                    f"docker.yml push.branches must be a list, got "
                    f"{type(branches).__name__}: {branches!r}"
                )
                assert "main" in branches, (
                    f"docker.yml push.branches must contain 'main', got {branches}"
                )
