# -*- coding: utf-8 -*-
"""OmniMedical Manager — central orchestrator for the OmniMedical Suite.

Coordinates the lifecycle of all infrastructure services (Redis, WebSocket,
Load Balancer, LSM store) and provides a unified ``process_document``
pipeline and health-check endpoint.

Typical usage::

    from services.core.omni_manager import OmniMedicalManager

    manager = OmniMedicalManager()
    manager.start_infrastructure()
    status = manager.get_status()
    manager.stop_infrastructure()

The module can also be run directly to start all services::

    python -m services.core.omni_manager
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("OmniMedicalManager")


class OmniMedicalManager:
    """Central coordinator for the OmniMedical Suite infrastructure.

    Manages the start-up, health monitoring, and graceful shutdown of
    all backend services: AsyncMedicalRedis, MedicalWebSocketServer,
    MedicalLoadBalancer, and MedicalLSMStore.

    Parameters
    ----------
    redis_port:
        TCP port for the custom Redis server (default 6380).
    ws_port:
        TCP port for the WebSocket server (default 8765).
    lb_port:
        TCP port for the load balancer (default 8080).
    lsm_dir:
        Filesystem directory for the LSM-Tree store.
    """

    def __init__(
        self,
        redis_port: int = 6380,
        ws_port: int = 8765,
        lb_port: int = 8080,
        lsm_dir: str = "data/lsm_audit",
    ) -> None:
        self.redis_port: int = redis_port
        self.ws_port: int = ws_port
        self.lb_port: int = lb_port
        self.lsm_dir: str = lsm_dir

        self._threads: List[threading.Thread] = []
        self._running: bool = False

        # Lazy-loaded service references.
        self._redis: Optional[Any] = None
        self._ws: Optional[Any] = None
        self._lb: Optional[Any] = None
        self._lsm: Optional[Any] = None

        # Track service start times for health reporting.
        self._start_times: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Infrastructure lifecycle
    # ------------------------------------------------------------------

    def start_infrastructure(self) -> None:
        """Start Redis, WebSocket, and Load Balancer as daemon threads.

        Each service runs its own ``asyncio`` event loop inside a
        dedicated thread so that the coordinator remains responsive
        for status queries and the processing pipeline.
        """
        if self._running:
            logger.warning("Infrastructure is already running.")
            return

        self._running = True
        logger.info("Starting OmniMedical infrastructure …")

        # -- Redis -----------------------------------------------------------
        try:
            self._start_service_thread(
                target=self._run_redis,
                name="redis",
                kwargs={"port": self.redis_port},
            )
        except Exception as exc:
            logger.error("Failed to start Redis: %s", exc)

        # -- WebSocket -------------------------------------------------------
        try:
            self._start_service_thread(
                target=self._run_websocket,
                name="websocket",
                kwargs={"port": self.ws_port},
            )
        except Exception as exc:
            logger.error("Failed to start WebSocket: %s", exc)

        # -- Load Balancer ---------------------------------------------------
        try:
            self._start_service_thread(
                target=self._run_load_balancer,
                name="load_balancer",
                kwargs={"port": self.lb_port},
            )
        except Exception as exc:
            logger.error("Failed to start Load Balancer: %s", exc)

        # -- LSM Store (synchronous, no thread needed) -----------------------
        try:
            from services.storage.medical_lsm import MedicalLSMStore
            os.makedirs(self.lsm_dir, exist_ok=True)
            self._lsm = MedicalLSMStore(base_dir=self.lsm_dir)
            self._start_times["lsm"] = time.monotonic()
            logger.info("LSM store initialised at %s", self.lsm_dir)
        except Exception as exc:
            logger.error("Failed to initialise LSM store: %s", exc)

        logger.info(
            "All services started — Redis:%d, WS:%d, LB:%d",
            self.redis_port, self.ws_port, self.lb_port,
        )

    def stop_infrastructure(self) -> None:
        """Gracefully shut down all infrastructure services."""
        self._running = False
        logger.info("Stopping OmniMedical infrastructure …")

        # Stop Redis
        if self._redis is not None:
            try:
                self._redis.shutdown()
                logger.info("Redis stopped.")
            except Exception as exc:
                logger.error("Error stopping Redis: %s", exc)

        # Stop Load Balancer
        if self._lb is not None:
            try:
                self._lb.shutdown()
                logger.info("Load Balancer stopped.")
            except Exception as exc:
                logger.error("Error stopping LB: %s", exc)

        # Wait for threads to finish (with timeout).
        for thread in self._threads:
            thread.join(timeout=5.0)

        self._threads.clear()
        self._start_times.clear()
        logger.info("Infrastructure stopped.")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a health summary of all infrastructure services.

        Returns
        -------
        dict
            Keys: ``running``, ``services`` (per-service status with
            ``alive``, ``uptime_s``, ``port``), ``lsm_stats``.
        """
        services: Dict[str, Any] = {}

        for name, thread in zip(
            ["redis", "websocket", "load_balancer"],
            self._threads,
        ):
            start = self._start_times.get(name, 0)
            services[name] = {
                "alive": thread.is_alive(),
                "uptime_s": round(time.monotonic() - start, 1) if start else 0,
            }

        # LSM stats
        lsm_stats: Dict[str, Any] = {}
        if self._lsm is not None:
            try:
                lsm_stats = self._lsm.get_stats()
            except Exception as exc:
                lsm_stats = {"error": str(exc)}

        return {
            "running": self._running,
            "services": services,
            "lsm_stats": lsm_stats,
        }

    # ------------------------------------------------------------------
    # Example document processing pipeline
    # ------------------------------------------------------------------

    def process_document(
        self,
        document_id: str,
        image_data: bytes,
    ) -> Dict[str, Any]:
        """Run the full document processing pipeline on a single image.

        This is a demonstration pipeline that:
        1. Stores the document reference in Redis.
        2. Persists processing metadata in the LSM store.
        3. Returns a summary of the operation.

        Parameters
        ----------
        document_id:
            Unique identifier for the document.
        image_data:
            Raw image bytes.

        Returns
        -------
        dict
            Processing result with ``document_id``, ``status``,
            ``redis_stored``, ``lsm_stored``, and ``timestamp``.
        """
        result: Dict[str, Any] = {
            "document_id": document_id,
            "status": "processed",
            "timestamp": time.time(),
        }

        # Store in Redis
        if self._redis is not None:
            try:
                size_mb = len(image_data) / (1024 * 1024)
                self._redis._execute_command([
                    "SET", f"doc:{document_id}", f"size_mb={size_mb:.2f}",
                ])
                result["redis_stored"] = True
            except Exception as exc:
                result["redis_stored"] = False
                result["redis_error"] = str(exc)

        # Store metadata in LSM
        if self._lsm is not None:
            try:
                self._lsm.put(
                    f"doc_meta:{document_id}",
                    {
                        "size": len(image_data),
                        "processed_at": time.time(),
                        "status": "ok",
                    },
                )
                result["lsm_stored"] = True
            except Exception as exc:
                result["lsm_stored"] = False
                result["lsm_error"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Thread helpers
    # ------------------------------------------------------------------

    def _start_service_thread(
        self,
        target: Any,
        name: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Start a daemon thread for a service and record its start time."""
        thread = threading.Thread(
            target=target,
            kwargs=kwargs or {},
            daemon=True,
            name=f"omni-{name}",
        )
        thread.start()
        self._threads.append(thread)
        self._start_times[name] = time.monotonic()
        logger.info("Thread '%s' started.", name)

    # ------------------------------------------------------------------
    # Service entry points (run in dedicated threads with own event loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_redis(port: int) -> None:
        """Start the AsyncMedicalRedis server in a new event loop."""
        from services.infra.medical_redis import AsyncMedicalRedis
        redis = AsyncMedicalRedis(port=port, aof_path="data/redis/medical_redis.aof")
        try:
            asyncio.run(redis.start())
        except Exception as exc:
            logger.error("Redis thread exited: %s", exc)

    @staticmethod
    def _run_websocket(port: int) -> None:
        """Start the MedicalWebSocket server in a new event loop."""
        from services.infra.medical_websocket import MedicalWebSocketServer
        ws = MedicalWebSocketServer(port=port)
        try:
            asyncio.run(ws.start())
        except Exception as exc:
            logger.error("WebSocket thread exited: %s", exc)

    @staticmethod
    def _run_load_balancer(port: int) -> None:
        """Start the MedicalLoadBalancer (starts without backends)."""
        from services.infra.medical_lb import MedicalLoadBalancer
        lb = MedicalLoadBalancer(port=port)
        try:
            asyncio.run(lb.start())
        except Exception as exc:
            logger.error("Load Balancer thread exited: %s", exc)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start all OmniMedical infrastructure services and wait for shutdown."""
    manager = OmniMedicalManager()
    manager.start_infrastructure()

    try:
        while True:
            time.sleep(5)
            status = manager.get_status()
            alive = sum(
                1 for s in status["services"].values() if s["alive"]
            )
            logger.info(
                "Heartbeat — alive services: %d/%d",
                alive, len(status["services"]),
            )
    except KeyboardInterrupt:
        logger.info("Received shutdown signal.")
    finally:
        manager.stop_infrastructure()


if __name__ == "__main__":
    main()
