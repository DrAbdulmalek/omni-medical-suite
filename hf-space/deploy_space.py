#!/usr/bin/env python3
"""
deploy_space.py — Deploy Omni Medical OCR to Hugging Face Spaces
Usage:
    python deploy_space.py --token hf_xxxxxxxxxxxxx
    # Or set HF_TOKEN env var:
    export HF_TOKEN=hf_xxxxxxxxxxxxx && python deploy_space.py
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None, check=True):
    """Run a shell command and return its output."""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(f"    {result.stdout.strip()}")
    if result.returncode != 0 and check:
        print(f"  ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Deploy Omni Medical OCR to HF Spaces")
    parser.add_argument("--token", help="HuggingFace access token (or set HF_TOKEN env var)")
    parser.add_argument("--repo", default="DrAbdulmalek/medical-ocr-demo", help="Space repo ID")
    parser.add_argument("--skip-create", action="store_true", help="Skip repo creation (if already exists)")
    args = parser.parse_args()

    token = args.token or os.environ.get("HF_TOKEN", "")
    if not token:
        print("ERROR: No HuggingFace token provided!")
        print("  Get one from: https://huggingface.co/settings/tokens")
        print("  Usage: python deploy_space.py --token hf_xxx")
        print("     or: export HF_TOKEN=hf_xxx && python deploy_space.py")
        sys.exit(1)

    space_dir = Path(__file__).parent
    repo_id = args.repo

    print(f"\n{'='*60}")
    print(f"  Omni Medical OCR — HF Space Deployment")
    print(f"  Target: https://huggingface.co/spaces/{repo_id}")
    print(f"{'='*60}\n")

    # Step 1: Create Space repo on HF (if needed)
    if not args.skip_create:
        print("Step 1/3: Creating Space repository on HuggingFace...")
        run(
            f'HF_TOKEN={token} hf repos create {repo_id} --type space --sdk docker',
            cwd=space_dir, check=False
        )
        print()
    else:
        print("Step 1/3: Skipping repo creation (already exists)\n")

    # Step 2: Configure git remote
    print("Step 2/3: Configuring git remote...")
    run(f"git remote remove origin 2>/dev/null || true", cwd=space_dir, check=False)
    run(
        f'git remote add origin https://DrAbdulmalek:{token}@huggingface.co/spaces/{repo_id}',
        cwd=space_dir
    )
    print()

    # Step 3: Push to HF
    print("Step 3/3: Pushing to HuggingFace...")
    run("git push -u origin main --force", cwd=space_dir)
    print()

    # Done
    url = f"https://huggingface.co/spaces/{repo_id}"
    print(f"{'='*60}")
    print(f"  ✅ Space deployed successfully!")
    print(f"")
    print(f"  🔗 URL: {url}")
    print(f"  📊 Status: {url}/tree/main")
    print(f"")
    print(f"  The Space will start building automatically.")
    print(f"  It may take 5-10 minutes for the Docker image to build.")
    print(f"  Once ready, the app will be live at the URL above.")
    print(f"{'='*60}\n")

    # Cleanup: remove token from remote URL
    run(f'git remote set-url origin https://huggingface.co/spaces/{repo_id}', cwd=space_dir)


if __name__ == "__main__":
    main()