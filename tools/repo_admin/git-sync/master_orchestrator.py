#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Master Orchestrator — Automated infrastructure management
Dr. Abdulmalek - Omni Medical Suite

Usage:
  python3 master_orchestrator.py              # dry-run (preview only)
  python3 master_orchestrator.py --apply      # apply changes
  python3 master_orchestrator.py --phase 1    # specific phase only
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════════
#  Settings
# ══════════════════════════════════════════════════════════════

BASE_DIR = Path(os.environ.get("REPOS_DIR", Path.home() / "github~"))
DRY_RUN = "--apply" not in sys.argv
LOG_FILE = BASE_DIR / f"orchestrator_{datetime.now():%Y%m%d_%H%M%S}.log"

ACTIVE_REPOS = [
    "omni-medical-suite",
    "medical-ocr-ground-truth",
    "medical-ocr-benchmarks",
    "medical-ocr-training-hub",
    "medical-ocr-trainer",
    "scanner-fixer",
    "telegram-forwarder",
    "ai-fuel-engine",
    "IntelliFile-app",
    "bilingual-extractor",
]

ARCHIVED_REPOS = [
    "medical-handwriting-ocr",
    "medical-ocr-postprocessor",
    "OmniFile_Processor",
    "medical-doc-processor",
]

GITHUB_USER = "DrAbdulmalek"

# ══════════════════════════════════════════════════════════════
#  Colors & Utilities
# ══════════════════════════════════════════════════════════════

class C:
    RED = '\033[91m'; GREEN = '\033[92m'; YELLOW = '\033[93m'
    BLUE = '\033[94m'; CYAN = '\033[96m'; RESET = '\033[0m'; BOLD = '\033[1m'

def log(msg, level="INFO"):
    prefix = {"INFO": "  ", "OK": "[OK] ", "WARN": "[!!] ",
              "ERROR": "[XX] ", "ACTION": "[>>] ", "DRY": "[DRY] ", "PHASE": "[##] "}
    colors = {"INFO": C.BLUE, "OK": C.GREEN, "WARN": C.YELLOW,
              "ERROR": C.RED, "ACTION": C.BLUE, "DRY": C.CYAN, "PHASE": C.BOLD + C.CYAN}
    tag = prefix.get(level, "")
    print(f"{colors.get(level, C.RESET)}{tag}{msg}{C.RESET}")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{level}] {msg}\n")

def run(cmd, cwd=None):
    if DRY_RUN:
        log(f"$ {cmd}", "DRY")
        return 0, "", ""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd,
                          capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        log(f"Failed: {e}", "ERROR")
        return 1, "", str(e)

def repo_exists(name):
    p = BASE_DIR / name
    return p.exists() and (p / ".git").exists()

def get_token():
    """Get GitHub token from environment or secrets file."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        secrets = Path.home() / ".config" / "git-sync-system" / "secrets.env"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"')
                    break
    return token

# ══════════════════════════════════════════════════════════════
#  Phase 1: Download Missing Repos
# ══════════════════════════════════════════════════════════════

def phase1_download_missing():
    log("=" * 55, "PHASE")
    log("Phase 1: Download missing repositories", "PHASE")
    log("=" * 55, "PHASE")

    token = get_token()
    all_repos = ACTIVE_REPOS + ARCHIVED_REPOS
    downloaded, skipped, failed = 0, 0, 0

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for repo in all_repos:
        path = BASE_DIR / repo
        if repo_exists(repo):
            log(f"{repo} (exists)", "INFO")
            skipped += 1
            continue

        log(f"{repo}...", "ACTION")
        url = f"https://github.com/{GITHUB_USER}/{repo}.git"
        if token:
            url = f"https://x-access-token:{token}@github.com/{GITHUB_USER}/{repo}.git"
        rc, _, err = run(f'git clone --depth 1 "{url}" "{path}"', cwd=BASE_DIR)
        if rc == 0:
            log(f"{repo}", "OK")
            downloaded += 1
        else:
            log(f"{repo}: {err[:80]}", "ERROR")
            failed += 1

    log(f"Result: {downloaded} cloned | {skipped} exists | {failed} failed", "INFO")
    return downloaded

# ══════════════════════════════════════════════════════════════
#  Phase 2: Unified .flake8 Config
# ══════════════════════════════════════════════════════════════

FLAKE8_CONFIG = """[flake8]
max-line-length = 120
extend-ignore = E203, W503
exclude =
    .git,
    __pycache__,
    build,
    dist,
    .venv,
    venv,
    node_modules,
    .pytest_cache
per-file-ignores =
    __init__.py:F401
    tests/*:E501,W293
"""

def phase2_flake8_config():
    log("=" * 55, "PHASE")
    log("Phase 2: Unified .flake8 config", "PHASE")
    log("=" * 55, "PHASE")

    created = 0
    for repo in ACTIVE_REPOS:
        if not repo_exists(repo):
            continue
        flake8 = BASE_DIR / repo / ".flake8"
        if flake8.exists():
            log(f"{repo}/.flake8 (exists)", "INFO")
            continue
        log(f"{repo}/.flake8", "ACTION")
        if not DRY_RUN:
            flake8.write_text(FLAKE8_CONFIG, encoding='utf-8')
            created += 1
    log(f"Created {created} .flake8 files", "OK")
    return created

# ══════════════════════════════════════════════════════════════
#  Phase 3: CONTRIBUTING.md
# ══════════════════════════════════════════════════════════════

CONTRIBUTING_MD = """# Contributing

Thank you for your interest!

## Quick Start

1. **Fork** the repository
2. **Clone** your fork locally
3. Create a branch: `git checkout -b feature/my-feature`
4. Commit: `git commit -m 'feat: add feature'`
5. Push: `git push origin feature/my-feature`
6. Open a Pull Request

## Code Standards

- Follow **PEP 8** (see `.flake8` in root)
- Use **type hints** for public functions
- Add **docstrings** (Google style)
- Write **tests** for new features

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add a feature
fix: fix a bug
docs: update documentation
chore: maintenance
test: add tests
```

## Reporting Issues

Use Issue Templates in `.github/ISSUE_TEMPLATE/`
"""

def phase3_contributing():
    log("=" * 55, "PHASE")
    log("Phase 3: Create CONTRIBUTING.md", "PHASE")
    log("=" * 55, "PHASE")

    created = 0
    for repo in ACTIVE_REPOS:
        if not repo_exists(repo):
            continue
        contrib = BASE_DIR / repo / "CONTRIBUTING.md"
        if contrib.exists():
            log(f"{repo}/CONTRIBUTING.md (exists)", "INFO")
            continue
        log(f"{repo}/CONTRIBUTING.md", "ACTION")
        if not DRY_RUN:
            contrib.write_text(CONTRIBUTING_MD, encoding='utf-8')
            created += 1
    log(f"Created {created} CONTRIBUTING.md files", "OK")
    return created

# ══════════════════════════════════════════════════════════════
#  Phase 4: Archive Banners
# ══════════════════════════════════════════════════════════════

ARCHIVE_BANNER = """> **Archived Repository**
>
> This repository is now **archived**. All active development has been
> migrated to the core platform:
> **[Omni-Medical-Suite](https://github.com/DrAbdulmalek/omni-medical-suite)**
>

"""

def phase4_archive_banners():
    log("=" * 55, "PHASE")
    log("Phase 4: Add archive banners", "PHASE")
    log("=" * 55, "PHASE")

    added = 0
    for repo in ARCHIVED_REPOS:
        if not repo_exists(repo):
            log(f"{repo} (not cloned)", "INFO")
            continue
        readme = BASE_DIR / repo / "README.md"
        if not readme.exists():
            continue
        content = readme.read_text(encoding='utf-8', errors='ignore')
        if "omni-medical-suite" in content and "Archived" in content:
            log(f"{repo} (banner exists)", "INFO")
            continue
        log(f"{repo}/README.md", "ACTION")
        if not DRY_RUN:
            readme.write_text(ARCHIVE_BANNER + content, encoding='utf-8')
            added += 1
    log(f"Added {added} archive banners", "OK")
    return added

# ══════════════════════════════════════════════════════════════
#  Phase 5: Quality Audit (flake8 + bandit)
# ══════════════════════════════════════════════════════════════

def phase5_quality_audit():
    log("=" * 55, "PHASE")
    log("Phase 5: Quality audit (flake8 + bandit)", "PHASE")
    log("=" * 55, "PHASE")

    report_lines = [f"# Quality Audit — {datetime.now():%Y-%m-%d %H:%M}", ""]

    for repo in ACTIVE_REPOS[:5]:
        if not repo_exists(repo):
            continue
        log(f"Scanning {repo}...", "ACTION")

        rc, flake_out, _ = run(
            'flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>/dev/null | head -20',
            cwd=BASE_DIR / repo
        )
        report_lines.append(f"## {repo}")
        report_lines.append(f"### Flake8 (Critical)\n```\n{flake_out.strip() or 'No critical errors'}\n```\n")

        rc, bandit_out, _ = run(
            'bandit -r . -q -lll 2>/dev/null | head -30',
            cwd=BASE_DIR / repo
        )
        report_lines.append(f"### Bandit (High)\n```\n{bandit_out.strip() or 'No high issues'}\n```\n")

    report_path = BASE_DIR / "quality_audit_report.md"
    if not DRY_RUN:
        report_path.write_text("\n".join(report_lines), encoding='utf-8')
        log(f"Report: {report_path}", "OK")
    return len(report_lines)

# ══════════════════════════════════════════════════════════════
#  Phase 6: Push All Changes
# ══════════════════════════════════════════════════════════════

def phase6_push_all():
    log("=" * 55, "PHASE")
    log("Phase 6: Push all changes to GitHub", "PHASE")
    log("=" * 55, "PHASE")

    if DRY_RUN:
        log("Would push changes to all repos", "DRY")
        return 0

    token = get_token()
    pushed = 0
    for repo in ACTIVE_REPOS + ARCHIVED_REPOS:
        if not repo_exists(repo):
            continue
        rc, status, _ = run("git status --porcelain", cwd=BASE_DIR / repo)
        if not status.strip():
            log(f"{repo} (clean)", "INFO")
            continue
        log(f"{repo}...", "ACTION")
        if token:
            run(f'git remote set-url origin "https://x-access-token:{token}@github.com/{GITHUB_USER}/{repo}.git"',
                cwd=BASE_DIR / repo)
        rc, branch, _ = run("git rev-parse --abbrev-ref HEAD", cwd=BASE_DIR / repo)
        branch = branch.strip()
        rc, _, err = run(f"git push origin {branch}", cwd=BASE_DIR / repo)
        if rc == 0:
            log(f"{repo}", "OK")
            pushed += 1
        else:
            log(f"{repo}: {err[:80]}", "ERROR")
    log(f"Pushed {pushed} repos", "OK")
    return pushed

# ══════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════

def main():
    print(f"\n{C.BOLD}{C.CYAN}{'=' * 57}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  Master Orchestrator — Omni Medical Suite{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'=' * 57}{C.RESET}")

    if DRY_RUN:
        print(f"\n{C.YELLOW}{C.BOLD}  DRY-RUN — no changes will be made{C.RESET}")
        print(f"{C.YELLOW}  To apply: python3 master_orchestrator.py --apply{C.RESET}\n")
    else:
        print(f"\n{C.RED}{C.BOLD}  APPLY MODE — changes will be made{C.RESET}\n")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Orchestrator — {datetime.now()}\nMode: {'APPLY' if not DRY_RUN else 'DRY-RUN'}\n\n")

    target_phase = None
    if "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        if idx + 1 < len(sys.argv):
            target_phase = int(sys.argv[idx + 1])

    phases = [
        (1, "Download missing repos", phase1_download_missing),
        (2, "Unified .flake8 config", phase2_flake8_config),
        (3, "Create CONTRIBUTING.md", phase3_contributing),
        (4, "Archive banners", phase4_archive_banners),
        (5, "Quality audit", phase5_quality_audit),
        (6, "Push all changes", phase6_push_all),
    ]

    results = {}
    for num, name, func in phases:
        if target_phase and num != target_phase:
            continue
        results[num] = func()

    print(f"\n{C.BOLD}{'=' * 57}{C.RESET}")
    print(f"{C.BOLD}  Summary:{C.RESET}")
    for num, name, _ in phases:
        if num in results:
            status = C.GREEN + str(results[num]) + C.RESET
            print(f"   {num}. {name}: {status}")
    print(f"{C.BOLD}{'=' * 57}{C.RESET}\n")

if __name__ == '__main__':
    main()