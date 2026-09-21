"""Regression tests: no embedded default credentials in deployment configuration.

Guards against reintroduction of hardcoded default passwords (SEC-1, 2026-09-21):
docker-compose.yml previously shipped ``POSTGRES_PASSWORD:-omni_dev_pass`` fallbacks,
letting any stack boot with a publicly-known credential.

Policy:
- docker-compose.yml must use required-variable syntax ``${POSTGRES_PASSWORD:?...}``
- no known default credential string may appear anywhere in tracked files
- documented tables must mark POSTGRES_PASSWORD as REQUIRED (no default)
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Any future default credential added here must also be removed from all tracked files.
KNOWN_FORBIDDEN_DEFAULTS: tuple[str, ...] = ("omni_dev_pass",)

COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
REQUIRED_SYNTAX_MARKERS = ("${POSTGRES_PASSWORD:?",)


def _iter_text_files():
    """Yield tracked, text-decodable files (skips .git, binaries, notebooks)."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
        )
        tracked = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    except Exception:  # pragma: no cover - fallback when git is unavailable
        tracked = set()

    if not tracked:  # fallback: filesystem walk
        for p in REPO_ROOT.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                tracked.add(str(p.relative_to(REPO_ROOT)))

    for rel in sorted(tracked):
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
                           ".7z", ".gz", ".whl", ".pyc", ".svg", ".ttf", ".woff"}:
            continue
        if ".ipynb" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        yield path, text


def test_compose_file_exists():
    assert COMPOSE_FILE.is_file(), "docker-compose.yml missing from repository root"


def test_compose_uses_required_postgres_password_syntax():
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert any(marker in text for marker in REQUIRED_SYNTAX_MARKERS), (
        "docker-compose.yml must require POSTGRES_PASSWORD via ${POSTGRES_PASSWORD:?...} "
        "syntax instead of a silent default"
    )


@pytest.mark.parametrize("forbidden", KNOWN_FORBIDDEN_DEFAULTS)
def test_no_known_default_credentials_anywhere(forbidden: str):
    hits = [str(path.relative_to(REPO_ROOT)) for path, text in _iter_text_files() if forbidden in text]
    assert not hits, (
        f"Known default credential '{forbidden}' reappeared in tracked files: {hits}. "
        "Deployment secrets must come from the environment (.env), never defaults."
    )


def test_readme_documents_postgres_password_as_required():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    row = next((line for line in readme.splitlines() if "`POSTGRES_PASSWORD`" in line and "|" in line), "")
    assert row, "README config table lost its POSTGRES_PASSWORD row"
    assert "required" in row.lower(), (
        "README must document POSTGRES_PASSWORD as REQUIRED (no default); "
        f"current row: {row!r}"
    )
