# -*- coding: utf-8 -*-
"""
خادم Redis الطبي غير المتزامن
==============================
خادم TCP غير متزامن ينفذ بروتوكول RESP (REdis Serialization Protocol)
مع دعم أوامر SET، GET، DEL، EXPIRE، LPUSH، RPOP، ودعم Pub/Sub.
يتضمن تنظيف TTL باستخدام كومة الأولوية، واستمرارية AOF (Append-Only File).

Async Medical Redis Server
===========================
An asynchronous TCP server implementing the RESP (REdis Serialization Protocol)
with support for SET, GET, DEL, EXPIRE, LPUSH, RPOP commands and Pub/Sub.
Includes TTL expiry heap cleanup and AOF (Append-Only File) persistence.
"""

from __future__ import annotations

import asyncio
import heapq
import json
import os
import time
import argparse
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger: logging.Logger = logging.getLogger("AsyncMedicalRedis")


# ---------------------------------------------------------------------------
# RESP Protocol Helpers
# ---------------------------------------------------------------------------

class RESPProtocol:
    """بروتوكول تسلسل Redis - Redis Serialization Protocol encoder/decoder."""

    _CRLF: bytes = b"\r\n"

    @staticmethod
    def encode_simple_string(s: str) -> bytes:
        return b"+" + s.encode("utf-8") + RESPProtocol._CRLF

    @staticmethod
    def encode_error(msg: str) -> bytes:
        return b"-" + msg.encode("utf-8") + RESPProtocol._CRLF

    @staticmethod
    def encode_integer(n: int) -> bytes:
        return b":" + str(n).encode("utf-8") + RESPProtocol._CRLF

    @staticmethod
    def encode_bulk_string(s: Optional[str]) -> bytes:
        if s is None:
            return b"$-1\r\n"
        payload: bytes = s.encode("utf-8")
        return b"$" + str(len(payload)).encode("utf-8") + RESPProtocol._CRLF + payload + RESPProtocol._CRLF

    @staticmethod
    def encode_array(items: List[Any]) -> bytes:
        parts: List[bytes] = [b"*" + str(len(items)).encode("utf-8") + RESPProtocol._CRLF]
        for item in items:
            if isinstance(item, str):
                parts.append(RESPProtocol.encode_bulk_string(item))
            elif isinstance(item, int):
                parts.append(RESPProtocol.encode_integer(item))
            elif item is None:
                parts.append(RESPProtocol.encode_bulk_string(None))
            else:
                parts.append(RESPProtocol.encode_bulk_string(str(item)))
        return b"".join(parts)

    @staticmethod
    async def read_line(reader: asyncio.StreamReader) -> bytes:
        return await reader.readline()

    @staticmethod
    async def parse(reader: asyncio.StreamReader) -> List[str]:
        """تحليل أمر RESP وارد من دفق القراءة - Parse an incoming RESP command."""
        line: bytes = await reader.readline()
        if not line:
            raise ConnectionError("تم إغلاق الاتصال / Connection closed")

        prefix: chr = chr(line[0])

        if prefix == "*":
            count: int = int(line[1:].strip())
            args: List[str] = []
            for _ in range(count):
                bulk_line: bytes = await reader.readline()
                if bulk_line.startswith(b"$"):
                    length: int = int(bulk_line[1:].strip())
                    if length == -1:
                        args.append("")
                    else:
                        data: bytes = await reader.readexactly(length + 2)
                        args.append(data[:length].decode("utf-8", errors="replace"))
                else:
                    args.append(bulk_line.strip().decode("utf-8", errors="replace"))
            return args
        else:
            return [line.strip().decode("utf-8", errors="replace")]


# ---------------------------------------------------------------------------
# Expiry Heap Entry
# ---------------------------------------------------------------------------

class ExpiryEntry:
    """إدخال انتهاء الصلاحية في كومة الأولوية - Expiry heap entry for TTL management."""
    __slots__ = ("expire_at", "key")

    def __init__(self, expire_at: float, key: str) -> None:
        self.expire_at: float = expire_at
        self.key: str = key

    def __lt__(self, other: ExpiryEntry) -> bool:
        return self.expire_at < other.expire_at

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExpiryEntry):
            return NotImplemented
        return self.expire_at == other.expire_at


# ---------------------------------------------------------------------------
# AsyncMedicalRedis - Main Server
# ---------------------------------------------------------------------------

class AsyncMedicalRedis:
    """
    خادم Redis طبي غير متزامن يدعم أوامر البيانات الأساسية و Pub/Sub واستمرارية AOF.

    An asynchronous medical Redis server supporting core data commands,
    Pub/Sub messaging, and AOF persistence for HIPAA compliance.
    """

    OK: bytes = RESPProtocol.encode_simple_string("OK")
    NIL: bytes = RESPProtocol.encode_bulk_string(None)
    PONG: bytes = RESPProtocol.encode_simple_string("PONG")

    def __init__(self, host: str = "0.0.0.0", port: int = 6380, aof_path: str = "medical_redis.aof") -> None:
        self.host: str = host
        self.port: int = port
        self.aof_path: str = aof_path

        # تخزين البيانات الرئيسي - Main data store
        self.data: Dict[str, str] = {}
        self.ttl_map: Dict[str, float] = {}
        self.expiry_heap: List[ExpiryEntry] = []

        # قوائم - Lists (LPUSH/RPOP)
        self.lists: Dict[str, List[str]] = {}

        # Pub/Sub - النشر والاشتراك
        self.channels: Dict[str, Set[asyncio.StreamWriter]] = {}

        # AOF persistence file handle
        self._aof_file: Optional[object] = None

        # Stats tracking
        self._stats: Dict[str, int] = {
            "commands_processed": 0,
            "connections_total": 0,
        }

    # ------------------------------------------------------------------
    # TTL / Expiry Management
    # ------------------------------------------------------------------

    def _cleanup_expired(self) -> None:
        """تنظيف المفاتيح المنتهية الصلاحية - Remove expired keys using the expiry heap."""
        now: float = time.monotonic()
        while self.expiry_heap and self.expiry_heap[0].expire_at <= now:
            entry: ExpiryEntry = heapq.heappop(self.expiry_heap)
            if entry.key in self.ttl_map and self.ttl_map[entry.key] <= now:
                self.data.pop(entry.key, None)
                self.lists.pop(entry.key, None)
                self.ttl_map.pop(entry.key, None)

    def _check_ttl(self, key: str) -> bool:
        """التحقق مما إذا كان المفتاح لا يزال صالحاً - Check if a key is still valid."""
        if key in self.ttl_map:
            if time.monotonic() >= self.ttl_map[key]:
                self.data.pop(key, None)
                self.lists.pop(key, None)
                self.ttl_map.pop(key, None)
                return False
        return True

    # ------------------------------------------------------------------
    # AOF Persistence
    # ------------------------------------------------------------------

    def _aof_open(self) -> None:
        """فتح ملف AOF للإلحاق - Open AOF file for appending."""
        try:
            self._aof_file = open(self.aof_path, "a", encoding="utf-8")
        except OSError as exc:
            logger.error("فشل فتح ملف AOF: %s / AOF open failed: %s", exc, exc)

    def _aof_append(self, args: List[str]) -> None:
        """إلحاق أمر بملف AOF - Append a command to the AOF file."""
        if self._aof_file is not None:
            try:
                line: str = json.dumps(args, ensure_ascii=False) + "\n"
                self._aof_file.write(line)  # type: ignore[union-attr]
                self._aof_file.flush()  # type: ignore[union-attr]
            except OSError as exc:
                logger.error("فشل كتابة AOF: %s / AOF write failed: %s", exc, exc)

    def _aof_replay(self) -> None:
        """إعادة تشغيل الأوامر من ملف AOF - Replay commands from the AOF file."""
        if not os.path.exists(self.aof_path):
            return
        try:
            with open(self.aof_path, "r", encoding="utf-8") as fh:
                for line_no, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        args: List[str] = json.loads(raw)
                        self._execute_command(args, replay=True)
                    except (json.JSONDecodeError, Exception) as exc:
                        logger.warning("AOF سطر %d: %s / AOF line %d error: %s", line_no, exc, line_no, exc)
            logger.info("تم إعادة تشغيل AOF بنجاح / AOF replay completed")
        except OSError as exc:
            logger.error("فشل قراءة AOF: %s / AOF read failed: %s", exc, exc)

    def _aof_close(self) -> None:
        """إغلاق ملف AOF - Close the AOF file."""
        if self._aof_file is not None:
            try:
                self._aof_file.close()  # type: ignore[union-attr]
            except OSError:
                pass
            self._aof_file = None

    # ------------------------------------------------------------------
    # Command Execution
    # ------------------------------------------------------------------

    def _execute_command(self, args: List[str], replay: bool = False) -> Optional[bytes]:
        """تنفيذ أمر واحد - Execute a single command and return RESP response."""
        if not args:
            return RESPProtocol.encode_error("ERR no command")

        cmd: str = args[0].upper()
        self._stats["commands_processed"] += 1

        if not replay:
            self._cleanup_expired()

        # --- String Commands ---
        if cmd == "PING":
            if len(args) > 1:
                return RESPProtocol.encode_bulk_string(args[1])
            return self.PONG

        elif cmd == "SET":
            if len(args) < 3:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'SET'")
            key, value = args[1], args[2]
            self.data[key] = value
            self.ttl_map.pop(key, None)
            if not replay:
                self._aof_append(args)
            return self.OK

        elif cmd == "GET":
            if len(args) < 2:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'GET'")
            key = args[1]
            if not self._check_ttl(key):
                return self.NIL
            return RESPProtocol.encode_bulk_string(self.data.get(key))

        elif cmd == "DEL":
            if len(args) < 2:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'DEL'")
            count: int = 0
            for key in args[1:]:
                if key in self.data:
                    del self.data[key]
                    self.ttl_map.pop(key, None)
                    self.lists.pop(key, None)
                    count += 1
            if not replay:
                self._aof_append(args)
            return RESPProtocol.encode_integer(count)

        elif cmd == "EXPIRE":
            if len(args) < 3:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'EXPIRE'")
            key = args[1]
            try:
                seconds: int = int(args[2])
            except ValueError:
                return RESPProtocol.encode_error("ERR value is not an integer or out of range")
            if key not in self.data and key not in self.lists:
                return RESPProtocol.encode_integer(0)
            self.ttl_map[key] = time.monotonic() + seconds
            heapq.heappush(self.expiry_heap, ExpiryEntry(self.ttl_map[key], key))
            if not replay:
                self._aof_append(args)
            return RESPProtocol.encode_integer(1)

        # --- List Commands ---
        elif cmd == "LPUSH":
            if len(args) < 3:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'LPUSH'")
            key = args[1]
            if key not in self.lists:
                self.lists[key] = []
            for val in args[2:]:
                self.lists[key].insert(0, val)
            if not replay:
                self._aof_append(args)
            return RESPProtocol.encode_integer(len(self.lists[key]))

        elif cmd == "RPOP":
            if len(args) < 2:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'RPOP'")
            key = args[1]
            if key not in self.lists or not self.lists[key]:
                return self.NIL
            value: str = self.lists[key].pop()
            if not self.lists[key]:
                del self.lists[key]
            if not replay:
                self._aof_append(args)
            return RESPProtocol.encode_bulk_string(value)

        # --- Pub/Sub ---
        elif cmd == "SUBSCRIBE":
            if len(args) < 2:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'SUBSCRIBE'")
            return None  # handled in client handler

        elif cmd == "PUBLISH":
            if len(args) < 3:
                return RESPProtocol.encode_error("ERR wrong number of arguments for 'PUBLISH'")
            channel, message = args[1], args[2]
            subscribers = self.channels.get(channel, set())
            msg_payload: bytes = RESPProtocol.encode_array(["message", channel, message])
            count: int = 0
            for writer in list(subscribers):
                try:
                    writer.write(msg_payload)
                    count += 1
                except OSError:
                    subscribers.discard(writer)
            return RESPProtocol.encode_integer(count)

        elif cmd == "INFO":
            info_dict: Dict[str, Any] = {
                "role": "medical_redis",
                "version": "1.0.0",
                "commands_processed": self._stats["commands_processed"],
                "connections_total": self._stats["connections_total"],
                "keys": len(self.data),
                "lists": len(self.lists),
                "channels": len(self.channels),
            }
            return RESPProtocol.encode_bulk_string(json.dumps(info_dict, indent=2))

        elif cmd == "DBSIZE":
            self._cleanup_expired()
            return RESPProtocol.encode_integer(len(self.data) + len(self.lists))

        elif cmd == "FLUSHDB":
            self.data.clear()
            self.lists.clear()
            self.ttl_map.clear()
            self.expiry_heap.clear()
            return self.OK

        else:
            return RESPProtocol.encode_error(f"ERR unknown command '{args[0]}'")

    # ------------------------------------------------------------------
    # Client Connection Handler
    # ------------------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """معالجة اتصال العميل - Handle a single client connection."""
        addr: Tuple[str, int] = writer.get_extra_info("peername")
        self._stats["connections_total"] += 1
        logger.info("اتصال جديد من %s / New connection from %s", addr, addr)

        subscribed_channels: Set[str] = set()

        try:
            while True:
                try:
                    args: List[str] = await RESPProtocol.parse(reader)
                except (ConnectionError, asyncio.IncompleteReadError, ConnectionResetError):
                    break

                if not args:
                    continue

                cmd: str = args[0].upper()

                # Handle SUBSCRIBE specially (requires writer reference)
                if cmd == "SUBSCRIBE":
                    for ch in args[1:]:
                        if ch not in self.channels:
                            self.channels[ch] = set()
                        self.channels[ch].add(writer)
                        subscribed_channels.add(ch)
                        writer.write(RESPProtocol.encode_array(["subscribe", ch, len(subscribed_channels)]))
                    await writer.drain()
                    continue

                elif cmd == "UNSUBSCRIBE":
                    channels_to_unsub: List[str] = args[1:] if len(args) > 1 else list(subscribed_channels)
                    for ch in channels_to_unsub:
                        if ch in self.channels:
                            self.channels[ch].discard(writer)
                            if not self.channels[ch]:
                                del self.channels[ch]
                        subscribed_channels.discard(ch)
                        writer.write(RESPProtocol.encode_array(["unsubscribe", ch, len(subscribed_channels)]))
                    await writer.drain()
                    continue

                response: Optional[bytes] = self._execute_command(args)
                if response is not None:
                    writer.write(response)
                    await writer.drain()

        except Exception as exc:
            logger.error("خطأ في معالجة العميل %s: %s / Client %s error: %s", addr, exc, addr, exc)
        finally:
            # Clean up subscriptions on disconnect
            for ch in list(subscribed_channels):
                if ch in self.channels:
                    self.channels[ch].discard(writer)
                    if not self.channels[ch]:
                        del self.channels[ch]
            try:
                writer.close()
                await writer.wait_closed()
            except OSError:
                pass
            logger.info("تم قطع اتصال %s / Disconnected %s", addr, addr)

    # ------------------------------------------------------------------
    # Server Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """بدء تشغيل خادم Redis - Start the Redis server."""
        self._aof_open()
        self._aof_replay()

        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        addrs: List[Tuple[str, int]] = list(server.sockets) if server.sockets else []
        logger.info(
            "خادم Redis الطبي يعمل على %s:%d / Medical Redis listening on %s:%d",
            self.host, self.port, self.host, self.port,
        )

        async with server:
            await server.serve_forever()

    def shutdown(self) -> None:
        """إيقاف الخادم بشكل نظيف - Gracefully shut down the server."""
        logger.info("جاري إيقاف خادم Redis الطبي / Shutting down Medical Redis...")
        self._aof_close()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """نقطة دخول سطر الأوامر - CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="خادم Redis الطبي غير المتزامن / Async Medical Redis Server",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="عنوان الاستماع / Bind address")
    parser.add_argument("--port", type=int, default=6380, help="منفذ الاستماع / Bind port")
    parser.add_argument("--aof", type=str, default="medical_redis.aof", help="مسار ملف AOF / AOF file path")
    cli_args: argparse.Namespace = parser.parse_args()

    redis_server: AsyncMedicalRedis = AsyncMedicalRedis(
        host=cli_args.host,
        port=cli_args.port,
        aof_path=cli_args.aof,
    )

    try:
        asyncio.run(redis_server.start())
    except KeyboardInterrupt:
        redis_server.shutdown()


if __name__ == "__main__":
    main()
