#!/usr/bin/env python3
"""
CLI wrapper for the PromotionPipeline.

Usage:
    python scripts/promote.py status                              List all datasets with stages
    python scripts/promote.py check <dataset_id>                  Show readiness score breakdown
    python scripts/promote.py promote <dataset_id> <stage>        Promote a dataset to a stage
    python scripts/promote.py demote <dataset_id> <stage> <reason> Demote a dataset (reason required)
    python scripts/promote.py register <dataset_id>               Register a new dataset
    python scripts/promote.py changelog <dataset_id>              Generate changelog for a dataset
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path so the src package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.promotion import PromotionPipeline, ReadinessScorer, AutoChangelog


# ══════════════════════════════════════════════════════════════════
# Logging Setup
# ══════════════════════════════════════════════════════════════════

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def _get_pipeline(state_file: str, datasets_dir: str) -> PromotionPipeline:
    """Create a PromotionPipeline instance with resolved paths."""
    state_path = Path(state_file) if state_file else None
    data_path = Path(datasets_dir) if datasets_dir else None
    return PromotionPipeline(state_file=state_path, datasets_dir=data_path)


def _print_json(data: object) -> None:
    """Pretty-print data as JSON to stdout."""
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _bar(score: int, max_score: int, width: int = 30) -> str:
    """Generate a simple text progress bar."""
    ratio = score / max_score if max_score > 0 else 0
    filled = int(width * ratio)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score}/{max_score}"


# ══════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════

def cmd_status(args: argparse.Namespace) -> int:
    """List all datasets grouped by promotion stage."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)
    all_datasets = pipeline.list_all()

    total = all_datasets.pop("_total", 0)
    stages = ["draft", "candidate", "approved", "production"]

    print(f"\n{'═' * 60}")
    print(f"  Promotion Pipeline Status — {total} dataset(s) registered")
    print(f"{'═' * 60}\n")

    any_found = False
    for stage in stages:
        datasets = all_datasets.get(stage, [])
        if not datasets:
            continue
        any_found = True

        emoji = {"draft": "📝", "candidate": "🔬", "approved": "✅", "production": "🚀"}
        print(f"  {emoji.get(stage, '•')} {stage.upper()} ({len(datasets)})")
        print(f"  {'─' * 50}")

        for ds in datasets:
            score_str = str(ds["last_score"]) if ds["last_score"] is not None else "—"
            print(
                f"    • {ds['dataset_id']:<30} score: {score_str:>3}  "
                f"registered: {ds['registered_at'][:10] if ds['registered_at'] else '—'}"
            )
        print()

    if not any_found:
        print("  No datasets registered yet. Use 'register <dataset_id>' to add one.\n")

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Show the readiness score breakdown for a dataset."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)

    print(f"\n{'═' * 60}")
    print(f"  Readiness Check: {args.dataset_id}")
    print(f"{'═' * 60}\n")

    try:
        report = pipeline.check_readiness(args.dataset_id)
    except Exception as exc:
        print(f"  ❌ Error: {exc}\n")
        return 1

    # Header
    print(f"  Dataset:      {report.dataset_id}")
    print(f"  Total Score:  {report.total_score}/{report.max_score} ({report.percentage}%)")
    print(f"  Ready for:    {report.ready_for_stage or 'none'}")
    print()

    # Criteria breakdown
    print(f"  {'Criterion':<20} {'Status':<8} {'Score':<10} Detail")
    print(f"  {'─' * 58}")

    for c in report.criteria:
        icon = "✅" if c.passed else "❌"
        bar_str = _bar(c.points_earned, c.points_max, width=8)
        print(f"  {c.name:<20} {icon:<8} {bar_str:<10} {c.message}")

    print()

    # Recommendations
    if report.recommendations:
        print("  💡 Recommendations:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"    {i}. {rec}")
        print()

    # JSON output if requested
    if args.json:
        _print_json(report)

    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    """Promote a dataset to the specified stage."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)

    print(f"\n{'═' * 60}")
    print(f"  Promote: {args.dataset_id} → {args.stage}")
    print(f"{'═' * 60}\n")

    # Auto-register if not found
    if pipeline.get_status(args.dataset_id) is None:
        if not args.auto_register:
            print(
                f"  ❌ Dataset '{args.dataset_id}' is not registered.\n"
                f"     Use 'register {args.dataset_id}' first, or add --auto-register."
            )
            return 1
        try:
            pipeline.register(args.dataset_id)
            print(f"  📝 Auto-registered '{args.dataset_id}' at draft.\n")
        except ValueError as exc:
            print(f"  ❌ {exc}\n")
            return 1

    try:
        ds = pipeline.promote(args.dataset_id, args.stage, force=args.force)
        print(f"  ✅ Promoted to: {ds.stage}")
        print(f"     Score: {ds.last_score}")
        print(f"     Time:  {ds.history[-1]['timestamp'] if ds.history else '—'}")
        print()
    except ValueError as exc:
        print(f"  ❌ Promotion failed: {exc}\n")
        return 1

    return 0


def cmd_demote(args: argparse.Namespace) -> int:
    """Demote a dataset to a previous stage."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)

    print(f"\n{'═' * 60}")
    print(f"  Demote: {args.dataset_id} → {args.stage}")
    print(f"{'═' * 60}\n")

    try:
        ds = pipeline.demote(args.dataset_id, args.stage, reason=args.reason)
        print(f"  ⚠️  Demoted to: {ds.stage}")
        print(f"     Reason: {args.reason}")
        print(f"     Time:   {ds.history[-1]['timestamp'] if ds.history else '—'}")
        print()
    except ValueError as exc:
        print(f"  ❌ Demotion failed: {exc}\n")
        return 1

    return 0


def cmd_register(args: argparse.Namespace) -> int:
    """Register a new dataset in the pipeline."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)

    print(f"\n{'═' * 60}")
    print(f"  Register: {args.dataset_id}")
    print(f"{'═' * 60}\n")

    try:
        ds = pipeline.register(args.dataset_id)
        print(f"  ✅ Registered '{ds.dataset_id}' at stage 'draft'")
        print(f"     Time: {ds.registered_at}")
        print()
    except ValueError as exc:
        print(f"  ❌ Registration failed: {exc}\n")
        return 1

    return 0


def cmd_changelog(args: argparse.Namespace) -> int:
    """Generate a changelog for a dataset."""
    pipeline = _get_pipeline(args.state_file, args.datasets_dir)

    print(f"\n{'═' * 60}")
    print(f"  Changelog: {args.dataset_id}")
    print(f"{'═' * 60}\n")

    try:
        md = pipeline.generate_changelog(
            dataset_id=args.dataset_id,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            version=args.version,
        )
        print(md)
    except Exception as exc:
        print(f"  ❌ Changelog generation failed: {exc}\n")
        return 1

    return 0


# ══════════════════════════════════════════════════════════════════
# Argument Parser
# ══════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promote",
        description="Promotion pipeline CLI for Medical OCR Training Hub datasets/models.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="Path to promotion_state.json (default: ./promotion_state.json).",
    )
    parser.add_argument(
        "--datasets-dir",
        default=None,
        help="Root directory containing dataset subdirectories.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    subparsers.add_parser("status", help="List all datasets with their promotion stages.")

    # check
    check_p = subparsers.add_parser("check", help="Show readiness score for a dataset.")
    check_p.add_argument("dataset_id", help="Dataset identifier.")
    check_p.add_argument(
        "--json", action="store_true", help="Output as JSON instead of formatted text."
    )

    # promote
    promote_p = subparsers.add_parser("promote", help="Promote a dataset to a target stage.")
    promote_p.add_argument("dataset_id", help="Dataset identifier.")
    promote_p.add_argument(
        "stage",
        choices=["draft", "candidate", "approved", "production"],
        help="Target promotion stage.",
    )
    promote_p.add_argument(
        "--force",
        action="store_true",
        help="Skip stage-adjacency and minimum score checks.",
    )
    promote_p.add_argument(
        "--auto-register",
        action="store_true",
        help="Auto-register the dataset at draft if not already registered.",
    )

    # demote
    demote_p = subparsers.add_parser("demote", help="Demote a dataset to an earlier stage.")
    demote_p.add_argument("dataset_id", help="Dataset identifier.")
    demote_p.add_argument(
        "stage",
        choices=["draft", "candidate", "approved", "production"],
        help="Target stage (must be earlier than current).",
    )
    demote_p.add_argument("reason", help="Reason for demotion (required).")

    # register
    register_p = subparsers.add_parser("register", help="Register a new dataset at draft.")
    register_p.add_argument("dataset_id", help="Dataset identifier.")

    # changelog
    cl_p = subparsers.add_parser("changelog", help="Generate changelog for a dataset.")
    cl_p.add_argument("dataset_id", help="Dataset identifier.")
    cl_p.add_argument("--from-ref", default="HEAD~20", help="Git ref to start from.")
    cl_p.add_argument("--to-ref", default="HEAD", help="Git ref to end at.")
    cl_p.add_argument("--version", default="Unreleased", help="Version string for header.")

    return parser


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

COMMAND_MAP = {
    "status": cmd_status,
    "check": cmd_check,
    "promote": cmd_promote,
    "demote": cmd_demote,
    "register": cmd_register,
    "changelog": cmd_changelog,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if not args.command:
        parser.print_help()
        return 0

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())