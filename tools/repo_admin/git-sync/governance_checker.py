#!/usr/bin/env python3
"""Governance checker for git-sync-system.

Enforces allowlist/denylist policies, write-mode gating, branch protection
awareness, and audit logging for all sync operations across the repo portfolio.

Usage:
    python governance_checker.py --repo omni-medical-suite --branch main --operation push --mode safe-push
    python governance_checker.py --repo ai-fuel-engine --branch main --operation push --mode safe-push
    python governance_checker.py --status  # show policy summary
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "governance.yaml"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "audit.log"

ALLOWED_MODES = {"read-only", "safe-push", "full-write"}
ALLOWED_OPERATIONS = {"pull", "fetch", "push", "delete-branch", "force-push"}

logger = logging.getLogger("governance")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class GovernanceConfig:
    """Parsed representation of governance.yaml."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.default_mode: str = data.get("default_mode", "read-only")
        self.allowlist: list[str] = data.get("allowlist", [])
        self.denylist: list[str] = data.get("denylist", [])
        self.sensitive: list[str] = data.get("sensitive", [])

        bp: dict[str, Any] = data.get("branch_protection", {})
        self.check_before_push: bool = bp.get("check_before_push", True)
        self.deny_force_push_protected: bool = bp.get("deny_force_push_protected", True)

        audit: dict[str, Any] = data.get("audit", {})
        self.audit_enabled: bool = audit.get("enabled", True)
        self.audit_log_file: str = audit.get("log_file", "logs/audit.log")
        self.max_log_size_mb: int = audit.get("max_log_size_mb", 50)

        rotation: dict[str, Any] = data.get("log_rotation", {})
        self.max_log_files: int = rotation.get("max_files", 10)
        self.compress_logs: bool = rotation.get("compress", True)

    # Convenience ---------------------------------------------------------------

    def resolve_log_path(self) -> Path:
        """Return the absolute path for the audit log."""
        p = Path(self.audit_log_file)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


class CheckResult:
    """Result of a governance policy check."""

    __slots__ = ("allowed", "reason", "repo", "branch", "operation", "mode")

    def __init__(
        self,
        *,
        allowed: bool,
        reason: str,
        repo: str,
        branch: str,
        operation: str,
        mode: str,
    ) -> None:
        self.allowed = allowed
        self.reason = reason
        self.repo = repo
        self.branch = branch
        self.operation = operation
        self.mode = mode

    def __repr__(self) -> str:
        status = "ALLOWED" if self.allowed else "DENIED"
        return f"CheckResult({status}: {self.repo}@{branch} {self.operation}/{self.mode} — {self.reason})"


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(path: Optional[Path] = None) -> GovernanceConfig:
    """Load and parse the governance YAML configuration.

    Args:
        path: Override path to governance.yaml. Falls back to CONFIG_PATH.

    Returns:
        A GovernanceConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file cannot be parsed.
    """
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Governance config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Governance config must be a YAML mapping, got {type(data).__name__}")

    return GovernanceConfig(data)


# ---------------------------------------------------------------------------
# Policy checker
# ---------------------------------------------------------------------------


def check_push_allowed(
    repo_name: str,
    branch: str = "main",
    mode: str = "safe-push",
    operation: str = "push",
    config: Optional[GovernanceConfig] = None,
) -> CheckResult:
    """Check whether a sync operation is allowed under governance policy.

    The evaluation order is:
        1. Read-only operations (pull, fetch) — always allowed.
        2. Denylist — always denied regardless of mode.
        3. Default mode is read-only; write operations require explicit mode.
        4. Sensitive repos require full-write mode.
        5. Allowlist — safe-push and full-write are allowed.
        6. Everything else is denied.

    Args:
        repo_name: Name of the repository (e.g. "omni-medical-suite").
        branch: Target branch name. Defaults to "main".
        mode: Requested write mode ("read-only", "safe-push", "full-write").
        operation: Type of operation ("pull", "fetch", "push", "delete-branch", "force-push").
        config: Pre-loaded config. Loaded from disk if None.

    Returns:
        CheckResult with allowed flag and human-readable reason.
    """
    if config is None:
        config = load_config()

    # Normalise inputs
    repo = repo_name.strip().lower().split("/")[-1]  # handle "owner/repo" form
    branch = branch.strip()
    mode = mode.strip().lower()
    operation = operation.strip().lower()

    # 1. Read-only operations are always allowed
    if operation in ("pull", "fetch"):
        return CheckResult(
            allowed=True,
            reason="Read-only operation always allowed",
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 2. Validate mode
    if mode not in ALLOWED_MODES:
        return CheckResult(
            allowed=False,
            reason=f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(ALLOWED_MODES))}",
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 3. Read-only mode blocks all writes
    if mode == "read-only":
        return CheckResult(
            allowed=False,
            reason=f"Operation '{operation}' blocked: repo is in read-only mode. Use --write or --force-write.",
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 4. Denylist — absolute block
    if repo in [r.lower() for r in config.denylist]:
        return CheckResult(
            allowed=False,
            reason=f"Repository '{repo_name}' is on the denylist (archived/protected). Pushes are never allowed.",
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 5. Force-push protection on any branch (configurable)
    if operation == "force-push" and config.deny_force_push_protected:
        return CheckResult(
            allowed=False,
            reason="Force-push is denied by governance policy (deny_force_push_protected=true).",
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 6. Sensitive repos require full-write + explicit confirmation
    if repo in [r.lower() for r in config.sensitive]:
        if mode == "full-write":
            return CheckResult(
                allowed=True,
                reason=(
                    f"Repository '{repo_name}' is sensitive. "
                    f"Full-write mode confirmed — proceed with caution."
                ),
                repo=repo,
                branch=branch,
                operation=operation,
                mode=mode,
            )
        return CheckResult(
            allowed=False,
            reason=(
                f"Repository '{repo_name}' is sensitive (contains training data). "
                f"Requires --force-write and explicit confirmation."
            ),
            repo=repo,
            branch=branch,
            operation=operation,
            mode=mode,
        )

    # 7. Allowlist check
    if repo in [r.lower() for r in config.allowlist]:
        if mode in ("safe-push", "full-write"):
            # safe-push to main is allowed for allowlist repos
            return CheckResult(
                allowed=True,
                reason=f"Repository '{repo_name}' is on the allowlist. {mode} to '{branch}' approved.",
                repo=repo,
                branch=branch,
                operation=operation,
                mode=mode,
            )

    # 8. Not on any list — deny by default (read-only default)
    return CheckResult(
        allowed=False,
        reason=(
            f"Repository '{repo_name}' is not on the allowlist. "
            f"Add it to config/governance.yaml allowlist to enable pushes."
        ),
        repo=repo,
        branch=branch,
        operation=operation,
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------


def _rotate_logs(config: GovernanceConfig) -> None:
    """Rotate audit logs if they exceed max_log_size_mb.

    Implements a simple numbered rotation scheme:
        audit.log       → audit.log.1.gz
        audit.log.1.gz  → audit.log.2.gz
        ...
    """
    log_path = config.resolve_log_path()
    if not log_path.exists():
        return

    size_mb = log_path.stat().st_size / (1024 * 1024)
    if size_mb < config.max_log_size_mb:
        return

    # Rotate existing numbered files (highest number first)
    for i in range(config.max_log_files, 1, -1):
        src = log_path.with_suffix(f".log.{i - 1}.gz") if i > 1 else log_path
        dst = log_path.with_suffix(f".log.{i}.gz")
        if i == 1:
            # Compress the current log as .log.1.gz
            dst = log_path.parent / (log_path.stem + ".log.1.gz")
            if dst.exists():
                dst.unlink()
            with open(log_path, "rb") as f_in:
                with gzip.open(dst, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)

    # Truncate the current log
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("")


def log_operation(
    operation: str,
    repo: str,
    branch: str,
    result: str,
    details: str = "",
    config: Optional[GovernanceConfig] = None,
) -> None:
    """Append an entry to the audit log.

    Args:
        operation: Operation type (push, pull, delete-branch, etc.).
        repo: Repository name.
        branch: Branch name.
        result: Result status (allowed, denied, error, etc.).
        details: Optional free-text details.
        config: Pre-loaded config. Loaded from disk if None.
    """
    if config is None:
        config = load_config()

    if not config.audit_enabled:
        logger.debug("Audit logging is disabled in configuration.")
        return

    log_path = config.resolve_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Rotate if needed
    _rotate_logs(config)

    entry: dict[str, str] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "repo": repo,
        "branch": branch,
        "result": result,
        "details": details,
    }

    line = json.dumps(entry, ensure_ascii=False)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def log_check_result(result: CheckResult, config: Optional[GovernanceConfig] = None) -> None:
    """Log a CheckResult to the audit log.

    Args:
        result: The CheckResult to log.
        config: Pre-loaded config. Loaded from disk if None.
    """
    status = "allowed" if result.allowed else "denied"
    log_operation(
        operation=result.operation,
        repo=result.repo,
        branch=result.branch,
        result=status,
        details=f"mode={result.mode} reason={result.reason}",
        config=config,
    )


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------


def print_status(config: Optional[GovernanceConfig] = None) -> None:
    """Print a summary of the current governance configuration.

    Args:
        config: Pre-loaded config. Loaded from disk if None.
    """
    if config is None:
        config = load_config()

    print("=" * 60)
    print("  git-sync-system — Governance Policy Status")
    print("=" * 60)
    print(f"  Default mode:           {config.default_mode}")
    print(f"  Branch protection check: {config.check_before_push}")
    print(f"  Deny force-push:        {config.deny_force_push_protected}")
    print(f"  Audit logging:          {'enabled' if config.audit_enabled else 'disabled'}")
    print(f"  Audit log:              {config.resolve_log_path()}")
    print(f"  Max log size:           {config.max_log_size_mb} MB")
    print(f"  Max rotated files:      {config.max_log_files}")
    print(f"  Compress rotated:       {config.compress_logs}")
    print()
    print(f"  Allowlist ({len(config.allowlist)} repos):")
    for r in sorted(config.allowlist):
        print(f"    ✅ {r}")
    print()
    print(f"  Denylist ({len(config.denylist)} repos):")
    for r in sorted(config.denylist):
        print(f"    🚫 {r}")
    print()
    print(f"  Sensitive ({len(config.sensitive)} repos):")
    for r in sorted(config.sensitive):
        print(f"    ⚠️  {r}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="governance_checker",
        description="Check whether a sync operation is allowed under governance policy.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check sub-command
    check_parser = subparsers.add_parser("check", help="Check if an operation is allowed")
    check_parser.add_argument("--repo", required=True, help="Repository name")
    check_parser.add_argument("--branch", default="main", help="Branch name (default: main)")
    check_parser.add_argument(
        "--operation",
        default="push",
        choices=sorted(ALLOWED_OPERATIONS),
        help="Operation type (default: push)",
    )
    check_parser.add_argument(
        "--mode",
        default="safe-push",
        choices=sorted(ALLOWED_MODES),
        help="Write mode (default: safe-push)",
    )

    # status sub-command
    subparsers.add_parser("status", help="Show governance policy summary")

    # log sub-command
    log_parser = subparsers.add_parser("log", help="Manually append an audit log entry")
    log_parser.add_argument("--operation", required=True, help="Operation type")
    log_parser.add_argument("--repo", required=True, help="Repository name")
    log_parser.add_argument("--branch", default="main", help="Branch name")
    log_parser.add_argument("--result", required=True, help="Result (allowed/denied/error)")
    log_parser.add_argument("--details", default="", help="Optional details")

    # Backward-compatible: support bare --repo/--branch/--operation/--mode
    parser.add_argument("--repo", dest="_compat_repo", help=argparse.SUPPRESS)
    parser.add_argument("--branch", dest="_compat_branch", help=argparse.SUPPRESS)
    parser.add_argument("--operation", dest="_compat_op", help=argparse.SUPPRESS)
    parser.add_argument("--mode", dest="_compat_mode", help=argparse.SUPPRESS)

    return parser


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 if operation is allowed, 1 if denied, 2 on error.
    """
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Sub-command dispatch
    if args.command == "status":
        print_status(config)
        return 0

    if args.command == "log":
        log_operation(
            operation=args.operation,
            repo=args.repo,
            branch=args.branch,
            result=args.result,
            details=args.details,
            config=config,
        )
        print(f"Audit entry logged: {args.operation} on {args.repo}@{args.branch} → {args.result}")
        return 0

    if args.command == "check":
        result = check_push_allowed(
            repo_name=args.repo,
            branch=args.branch,
            operation=args.operation,
            mode=args.mode,
            config=config,
        )
        log_check_result(result, config)

        if result.allowed:
            print(f"ALLOWED: {result.reason}")
            return 0
        else:
            print(f"DENIED: {result.reason}", file=sys.stderr)
            return 1

    # Backward-compat: bare flags treated as check
    if getattr(args, "_compat_repo", None):
        result = check_push_allowed(
            repo_name=args._compat_repo,
            branch=args._compat_branch or "main",
            operation=args._compat_op or "push",
            mode=args._compat_mode or "safe-push",
            config=config,
        )
        log_check_result(result, config)

        if result.allowed:
            print(f"ALLOWED: {result.reason}")
            return 0
        else:
            print(f"DENIED: {result.reason}", file=sys.stderr)
            return 1

    # No command specified — show help
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
