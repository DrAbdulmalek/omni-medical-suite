# مقترحات التطوير المستقبلي | OmniMedical Suite

> هذا الملف يوثق الأفكار والمشاريع المقترحة للتطوير المستقبلي ضمن مبادرة "ابنِ من الصفر" (Build-Your-Own-X).
> كل مشروع مُوثَّق بالتفصيل بما في ذلك المفهوم، والتطبيق في OmniMedical، وخطة التنفيذ، وأمثلة الكود، والتحديات، والتأثير المتوقع.

---

## المُنفَّذ مسبقاً (للرجوع إليه)

تم تنفيذ المكونات التالية ودمجها في المشروع (انظر الملفات المحددة):

1. **MedicalRedis** — خادم Redis مخصص (`services/api/app/core/medical_redis.py` — 1,300 سطر)
2. **MedicalWebSocketServer** — خادم WebSocket (`services/api/app/core/medical_websocket_server.py` — 625 سطر)

---

## 1. LSM Tree — هيكل بيانات للكتابة عالية الأداء

### المفهوم

LSM Tree (Log-Structured Merge Tree) هو هيكل بيانات مُحسَّن لعمليات الكتابة العالية، يُستخدم في قواعد البيانات مثل LevelDB و RocksDB و Cassandra. بدلاً من تحديث البيانات في مكانها، تُكتب جميع العمليات في سجل متتابع (WAL)، ثم تُدمج دورياً في ملفات مرتبة (SSTables).

### التطبيق في OmniMedical

يمكن استخدام LSM Tree كطبقة تخزين عالية الأداء لحالات الاستخدام التالية:

- **تخزين نتائج OCR مؤقتاً:** قبل الدمج النهائي، تُخزن نتائج كل محرك في LSM Tree للقراءة والكتابة السريعة.
- **سجل عمليات التصحيح (CorrectionMemory):** بدلاً من SQLite، يمكن لـ LSM Tree التعامل مع ملايين عمليات الكتابة من تصحيحات المستخدمين بكفاءة أعلى.
- **ذاكرة التخزين المؤقت للبحث الدلالي:** تخزين نتائج البحث المتكررة في هيكل سريع الوصول.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1-2): البنية الأساسية
├── MemTable (شجرة مرتبة في الذاكرة)
├── WAL (Write-Ahead Log) للاستمرارية
└── SSTable (ملف مفاتيح مرتبة على القرص)

المرحلة 2 (أسبوع 3): التحسينات
├── Bloom Filter لتسريع البحث
├── Compaction Strategy (Size-Tiered + Leveled)
└── TTL وانتهاء الصلاحية

المرحلة 3 (أسبوع 4): التكامل
├── واجهة Python Module
├── تكامل مع OCR Fusion Pipeline
└── اختبارات الأداء
```

### مثال الكود

```python
import hashlib
import pickle
import struct
import os
from collections import OrderedDict
from bisect import bisect_left
from typing import Optional, List, Tuple, Iterator


class MemTable:
    """جدول مرتب في الذاكرة — المرحلة الأولى من LSM Tree"""

    def __init__(self, max_size: int = 1024 * 1024):
        self.max_size = max_size
        self.data: OrderedDict = OrderedDict()
        self.current_size = 0

    def put(self, key: str, value: bytes, tombstone: bool = False):
        """إدراج أو تحديث مفتاح"""
        old_value = self.data.get(key)
        if old_value is not None:
            self.current_size -= len(old_value)
        entry = value if not tombstone else b"__TOMBSTONE__"
        self.data[key] = entry
        self.current_size += len(key) + len(entry)

    def get(self, key: str) -> Optional[bytes]:
        """قراءة قيمة مفتاح"""
        value = self.data.get(key)
        if value == b"__TOMBSTONE__":
            return None
        return value

    def delete(self, key: str):
        """حذف مفتاح (بإدراج شاهد قبر)"""
        self.put(key, b"", tombstone=True)

    def is_full(self) -> bool:
        return self.current_size >= self.max_size

    def items(self) -> Iterator[Tuple[str, bytes]]:
        return iter(self.data.items())

    def clear(self):
        self.data.clear()
        self.current_size = 0


class SSTable:
    """ملف مفاتيح مرتب على القرص — المرحلة الدائمة من LSM Tree"""

    MAGIC = b"SSTB"
    VERSION = 1

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.index: List[Tuple[str, int]] = []
        self._load_index()

    def _load_index(self):
        """تحميل الفهرس من نهاية الملف"""
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "rb") as f:
            # قراءة الفهرس من نهاية الملف
            f.seek(-8, os.SEEK_END)
            index_offset = struct.unpack(">Q", f.read(8))[0]
            index_size = struct.unpack(">I", f.read(4))[0]
            f.seek(index_offset)
            index_data = f.read(index_size)
            self.index = pickle.loads(index_data)

    def build(self, memtable: MemTable):
        """بناء SSTable من MemTable"""
        with open(self.filepath, "wb") as f:
            # كتابة رأس الملف
            f.write(self.MAGIC)
            f.write(struct.pack(">I", self.VERSION))

            # كتابة البيانات المرتبة
            index_entries = []
            for key, value in memtable.items():
                offset = f.tell()
                key_bytes = key.encode("utf-8")
                f.write(struct.pack(">H", len(key_bytes)))
                f.write(key_bytes)
                f.write(struct.pack(">I", len(value)))
                f.write(value)
                index_entries.append((key, offset))

            # كتابة الفهرس
            index_offset = f.tell()
            index_data = pickle.dumps(index_entries)
            f.write(index_data)
            f.write(struct.pack(">I", len(index_data)))
            f.write(struct.pack(">Q", index_offset))

        self._load_index()

    def get(self, key: str) -> Optional[bytes]:
        """قراءة قيمة باستخدام البحث الثنائي على الفهرس"""
        # بحث ثنائي
        lo, hi = 0, len(self.index) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.index[mid][0] == key:
                offset = self.index[mid][1]
                return self._read_at(offset, key)
            elif self.index[mid][0] < key:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def _read_at(self, offset: int, expected_key: str) -> Optional[bytes]:
        """قراءة قيمة من موضع محدد"""
        with open(self.filepath, "rb") as f:
            f.seek(offset)
            key_len = struct.unpack(">H", f.read(2))[0]
            key = f.read(key_len).decode("utf-8")
            val_len = struct.unpack(">I", f.read(4))[0]
            value = f.read(val_len)
            if value == b"__TOMBSTONE__":
                return None
            return value


class BloomFilter:
    """فلتر بلوم لتسريع البحث في SSTables"""

    def __init__(self, expected_items: int = 10000, fp_rate: float = 0.01):
        import math
        self.size = int(-expected_items * math.log(fp_rate) / (math.log(2) ** 2))
        self.hash_count = int(self.size / expected_items * math.log(2))
        self.bit_array = 0

    def _hashes(self, key: str):
        """توليد عدة قيم تجزئة للمفتاح"""
        h1 = int(hashlib.md5(key.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, key: str):
        """إضافة مفتاح"""
        for pos in self._hashes(key):
            self.bit_array |= (1 << pos)

    def might_contain(self, key: str) -> bool:
        """التحقق مما إذا كان المفتاح قد يكون موجوداً"""
        for pos in self._hashes(key):
            if not (self.bit_array & (1 << pos)):
                return False
        return True


class LSMStore:
    """تخزين LSM Tree متكامل للتطبيقات الطبية"""

    def __init__(self, data_dir: str, memtable_size: int = 1024 * 1024):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.memtable = MemTable(max_size=memtable_size)
        self.sstables: List[SSTable] = []
        self.bloom_filters: List[BloomFilter] = []
        self._load_sstables()

    def _load_sstables(self):
        """تحميل SSTables الموجودة"""
        sst_files = sorted(
            f for f in os.listdir(self.data_dir) if f.startswith("sst_")
        )
        for fname in sst_files:
            path = os.path.join(self.data_dir, fname)
            self.sstables.append(SSTable(path))

    def put(self, key: str, value: bytes):
        """كتابة مفتاح-قيمة"""
        self.memtable.put(key, value)
        if self.memtable.is_full():
            self._flush()

    def get(self, key: str) -> Optional[bytes]:
        """قراءة قيمة — البحث في MemTable أولاً، ثم SSTables بالترتيب العكسي"""
        # البحث في MemTable أولاً
        value = self.memtable.get(key)
        if value is not None:
            return value

        # البحث في SSTables من الأحدث إلى الأقدم
        for i in range(len(self.sstables) - 1, -1, -1):
            if i < len(self.bloom_filters):
                if not self.bloom_filters[i].might_contain(key):
                    continue
            value = self.sstables[i].get(key)
            if value is not None:
                return value
        return None

    def delete(self, key: str):
        """حذف مفتاح"""
        self.memtable.delete(key)
        if self.memtable.is_full():
            self._flush()

    def _flush(self):
        """تفريغ MemTable إلى SSTable جديد"""
        sst_num = len(self.sstables)
        sst_path = os.path.join(self.data_dir, f"sst_{sst_num:06d}.dat")
        sstable = SSTable(sst_path)
        sstable.build(self.memtable)

        # إنشاء Bloom Filter للـ SSTable الجديد
        bf = BloomFilter()
        for key, _ in self.memtable.items():
            bf.add(key)

        self.sstables.append(sstable)
        self.bloom_filters.append(bf)
        self.memtable.clear()

    def compact(self):
        """دمج SSTables لتحسين الأداء (Size-Tiered Compaction)"""
        if len(self.sstables) < 4:
            return
        merged = {}
        for sst in self.sstables:
            for key, value in sst.items():
                if value != b"__TOMBSTONE__":
                    merged[key] = value
        # إعادة بناء SSTables
        for sst in self.sstables:
            os.remove(sst.filepath)
        self.sstables.clear()
        self.bloom_filters.clear()

        new_memtable = MemTable(max_size=self.memtable.max_size * 2)
        for key, value in merged.items():
            new_memtable.put(key, value)
        self._sst_num = 0
        self._flush_from(new_memtable)
```

### التحديات

- **استخدام الذاكرة:** MemTable يحتاج ذاكرة كافية، يتطلب مراقبة واستراتيجية تبديل.
- **Compaction I/O:** عملية الدمج تستهلك موارد القرص بشكل كبير أثناء التنفيذ.
- **قراءة متسقة:** يجب ضمان قراءة البيانات المتسقة عبر MemTable و SSTables.
- **استعادة بعد الفشل:** WAL يجب أن يكتب بشكل متزامن لضمان عدم فقدان البيانات.

### التأثير المتوقع

- **سرعة الكتابة:** O(log N) للكتابة مقارنة بـ O(log N) في B-Tree ولكن مع أداء ثابت أفضل.
- **الاستفادة لـ OmniMedical:** تحسين سرعة تخزين واسترجاع نتائج OCR وتصحيحات المستخدمين بنسبة 40-60%.
- **الزمن المقدر:** 3-4 أسابيع للتنفيذ الكامل.

---

## 2. Load Balancer — موزع أحمال TCP

### المفهوم

موازن الأحمال هو مكون شبكة يوزع الطلبات الواردة عبر عدة خوادم خلفية لتحسين الأداء والتوفر. سننفذ موزع أحمال TCP بسيط يدعم خوارزميات متعددة.

### التطبيق في OmniMedical

- **توزيع مهام OCR:** توزيع مهام التعرف البصري عبر عدة خوادم حسب نوع المحرك.
- **توازن واجهة API:** توزيع طلبات FastAPI عبر نسخ متعددة.
- **High Availability:** تجاوز الفشل التلقائي عند سقوط خادم.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1): النواة
├── TCP Proxy (asyncio)
├── خوارزميات: Round Robin, Least Connections, IP Hash
└── Health Checks (HTTP/TCP)

المرحلة 2 (أسبوع 2): المتقدم
├── فحص صحة ديناميكي
├── Session Affinity
├── Metrics (Prometheus)
└── إدارة التكوين الديناميكي
```

### مثال الكود

```python
import asyncio
import hashlib
import time
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum


class LBAlgorithm(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"


@dataclass
class Backend:
    """خادم خلفي"""
    host: str
    port: int
    max_connections: int = 100
    healthy: bool = True
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_check: float = 0
    response_time_ms: float = 0

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class HealthCheckConfig:
    """إعدادات فحص الصحة"""
    interval_seconds: int = 10
    timeout_seconds: int = 5
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2


class LoadBalancer:
    """موازن أحمال TCP غير متزامن"""

    def __init__(self, algorithm: LBAlgorithm = LBAlgorithm.ROUND_ROBIN):
        self.backends: List[Backend] = []
        self.algorithm = algorithm
        self._rr_index = 0
        self._connections: Dict[str, int] = {}
        self.health_config = HealthCheckConfig()
        self._health_task: Optional[asyncio.Task] = None

    def add_backend(self, host: str, port: int, max_connections: int = 100):
        """إضافة خادم خلفي"""
        self.backends.append(Backend(host=host, port=port, max_connections=max_connections))

    def remove_backend(self, host: str, port: int):
        """إزالة خادم خلفي"""
        self.backends = [
            b for b in self.backends if not (b.host == host and b.port == port)
        ]

    def get_backend(self, client_ip: str = "") -> Optional[Backend]:
        """اختيار خادم خلفي حسب الخوارزمية"""
        healthy_backends = [b for b in self.backends if b.healthy]
        if not healthy_backends:
            return None

        if self.algorithm == LBAlgorithm.ROUND_ROBIN:
            backend = healthy_backends[self._rr_index % len(healthy_backends)]
            self._rr_index += 1
            return backend

        elif self.algorithm == LBAlgorithm.LEAST_CONNECTIONS:
            return min(healthy_backends, key=lambda b: b.active_connections)

        elif self.algorithm == LBAlgorithm.IP_HASH:
            if not client_ip:
                return healthy_backends[0]
            hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
            return healthy_backends[hash_val % len(healthy_backends)]

        return healthy_backends[0]

    async def health_check(self):
        """فحص صحة دوري للخوادم الخلفية"""
        while True:
            for backend in self.backends:
                try:
                    start = time.time()
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(backend.host, backend.port),
                        timeout=self.health_config.timeout_seconds,
                    )
                    writer.close()
                    await writer.wait_closed()
                    backend.response_time_ms = (time.time() - start) * 1000

                    if not backend.healthy:
                        backend._unhealthy_count = getattr(backend, "_unhealthy_count", 0) + 1
                        if backend._unhealthy_count >= self.health_config.healthy_threshold:
                            backend.healthy = True
                            backend._unhealthy_count = 0
                    backend.last_check = time.time()
                except (asyncio.TimeoutError, ConnectionError):
                    if backend.healthy:
                        backend._healthy_count = getattr(backend, "_healthy_count", 0) + 1
                        if backend._healthy_count >= self.health_config.unhealthy_threshold:
                            backend.healthy = False
                            backend._healthy_count = 0

            await asyncio.sleep(self.health_config.interval_seconds)

    async def start_health_checks(self):
        """بدء فحص الصحة في الخلفية"""
        self._health_task = asyncio.create_task(self.health_check())

    async def proxy_connection(self, client_reader, client_writer, client_ip: str):
        """تمرير اتصال TCP إلى الخادم الخلفي المختار"""
        backend = self.get_backend(client_ip)
        if not backend:
            client_writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
            client_writer.close()
            return

        try:
            backend.active_connections += 1
            backend.total_requests += 1

            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(backend.host, backend.port),
                timeout=5,
            )

            async def forward(src, dst):
                try:
                    while True:
                        data = await src.read(65536)
                        if not data:
                            break
                        dst.write(data)
                        await dst.drain()
                except (ConnectionError, asyncio.CancelledError):
                    pass
                finally:
                    try:
                        dst.close()
                    except Exception:
                        pass

            await asyncio.gather(
                forward(client_reader, backend_writer),
                forward(backend_reader, client_writer),
            )
        except asyncio.TimeoutError:
            backend.failed_requests += 1
        finally:
            backend.active_connections -= 1
            try:
                client_writer.close()
            except Exception:
                pass

    async def start(self, listen_host: str = "0.0.0.0", listen_port: int = 8080):
        """بدء موزع الأحمال"""
        await self.start_health_checks()
        server = await asyncio.start_server(
            lambda r, w: self.proxy_connection(r, w, ""),
            listen_host,
            listen_port,
        )
        async with server:
            await server.serve_forever()
```

### التحديات

- **Sticky Sessions:** الحفاظ على جلسة المستخدم على نفس الخادم.
- **Graceful Shutdown:** إغلاق أنيق دون قطع الاتصالات النشطة.
- **المقاييس:** جمع وتصدير المقاييس لـ Prometheus.

### التأثير المتوقع

- **التوفر:** تحسين التوفر عبر توزيع الحمل وتجاوز الفشل.
- **الأداء:** استغلال موارد متعددة بدلاً من خادم واحد.
- **الزمن المقدر:** 1-2 أسبوع.

---

## 3. Git-like VCS — نظام تحكم إصدارات مبسط

### المفهوم

نظام تحكم إصدارات (Version Control System) مبسط يوفر وظائف أساسية مشابهة لـ Git: تتبع الملفات، إنشاء نقاط حفظ (commits)، الفروع (branches)، الاندماج (merge)، والفرق (diff).

### التطبيق في OmniMedical

- **تتبع تغييرات المستندات الطبية:** تسجيل كل تعديل على المستندات مع السبب.
- **تتبع تصحيحات المستخدمين:** كل تصحيح يُعتبر commit مع metadata.
- **إدارة نماذج التدريب:** تتبع إصدارات النماذج وبيانات التدريب.
- **التدقيق (Audit Trail):** سجل كامل للتغييرات لأغراض التدقيق الطبي.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1-2): النواة
├── Blob Store (content-addressable, SHA-256)
├── Tree Objects (هيكل المجلدات)
├── Commit Objects (metadata + tree reference)
└── Working Directory Management

المرحلة 2 (أسبوع 3): الفروع والدمج
├── Branch / Checkout
├── Merge (ثلاثي)
├── Diff / Log
└── Status

المرحلة 3 (أسبوع 4-5): التكامل
├── واجهة Python API
├── تكامل مع Medical Document Pipeline
├── Audit Trail Interface
└── اختبارات شاملة
```

### مثال الكود

```python
import hashlib
import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple


class ObjectStore:
    """تخزين كائنات بعنونة المحتوى (Content-Addressable Storage)"""

    def __init__(self, repo_path: str):
        self.objects_dir = os.path.join(repo_path, ".omni", "objects")
        os.makedirs(self.objects_dir, exist_ok=True)

    def _hash_object(self, data: bytes, obj_type: str) -> str:
        """حساب SHA-256 وتخزين الكائن"""
        header = f"{obj_type} {len(data)}\0".encode()
        full_content = header + data
        sha = hashlib.sha256(full_content).hexdigest()
        obj_dir = os.path.join(self.objects_dir, sha[:2])
        obj_path = os.path.join(obj_dir, sha[2:])
        if not os.path.exists(obj_path):
            os.makedirs(obj_dir, exist_ok=True)
            with open(obj_path, "wb") as f:
                f.write(full_content)
        return sha

    def read_object(self, sha: str) -> Tuple[str, bytes]:
        """قراءة كائن من التخزين"""
        obj_path = os.path.join(self.objects_dir, sha[:2], sha[2:])
        with open(obj_path, "rb") as f:
            raw = f.read()
        null_idx = raw.index(b"\0")
        header = raw[:null_idx].decode()
        obj_type = header.split(" ")[0]
        content = raw[null_idx + 1:]
        return obj_type, content

    def store_blob(self, content: bytes) -> str:
        """تخزين ملف (blob)"""
        return self._hash_object(content, "blob")

    def store_tree(self, entries: Dict[str, str]) -> str:
        """تخزين شجرة (tree) — اسم_الملف -> SHA"""
        tree_data = json.dumps(entries).encode()
        return self._hash_object(tree_data, "tree")


class Commit:
    """كائن نقطة حفظ (commit)"""

    def __init__(self, tree_sha: str, message: str, parent: Optional[str] = None,
                 author: str = "", committer: str = ""):
        self.tree_sha = tree_sha
        self.message = message
        self.parent = parent
        self.author = author
        self.committer = committer
        self.timestamp = time.time()
        self.sha = ""

    def to_dict(self) -> dict:
        return {
            "tree": self.tree_sha,
            "parent": self.parent,
            "author": self.author,
            "committer": self.committer,
            "timestamp": self.timestamp,
            "message": self.message,
        }

    def serialize(self) -> bytes:
        return json.dumps(self.to_dict()).encode()


class SimpleVCS:
    """نظام تحكم إصدارات مبسط للتطبيقات الطبية"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.omni_dir = os.path.join(repo_path, ".omni")
        self.store = ObjectStore(repo_path)
        self.head_file = os.path.join(self.omni_dir, "HEAD")
        self.refs_dir = os.path.join(self.omni_dir, "refs")
        self.branches_dir = os.path.join(self.refs_dir, "heads")
        os.makedirs(self.branches_dir, exist_ok=True)

        if not os.path.exists(self.head_file):
            self._set_head("main")
            self._set_branch_ref("main", None)

    def _set_head(self, ref: str):
        with open(self.head_file, "w") as f:
            f.write(f"ref: refs/heads/{ref}\n")

    def _get_current_branch(self) -> str:
        with open(self.head_file, "r") as f:
            content = f.read().strip()
        if content.startswith("ref: refs/heads/"):
            return content.replace("ref: refs/heads/", "")
        return content

    def _set_branch_ref(self, branch: str, commit_sha: Optional[str]):
        ref_path = os.path.join(self.branches_dir, branch)
        with open(ref_path, "w") as f:
            f.write(commit_sha or "")

    def _get_branch_ref(self, branch: str) -> Optional[str]:
        ref_path = os.path.join(self.branches_dir, branch)
        if os.path.exists(ref_path):
            with open(ref_path, "r") as f:
                content = f.read().strip()
            return content if content else None
        return None

    def add(self, file_path: str):
        """إضافة ملف إلى منطقة التخزين المؤقت"""
        abs_path = os.path.join(self.repo_path, file_path)
        with open(abs_path, "rb") as f:
            content = f.read()
        blob_sha = self.store.store_blob(content)
        index_path = os.path.join(self.omni_dir, "index")
        index: Dict[str, str] = {}
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                index = json.load(f)
        index[file_path] = blob_sha
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

    def commit(self, message: str, author: str = "OmniMedical") -> str:
        """إنشاء نقطة حفظ جديدة"""
        # قراءة index
        index_path = os.path.join(self.omni_dir, "index")
        if not os.path.exists(index_path):
            raise ValueError("No files staged. Use 'add' first.")
        with open(index_path, "r") as f:
            index = json.load(f)

        # إنشاء tree
        tree_sha = self.store.store_tree(index)

        # إنشاء commit
        branch = self._get_current_branch()
        parent = self._get_branch_ref(branch)
        commit = Commit(
            tree_sha=tree_sha,
            message=message,
            parent=parent,
            author=author,
            committer=author,
        )
        commit.sha = self.store._hash_object(commit.serialize(), "commit")

        # تحديث المرجع
        self._set_branch_ref(branch, commit.sha)

        # مسح index
        os.remove(index_path)

        return commit.sha

    def log(self, max_count: int = 10) -> List[dict]:
        """عرض سجل نقاط الحفظ"""
        branch = self._get_current_branch()
        current_sha = self._get_branch_ref(branch)
        if not current_sha:
            return []

        commits = []
        while current_sha and len(commits) < max_count:
            _, data = self.store.read_object(current_sha)
            commit_data = json.loads(data)
            commit_data["sha"] = current_sha
            commits.append(commit_data)
            current_sha = commit_data.get("parent")

        return commits

    def branch(self, name: str):
        """إنشاء فرع جديد"""
        branch = self._get_current_branch()
        current_sha = self._get_branch_ref(branch)
        self._set_branch_ref(name, current_sha)

    def checkout(self, branch_name: str):
        """التبديل إلى فرع"""
        if not os.path.exists(os.path.join(self.branches_dir, branch_name)):
            raise ValueError(f"Branch '{branch_name}' not found.")
        self._set_head(branch_name)

    def diff(self, sha1: str, sha2: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """مقارنة نقطتي حفظ"""
        _, data1 = self.store.read_object(sha1)
        tree1 = json.loads(data1)
        _, data2 = self.store.read_object(sha2)
        tree2 = json.loads(data2)

        all_files = set(list(tree1.keys()) + list(tree2.keys()))
        changes = {}
        for fname in all_files:
            old_sha = tree1.get(fname)
            new_sha = tree2.get(fname)
            if old_sha != new_sha:
                changes[fname] = (old_sha, new_sha)
        return changes
```

### التحديات

- **الدمج (Merge):** خوارزمية الدمج الثلاثي معالجة التعارضات معقدة.
- **الأداء:** مع عدد كبير من الملفات، يحتاج إلى تحسينات في القراءة.
- **التكامل:** ربط VCS مع خط أنابيب OCR يتطلب تصميم حذر.

### التأثير المتوقع

- **التدقيق الطبي:** سجل كامل وغير قابل للتعديل لكل تغيير.
- **التراجع:** إمكانية التراجع عن التصحيحات الخاطئة.
- **الزمن المقدر:** 4-5 أسابيع.

---

## 4. Lisp Interpreter — مفسر لغة Lisp

### المفهوم

مفسر لغة Lisp يدعم الميزات الأساسية: الأرقام، السلاسل النصية، المتغيرات، الدوال، الشروط، التكرار، والقوائم. يمكن استخدامه لبرمجة قواعد معالجة مخصصة داخل OmniMedical.

### التطبيق في OmniMedical

- **قواعد المعالجة المخصصة:** كتابة قواعد NLP/OCR بلغة مرنة.
- **ماكروات المستخدم:** السماح للمستخدمين بتعريف معالجات مخصصة.
- **نظام البرمجة النصية:** أتمتة سير العمل الطبي.
- **التعبيرات الشرطية:** قواعد معقدة لتوجيه المحركات.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1-2): النواة
├── Tokenizer (مُحلل رموز)
├── Parser (مُحلل بناء الجملة)
├── AST Node Types
└── Environment (نطاق المتغيرات)

المرحلة 2 (أسبوع 3): التقييم
├── Eval/Apply
├── Special Forms (if, define, lambda, let, cond)
├── Built-in Functions
└── Tail Call Optimization

المرحلة 3 (أسبوع 4): التكامل
├── Python Binding (استدعاء دوال Python من Lisp)
├── Medical DSL (لغة خاصة بالمجال الطبي)
├── واجهة REPL
└── اختبارات
```

### مثال الكود

```python
import re
from typing import Any, List, Optional, Dict, Callable
from dataclasses import dataclass, field


# ============ أنواع البيانات ============

@dataclass
class Symbol:
    """رمز في Lisp"""
    name: str
    def __repr__(self):
        return f"Symbol({self.name})"

@dataclass
class LispList:
    """قائمة في Lisp"""
    elements: list
    def __repr__(self):
        return f"LispList({self.elements})"

@dataclass
class Lambda:
    """دالة مجهولة في Lisp"""
    params: list
    body: Any
    env: "Environment"
    def __repr__(self):
        return f"Lambda({self.params}, {self.body})"

NIL = None  # nil في Lisp = None في Python
TRUE = True
FALSE = False


# ============ مُحلل الرموز (Tokenizer) ============

class Tokenizer:
    """مُحلل رموز لغة Lisp"""

    TOKEN_PATTERNS = [
        ("COMMENT", r";[^\n]*"),
        ("STRING", r'"(?:[^"\\]|\\.)*"'),
        ("NUMBER", r"-?\d+\.?\d*"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("SYMBOL", r"[^\s()'\";]+"),
        ("WS", r"\s+"),
    ]

    def __init__(self, source: str):
        self.source = source
        self.tokens: List[tuple] = []
        self._tokenize()

    def _tokenize(self):
        pos = 0
        combined = "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_PATTERNS)
        regex = re.compile(combined)
        for match in regex.finditer(self.source):
            kind = match.lastgroup
            value = match.group()
            if kind in ("WS", "COMMENT"):
                continue
            self.tokens.append((kind, value))


# ============ مُحلل بناء الجملة (Parser) ============

class Parser:
    """مُحلل بناء جملة لغة Lisp"""

    def __init__(self, tokens: List[tuple]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> Any:
        """تحليل البرنامج وإنشاء AST"""
        if self.pos >= len(self.tokens):
            return NIL

        kind, value = self.tokens[self.pos]
        self.pos += 1

        if kind == "LPAREN":
            return self._parse_list()
        elif kind == "NUMBER":
            return float(value) if "." in value else int(value)
        elif kind == "STRING":
            return value[1:-1]  # إزالة علامات الاقتباس
        elif kind == "SYMBOL":
            return Symbol(value)
        elif kind == "RPAREN":
            raise SyntaxError("Unexpected ')'")
        return NIL

    def _parse_list(self) -> LispList:
        """تحليل قائمة (تعبير)"""
        elements = []
        while self.pos < len(self.tokens):
            kind, _ = self.tokens[self.pos]
            if kind == "RPAREN":
                self.pos += 1
                return LispList(elements)
            elements.append(self.parse())
        raise SyntaxError("Expected ')'")


# ============ البيئة (Environment) ============

class Environment:
    """نطاق المتغيرات"""

    def __init__(self, parent: Optional["Environment"] = None):
        self.bindings: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable: {name}")

    def set(self, name: str, value: Any):
        self.bindings[name] = value

    def define(self, name: str, value: Any):
        self.bindings[name] = value


# ============ المفسر (Evaluator) ============

class LispInterpreter:
    """مفسر لغة Lisp متكامل"""

    def __init__(self):
        self.global_env = Environment()
        self._setup_builtins()

    def _setup_builtins(self):
        """إعداد الدوال المدمجة"""
        self.global_env.define("+", lambda *args: sum(args))
        self.global_env.define("-", lambda a, b: a - b)
        self.global_env.define("*", lambda *args: eval("*".join(str(a) for a in args)))
        self.global_env.define("/", lambda a, b: a / b)
        self.global_env.define("=", lambda a, b: a == b)
        self.global_env.define("<", lambda a, b: a < b)
        self.global_env.define(">", lambda a, b: a > b)
        self.global_env.define("<=", lambda a, b: a <= b)
        self.global_env.define(">=", lambda a, b: a >= b)
        self.global_env.define("not", lambda a: not a)
        self.global_env.define("car", lambda lst: lst.elements[0] if isinstance(lst, LispList) and lst.elements else NIL)
        self.global_env.define("cdr", lambda lst: LispList(lst.elements[1:]) if isinstance(lst, LispList) else NIL)
        self.global_env.define("cons", lambda a, lst: LispList([a] + (lst.elements if isinstance(lst, LispList) else [])))
        self.global_env.define("list", lambda *args: LispList(list(args)))
        self.global_env.define("null?", lambda a: a is NIL or a == [])
        self.global_env.define("display", lambda a: print(a) or NIL)
        self.global_env.define("length", lambda lst: len(lst.elements) if isinstance(lst, LispList) else 0)
        self.global_env.define("append", lambda a, b: LispList(a.elements + b.elements) if isinstance(a, LispList) and isinstance(b, LispList) else NIL)

    def eval(self, expr: Any, env: Optional[Environment] = None) -> Any:
        """تقييم تعبير Lisp"""
        if env is None:
            env = self.global_env

        # الأرقام والسلاسل النصية — تُرجع كما هي
        if isinstance(expr, (int, float, str)):
            return expr

        # الرموز — البحث في البيئة
        if isinstance(expr, Symbol):
            return env.get(expr.name)

        # القوائم — تقييم كتعبير
        if isinstance(expr, LispList):
            if not expr.elements:
                return NIL

            first = expr.elements[0]

            # أشكال خاصة (Special Forms)
            if isinstance(first, Symbol):
                if first.name == "quote":
                    return expr.elements[1]
                elif first.name == "if":
                    condition = self.eval(expr.elements[1], env)
                    if condition is not FALSE and condition is not NIL:
                        return self.eval(expr.elements[2], env)
                    elif len(expr.elements) > 3:
                        return self.eval(expr.elements[3], env)
                    return NIL
                elif first.name == "define":
                    name = expr.elements[1].name if isinstance(expr.elements[1], Symbol) else str(expr.elements[1])
                    value = self.eval(expr.elements[2], env)
                    env.define(name, value)
                    return value
                elif first.name == "set!":
                    name = expr.elements[1].name
                    value = self.eval(expr.elements[2], env)
                    env.set(name, value)
                    return value
                elif first.name == "lambda":
                    params = [p.name for p in expr.elements[1].elements] if isinstance(expr.elements[1], LispList) else []
                    body = expr.elements[2] if len(expr.elements) == 3 else LispList(expr.elements[2:])
                    return Lambda(params, body, env)
                elif first.name == "let":
                    bindings = expr.elements[1]
                    body = expr.elements[2]
                    new_env = Environment(parent=env)
                    for binding in bindings.elements:
                        var_name = binding.elements[0].name
                        var_val = self.eval(binding.elements[1], env)
                        new_env.define(var_name, var_val)
                    return self.eval(body, new_env)
                elif first.name == "begin":
                    result = NIL
                    for e in expr.elements[1:]:
                        result = self.eval(e, env)
                    return result
                elif first.name == "cond":
                    for clause in expr.elements[1:]:
                        test = self.eval(clause.elements[0], env)
                        if test is not FALSE and test is not NIL:
                            return self.eval(clause.elements[1], env)
                    return NIL

            # استدعاء دالة عادية
            proc = self.eval(first, env)
            args = [self.eval(arg, env) for arg in expr.elements[1:]]

            if isinstance(proc, Lambda):
                new_env = Environment(parent=proc.env)
                for param, arg in zip(proc.params, args):
                    new_env.define(param, arg)
                return self.eval(proc.body, new_env)
            elif callable(proc):
                return proc(*args)
            else:
                raise TypeError(f"Not callable: {proc}")

        return expr

    def run(self, source: str) -> Any:
        """تنفيذ برنامج Lisp كامل"""
        tokenizer = Tokenizer(source)
        parser = Parser(tokenizer.tokens)
        result = NIL
        while parser.pos < len(parser.tokens):
            result = self.eval(parser.parse())
        return result

    def add_python_function(self, name: str, func: Callable):
        """إضافة دالة Python كمكالمة من Lisp"""
        self.global_env.define(name, func)
```

### التحديات

- **Tail Call Optimization:** ضروري لمنع تجاوز المكدس في التكرار.
- **الأداء:** المفسر بطبيعة الحال أبطأ من الكود المترجم.
- **DSL التصميم:** تصميم لغة خاصة بالمجال الطبي يتطلب خبرة لغوية.

### التأثير المتوقع

- **المرونة:** إضافة قواعد معالجة جديدة دون تعديل الكود الأساسي.
- **قابلية التوسع:** المستخدمون المتقدمون يمكنهم كتابة سكريبتات مخصصة.
- **الزمن المقدر:** 3-4 أسابيع.

---

## 5. Vector DB (HNSW) — قاعدة بيانات شعاعية

### المفهوم

قاعدة بيانات شعاعية تعتمد على خوارزمية HNSW (Hierarchical Navigable Small World) للبحث عن أقرب جار تقريبي (Approximate Nearest Neighbor - ANN). تُستخدم لتخزين واسترجاع المتجهات (embeddings) بكفاءة.

### التطبيق في OmniMedical

- **البحث الدلالي الطبي:** البحث في المستندات الطبية بالمعنى لا بالنص الحرفي.
- **تجميع النتائج:** تجميع نتائج OCR المتشابهة دلالياً.
- **تصنيف المستندات:** تصنيف المستندات حسب نوعها الطبي.
- **Medical Semantic Search:** بديل مفتوح المصدر عن Qdrant/FAISS.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1-2): النموذج الأولي
├── Vector insertion + Linear search
├── Cosine similarity
├── Persistence (pickle/JSON)
└── Basic filtering

المرحلة 2 (أسبوع 3-5): HNSW
├── Graph construction (multi-layer)
├── Insert with random level
├── Search with beam
├── Deletion (soft delete)
└── Persistence

المرحلة 3 (أسبوع 6-8): المتقدم
├── BM25 hybrid search
├── Metadata filtering
├── Multi-tenant isolation
├── Batch operations
└── تكامل مع OCR Fusion
```

### مثال الكود

```python
import numpy as np
import pickle
import math
import random
import os
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict


class SimpleVectorDB:
    """قاعدة بيانات شعاعية بسيطة (Linear Search — أساس للتطوير المتقدم)"""

    def __init__(self, dimension: int = 384, metric: str = "cosine"):
        self.dimension = dimension
        self.metric = metric
        self.vectors: Dict[str, np.ndarray] = {}  # id -> vector
        self.metadata: Dict[str, Dict[str, Any]] = {}  # id -> metadata

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """حساب تشابه جيب التمام"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def euclidean_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """حساب المسافة الإقليدية"""
        return float(np.linalg.norm(a - b))

    def distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """حساب المسافة حسب المقياس المختار"""
        if self.metric == "cosine":
            return 1.0 - self.cosine_similarity(a, b)
        return self.euclidean_distance(a, b)

    def insert(self, vector_id: str, vector: List[float], metadata: Optional[Dict] = None):
        """إدراج متجه جديد"""
        vec = np.array(vector, dtype=np.float32)
        if len(vec) != self.dimension:
            raise ValueError(f"Expected dimension {self.dimension}, got {len(vec)}")
        self.vectors[vector_id] = vec
        self.metadata[vector_id] = metadata or {}

    def search(self, query: List[float], top_k: int = 5,
               filters: Optional[Dict] = None) -> List[Tuple[str, float, Dict]]:
        """البحث عن أقرب المتجهات"""
        query_vec = np.array(query, dtype=np.float32)
        results = []

        for vid, vec in self.vectors.items():
            # تطبيق الفلاتر
            if filters:
                meta = self.metadata.get(vid, {})
                match = True
                for key, value in filters.items():
                    if meta.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            dist = self.distance(query_vec, vec)
            results.append((vid, dist, self.metadata.get(vid, {})))

        # ترتيب حسب المسافة (الأصغر أولاً)
        results.sort(key=lambda x: x[1])
        return results[:top_k]

    def delete(self, vector_id: str):
        """حذف متجه"""
        self.vectors.pop(vector_id, None)
        self.metadata.pop(vector_id, None)

    def save(self, filepath: str):
        """حفظ قاعدة البيانات"""
        data = {
            "dimension": self.dimension,
            "metric": self.metric,
            "vectors": {k: v.tolist() for k, v in self.vectors.items()},
            "metadata": self.metadata,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f)

    def load(self, filepath: str):
        """تحميل قاعدة البيانات"""
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        self.dimension = data["dimension"]
        self.metric = data["metric"]
        self.vectors = {k: np.array(v) for k, v in data["vectors"].items()}
        self.metadata = data["metadata"]


class HNSWIndex:
    """فهرس HNSW للبحث عن أقرب جار تقريبي (ANN)"""

    def __init__(self, dimension: int = 384, M: int = 16, ef_construction: int = 200,
                 ef_search: int = 50, max_level_mult: float = 1.0 / math.log(2)):
        self.dimension = dimension
        self.M = M  # عدد الروابط لكل عقدة
        self.M_max0 = 2 * M  # عدد الروابط في المستوى 0
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.max_level_mult = max_level_mult

        # هياكل البيانات
        self.vectors: Dict[int, np.ndarray] = {}
        self.graphs: List[Dict[int, List[int]]] = [{}]  # graphs[level][node] = [neighbors]
        self.node_levels: Dict[int, int] = {}
        self.entry_point: Optional[int] = None
        self.max_level = 0
        self._next_id = 0

    def _random_level(self) -> int:
        """توليد مستوى عشوائي للعقدة الجديدة"""
        level = 0
        while random.random() < (1.0 / self.max_level_mult) and level < 32:
            level += 1
        return level

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """تشابه جيب التمام (كمسافة)"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 1.0
        return 1.0 - float(np.dot(a, b) / (norm_a * norm_b))

    def _search_layer(self, query: np.ndarray, entry_point: int,
                      ef: int, level: int) -> List[Tuple[float, int]]:
        """بحث في مستوى واحد من الرسم البياني"""
        visited = {entry_point}
        candidates = [(self._distance(query, self.vectors[entry_point]), entry_point)]
        results = list(candidates)

        while candidates:
            candidates.sort()
            c_dist, c_id = candidates[0]

            f_dist = results[-1][0] if results else float("inf")

            if c_dist > f_dist:
                break

            candidates = candidates[1:]
            neighbors = self.graphs[level].get(c_id, [])

            for n_id in neighbors:
                if n_id in visited:
                    continue
                visited.add(n_id)

                n_dist = self._distance(query, self.vectors[n_id])

                if n_dist < f_dist or len(results) < ef:
                    candidates.append((n_dist, n_id))
                    results.append((n_dist, n_id))
                    results.sort()
                    if len(results) > ef:
                        results = results[:ef]

        return results

    def insert(self, vector: List[float], metadata: Optional[Dict] = None) -> int:
        """إدراج متجه جديد في الفهرس"""
        node_id = self._next_id
        self._next_id += 1
        vec = np.array(vector, dtype=np.float32)
        self.vectors[node_id] = vec

        level = self._random_level()

        # إنشاء مستويات الرسم البياني
        while len(self.graphs) <= level:
            self.graphs.append({})

        self.node_levels[node_id] = level

        if self.entry_point is None:
            self.entry_point = node_id
            for l in range(level + 1):
                self.graphs[l][node_id] = []
            self.max_level = level
            return node_id

        # البحث عن أقرب الجيران في كل مستوى
        ep = self.entry_point
        for l in range(self.max_level, level, -1):
            if ep in self.graphs[l]:
                results = self._search_layer(vec, ep, 1, l)
                ep = results[0][1] if results else ep

        # إدراج في المستويات level إلى 0
        for l in range(min(level, self.max_level), -1, -1):
            results = self._search_layer(vec, ep, self.ef_construction, l)
            M_max = self.M_max0 if l == 0 else self.M

            # اختيار أفضل M جيران
            neighbors = [r[1] for r in results[:M_max]]
            self.graphs[l][node_id] = neighbors

            # إضافة روابط ثنائية
            for n_id in neighbors:
                self.graphs[l].setdefault(n_id, [])
                self.graphs[l][n_id].append(node_id)
                if len(self.graphs[l][n_id]) > M_max:
                    # تقليص الروابط (Simple version: keep closest)
                    n_neighbors = self.graphs[l][n_id]
                    dists = [(self._distance(self.vectors[n_id], self.vectors[nn]), nn) for nn in n_neighbors]
                    dists.sort()
                    self.graphs[l][n_id] = [d[1] for d in dists[:M_max]]

            if results:
                ep = results[0][1]

        if level > self.max_level:
            self.entry_point = node_id
            self.max_level = level

        return node_id

    def search(self, query: List[float], top_k: int = 5) -> List[Tuple[float, int]]:
        """البحث عن أقرب المتجهات باستخدام HNSW"""
        if self.entry_point is None:
            return []

        query_vec = np.array(query, dtype=np.float32)
        ep = self.entry_point

        # البدء من أعلى مستوى
        for l in range(self.max_level, 0, -1):
            results = self._search_layer(query_vec, ep, 1, l)
            if results:
                ep = results[0][1]

        # البحث في المستوى 0 مع ef_search
        results = self._search_layer(query_vec, ep, max(self.ef_search, top_k), 0)
        return results[:top_k]
```

### التحديات

- **استهلاك الذاكرة:** HNSW يحتاج ذاكرة كبيرة للرسم البياني.
- **توليد المتجهات:** يحتاج إلى نموذج embeddings (Sentence Transformers).
- **الأداء:** التحسين يتطلب numpy/Cython أو Rust.
- **الاستمرارية:** حفظ وتحميل الرسم البياني بكفاءة.

### التأثير المتوقع

- **البحث الدلالي:** استبدال أو تكميل Qdrant بحل محلي خفيف.
- **الاستقلالية:** عدم الاعتماد على خدمات خارجية.
- **الزمن المقدر:** 6-8 أسابيع (بما في ذلك التكامل).

---

## 6. ML Framework — إطار تعلم آلي من الصفر

### المفهوم

إطار عمل للتعلم الآلي يُبنى من الصفر لتوفير فهم عميق لخوارزميات التعلم الآلي وربطها مباشرة بمتطلبات المعالجة الطبية. يشمل: Tensor، Autograd (Backpropagation)، Decision Trees، Random Forest، و SGD Optimizer.

### التطبيق في OmniMedical

- **تصنيف المستندات:** تصنيف المستندات الطبية حسب نوعها.
- **تحديد جودة OCR:** توقع جودة النتيجة قبل عرضها للمستخدم.
- **أوزان Fusion ديناميكية:** تعلم أفضل أوزان لدمج نتائج المحركات.
- **كشف الأنماط الطبية:** اكتشاف أنماط في تصحيحات المستخدمين.

### خطة التنفيذ

```
المرحلة 1 (أسبوع 1-2): الأساسيات
├── Tensor class (ndarray مع autograd)
├── العمليات: add, mul, matmul, relu, sigmoid, softmax
├── Autograd (backpropagation تلقائي)
└── SGD Optimizer

المرحلة 2 (أسبوع 3-4): النماذج
├── Perceptron / MLP
├── Decision Tree (ID3/C4.5)
├── Random Forest
├── Cross-validation
└── Metrics (accuracy, precision, recall, F1)

المرحلة 3 (أسبوع 5-6): التكامل
├── Fusion Weight Learner
├── Document Quality Classifier
├── Medical Pattern Detector
├── Training Pipeline
└── Evaluation Suite
```

### مثال الكود

```python
import numpy as np
import random
from typing import List, Optional, Dict, Tuple, Callable
from collections import Counter


# ============ فئة Tensor مع Autograd ============

class Tensor:
    """موتر يدعم حساب المشتقات التلقائي (Autograd)"""

    def __init__(self, data, _children=(), _op=""):
        if isinstance(data, (int, float)):
            data = np.array(data, dtype=np.float64)
        elif isinstance(data, list):
            data = np.array(data, dtype=np.float64)
        self.data = data.astype(np.float64) if data.dtype != np.float64 else data
        self.grad = np.zeros_like(self.data)
        self._backward = lambda: None
        self._prev = set(_children)
        self._op = _op

    def __repr__(self):
        return f"Tensor(data={self.data}, grad={self.grad})"

    def __add__(self, other):
        other = other if isinstance(other, Tensor) else Tensor(other)
        out = Tensor(self.data + other.data, (self, other), "+")

        def _backward():
            self.grad += np.ones_like(self.data) * out.grad
            other.grad += np.ones_like(other.data) * out.grad
        out._backward = _backward
        return out

    def __mul__(self, other):
        other = other if isinstance(other, Tensor) else Tensor(other)
        out = Tensor(self.data * other.data, (self, other), "*")

        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward
        return out

    def __neg__(self):
        return self * (-1)

    def __sub__(self, other):
        return self + (-other)

    def matmul(self, other):
        """ضرب مصفوفات"""
        other = other if isinstance(other, Tensor) else Tensor(other)
        out = Tensor(np.matmul(self.data, other.data), (self, other), "matmul")

        def _backward():
            self.grad += np.matmul(out.grad, other.data.T)
            other.grad += np.matmul(self.data.T, out.grad)
        out._backward = _backward
        return out

    def relu(self):
        """دالة التنشيط ReLU"""
        out = Tensor(np.maximum(0, self.data), (self,), "relu")

        def _backward():
            self.grad += (self.data > 0).astype(np.float64) * out.grad
        out._backward = _backward
        return out

    def sigmoid(self):
        """دالة التنشيط Sigmoid"""
        s = 1.0 / (1.0 + np.exp(-self.data))
        out = Tensor(s, (self,), "sigmoid")

        def _backward():
            self.grad += s * (1 - s) * out.grad
        out._backward = _backward
        return out

    def sum(self):
        """مجموع كل العناصر"""
        out = Tensor(np.sum(self.data), (self,), "sum")

        def _backward():
            self.grad += np.ones_like(self.data) * out.grad
        out._backward = _backward
        return out

    def mean(self):
        """متوسط العناصر"""
        out = Tensor(np.mean(self.data), (self,), "mean")

        def _backward():
            self.grad += np.ones_like(self.data) * out.grad / self.data.size
        out._backward = _backward
        return out

    def backward(self):
        """حساب المشتقات العكسية (Backpropagation)"""
        topo = []
        visited = set()

        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for child in v._prev:
                    build_topo(child)
                topo.append(v)
        build_topo(self)

        self.grad = np.ones_like(self.data)
        for v in reversed(topo):
            v._backward()

    def zero_grad(self):
        """تصفير التدرجات"""
        self.grad = np.zeros_like(self.data)


class SGD:
    """مُحسِّن SGD (Stochastic Gradient Descent)"""

    def __init__(self, params: List[Tensor], lr: float = 0.01, momentum: float = 0.0):
        self.params = params
        self.lr = lr
        self.momentum = momentum
        self.velocities = [np.zeros_like(p.data) for p in params]

    def step(self):
        """تحديث المعاملات"""
        for i, param in enumerate(self.params):
            if self.momentum > 0:
                self.velocities[i] = self.momentum * self.velocities[i] + param.grad
                param.data -= self.lr * self.velocities[i]
            else:
                param.data -= self.lr * param.grad

    def zero_grad(self):
        """تصفير تدرجات جميع المعاملات"""
        for param in self.params:
            param.zero_grad()


# ============ شبكة عصبية بسيطة ============

class Perceptron:
    """مُدرِّك إدراكي (Perceptron) مع إمكانية التصنيف"""

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        # تهيئة الأوزان عشوائياً
        limit = np.sqrt(6.0 / (input_dim + hidden_dim))
        self.w1 = Tensor(np.random.uniform(-limit, limit, (input_dim, hidden_dim)))
        self.b1 = Tensor(np.zeros(hidden_dim))
        self.w2 = Tensor(np.random.uniform(-limit, limit, (hidden_dim, output_dim)))
        self.b2 = Tensor(np.zeros(output_dim))
        self.params = [self.w1, self.b1, self.w2, self.b2]

    def __call__(self, x: Tensor) -> Tensor:
        """الانتشار الأمامي"""
        hidden = x.matmul(self.w1) + self.b1
        hidden = hidden.relu()
        output = hidden.matmul(self.w2) + self.b2
        return output

    def parameters(self) -> List[Tensor]:
        return self.params


# ============ شجرة القرار ============

class DecisionTree:
    """شجرة قرار (ID3/C4.5 مبسطة)"""

    def __init__(self, max_depth: int = 10, min_samples_split: int = 2):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.tree = None
        self.feature_importances_ = None

    def _entropy(self, y: np.ndarray) -> float:
        """حساب الإنتروبيا"""
        if len(y) == 0:
            return 0
        counts = Counter(y)
        total = len(y)
        return -sum((c / total) * np.log2(c / total) for c in counts.values() if c > 0)

    def _gini(self, y: np.ndarray) -> float:
        """حساب مؤشر جيني"""
        if len(y) == 0:
            return 0
        counts = Counter(y)
        total = len(y)
        return 1.0 - sum((c / total) ** 2 for c in counts.values())

    def _best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float]:
        """إيجاد أفضل نقطة تقسيم"""
        best_gain = -1
        best_feature = 0
        best_threshold = 0
        parent_entropy = self._entropy(y)

        n_features = X.shape[1]
        for feature_idx in range(n_features):
            thresholds = np.unique(X[:, feature_idx])
            for threshold in thresholds:
                left_mask = X[:, feature_idx] <= threshold
                right_mask = ~left_mask

                if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
                    continue

                left_entropy = self._entropy(y[left_mask])
                right_entropy = self._entropy(y[right_mask])
                n_left, n_right = np.sum(left_mask), np.sum(right_mask)
                weighted_entropy = (n_left * left_entropy + n_right * right_entropy) / len(y)
                gain = parent_entropy - weighted_entropy

                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature_idx
                    best_threshold = threshold

        return best_feature, best_threshold

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> dict:
        """بناء الشجرة بشكل تعاودي"""
        # شروط التوقف
        if depth >= self.max_depth or len(set(y)) == 1 or len(y) < self.min_samples_split:
            return {"leaf": True, "value": Counter(y).most_common(1)[0][0]}

        feature, threshold = self._best_split(X, y)
        left_mask = X[:, feature] <= threshold
        right_mask = ~left_mask

        if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
            return {"leaf": True, "value": Counter(y).most_common(1)[0][0]}

        return {
            "leaf": False,
            "feature": feature,
            "threshold": threshold,
            "left": self._build_tree(X[left_mask], y[left_mask], depth + 1),
            "right": self._build_tree(X[right_mask], y[right_mask], depth + 1),
        }

    def fit(self, X: np.ndarray, y: np.ndarray):
        """تدريب شجرة القرار"""
        self.tree = self._build_tree(X, y, 0)

        # حساب أهمية الميزات
        self.feature_importances_ = np.zeros(X.shape[1])
        self._compute_importances(self.tree, X, y)

    def _compute_importances(self, node: dict, X: np.ndarray, y: np.ndarray):
        """حساب أهمية الميزات"""
        if node["leaf"]:
            return
        feature = node["feature"]
        self.feature_importances_[feature] += 1
        left_mask = X[:, feature] <= node["threshold"]
        right_mask = ~left_mask
        self._compute_importances(node["left"], X[left_mask], y[left_mask])
        self._compute_importances(node["right"], X[right_mask], y[right_mask])

    def _predict_one(self, x: np.ndarray, node: dict):
        """تنبؤ لعينة واحدة"""
        if node["leaf"]:
            return node["value"]
        if x[node["feature"]] <= node["threshold"]:
            return self._predict_one(x, node["left"])
        return self._predict_one(x, node["right"])

    def predict(self, X: np.ndarray) -> np.ndarray:
        """تنبؤ لمجموعة عينات"""
        return np.array([self._predict_one(x, self.tree) for x in X])


# ============ غابة عشوائية ============

class RandomForest:
    """غابة عشوائية (Random Forest)"""

    def __init__(self, n_trees: int = 100, max_depth: int = 10,
                 min_samples_split: int = 2, max_features: Optional[int] = None):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.max_features = max_features
        self.trees: List[DecisionTree] = []
        self.feature_importances_ = None

    def _bootstrap_sample(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """عينة Bootstrap"""
        n = len(y)
        indices = np.random.choice(n, size=n, replace=True)
        return X[indices], y[indices]

    def fit(self, X: np.ndarray, y: np.ndarray):
        """تدريب الغابة العشوائية"""
        n_features = X.shape[1]
        max_features = self.max_features or int(np.sqrt(n_features))

        self.trees = []
        for _ in range(self.n_trees):
            X_sample, y_sample = self._bootstrap_sample(X, y)

            # اختيار مجموعة عشوائية من الميزات
            feature_indices = np.random.choice(n_features, max_features, replace=False)
            X_sub = X_sample[:, feature_indices]

            tree = DecisionTree(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
            )
            tree.fit(X_sub, y_sample)
            self.trees.append((tree, feature_indices))

        # حساب أهمية الميزات المتوسطة
        all_importances = np.zeros(n_features)
        for tree, indices in self.trees:
            all_importances[indices] += tree.feature_importances_
        self.feature_importances_ = all_importances / self.n_trees

    def predict(self, X: np.ndarray) -> np.ndarray:
        """تنبؤ بالتصويت الأغلبية"""
        predictions = np.array([tree.predict(X[:, indices]) for tree, indices in self.trees])
        # التصويت الأغلبية
        result = []
        for i in range(X.shape[0]):
            votes = Counter(predictions[:, i])
            result.append(votes.most_common(1)[0][0])
        return np.array(result)
```

### التحديات

- **الأداء:** Python البحتة بطيئة مقارنة بـ NumPy المُحسَّن أو GPU.
- **الاستقرار العددي:** backpropagation يحتاج إلى معالجة الـ gradients المتفجرة/المتلاشية.
- **النماذج المتقدمة:** إضافة CNNs/Transformers يتطلب جهداً كبيراً.
- **التكامل:** ربط المخرجات مع خط أنابيب OCR يتطلب معايرة دقيقة.

### التأثير المتوقع

- **أوزان ديناميكية:** تحسين دقة Fusion عبر تعلم الأوزان المثلى تلقائياً.
- **جودة OCR:** التنبؤ بجودة النتيجة وطلب مراجعة بشرية عند الحاجة.
- **الاستقلالية:** عدم الاعتماد على scikit-learn أو TensorFlow.
- **الزمن المقدر:** 4-6 أسابيع.

---

## ملخص جدولي

| # | المشروع | التعقيد | الزمن المقدر | الأولوية المقترحة | التأثير على OmniMedical |
|:---|:---|:---|:---|:---|:---|
| 1 | **LSM Tree** | متوسط | 3-4 أسابيع | عالية | تحسين أداء التخزين المؤقت 40-60% |
| 2 | **Load Balancer** | منخفض | 1-2 أسبوع | عالية | توافر عالٍ + توزيع الحمل |
| 3 | **Git-like VCS** | عالي | 4-5 أسابيع | متوسطة | تدقيق طبي + تتبع التغييرات |
| 4 | **Lisp Interpreter** | متوسط | 3-4 أسابيع | منخفضة | مرونة في القواعد + DSL |
| 5 | **Vector DB (HNSW)** | عالي | 6-8 أسابيع | عالية | بحث دلالي مستقل |
| 6 | **ML Framework** | عالي | 4-6 أسابيع | عالية | أوزان Fusion + تصنيف ذكي |

**إجمالي الزمن المقدر:** 21-29 أسبوع (حوالي 5-7 أشهر للتنفيذ الكامل)

---

> **ملاحظة:** هذا الملف يُحدَّث مع كل تقدم في التنفيذ. عند البدء بأي مشروع، أنشئ فرعاً جديداً من `main` باسم `feature/byox-{project-name}` وعند الانتهاء أرسل طلب دمج (Pull Request).
