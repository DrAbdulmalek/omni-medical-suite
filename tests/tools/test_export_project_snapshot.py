#!/usr/bin/env python3
"""
Tests for export_project_snapshot.py
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_project_snapshot import (
    SnapshotGenerator,
    FileCollector,
    FileFilter,
    SecretScanner,
    GitMeta,
    run_git,
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


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        root = Path(self.tmpdir)
        (root / "src").mkdir()
        (root / "src" / "config.py").write_text(
            'HF_TOKEN = "hf_REAL_SECRET_99999"\n'
            'OPENAI_API_KEY = "sk-fakeopenaikey12345"\n'
            'DB_URL = "postgresql://admin:RealPassword123@db.local:5432/medical"\n'
        )
        (root / ".env").write_text("SECRET=hidden\n")
        (root / "key.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\nxxx\n-----END RSA PRIVATE KEY-----\n")
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
        self.assertNotIn("hf_REAL_SECRET_99999", self.content)
        self.assertIn("[REDACTED:", self.content)

    def test_openai_key_redacted(self):
        self.assertNotIn("sk-fakeopenaikey12345", self.content)

    def test_db_password_redacted(self):
        self.assertNotIn("RealPassword123", self.content)
        self.assertIn("[REDACTED: DB PASSWORD]", self.content)

    def test_secret_regression(self):
        """الاختبار الحرج: القيمة السرية الحقيقية لا تظهر أبداً"""
        self.assertNotIn("hf_REAL_SECRET_99999", self.content)
        self.assertNotIn("RealPassword123", self.content)


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
            scope="full",
            purpose="Binary test",
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
        # يُستبعد إما لأنه ثنائي أو بسبب الامتداد
        self.assertTrue(
            "logo.png (binary file)" in self.content or "logo.png (excluded extension)" in self.content
        )

    def test_oversized_file_excluded(self):
        self.assertNotIn("FILE: huge.txt", self.content)
        self.assertIn("huge.txt (exceeds max-file-size)", self.content)


class TestScopes(unittest.TestCase):
    def _run_scope(self, scope, include=None):
        output = PROJECT_ROOT / f"test_snapshot_{scope}.txt"
        gen = SnapshotGenerator(
            root=PROJECT_ROOT,
            output=output,
            scope=scope,
            purpose="Scope test",
            with_prompt=False,
            max_file_size=100_000,
            max_total_size=10_000_000,
        )
        if include:
            gen.collector.include = include
        gen.generate()
        content = output.read_text(encoding="utf-8")
        output.unlink()
        return content

    def test_tracked_includes_git_files(self):
        content = self._run_scope("tracked")
        # Just verify the snapshot contains *some* tracked file
        self.assertIn("FILE:", content)
        self.assertIn("PROJECT MANIFEST", content)

    def test_selected_scope(self):
        content = self._run_scope("selected", include=["tools/export_project_snapshot.py"])
        self.assertIn("FILE: tools/export_project_snapshot.py", content)


class TestSecretScanner(unittest.TestCase):
    def test_redacts_hf_token(self):
        scanner = SecretScanner()
        text = 'HF_TOKEN = "hf_abc123xyz999999999"'
        result = scanner.scan_and_redact(text, "test.py")
        self.assertNotIn("hf_abc123xyz999999999", result)
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
        self.assertIn('API_KEY = "[REDACTED: POSSIBLE SECRET]"', result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
