"""Pytest config — make observability + scanner_fixer importable."""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for pkg in ("observability", "scanner_fixer"):
    src = _REPO_ROOT / "packages" / pkg / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
