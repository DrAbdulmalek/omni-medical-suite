"""Regression tests for cross-process serialization of the local training queue."""
from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

import pytest

import app.services.hf_dataset_service as service


def _worker_acquire_queue_lock(stage_dir: str, lock_path: str, acquired) -> None:
    import app.services.hf_dataset_service as worker_service

    worker_service._STAGE_DIR = Path(stage_dir)
    worker_service._QUEUE_LOCK_FILE = Path(lock_path)
    with worker_service._queue_lock():
        acquired.set()


@pytest.mark.skipif(os.name == "nt", reason="this process-lock regression uses POSIX flock")
def test_queue_lock_serializes_independent_processes(tmp_path, monkeypatch):
    import fcntl

    stage_dir = tmp_path / "queue"
    stage_dir.mkdir()
    lock_path = stage_dir / ".queue.lock"
    lock_path.write_bytes(b"\x00")
    monkeypatch.setattr(service, "_STAGE_DIR", stage_dir)
    monkeypatch.setattr(service, "_QUEUE_LOCK_FILE", lock_path)
    monkeypatch.setattr(service, "_UPLOADED_DIR", stage_dir / "uploaded")

    # Hold only the OS-level lock in this process, so the child starts with an
    # unlocked Python threading lock and must block on the shared lock file.
    with lock_path.open("r+b") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        context = multiprocessing.get_context("fork")
        acquired = context.Event()
        child = context.Process(
            target=_worker_acquire_queue_lock,
            args=(str(stage_dir), str(lock_path), acquired),
        )
        child.start()
        try:
            assert not acquired.wait(0.25), "second process bypassed the queue lock"
        finally:
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)

        assert acquired.wait(3), "second process did not acquire the queue lock after release"
        child.join(timeout=3)
        assert child.exitcode == 0


def test_corrupt_pending_row_is_preserved_and_blocks_queue_processing(tmp_path, monkeypatch):
    stage_dir = tmp_path / "queue"
    stage_dir.mkdir()
    pending_path = stage_dir / "pending.jsonl"
    original = b'{"content_hash":"ok"}\\n{corrupt-json\\n'
    pending_path.write_bytes(original)
    monkeypatch.setattr(service, "_STAGE_DIR", stage_dir)
    monkeypatch.setattr(service, "_PENDING_FILE", pending_path)
    monkeypatch.setattr(service, "_QUEUE_LOCK_FILE", stage_dir / ".queue.lock")
    monkeypatch.setattr(service, "_UPLOADED_DIR", stage_dir / "uploaded")

    with pytest.raises(RuntimeError, match="corrupt pending JSON"):
        service._read_pending()

    # A failed parse must not silently drop bytes that queue cleanup could
    # otherwise overwrite during an export/recovery attempt.
    assert pending_path.read_bytes() == original
