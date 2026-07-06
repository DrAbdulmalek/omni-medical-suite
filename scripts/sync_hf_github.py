"""
Sync training data between GitHub training-hub and HuggingFace Space.

Two directions:
1. GitHub → HF:  Push new ground truth + configs to HF Space persistent storage
2. HF → GitHub:  Pull exported corrections from HF and commit to GitHub repo

Usage:
    # Pull corrections from HF Space and commit to GitHub
    python sync_hf_github.py --direction hf_to_github

    # Push ground truth from GitHub to HF Space
    python sync_hf_github.py --direction github_to_hf

    # Full bidirectional sync
    python sync_hf_github.py --direction both
"""

import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ──
GITHUB_REPO_PATH = Path(__file__).parent.parent  # medical-ocr-training-hub
HF_SPACE_PATH = Path(__file__).parent.parent.parent / "hf-space-push"
TRAINING_DATA_DIR = GITHUB_REPO_PATH / "training_data"


def git_commit_push(repo_path: Path, message: str, branch: str = "main") -> bool:
    """Stage all changes, commit, and push to remote."""
    try:
        subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True, capture_output=True)
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if not result.stdout.strip():
            logger.info("No changes to commit in %s", repo_path)
            return False

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_path, check=True, capture_output=True,
        )
        logger.info("Pushed to %s: %s", repo_path.name, message)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git error in %s: %s", repo_path, e.stderr.decode() if e.stderr else str(e))
        return False


def hf_to_github() -> Dict:
    """
    Pull exported corrections from HF Space data directory
    and merge into GitHub training-hub.
    """
    logger.info("=== HF → GitHub Sync ===")

    hf_data_dir = HF_SPACE_PATH / "data"  # HF persistent storage
    if not hf_data_dir.exists():
        # Try alternative: look for the latest export in uploads or data
        hf_data_dir = HF_SPACE_PATH / "uploads"

    crops_dest = TRAINING_DATA_DIR / "word_crops"
    crops_dest.mkdir(parents=True, exist_ok=True)

    stats = {"files_copied": 0, "total_entries": 0, "errors": []}

    # Find and copy correction JSONL files from HF
    possible_sources = [
        HF_SPACE_PATH / "data" / "word_crops",
        HF_SPACE_PATH / "exports",
    ]

    for src_dir in possible_sources:
        if not src_dir.exists():
            continue
        for f in src_dir.glob("*.jsonl"):
            target = crops_dest / f.name
            if not target.exists() or target.stat().st_size != f.stat().st_size:
                shutil.copy2(f, target)
                stats["files_copied"] += 1
                # Count entries
                with open(target, "r", encoding="utf-8") as fh:
                    count = sum(1 for _ in fh)
                stats["total_entries"] += count
                logger.info("Copied: %s (%d entries)", f.name, count)

    # Also check if HF Space has a SQLite DB we can export
    hf_db = HF_SPACE_PATH / "corrections.db"
    if hf_db.exists():
        logger.info("Found HF corrections DB — running export")
        try:
            # Import and run the export script
            sys.path.insert(0, str(GITHUB_REPO_PATH / "scripts"))
            from export_from_hf import export_corrections

            result = export_corrections(
                db_path=hf_db,
                output_dir=GITHUB_REPO_PATH,
            )
            stats["db_export"] = result
        except Exception as e:
            stats["errors"].append(f"DB export failed: {e}")
            logger.error("DB export failed: %s", e)

    if stats["files_copied"] > 0 or stats.get("db_export"):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        git_commit_push(
            GITHUB_REPO_PATH,
            f"sync: HF corrections → training hub ({timestamp})\n"
            f"- Files: {stats['files_copied']}\n"
            f"- Entries: {stats['total_entries']}",
        )

    return stats


def github_to_hf() -> Dict:
    """
    Push ground truth + model configs from GitHub training-hub
    to HF Space so the app can use them.
    """
    logger.info("=== GitHub → HF Sync ===")

    stats = {"files_copied": 0, "errors": []}

    # 1. Copy ground truth to HF Space
    gt_src = TRAINING_DATA_DIR / "ground_truth"
    gt_dst = HF_SPACE_PATH / "data" / "ground_truth"
    if gt_src.exists():
        gt_dst.mkdir(parents=True, exist_ok=True)
        for f in gt_src.glob("*.jsonl"):
            shutil.copy2(f, gt_dst / f.name)
            stats["files_copied"] += 1
            logger.info("GT → HF: %s", f.name)

    # 2. Copy model configs
    configs_src = GITHUB_REPO_PATH / "models" / "configs"
    configs_dst = HF_SPACE_PATH / "data" / "model_configs"
    if configs_src.exists():
        configs_dst.mkdir(parents=True, exist_ok=True)
        for f in configs_src.glob("*"):
            shutil.copy2(f, configs_dst / f.name)
            stats["files_copied"] += 1

    # 3. Copy config.yaml
    config_src = GITHUB_REPO_PATH / "config.yaml"
    config_dst = HF_SPACE_PATH / "data" / "config.yaml"
    if config_src.exists():
        shutil.copy2(config_src, config_dst)
        stats["files_copied"] += 1

    if stats["files_copied"] > 0:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        git_commit_push(
            HF_SPACE_PATH,
            f"sync: training hub → HF Space ({timestamp})\n"
            f"- Files: {stats['files_copied']}",
        )

    return stats


def generate_sync_log(direction: str, result: Dict) -> None:
    """Write a sync log entry."""
    logs_dir = GITHUB_REPO_PATH / "logs" / "corrections"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"sync_{direction}_{timestamp}.json"

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": direction,
        "result": result,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)

    logger.info("Sync log written: %s", log_file.name)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync between HF Space and GitHub training hub")
    parser.add_argument(
        "--direction",
        choices=["hf_to_github", "github_to_hf", "both"],
        default="both",
        help="Sync direction",
    )
    args = parser.parse_args()

    if args.direction in ("hf_to_github", "both"):
        result = hf_to_github()
        generate_sync_log("hf_to_github", result)

    if args.direction in ("github_to_hf", "both"):
        result = github_to_hf()
        generate_sync_log("github_to_hf", result)

    print("\nSync complete. Check logs/corrections/ for details.")