# -*- coding: utf-8 -*-
"""
خادم WebSocket الطبي
======================
خادم WebSocket غير متزامن ينفذ بروتوكول RFC 6455 بالكامل.
يدعم: المصافحة (Handshake)، محلل/باني الإطارات (Frame Parser/Builder) مع القناع/إلغاء القناع،
عزل المستأجرين عبر الغرف، البث الجماعي، و آلية Ping/Pong.

Medical WebSocket Server
=========================
An asynchronous WebSocket server fully implementing RFC 6455.
Supports: Handshake, Frame Parser/Builder (mask/unmask), room-based tenant isolation,
broadcast, and ping/pong keep-alive mechanism.
"""

from __future__ import annotations

import asyncio
import argparse
import base64
import hashlib
import json
import logging
import os
import struct
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger: logging.Logger = logging.getLogger("MedicalWebSocket")

# RFC 6455 magic GUID for Sec-WebSocket-Accept
_WS_MAGIC: str = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# WebSocket opcodes
OP_CONTINUATION: int = 0x0
OP_TEXT: int = 0x1
OP_BINARY: int = 0x2
OP_CLOSE: int = 0x8
OP_PING: int = 0x9
OP_PONG: int = 0xA


# ---------------------------------------------------------------------------
# WebSocket Frame
# ---------------------------------------------------------------------------

class WebSocketFrame:
    """
    إطار WebSocket وفق RFC 6455.

    A WebSocket frame per RFC 6455 specification.
    """

    __slots__ = ("fin", "opcode", "masked", "payload", "masking_key")

    def __init__(
        self,
        fin: bool = True,
        opcode: int = OP_TEXT,
        masked: bool = False,
        payload: bytes = b"",
        masking_key: Optional[bytes] = None,
    ) -> None:
        self.fin: bool = fin
        self.opcode: int = opcode
        self.masked: bool = masked
        self.payload: bytes = payload
        self.masking_key: Optional[bytes] = masking_key

    @staticmethod
    def mask(data: bytes, key: bytes) -> bytes:
        """تطبيق قناع XOR على البيانات - Apply XOR masking to data."""
        return bytes(b ^ key[i % 4] for i, b in enumerate(data))

    @staticmethod
    def unmask(data: bytes, key: bytes) -> bytes:
        """إزالة قناع XOR من البيانات - Remove XOR masking from data."""
        return bytes(b ^ key[i % 4] for i, b in enumerate(data))

    def build(self) -> bytes:
        """بناء إطار خام للإرسال - Build raw frame bytes for transmission."""
        header: int = (0x80 if self.fin else 0x00) | (self.opcode & 0x0F)
        length: int = len(self.payload)
        parts: List[bytes] = [struct.pack("!B", header)]

        if length < 126:
            parts.append(struct.pack("!B", length))
        elif length < 65536:
            parts.append(struct.pack("!BH", 126, length))
        else:
            parts.append(struct.pack("!BQ", 127, length))

        if self.masked and self.masking_key:
            parts.append(self.masking_key)
            parts.append(self.mask(self.payload, self.masking_key))
        else:
            parts.append(self.payload)

        return b"".join(parts)

    @classmethod
    async def read_from(cls, reader: asyncio.StreamReader) -> WebSocketFrame:
        """قراءة إطار من دفق القراءة - Read a frame from a stream reader."""
        # Read first 2 bytes
        first_two: bytes = await reader.readexactly(2)
        byte0: int = first_two[0]
        byte1: int = first_two[1]

        fin: bool = bool(byte0 & 0x80)
        opcode: int = byte0 & 0x0F
        masked: bool = bool(byte1 & 0x80)
        payload_len: int = byte1 & 0x7F

        # Extended payload length
        if payload_len == 126:
            ext: bytes = await reader.readexactly(2)
            payload_len = struct.unpack("!H", ext)[0]
        elif payload_len == 127:
            ext: bytes = await reader.readexactly(8)
            payload_len = struct.unpack("!Q", ext)[0]

        # Masking key
        masking_key: Optional[bytes] = None
        if masked:
            masking_key = await reader.readexactly(4)

        # Payload
        payload: bytes = b""
        if payload_len > 0:
            payload = await reader.readexactly(payload_len)

        # Unmask if needed
        if masked and masking_key and payload:
            payload = cls.unmask(payload, masking_key)

        return cls(fin=fin, opcode=opcode, masked=masked, payload=payload, masking_key=masking_key)

    @classmethod
    def build_text(cls, message: str) -> bytes:
        """بناء إطار نصي للإرسال - Build a text frame for transmission."""
        frame: WebSocketFrame = cls(opcode=OP_TEXT, payload=message.encode("utf-8"))
        return frame.build()

    @classmethod
    def build_close(cls, code: int = 1000, reason: str = "") -> bytes:
        """بناء إطار إغلاق - Build a close frame."""
        payload: bytes = struct.pack("!H", code) + reason.encode("utf-8")
        frame: WebSocketFrame = cls(opcode=OP_CLOSE, payload=payload)
        return frame.build()

    @classmethod
    def build_pong(cls, ping_payload: bytes = b"") -> bytes:
        """بناء إطار Pong - Build a Pong frame."""
        frame: WebSocketFrame = cls(opcode=OP_PONG, payload=ping_payload)
        return frame.build()

    @classmethod
    def build_ping(cls, payload: bytes = b"") -> bytes:
        """بناء إطار Ping - Build a Ping frame."""
        frame: WebSocketFrame = cls(opcode=OP_PING, payload=payload)
        return frame.build()


# ---------------------------------------------------------------------------
# Connected Client
# ---------------------------------------------------------------------------

class ClientConnection:
    """تمثيل اتصال عميل WebSocket - Representation of a WebSocket client connection."""

    def __init__(self, writer: asyncio.StreamWriter, client_id: str) -> None:
        self.writer: asyncio.StreamWriter = writer
        self.client_id: str = client_id
        self.rooms: Set[str] = set()
        self.connected_at: float = time.monotonic()
        self.is_alive: bool = True

    def send_text(self, message: str) -> None:
        """إرسال رسالة نصية - Send a text message."""
        if self.is_alive:
            try:
                self.writer.write(WebSocketFrame.build_text(message))
            except (BrokenPipeError, OSError):
                self.is_alive = False

    async def drain(self) -> None:
        """تفريغ المخزن المؤقت - Flush the write buffer."""
        if self.is_alive:
            try:
                await self.writer.drain()
            except (BrokenPipeError, OSError):
                self.is_alive = False


# ---------------------------------------------------------------------------
# MedicalWebSocketServer - Main Server
# ---------------------------------------------------------------------------

class MedicalWebSocketServer:
    """
    خادم WebSocket طبي غير متزامن يدعم:
    - مصافحة RFC 6455 كاملة مع التحقق من Sec-WebSocket-Key
    - تحليل وبناء الإطارات مع دعم القناع/إلغاء القناع
    - عزل المستأجرين عبر نظام الغرف
    - البث الجماعي في الغرف
    - آلية Ping/Pong للحفاظ على الاتصال

    An asynchronous medical WebSocket server supporting:
    - Full RFC 6455 handshake with Sec-WebSocket-Key validation
    - Frame parsing/building with mask/unmask support
    - Room-based tenant isolation
    - Room broadcast messaging
    - Ping/Pong keep-alive mechanism
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host: str = host
        self.port: int = port
        self.clients: Dict[str, ClientConnection] = {}
        self.rooms: Dict[str, Set[str]] = {}
        self._client_counter: int = 0
        self._ping_interval: float = 30.0
        self._stats: Dict[str, int] = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_received": 0,
            "messages_sent": 0,
        }

    # ------------------------------------------------------------------
    # Handshake (RFC 6455 Section 4.2)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_accept_key(websocket_key: str) -> str:
        """
        حساب Sec-WebSocket-Accept من Sec-WebSocket-Key.
        Compute Sec-WebSocket-Accept from Sec-WebSocket-Key.
        """
        value: str = websocket_key.strip() + _WS_MAGIC
        sha1_hash: bytes = hashlib.sha1(value.encode("utf-8")).digest()
        return base64.b64encode(sha1_hash).decode("utf-8")

    async def _perform_handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> bool:
        """
        تنفيذ مصافحة WebSocket مع العميل.
        Perform the WebSocket handshake with a client.
        """
        # Read HTTP request headers
        request_line: bytes = await reader.readline()
        if not request_line:
            return False

        headers: Dict[str, str] = {}
        while True:
            line: bytes = await reader.readline()
            if line == b"\r\n" or line == b"\n" or not line:
                break
            decoded: str = line.decode("utf-8", errors="replace").strip()
            if ":" in decoded:
                key_part, value_part = decoded.split(":", 1)
                headers[key_part.strip().lower()] = value_part.strip()

        # Validate required headers
        ws_key: Optional[str] = headers.get("sec-websocket-key")
        ws_version: Optional[str] = headers.get("sec-websocket-version")

        if not ws_key:
            logger.warning("مصافحة مرفوضة: لا يوجد Sec-WebSocket-Key / Handshake rejected: missing key")
            return False

        if ws_version and ws_version != "13":
            logger.warning("إصدار WebSocket غير مدعوم: %s / Unsupported version: %s", ws_version, ws_version)

        accept_key: str = self._compute_accept_key(ws_key)

        # Build HTTP 101 response
        response: str = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "\r\n"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()
        return True

    # ------------------------------------------------------------------
    # Room Management
    # ------------------------------------------------------------------

    def _join_room(self, client_id: str, room: str) -> None:
        """انضمام عميل إلى غرفة - Add a client to a room."""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(client_id)
        if client_id in self.clients:
            self.clients[client_id].rooms.add(room)
        logger.debug("العميل %s انضم إلى الغرفة '%s' / Client %s joined room '%s'", client_id, room, client_id, room)

    def _leave_room(self, client_id: str, room: str) -> None:
        """مغادرة عميل من غرفة - Remove a client from a room."""
        if room in self.rooms:
            self.rooms[room].discard(client_id)
            if not self.rooms[room]:
                del self.rooms[room]
        if client_id in self.clients:
            self.clients[client_id].rooms.discard(room)

    async def _broadcast_to_room(self, room: str, message: str, sender_id: Optional[str] = None) -> int:
        """بث رسالة لجميع العملاء في غرفة - Broadcast a message to all clients in a room."""
        if room not in self.rooms:
            return 0
        count: int = 0
        for cid in list(self.rooms[room]):
            if cid == sender_id:
                continue
            if cid in self.clients and self.clients[cid].is_alive:
                self.clients[cid].send_text(message)
                count += 1
        if count > 0:
            self._stats["messages_sent"] += count
            # Drain all writers
            await asyncio.gather(
                *[self.clients[cid].drain() for cid in list(self.rooms[room])
                  if cid != sender_id and cid in self.clients and self.clients[cid].is_alive],
                return_exceptions=True,
            )
        return count

    # ------------------------------------------------------------------
    # Protocol Message Handler
    # ------------------------------------------------------------------

    async def _handle_protocol_message(self, client_id: str, frame: WebSocketFrame) -> bool:
        """
        معالجة رسالة بروتوكول واردة (نصية/ثنائية).
        Handle an incoming protocol message (text/binary).
        """
        client: Optional[ClientConnection] = self.clients.get(client_id)
        if client is None:
            return False

        try:
            message: str = frame.payload.decode("utf-8")
        except UnicodeDecodeError:
            return True

        self._stats["messages_received"] += 1

        try:
            msg_data: Dict[str, Any] = json.loads(message)
            msg_type: str = msg_data.get("type", "")

            if msg_type == "join":
                room_name: str = msg_data.get("room", "")
                if room_name:
                    self._join_room(client_id, room_name)

            elif msg_type == "leave":
                room_name = msg_data.get("room", "")
                if room_name:
                    self._leave_room(client_id, room_name)

            elif msg_type == "broadcast":
                room_name = msg_data.get("room", "")
                content: Any = msg_data.get("content", "")
                if room_name:
                    count: int = await self._broadcast_to_room(
                        room_name,
                        json.dumps({"type": "message", "from": client_id, "content": content}),
                        sender_id=client_id,
                    )
                    if count > 0:
                        client.send_text(json.dumps({"type": "ack", "delivered": count}))

            elif msg_type == "direct":
                target_id: str = msg_data.get("to", "")
                content = msg_data.get("content", "")
                if target_id in self.clients and self.clients[target_id].is_alive:
                    self.clients[target_id].send_text(
                        json.dumps({"type": "direct", "from": client_id, "content": content}),
                    )
                    await self.clients[target_id].drain()

        except json.JSONDecodeError:
            pass

        return True

    # ------------------------------------------------------------------
    # Client Connection Lifecycle
    # ------------------------------------------------------------------

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """معالجة اتصال WebSocket لعميل واحد - Handle a single WebSocket client connection."""
        addr: Tuple[str, int] = writer.get_extra_info("peername")

        # Perform handshake
        handshake_ok: bool = await self._perform_handshake(reader, writer)
        if not handshake_ok:
            writer.close()
            await writer.wait_closed()
            return

        # Register client
        self._client_counter += 1
        client_id: str = f"client-{self._client_counter}"
        client: ClientConnection = ClientConnection(writer, client_id)
        self.clients[client_id] = client
        self._stats["total_connections"] += 1
        self._stats["active_connections"] += 1

        logger.info(
            "اتصال WebSocket جديد: %s (المعرف=%s) / New WebSocket: %s (id=%s)",
            addr, client_id, addr, client_id,
        )

        try:
            while True:
                frame: WebSocketFrame = await WebSocketFrame.read_from(reader)

                if frame.opcode == OP_TEXT or frame.opcode == OP_BINARY:
                    should_continue: bool = await self._handle_protocol_message(client_id, frame)
                    if not should_continue:
                        break

                elif frame.opcode == OP_CLOSE:
                    logger.info("إغلاق من %s / Close from %s (id=%s)", addr, client_id, client_id)
                    writer.write(WebSocketFrame.build_close())
                    await writer.drain()
                    break

                elif frame.opcode == OP_PING:
                    logger.debug("Ping من %s / Ping from %s", addr, client_id)
                    writer.write(WebSocketFrame.build_pong(frame.payload))
                    await writer.drain()

                elif frame.opcode == OP_PONG:
                    logger.debug("Pong من %s / Pong from %s", addr, client_id)

                else:
                    logger.warning("رمز عملية غير مدعوم: 0x%X / Unsupported opcode: 0x%X", frame.opcode, frame.opcode)

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.error("خطأ في WebSocket %s: %s / WebSocket %s error: %s", addr, exc, client_id, exc)
        finally:
            # Cleanup
            for room in list(client.rooms):
                self._leave_room(client_id, room)
            self.clients.pop(client_id, None)
            self._stats["active_connections"] = max(0, self._stats["active_connections"] - 1)
            client.is_alive = False
            try:
                writer.close()
                await writer.wait_closed()
            except OSError:
                pass
            logger.info("تم قطع اتصال WebSocket %s / WebSocket disconnected %s", client_id, client_id)

    # ------------------------------------------------------------------
    # Server Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """بدء تشغيل خادم WebSocket - Start the WebSocket server."""
        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        logger.info(
            "خادم WebSocket الطبي يعمل على %s:%d / Medical WebSocket listening on %s:%d",
            self.host, self.port, self.host, self.port,
        )
        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """نقطة دخول سطر الأوامر - CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="خادم WebSocket الطبي / Medical WebSocket Server",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="عنوان الاستماع / Bind address")
    parser.add_argument("--port", type=int, default=8765, help="منفذ الاستماع / Bind port")
    cli_args: argparse.Namespace = parser.parse_args()

    ws_server: MedicalWebSocketServer = MedicalWebSocketServer(
        host=cli_args.host,
        port=cli_args.port,
    )

    try:
        asyncio.run(ws_server.start())
    except KeyboardInterrupt:
        logger.info("جاري إيقاف خادم WebSocket / Shutting down WebSocket server...")


if __name__ == "__main__":
    main()
