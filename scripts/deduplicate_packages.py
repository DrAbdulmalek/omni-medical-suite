#!/usr/bin/env python3
"""
deduplicate_packages.py — إزالة التكرارات في packages/ وتحديث imports

Usage:
    python scripts/deduplicate_packages.py --dry-run   # معاينة فقط
    python scripts/deduplicate_packages.py --apply      # تنفيذ فعلي
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"


# ─── Rules ───────────────────────────────────────────────────────

DEDUP_RULES = [
    {
        "description": "pattern_db.py: إبقاء packages/learning/ فقط",
        "keep": PACKAGES_DIR / "learning" / "pattern_db.py",
        "remove": PACKAGES_DIR / "ai" / "pattern_db.py",
        "import_fixes": [
            (r"from packages\.ai\.pattern_db", "from packages.learning.pattern_db"),
            (r"from \.pattern_db import", "from packages.learning.pattern_db import"),
        ],
    },
    {
        "description": "audit_logger.py: إبقاء packages/audit/ فقط",
        "keep": PACKAGES_DIR / "audit" / "audit_logger.py",
        "remove": PACKAGES_DIR / "security" / "audit_logger.py",
        "import_fixes": [
            (r"from packages\.security\.audit_logger", "from packages.audit.audit_logger"),
            (r"from \.audit_logger import", "from packages.audit.audit_logger import"),
        ],
    },
    {
        "description": "encryption.py: إبقاء packages/security/ فقط",
        "keep": PACKAGES_DIR / "security" / "encryption.py",
        "remove": PACKAGES_DIR / "core" / "encryption.py",
        "import_fixes": [
            (r"from packages\.core\.encryption", "from packages.security.encryption"),
            (r"from \.encryption import", "from packages.security.encryption import"),
        ],
    },
    {
        "description": "layout_preserving.py: إبقاء المجلد فقط",
        "keep": PACKAGES_DIR / "export" / "layout_preserving",  # directory
        "remove": PACKAGES_DIR / "export" / "layout_preserving.py",  # file
        "import_fixes": [
            (
                r"from packages\.export\.layout_preserving import LayoutPreservingExporter",
                "from packages.export.layout_preserving.exporter import LayoutPreservingExporter",
            ),
            (
                r"from packages\.export\.layout_preserving import",
                "from packages.export.layout_preserving.exporter import",
            ),
        ],
    },
]


def find_python_files(root: Path) -> list[Path]:
    """Find all .py files recursively."""
    return list(root.rglob("*.py"))


def count_imports(needle: str, files: list[Path]) -> int:
    count = 0
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if needle in content:
            count += 1
    return count


def fix_imports(rule: dict, py_files: list[Path], dry_run: bool) -> int:
    """Fix import paths in all Python files. Returns count of files modified."""
    fixed = 0
    for pattern, replacement in rule.get("import_fixes", []):
        regex = re.compile(pattern)
        for f in py_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            new_content = regex.sub(replacement, content)
            if new_content != content:
                fixed += 1
                if dry_run:
                    print(f"  [DRY-RUN] Would fix in: {f.relative_to(REPO_ROOT)}")
                else:
                    f.write_text(new_content, encoding="utf-8")
                    print(f"  Fixed imports in: {f.relative_to(REPO_ROOT)}")
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Remove duplicate modules in packages/")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"=== Deduplication [{mode}] ===\n")

    py_files = find_python_files(PACKAGES_DIR)
    py_files += find_python_files(REPO_ROOT / "services")
    py_files += find_python_files(REPO_ROOT / "apps")
    py_files += find_python_files(REPO_ROOT / "tests")

    total_removed = 0
    total_fixed = 0

    for rule in DEDUP_RULES:
        desc = rule["description"]
        keep_path = rule["keep"]
        remove_path = rule["remove"]

        print(f"\n--- {desc} ---")

        if not keep_path.exists():
            print(f"  WARNING: Keep target does not exist: {keep_path.relative_to(REPO_ROOT)}")
            continue

        if not remove_path.exists():
            print(f"  OK: Remove target already gone: {remove_path.relative_to(REPO_ROOT)}")
            continue

        # Count references before
        remove_name = remove_path.name.replace(".py", "")
        refs = count_imports(remove_name, py_files)
        print(f"  Found {refs} references to {remove_name}")

        # Fix imports
        fixed = fix_imports(rule, py_files, dry_run=args.dry_run)
        total_fixed += fixed
        print(f"  Import fixes: {fixed} files")

        # Remove
        if args.dry_run:
            print(f"  [DRY-RUN] Would remove: {remove_path.relative_to(REPO_ROOT)}")
        else:
            if remove_path.is_dir():
                shutil.rmtree(remove_path)
            else:
                remove_path.unlink()
            print(f"  Removed: {remove_path.relative_to(REPO_ROOT)}")
            total_removed += 1

    # ── omni-core merge ──
    print(f"\n--- Merge packages/omni-core into packages/core ---")
    omni_core = PACKAGES_DIR / "omni-core"
    core = PACKAGES_DIR / "core"

    if omni_core.exists() and core.exists():
        if args.dry_run:
            print(f"  [DRY-RUN] Would merge {len(list(omni_core.iterdir()))} files from omni-core to core")
            print(f"  [DRY-RUN] Would remove packages/omni-core/")
        else:
            # Copy unique files
            for item in omni_core.iterdir():
                dest = core / item.name
                if not dest.exists():
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    print(f"  Copied: {item.name}")
            # Fix imports
            for f in py_files:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                new_content = re.sub(
                    r"from packages\.omni[_\.]core",
                    "from packages.core",
                    content,
                )
                new_content = re.sub(
                    r"import packages\.omni[_\.]core",
                    "import packages.core",
                    new_content,
                )
                if new_content != content:
                    f.write_text(new_content, encoding="utf-8")
                    total_fixed += 1
            shutil.rmtree(omni_core)
            print(f"  Removed: packages/omni-core/")
            total_removed += 1
    else:
        print(f"  OK: omni-core already merged or doesn't exist")

    print(f"\n=== Summary [{mode}] ===")
    print(f"  Files removed: {total_removed}")
    print(f"  Import fixes: {total_fixed} files")
    print(f"  Done.")


if __name__ == "__main__":
    main()
