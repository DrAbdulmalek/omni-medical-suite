# -*- coding: utf-8 -*-
"""
نظام التحكم بالإصدارات الطبي
================================
نظام تحكم بالإصدارات مستوحى من Git يستخدم تجزئة SHA-256 للكائنات،
مع تخزين قابل للعنونة حسب المحتوى (objects/XX/XXXX)،
وسلسلة آباء الالتزام، واسترجاع أي إصدار،
وسجل تاريخي كامل، ومؤشر HEAD.

Medical Version Control System
================================
A Git-inspired version control system using SHA-256 object hashing,
content-addressable storage (objects/XX/XXXX), commit parent chain,
checkout any version, full history log, and HEAD pointer.
Designed for HIPAA audit trails of medical data changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Utility: SHA-256 hashing
# ---------------------------------------------------------------------------

def _sha256_hash(content: bytes) -> str:
    """حساب تجزئة SHA-256 - Compute SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# MedicalVCS - Core Version Control System
# ---------------------------------------------------------------------------

class MedicalVCS:
    """
    نظام تحكم بالإصدارات طبي يعتمد على نموذج المحتوى القابل للعنونة.
    كل كائن (ملف، التزام، شجرة) يُخزن وفق تجزئة SHA-256 الخاصة به.

    A medical version control system based on content-addressable storage.
    Every object (blob, commit, tree) is stored by its SHA-256 hash.

    Storage layout:
        <repo>/
        ├── objects/
        │   └── XX/
        │       └── XXXXXX...   (remaining 38 hex chars)
        ├── refs/
        │   └── HEAD            (current commit hash)
        ├── index.json          (staged files)
        └── config.json         (repository metadata)
    """

    OBJ_DIR: str = "objects"
    REFS_DIR: str = "refs"
    INDEX_FILE: str = "index.json"
    CONFIG_FILE: str = "config.json"

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path: str = os.path.abspath(repo_path)
        self._objects_path: str = os.path.join(self.repo_path, self.OBJ_DIR)
        self._refs_path: str = os.path.join(self.repo_path, self.REFS_DIR)
        self._index_path: str = os.path.join(self.repo_path, self.INDEX_FILE)
        self._config_path: str = os.path.join(self.repo_path, self.CONFIG_FILE)
        self._head_path: str = os.path.join(self._refs_path, "HEAD")

    # ------------------------------------------------------------------
    # Repository Initialization
    # ------------------------------------------------------------------

    def init(self) -> None:
        """
        تهيئة مستودع جديد.
        Initialize a new version control repository.
        """
        os.makedirs(self._objects_path, exist_ok=True)
        os.makedirs(self._refs_path, exist_ok=True)
        self._write_json(self._index_path, {"staged": {}, "timestamp": time.time()})
        self._write_json(self._config_path, {
            "repo_version": "1.0.0",
            "created_at": time.time(),
            "description": "Medical VCS Repository - HIPAA Audit Trail",
        })
        if not os.path.exists(self._head_path):
            with open(self._head_path, "w", encoding="utf-8") as fh:
                fh.write("")
        print(f"تم تهيئة المستودع الطبي في: {self.repo_path}")
        print(f"Initialized medical repository at: {self.repo_path}")

    # ------------------------------------------------------------------
    # Object Storage (Content-Addressable)
    # ------------------------------------------------------------------

    def _object_path(self, obj_hash: str) -> str:
        """
        حساب مسار كائن من تجزئته.
        Compute the filesystem path for an object from its hash.
        Layout: objects/XX/XXXXXXXXXXXXXXXX...
        """
        return os.path.join(self._objects_path, obj_hash[:2], obj_hash[2:])

    def _store_object(self, content: bytes) -> str:
        """
        تخزين كائن بإرجاع تجزئته SHA-256.
        Store an object and return its SHA-256 hash.
        """
        obj_hash: str = _sha256_hash(content)
        path: str = self._object_path(obj_hash)
        if os.path.exists(path):
            return obj_hash
        dir_name: str = os.path.dirname(path)
        os.makedirs(dir_name, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)
        return obj_hash

    def _read_object(self, obj_hash: str) -> bytes:
        """
        قراءة كائن من تجزئته.
        Read an object by its hash.
        """
        path: str = self._object_path(obj_hash)
        if not os.path.exists(path):
            raise FileNotFoundError(f"الكائن غير موجود: {obj_hash} / Object not found: {obj_hash}")
        with open(path, "rb") as fh:
            return fh.read()

    # ------------------------------------------------------------------
    # Blob Operations (File Content)
    # ------------------------------------------------------------------

    def add(self, file_path: str, data: bytes) -> str:
        """
        إضافة ملف إلى منطقة التجهيز (staging).
        Add a file to the staging area.
        """
        blob: Dict[str, Any] = {
            "type": "blob",
            "path": file_path,
            "data_hash": _sha256_hash(data),
            "size": len(data),
            "timestamp": time.time(),
        }
        blob_hash: str = self._store_object(json.dumps(blob, ensure_ascii=False).encode("utf-8"))
        self._store_object(data)

        # Update index
        index: Dict[str, Any] = self._read_json(self._index_path)
        index["staged"][file_path] = blob_hash
        self._write_json(self._index_path, index)

        print(f"تم تجهيز '{file_path}' -> {blob_hash[:12]}...")
        print(f"Staged '{file_path}' -> {blob_hash[:12]}...")
        return blob_hash

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def commit(self, author: str, message: str) -> str:
        """
        إنشاء التزام جديد مع سلسلة الآباء.

        Create a new commit with a parent chain.
        Each commit stores its parent hash, snapshot of staged files,
        author, message, and timestamp for HIPAA audit compliance.
        """
        index: Dict[str, Any] = self._read_json(self._index_path)
        staged: Dict[str, str] = index.get("staged", {})
        if not staged:
            print("لا توجد ملفات مُجهزة / Nothing to commit")
            return ""

        parent: str = self._read_head()

        commit_obj: Dict[str, Any] = {
            "type": "commit",
            "parent": parent,
            "tree": dict(staged),
            "author": author,
            "message": message,
            "timestamp": time.time(),
            "staged_count": len(staged),
        }

        commit_data: bytes = json.dumps(commit_obj, ensure_ascii=False, indent=2).encode("utf-8")
        commit_hash: str = self._store_object(commit_data)

        # Update HEAD
        self._write_head(commit_hash)

        # Clear staging area
        index["staged"] = {}
        index["last_commit"] = commit_hash
        self._write_json(self._index_path, index)

        short_hash: str = commit_hash[:12]
        parent_short: str = parent[:12] if parent else "(none)"
        print(f"التزام {short_hash} | الآب: {parent_short} | '{message}'")
        print(f"Commit {short_hash} | Parent: {parent_short} | '{message}'")
        return commit_hash

    # ------------------------------------------------------------------
    # HEAD Pointer
    # ------------------------------------------------------------------

    def _read_head(self) -> str:
        """قراءة مؤشر HEAD - Read the HEAD pointer."""
        if not os.path.exists(self._head_path):
            return ""
        with open(self._head_path, "r", encoding="utf-8") as fh:
            return fh.read().strip()

    def _write_head(self, commit_hash: str) -> None:
        """كتابة مؤشر HEAD - Write the HEAD pointer."""
        os.makedirs(self._refs_path, exist_ok=True)
        with open(self._head_path, "w", encoding="utf-8") as fh:
            fh.write(commit_hash)

    # ------------------------------------------------------------------
    # History Log
    # ------------------------------------------------------------------

    def log(self, max_entries: int = 50) -> List[Dict[str, Any]]:
        """
        عرض السجل الكامل لسلسلة الالتزامات.

        Display the full commit history log starting from HEAD,
        walking the parent chain in reverse chronological order.
        """
        entries: List[Dict[str, Any]] = []
        current: str = self._read_head()

        while current and len(entries) < max_entries:
            raw: bytes = self._read_object(current)
            commit_data: Dict[str, Any] = json.loads(raw.decode("utf-8"))
            entries.append({
                "hash": current,
                "parent": commit_data.get("parent", ""),
                "author": commit_data.get("author", "unknown"),
                "message": commit_data.get("message", ""),
                "timestamp": commit_data.get("timestamp", 0),
                "files": commit_data.get("staged_count", 0),
            })
            current = commit_data.get("parent", "")

        if not entries:
            print("لا يوجد سجل / No commit history")
            return entries

        print(f"{'التزام':<14} {'الآب':<14} {'المؤلف':<16} {'الملفات':<8} {'الرسالة'}")
        print(f"{'Commit':<14} {'Parent':<14} {'Author':<16} {'Files':<8} {'Message'}")
        print("-" * 80)
        for entry in entries:
            short_hash: str = entry["hash"][:12]
            parent_short: str = entry["parent"][:12] if entry["parent"] else "(none)"
            ts_str: str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["timestamp"]))
            print(
                f"{short_hash:<14} {parent_short:<14} {entry['author']:<16} "
                f"{entry['files']:<8} {entry['message']} [{ts_str}]"
            )
        return entries

    # ------------------------------------------------------------------
    # Checkout (Restore a Version)
    # ------------------------------------------------------------------

    def checkout(self, commit_hash: str) -> Dict[str, bytes]:
        """
        استرجاع حالة مستودع من التزام محدد.

        Restore the repository state to a specific commit.
        Returns a mapping of file paths to their content at that commit version.
        """
        if len(commit_hash) != 64:
            # Try to find by short hash prefix
            full_hash: Optional[str] = self._resolve_short_hash(commit_hash)
            if full_hash is None:
                raise ValueError(f"لا يمكن العثور على الالتزام '{commit_hash}' / Cannot resolve commit '{commit_hash}'")
            commit_hash = full_hash

        raw: bytes = self._read_object(commit_hash)
        commit_data: Dict[str, Any] = json.loads(raw.decode("utf-8"))
        tree: Dict[str, str] = commit_data.get("tree", {})

        restored: Dict[str, bytes] = {}
        for file_path, blob_hash in tree.items():
            blob_raw: bytes = self._read_object(blob_hash)
            blob_obj: Dict[str, Any] = json.loads(blob_raw.decode("utf-8"))
            file_data: bytes = self._read_object(blob_obj["data_hash"])
            restored[file_path] = file_data

        # Update HEAD to the checked-out commit
        self._write_head(commit_hash)

        short_hash: str = commit_hash[:12]
        print(f"تم استرجاع الالتزام {short_hash} ({len(restored)} ملفات)")
        print(f"Checked out commit {short_hash} ({len(restored)} files)")
        return restored

    # ------------------------------------------------------------------
    # Short Hash Resolution
    # ------------------------------------------------------------------

    def _resolve_short_hash(self, prefix: str) -> Optional[str]:
        """
        البحث عن تجزئة كاملة ببادئة قصيرة.
        Resolve a short hash prefix to a full hash.
        """
        for dir_name in os.listdir(self._objects_path):
            dir_path: str = os.path.join(self._objects_path, dir_name)
            if not os.path.isdir(dir_path):
                continue
            for file_name in os.listdir(dir_path):
                full_hash: str = dir_name + file_name
                if full_hash.startswith(prefix):
                    return full_hash
        return None

    # ------------------------------------------------------------------
    # JSON File Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_json(path: str, data: Any) -> None:
        """كتابة كائن JSON إلى ملف - Write a JSON object to a file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    @staticmethod
    def _read_json(path: str) -> Dict[str, Any]:
        """قراءة كائن JSON من ملف - Read a JSON object from a file."""
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> None:
        """عرض حالة المستودع الحالية - Display the current repository status."""
        head: str = self._read_head()
        index: Dict[str, Any] = self._read_json(self._index_path)
        staged: Dict[str, str] = index.get("staged", {})

        print(f"المستودع: {self.repo_path}")
        print(f"Repository: {self.repo_path}")
        print(f"HEAD: {head[:12] if head else '(empty)'}")
        print(f"الملفات المُجهزة: {len(staged)} / Staged files: {len(staged)}")

        if staged:
            for path_key, hash_val in staged.items():
                print(f"  staged: {path_key} -> {hash_val[:12]}")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """نقطة دخول سطر الأوامر - CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="نظام التحكم بالإصدارات الطبي / Medical Version Control System",
    )
    parser.add_argument("--repo", type=str, default=".", help="مسار المستودع / Repository path")
    subparsers = parser.add_subparsers(dest="command", help="الأمر / Command")

    # init
    subparsers.add_parser("init", help="تهيئة مستودع / Initialize repository")

    # add
    add_parser: argparse.ArgumentParser = subparsers.add_parser("add", help="إضافة ملف / Stage a file")
    add_parser.add_argument("file", type=str, help="مسار الملف / File path")
    add_parser.add_argument("--data", type=str, default="", help="محتوى الملف / File content")

    # commit
    commit_parser: argparse.ArgumentParser = subparsers.add_parser("commit", help="التزام جديد / New commit")
    commit_parser.add_argument("--author", type=str, default="medic", help="المؤلف / Author")
    commit_parser.add_argument("--message", "-m", type=str, required=True, help="رسالة الالتزام / Commit message")

    # log
    log_parser: argparse.ArgumentParser = subparsers.add_parser("log", help="سجل الالتزامات / Commit history")
    log_parser.add_argument("--max", type=int, default=50, help="الحد الأقصى / Max entries")

    # checkout
    checkout_parser: argparse.ArgumentParser = subparsers.add_parser("checkout", help="استرجاع إصدار / Checkout version")
    checkout_parser.add_argument("hash", type=str, help="تجزئة الالتزام / Commit hash")

    # status
    subparsers.add_parser("status", help="حالة المستودع / Repository status")

    cli_args: argparse.Namespace = parser.parse_args()

    if not cli_args.command:
        parser.print_help()
        return

    vcs: MedicalVCS = MedicalVCS(repo_path=cli_args.repo)

    if cli_args.command == "init":
        vcs.init()

    elif cli_args.command == "add":
        data: str = cli_args.data
        if not data and os.path.exists(cli_args.file):
            with open(cli_args.file, "rb") as fh:
                data = fh.read().decode("utf-8", errors="replace")
        vcs.add(cli_args.file, data.encode("utf-8"))

    elif cli_args.command == "commit":
        vcs.commit(author=cli_args.author, message=cli_args.message)

    elif cli_args.command == "log":
        vcs.log(max_entries=cli_args.max)

    elif cli_args.command == "checkout":
        vcs.checkout(cli_args.hash)

    elif cli_args.command == "status":
        vcs.status()


if __name__ == "__main__":
    main()
