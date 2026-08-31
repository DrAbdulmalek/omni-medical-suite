#!/usr/bin/env python3
"""
Tests for export_project_snapshot.py — Security-hardened test suite

Covers:
  - Basic file generation and manifest
  - Git metadata detection
  - Security: .env exclusion, .pem exclusion, secret redaction, secret regression
  - Binary file exclusion, oversized file exclusion
  - Scope selection (tracked, selected)
  - SecretScanner: HF_TOKEN, private key block, code structure preservation
  - Symlink escape prevention (outside symlinks never read)
  - Path traversal prevention (../ never read)
  - Fail-closed scope semantics (tracked/diff fail if git unavailable)
  - Normal hashes/identifiers NOT redacted (false positive prevention)
  - Explicit --base-ref / --base-sha for diff scope
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_project_snapshot import (
    SnapshotGenerator,
    FileCollector,
    FileFilter,
    SecretScanner,
    GitMeta,
    run_git,
    _is_within_directory,
    _safe_resolve,
)


class TestBasic(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        root = Path(self.tmpdir)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("print('hello')\n")
        (root / "README.md").write_text("# Project\n")
        self.output = root / "snapshot.txt"
        self.gen = SnapshotGenerator(
            root=root,
            output=self.output,
            scope="full",
            purpose="Unit test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        self.gen.generate()
        self.content = self.output.read_text(encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_file_created(self):
        self.assertTrue(self.output.exists())

    def test_contains_manifest(self):
        self.assertIn("PROJECT MANIFEST", self.content)
        self.assertIn("INCLUDED FILES", self.content)
        self.assertIn("EXCLUDED FILES", self.content)

    def test_contains_file_content(self):
        self.assertIn("FILE: README.md", self.content)
        self.assertIn("# Project", self.content)
        self.assertIn("FILE: src/app.py", self.content)

    def test_deterministic_ordering(self):
        lines = self.content.splitlines()
        files = []
        in_included = False
        for line in lines:
            if line.startswith("INCLUDED FILES"):
                in_included = True
                continue
            if in_included:
                if line.startswith("-") or line.strip() == "" or line.startswith("EXCLUDED"):
                    break
                if line[0].isdigit():
                    files.append(line.split(" ", 1)[1].strip())
        self.assertEqual(files, sorted(files))


class TestGitMeta(unittest.TestCase):
    def setUp(self):
        self.meta = GitMeta(PROJECT_ROOT)

    def test_branch_detected(self):
        if self.meta.available:
            self.assertNotEqual(self.meta.branch, "UNAVAILABLE")

    def test_sha_detected(self):
        if self.meta.available:
            self.assertNotEqual(self.meta.head, "UNAVAILABLE")
            self.assertEqual(len(self.meta.head), 40)

    def test_not_crash_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = GitMeta(Path(tmp))
            self.assertFalse(meta.available)
            self.assertEqual(meta.branch, "UNAVAILABLE")

    def test_explicit_base_ref(self):
        """--base-ref should be used for diff base."""
        # Use a ref that definitely exists in the repo
        meta = GitMeta(PROJECT_ROOT, base_ref="HEAD")
        self.assertEqual(meta.base_ref, "HEAD")

    def test_explicit_base_sha(self):
        """--base-sha should take precedence over --base-ref."""
        # Use a real SHA from the repo so verification passes
        _, real_sha, _ = run_git(["rev-parse", "HEAD"], PROJECT_ROOT)
        meta = GitMeta(PROJECT_ROOT, base_ref="main", base_sha=real_sha)
        self.assertEqual(meta.base_sha, real_sha)
        # get_diff_base should return base_sha first
        self.assertEqual(meta.get_diff_base(), real_sha)


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        root = Path(self.tmpdir)
        (root / "src").mkdir()
        (root / "src" / "config.py").write_text(
            'HF_TOKEN = "hf_REAL_SECRET_99999_abcdefghij"\n'
            'OPENAI_API_KEY = "sk-fakeopenaikey1234567890"\n'
            'DB_URL = "postgresql://admin:RealPassword123@db.local:5432/medical"\n'
            'AWS_SECRET_ACCESS_KEY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"\n'
        )
        (root / ".env").write_text("SECRET=hidden\n")
        (root / "key.pem").write_text(
            "-----BEGIN RSA PRIVATE KEY-----\nxxx\n-----END RSA PRIVATE KEY-----\n"
        )
        self.output = root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=root,
            output=self.output,
            scope="full",
            purpose="Security test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        gen.generate()
        self.content = self.output.read_text(encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_env_excluded(self):
        self.assertNotIn("FILE: .env", self.content)
        self.assertIn(".env (sensitive file)", self.content)

    def test_pem_excluded(self):
        self.assertNotIn("FILE: key.pem", self.content)
        self.assertIn("key.pem (sensitive file)", self.content)

    def test_hf_token_redacted(self):
        self.assertNotIn("hf_REAL_SECRET_99999_abcdefghij", self.content)
        self.assertIn("[REDACTED:", self.content)

    def test_openai_key_redacted(self):
        self.assertNotIn("sk-fakeopenaikey1234567890", self.content)

    def test_db_password_redacted(self):
        self.assertNotIn("RealPassword123", self.content)
        self.assertIn("[REDACTED: DB PASSWORD]", self.content)

    def test_aws_secret_redacted(self):
        self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd", self.content)
        self.assertIn("[REDACTED: AWS_SECRET_KEY]", self.content)

    def test_secret_regression(self):
        """The real secret values must never appear in the output."""
        self.assertNotIn("hf_REAL_SECRET_99999_abcdefghij", self.content)
        self.assertNotIn("RealPassword123", self.content)
        self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd", self.content)


class TestBinaryAndSize(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        root = Path(self.tmpdir)
        (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        (root / "huge.txt").write_text("x" * 200_000)
        self.output = root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=root,
            output=self.output,
            scope="full",            purpose="Binary test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        gen.generate()
        self.content = self.output.read_text(encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_binary_png_excluded(self):
        self.assertNotIn("FILE: logo.png", self.content)
        self.assertTrue(
            "logo.png (binary file)" in self.content or "logo.png (excluded extension)" in self.content
        )

    def test_oversized_file_excluded(self):
        self.assertNotIn("FILE: huge.txt", self.content)
        self.assertIn("huge.txt (exceeds max-file-size)", self.content)


class TestScopes(unittest.TestCase):
    def _run_scope(self, scope, include=None, **kwargs):
        output = PROJECT_ROOT / f"test_snapshot_{scope}_{os.getpid()}.txt"
        gen = SnapshotGenerator(
            root=PROJECT_ROOT,
            output=output,
            scope=scope,
            purpose="Scope test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
            **kwargs,
        )
        if include:
            gen.collector.include = include
        gen.generate()
        content = output.read_text(encoding="utf-8")
        output.unlink()
        return content

    def test_tracked_includes_git_files(self):
        content = self._run_scope("tracked")
        self.assertIn("FILE:", content)
        self.assertIn("PROJECT MANIFEST", content)

    def test_selected_scope(self):
        content = self._run_scope("selected", include=["tools/export_project_snapshot.py"])
        self.assertIn("FILE: tools/export_project_snapshot.py", content)


class TestSecretScanner(unittest.TestCase):
    def test_redacts_hf_token(self):
        scanner = SecretScanner()
        text = 'HF_TOKEN = "hf_abc123xyz999999999qwerty"'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertNotIn("hf_abc123xyz999999999qwerty", result)
        self.assertIn("[REDACTED:", result)

    def test_redacts_private_key_block(self):
        scanner = SecretScanner()
        text = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"
        result = scanner.scan_and_redact(text, "test.pem")
        self.assertNotIn("abc", result)
        self.assertIn("[REDACTED: PRIVATE KEY BLOCK START]", result)

    def test_preserves_code_structure(self):
        scanner = SecretScanner()
        text = 'API_KEY = "secret123"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertIn('[REDACTED: POSSIBLE SECRET]', result)

    def test_does_not_redact_sha256_hash(self):
        """SHA256 hashes must NOT be redacted — they are not secrets."""
        scanner = SecretScanner()
        sha = "a" * 64  # 64-char hex string (SHA256)
        text = f'file_hash = "{sha}"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertIn(sha, result)

    def test_does_not_redact_normal_long_identifier(self):
        """Normal long identifiers must NOT be redacted."""
        scanner = SecretScanner()
        ident = "abcdefghijklmnopqrstuv"  # 22 chars, no prefix
        text = f'project_id = "{ident}"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertIn(ident, result)

    def test_does_not_redact_normal_base64_string(self):
        """Standalone base64-like strings without context must NOT be redacted."""
        scanner = SecretScanner()
        b64 = "SGVsbG8gV29ybGQ="  # "Hello World" in base64
        text = f'data = "{b64}"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertIn(b64, result)

    def test_redacts_aws_secret_access_key_contextual(self):
        """AWS_SECRET_ACCESS_KEY in assignment context must be redacted."""
        scanner = SecretScanner()
        secret = "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"  # 40 chars
        text = f'AWS_SECRET_ACCESS_KEY = "{secret}"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertNotIn(secret, result)

    def test_redacts_anthropic_key(self):
        """Anthropic API keys must be redacted."""
        scanner = SecretScanner()
        key = "sk-ant-api03-1234567890abcdefghijklmnopqrst"
        text = f'ANTHROPIC_KEY = "{key}"\n'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertNotIn(key, result)


# ---------------------------------------------------------------------------
# Symlink Escape Prevention
# ---------------------------------------------------------------------------

class TestSymlinkEscape(unittest.TestCase):
    """Verify that symlinks pointing outside the repo are never read."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir) / "repo"
        self.root.mkdir()
        (self.root / "safe.txt").write_text("safe content\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_outside_symlink_not_exported(self):
        """Symlink pointing to /tmp must never be read."""
        outside = Path(self.tmpdir) / "outside_secret.txt"
        outside.write_text("TOP_SECRET\n")
        link = self.root / "evil_link.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Cannot create symlinks on this platform")

        output = self.root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=self.root,
            output=output,
            scope="full",
            purpose="Symlink test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        gen.generate()
        content = output.read_text(encoding="utf-8")

        self.assertIn("FILE: safe.txt", content)
        self.assertNotIn("TOP_SECRET", content)
        self.assertNotIn("FILE: evil_link.txt", content)

    def test_inside_symlink_exported(self):
        """Symlink pointing to a file inside the repo IS exported."""
        link = self.root / "inside_link.txt"
        try:
            link.symlink_to(self.root / "safe.txt")
        except OSError:
            self.skipTest("Cannot create symlinks on this platform")

        output = self.root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=self.root,
            output=output,
            scope="full",
            purpose="Symlink test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        gen.generate()
        content = output.read_text(encoding="utf-8")

        # The symlink target content should be accessible (via the symlink)
        self.assertIn("safe content", content)

    def test_nested_symlink_chain_escape(self):
        """Nested symlink chain pointing outside must not be read."""
        outside = Path(self.tmpdir) / "nested_secret.txt"
        outside.write_text("NESTED_SECRET\n")
        link1 = self.root / "link1.txt"
        link2 = self.root / "link2.txt"
        try:
            link2.symlink_to(outside)
            link1.symlink_to(link2)
        except OSError:
            self.skipTest("Cannot create symlinks on this platform")

        output = self.root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=self.root,
            output=output,
            scope="full",
            purpose="Nested symlink test",
            with_prompt=False,            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        gen.generate()
        content = output.read_text(encoding="utf-8")

        self.assertNotIn("NESTED_SECRET", content)


# ---------------------------------------------------------------------------
# Path Traversal Prevention
# ---------------------------------------------------------------------------

class TestPathTraversal(unittest.TestCase):
    """Verify that ../ and absolute paths outside root are never read."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir) / "repo"
        self.root.mkdir()
        (self.root / "safe.txt").write_text("safe\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dotdot_traversal_not_exported(self):
        """../secret.txt must never be read via selected scope."""
        outside = Path(self.tmpdir) / "outside_secret.txt"
        outside.write_text("TRAVERSAL_SECRET\n")

        output = self.root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=self.root,
            output=output,
            scope="selected",
            purpose="Traversal test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
            include=["../outside_secret.txt"],
        )
        gen.generate()
        content = output.read_text(encoding="utf-8")

        self.assertNotIn("TRAVERSAL_SECRET", content)

    def test_absolute_outside_path_not_exported(self):
        """Absolute path outside root must never be read."""
        outside = Path(self.tmpdir) / "abs_secret.txt"
        outside.write_text("ABS_SECRET\n")

        output = self.root / "snapshot.txt"
        gen = SnapshotGenerator(
            root=self.root,
            output=output,
            scope="selected",
            purpose="Absolute path test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
            include=[str(outside)],
        )
        gen.generate()
        content = output.read_text(encoding="utf-8")

        self.assertNotIn("ABS_SECRET", content)


# ---------------------------------------------------------------------------
# Fail-Closed Scope Semantics
# ---------------------------------------------------------------------------

class TestFailClosedScopes(unittest.TestCase):
    """Verify that Git scope failures cause explicit errors, not silent fallback."""

    def test_tracked_fails_without_git(self):
        """--scope tracked in a non-Git directory must raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("test\n")
            output = root / "snapshot.txt"

            with self.assertRaises(RuntimeError) as ctx:
                gen = SnapshotGenerator(
                    root=root,
                    output=output,
                    scope="tracked",
                    purpose="Fail test",
                    with_prompt=False,
                    max_file_size=100_000,
                    max_total_size=10_000_000,
                )
                gen.generate()
            self.assertIn("Git", str(ctx.exception))

    def test_diff_fails_without_git(self):
        """--scope diff in a non-Git directory must raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("test\n")
            output = root / "snapshot.txt"

            with self.assertRaises(RuntimeError) as ctx:
                gen = SnapshotGenerator(
                    root=root,
                    output=output,
                    scope="diff",
                    purpose="Fail test",
                    with_prompt=False,
                    max_file_size=100_000,
                    max_total_size=10_000_000,
                )
                gen.generate()
            self.assertIn("Git", str(ctx.exception))

    def test_tracked_fails_on_git_ls_files_error(self):
        """If git ls-files fails, tracked scope must raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("test\n")
            output = root / "snapshot.txt"

            # Initialize git so GitMeta thinks it's available, then make ls-files fail
            os.system(f"git init {tmp} > /dev/null 2>&1")

            with patch("tools.export_project_snapshot.run_git") as mock_git:
                # First call: rev-parse --git-dir (success to make available=True)
                # Then: ls-files (fail)
                mock_git.side_effect = [
                    (0, ".git", ""),  # rev-parse --git-dir
                    (0, "main", ""),  # rev-parse --abbrev-ref HEAD
                    (0, "abc123", ""),  # rev-parse HEAD
                    (0, "1", ""),  # rev-list --count
                    (0, "", ""),  # status --porcelain
                    (0, "", ""),  # rev-parse --verify main
                    (1, "", "fatal: not a git repository"),  # ls-files fails
                ]

                with self.assertRaises(RuntimeError) as ctx:
                    gen = SnapshotGenerator(
                        root=root,
                        output=output,
                        scope="tracked",
                        purpose="Fail test",
                        with_prompt=False,
                        max_file_size=100_000,
                        max_total_size=10_000_000,
                    )
                    gen.generate()
                self.assertIn("ls-files", str(ctx.exception).lower())

    def test_diff_fails_on_git_diff_error(self):
        """If git diff fails, diff scope must raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("test\n")
            output = root / "snapshot.txt"

            os.system(f"git init {tmp} > /dev/null 2>&1")
            os.system(f"git -C {tmp} add -A > /dev/null 2>&1")
            os.system(f"git -C {tmp} commit -m init > /dev/null 2>&1")

            with patch("tools.export_project_snapshot.run_git") as mock_git:
                mock_git.side_effect = [
                    (0, ".git", ""),  # rev-parse --git-dir
                    (0, "main", ""),  # rev-parse --abbrev-ref HEAD
                    (0, "abc123", ""),  # rev-parse HEAD
                    (0, "1", ""),  # rev-list --count
                    (0, "", ""),  # status --porcelain
                    (0, "", ""),  # rev-parse --verify main
                    (1, "", "fatal: bad revision"),  # diff fails
                    (1, "", "fatal: bad revision"),  # fallback diff also fails
                ]

                with self.assertRaises(RuntimeError) as ctx:
                    gen = SnapshotGenerator(
                        root=root,
                        output=output,
                        scope="diff",
                        purpose="Fail test",
                        with_prompt=False,
                        max_file_size=100_000,
                        max_total_size=10_000_000,
                    )
                    gen.generate()
                self.assertIn("diff", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# Containment Utility Tests
# ---------------------------------------------------------------------------

class TestContainment(unittest.TestCase):
    """Test _is_within_directory and _safe_resolve directly."""

    def test_path_inside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "subdir" / "file.txt"
            target.parent.mkdir()            target.touch()
            self.assertTrue(_is_within_directory(root, target))

    def test_path_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret")
            self.assertFalse(_is_within_directory(root, outside))

    def test_safe_resolve_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "file.txt"
            target.write_text("ok")
            resolved = _safe_resolve(target, root)
            self.assertIsNotNone(resolved)
            self.assertTrue(resolved.is_file())

    def test_safe_resolve_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret")
            resolved = _safe_resolve(outside, root)
            self.assertIsNone(resolved)

    def test_safe_resolve_symlink_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret")
            link = root / "link.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("Cannot create symlinks")
            resolved = _safe_resolve(link, root)
            self.assertIsNone(resolved)




# ---------------------------------------------------------------------------
# Regression: strict selected and diff semantics
# ---------------------------------------------------------------------------

class TestStrictScopeAndDiffSemantics(unittest.TestCase):
    def test_selected_without_include_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "safe.txt").write_text("safe\n")
            with self.assertRaisesRegex(RuntimeError, "requires --include"):
                FileCollector(root, "selected", None, GitMeta(root)).collect()

    def test_selected_empty_include_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "safe.txt").write_text("safe\n")
            with self.assertRaisesRegex(RuntimeError, "requires --include"):
                FileCollector(root, "selected", [], GitMeta(root)).collect()

    def test_invalid_explicit_base_ref_does_not_autodetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.export_project_snapshot.run_git") as mock_git:
                mock_git.side_effect=[(0,".git",""),(0,"main",""),(0,"a"*40,""),(0,"1",""),(0,"",""),(1,"","bad ref")]
                meta=GitMeta(Path(tmp), base_ref="missing")
            self.assertIsNone(meta.get_diff_base())
            self.assertTrue(meta._explicit_base_invalid)

    def test_invalid_explicit_base_sha_does_not_autodetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.export_project_snapshot.run_git") as mock_git:
                mock_git.side_effect=[(0,".git",""),(0,"main",""),(0,"a"*40,""),(0,"1",""),(0,"",""),(1,"","bad sha")]
                meta=GitMeta(Path(tmp), base_sha="deadbeef")
            self.assertIsNone(meta.get_diff_base())
            self.assertTrue(meta._explicit_base_invalid)

    def test_three_dot_diff_failure_never_falls_back_to_two_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            meta=MagicMock()
            meta.get_diff_base.return_value="main"
            collector=FileCollector(root,"diff",None,meta)
            with patch("tools.export_project_snapshot.run_git", return_value=(1,"","no merge base")) as mock_git:
                with self.assertRaisesRegex(RuntimeError,"Three-dot diff is required"):
                    collector._collect_diff()
            self.assertEqual(mock_git.call_count,1)
            self.assertEqual(mock_git.call_args.args[0],["diff","--name-only","main...HEAD"])

if __name__ == "__main__":
    unittest.main(verbosity=2)