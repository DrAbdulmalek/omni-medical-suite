# -*- coding: utf-8 -*-
"""WebSocket bridge for PyQt5 — OmniMedical Suite.

Provides a :class:`QtWebSocketBridge` QObject that wraps an asyncio
WebSocket client inside a daemon thread.  Incoming messages are relayed
to the Qt signal ``update`` so that any QObject receiver can process them
on the main (GUI) thread via Qt's queued connection mechanism.

Typical usage::

    bridge = QtWebSocketBridge(
        ws_url="ws://host/ws",
        tenant_id="hospital-a",
    )
    bridge.update.connect(my_handler)
    bridge.start()
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal  # type: ignore[import]

logger = logging.getLogger(__name__)


class QtWebSocketBridge(QObject):
    """Long-lived WebSocket bridge suitable for embedding in a PyQt5
    application.

    Signals:
        connected:    Emitted (with no arguments) after a successful
                      WebSocket handshake.
        update:       Emitted with the parsed JSON payload (``dict``)
                      whenever a text message arrives from the server.
        disconnected: Emitted with a human-readable reason string when
                      the connection is lost.
        error:        Emitted with an error description string on
                      connection failures.
    """

    connected = pyqtSignal()
    update = pyqtSignal(dict)
    disconnected = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        ws_url: str,
        tenant_id: str,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the bridge.

        Args:
            ws_url:    Full WebSocket URL (e.g. ``ws://host:port/ws``).
            tenant_id: Identifier of the tenant / hospital whose room
                       the bridge will subscribe to.
            parent:    Optional Qt parent object.
        """
        super().__init__(parent)
        self._ws_url: str = ws_url
        self._tenant_id: str = tenant_id
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the bridge in a background daemon thread.

        The asyncio event loop runs until :meth:`stop` is called or the
        thread is terminated.
        """
        if self._running:
            logger.warning("Bridge is already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("QtWebSocketBridge started (tenant=%s).", self._tenant_id)

    def stop(self) -> None:
        """Request a clean shutdown of the bridge."""
        self._running = False
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("QtWebSocketBridge stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Entry point for the background thread — creates and runs the
        asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except asyncio.CancelledError:
            pass
        finally:
            self._loop.close()

    async def _connect(self) -> None:
        """Maintain a persistent WebSocket connection with automatic
        reconnection on failure (3-second back-off)."""
        import websockets  # type: ignore[import-untyped]

        while self._running:
            try:
                async with websockets.connect(
                    self._ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self.connected.emit()
                    # Subscribe to the tenant-specific room.
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "tenant_id": self._tenant_id,
                    }))

                    async for raw_message in ws:
                        if not self._running:
                            break
                        try:
                            payload = json.loads(raw_message)
                        except json.JSONDecodeError:
                            logger.warning("Non-JSON message received.")
                            continue
                        self.update.emit(payload)

            except Exception as exc:  # pragma: no cover — network errors
                self.disconnected.emit(str(exc))
                self.error.emit(str(exc))
                if self._running:
                    await asyncio.sleep(3)
