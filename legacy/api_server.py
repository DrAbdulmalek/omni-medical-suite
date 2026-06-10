"""
OmniMedical Suite — API Worker (Stub)
=======================================
عقدة API توفر نقاط نهاية REST لمعالجة المستندات الطبية.
هذا ملف أساسي (stub) يمكن تطويره ليشمل:
- معالجة OCR الحقيقية
- التصحيح الإملائي
- استخراج الكيانات الطبية
- إدارة المستخدمين والمستأجرين

المؤلف: Dr. Abdulmalek Al-husseini
"""

import os
import json
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKER_ID = os.environ.get("WORKER_ID", "unknown")


class APIHandler(BaseHTTPRequestHandler):
    """معالج طلبات API."""

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {
                "status": "ok",
                "worker_id": WORKER_ID,
                "timestamp": time.time()
            })
        elif self.path == "/metrics":
            self._json(200, {
                "worker_id": WORKER_ID,
                "requests_total": 0,
                "requests_active": 0,
            })
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON"})
            return

        if self.path == "/api/documents/upload":
            # Stub: محاكاة معالجة المستند
            self._json(200, {
                "status": "queued",
                "worker_id": WORKER_ID,
                "doc_type": data.get("doc_type", "unknown"),
                "document_id": f"doc_{int(time.time())}",
            })
        elif self.path == "/api/ocr/correction":
            self._json(200, {
                "status": "saved",
                "worker_id": WORKER_ID,
            })
        else:
            self._json(404, {"error": "Not found"})

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.info(f"[{WORKER_ID}] {args[0]}")


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    logger.info(f"API Worker {WORKER_ID} running on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
