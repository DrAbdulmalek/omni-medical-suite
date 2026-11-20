#!/usr/bin/env python3
"""
Validate all Jupyter notebooks under notebooks/ for Colab compatibility.

Used by .github/workflows/ci-matrix.yml (colab-smoke job).
Exit codes:
    0 — all notebooks valid
    1 — at least one notebook failed validation
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

try:
    from nbformat import read, validate
    from nbformat.validator import ValidationError
except ImportError:
    print("❌ nbformat not installed. Run: pip install nbformat", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    notebooks = sorted(glob.glob("notebooks/*.ipynb"))
    print(f"Found {len(notebooks)} notebooks:")

    failures: list[str] = []
    for nb_path in notebooks:
        try:
            with open(nb_path) as f:
                nb = read(f, as_version=4)
            validate(nb)
            cells = len(nb.cells)
            code_cells = sum(1 for c in nb.cells if c.cell_type == "code")
            md_cells = sum(1 for c in nb.cells if c.cell_type == "markdown")
            print(
                f"  ✅ {nb_path} ({cells} cells: "
                f"{code_cells} code, {md_cells} markdown)"
            )
        except ValidationError as e:
            print(f"  ❌ {nb_path}: {e}")
            failures.append(nb_path)
        except Exception as e:
            print(f"  ❌ {nb_path}: {type(e).__name__}: {e}")
            failures.append(nb_path)

    print()
    if failures:
        print(f"{len(failures)} notebook(s) failed validation")
        return 1

    print(f"All {len(notebooks)} notebooks valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
