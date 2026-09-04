# src/integrations/calibre_manager.py
"""
Safe wrapper around the Calibre `calibredb` CLI for managing a medical
e-book library.

Design constraints:
  * Never invoke a shell. All subprocess calls use argument lists.
  * Never pass user input verbatim into query strings. Free-text fields
    (title, authors, tags, specialty) are validated against a strict
    allowlist regex before being forwarded to calibredb.
  * Fail closed: any calibredb failure raises :class:`CalibreError`.
  * No network access. Calibre must already be installed on the host.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence


# Conservative allowlist for fields passed through to calibredb.
# Allows Latin/Arabic letters, digits, spaces, dashes, underscores, dots,
# commas (for multi-author), and parentheses (for disambiguation).
SAFE_TEXT_RE = re.compile(r"^[\w\u0600-\u06FF\s\-.,()]+$")


class CalibreError(RuntimeError):
    """Raised when the calibredb CLI fails or is unavailable."""


class CalibreManager:
    """Manager around a Calibre library exposed via the ``calibredb`` CLI."""

    def __init__(
        self,
        library_path: str | Path,
        calibredb_executable: str = "calibredb",
        timeout: int = 120,
    ) -> None:
        self.library_path = Path(library_path).expanduser().resolve()
        self.calibredb = calibredb_executable
        self.timeout = timeout

        if not self.library_path.is_dir():
            raise FileNotFoundError(
                f"Calibre library path does not exist: {self.library_path}"
            )

    # ── Low-level subprocess wrapper ──────────────────────────────────────

    def _run(self, args: Sequence[str]) -> str:
        cmd = [str(self.calibredb), *args]
        try:
            proc = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.CalledProcessError as exc:
            raise CalibreError(
                f"calibredb failed: {exc.stderr.strip() or exc.stdout.strip()}"
            ) from exc
        except FileNotFoundError as exc:
            raise CalibreError(
                "calibredb executable not found. Install Calibre first."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CalibreError("calibredb timed out") from exc
        return proc.stdout

    # ── Public API ────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            self._run(["--version"])
            return True
        except CalibreError:
            return False

    def search_ids(self, query: str) -> List[int]:
        """Return the list of integer book IDs matching a Calibre search query."""
        query = query.strip()
        if not query:
            return []
        out = self._run(
            [
                "search",
                "--library-path",
                str(self.library_path),
                query,
            ]
        )
        ids: List[int] = []
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                ids.append(int(line))
        return ids

    def list_books(self, ids: Optional[List[int]] = None) -> List[Dict]:
        """List books in JSON form, optionally filtered by IDs."""
        args: List[str] = [
            "list",
            "--library-path",
            str(self.library_path),
            "--for-machine",
            "--fields",
            "id,title,authors,tags",
        ]
        if ids:
            args.extend(["--ids", ",".join(str(book_id) for book_id in ids)])
        out = self._run(args)
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return data
        return []

    def search_by_specialty(self, specialty: str) -> List[Dict]:
        """Search books tagged ``specialty:<name>``.

        Validates the specialty against a strict allowlist so user input can
        never be used to inject arbitrary Calibre search syntax.
        """
        specialty = specialty.strip()
        if not specialty:
            raise ValueError("Specialty must not be empty")
        if not SAFE_TEXT_RE.match(specialty):
            raise ValueError("Specialty contains unsafe characters")
        query = f'tags:"specialty:{specialty}"'
        ids = self.search_ids(query)
        if not ids:
            return []
        return self.list_books(ids)

    def add_book(
        self,
        file_path: str | Path,
        title: Optional[str] = None,
        authors: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> str:
        """Add a file to the Calibre library. Returns calibredb stdout."""
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File does not exist: {path}")

        args: List[str] = [
            "add",
            "-1",
            "--library-path",
            str(self.library_path),
        ]

        if title:
            if not SAFE_TEXT_RE.match(title):
                raise ValueError("Title contains unsafe characters")
            args.extend(["--title", title])
        if authors:
            if not SAFE_TEXT_RE.match(authors):
                raise ValueError("Authors contain unsafe characters")
            args.extend(["--authors", authors])
        if tags:
            if not SAFE_TEXT_RE.match(tags):
                raise ValueError("Tags contain unsafe characters")
            args.extend(["--tags", tags])

        args.append(str(path))
        return self._run(args)
