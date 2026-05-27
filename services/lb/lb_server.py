"""
OmniMedical Suite — Load Balancer Server
==========================================
موزع حمل بسيط وفعال يعمل باستخدام least_conn أو round_robin.

الاستراتيجيات المدعومة:
- least_conn: يوجه الطلب لأقل عقدة تحميلاً
- round_robin: التوزيع الدوري

المؤلف: Dr. Abdulmalek Al-husseini
"""

import os
import time
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class BackendManager:
    """إدارة عقد API الخلفية."""

    def __init__(self, backends_str: str, strategy: str = "least_conn"):
        self.backends = []
        self.strategy = strategy
        self._lock = threading.Lock()

        # Parse backends: "api1:8000,api2:8000"
        for b in backends_str.split(","):
            b = b.strip()
            if b:
                self.backends.append({
                    "host": b,
                    "active_connections": 0,
                    "total_requests": 0,
                    "total_errors": 0,
                    "healthy": True,
                    "last_check": 0.0,
                })

        logger.info(f"Backends configured: {len(self.backends)} [{strategy}]")
        for b in self.backends:
            logger.info(f"  - {b['host']}")

    def get_backend(self) -> Optional[str]:
        """اختيار عقدة حسب الاستراتيجية."""
        with self._lock:
            healthy = [b for b in self.backends if b["healthy"]]
            if not healthy:
                # fallback: أي عقدة
                healthy = self.backends
            if not healthy:
                return None

            if self.strategy == "least_conn":
                backend = min(healthy, key=lambda b: b["active_connections"])
            else:  # round_robin
                backend = healthy[int(time.time()) % len(healthy)]

            backend["active_connections"] += 1
            backend["total_requests"] += 1
            return backend["host"]

    def release(self, host: str, error: bool = False):
        """تحرير الاتصال."""
        with self._lock:
            for b in self.backends:
                if b["host"] == host:
                    b["active_connections"] = max(0, b["active_connections"] - 1)
                    if error:
                        b["total_errors"] += 1
                    break

    def health_check(self):
        """فحص صحة العقد."""
        with self._lock:
            for b in self.backends:
                try:
                    url = f"http://{b['host']}/health"
                    req = Request(url, method="GET")
                    with urlopen(req, timeout=3) as resp:
                        b["healthy"] = (resp.status == 200)
                except Exception:
                    b["healthy"] = False
                b["last_check"] = time.time()


class LBHandler(BaseHTTPRequestHandler):
    """معالج طلبات موزع الحمل."""

    manager: BackendManager = None  # set by main

    def do_GET(self):
        self._proxy_request()

    def do_POST(self):
        self._proxy_request()

    def do_PUT(self):
        self._proxy_request()

    def do_DELETE(self):
        self._proxy_request()

    def do_OPTIONS(self):
        self._proxy_request()

    def _proxy_request(self):
        # Health check endpoint محلي
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "omni-lb",
                "backends": len(self.manager.backends),
                "strategy": self.manager.strategy,
            })
            return

        # Metrics endpoint
        if self.path == "/metrics":
            self._send_json(200, {
                "lb_total_requests": sum(
                    b["total_requests"] for b in self.manager.backends
                ),
                "lb_total_errors": sum(
                    b["total_errors"] for b in self.manager.backends
                ),
                "backends": [
                    {
                        "host": b["host"],
                        "healthy": b["healthy"],
                        "active_connections": b["active_connections"],
                        "total_requests": b["total_requests"],
                    }
                    for b in self.manager.backends
                ],
            })
            return

        # اختيار عقدة وتوجيه الطلب
        backend = self.manager.get_backend()
        if not backend:
            self._send_json(503, {"error": "No healthy backends available"})
            return

        try:
            # قراءة body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # بناء الطلب
            url = f"http://{backend}{self.path}"
            req = Request(url, data=body, method=self.command)

            # نسخ الـ headers
            for key, value in self.headers.items():
                if key.lower() not in ("host", "content-length"):
                    req.add_header(key, value)
            if body:
                req.add_header("Content-Length", str(len(body)))

            # إرسال
            with urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    if key.lower() not in ("transfer-encoding",):
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(resp_body)

            self.manager.release(backend)

        except (URLError, HTTPError) as e:
            self.manager.release(backend, error=True)
            self._send_json(502, {"error": f"Backend error: {str(e)}"[:200]})
        except Exception as e:
            self.manager.release(backend, error=True)
            self._send_json(500, {"error": f"Internal error: {str(e)}"[:200]})

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.info(f"[LB] {args[0]}")


def health_check_loop(manager: BackendManager, interval: int = 10):
    """حلقة فحص الصحة الدورية."""
    while True:
        time.sleep(interval)
        manager.health_check()
        healthy = sum(1 for b in manager.backends if b["healthy"])
        logger.info(f"Health check: {healthy}/{len(manager.backends)} healthy")


def main():
    backends = os.environ.get("BACKENDS", "api1:8000,api2:8000")
    strategy = os.environ.get("STRATEGY", "least_conn")
    port = int(os.environ.get("PORT", "8080"))
    health_interval = int(os.environ.get("HEALTH_CHECK_INTERVAL", "10"))

    LBHandler.manager = BackendManager(backends, strategy)

    # بدء فحص الصحة في خلفية
    t = threading.Thread(
        target=health_check_loop,
        args=(LBHandler.manager, health_interval),
        daemon=True
    )
    t.start()

    server = HTTPServer(("0.0.0.0", port), LBHandler)
    logger.info(f"Load Balancer running on :{port} [{strategy}]")
    logger.info(f"Backends: {backends}")
    server.serve_forever()


if __name__ == "__main__":
    main()
