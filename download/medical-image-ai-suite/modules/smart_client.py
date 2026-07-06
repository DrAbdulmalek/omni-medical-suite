# -*- coding: utf-8 -*-
"""Smart medical client with offline persistence — OmniMedical Suite.

:class:`SmartMedicalClient` extends the basic WebSocket bridge with:

* **Offline task queuing** — tasks enqueued while the connection is down
  are written to a local JSON-lines file and automatically replayed
  when connectivity is restored.
* **Periodic sync** — a 30-second timer periodically drains the
  persisted queue to the server.
* **Qt signal integration** — all lifecycle events are emitted as Qt
  signals so that the GUI can react in real time.

Typical usage::

    client = SmartMedicalClient(
        ws_url="ws://host/ws",
        jwt_token="eyJ…",
    )
    client.update.connect(on_server_message)
    client.start()
    client.enqueue_task({"action": "process_image", "path": "/tmp/x.png"})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal  # type: ignore[import]

logger = logging.getLogger(__name__)

#: Default path for the offline persistence file.
_PERSIST_PATH: str = os.path.join(
    os.path.expanduser("~"), ".omnimedical", "offline_queue.jsonl"
)


class SmartMedicalClient(QObject):
    """WebSocket client with offline disk persistence and automatic queue
    draining for the OmniMedical Suite.

    Signals:
        online:        Emitted after a successful WebSocket connection.
        offline:       Emitted when the connection is lost or has not yet
                       been established.
        update:        Emitted with the parsed JSON payload (``dict``)
                       for every inbound server message.
        sync_complete: Emitted with the number of tasks that were
                       successfully flushed from the offline queue.
    """

    online = pyqtSignal()
    offline = pyqtSignal()
    update = pyqtSignal(dict)
    sync_complete = pyqtSignal(int)

    def __init__(
        self,
        ws_url: str,
        jwt_token: str,
        persist_path: str = _PERSIST_PATH,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the smart client.

        Args:
            ws_url:       Full WebSocket URL.
            jwt_token:    JSON Web Token used for authentication.
            persist_path: Filesystem path for the offline queue file.
            parent:       Optional Qt parent.
        """
        super().__init__(parent)
        self._ws_url: str = ws_url
        self._jwt_token: str = jwt_token
        self._persist_path: str = persist_path
        self._task_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._connected: bool = False

        # Periodic sync timer (runs on the Qt main thread).
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._attempt_sync)
        self._sync_timer.setInterval(30_000)  # 30 s

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the client: open the background thread, connect to the
        WebSocket, and begin the periodic sync timer."""
        if self._running:
            logger.warning("SmartMedicalClient is already running.")
            return

        self._running = True
        self._ensure_persist_dir()
        self._load_from_disk()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._sync_timer.start()
        logger.info("SmartMedicalClient started.")

    def stop(self) -> None:
        """Gracefully shut down the client."""
        self._running = False
        self._sync_timer.stop()
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("SmartMedicalClient stopped.")

    def enqueue_task(self, payload: Dict[str, Any]) -> None:
        """Add a task payload to the outgoing queue.

        If the WebSocket is currently connected the task is sent
        immediately; otherwise it is persisted to disk for later
        delivery.

        Args:
            payload: Arbitrary JSON-serialisable dictionary representing
                     the task to send.
        """
        self._task_queue.put(payload)
        self._save_to_disk(payload)
        if self._connected:
            self._drain_queue()
        logger.debug("Task enqueued: %s", payload.get("action", "<unnamed>"))

    # ------------------------------------------------------------------
    # Queue persistence
    # ------------------------------------------------------------------

    def _save_to_disk(self, payload: Dict[str, Any]) -> None:
        """Append a single task to the offline persistence file.

        Each line in the file is a valid JSON object (JSON-Lines format).

        Args:
            payload: The task payload to persist.
        """
        try:
            with open(self._persist_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to persist task: %s", exc)

    def _load_from_disk(self) -> None:
        """Load previously persisted tasks back into the in-memory
        queue (called once at start-up)."""
        if not os.path.isfile(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._task_queue.put(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning(
                            "Skipping malformed line %d in offline queue.",
                            line_no,
                        )
        except OSError as exc:
            logger.error("Failed to load offline queue: %s", exc)

    def _clear_persist_file(self) -> None:
        """Remove the offline persistence file after a successful drain."""
        try:
            if os.path.isfile(self._persist_path):
                os.remove(self._persist_path)
        except OSError as exc:
            logger.error("Failed to clear offline queue file: %s", exc)

    def _ensure_persist_dir(self) -> None:
        """Create the parent directory for the persistence file if it
        does not already exist."""
        parent = os.path.dirname(self._persist_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    # ------------------------------------------------------------------
    # Synchronisation
    # ------------------------------------------------------------------

    def _drain_queue(self) -> None:
        """Send all queued tasks to the server (best-effort).

        Runs on the asyncio background thread.  Successfully sent tasks
        are removed from both the in-memory queue and the disk file.
        """
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._async_drain(), self._loop)

    async def _async_drain(self) -> None:
        """Coroutine that sends queued payloads over the WebSocket."""
        import websockets  # type: ignore[import-untyped]

        if not self._connected:
            return

        sent = 0
        while not self._task_queue.empty():
            try:
                payload = self._task_queue.get_nowait()
            except queue.Empty:
                break
            try:
                async with websockets.connect(
                    self._ws_url,
                    extra_headers={"Authorization": f"Bearer {self._jwt_token}"},
                ) as ws:
                    await ws.send(json.dumps(payload, ensure_ascii=False))
                    sent += 1
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to send queued task: %s", exc)
                # Put it back for the next attempt.
                self._task_queue.put(payload)
                break

        if sent > 0:
            self._clear_persist_file()
            self.sync_complete.emit(sent)

    def _attempt_sync(self) -> None:
        """Slot connected to the periodic sync QTimer.  Triggers a drain
        if the client is currently online."""
        if self._connected:
            self._drain_queue()

    # ------------------------------------------------------------------
    # Asyncio networking
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except asyncio.CancelledError:
            pass
        finally:
            self._loop.close()

    async def _connect_loop(self) -> None:
        """Maintain a persistent WebSocket connection with automatic
        reconnection (3-second back-off)."""
        import websockets  # type: ignore[import-untyped]

        while self._running:
            try:
                async with websockets.connect(
                    self._ws_url,
                    extra_headers={"Authorization": f"Bearer {self._jwt_token}"},
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._connected = True
                    self.online.emit()
                    self._drain_queue()

                    async for raw_message in ws:
                        if not self._running:
                            break
                        try:
                            payload = json.loads(raw_message)
                        except json.JSONDecodeError:
                            continue
                        self.update.emit(payload)

            except Exception as exc:  # pragma: no cover
                self._connected = False
                self.offline.emit()
                logger.error("Connection error: %s", exc)
                if self._running:
                    await asyncio.sleep(3)
