#!/usr/bin/env python3
"""
Gemini Project Snapshot Exporter

تولد ملف نصي واحد يحتوي على محتوى المشروع الآمن
للرفع إلى Gemini أو أي LLM آخر لمراجعة الكود.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# الإعدادات الافتراضية
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT = "gemini_project_snapshot.txt"
DEFAULT_MAX_FILE_SIZE = 100 * 1024       # 100 KB
DEFAULT_MAX_TOTAL_SIZE = 2 * 1024 * 1024  # 2 MB

EXCLUDED_DIRS = {
    ".git",
    ".github" + os.sep + "secrets",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "coverage",
    "htmlcov",
}

EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".7z",
    ".mp3", ".mp4", ".mov",
    ".woff", ".woff2", ".ttf", ".otf",
    ".so", ".dll", ".exe", ".bin",
    ".db", ".sqlite", ".sqlite3",
}

SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "service-account.json", "secrets.json",
}

SENSITIVE_FILENAME_SUFFIXES = (
    ".pem", ".key", ".p12", ".pfx", ".crt", ".cer",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
)

# ---------------------------------------------------------------------------
# Secret Patterns
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    # Hugging Face
    (re.compile(r'\b(hf_[A-Za-z0-9_]{8,})\b'), "HF_TOKEN"),
    # OpenAI
    (re.compile(r'\b(sk-[A-Za-z0-9]{8,})\b'), "OPENAI_API_KEY"),
    # GitHub personal access token
    (re.compile(r'\b(ghp_[A-Za-z0-9]{20,})\b'), "GITHUB_TOKEN"),
    # AWS Access Key ID
    (re.compile(r'\b(AKIA[0-9A-Z]{16})\b'), "AWS_KEY"),
    # AWS Secret Key
    (re.compile(r'\b([A-Za-z0-9/+=]{16,})\b'), "AWS_SECRET"),
    # JWT
    (re.compile(r'\b(eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*)\b'), "JWT"),
    # Generic high-entropy assignment
    (re.compile(r'(?i)(\b(?:api_key|token|secret|password)\s*[=:]\s*)["\']?[A-Za-z0-9_\-]{8,}["\']?'), "ASSIGNMENT"),
    # Database URL with credentials
    (re.compile(r'((?:postgresql|mysql|mongodb|redis)://[^:]+:)([^@]+)(@)'), "DB_URL"),
    # Bearer token
    (re.compile(r'\b(Bearer\s+[A-Za-z0-9_\-\.]+)\b'), "BEARER"),
]

PRIVATE_KEY_START = re.compile(r'-----BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----')
PRIVATE_KEY_END = re.compile(r'-----END (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----')


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def sha256_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def is_binary(path: Path) -> bool:
    """يحاول قراءة أول 1024 بايت كـ UTF-8؛ إذا فشل أو وجد \x00 يعتبره ثنائي."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        if b"\x00" in chunk:
            return True
        chunk.decode("utf-8")
        return False
    except (UnicodeDecodeError, OSError):
        return True


def run_git(cmd: List[str], cwd: Path) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return -1, "", "git not available"


# ---------------------------------------------------------------------------
# Git Metadata
# ---------------------------------------------------------------------------
class GitMeta:
    def __init__(self, cwd: Path):
        self.available = False
        self.branch = "UNAVAILABLE"
        self.head = "UNAVAILABLE"
        self.base_branch = "UNAVAILABLE"
        self.dirty = False
        self.commit_count = 0

        rc, _, _ = run_git(["rev-parse", "--git-dir"], cwd)
        if rc != 0:
            return

        self.available = True
        _, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
        self.branch = out or "UNAVAILABLE"

        _, out, _ = run_git(["rev-parse", "HEAD"], cwd)
        self.head = out or "UNAVAILABLE"

        _, out, _ = run_git(["rev-list", "--count", "HEAD"], cwd)
        try:
            self.commit_count = int(out)
        except ValueError:
            self.commit_count = 0

        _, out, _ = run_git(["status", "--porcelain"], cwd)
        self.dirty = bool(out)

        for candidate in ("main", "master"):
            rc, _, _ = run_git(["rev-parse", "--verify", candidate], cwd)
            if rc == 0:
                self.base_branch = candidate
                break


# ---------------------------------------------------------------------------
# File Collector
# ---------------------------------------------------------------------------
class FileCollector:
    def __init__(self, root: Path, scope: str, include: Optional[List[str]], git_meta: GitMeta):
        self.root = root.resolve()
        self.scope = scope
        self.include = include
        self.git_meta = git_meta
        self.files: List[Path] = []

    def collect(self) -> List[Path]:
        if self.scope == "selected" and self.include:
            self.files = self._collect_selected()
        elif self.scope == "tracked" and self.git_meta.available:
            self.files = self._collect_tracked()
        elif self.scope == "diff" and self.git_meta.available:
            self.files = self._collect_diff()
        else:
            self.files = self._collect_full()

        self.files = sorted(self.files, key=lambda p: str(p).replace(os.sep, "/"))
        return self.files

    def _collect_full(self) -> List[Path]:
        files = []
        for p in self.root.rglob("*"):
            if p.is_file():
                files.append(p)
        return files

    def _collect_tracked(self) -> List[Path]:
        rc, out, _ = run_git(["ls-files", "-z"], self.root)
        if rc != 0:
            return self._collect_full()
        files = []
        for name in out.split("\x00"):
            if name:
                files.append(self.root / name)
        return files

    def _collect_diff(self) -> List[Path]:
        base = self.git_meta.base_branch
        if base == "UNAVAILABLE":
            return self._collect_tracked()
        rc, out, _ = run_git(["diff", "--name-only", f"{base}...HEAD"], self.root)
        if rc != 0:
            rc, out, _ = run_git(["diff", "--name-only", base, "HEAD"], self.root)
        if rc != 0:
            return self._collect_tracked()
        files = []
        for name in out.splitlines():
            if name:
                files.append(self.root / name)
        return files

    def _collect_selected(self) -> List[Path]:
        files = []
        for pattern in self.include:
            target = self.root / pattern
            if target.is_file():
                files.append(target)
            elif target.is_dir():
                for p in target.rglob("*"):
                    if p.is_file():
                        files.append(p)
            else:
                for p in self.root.glob(pattern):
                    if p.is_file():
                        files.append(p)
        return files


# ---------------------------------------------------------------------------
# File Filter
# ---------------------------------------------------------------------------
class FileFilter:
    def __init__(self, root: Path, max_file_size: int):
        self.root = root
        self.max_file_size = max_file_size
        self.excluded: List[Tuple[str, str]] = []

    def filter(self, files: List[Path]) -> List[Path]:
        included = []
        for f in files:
            rel = f.relative_to(self.root).as_posix()
            reason = self._exclude_reason(f, rel)
            if reason:
                self.excluded.append((rel, reason))
            else:
                included.append(f)
        return included

    def _exclude_reason(self, path: Path, rel: str) -> Optional[str]:
        name = path.name
        if name in SENSITIVE_FILENAMES:
            return "sensitive file"
        if name.startswith("id_") or name.endswith(SENSITIVE_FILENAME_SUFFIXES):
            return "sensitive file"

        parts = path.parts
        for part in parts:
            if part in EXCLUDED_DIRS:
                return "excluded directory"

        if path.suffix.lower() in EXCLUDED_EXTENSIONS:
            return "excluded extension"

        try:
            size = path.stat().st_size
            if size > self.max_file_size:
                return "exceeds max-file-size"
        except OSError:
            return "unreadable"

        if is_binary(path):
            return "binary file"

        return None


# ---------------------------------------------------------------------------
# Secret Scanner & Redactor
# ---------------------------------------------------------------------------
class SecretScanner:
    def __init__(self):
        self.redactions = 0

    def scan_and_redact(self, content: str, rel_path: str) -> str:
        lines = content.splitlines(keepends=True)
        out_lines = []
        in_private_key = False

        for line in lines:
            if PRIVATE_KEY_START.search(line):
                in_private_key = True
                out_lines.append("[REDACTED: PRIVATE KEY BLOCK START]\n")
                self.redactions += 1
                continue
            if in_private_key:
                if PRIVATE_KEY_END.search(line):
                    out_lines.append("[REDACTED: PRIVATE KEY BLOCK END]\n")
                    in_private_key = False
                continue

            original_line = line
            new_line = line
            for pattern, label in SECRET_PATTERNS:
                if label == "DB_URL":
                    new_line = pattern.sub(r'\1[REDACTED: DB PASSWORD]\3', new_line)
                elif label == "ASSIGNMENT":
                    def repl(m):
                        prefix = m.group(1)
                        return f'{prefix}"[REDACTED: POSSIBLE SECRET]"'
                    new_line = pattern.sub(repl, new_line)
                else:
                    new_line = pattern.sub(f'[REDACTED: {label}]', new_line)

            if new_line != original_line:
                self.redactions += 1
            out_lines.append(new_line)

        return "".join(out_lines)


# ---------------------------------------------------------------------------
# Snapshot Generator
# ---------------------------------------------------------------------------
class SnapshotGenerator:
    def __init__(
        self,
        root: Path,
        output: Path,
        scope: str,
        purpose: str,
        with_prompt: bool,
        max_file_size: int,
        max_total_size: int,
        include: Optional[List[str]] = None,
    ):
        self.root = root
        self.output = output
        self.scope = scope
        self.purpose = purpose
        self.with_prompt = with_prompt
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size
        self.git_meta = GitMeta(root)
        self.collector = FileCollector(root, scope, include, self.git_meta)
        self.file_filter = FileFilter(root, max_file_size)
        self.scanner = SecretScanner()
        self.total_bytes = 0
        self.redacted_count = 0
        self.file_records = []

    def generate(self) -> None:
        files = self.collector.collect()
        files = self.file_filter.filter(files)

        # Prepass: read, redact, compute hashes, enforce total size
        file_records = []
        running_total = 0
        for f in files:
            rel = f.relative_to(self.root).as_posix()
            try:
                raw = f.read_bytes()
            except OSError:
                self.file_filter.excluded.append((rel, "read error"))
                continue

            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                self.file_filter.excluded.append((rel, "unsupported encoding"))
                continue

            redacted_text = self.scanner.scan_and_redact(text, rel)
            sha = sha256_content(raw)
            size = len(raw)
            lang = self._detect_language(f)

            if running_total + size > self.max_total_size:
                self.file_filter.excluded.append((rel, "exceeds max-total-size"))
                continue

            running_total += size
            self.total_bytes += size
            file_records.append((f, lang, sha, size, redacted_text))

        self.file_records = file_records
        self.redacted_count = self.scanner.redactions

        with open(self.output, "w", encoding="utf-8") as out:
            self._write_header(out)
            self._write_manifest(out, file_records)
            if self.with_prompt:
                self._write_ai_prompt(out)
            self._write_files(out, file_records)
            self._write_footer(out)

        self._print_summary()

    def _write_header(self, out):
        out.write("=" * 80 + "\n")
        out.write("GEMINI PROJECT SNAPSHOT\n")
        out.write("=" * 80 + "\n\n")
        out.write(f"Repository: DrAbdulmalek/omni-medical-suite\n")
        out.write(f"Branch: {self.git_meta.branch}\n")
        out.write(f"HEAD: {self.git_meta.head}\n")
        out.write(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        out.write(f"Purpose: {self.purpose}\n")
        if self.git_meta.base_branch != "UNAVAILABLE":
            out.write(f"Base comparison: {self.git_meta.base_branch}\n")
        else:
            out.write("Base comparison: UNAVAILABLE\n")
        out.write("\n")

    def _write_manifest(self, out, file_records):
        out.write("=" * 80 + "\n")
        out.write("PROJECT MANIFEST\n")
        out.write("=" * 80 + "\n\n")
        out.write(f"Files included: {len(file_records)}\n")
        out.write(f"Files excluded: {len(self.file_filter.excluded)}\n")
        out.write(f"Files redacted: {self.redacted_count}\n")
        out.write(f"Total source bytes: {self.total_bytes}\n\n")

        out.write("-" * 80 + "\n")
        out.write("INCLUDED FILES\n")
        out.write("-" * 80 + "\n")
        for i, (f, *_rest) in enumerate(file_records, 1):
            rel = f.relative_to(self.root).as_posix()
            out.write(f"{i}. {rel}\n")
        out.write("\n")

        out.write("-" * 80 + "\n")
        out.write("EXCLUDED FILES\n")
        out.write("-" * 80 + "\n")
        for rel, reason in self.file_filter.excluded:
            out.write(f"{rel} ({reason})\n")
        out.write("\n")

    def _write_ai_prompt(self, out):
        out.write("=" * 80 + "\n")
        out.write("AI REVIEW CONTEXT\n")
        out.write("=" * 80 + "\n\n")
        out.write("This snapshot was generated automatically.\n\n")
        out.write("The AI reviewer must:\n")
        out.write("- inspect only supplied files;\n")
        out.write("- never assume unseen files;\n")
        out.write("- mark unsupported claims as UNVERIFIED;\n")
        out.write("- distinguish fail-closed from required branch protection;\n")
        out.write("- distinguish informational checks from gating checks;\n")
        out.write("- avoid proposing unrelated production changes.\n\n")

    def _write_files(self, out, file_records):
        out.write("=" * 80 + "\n")
        out.write("FILES\n")
        out.write("=" * 80 + "\n\n")

        for f, lang, sha, size, redacted_text in file_records:
            rel = f.relative_to(self.root).as_posix()
            out.write("=" * 80 + "\n")
            out.write(f"FILE: {rel}\n")
            out.write(f"LANGUAGE: {lang}\n")
            out.write(f"SIZE: {size}\n")
            out.write(f"SHA256: {sha}\n")
            out.write("=" * 80 + "\n\n")
            out.write(redacted_text)
            if not redacted_text.endswith("\n"):
                out.write("\n")
            out.write("\n")

    def _write_footer(self, out):
        out.write("=" * 80 + "\n")
        out.write("END OF SNAPSHOT\n")
        out.write("=" * 80 + "\n")

    def _detect_language(self, path: Path) -> str:
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
            ".sh": "bash",
            ".sql": "sql",
        }
        return mapping.get(path.suffix.lower(), "text")

    def _print_summary(self):
        print("\nGemini snapshot generated successfully.\n")
        print(f"Output:\n{self.output.resolve()}\n")
        print(f"Files included: {len(self.file_records)}")
        print(f"Files excluded: {len(self.file_filter.excluded)}")
        print(f"Files redacted: {self.redacted_count}")
        binary_excluded = sum(1 for _, r in self.file_filter.excluded if r == "binary file")
        print(f"Binary files excluded: {binary_excluded}")
        print(f"Total size: {self.total_bytes:,} bytes")
        if self.redacted_count > 0:
            print("\nWARNING: Sensitive values were redacted.")
            print("Review the manifest before uploading the snapshot.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate a single text snapshot of the project for LLM review."
    )
    parser.add_argument(
        "--output", "-o", default=DEFAULT_OUTPUT,
        help="Output file path (default: gemini_project_snapshot.txt)"
    )
    parser.add_argument(
        "--scope", choices=["full", "tracked", "selected", "diff"],
        default="tracked",
        help="Scope of files to include (default: tracked)"
    )
    parser.add_argument(
        "--include", nargs="+", default=None,
        help="Paths to include when scope=selected"
    )
    parser.add_argument(
        "--purpose", default="AI-assisted code review",
        help="Purpose string to embed in the snapshot"
    )
    parser.add_argument(
        "--with-prompt", action="store_true",
        help="Include AI review instructions in the snapshot"
    )
    parser.add_argument(
        "--max-file-size", type=int, default=DEFAULT_MAX_FILE_SIZE,
        help="Max bytes per file"
    )
    parser.add_argument(
        "--max-total-size", type=int, default=DEFAULT_MAX_TOTAL_SIZE,
        help="Max total bytes for the snapshot"
    )
    parser.add_argument(
        "--root", default=".",
        help="Project root directory"
    )

    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output)

    if args.scope == "selected" and not args.include:
        parser.error("--include is required when --scope=selected")

    gen = SnapshotGenerator(
        root=root,
        output=output,
        scope=args.scope,
        purpose=args.purpose,
        with_prompt=args.with_prompt,
        max_file_size=args.max_file_size,
        max_total_size=args.max_total_size,
        include=args.include,
    )
    gen.generate()


if __name__ == "__main__":
    main()
