"""SEC-2 regression tests: no token-like strings in tracked .env files (suite).

Master prompt Wave 1.2: example/env files must never carry real-shaped
credentials. Companion to test_no_embedded_default_credentials.py which
covers default passwords; this module covers token SHAPES
(github classic / fine-grained / huggingface / telegram bot / openai-style
/ aws) in tracked .env-style files.

Policy:
- Tracked .env-style files must contain no string matching a known token
  shape, outside explicitly declared placeholder templates.
- Pattern literals below cannot match themselves (metacharacters break the
  shape). Matched values are never printed — only file:line.
- Whole-repository / full-history secret coverage is handled by the
  gitleaks-style history scan (Wave 1.1) and CI secret scanning.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

TOKEN_SHAPES: dict[str, re.Pattern[str]] = {
    "github_classic_pat": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "github_other_pat": re.compile(r"gh[osu]_[A-Za-z0-9]{30,}"),
    "github_fine_grained": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "huggingface": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "telegram_bot": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
}

# Structural placeholder templates (fullmatch on the matched value only).
# Never substring-classify: real base62 tokens can contain runs like 'xxxxx'.
PLACEHOLDER_TEMPLATES = [
    re.compile(r"^<[A-Z_][A-Z0-9_]*>$"),
    re.compile(r"(?i)^change_me.*$"),
    re.compile(r"^[A-Za-z]+[_-][xX]{8,}$"),
    re.compile(r"^\[REDACTED[^\]]*\]$"),
    re.compile(r"^1234567890:ABCdefGHIjklMNOpqrsTUVwxyz$"),
    re.compile(r"(?i)^(dummy|sample|example|test|fixture)[-_]?(token|key|secret)$"),
    re.compile(r"(?i)^generate_a_random_.*$"),
]


def _is_placeholder(value: str) -> bool:
    return any(t.fullmatch(value) for t in PLACEHOLDER_TEMPLATES)


def _tracked_env_files():
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
        )
        tracked = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    except Exception:  # pragma: no cover - git unavailable
        tracked = set()
    for rel in sorted(tracked):
        name = Path(rel).name
        if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
            path = REPO_ROOT / rel
            if path.is_file():
                yield rel, path


@pytest.mark.parametrize("label", sorted(TOKEN_SHAPES))
def test_no_token_like_strings_in_env_files(label: str):
    rx = TOKEN_SHAPES[label]
    hits: list[str] = []
    for rel, path in _tracked_env_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in rx.finditer(text):
            value = match.group(0)
            if _is_placeholder(value):
                continue
            line_no = text[: match.start()].count("\n") + 1
            hits.append(f"{rel}:{line_no} (value withheld)")
    assert not hits, (
        f"Token-like string ({label}) found in tracked env files: {hits}. "
        "Real tokens belong only in untracked .env; use <YOUR_*> placeholders "
        "in example files and rotate/revoke any leaked value immediately."
    )
