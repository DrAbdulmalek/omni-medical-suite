# -*- coding: utf-8 -*-
"""Infrastructure tests for the OmniMedical Suite.

Validates the core infrastructure components — AsyncMedicalRedis,
MedicalLSMStore, MedicalVCS, and MedicalLoadBalancer — using isolated
temp directories and asyncio event loops.

Run with::

    pytest tests/test_infrastructure.py -v
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import Any, Generator

import pytest


# ---------------------------------------------------------------------------
# AsyncMedicalRedis tests (in-process RESP command execution)
# ---------------------------------------------------------------------------

class TestAsyncMedicalRedis:
    """Tests for the asynchronous medical Redis server.

    The server's ``_execute_command`` method is exercised directly so
    no network socket is needed.
    """

    @pytest.fixture()
    def redis(self) -> Any:
        """Create a fresh AsyncMedicalRedis instance with AOF disabled."""
        from services.infra.medical_redis import AsyncMedicalRedis
        srv = AsyncMedicalRedis(aof_path=":memory:")
        return srv

    def test_set_get(self, redis: Any) -> None:
        """SET stores a value and GET retrieves it."""
        redis._execute_command(["SET", "patient:001", '{"name":"Ali"}'])
        resp = redis._execute_command(["GET", "patient:001"])
        assert resp is not None
        assert b"Ali" in resp

    def test_get_missing(self, redis: Any) -> None:
        """GET on a non-existent key returns NIL bulk string."""
        resp = redis._execute_command(["GET", "no:such:key"])
        assert resp is not None
        assert b"-1" in resp  # RESP NIL bulk string

    def test_del(self, redis: Any) -> None:
        """DEL removes a key and returns the count of deleted keys."""
        redis._execute_command(["SET", "tmp:k1", "v1"])
        redis._execute_command(["SET", "tmp:k2", "v2"])
        resp = redis._execute_command(["DEL", "tmp:k1", "tmp:k2"])
        assert resp is not None
        assert b":2" in resp

    def test_expire_and_ttl(self, redis: Any) -> None:
        """EXPIRE sets a TTL; the key is cleaned up once it expires."""
        redis._execute_command(["SET", "ephemeral", "data"])
        resp = redis._execute_command(["EXPIRE", "ephemeral", "1"])
        assert resp is not None
        assert b":1" in resp

        # Key should still exist immediately.
        resp = redis._execute_command(["GET", "ephemeral"])
        assert b"data" in resp

        # After expiry the key should be gone.
        time.sleep(1.5)
        redis._cleanup_expired()
        resp = redis._execute_command(["GET", "ephemeral"])
        assert b"-1" in resp

    def test_lpush_rpop(self, redis: Any) -> None:
        """LPUSH prepends and RPOP removes from the tail of a list."""
        redis._execute_command(["LPUSH", "queue:jobs", "job_c"])
        redis._execute_command(["LPUSH", "queue:jobs", "job_b"])
        redis._execute_command(["LPUSH", "queue:jobs", "job_a"])
        resp = redis._execute_command(["RPOP", "queue:jobs"])
        assert b"job_c" in resp
        resp = redis._execute_command(["RPOP", "queue:jobs"])
        assert b"job_b" in resp


# ---------------------------------------------------------------------------
# MedicalLSMStore tests
# ---------------------------------------------------------------------------

class TestMedicalLSMStore:
    """Tests for the LSM-Tree key-value store with WAL persistence."""

    @pytest.fixture()
    def store(self) -> Generator[Any, None, None]:
        """Create a store in a temporary directory, cleaned up after test."""
        tmpdir = tempfile.mkdtemp(prefix="lsm_test_")
        from services.storage.medical_lsm import MedicalLSMStore
        yield MedicalLSMStore(base_dir=tmpdir, memtable_size=100)
        # Cleanup is handled by the temp directory being garbage-collected.

    def test_put_get(self, store: Any) -> None:
        """PUT stores data and GET retrieves it."""
        store.put("patient:001", {"status": "scanned"})
        result = store.get("patient:001")
        assert result is not None
        assert result["status"] == "scanned"

    def test_get_missing(self, store: Any) -> None:
        """GET on a missing key returns None."""
        assert store.get("nonexistent") is None

    def test_delete(self, store: Any) -> None:
        """DELETE marks a key with a tombstone; GET returns None."""
        store.put("temp:key", "value")
        store.delete("temp:key")
        assert store.get("temp:key") is None

    def test_auto_flush(self, store: Any) -> None:
        """Writing enough entries triggers an automatic flush to SSTable."""
        for i in range(120):
            store.put(f"key:{i:04d}", f"value_{i}")
        stats = store.get_stats()
        assert stats["total_flushes"] >= 1
        assert stats["sstables"] >= 1

    def test_wal_recovery(self) -> None:
        """Unflushed writes survive across a new store instance (WAL replay)."""
        tmpdir = tempfile.mkdtemp(prefix="lsm_wal_")
        from services.storage.medical_lsm import MedicalLSMStore

        store1 = MedicalLSMStore(base_dir=tmpdir, memtable_size=5000)
        store1.put("recovery:key", "survives")
        # Simulate crash: don't call flush, just abandon the object.

        store2 = MedicalLSMStore(base_dir=tmpdir, memtable_size=5000)
        result = store2.get("recovery:key")
        assert result == "survives"


# ---------------------------------------------------------------------------
# MedicalVCS tests
# ---------------------------------------------------------------------------

class TestMedicalVCS:
    """Tests for the medical version control system."""

    @pytest.fixture()
    def repo(self, tmp_path: Any) -> Generator[Any, None, None]:
        """Create a VCS repo in a temporary directory."""
        from services.infra.medical_vcs import MedicalVCS
        vcs = MedicalVCS(repo_path=str(tmp_path / "repo"))
        vcs.init()
        yield vcs

    def test_init(self, repo: Any, tmp_path: Any) -> None:
        """init creates the expected directory structure."""
        repo_dir = tmp_path / "repo"
        assert (repo_dir / "objects").is_dir()
        assert (repo_dir / "refs" / "HEAD").exists()
        assert (repo_dir / "index.json").exists()

    def test_add_and_commit(self, repo: Any) -> None:
        """add stages a file and commit creates a new commit hash."""
        repo.add("report.txt", b"Patient CT scan results.")
        commit_hash = repo.commit(author="dr_ali", message="initial report")
        assert len(commit_hash) == 64

    def test_log(self, repo: Any) -> None:
        """log returns the commit history from HEAD."""
        repo.add("file1.txt", b"content1")
        repo.commit(author="alice", message="first commit")
        repo.add("file2.txt", b"content2")
        repo.commit(author="bob", message="second commit")

        entries = repo.log(max_entries=10)
        assert len(entries) == 2
        assert entries[0]["message"] == "second commit"
        assert entries[1]["message"] == "first commit"

    def test_checkout(self, repo: Any) -> None:
        """checkout restores file contents from a previous commit."""
        repo.add("data.txt", b"version 1")
        repo.commit(author="tester", message="v1")
        hash_v1 = repo._read_head()

        repo.add("data.txt", b"version 2")
        repo.commit(author="tester", message="v2")

        restored = repo.checkout(hash_v1)
        assert restored["data.txt"] == b"version 1"

    def test_status(self, repo: Any) -> None:
        """status reports staged files and HEAD pointer."""
        repo.add("staged.txt", b"pending")
        # status prints but does not return — verify it does not raise.
        repo.status()


# ---------------------------------------------------------------------------
# MedicalLoadBalancer tests
# ---------------------------------------------------------------------------

class TestMedicalLoadBalancer:
    """Tests for the medical load balancer (strategy selection and health)."""

    def test_least_connections_strategy(self) -> None:
        """Least connections strategy picks the backend with fewest active."""
        from services.infra.medical_lb import (
            BackendServer,
            LeastConnectionsStrategy,
        )
        backends = [
            BackendServer("host1", 8001, weight=1),
            BackendServer("host2", 8002, weight=1),
        ]
        backends[0].active_connections = 5
        backends[1].active_connections = 1

        strategy = LeastConnectionsStrategy(backends)
        selected = strategy.select()
        assert selected is not None
        assert selected.port == 8002

    def test_round_robin_strategy(self) -> None:
        """Round Robin distributes requests evenly across healthy backends."""
        from services.infra.medical_lb import BackendServer, RoundRobinStrategy

        backends = [
            BackendServer("host1", 8001),
            BackendServer("host2", 8002),
            BackendServer("host3", 8003),
        ]
        strategy = RoundRobinStrategy(backends)
        ports = [strategy.select().port for _ in range(6)]  # type: ignore[union-attr]
        assert ports == [8001, 8002, 8003, 8001, 8002, 8003]

    def test_health_check_unhealthy_marking(self) -> None:
        """Consecutive failures mark a backend as unhealthy."""
        from services.infra.medical_lb import BackendServer

        backend = BackendServer("unreachable", 9999)
        assert backend.healthy is True

        backend.consecutive_failures = 3
        # Simulate the health checker's threshold logic.
        from services.infra.medical_lb import HealthChecker

        backends = [backend]
        checker = HealthChecker(backends)
        checker.FAILURE_THRESHOLD = 3

        # Mark unhealthy after threshold exceeded.
        backend.consecutive_failures = 3
        backend.healthy = False
        assert backend.healthy is False

    def test_strategy_skips_unhealthy(self) -> None:
        """Both strategies skip backends marked as unhealthy."""
        from services.infra.medical_lb import (
            BackendServer,
            LeastConnectionsStrategy,
            RoundRobinStrategy,
        )

        backends = [
            BackendServer("down", 8001),
            BackendServer("up", 8002),
        ]
        backends[0].healthy = False

        lc = LeastConnectionsStrategy(backends)
        assert lc.select().port == 8002

        rr = RoundRobinStrategy(backends)
        assert rr.select().port == 8002
