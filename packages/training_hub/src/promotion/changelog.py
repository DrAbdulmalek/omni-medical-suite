#!/usr/bin/env python3
"""
AutoChangelog — Automatic changelog generation from git history.

Parses git log between two refs (tags, commits, or branches) and produces
a markdown changelog following the Keep a Changelog format with sections:
  - Added
  - Changed
  - Fixed
  - Performance

Commit messages are classified into sections using keyword matching.
Related commit hashes and issue references are preserved as links.
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════

@dataclass
class CommitEntry:
    """A parsed git commit for changelog classification."""

    hash: str
    short_hash: str
    subject: str
    body: str
    author: str
    date: str
    refs: List[str] = field(default_factory=list)


@dataclass
class ChangelogSection:
    """A single section of the changelog (e.g., Added, Fixed)."""

    title: str
    entries: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# Classification Keywords
# ══════════════════════════════════════════════════════════════════

SECTION_KEYWORDS: Dict[str, List[str]] = {
    "Added": [
        "add", "added", "adding", "new", "introduce", "introduced",
        "implement", "implemented", "create", "created", "support",
    ],
    "Changed": [
        "change", "changed", "update", "updated", "updating",
        "refactor", "refactored", "rename", "renamed", "replace",
        "migrate", "migrated", "rewrite", "rewritten", "deprecate",
    ],
    "Fixed": [
        "fix", "fixed", "fixing", "bug", "bugfix", "resolve",
        "resolved", "repair", "patch", "correct", "corrected",
        "error", "issue", "broken", "regression",
    ],
    "Performance": [
        "performance", "speed", "faster", "slow", "optimize",
        "optimized", "optimization", "efficient", "latency",
        "throughput", "memory", "reduce", "reduction",
    ],
}

# Section order in the output
SECTION_ORDER = ["Added", "Changed", "Fixed", "Performance"]

# Fallback section for unclassified commits
FALLBACK_SECTION = "Changed"


# ══════════════════════════════════════════════════════════════════
# AutoChangelog
# ══════════════════════════════════════════════════════════════════

class AutoChangelog:
    """
    Generate changelogs from git history between two refs.

    Parameters
    ----------
    repo_dir : Path
        Path to the git repository root.
    remote_url : str, optional
        Base URL for the remote repository (for linking commits).
        If not provided, links will use a placeholder.
    """

    # Changelog template
    TEMPLATE = """\
## [{version}] - {date}

{sections}

**{commit_count} commit(s) between `{from_ref}` and `{to_ref}`**
"""

    SECTION_TEMPLATE = """\
### {title}

{entries}
"""

    def __init__(
        self,
        repo_dir: Optional[Path] = None,
        remote_url: Optional[str] = None,
    ):
        self.repo_dir = Path(repo_dir) if repo_dir else Path.cwd()
        self.remote_url = remote_url

        # Try to detect remote URL from git config
        if self.remote_url is None:
            self.remote_url = self._detect_remote_url()

        logger.info("AutoChangelog initialized for %s", self.repo_dir)

    # ── Public API ──────────────────────────────────────────────

    def generate(
        self,
        from_ref: str = "HEAD~20",
        to_ref: str = "HEAD",
        version: str = "Unreleased",
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate a changelog from git log between two refs.

        Parameters
        ----------
        from_ref : str
            Starting git ref (commit hash, tag, branch, or relative ref).
        to_ref : str
            Ending git ref.
        version : str
            Version string for the changelog header.
        output_path : Path, optional
            If provided, write the changelog to this file.

        Returns
        -------
        str
            The generated markdown changelog.
        """
        commits = self._get_commits(from_ref, to_ref)
        sections = self._classify_commits(commits)
        markdown = self._render(version, sections, from_ref, to_ref, len(commits))

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            logger.info("Changelog written to %s", output_path)

        return markdown

    def generate_for_dataset(
        self,
        dataset_id: str,
        dataset_dir: Optional[Path] = None,
        from_ref: str = "HEAD~20",
        to_ref: str = "HEAD",
        version: str = "Unreleased",
    ) -> str:
        """
        Generate a changelog filtered to commits relevant to a specific dataset.

        Filters commits whose messages or changed files reference the dataset_id.

        Parameters
        ----------
        dataset_id : str
            Dataset identifier to filter commits by.
        dataset_dir : Path, optional
            Path to the dataset directory (used for file-based filtering).
        from_ref, to_ref, version : see generate().

        Returns
        -------
        str
            Filtered markdown changelog.
        """
        commits = self._get_commits(from_ref, to_ref)

        if dataset_dir:
            filtered = self._filter_commits_by_files(commits, dataset_dir)
        else:
            filtered = [
                c for c in commits
                if dataset_id.lower() in c.subject.lower()
                or dataset_id.lower() in c.body.lower()
            ]

        if not filtered:
            logger.warning(
                "No commits found related to dataset %s between %s and %s",
                dataset_id,
                from_ref,
                to_ref,
            )

        sections = self._classify_commits(filtered)
        return self._render(
            f"{version} ({dataset_id})", sections, from_ref, to_ref, len(filtered)
        )

    # ── Git Operations ──────────────────────────────────────────

    def _get_commits(self, from_ref: str, to_ref: str) -> List[CommitEntry]:
        """Fetch and parse git log between two refs."""
        # Use a format string that separates fields with special markers
        fmt = (
            "%H%n%h%n%s%n%b%n%an%n%aI%n%D%n---COMMIT_SEP---"
        )
        cmd = [
            "git", "log", f"{from_ref}..{to_ref}",
            f"--format={fmt}",
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.error("Failed to run git log: %s", exc)
            return []

        if result.returncode != 0:
            logger.error("git log returned non-zero: %s", result.stderr.strip())
            return []

        commits: List[CommitEntry] = []
        raw = result.stdout.strip()

        if not raw:
            logger.info("No commits found between %s and %s", from_ref, to_ref)
            return []

        for block in raw.split("---COMMIT_SEP---"):
            block = block.strip()
            if not block:
                continue

            lines = block.split("\n", 6)
            if len(lines) < 6:
                continue

            hash_val = lines[0].strip()
            short_hash = lines[1].strip()
            subject = lines[2].strip()
            body = lines[3].strip() if len(lines) > 3 else ""
            author = lines[4].strip() if len(lines) > 4 else ""
            date = lines[5].strip() if len(lines) > 5 else ""
            refs_raw = lines[6].strip() if len(lines) > 6 else ""

            # Parse refs (tag:, HEAD -> branch, etc.)
            refs = []
            if refs_raw:
                for part in refs_raw.split(", "):
                    part = part.strip().strip("-> ").strip()
                    if part and part != "HEAD":
                        refs.append(part)

            commits.append(CommitEntry(
                hash=hash_val,
                short_hash=short_hash,
                subject=subject,
                body=body,
                author=author,
                date=date,
                refs=refs,
            ))

        logger.debug("Parsed %d commits from git log", len(commits))
        return commits

    def _filter_commits_by_files(
        self, commits: List[CommitEntry], dataset_dir: Path
    ) -> List[CommitEntry]:
        """Filter commits that touch files within the given directory."""
        filtered = []
        dir_str = str(dataset_dir)

        for commit in commits:
            cmd = [
                "git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit.hash,
            ]
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and dir_str in result.stdout:
                    filtered.append(commit)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return filtered

    # ── Classification ──────────────────────────────────────────

    def _classify_commits(
        self, commits: List[CommitEntry]
    ) -> Dict[str, ChangelogSection]:
        """Classify commit messages into changelog sections."""
        sections: Dict[str, ChangelogSection] = {
            title: ChangelogSection(title=title) for title in SECTION_ORDER
        }

        for commit in commits:
            section_title = self._classify_single_commit(commit)
            if section_title not in sections:
                sections[section_title] = ChangelogSection(title=section_title)

            entry = self._format_commit_entry(commit)
            sections[section_title].entries.append(entry)

        # Remove empty sections
        return {k: v for k, v in sections.items() if v.entries}

    def _classify_single_commit(self, commit: CommitEntry) -> str:
        """Classify a single commit into a changelog section."""
        text = (commit.subject + " " + commit.body).lower()

        # Score each section by keyword matches
        best_section = FALLBACK_SECTION
        best_score = 0

        for section, keywords in SECTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_section = section

        return best_section

    def _format_commit_entry(self, commit: CommitEntry) -> str:
        """Format a commit as a markdown changelog entry."""
        # Extract issue references (#123, GH-456)
        issues = re.findall(r"(?:#|GH-|gh-)(\d+)", commit.subject + " " + commit.body)
        issue_links = ""
        if issues:
            links = ", ".join(f"#{num}" for num in issues)
            issue_links = f" ({links})"

        # Create commit hash link if remote URL is known
        if self.remote_url:
            commit_link = f"[`{commit.short_hash}`]({self.remote_url}/commit/{commit.hash})"
        else:
            commit_link = f"`{commit.short_hash}`"

        return f"- {commit.subject} {commit_link}{issue_links}"

    # ── Rendering ───────────────────────────────────────────────

    def _render(
        self,
        version: str,
        sections: Dict[str, ChangelogSection],
        from_ref: str,
        to_ref: str,
        commit_count: int,
    ) -> str:
        """Render the final markdown changelog from classified sections."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Build section blocks (only non-empty sections)
        section_blocks = []
        for title in SECTION_ORDER:
            sec = sections.get(title)
            if sec and sec.entries:
                entries_text = "\n".join(sec.entries)
                block = self.SECTION_TEMPLATE.format(
                    title=title,
                    entries=entries_text,
                ).rstrip()
                section_blocks.append(block)

        # Add any extra sections not in the standard order
        for title, sec in sections.items():
            if title not in SECTION_ORDER and sec.entries:
                entries_text = "\n".join(sec.entries)
                block = self.SECTION_TEMPLATE.format(
                    title=title,
                    entries=entries_text,
                ).rstrip()
                section_blocks.append(block)

        if not section_blocks:
            sections_text = "_No changes found in this range._"
        else:
            sections_text = "\n\n".join(section_blocks)

        return self.TEMPLATE.format(
            version=version,
            date=today,
            sections=sections_text,
            commit_count=commit_count,
            from_ref=from_ref,
            to_ref=to_ref,
        )

    # ── Helpers ─────────────────────────────────────────────────

    def _detect_remote_url(self) -> Optional[str]:
        """Try to detect the GitHub remote URL from git config."""
        cmd = ["git", "remote", "get-url", "origin"]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Convert SSH to HTTPS for linking
                url = re.sub(
                    r"git@([^:]+):(.+?)(\.git)?$",
                    r"https://\1/\2",
                    url,
                )
                # Remove trailing .git
                url = re.sub(r"\.git$", "", url)
                logger.debug("Detected remote URL: %s", url)
                return url
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None