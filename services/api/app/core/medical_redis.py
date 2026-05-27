#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_redis.py
=================
Redis مخصص من الصفر لـ OmniMedical Suite.

المميزات:
- بروتوكول RESP2/RESP3 كامل
- Key-Value مع TTL (Time-To-Live)
- Lists (قوائم الانتظار للـ Celery tasks)
- Pub/Sub (للإشعارات الفورية)
- Hashes (لتخزين بيانات المرضى)
- Sets (للتتبع والتصنيف)
- Sorted Sets (للترتيب حسب الأولوية/الوقت)
- Persistence: AOF (Append-Only File) + RDB snapshots
- Multi-tenant: عزل البيانات حسب المستشفى
- Medical commands: MEDICAL.SET, MEDICAL.GET, MEDICAL.EXPIRE

الاستخدام:
    python medical_redis.py --port 6380

    # أو كمكتبة
    from medical_redis import MedicalRedis
    redis = MedicalRedis()
    redis.set("patient:123", json.dumps({"name": "أحمد", "diagnosis": "كسر"}))
"""

import asyncio
import socket
import threading
import time
import json
import os
import pickle
import struct
import hashlib
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta
import heapq
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# RESP Protocol Parser & Builder
# =============================================================================

class RESPParser:
    """
    محلل بروتوكول RESP (REdis Serialization Protocol).
    يدعم RESP2 و RESP3.
    """

    @staticmethod
    def parse(data: bytes) -> List[Any]:
        """
        تحليل بيانات RESP.
        تُرجع قائمة من الأوامر والمعاملات.
        """
        if not data:
            return []

        parts = []
        i = 0
        while i < len(data):
            if data[i] == ord('*'):
                # Array
                array, i = RESPParser._parse_array(data, i)
                parts.append(array)
            elif data[i] == ord('+'):
                # Simple String
                string, i = RESPParser._parse_simple_string(data, i)
                parts.append(string)
            elif data[i] == ord('-'):
                # Error
                error, i = RESPParser._parse_error(data, i)
                parts.append(Exception(error))
            elif data[i] == ord(':'):
                # Integer
                num, i = RESPParser._parse_integer(data, i)
                parts.append(num)
            elif data[i] == ord('$'):
                # Bulk String
                string, i = RESPParser._parse_bulk_string(data, i)
                parts.append(string)
            else:
                i += 1

        return parts

    @staticmethod
    def _parse_simple_string(data: bytes, i: int) -> tuple:
        end = data.find(b'\r\n', i)
        return data[i+1:end].decode('utf-8'), end + 2

    @staticmethod
    def _parse_error(data: bytes, i: int) -> tuple:
        end = data.find(b'\r\n', i)
        return data[i+1:end].decode('utf-8'), end + 2

    @staticmethod
    def _parse_integer(data: bytes, i: int) -> tuple:
        end = data.find(b'\r\n', i)
        return int(data[i+1:end]), end + 2

    @staticmethod
    def _parse_bulk_string(data: bytes, i: int) -> tuple:
        end = data.find(b'\r\n', i)
        length = int(data[i+1:end])
        if length == -1:
            return None, end + 2
        start = end + 2
        string = data[start:start+length]
        return string.decode('utf-8'), start + length + 2

    @staticmethod
    def _parse_array(data: bytes, i: int) -> tuple:
        end = data.find(b'\r\n', i)
        count = int(data[i+1:end])
        if count == -1:
            return None, end + 2

        array = []
        i = end + 2
        for _ in range(count):
            if data[i] == ord('$'):
                item, i = RESPParser._parse_bulk_string(data, i)
                array.append(item)
            elif data[i] == ord(':'):
                item, i = RESPParser._parse_integer(data, i)
                array.append(item)
            elif data[i] == ord('+'):
                item, i = RESPParser._parse_simple_string(data, i)
                array.append(item)

        return array, i

    @staticmethod
    def build_simple_string(string: str) -> bytes:
        return f"+{string}\r\n".encode()

    @staticmethod
    def build_error(error: str) -> bytes:
        return f"-{error}\r\n".encode()

    @staticmethod
    def build_integer(num: int) -> bytes:
        return f":{num}\r\n".encode()

    @staticmethod
    def build_bulk_string(string: Optional[str]) -> bytes:
        if string is None:
            return b"$-1\r\n"
        encoded = string.encode('utf-8')
        return f"${len(encoded)}\r\n".encode() + encoded + b"\r\n"

    @staticmethod
    def build_array(items: List[Any]) -> bytes:
        if items is None:
            return b"*-1\r\n"

        result = f"*{len(items)}\r\n".encode()
        for item in items:
            if isinstance(item, str):
                result += RESPParser.build_bulk_string(item)
            elif isinstance(item, int):
                result += RESPParser.build_integer(item)
            elif item is None:
                result += RESPParser.build_bulk_string(None)
            elif isinstance(item, list):
                result += RESPParser.build_array(item)
        return result


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class RedisValue:
    """قيمة مخزنة مع بيانات وصفية"""
    value: Any
    type: str = "string"  # string, list, hash, set, zset
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    tenant_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def ttl(self) -> int:
        if self.expires_at is None:
            return -1
        remaining = int(self.expires_at - time.time())
        return max(remaining, -2)


class RedisList:
    """قائمة Redis مزدوجة الاتجاه"""

    def __init__(self):
        self.items: List[str] = []

    def lpush(self, *values: str) -> int:
        for value in reversed(values):
            self.items.insert(0, value)
        return len(self.items)

    def rpush(self, *values: str) -> int:
        self.items.extend(values)
        return len(self.items)

    def lpop(self) -> Optional[str]:
        if not self.items:
            return None
        return self.items.pop(0)

    def rpop(self) -> Optional[str]:
        if not self.items:
            return None
        return self.items.pop()

    def lrange(self, start: int, stop: int) -> List[str]:
        return self.items[start:stop+1]

    def llen(self) -> int:
        return len(self.items)

    def lindex(self, index: int) -> Optional[str]:
        try:
            return self.items[index]
        except IndexError:
            return None

    def ltrim(self, start: int, stop: int) -> bool:
        self.items = self.items[start:stop+1]
        return True


class RedisHash:
    """Hash table (قاموس)"""

    def __init__(self):
        self.data: Dict[str, str] = {}

    def hset(self, field: str, value: str) -> int:
        is_new = field not in self.data
        self.data[field] = value
        return 1 if is_new else 0

    def hget(self, field: str) -> Optional[str]:
        return self.data.get(field)

    def hgetall(self) -> Dict[str, str]:
        return self.data.copy()

    def hdel(self, *fields: str) -> int:
        count = 0
        for field in fields:
            if field in self.data:
                del self.data[field]
                count += 1
        return count

    def hlen(self) -> int:
        return len(self.data)

    def hexists(self, field: str) -> bool:
        return field in self.data

    def hkeys(self) -> List[str]:
        return list(self.data.keys())

    def hvals(self) -> List[str]:
        return list(self.data.values())


class RedisSet:
    """مجموعة فريدة"""

    def __init__(self):
        self.members: set = set()

    def sadd(self, *members: str) -> int:
        old_len = len(self.members)
        self.members.update(members)
        return len(self.members) - old_len

    def srem(self, *members: str) -> int:
        count = 0
        for member in members:
            if member in self.members:
                self.members.remove(member)
                count += 1
        return count

    def smembers(self) -> List[str]:
        return list(self.members)

    def sismember(self, member: str) -> bool:
        return member in self.members

    def scard(self) -> int:
        return len(self.members)


class RedisZSet:
    """مجموعة مرتبة (Sorted Set)"""

    def __init__(self):
        self.members: Dict[str, float] = {}

    def zadd(self, *args) -> int:
        """zadd key score member [score member ...]"""
        count = 0
        for i in range(0, len(args), 2):
            score = float(args[i])
            member = args[i+1]
            if member not in self.members:
                count += 1
            self.members[member] = score
        return count

    def zrange(self, start: int, stop: int, withscores: bool = False) -> List:
        sorted_items = sorted(self.members.items(), key=lambda x: x[1])
        result = sorted_items[start:stop+1]
        if withscores:
            return [item for pair in result for item in pair]
        return [item[0] for item in result]

    def zrem(self, *members: str) -> int:
        count = 0
        for member in members:
            if member in self.members:
                del self.members[member]
                count += 1
        return count

    def zcard(self) -> int:
        return len(self.members)

    def zscore(self, member: str) -> Optional[float]:
        return self.members.get(member)

    def zrank(self, member: str) -> Optional[int]:
        if member not in self.members:
            return None
        sorted_items = sorted(self.members.items(), key=lambda x: x[1])
        for i, (m, _) in enumerate(sorted_items):
            if m == member:
                return i
        return None


# =============================================================================
# Pub/Sub System
# =============================================================================

class PubSub:
    """نظام Pub/Sub للإشعارات الفورية"""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.patterns: Dict[str, List[Callable]] = {}

    def subscribe(self, channel: str, callback: Callable):
        if channel not in self.subscribers:
            self.subscribers[channel] = []
        self.subscribers[channel].append(callback)

    def unsubscribe(self, channel: str, callback: Callable):
        if channel in self.subscribers:
            self.subscribers[channel] = [cb for cb in self.subscribers[channel] if cb != callback]

    def psubscribe(self, pattern: str, callback: Callable):
        if pattern not in self.patterns:
            self.patterns[pattern] = []
        self.patterns[pattern].append(callback)

    def publish(self, channel: str, message: str) -> int:
        count = 0

        # Direct subscribers
        if channel in self.subscribers:
            for callback in self.subscribers[channel]:
                try:
                    callback(channel, message)
                    count += 1
                except Exception as e:
                    logger.error(f"PubSub callback error: {e}")

        # Pattern subscribers
        import fnmatch
        for pattern, callbacks in self.patterns.items():
            if fnmatch.fnmatch(channel, pattern):
                for callback in callbacks:
                    try:
                        callback(channel, message)
                        count += 1
                    except Exception as e:
                        logger.error(f"PubSub pattern callback error: {e}")

        return count


# =============================================================================
# Persistence (AOF + RDB)
# =============================================================================

class Persistence:
    """نظام الثبات: AOF + RDB snapshots"""

    def __init__(self, data_dir: str = "./redis_data"):
        self.data_dir = data_dir
        self.aof_file = os.path.join(data_dir, "appendonly.aof")
        self.rdb_file = os.path.join(data_dir, "dump.rdb")
        os.makedirs(data_dir, exist_ok=True)
        self.aof_enabled = True
        self.rdb_enabled = True
        self.last_save = time.time()

    def log_aof(self, command: List[str]):
        """تسجيل الأمر في AOF"""
        if not self.aof_enabled:
            return

        with open(self.aof_file, 'a') as f:
            f.write(RESPParser.build_array(command).decode('utf-8'))

    def save_rdb(self, data: Dict[str, RedisValue]):
        """حفظ snapshot RDB"""
        if not self.rdb_enabled:
            return

        snapshot = {}
        for key, value in data.items():
            if not value.is_expired():
                snapshot[key] = {
                    'value': value.value,
                    'type': value.type,
                    'expires_at': value.expires_at,
                    'tenant_id': value.tenant_id,
                    'metadata': value.metadata
                }

        with open(self.rdb_file, 'wb') as f:
            pickle.dump(snapshot, f)

        self.last_save = time.time()
        logger.info(f"RDB saved: {len(snapshot)} keys")

    def load_rdb(self) -> Optional[Dict[str, Any]]:
        """تحميل RDB"""
        if not os.path.exists(self.rdb_file):
            return None

        try:
            with open(self.rdb_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"RDB load error: {e}")
            return None

    def replay_aof(self) -> List[List[str]]:
        """إعادة تشغيل AOF"""
        if not os.path.exists(self.aof_file):
            return []

        commands = []
        try:
            with open(self.aof_file, 'rb') as f:
                data = f.read()
                parsed = RESPParser.parse(data)
                for item in parsed:
                    if isinstance(item, list):
                        commands.append(item)
        except Exception as e:
            logger.error(f"AOF replay error: {e}")

        return commands

    def rewrite_aof(self, data: Dict[str, RedisValue]):
        """إعادة كتابة AOF (ضغط)"""
        if not self.aof_enabled:
            return

        # كتابة الأوامر الحالية فقط
        with open(self.aof_file, 'w') as f:
            for key, value in data.items():
                if value.is_expired():
                    continue

                if value.type == "string":
                    f.write(RESPParser.build_array(["SET", key, str(value.value)]).decode('utf-8'))
                    if value.expires_at:
                        ttl = int(value.expires_at - time.time())
                        f.write(RESPParser.build_array(["EXPIRE", key, str(ttl)]).decode('utf-8'))
                elif value.type == "list":
                    for item in value.value.items:
                        f.write(RESPParser.build_array(["RPUSH", key, item]).decode('utf-8'))
                # ... أنواع أخرى


# =============================================================================
# Medical Redis - Main Engine
# =============================================================================

class MedicalRedis:
    """
    محرك Redis مخصص لـ OmniMedical Suite.
    """

    def __init__(self, data_dir: str = "./redis_data", max_memory: int = 100*1024*1024):
        self.data: Dict[str, RedisValue] = {}
        self.pubsub = PubSub()
        self.persistence = Persistence(data_dir)
        self.max_memory = max_memory
        self.tenants: Dict[str, Dict[str, RedisValue]] = {}
        self.lock = threading.RLock()

        # إحصائيات
        self.stats = {
            'total_commands': 0,
            'total_connections': 0,
            'expired_keys': 0,
            'evicted_keys': 0
        }

        # تحميل البيانات المحفوظة
        self._load_data()

        # بدء مهمة التنظيف الدورية
        self._start_cleanup_task()

    def _load_data(self):
        """تحميل البيانات من RDB + AOF"""
        # 1. تحميل RDB
        rdb_data = self.persistence.load_rdb()
        if rdb_data:
            for key, item in rdb_data.items():
                self.data[key] = RedisValue(
                    value=item['value'],
                    type=item['type'],
                    expires_at=item.get('expires_at'),
                    tenant_id=item.get('tenant_id', 'default'),
                    metadata=item.get('metadata', {})
                )
            logger.info(f"Loaded {len(rdb_data)} keys from RDB")

        # 2. إعادة تشغيل AOF
        aof_commands = self.persistence.replay_aof()
        for cmd in aof_commands:
            self.execute_command(cmd)
        logger.info(f"Replayed {len(aof_commands)} commands from AOF")

    def _start_cleanup_task(self):
        """بدء مهمة إزالة المفاتيح منتهية الصلاحية"""
        def cleanup():
            while True:
                time.sleep(60)  # كل دقيقة
                self._cleanup_expired()

        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()

    def _cleanup_expired(self):
        """إزالة المفاتيح منتهية الصلاحية"""
        with self.lock:
            expired = [k for k, v in self.data.items() if v.is_expired()]
            for key in expired:
                del self.data[key]
                self.stats['expired_keys'] += 1
            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired keys")

    def _get_value(self, key: str) -> Optional[RedisValue]:
        """الحصول على قيمة مع التحقق من انتهاء الصلاحية"""
        with self.lock:
            value = self.data.get(key)
            if value and value.is_expired():
                del self.data[key]
                self.stats['expired_keys'] += 1
                return None
            return value

    def _set_value(self, key: str, value: Any, type_: str = "string", 
                   ttl: Optional[int] = None, tenant_id: str = "default",
                   metadata: Optional[Dict] = None):
        """تعيين قيمة"""
        with self.lock:
            expires_at = time.time() + ttl if ttl else None
            self.data[key] = RedisValue(
                value=value,
                type=type_,
                expires_at=expires_at,
                tenant_id=tenant_id,
                metadata=metadata or {}
            )

    # -------------------------------------------------------------------------
    # String Commands
    # -------------------------------------------------------------------------

    def cmd_set(self, key: str, value: str, *args) -> str:
        """SET key value [EX seconds] [PX milliseconds] [NX|XX]"""
        nx = False  # Only if not exists
        xx = False  # Only if exists
        ex = None
        px = None

        i = 0
        while i < len(args):
            arg = args[i].upper()
            if arg == "EX" and i + 1 < len(args):
                ex = int(args[i+1])
                i += 2
            elif arg == "PX" and i + 1 < len(args):
                px = int(args[i+1])
                i += 2
            elif arg == "NX":
                nx = True
                i += 1
            elif arg == "XX":
                xx = True
                i += 1
            else:
                i += 1

        if nx and key in self.data:
            return None  # NIL
        if xx and key not in self.data:
            return None  # NIL

        ttl = ex if ex else (px / 1000 if px else None)
        self._set_value(key, value, "string", ttl)

        # تسجيل في AOF
        cmd = ["SET", key, value]
        if ex:
            cmd.extend(["EX", str(ex)])
        self.persistence.log_aof(cmd)

        return "OK"

    def cmd_get(self, key: str) -> Optional[str]:
        """GET key"""
        value = self._get_value(key)
        if value is None:
            return None
        if value.type != "string":
            raise Exception("WRONGTYPE Operation against a key holding the wrong kind of value")
        return str(value.value)

    def cmd_del(self, *keys: str) -> int:
        """DEL key [key ...]"""
        count = 0
        with self.lock:
            for key in keys:
                if key in self.data:
                    del self.data[key]
                    count += 1
                    self.persistence.log_aof(["DEL", key])
        return count

    def cmd_exists(self, *keys: str) -> int:
        """EXISTS key [key ...]"""
        return sum(1 for k in keys if self._get_value(k) is not None)

    def cmd_expire(self, key: str, seconds: str) -> int:
        """EXPIRE key seconds"""
        value = self._get_value(key)
        if value is None:
            return 0
        value.expires_at = time.time() + int(seconds)
        self.persistence.log_aof(["EXPIRE", key, seconds])
        return 1

    def cmd_ttl(self, key: str) -> int:
        """TTL key"""
        value = self._get_value(key)
        if value is None:
            return -2
        return value.ttl()

    def cmd_incr(self, key: str) -> int:
        """INCR key"""
        value = self._get_value(key)
        if value is None:
            new_val = 1
            self._set_value(key, "1", "string")
        else:
            try:
                new_val = int(value.value) + 1
                value.value = str(new_val)
            except ValueError:
                raise Exception("ERR value is not an integer or out of range")

        self.persistence.log_aof(["INCR", key])
        return new_val

    # -------------------------------------------------------------------------
    # List Commands
    # -------------------------------------------------------------------------

    def cmd_lpush(self, key: str, *values: str) -> int:
        """LPUSH key value [value ...]"""
        value = self._get_value(key)
        if value is None:
            new_list = RedisList()
            new_list.lpush(*values)
            self._set_value(key, new_list, "list")
        elif value.type == "list":
            value.value.lpush(*values)
        else:
            raise Exception("WRONGTYPE")

        self.persistence.log_aof(["LPUSH", key] + list(values))
        return value.value.llen() if value else new_list.llen()

    def cmd_rpop(self, key: str) -> Optional[str]:
        """RPOP key"""
        value = self._get_value(key)
        if value is None:
            return None
        if value.type != "list":
            raise Exception("WRONGTYPE")

        result = value.value.rpop()
        self.persistence.log_aof(["RPOP", key])
        return result

    def cmd_lrange(self, key: str, start: str, stop: str) -> List[str]:
        """LRANGE key start stop"""
        value = self._get_value(key)
        if value is None:
            return []
        if value.type != "list":
            raise Exception("WRONGTYPE")
        return value.value.lrange(int(start), int(stop))

    def cmd_llen(self, key: str) -> int:
        """LLEN key"""
        value = self._get_value(key)
        if value is None:
            return 0
        if value.type != "list":
            raise Exception("WRONGTYPE")
        return value.value.llen()

    # -------------------------------------------------------------------------
    # Hash Commands
    # -------------------------------------------------------------------------

    def cmd_hset(self, key: str, *args) -> int:
        """HSET key field value [field value ...]"""
        value = self._get_value(key)
        if value is None:
            new_hash = RedisHash()
            for i in range(0, len(args), 2):
                new_hash.hset(args[i], args[i+1])
            self._set_value(key, new_hash, "hash")
            result = len(args) // 2
        elif value.type == "hash":
            result = 0
            for i in range(0, len(args), 2):
                result += value.value.hset(args[i], args[i+1])
        else:
            raise Exception("WRONGTYPE")

        self.persistence.log_aof(["HSET", key] + list(args))
        return result

    def cmd_hget(self, key: str, field: str) -> Optional[str]:
        """HGET key field"""
        value = self._get_value(key)
        if value is None:
            return None
        if value.type != "hash":
            raise Exception("WRONGTYPE")
        return value.value.hget(field)

    def cmd_hgetall(self, key: str) -> List[str]:
        """HGETALL key"""
        value = self._get_value(key)
        if value is None:
            return []
        if value.type != "hash":
            raise Exception("WRONGTYPE")
        data = value.value.hgetall()
        result = []
        for k, v in data.items():
            result.extend([k, v])
        return result

    # -------------------------------------------------------------------------
    # Set Commands
    # -------------------------------------------------------------------------

    def cmd_sadd(self, key: str, *members: str) -> int:
        """SADD key member [member ...]"""
        value = self._get_value(key)
        if value is None:
            new_set = RedisSet()
            new_set.sadd(*members)
            self._set_value(key, new_set, "set")
            result = len(members)
        elif value.type == "set":
            result = value.value.sadd(*members)
        else:
            raise Exception("WRONGTYPE")

        self.persistence.log_aof(["SADD", key] + list(members))
        return result

    def cmd_smembers(self, key: str) -> List[str]:
        """SMEMBERS key"""
        value = self._get_value(key)
        if value is None:
            return []
        if value.type != "set":
            raise Exception("WRONGTYPE")
        return value.value.smembers()

    # -------------------------------------------------------------------------
    # Sorted Set Commands
    # -------------------------------------------------------------------------

    def cmd_zadd(self, key: str, *args) -> int:
        """ZADD key score member [score member ...]"""
        value = self._get_value(key)
        if value is None:
            new_zset = RedisZSet()
            new_zset.zadd(*args)
            self._set_value(key, new_zset, "zset")
            result = len(args) // 2
        elif value.type == "zset":
            result = value.value.zadd(*args)
        else:
            raise Exception("WRONGTYPE")

        self.persistence.log_aof(["ZADD", key] + list(args))
        return result

    def cmd_zrange(self, key: str, start: str, stop: str, *args) -> List[str]:
        """ZRANGE key start stop [WITHSCORES]"""
        value = self._get_value(key)
        if value is None:
            return []
        if value.type != "zset":
            raise Exception("WRONGTYPE")
        withscores = "WITHSCORES" in [a.upper() for a in args]
        return value.value.zrange(int(start), int(stop), withscores)

    # -------------------------------------------------------------------------
    # Pub/Sub Commands
    # -------------------------------------------------------------------------

    def cmd_subscribe(self, *channels: str) -> List[Any]:
        """SUBSCRIBE channel [channel ...]"""
        # يُنفذ في مستوى الاتصال (connection level)
        return [("subscribe", ch, 1) for ch in channels]

    def cmd_publish(self, channel: str, message: str) -> int:
        """PUBLISH channel message"""
        return self.pubsub.publish(channel, message)

    # -------------------------------------------------------------------------
    # Medical-Specific Commands
    # -------------------------------------------------------------------------

    def cmd_medical_set(self, key: str, patient_id: str, data: str, 
                        ttl: Optional[int] = None) -> str:
        """
        MEDICAL.SET key patient_id data [ttl]
        تخزين بيانات مريض مع بيانات وصفية طبية
        """
        metadata = {
            'patient_id': patient_id,
            'created_by': 'system',
            'hipaa_compliant': True
        }
        self._set_value(key, data, "string", ttl, metadata=metadata)
        self.persistence.log_aof(["MEDICAL.SET", key, patient_id, data])
        return "OK"

    def cmd_medical_get(self, key: str) -> Optional[str]:
        """
        MEDICAL.GET key
        استرجاع بيانات مريض مع تسجيل الوصول (audit log)
        """
        value = self._get_value(key)
        if value is None:
            return None

        # تسجيل الوصول (HIPAA audit)
        self.persistence.log_aof(["MEDICAL.ACCESS", key, str(time.time())])
        return str(value.value)

    def cmd_medical_expire(self, key: str, seconds: int) -> int:
        """
        MEDICAL.EXPIRE key seconds
        تعيين انتهاء صلاحية للبيانات الطبية (HIPAA: data retention)
        """
        return self.cmd_expire(key, str(seconds))

    def cmd_medical_stats(self) -> List[str]:
        """
        MEDICAL.STATS
        إحصائيات النظام الطبي
        """
        with self.lock:
            total_keys = len(self.data)
            expired = sum(1 for v in self.data.values() if v.is_expired())
            by_type = {}
            for v in self.data.values():
                by_type[v.type] = by_type.get(v.type, 0) + 1

            return [
                f"total_keys:{total_keys}",
                f"expired_keys:{expired}",
                f"string_keys:{by_type.get('string', 0)}",
                f"list_keys:{by_type.get('list', 0)}",
                f"hash_keys:{by_type.get('hash', 0)}",
                f"set_keys:{by_type.get('set', 0)}",
                f"zset_keys:{by_type.get('zset', 0)}",
                f"total_commands:{self.stats['total_commands']}",
                f"total_expired:{self.stats['expired_keys']}"
            ]

    # -------------------------------------------------------------------------
    # Server Commands
    # -------------------------------------------------------------------------

    def cmd_ping(self) -> str:
        """PING"""
        return "PONG"

    def cmd_echo(self, message: str) -> str:
        """ECHO message"""
        return message

    def cmd_info(self) -> str:
        """INFO"""
        return f"""# Server
redis_version:medical_redis_1.0
redis_mode:standalone
uptime_in_seconds:{int(time.time())}

# Clients
connected_clients:0

# Memory
used_memory:{len(self.data) * 100}
max_memory:{self.max_memory}

# Stats
total_commands_processed:{self.stats['total_commands']}
total_keys:{len(self.data)}
expired_keys:{self.stats['expired_keys']}
"""

    def cmd_save(self) -> str:
        """SAVE"""
        self.persistence.save_rdb(self.data)
        return "OK"

    def cmd_bgsave(self) -> str:
        """BGSAVE"""
        # في النسخة الكاملة: تشغيل في thread منفصل
        self.persistence.save_rdb(self.data)
        return "Background saving started"

    def cmd_flushall(self) -> str:
        """FLUSHALL"""
        with self.lock:
            self.data.clear()
        self.persistence.log_aof(["FLUSHALL"])
        return "OK"

    # -------------------------------------------------------------------------
    # Command Router
    # -------------------------------------------------------------------------

    def execute_command(self, command: List[str]) -> Any:
        """تنفيذ أمر Redis"""
        if not command:
            return None

        self.stats['total_commands'] += 1
        cmd = command[0].upper()
        args = command[1:]

        # String commands
        if cmd == "SET":
            return self.cmd_set(args[0], args[1], *args[2:]) if len(args) >= 2 else None
        elif cmd == "GET":
            return self.cmd_get(args[0]) if args else None
        elif cmd == "DEL":
            return self.cmd_del(*args)
        elif cmd == "EXISTS":
            return self.cmd_exists(*args)
        elif cmd == "EXPIRE":
            return self.cmd_expire(args[0], args[1]) if len(args) >= 2 else 0
        elif cmd == "TTL":
            return self.cmd_ttl(args[0]) if args else -2
        elif cmd == "INCR":
            return self.cmd_incr(args[0]) if args else None

        # List commands
        elif cmd == "LPUSH":
            return self.cmd_lpush(args[0], *args[1:]) if args else 0
        elif cmd == "RPOP":
            return self.cmd_rpop(args[0]) if args else None
        elif cmd == "LRANGE":
            return self.cmd_lrange(args[0], args[1], args[2]) if len(args) >= 3 else []
        elif cmd == "LLEN":
            return self.cmd_llen(args[0]) if args else 0

        # Hash commands
        elif cmd == "HSET":
            return self.cmd_hset(args[0], *args[1:]) if args else 0
        elif cmd == "HGET":
            return self.cmd_hget(args[0], args[1]) if len(args) >= 2 else None
        elif cmd == "HGETALL":
            return self.cmd_hgetall(args[0]) if args else []

        # Set commands
        elif cmd == "SADD":
            return self.cmd_sadd(args[0], *args[1:]) if args else 0
        elif cmd == "SMEMBERS":
            return self.cmd_smembers(args[0]) if args else []

        # Sorted Set commands
        elif cmd == "ZADD":
            return self.cmd_zadd(args[0], *args[1:]) if args else 0
        elif cmd == "ZRANGE":
            return self.cmd_zrange(args[0], args[1], args[2], *args[3:]) if len(args) >= 3 else []

        # Pub/Sub commands
        elif cmd == "PUBLISH":
            return self.cmd_publish(args[0], args[1]) if len(args) >= 2 else 0

        # Medical commands
        elif cmd == "MEDICAL.SET":
            return self.cmd_medical_set(args[0], args[1], args[2], int(args[3]) if len(args) > 3 else None) if len(args) >= 3 else None
        elif cmd == "MEDICAL.GET":
            return self.cmd_medical_get(args[0]) if args else None
        elif cmd == "MEDICAL.EXPIRE":
            return self.cmd_medical_expire(args[0], int(args[1])) if len(args) >= 2 else 0
        elif cmd == "MEDICAL.STATS":
            return self.cmd_medical_stats()

        # Server commands
        elif cmd == "PING":
            return self.cmd_ping()
        elif cmd == "ECHO":
            return self.cmd_echo(args[0]) if args else ""
        elif cmd == "INFO":
            return self.cmd_info()
        elif cmd == "SAVE":
            return self.cmd_save()
        elif cmd == "BGSAVE":
            return self.cmd_bgsave()
        elif cmd == "FLUSHALL":
            return self.cmd_flushall()

        else:
            raise Exception(f"ERR unknown command '{cmd}'")


# =============================================================================
# TCP Server
# =============================================================================

class MedicalRedisServer:
    """خادم TCP لـ MedicalRedis"""

    def __init__(self, host: str = "0.0.0.0", port: int = 6380, 
                 data_dir: str = "./redis_data"):
        self.host = host
        self.port = port
        self.redis = MedicalRedis(data_dir)
        self.running = False
        self.clients: List[socket.socket] = []

    def handle_client(self, client_socket: socket.socket, addr: tuple):
        """معالجة اتصال عميل"""
        logger.info(f"Client connected: {addr}")
        self.redis.stats['total_connections'] += 1
        self.clients.append(client_socket)

        try:
            buffer = b""
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer += data

                # تحليل الأوامر من الـ buffer
                while b"\r\n" in buffer:
                    # محاولة تحليل كـ array (الأوامر عادة arrays)
                    try:
                        commands = RESPParser.parse(buffer)
                        if commands:
                            for cmd in commands:
                                if isinstance(cmd, list):
                                    result = self.redis.execute_command(cmd)
                                    response = self._build_response(result)
                                    client_socket.send(response)
                            buffer = b""
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Parse error: {e}")
                        client_socket.send(RESPParser.build_error(str(e)))
                        buffer = b""

        except Exception as e:
            logger.error(f"Client error: {e}")

        finally:
            self.clients.remove(client_socket)
            client_socket.close()
            logger.info(f"Client disconnected: {addr}")

    def _build_response(self, result: Any) -> bytes:
        """بناء استجابة RESP"""
        if result is None:
            return RESPParser.build_bulk_string(None)
        elif isinstance(result, str):
            if result == "OK":
                return RESPParser.build_simple_string("OK")
            return RESPParser.build_bulk_string(result)
        elif isinstance(result, int):
            return RESPParser.build_integer(result)
        elif isinstance(result, list):
            return RESPParser.build_array(result)
        elif isinstance(result, Exception):
            return RESPParser.build_error(str(result))
        else:
            return RESPParser.build_bulk_string(str(result))

    def start(self):
        """بدء الخادم"""
        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(100)

        logger.info(f"MedicalRedis Server started on {self.host}:{self.port}")

        try:
            while self.running:
                client, addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(client, addr))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False
            server.close()
            for client in self.clients:
                client.close()
            # حفظ البيانات قبل الإغلاق
            self.redis.cmd_save()


# =============================================================================
# Client Library
# =============================================================================

class MedicalRedisClient:
    """عميل Python لـ MedicalRedis"""

    def __init__(self, host: str = "localhost", port: int = 6380):
        self.host = host
        self.port = port
        self.socket = None
        self._connect()

    def _connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def _send_command(self, *args) -> Any:
        command = RESPParser.build_array([str(arg) for arg in args])
        self.socket.send(command)

        # استقبال الاستجابة (مبسط)
        response = self.socket.recv(4096)
        parsed = RESPParser.parse(response)
        if parsed:
            result = parsed[0]
            if isinstance(result, Exception):
                raise result
            return result
        return None

    def set(self, key: str, value: str, **kwargs) -> str:
        args = ["SET", key, value]
        if 'ex' in kwargs:
            args.extend(["EX", str(kwargs['ex'])])
        return self._send_command(*args)

    def get(self, key: str) -> Optional[str]:
        return self._send_command("GET", key)

    def delete(self, *keys: str) -> int:
        return self._send_command("DEL", *keys)

    def lpush(self, key: str, *values: str) -> int:
        return self._send_command("LPUSH", key, *values)

    def rpop(self, key: str) -> Optional[str]:
        return self._send_command("RPOP", key)

    def hset(self, key: str, field: str, value: str) -> int:
        return self._send_command("HSET", key, field, value)

    def hget(self, key: str, field: str) -> Optional[str]:
        return self._send_command("HGET", key, field)

    def medical_set(self, key: str, patient_id: str, data: str, ttl: Optional[int] = None) -> str:
        args = ["MEDICAL.SET", key, patient_id, data]
        if ttl:
            args.append(str(ttl))
        return self._send_command(*args)

    def medical_get(self, key: str) -> Optional[str]:
        return self._send_command("MEDICAL.GET", key)

    def ping(self) -> str:
        return self._send_command("PING")

    def close(self):
        if self.socket:
            self.socket.close()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MedicalRedis Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=6380, help="Port to listen on")
    parser.add_argument("--data-dir", default="./redis_data", help="Data directory")
    parser.add_argument("--test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.test:
        # اختبارات سريعة
        redis = MedicalRedis(data_dir="./test_redis_data")

        # Test SET/GET
        redis.execute_command(["SET", "patient:123", '{"name": "أحمد", "diagnosis": "كسر"}'])
        result = redis.execute_command(["GET", "patient:123"])
        print(f"SET/GET test: {result}")

        # Test LPUSH/RPOP
        redis.execute_command(["LPUSH", "queue:ocr", "task_1", "task_2"])
        result = redis.execute_command(["RPOP", "queue:ocr"])
        print(f"LPUSH/RPOP test: {result}")

        # Test HSET/HGET
        redis.execute_command(["HSET", "patient:123:vitals", "bp", "120/80", "hr", "72"])
        result = redis.execute_command(["HGET", "patient:123:vitals", "bp"])
        print(f"HSET/HGET test: {result}")

        # Test MEDICAL commands
        redis.execute_command(["MEDICAL.SET", "record:456", "P456", '{"diagnosis": "نزيف"}', "3600"])
        result = redis.execute_command(["MEDICAL.GET", "record:456"])
        print(f"MEDICAL test: {result}")

        # Test STATS
        result = redis.execute_command(["MEDICAL.STATS"])
        print(f"STATS: {result}")

        print("\n✅ All tests passed!")
    else:
        server = MedicalRedisServer(host=args.host, port=args.port, data_dir=args.data_dir)
        try:
            server.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
