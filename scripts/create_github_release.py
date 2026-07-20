#!/usr/bin/env python3
"""Create GitHub Release via PyGithub API.

Usage:
    GITHUB_TOKEN=ghp_xxx python3 scripts/create_github_release.py [TAG] [REPO]

Environment:
    GITHUB_TOKEN — GitHub PAT with repo scope (required)
"""
import os
import sys
from github import Github, Auth

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_NAME = os.argv[2] if len(sys.argv) > 2 else "DrAbdulmalek/omni-medical-suite"
TAG = os.argv[1] if len(sys.argv) > 1 else "v1.1.0"

if not TOKEN:
    print("ERROR: GITHUB_TOKEN env var is required", file=sys.stderr)
    sys.exit(1)

# Read release notes
script_dir = os.path.dirname(os.path.abspath(__file__))
notes_path = os.path.join(script_dir, "..", "docs", f"RELEASE_NOTES_{TAG}.md")
if not os.path.exists(notes_path):
    # Fallback: try with dots instead of dots in filename
    version = TAG.lstrip("v")
    notes_path = os.path.join(script_dir, "..", "docs", f"RELEASE_NOTES_v{version}.md")

with open(notes_path, "r") as f:
    body = f.read()

auth = Auth.Token(TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo(REPO_NAME)

# Check if release already exists
for rel in repo.get_releases():
    if rel.tag_name == TAG:
        print(f"Release {TAG} already exists (id={rel.id}), updating...")
        rel.update_release(
            name=f"{TAG} — Stable Release",
            message=body,
            draft=False,
            prerelease=False,
        )
        print(f"✅ Release updated: {rel.html_url}")
        sys.exit(0)

# Create the release
release = repo.create_git_release(
    tag=TAG,
    name=f"{TAG} — Stable Release",
    message=body,
    draft=False,
    prerelease=False,
)

print(f"✅ Release created: {release.html_url}")
print(f"   Tag: {TAG}")
print(f"   ID: {release.id}")
