#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_websocket_server.py
============================
خادم WebSocket مخصص من الصفر لـ OmniMedical Suite.

المميزات:
- مصافحة WebSocket كاملة (RFC 6455)
- فك/تشفير إطارات البيانات (text, binary, close, ping, pong)
- غرف (rooms) لعزل المستأجرين (tenants) - مطلب HIPAA
- بث متعدد (broadcast) لتحديثات حالة المعالجة
- دعم asyncio لأداء عالٍ
- تكامل مع Celery tasks لإرسال تحديثات فورية

الاستخدام:
    python medical_websocket_server.py --port 8765
"""

import asyncio
import base64
import hashlib
import struct
import json
import logging
import time
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# WebSocket Protocol Constants (RFC 6455)
# =============================================================================

class OpCode(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class WSConnection:
    """يمثل اتصال WebSocket واحد"""
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    tenant_id: str = "default"
    user_id: Optional[str] = None
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)

    async def send(self, data: str):
        """إرسال إطار نصي"""
        frame = WSFrameBuilder.build_text_frame(data)
        self.writer.write(frame)
        await self.writer.drain()

    async def close(self, code: int = 1000, reason: str = ""):
        """إغلاق الاتصال بشكل مهذب"""
        frame = WSFrameBuilder.build_close_frame(code, reason)
        self.writer.write(frame)
        await self.writer.drain()
        self.writer.close()
        await self.writer.wait_closed()


@dataclass
class ProcessingUpdate:
    """تحديث حالة معالجة مستند"""
    document_id: str
    stage: str  # "uploaded", "ocr_started", "ocr_finished", "fusion_started", 
                # "fusion_finished", "dedup_started", "dedup_finished", 
                # "completed", "error"
    progress: int  # 0-100
    message: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "type": "processing_update",
            "document_id": self.document_id,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }, ensure_ascii=False)


# =============================================================================
# WebSocket Frame Parser & Builder
# =============================================================================

class WSFrameParser:
    """فك تشفير إطارات WebSocket حسب RFC 6455"""

    @staticmethod
    async def parse_frame(reader: asyncio.StreamReader) -> Optional[tuple]:
        """
        تقرأ إطاراً واحداً من الـ stream.
        تُرجع: (fin, opcode, payload) أو None إذا انتهى الاتصال
        """
        # قراءة البايتين الأولين
        header = await reader.read(2)
        if len(header) < 2:
            return None

        byte1, byte2 = header[0], header[1]
        fin = (byte1 >> 7) & 1
        opcode = byte1 & 0x0F
        masked = (byte2 >> 7) & 1
        payload_len = byte2 & 0x7F

        # قراءة طول الحمولة الممتد
        if payload_len == 126:
            ext_len = await reader.read(2)
            payload_len = struct.unpack('>H', ext_len)[0]
        elif payload_len == 127:
            ext_len = await reader.read(8)
            payload_len = struct.unpack('>Q', ext_len)[0]

        # قراءة مفتاح القناع (إذا كان من العميل)
        mask_key = None
        if masked:
            mask_key = await reader.read(4)

        # قراءة الحمولة
        payload = await reader.read(payload_len)
        if masked and mask_key:
            payload = bytes([payload[i] ^ mask_key[i % 4] for i in range(len(payload))])

        return fin, opcode, payload


class WSFrameBuilder:
    """بناء إطارات WebSocket"""

    @staticmethod
    def build_frame(opcode: int, payload: bytes, fin: bool = True) -> bytes:
        """بناء إطار عام"""
        byte1 = (0x80 if fin else 0x00) | opcode
        payload_len = len(payload)

        if payload_len <= 125:
            header = struct.pack('BB', byte1, payload_len)
        elif payload_len <= 65535:
            header = struct.pack('!BH', byte1, payload_len)
        else:
            header = struct.pack('!BQ', byte1, payload_len)

        return header + payload

    @staticmethod
    def build_text_frame(text: str) -> bytes:
        return WSFrameBuilder.build_frame(OpCode.TEXT, text.encode('utf-8'))

    @staticmethod
    def build_binary_frame(data: bytes) -> bytes:
        return WSFrameBuilder.build_frame(OpCode.BINARY, data)

    @staticmethod
    def build_close_frame(code: int = 1000, reason: str = "") -> bytes:
        payload = struct.pack('>H', code) + reason.encode('utf-8')
        return WSFrameBuilder.build_frame(OpCode.CLOSE, payload)

    @staticmethod
    def build_ping_frame(data: bytes = b"") -> bytes:
        return WSFrameBuilder.build_frame(OpCode.PING, data)

    @staticmethod
    def build_pong_frame(data: bytes = b"") -> bytes:
        return WSFrameBuilder.build_frame(OpCode.PONG, data)


# =============================================================================
# Handshake Handler
# =============================================================================

class WSHandshake:
    """معالج مصافحة WebSocket"""

    @staticmethod
    def compute_accept_key(key: str) -> str:
        """حساب Sec-WebSocket-Accept حسب RFC 6455"""
        combined = key + WS_GUID
        sha1_hash = hashlib.sha1(combined.encode()).digest()
        return base64.b64encode(sha1_hash).decode()

    @staticmethod
    def build_response(accept_key: str) -> bytes:
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "\r\n"
        )
        return response.encode()

    @staticmethod
    def parse_request(data: bytes) -> Optional[Dict[str, str]]:
        """تحليل طلب HTTP Upgrade"""
        try:
            lines = data.decode('utf-8').strip().split('\r\n')
            headers = {}
            for line in lines[1:]:
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    headers[key.strip().lower()] = value.strip()
            return headers
        except:
            return None


# =============================================================================
# Room Manager (Tenant Isolation)
# =============================================================================

class RoomManager:
    """
    إدارة الغرف لعزل المستأجرين.
    كل tenant لديه غرفته الخاصة - لا يمكنه رؤية تحديثات tenant آخر.
    """

    def __init__(self):
        self.rooms: Dict[str, Set[WSConnection]] = {}
        self.lock = asyncio.Lock()

    async def join(self, room_id: str, conn: WSConnection):
        async with self.lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            self.rooms[room_id].add(conn)
            conn.tenant_id = room_id
            logger.info(f"Client joined room: {room_id}")

    async def leave(self, room_id: str, conn: WSConnection):
        async with self.lock:
            if room_id in self.rooms:
                self.rooms[room_id].discard(conn)
                if not self.rooms[room_id]:
                    del self.rooms[room_id]
            logger.info(f"Client left room: {room_id}")

    async def broadcast_to_room(self, room_id: str, message: str, exclude: Optional[WSConnection] = None):
        """بث رسالة لجميع المتصلين في غرفة معينة"""
        async with self.lock:
            if room_id not in self.rooms:
                return

            disconnected = []
            for conn in self.rooms[room_id]:
                if conn == exclude:
                    continue
                try:
                    await conn.send(message)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected.append(conn)

            # إزالة المتصلين المفصولين
            for conn in disconnected:
                self.rooms[room_id].discard(conn)

    async def broadcast_to_all(self, message: str):
        """بث لجميع الغرف (للإشعارات العامة فقط)"""
        for room_id in list(self.rooms.keys()):
            await self.broadcast_to_room(room_id, message)

    def get_room_stats(self) -> Dict[str, int]:
        """إحصائيات المتصلين لكل غرفة"""
        return {room_id: len(conns) for room_id, conns in self.rooms.items()}


# =============================================================================
# Medical WebSocket Server
# =============================================================================

class MedicalWebSocketServer:
    """
    خادم WebSocket الرئيسي لـ OmniMedical Suite.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.rooms = RoomManager()
        self.connections: Set[WSConnection] = set()
        self.running = False

        # معالجات الرسائل المخصصة
        self.handlers: Dict[str, Callable] = {
            "subscribe_document": self._handle_subscribe_document,
            "subscribe_tenant": self._handle_subscribe_tenant,
            "ping": self._handle_ping,
        }

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """معالجة اتصال عميل جديد"""
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")

        # 1. المصافحة
        handshake_data = await reader.read(4096)
        headers = WSHandshake.parse_request(handshake_data)

        if not headers or 'sec-websocket-key' not in headers:
            logger.warning(f"Invalid WebSocket handshake from {addr}")
            writer.close()
            await writer.wait_closed()
            return

        accept_key = WSHandshake.compute_accept_key(headers['sec-websocket-key'])
        writer.write(WSHandshake.build_response(accept_key))
        await writer.drain()

        # 2. إنشاء اتصال
        conn = WSConnection(reader=reader, writer=writer)
        self.connections.add(conn)

        try:
            # 3. حلقة استقبال الرسائل
            while self.running:
                frame = await WSFrameParser.parse_frame(reader)
                if frame is None:
                    break

                fin, opcode, payload = frame

                if opcode == OpCode.TEXT:
                    await self._handle_text_message(conn, payload.decode('utf-8'))

                elif opcode == OpCode.BINARY:
                    logger.debug(f"Received binary frame: {len(payload)} bytes")

                elif opcode == OpCode.PING:
                    # الرد بـ pong
                    writer.write(WSFrameBuilder.build_pong_frame(payload))
                    await writer.drain()
                    conn.last_ping = time.time()

                elif opcode == OpCode.CLOSE:
                    logger.info(f"Client {addr} requested close")
                    break

                elif opcode == OpCode.CONTINUATION:
                    logger.debug("Continuation frame received")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")

        finally:
            # 4. تنظيف
            self.connections.discard(conn)
            await self.rooms.leave(conn.tenant_id, conn)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            logger.info(f"Client {addr} disconnected")

    async def _handle_text_message(self, conn: WSConnection, message: str):
        """معالجة رسالة نصية من العميل"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")

            if msg_type in self.handlers:
                await self.handlers[msg_type](conn, data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                await conn.send(json.dumps({"error": f"Unknown type: {msg_type}"}))

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {message[:100]}")
            await conn.send(json.dumps({"error": "Invalid JSON"}))

    # -------------------------------------------------------------------------
    # Message Handlers
    # -------------------------------------------------------------------------

    async def _handle_subscribe_document(self, conn: WSConnection, data: Dict):
        """الاشتراك في تحديثات مستند معين"""
        doc_id = data.get("document_id")
        tenant_id = data.get("tenant_id", "default")

        # الانضمام لغرفة المستند
        room_id = f"doc:{tenant_id}:{doc_id}"
        await self.rooms.join(room_id, conn)

        await conn.send(json.dumps({
            "type": "subscribed",
            "document_id": doc_id,
            "status": "success"
        }))
        logger.info(f"Client subscribed to document: {doc_id}")

    async def _handle_subscribe_tenant(self, conn: WSConnection, data: Dict):
        """الاشتراك في تحديثات مستأجر كامل (مثلاً مستشفى بأكمله)"""
        tenant_id = data.get("tenant_id", "default")

        await self.rooms.join(f"tenant:{tenant_id}", conn)

        await conn.send(json.dumps({
            "type": "subscribed",
            "tenant_id": tenant_id,
            "status": "success"
        }))
        logger.info(f"Client subscribed to tenant: {tenant_id}")

    async def _handle_ping(self, conn: WSConnection, data: Dict):
        """رد على ping من العميل"""
        await conn.send(json.dumps({
            "type": "pong",
            "timestamp": time.time()
        }))

    # -------------------------------------------------------------------------
    # Public API for Broadcasting Updates
    # -------------------------------------------------------------------------

    async def notify_document_update(self, update: ProcessingUpdate):
        """إرسال تحديث لجميع المشتركين في مستند معين"""
        room_id = f"doc:{update.metadata.get('tenant_id', 'default')}:{update.document_id}"
        await self.rooms.broadcast_to_room(room_id, update.to_json())

    async def notify_tenant_update(self, tenant_id: str, message: Dict):
        """إرسال إشعار عام لجميع مستخدمي مستأجر"""
        room_id = f"tenant:{tenant_id}"
        await self.rooms.broadcast_to_room(room_id, json.dumps(message, ensure_ascii=False))

    async def notify_medical_alert(self, tenant_id: str, alert: Dict):
        """إرسال تنبيه طبي عاجل (مثلاً تعارض في السياق)"""
        message = {
            "type": "medical_alert",
            "severity": alert.get("severity", "medium"),
            "message": alert.get("message", ""),
            "timestamp": time.time(),
            "requires_action": alert.get("requires_action", False)
        }
        await self.notify_tenant_update(tenant_id, message)

    # -------------------------------------------------------------------------
    # Server Lifecycle
    # -------------------------------------------------------------------------

    async def start(self):
        """بدء الخادم"""
        self.running = True
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )

        # بدء مهمة ping الدورية
        ping_task = asyncio.create_task(self._ping_loop())

        logger.info(f"Medical WebSocket Server started on ws://{self.host}:{self.port}")

        async with server:
            await server.serve_forever()

        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass

    async def _ping_loop(self):
        """إرسال ping دوري للمتصلين للحفاظ على الاتصالات حية"""
        while self.running:
            await asyncio.sleep(30)  # كل 30 ثانية
            disconnected = []
            for conn in list(self.connections):
                try:
                    conn.writer.write(WSFrameBuilder.build_ping_frame())
                    await conn.writer.drain()
                except Exception:
                    disconnected.append(conn)

            for conn in disconnected:
                self.connections.discard(conn)
                await self.rooms.leave(conn.tenant_id, conn)

    def get_stats(self) -> Dict:
        """إحصائيات الخادم"""
        return {
            "total_connections": len(self.connections),
            "rooms": self.rooms.get_room_stats(),
            "uptime": time.time()  # يمكن حسابه بدقة أكبر
        }


# =============================================================================
# Integration with Celery (for sending updates from background tasks)
# =============================================================================

class WebSocketNotifier:
    """
    واجهة لإرسال تحديثات من Celery tasks إلى WebSocket server.
    يمكن استخدام Redis pub/sub أو queue مشتركة.
    """

    def __init__(self, server: MedicalWebSocketServer):
        self.server = server

    async def send_processing_update(self, document_id: str, stage: str, 
                                     progress: int, message: str,
                                     tenant_id: str = "default",
                                     metadata: Optional[Dict] = None):
        """إرسال تحديث معالجة من Celery task"""
        update = ProcessingUpdate(
            document_id=document_id,
            stage=stage,
            progress=progress,
            message=message,
            metadata={**(metadata or {}), "tenant_id": tenant_id}
        )
        await self.server.notify_document_update(update)

    async def send_ocr_complete(self, document_id: str, text: str,
                               confidence: float, tenant_id: str = "default"):
        """إشعار بانتهاء OCR"""
        await self.send_processing_update(
            document_id=document_id,
            stage="ocr_finished",
            progress=40,
            message=f"OCR completed with confidence {confidence:.1%}",
            tenant_id=tenant_id,
            metadata={"extracted_text_preview": text[:200]}
        )

    async def send_fusion_complete(self, document_id: str, fused_text: str,
                                   engines_used: list, tenant_id: str = "default"):
        """إشعار بانتهاء Fusion"""
        await self.send_processing_update(
            document_id=document_id,
            stage="fusion_finished",
            progress=70,
            message=f"Fusion completed using {', '.join(engines_used)}",
            tenant_id=tenant_id,
            metadata={"fused_text_preview": fused_text[:200]}
        )

    async def send_medical_conflict_alert(self, document_id: str, 
                                          conflict_reason: str,
                                          tenant_id: str = "default"):
        """إرسال تنبيه تعارض طبي عاجل"""
        await self.server.notify_medical_alert(
            tenant_id=tenant_id,
            alert={
                "severity": "high",
                "message": f"Medical context conflict detected in {document_id}: {conflict_reason}",
                "requires_action": True
            }
        )


# =============================================================================
# Client Example (for testing)
# =============================================================================

async def test_client():
    """عميل اختبار بسيط"""
    import websockets

    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # الاشتراك في مستند
        await websocket.send(json.dumps({
            "type": "subscribe_document",
            "document_id": "doc_001",
            "tenant_id": "hospital_a"
        }))

        response = await websocket.recv()
        print(f"Subscription response: {response}")

        # استقبال التحديثات
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(msg)
                print(f"Received update: {data.get('stage', 'unknown')} - {data.get('progress', 0)}%")
            except asyncio.TimeoutError:
                # إرسال ping
                await websocket.send(json.dumps({"type": "ping"}))


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OmniMedical WebSocket Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--test-client", action="store_true", help="Run test client")
    args = parser.parse_args()

    if args.test_client:
        asyncio.run(test_client())
    else:
        server = MedicalWebSocketServer(host=args.host, port=args.port)
        try:
            asyncio.run(server.start())
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
            server.running = False
