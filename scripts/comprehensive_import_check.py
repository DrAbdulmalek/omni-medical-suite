#!/usr/bin/env python3
"""
Comprehensive import check for omni-medical-suite.

Strategy:
  1. Walk packages/* and app/* looking for every __init__.py
  2. For each, derive the dotted module path and attempt importlib.import_module
  3. Also try a curated list of critical modules known to break in this repo
  4. Report any import failures with full traceback context

Used as the project-wide "zero-breakage" gate after risky merges.
Especially important after merges that delete or move files (mobile consolidation,
app/services rewiring).

Usage:
    python3 /home/z/my-project/scripts/comprehensive_import_check.py
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Canonical path setup (matches tests/conftest.py + pytest.ini `pythonpath = . src packages`)
# 1. REPO_ROOT  → for `app/` and `packages/<pkg>` as top-level
# 2. REPO_ROOT/src → for top-level src/ modules
# 3. REPO_ROOT/packages → for `packages.<pkg>` dotted access
# 4. Each packages/<pkg>/src → for src-layout packages (e.g. scanner_fixer)
#
# NOTE: We deliberately DO NOT add `packages/<pkg>` directly to sys.path.
# That would shadow the `app` package (e.g. packages/handwriting/app.py would win over app/)
# and would shadow the `packages.core` namespace (e.g. packages/doc_processor/packages/core/__init__.py
# would override packages/core/__init__.py).
for p in [REPO_ROOT, REPO_ROOT / "src", REPO_ROOT / "packages"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
for src in REPO_ROOT.glob("packages/*/src"):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

# Curated list of modules known to be load-bearing in this project
# (these are the ones that have broken before or are critical)
CRITICAL_MODULES = [
    # App entry points
    "app",
    "app.gradio_full_hitl",
    "app.gradio_extended",
    "app.advanced_review_app",
    "app.main",
    "app.services",
    # Scanner fixer (the focus of this merge round)
    "scanner_fixer.pdf_ocr_processor",
    # Mobile (the focus of merges 5 & 6) — try both old and new locations
    "packages.core.mobile",
    "packages.core.mobile.server",
    # Core engine registry
    "packages.core.engine_registry",
    # NLP translation corrector (was broken by orphan dir shadowing the .py file)
    "packages.nlp.translation_corrector",
]

# Packages that are archived / legacy / structurally unimportable.
# These are NOT counted as failures when they don't import — they're documented
# as "not part of the active import graph" and skipped to keep the report clean.
#
# Reasons:
#   - file_processor, omnifile, handwriting: archived packages (per pyproject.toml
#     comment "ARCHIVED: merged into omni-medical-suite"). Designed for standalone
#     execution (cwd on sys.path) not for `packages.<pkg>.modules.X` absolute import.
#     All internal `from modules.X import Y` imports work in their designed runtime
#     but fail in repo-wide import checks.
#   - ai-fuel, interactive-learning: hyphen in directory name. Python identifiers
#     cannot contain hyphens, so `packages.ai-fuel` is not a valid module path.
#     The active underscore-named versions live elsewhere (e.g. tools/ai_fuel/).
#   - omniparse: requires torch (heavy dep, not installed in CI).
#   - benchmark_core: no __init__.py at root — not a proper Python package,
#     just a directory of standalone benchmark scripts.
ARCHIVED_PACKAGES = {
    "packages.file_processor",
    "packages.omnifile",
    "packages.handwriting",
    "packages.ai-fuel",
    "packages.interactive-learning",
    "packages.omniparse",
    "packages.benchmark_core",
    "packages.doc_processor",
}


def find_init_files(root: Path) -> list[Path]:
    """Find every __init__.py under root, excluding venvs/caches."""
    skip_dirs = {".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".git"}
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped dirs in-place (mutating dirnames affects os.walk)
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if fname == "__init__.py":
                results.append(Path(dirpath) / fname)
    return sorted(results)


def derive_dotted_path(init_file: Path, repo_root: Path) -> str | None:
    """
    Derive the dotted import path for an __init__.py file.

    Rules:
      - If file is under packages/<pkg>/src/<rest>/__init__.py → "<rest joined by .>"
        (because src/ is the package root added to sys.path)
      - If file is under packages/<pkg>/<rest>/__init__.py → "packages.<pkg>.<rest>"
        BUT ONLY if <rest> does not itself start with "packages/" or "app/" or "src/"
        (those are shadow dirs we should not import — they would pollute the namespace).
      - If file is under app/<rest>/__init__.py → "app.<rest>"
      - Otherwise: skip (we don't know how to import it reliably)
    """
    try:
        rel = init_file.relative_to(repo_root)
    except ValueError:
        return None
    parts = list(rel.parts)
    if parts[0] == "packages" and len(parts) >= 3:
        if parts[2] == "src":
            # packages/<pkg>/src/<rest>/__init__.py → import as <rest>
            module_parts = parts[3:-1]
            if not module_parts:
                module_parts = [parts[1]]
            return ".".join(module_parts)
        else:
            # packages/<pkg>/<rest>/__init__.py → import as packages.<pkg>.<rest>
            # Skip shadow directories that would re-export top-level namespaces
            # (e.g. packages/doc_processor/packages/core/__init__.py is a vendored
            # copy, not the real packages.core — it would shadow the canonical one).
            rest_parts = parts[2:-1]
            if not rest_parts:
                return f"packages.{parts[1]}"
            if rest_parts[0] in ("packages", "app", "src"):
                return None  # skip shadow dir
            return "packages." + ".".join([parts[1]] + rest_parts)
    elif parts[0] == "app" and len(parts) >= 2:
        module_parts = parts[:-1]
        return ".".join(module_parts)
    return None


def try_import(module_name: str) -> tuple[bool, str | None]:
    """Attempt to import module_name. Returns (success, error_message_or_None)."""
    try:
        importlib.import_module(module_name)
        return True, None
    except Exception as exc:
        # Capture just the final exception line + type for brevity
        tb = traceback.format_exc()
        # Get last 3 lines of traceback for context
        tb_lines = tb.strip().splitlines()
        last_lines = "\n".join(tb_lines[-6:]) if len(tb_lines) > 6 else tb
        return False, f"{type(exc).__name__}: {exc}\n{last_lines}"


def main() -> int:
    print(f"[comprehensive_import_check] repo_root = {REPO_ROOT}")
    print(f"[comprehensive_import_check] sys.path[0:8] =")
    for p in sys.path[:8]:
        print(f"  {p}")
    print()

    # Phase 1: Find every __init__.py and try to import it
    pkg_root = REPO_ROOT / "packages"
    app_root = REPO_ROOT / "app"

    init_files = []
    if pkg_root.exists():
        init_files.extend(find_init_files(pkg_root))
    if app_root.exists():
        init_files.extend(find_init_files(app_root))

    print(f"[comprehensive_import_check] discovered {len(init_files)} __init__.py files")
    print()

    results = []  # list of (module_name, success, error)
    seen_modules = set()

    for init_file in init_files:
        module_name = derive_dotted_path(init_file, REPO_ROOT)
        if module_name is None or module_name in seen_modules:
            continue
        seen_modules.add(module_name)
        ok, err = try_import(module_name)
        results.append((module_name, ok, err))

    # Phase 2: Critical modules (some may not have __init__.py discovery path)
    for crit in CRITICAL_MODULES:
        if crit in seen_modules:
            continue
        seen_modules.add(crit)
        ok, err = try_import(crit)
        results.append((crit, ok, err))

    # Report
    failures = [r for r in results if not r[1]]
    successes = [r for r in results if r[1]]

    # Separate failures into: active-package failures (real) vs archived-package (skip)
    active_failures = []
    archived_failures = []
    for module_name, _ok, err in failures:
        if any(module_name.startswith(prefix) for prefix in ARCHIVED_PACKAGES):
            archived_failures.append((module_name, _ok, err))
        else:
            active_failures.append((module_name, _ok, err))

    print("=" * 78)
    print(f"IMPORT CHECK SUMMARY")
    print(f"  Total modules attempted       : {len(results)}")
    print(f"  Successful imports            : {len(successes)}")
    print(f"  Failures in ACTIVE packages   : {len(active_failures)}")
    print(f"  Failures in ARCHIVED packages : {len(archived_failures)} (skipped — see ARCHIVED_PACKAGES)")
    print("=" * 78)

    if active_failures:
        print()
        print("ACTIVE-PACKAGE FAILURES (real bugs to investigate):")
        print("-" * 78)
        for module_name, _ok, err in active_failures:
            print(f"\n  ❌ {module_name}")
            for line in (err or "").splitlines():
                print(f"      {line}")

    if archived_failures:
        print()
        print(f"ARCHIVED-PACKAGE FAILURES (skipped, {len(archived_failures)} modules):")
        print("-" * 78)
        archived_prefixes = {}
        for module_name, _ok, _err in archived_failures:
            prefix = ".".join(module_name.split(".")[:2])
            archived_prefixes[prefix] = archived_prefixes.get(prefix, 0) + 1
        for prefix, count in sorted(archived_prefixes.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}× {prefix}")
        print()
        print("  These packages are documented as archived/legacy in their pyproject.toml.")
        print("  They are designed for standalone execution (cwd on sys.path) and are not")
        print("  part of the active repo-wide import graph. See ARCHIVED_PACKAGES in this script.")

    print()
    print("=" * 78)
    if active_failures:
        print(f"RESULT: FAIL — {len(active_failures)} active-package failure(s) must be fixed")
        print(f"        ({len(archived_failures)} archived-package failures skipped)")
    else:
        print(f"RESULT: PASS — zero active-package breakage across {len(successes)} modules")
        print(f"        ({len(archived_failures)} archived-package failures skipped)")
    print("=" * 78)
    return 1 if active_failures else 0


if __name__ == "__main__":
    sys.exit(main())
