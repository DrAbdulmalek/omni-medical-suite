"""
OmniMedical Suite — WebSocket Server
=======================================
خادم WebSocket للتنبيهات الفورية والمزامنة التلقائية.
يدعم:
- الاشتراك في المستأجرين (tenants) — عزل المستشفيات
- إرسال تحديثات معالجة المستندات
- نبضات القلب (heartbeat)
- بث الرسائل للمجموعات

المؤلف: Dr. Abdulmalek Al-husseini
"""

import os
import json
import time
import asyncio
import logging
from typing import Dict, Set
from dataclasses import dataclass, field

try:
    import websockets
    from websockets.server import serve
except ImportError:
    raise ImportError(
        "websockets مطلوب. ثبته بـ: pip install websockets"
    )

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Client:
    """عميل متصل."""
    ws = None
    user_id: str = ""
    tenant_id: str = ""
    connected_at: float = 0.0
    last_heartbeat: float = 0.0


class WebSocketHub:
    """مركز WebSocket لإدارة الاتصالات والبث."""

    def __init__(self, heartbeat_interval: int = 30, max_connections: int = 5000):
        self.clients: Dict[str, Client] = {}  # client_id -> Client
        self.tenant_subscribers: Dict[str, Set[str]] = {}  # tenant_id -> {client_ids}
        self.heartbeat_interval = heartbeat_interval
        self.max_connections = max_connections
        self._lock = asyncio.Lock()
        self._message_count = 0
        self._connection_count = 0

    async def register(self, ws, client_id: str) -> Client:
        """تسجيل عميل جديد."""
        async with self._lock:
            if len(self.clients) >= self.max_connections:
                await ws.close(1013, "Max connections reached")
                raise ConnectionError("Max connections reached")

            client = Client(
                ws=ws,
                user_id=client_id,
                connected_at=time.time(),
                last_heartbeat=time.time()
            )
            self.clients[client_id] = client
            self._connection_count += 1

        logger.info(f"Client connected: {client_id} "
                     f"({len(self.clients)}/{self.max_connections})")
        return client

    async def unregister(self, client_id: str):
        """إلغاء تسجيل عميل."""
        async with self._lock:
            client = self.clients.pop(client_id, None)
            if client:
                # إزالة من اشتراكات المستأجر
                if client.tenant_id in self.tenant_subscribers:
                    self.tenant_subscribers[client.tenant_id].discard(client_id)
                    if not self.tenant_subscribers[client.tenant_id]:
                        del self.tenant_subscribers[client.tenant_id]

        logger.info(f"Client disconnected: {client_id} "
                     f"({len(self.clients)}/{self.max_connections})")

    async def subscribe_tenant(self, client_id: str, tenant_id: str):
        """اشتراك عميل في مستأجر (مستشفى/عيادة)."""
        async with self._lock:
            client = self.clients.get(client_id)
            if client:
                client.tenant_id = tenant_id
                if tenant_id not in self.tenant_subscribers:
                    self.tenant_subscribers[tenant_id] = set()
                self.tenant_subscribers[tenant_id].add(client_id)
                logger.info(f"{client_id} subscribed to tenant: {tenant_id}")

    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """بث رسالة لجميع عملاء المستأجر."""
        async with self._lock:
            subscribers = self.tenant_subscribers.get(tenant_id, set()).copy()

        if not subscribers:
            return

        payload = json.dumps(message, ensure_ascii=False)
        tasks = []
        for cid in subscribers:
            client = self.clients.get(cid)
            if client and client.ws:
                tasks.append(self._safe_send(client.ws, payload))

        await asyncio.gather(*tasks, return_exceptions=True)
        self._message_count += 1

    async def send_to_client(self, client_id: str, message: dict):
        """إرسال رسالة لعميل محدد."""
        client = self.clients.get(client_id)
        if client and client.ws:
            await self._safe_send(client.ws, json.dumps(message, ensure_ascii=False))
            self._message_count += 1

    async def _safe_send(self, ws, payload: str):
        """إرسال آمن مع معالجة الأخطاء."""
        try:
            await ws.send(payload)
        except Exception as e:
            logger.debug(f"Send failed: {e}")

    async def heartbeat_checker(self):
        """فحص نبضات القلب لإزالة العملاء غير النشطين."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            now = time.time()
            stale = []
            async with self._lock:
                for cid, client in self.clients.items():
                    if now - client.last_heartbeat > (self.heartbeat_interval * 3):
                        stale.append(cid)
            for cid in stale:
                logger.info(f"Heartbeat timeout: {cid}")
                client = self.clients.get(cid)
                if client and client.ws:
                    await client.ws.close(4000, "Heartbeat timeout")
                await self.unregister(cid)

    def get_stats(self) -> dict:
        """إحصائيات الخادم."""
        return {
            "connected_clients": len(self.clients),
            "tenants": len(self.tenant_subscribers),
            "total_messages": self._message_count,
            "total_connections": self._connection_count,
            "max_connections": self.max_connections,
        }


# ============================================================================
# Message Handler
# ============================================================================

async def handle_client(hub: WebSocketHub, ws, path: str):
    """معالجة اتصال عميل واحد."""
    client_id = f"client_{id(ws) % 100000}"

    try:
        client = await hub.register(ws, client_id)
    except ConnectionError:
        return

    try:
        async for message in ws:
            try:
                data = json.loads(message)

                msg_type = data.get("type", "")

                if msg_type == "subscribe_tenant":
                    tenant_id = data.get("tenant_id", "")
                    if tenant_id:
                        await hub.subscribe_tenant(client_id, tenant_id)
                        await hub.send_to_client(client_id, {
                            "type": "subscribed",
                            "tenant_id": tenant_id,
                            "status": "ok"
                        })

                elif msg_type == "ping":
                    client.last_heartbeat = time.time()
                    await hub.send_to_client(client_id, {"type": "pong"})

                elif msg_type == "document_update":
                    # Forward to all subscribers of the same tenant
                    if client.tenant_id:
                        await hub.broadcast_to_tenant(client.tenant_id, {
                            "type": "document_update",
                            "from": client_id,
                            "data": data.get("data", {}),
                            "timestamp": time.time()
                        })

                elif msg_type == "processing_progress":
                    if client.tenant_id:
                        await hub.broadcast_to_tenant(client.tenant_id, {
                            "type": "processing_progress",
                            "from": client_id,
                            "stage": data.get("stage", ""),
                            "progress": data.get("progress", 0),
                            "timestamp": time.time()
                        })

                elif msg_type == "chat":
                    if client.tenant_id:
                        await hub.broadcast_to_tenant(client.tenant_id, {
                            "type": "chat",
                            "from": client.user_id or client_id,
                            "message": data.get("message", ""),
                            "timestamp": time.time()
                        })

            except json.JSONDecodeError:
                await hub.send_to_client(client_id, {
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await hub.unregister(client_id)


# ============================================================================
# Main
# ============================================================================

async def main():
    port = int(os.environ.get("WS_PORT", "8765"))
    heartbeat = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))
    max_conn = int(os.environ.get("MAX_CONNECTIONS", "5000"))

    hub = WebSocketHub(
        heartbeat_interval=heartbeat,
        max_connections=max_conn
    )

    # بدء فحص نبضات القلب
    asyncio.create_task(hub.heartbeat_checker())

    logger.info(f"WebSocket server starting on :{port}")
    logger.info(f"Heartbeat: {heartbeat}s | Max connections: {max_conn}")

    async with serve(handle_client, "0.0.0.0", port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
