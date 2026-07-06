# -*- coding: utf-8 -*-
"""
موازن التحميل الطبي
=====================
موازن تحميل غير متزامن يعتمد على استراتيجية أقل الاتصالات (Least Connections)
مع الرجوع إلى الجولة الدائرية (Round Robin). يدعم الفحص الصحي كل 5 ثوانٍ،
والوكيل الثنائي الاتجاه عبر TCP لدعم WebSocket.

Medical Load Balancer
======================
An asyncio-based load balancer implementing the Least Connections strategy
with Round Robin fallback. Supports health checks every 5 seconds and
bidirectional TCP proxying for WebSocket traffic.
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import time
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger: logging.Logger = logging.getLogger("MedicalLoadBalancer")


# ---------------------------------------------------------------------------
# Backend Server Representation
# ---------------------------------------------------------------------------

class BackendServer:
    """
    تمثيل خادم خلفي واحد في مجموعة الموازنة.

    Representation of a single backend server in the load-balancer pool.
    """

    def __init__(self, host: str, port: int, weight: int = 1) -> None:
        self.host: str = host
        self.port: int = port
        self.weight: int = weight
        self.active_connections: int = 0
        self.healthy: bool = True
        self.consecutive_failures: int = 0
        self.last_health_check: float = 0.0
        self.total_requests: int = 0
        self.total_failures: int = 0

    @property
    def address(self) -> Tuple[str, int]:
        return (self.host, self.port)

    def __repr__(self) -> str:
        status: str = "healthy" if self.healthy else "unhealthy"
        return f"Backend({self.host}:{self.port}, conn={self.active_connections}, {status})"


# ---------------------------------------------------------------------------
# Health Checker
# ---------------------------------------------------------------------------

class HealthChecker:
    """
    فاحص صحي دوري لخوادم الخلفية.
    يتحقق كل 5 ثوانٍ من توفر كل خادم عبر اتصال TCP.

    Periodic health checker for backend servers.
    Verifies each server's availability every 5 seconds via a TCP probe.
    """

    CHECK_INTERVAL: float = 5.0
    MAX_CONSECUTIVE_FAILURES: int = 3
    FAILURE_THRESHOLD: int = 3
    RECOVERY_ATTEMPTS: int = 1

    def __init__(self, backends: List[BackendServer]) -> None:
        self.backends: List[BackendServer] = backends
        self._running: bool = False

    async def _check_single(self, backend: BackendServer) -> None:
        """فحص صحي واحد لخادم خلفي - Perform a single health check on a backend."""
        backend.last_health_check = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(backend.host, backend.port),
                timeout=3.0,
            )
            writer.close()
            await writer.wait_closed()

            if not backend.healthy:
                logger.info(
                    "تم استعادة الخادم %s:%d / Backend %s:%d recovered",
                    backend.host, backend.port, backend.host, backend.port,
                )
            backend.healthy = True
            backend.consecutive_failures = 0

        except (OSError, asyncio.TimeoutError, ConnectionRefusedError):
            backend.consecutive_failures += 1
            backend.total_failures += 1
            if backend.consecutive_failures >= self.FAILURE_THRESHOLD:
                if backend.healthy:
                    logger.warning(
                        "الخادم %s:%d غير صحي (فشل متتالي=%d) / Backend %s:%d unhealthy (failures=%d)",
                        backend.host, backend.port, backend.consecutive_failures,
                        backend.host, backend.port, backend.consecutive_failures,
                    )
                backend.healthy = False

    async def run(self) -> None:
        """بدء حلقة الفحص الصحي - Start the health-check loop."""
        self._running = True
        logger.info("بدء الفحص الصحي (كل %.1fs) / Health checker started (every %.1fs)",
                     self.CHECK_INTERVAL, self.CHECK_INTERVAL)
        while self._running:
            for backend in self.backends:
                await self._check_single(backend)
            await asyncio.sleep(self.CHECK_INTERVAL)

    def stop(self) -> None:
        """إيقاف الفحص الصحي - Stop the health checker."""
        self._running = False
        logger.info("تم إيقاف الفحص الصحي / Health checker stopped")


# ---------------------------------------------------------------------------
# Load Balancing Strategies
# ---------------------------------------------------------------------------

class LoadBalancerStrategy:
    """واجهة استراتيجية موازنة التحميل - Load balancing strategy interface."""

    def __init__(self, backends: List[BackendServer]) -> None:
        self.backends: List[BackendServer] = backends
        self._rr_index: int = 0

    def select(self) -> Optional[BackendServer]:
        """اختيار خادم خلفي - Select a backend server."""
        raise NotImplementedError

    def _healthy_backends(self) -> List[BackendServer]:
        """قائمة الخوادم الصحية - List of healthy backends."""
        return [b for b in self.backends if b.healthy]


class LeastConnectionsStrategy(LoadBalancerStrategy):
    """
    استراتيجية أقل الاتصالات النشطة.
    تختار الخادم الذي يحمل أقل عدد من الاتصالات الحالية.

    Least Connections strategy.
    Selects the backend with the fewest active connections.
    """

    def select(self) -> Optional[BackendServer]:
        healthy: List[BackendServer] = self._healthy_backends()
        if not healthy:
            return None
        return min(healthy, key=lambda b: (b.active_connections, -b.weight))


class RoundRobinStrategy(LoadBalancerStrategy):
    """
    استراتيجية الجولة الدائرية.
    توزع الطلبات بالتناوب على الخوادم الصحية.

    Round Robin strategy.
    Distributes requests evenly across healthy backends.
    """

    def select(self) -> Optional[BackendServer]:
        healthy: List[BackendServer] = self._healthy_backends()
        if not healthy:
            return None
        selected: BackendServer = healthy[self._rr_index % len(healthy)]
        self._rr_index += 1
        return selected


# ---------------------------------------------------------------------------
# Bidirectional TCP Proxy
# ---------------------------------------------------------------------------

async def _proxy_relay(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    backend_name: str,
    direction: str,
) -> None:
    """تمرير البيانات ثنائي الاتجاه بين العميل والخادم الخلفي."""
    try:
        while True:
            data: bytes = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            if writer.can_write_eof():
                writer.write_eof()
        except (NotImplementedError, OSError):
            pass
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# MedicalLoadBalancer - Main Server
# ---------------------------------------------------------------------------

class MedicalLoadBalancer:
    """
    موازن تحميل طبي غير متزامن يدعم:
    - استراتيجية أقل الاتصالات (Least Connections) كأولوية
    - الرجوع إلى الجولة الدائرية (Round Robin) في حالة التساوي
    - الفحص الصحي الدوري لكل خادم
    - الوكيل الثنائي الاتجاه عبر TCP لدعم WebSocket

    An asynchronous medical load balancer supporting:
    - Least Connections as primary strategy
    - Round Robin fallback on ties
    - Periodic health checks per backend
    - Bidirectional TCP proxying for WebSocket support
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.host: str = host
        self.port: int = port
        self.backends: List[BackendServer] = []
        self._health_checker: Optional[HealthChecker] = None
        self._stats: Dict[str, int] = {
            "total_connections": 0,
            "proxied": 0,
            "rejected": 0,
        }

    def add_backend(self, host: str, port: int, weight: int = 1) -> None:
        """إضافة خادم خلفي إلى مجموعة الموازنة - Add a backend to the pool."""
        backend: BackendServer = BackendServer(host, port, weight)
        self.backends.append(backend)
        logger.info("تمت إضافة الخادم الخلفي %s:%d (الوزن=%d) / Added backend %s:%d (weight=%d)",
                     host, port, weight, host, port, weight)

    def _select_backend(self) -> Optional[BackendServer]:
        """
        اختيار خادم خلفي باستخدام استراتيجية أقل الاتصالات مع الرجوع إلى الجولة الدائرية.

        Select a backend using Least Connections with Round Robin fallback.
        """
        lc: LeastConnectionsStrategy = LeastConnectionsStrategy(self.backends)
        primary: Optional[BackendServer] = lc.select()

        if primary is not None:
            # If multiple backends tie, use Round Robin among them
            min_conn: int = primary.active_connections
            tied: List[BackendServer] = [b for b in self.backends if b.healthy and b.active_connections == min_conn]
            if len(tied) > 1:
                rr: RoundRobinStrategy = RoundRobinStrategy(tied)
                return rr.select()
            return primary

        return None

    async def _handle_client(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """معالجة اتصال عميل واحد عبر الوكيل الثنائي - Handle a single client via bidirectional proxy."""
        addr: Tuple[str, int] = client_writer.get_extra_info("peername")
        self._stats["total_connections"] += 1

        backend: Optional[BackendServer] = self._select_backend()
        if backend is None:
            self._stats["rejected"] += 1
            error_msg: str = "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n"
            client_writer.write(error_msg.encode("utf-8"))
            await client_writer.drain()
            client_writer.close()
            await client_writer.wait_closed()
            logger.warning("رفض طلب من %s - لا خوادم صحية / Rejected %s - no healthy backends", addr, addr)
            return

        backend.active_connections += 1
        backend.total_requests += 1
        self._stats["proxied"] += 1

        logger.info(
            "وكيل %s -> %s:%d (الاتصالات النشطة=%d) / Proxy %s -> %s:%d (active=%d)",
            addr, backend.host, backend.port, backend.active_connections,
            addr, backend.host, backend.port, backend.active_connections,
        )

        try:
            backend_reader: asyncio.StreamReader
            backend_writer: asyncio.StreamWriter
            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(backend.host, backend.port),
                timeout=10.0,
            )

            task_c2b: asyncio.Task = asyncio.create_task(
                _proxy_relay(client_reader, backend_writer, f"{backend.host}:{backend.port}", "c2b"),
            )
            task_b2c: asyncio.Task = asyncio.create_task(
                _proxy_relay(backend_reader, client_writer, f"{backend.host}:{backend.port}", "b2c"),
            )

            done: set
            pending: set
            done, pending = await asyncio.wait(
                [task_c2b, task_b2c],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except (OSError, asyncio.TimeoutError) as exc:
            logger.error(
                "فشل الاتصال بالخادم الخلفي %s:%d: %s / Backend %s:%d connection failed: %s",
                backend.host, backend.port, exc, backend.host, backend.port, exc,
            )
        finally:
            backend.active_connections -= 1
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except OSError:
                pass

    async def start(self) -> None:
        """بدء تشغيل موازن التحميل - Start the load balancer."""
        if not self.backends:
            logger.error("لا توجد خوادم خلفية مُهيأة / No backends configured")
            return

        # Start health checker
        self._health_checker = HealthChecker(self.backends)
        health_task: asyncio.Task = asyncio.create_task(self._health_checker.run())

        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )

        logger.info(
            "موازن التحميل الطبي يعمل على %s:%d / Medical Load Balancer listening on %s:%d",
            self.host, self.port, self.host, self.port,
        )
        logger.info("الخوادم الخلفية: %s / Backends: %s", self.backends, self.backends)

        async with server:
            await server.serve_forever()

    def shutdown(self) -> None:
        """إيقاف موازن التحميل - Shut down the load balancer."""
        if self._health_checker is not None:
            self._health_checker.stop()
        logger.info("إحصائيات موازن التحميل: %s / LB stats: %s", self._stats, self._stats)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """نقطة دخول سطر الأوامر - CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="موازن التحميل الطبي / Medical Load Balancer",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="عنوان الاستماع / Bind address")
    parser.add_argument("--port", type=int, default=8080, help="منفذ الاستماع / Bind port")
    parser.add_argument(
        "--backends", type=str, required=True,
        help="الخوادم الخلفية مفصولة بفاصلة (host:port,host:port) / Comma-separated backends",
    )
    cli_args: argparse.Namespace = parser.parse_args()

    lb: MedicalLoadBalancer = MedicalLoadBalancer(host=cli_args.host, port=cli_args.port)

    for entry in cli_args.backends.split(","):
        entry = entry.strip()
        if ":" not in entry:
            logger.warning("تنسيق خاطئ: %s (يجب أن يكون host:port) / Bad format: %s", entry, entry)
            continue
        host_part, port_str = entry.rsplit(":", 1)
        try:
            lb.add_backend(host_part.strip(), int(port_str.strip()))
        except ValueError:
            logger.warning("منفذ غير صالح: %s / Invalid port: %s", entry, entry)

    try:
        asyncio.run(lb.start())
    except KeyboardInterrupt:
        lb.shutdown()


if __name__ == "__main__":
    main()
