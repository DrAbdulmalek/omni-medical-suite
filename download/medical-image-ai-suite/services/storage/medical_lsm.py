# -*- coding: utf-8 -*-
"""LSM-Tree storage engine for medical audit trails and telemetry.

Provides a lightweight, crash-safe key-value store built entirely on the
Python standard library.  Data is first written to a Write-Ahead Log (WAL),
then applied to an in-memory MemTable.  When the MemTable reaches its
capacity threshold the contents are flushed to a sorted-string table (SSTable)
on disk.

Read path:
    MemTable → SSTable_n (newest) → … → SSTable_0 (oldest)

Deletions use a *tombstone* sentinel value so that older SSTables can be
compacted independently.

Typical usage::

    store = MedicalLSMStore()
    store.put("patient:001", {"scan_type": "CT", "status": "completed"})
    record = store.get("patient:001")
    store.delete("patient:001")
"""

from __future__ import annotations

import json
import os
import pickle
import threading
from collections import OrderedDict
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Sentinel used to mark deleted keys (tombstone pattern)
# ---------------------------------------------------------------------------
_TOMBSTONE = object()


class MemTable:
    """In-memory ordered table backed by :class:`collections.OrderedDict`.

    Parameters
    ----------
    max_size:
        Maximum number of key-value pairs before the table is considered
        full and must be flushed to disk.  Defaults to **5 000**.

    Attributes
    ----------
    table : OrderedDict[str, Any]
        The underlying ordered mapping.
    size : int
        Current number of live entries (excludes tombstones from count but
        they still occupy a slot).
    """

    def __init__(self, max_size: int = 5000) -> None:
        self.max_size: int = max_size
        self.table: OrderedDict[str, Any] = OrderedDict()
        self.size: int = 0

    def put(self, key: str, value: Any) -> None:
        """Insert or update *key* with *value*.

        If the key already exists the size counter is **not** incremented
        (it counts slots, not mutations).
        """
        is_new = key not in self.table
        self.table[key] = value
        if is_new:
            self.size += 1

    def get(self, key: str) -> Any:
        """Return the value for *key*, or ``None`` if absent."""
        return self.table.get(key)

    def full(self) -> bool:
        """Return ``True`` when the table has reached *max_size* slots."""
        return self.size >= self.max_size

    def clear(self) -> None:
        """Remove all entries and reset the size counter."""
        self.table.clear()
        self.size = 0

    def items(self) -> "list[tuple[str, Any]]":
        """Return all key-value pairs in insertion order."""
        return list(self.table.items())


class SSTable:
    """Immutable on-disk sorted-string table serialised with :mod:`pickle`.

    Each SSTable file stores a list of ``(key, value)`` tuples.  Tombstone
    entries (values equal to ``_TOMBSTONE``) are preserved so that compaction
    can correctly remove superseded data later.
    """

    @staticmethod
    def write(path: str, data: list[tuple[str, Any]]) -> None:
        """Persist *data* to *path* using the pickle protocol.

        Parameters
        ----------
        path:
            Destination file path.
        data:
            List of ``(key, value)`` pairs in sorted order.
        """
        with open(path, "wb") as fh:
            pickle.dump(data, fh, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def read(path: str) -> list[tuple[str, Any]]:
        """Load and return the key-value pairs stored at *path*.

        Returns an empty list if the file does not exist.
        """
        if not os.path.exists(path):
            return []
        with open(path, "rb") as fh:
            return pickle.load(fh)  # type: ignore[return-value]


class MedicalLSMStore:
    """High-level LSM-Tree key-value store tailored for medical telemetry.

    Features:
    * **Crash recovery** – every write is first appended to a WAL
      (``wal.log``) so that an unclean shutdown can be recovered on the
      next start-up.
    * **Auto-flush** – when the MemTable reaches its capacity the contents
      are flushed to a numbered SSTable file and the WAL is truncated.
    * **Tombstone deletion** – ``delete()`` inserts a tombstone so that
      ``get()`` correctly returns ``None`` even if the key exists in an
      older SSTable.
    * **Thread-safety** – a reentrant lock protects all mutable state.

    Parameters
    ----------
    base_dir:
        Directory in which WAL, SSTable files, and metadata are stored.
        Defaults to ``"data/lsm_audit"``.
    memtable_size:
        Maximum entries in the in-memory table before flushing.
    """

    def __init__(
        self,
        base_dir: str = "data/lsm_audit",
        memtable_size: int = 5000,
    ) -> None:
        self.base_dir: str = base_dir
        self.memtable_size: int = memtable_size
        self._memtable = MemTable(max_size=memtable_size)
        self._sstables: list[SSTable] = []
        self._lock = threading.RLock()
        self._write_count: int = 0
        self._delete_count: int = 0
        self._flush_count: int = 0
        self._ss_counter: int = 0

        os.makedirs(self.base_dir, exist_ok=True)
        self._recover()

    # -- WAL helpers --------------------------------------------------------

    @property
    def _wal_path(self) -> str:
        return os.path.join(self.base_dir, "wal.log")

    def _wal_append(self, key: str, value: Any) -> None:
        """Append a single entry to the Write-Ahead Log.

        Each line is a JSON object with ``k`` (key) and ``v`` (value).  A
        tombstone is encoded as ``{"k": ..., "v": null, "tombstone": true}``.
        """
        entry: dict[str, Any] = {"k": key, "v": None}
        if value is _TOMBSTONE:
            entry["tombstone"] = True
        else:
            entry["v"] = value
        with open(self._wal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _wal_clear(self) -> None:
        """Remove the WAL file after a successful flush."""
        if os.path.exists(self._wal_path):
            os.remove(self._wal_path)

    def _recover(self) -> None:
        """Replay the WAL and load existing SSTables on start-up.

        1. Scans *base_dir* for ``sst_*.dat`` files and loads them into
           ``_sstables`` (oldest first).
        2. Replays any remaining WAL entries into the MemTable so that
           writes that have not yet been flushed are not lost.
        3. Truncates the WAL after successful replay.
        """
        # -- Load existing SSTables from disk (oldest → newest) ----------
        ss_files = sorted(
            f for f in os.listdir(self.base_dir)
            if f.startswith("sst_") and f.endswith(".dat")
        )
        for fname in ss_files:
            path = os.path.join(self.base_dir, fname)
            data = SSTable.read(path)
            self._sstables.append(data)
            self._flush_count += 1
        if ss_files:
            # Derive the next SSTable sequence number.
            last_num = int(ss_files[-1].replace("sst_", "").replace(".dat", ""))
            self._ss_counter = last_num + 1

        # -- Replay the WAL into the MemTable ------------------------------
        if not os.path.exists(self._wal_path):
            return
        with open(self._wal_path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key: str = entry["k"]
                    if entry.get("tombstone"):
                        value = _TOMBSTONE
                    else:
                        value = entry["v"]
                    self._memtable.put(key, value)
                    self._write_count += 1
                except (json.JSONDecodeError, KeyError):
                    # Skip corrupted lines rather than aborting recovery.
                    continue
        # After successful replay, discard the WAL.
        self._wal_clear()

    # -- Public API ---------------------------------------------------------

    def put(self, key: str, value: Any) -> None:
        """Write *key* → *value* to the store.

        The entry is appended to the WAL **before** being applied to the
        MemTable so that no data is lost on a crash.  If the MemTable
        becomes full after the insert an automatic flush is triggered.

        Parameters
        ----------
        key:
            Unique string identifier.
        value:
            Arbitrary serialisable value (dict, list, str, int, …).
        """
        with self._lock:
            self._wal_append(key, value)
            self._memtable.put(key, value)
            self._write_count += 1
            if self._memtable.full():
                self._flush()

    def get(self, key: str) -> Optional[Any]:
        """Look up *key* in the store.

        Search order: **MemTable** → **newest SSTable** → … → **oldest
        SSTable**.  Tombstone markers cause an immediate ``None`` return.
        """
        with self._lock:
            # 1. Check MemTable
            value = self._memtable.get(key)
            if value is not None:
                return None if value is _TOMBSTONE else value
            if value is _TOMBSTONE:
                return None

            # 2. Check SSTables in reverse order (newest first)
            for sstable in reversed(self._sstables):
                for k, v in sstable:
                    if k == key:
                        return None if v is _TOMBSTONE else v
            return None

    def delete(self, key: str) -> None:
        """Mark *key* as deleted by inserting a tombstone.

        The tombstone overwrites any existing value so that ``get()``
        will return ``None`` even if the key is found in an older SSTable.
        """
        with self._lock:
            self._wal_append(key, _TOMBSTONE)
            self._memtable.put(key, _TOMBSTONE)
            self._delete_count += 1
            if self._memtable.full():
                self._flush()

    # -- Flush / compaction --------------------------------------------------

    def _flush(self) -> None:
        """Persist the current MemTable to a new SSTable on disk.

        Steps:
        1. Dump MemTable contents to ``sst_{n}.dat``.
        2. Clear the MemTable and truncate the WAL.
        3. Register the new SSTable in the in-memory list.
        """
        data = self._memtable.items()
        if not data:
            return

        path = os.path.join(self.base_dir, f"sst_{self._ss_counter}.dat")
        SSTable.write(path, data)
        self._sstables.append(data)
        self._ss_counter += 1
        self._flush_count += 1

        self._memtable.clear()
        self._wal_clear()

    # -- Statistics ----------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return a dictionary of operational statistics.

        Returns
        -------
        dict
            Keys: ``memtable_size``, ``memtable_max``, ``sstables``,
            ``total_writes``, ``total_deletes``, ``total_flushes``,
            ``wal_exists``, ``base_dir``.
        """
        with self._lock:
            return {
                "memtable_size": self._memtable.size,
                "memtable_max": self._memtable.max_size,
                "sstables": len(self._sstables),
                "total_writes": self._write_count,
                "total_deletes": self._delete_count,
                "total_flushes": self._flush_count,
                "wal_exists": os.path.exists(self._wal_path),
                "base_dir": self.base_dir,
            }
