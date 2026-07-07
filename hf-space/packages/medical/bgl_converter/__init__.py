"""
BGL Converter - Python 3
محول ملفات Babylon Glossary (.bgl) إلى صيغ متعددة

محول مكتوب بلغة Python 3 لقراءة ملفات Babylon (.bgl) واستخراج
المداخل والتعريفات منها، ثم تحويلها إلى صيغ مدعومة في تطبيق
OmniMedical Suite.

بناءً على عمل Andrea Barberio (parnurzeal/bglconverter)
مُعاد كتابته بالكامل بلغة Python 3 مع تحسينات.

الصيغ المدعومة:
    - bgl → json  (قاموس OmniMedical)
    - bgl → dic   (قاموس نصي)
    - bgl → csv   (جدول بيانات)
    - bgl → sqlite (قاعدة بيانات)
    - dic → json  (استيراد من قاموس نصي)

الاستخدام:
    from packages.medical.bgl_converter import BGLConverter
    converter = BGLConverter()
    entries = converter.convert("dictionary.bgl", output_format="json")
"""

import gzip
import struct
import os
import io
import csv
import json
import sqlite3
import re
import html
import logging
from typing import Dict, List, Tuple, Optional, Any, Iterator, BinaryIO
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============ أنواع البيانات ============

class OutputFormat(Enum):
    """صيغ الإخراج المدعومة"""
    JSON = "json"
    DIC = "dic"
    CSV = "csv"
    SQLITE = "sqlite"
    SQLITE_OMNI = "sqlite_omni"


class RecordType(Enum):
    """أنواع السجلات داخل ملف BGL"""
    DEBUG = 0
    ENTRY = 1
    RESOURCE = 2


@dataclass
class DictionaryEntry:
    """مدخلة قاموسية"""
    term: str
    definition: str
    term_html: str = ""
    definition_html: str = ""
    resources: List[Dict[str, Any]] = field(default_factory=list)

    def __repr__(self):
        return f"DictionaryEntry(term='{self.term}', definition='{self.definition[:50]}...')"


@dataclass
class DictionaryMetadata:
    """بيانات وصفية للقاموس"""
    title: str = ""
    author: str = ""
    source_lang: str = "ar"
    target_lang: str = "en"
    description: str = ""
    total_entries: int = 0
    encoding: str = "utf-8"
    format_version: str = "1.0"


# ============ فلاتر النصوص ============

class TextFilter:
    """فلاتر تنظيف النصوص المستخرجة"""

    # استبدال الأحرف غير المطبوعة
    CHAR_REPLACEMENTS = {
        0x91: "'",
        0x92: "'",
        0x93: "\u201c",
        0x94: "\u201d",
        0x95: "\u2022",
        0x96: "-",
        0x97: "-",
        0x98: "~",
        0x99: "\u2122",
        0x9B: "\u203a",
    }

    # أنماط HTML المراد تنظيفها
    HTML_CLEANUP_PATTERNS = [
        (re.compile(r'<br\s*/?>', re.IGNORECASE), '\n'),
        (re.compile(r'<p\s*/?>', re.IGNORECASE), '\n'),
        (re.compile(r'</p>', re.IGNORECASE), '\n'),
        (re.compile(r'<li\s*/?>', re.IGNORECASE), '\n- '),
        (re.compile(r'</li>', re.IGNORECASE), ''),
        (re.compile(r'<[^>]+>'), ''),  # إزالة باقي الوسوم
        (re.compile(r'&nbsp;'), ' '),
        (re.compile(r'&amp;'), '&'),
        (re.compile(r'&lt;'), '<'),
        (re.compile(r'&gt;'), '>'),
        (re.compile(r'&quot;'), '"'),
        (re.compile(r'&#(\d+);'), lambda m: chr(int(m.group(1)))),
        (re.compile(r'&#x([0-9a-fA-F]+);'), lambda m: chr(int(m.group(1), 16))),
        (re.compile(r'\n{3,}'), '\n\n'),  # تنظيف الأسطر الفارغة المتعددة
    ]

    @classmethod
    def fix_characters(cls, text: str) -> str:
        """استبدال الأحرف غير المطبوعة"""
        result = []
        for char in text:
            code = ord(char)
            if code in cls.CHAR_REPLACEMENTS:
                result.append(cls.CHAR_REPLACEMENTS[code])
            else:
                result.append(char)
        return ''.join(result)

    @classmethod
    def strip_html(cls, html_text: str) -> str:
        """إزالة وسوم HTML وتحويل الكيانات"""
        text = html_text
        for pattern, replacement in cls.HTML_CLEANUP_PATTERNS:
            text = pattern.sub(replacement, text)
        return text.strip()

    @classmethod
    def clean_definition(cls, text: str) -> str:
        """تنظيف كامل للتعريف"""
        text = cls.fix_characters(text)
        text = cls.strip_html(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def clean_term(cls, text: str) -> str:
        """تنظيف المصطلح"""
        text = cls.fix_characters(text)
        text = html.unescape(text)
        text = text.strip()
        return text


# ============ محول BGL الأساسي ============

class BGLReader:
    """قارئ ملفات Babylon Glossary (.bgl)"""

    def __init__(self, encoding: str = "utf-8", auto_detect: bool = True):
        self.encoding = encoding
        self.auto_detect = auto_detect

    def unpack(self, bgl_data: bytes) -> bytes:
        """
        فك ضغط ملف BGL واستخراج البيانات الخام.
        
        بنية ملف BGL:
        - أول 6 بايت: رأس الملف
        - البايتان 4-5: إزاحة بداية بيانات gzip (big-endian)
        - بعد الإزاحة: بيانات gzip المضغوطة
        """
        if len(bgl_data) < 6:
            raise ValueError("ملف BGL غير صالح: حجم الملف أقل من 6 بايت")

        # استخراج إزاحة gzip من البايتات 4-5
        offset = (bgl_data[4] << 16) | bgl_data[5]

        if offset >= len(bgl_data):
            raise ValueError(f"إزاحة gzip ({offset}) أكبر من حجم الملف ({len(bgl_data)})")

        # استخراج البيانات المضغوطة
        compressed = bgl_data[offset:]

        try:
            # محاولة فك الضغط باستخدام gzip
            decompressed = gzip.decompress(compressed)
            return decompressed
        except Exception as e:
            logger.warning(f"فشل فك الضغط بـ gzip: {e}")
            # محاولة فك الضغط مباشرة (قد لا يكون مضغوطاً)
            try:
                return gzip.open(io.BytesIO(compressed), 'rb').read()
            except Exception:
                raise ValueError(f"فشل فك ضغط ملف BGL: {e}")

    def detect_encoding(self, data: bytes) -> str:
        """اكتشاف ترميز النص تلقائياً"""
        if not self.auto_detect:
            return self.encoding

        # محاولة استخدام chardet إذا كان متاحاً
        try:
            import chardet
            result = chardet.detect(data[:10000])
            if result and result.get('confidence', 0) > 0.7:
                detected = result['encoding']
                logger.info(f"اكتشاف الترميز: {detected} (الثقة: {result['confidence']:.2f})")
                return detected
        except ImportError:
            pass

        return self.encoding

    def parse_entries(self, data: bytes) -> Iterator[DictionaryEntry]:
        """
        تحليل السجلات من البيانات المستخرجة.
        
        تنسيق السجلات:
        - كل سجل يبدأ بنibble (4 بت) يشير إلى النوع
        - البتات العلوية تشفر طول السجل
        - النوع 1: مدخلة قاموسية (مصطلح + تعريف)
        - النوع 2: مورد (صورة/ملف مضمن)
        - النوع 0: سجل تصحيح/معلومات
        """
        encoding = self.detect_encoding(data)
        pos = 0
        buffer = io.BytesIO(data)

        while pos < len(data):
            try:
                # قراءة نوع السجل
                if pos >= len(data):
                    break

                first_byte = data[pos]
                record_type_nibble = first_byte & 0x0F
                length_nibble = (first_byte >> 4) & 0x0F

                # حساب طول السجل (ترميز متغير الطول)
                length = length_nibble
                shift = 4
                while True:
                    pos += 1
                    if pos >= len(data):
                        break
                    byte_val = data[pos]
                    length |= (byte_val & 0x7F) << shift
                    shift += 7
                    if not (byte_val & 0x80):
                        break

                pos += 1
                if pos + length > len(data):
                    break

                record_data = data[pos:pos + length]
                pos += length

                # معالجة حسب نوع السجل
                if record_type_nibble == RecordType.ENTRY.value and length > 0:
                    try:
                        entry = self._parse_entry(record_data, encoding)
                        if entry and entry.term:
                            yield entry
                    except Exception as e:
                        logger.debug(f"فشل تحليل مدخلة عند الموضع {pos}: {e}")
                        continue

            except Exception as e:
                logger.debug(f"خطأ في التحليل عند الموضع {pos}: {e}")
                pos += 1

    def _parse_entry(self, data: bytes, encoding: str) -> Optional[DictionaryEntry]:
        """تحليل مدخلة قاموسية واحدة"""
        if len(data) < 4:
            return None

        try:
            # البحث عن الفاصل بين المصطلح والتعريف
            # في BGL، يكون المصطلح والتعريف مفصولين بحرف NULL أو بنمط محدد
            separator_pos = data.find(b'\x00')

            if separator_pos > 0 and separator_pos < len(data):
                term_bytes = data[:separator_pos]
                def_bytes = data[separator_pos + 1:]
            elif separator_pos == 0:
                # المصطلح فارغ، محاولة قراءة التعريف فقط
                def_bytes = data[1:]
                term_bytes = b""
            else:
                # لا يوجد فاصل NULL — محاولة فصل بناءً على النمط
                term_bytes, def_bytes = self._split_entry(data, encoding)

            # فك ترميز النص
            try:
                term = term_bytes.decode(encoding, errors='replace')
                definition = def_bytes.decode(encoding, errors='replace')
            except Exception:
                term = term_bytes.decode('utf-8', errors='replace')
                definition = def_bytes.decode('utf-8', errors='replace')

            # تنظيف النصوص
            term = TextFilter.clean_term(term)
            definition = TextFilter.clean_definition(definition)

            if not term or not term.strip():
                return None

            return DictionaryEntry(
                term=term.strip(),
                definition=definition.strip(),
                term_html=term,
                definition_html=definition,
            )

        except Exception as e:
            logger.debug(f"خطأ في تحليل المدخلة: {e}")
            return None

    def _split_entry(self, data: bytes, encoding: str) -> Tuple[bytes, bytes]:
        """فصل المصطلح عن التعريف عندما لا يوجد فاصل NULL واضح"""
        # محاولة فصل بناءً على أول سطر فارغ
        for i in range(len(data)):
            if data[i:i+2] == b'\r\n' or data[i] == b'\n'[0]:
                return data[:i], data[i+1:]
        # فاصل افتراضي: أول 50 بايت كمصطلح
        return data[:50], data[50:]


# ============ محول DIC (قاموس نصي) ============

class DICReader:
    """قارئ ملفات DIC (قاموس نصي)"""

    @staticmethod
    def read(filepath: str, encoding: str = "utf-8") -> Iterator[DictionaryEntry]:
        """
        قراءة ملف DIC.
        
        تنسيق DIC:
        - سطر 1: المصطلح
        - سطر 2: التعريف
        - سطر 3: المصطلح التالي
        - ... وهكذا
        """
        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines) - 1:
            term = lines[i].strip()
            definition = lines[i + 1].strip() if i + 1 < len(lines) else ""

            if term:
                yield DictionaryEntry(
                    term=TextFilter.clean_term(term),
                    definition=TextFilter.clean_definition(definition),
                )
            i += 2


# ============ المحول الرئيسي ============

class BGLConverter:
    """
    المحول الرئيسي لملفات القواميس الطبية.
    
    يدعم قراءة ملفات BGL و DIC وتحويلها إلى صيغ متعددة
    مناسبة للاستخدام في تطبيق OmniMedical Suite.

    المثال:
        converter = BGLConverter()
        
        # تحويل ملف BGL إلى JSON
        result = converter.convert("medical.bgl", output_format="json")
        
        # تحويل إلى CSV
        result = converter.convert("medical.bgl", output_format="csv")
        
        # تحويل إلى قاعدة بيانات SQLite بتنسيق OmniMedical
        result = converter.convert("medical.bgl", output_format="sqlite_omni")
    """

    def __init__(self, encoding: str = "utf-8", auto_detect_encoding: bool = True):
        self.encoding = encoding
        self.auto_detect_encoding = auto_detect_encoding
        self.bgl_reader = BGLReader(
            encoding=encoding,
            auto_detect=auto_detect_encoding
        )
        self.metadata = DictionaryMetadata()

    def read_file(self, filepath: str) -> List[DictionaryEntry]:
        """
        قراءة ملف قاموس وكشف صيغته تلقائياً.
        
        المعاملات:
            filepath: مسار ملف القاموس
            
        العائد:
            قائمة بمداخل القاموس
        """
        path = Path(filepath)
        suffix = path.suffix.lower()

        if suffix == '.bgl':
            return self._read_bgl(filepath)
        elif suffix == '.dic':
            return list(DICReader.read(filepath, encoding=self.encoding))
        elif suffix == '.json':
            return self._read_json(filepath)
        elif suffix == '.csv':
            return self._read_csv(filepath)
        else:
            # محاولة القراءة كـ BGL أولاً ثم DIC
            try:
                return self._read_bgl(filepath)
            except Exception:
                return list(DICReader.read(filepath, encoding=self.encoding))

    def _read_bgl(self, filepath: str) -> List[DictionaryEntry]:
        """قراءة ملف BGL"""
        logger.info(f"قراءة ملف BGL: {filepath}")

        with open(filepath, 'rb') as f:
            bgl_data = f.read()

        # فك الضغط
        unpacked = self.bgl_reader.unpack(bgl_data)
        logger.info(f"تم فك الضغط: {len(bgl_data)} → {len(unpacked)} بايت")

        # استخراج المداخل
        entries = list(self.bgl_reader.parse_entries(unpacked))
        self.metadata.total_entries = len(entries)
        self.metadata.title = Path(filepath).stem

        logger.info(f"تم استخراج {len(entries)} مدخلة")
        return entries

    def _read_json(self, filepath: str) -> List[DictionaryEntry]:
        """قراءة ملف JSON"""
        logger.info(f"قراءة ملف JSON: {filepath}")

        with open(filepath, 'r', encoding=self.encoding) as f:
            data = json.load(f)

        entries = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    term = item.get('term', item.get('ar', item.get('name', '')))
                    definition = item.get('definition', item.get('en', item.get('desc', '')))
                    category = item.get('category', item.get('type', ''))
                    if term:
                        entries.append(DictionaryEntry(
                            term=str(term),
                            definition=f"{definition} [{category}]".strip() if category else str(definition),
                        ))
                elif isinstance(item, str):
                    entries.append(DictionaryEntry(term=item, definition=""))

        elif isinstance(data, dict):
            # معالجة هيكل OmniMedical الموجود
            for section_name, section_data in data.items():
                if isinstance(section_data, dict) and section_name in (
                    'arabic_corrections', 'english_corrections'
                ):
                    for wrong, correct in section_data.items():
                        entries.append(DictionaryEntry(
                            term=wrong,
                            definition=f"التصحيح: {correct} (قسم: {section_name})",
                        ))
                elif isinstance(section_data, list):
                    for item in section_data:
                        if isinstance(item, dict):
                            term = item.get('term', item.get('ar', ''))
                            definition_parts = []
                            for k, v in item.items():
                                if k not in ('term',) and v:
                                    definition_parts.append(f"{k}: {v}")
                            definition = " | ".join(definition_parts)
                            if term:
                                entries.append(DictionaryEntry(term=str(term), definition=definition))
                elif isinstance(section_data, dict):
                    for term, defn in section_data.items():
                        entries.append(DictionaryEntry(term=str(term), definition=str(defn)))

        logger.info(f"تم استخراج {len(entries)} مدخلة من JSON")
        return entries

    def _read_csv(self, filepath: str) -> List[DictionaryEntry]:
        """قراءة ملف CSV"""
        logger.info(f"قراءة ملف CSV: {filepath}")
        entries = []
        with open(filepath, 'r', encoding=self.encoding, errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                term = row.get('term', row.get('ar', row.get('word', '')))
                definition = row.get('definition', row.get('en', row.get('desc', '')))
                if term:
                    entries.append(DictionaryEntry(
                        term=str(term),
                        definition=str(definition) if definition else "",
                    ))
        logger.info(f"تم استخراج {len(entries)} مدخلة من CSV")
        return entries

    def convert(self, input_path: str, output_format: str = "json",
                output_path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        تحويل ملف قاموس من صيغة إلى أخرى.
        
        المعاملات:
            input_path: مسار ملف الإدخال
            output_format: صيغة الإخراج (json, dic, csv, sqlite, sqlite_omni)
            output_path: مسار ملف الإخراج (اختياري)
            **kwargs: معاملات إضافية:
                - source_lang: لغة المصدر
                - target_lang: لغة الهدف
                - title: عنوان القاموس
                - db_table_name: اسم الجدول (لـ sqlite)
                
        العائد:
            {
                'format': صيغة الإخراج,
                'output_path': مسار الملف,
                'total_entries': عدد المداخل,
                'metadata': بيانات وصفية,
            }
        """
        # تحديث البيانات الوصفية
        self.metadata.source_lang = kwargs.get('source_lang', 'ar')
        self.metadata.target_lang = kwargs.get('target_lang', 'en')
        self.metadata.title = kwargs.get('title', Path(input_path).stem)
        self.metadata.description = kwargs.get('description', '')

        # قراءة المداخل
        entries = self.read_file(input_path)

        if not entries:
            logger.warning(f"لم يتم العثور على مداخل في الملف: {input_path}")
            return {
                'format': output_format,
                'output_path': None,
                'total_entries': 0,
                'entries': [],
                'metadata': self.metadata.__dict__,
            }

        # تحديد مسار الإخراج
        if not output_path:
            stem = Path(input_path).stem
            ext = self._get_extension(output_format)
            output_dir = kwargs.get('output_dir', str(Path(input_path).parent))
            output_path = str(Path(output_dir) / f"{stem}_omnimed{ext}")

        # التحويل حسب الصيغة المطلوبة
        fmt = OutputFormat(output_format.lower())
        result = {
            'format': output_format,
            'output_path': output_path,
            'total_entries': len(entries),
            'metadata': self.metadata.__dict__,
        }

        if fmt == OutputFormat.JSON:
            self._convert_to_json(entries, output_path, **kwargs)
        elif fmt == OutputFormat.DIC:
            self._convert_to_dic(entries, output_path)
        elif fmt == OutputFormat.CSV:
            self._convert_to_csv(entries, output_path)
        elif fmt == OutputFormat.SQLITE:
            self._convert_to_sqlite(entries, output_path,
                                    table_name=kwargs.get('db_table_name', 'dictionary'))
        elif fmt == OutputFormat.SQLITE_OMNI:
            self._convert_to_sqlite_omni(entries, output_path, **kwargs)

        result['entries'] = [
            {'term': e.term, 'definition': e.definition} for e in entries
        ]
        logger.info(f"تم التحويل بنجاح → {output_path} ({len(entries)} مدخلة)")
        return result

    def _convert_to_json(self, entries: List[DictionaryEntry],
                         output_path: str, **kwargs) -> None:
        """تحويل إلى JSON بتنسيق OmniMedical"""
        data = {
            "_metadata": {
                "title": self.metadata.title,
                "source_lang": self.metadata.source_lang,
                "target_lang": self.metadata.target_lang,
                "total_entries": len(entries),
                "format_version": self.metadata.format_version,
                "description": self.metadata.description,
                "source_file": str(output_path),
            },
            "entries": [
                {
                    "term": e.term,
                    "definition": e.definition,
                    "term_html": e.term_html,
                    "definition_html": e.definition_html,
                }
                for e in entries
            ],
        }

        # تنظيف المسار
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _convert_to_dic(self, entries: List[DictionaryEntry],
                        output_path: str) -> None:
        """تحويل إلى DIC (قاموس نصي)"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(f"{entry.term}\n")
                f.write(f"{entry.definition}\n")

    def _convert_to_csv(self, entries: List[DictionaryEntry],
                        output_path: str) -> None:
        """تحويل إلى CSV"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['term', 'definition', 'term_html', 'definition_html'])
            for entry in entries:
                writer.writerow([
                    entry.term,
                    entry.definition,
                    entry.term_html,
                    entry.definition_html,
                ])

    def _convert_to_sqlite(self, entries: List[DictionaryEntry],
                           output_path: str, table_name: str = "dictionary") -> None:
        """تحويل إلى قاعدة بيانات SQLite"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        conn = sqlite3.connect(output_path)
        cursor = conn.cursor()

        # إنشاء الجدول
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                definition TEXT,
                term_html TEXT,
                definition_html TEXT,
                length INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # إنشاء الفهارس
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_term ON {table_name}(term)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_length ON {table_name}(length)")

        # إدراج البيانات
        cursor.executemany(
            f"INSERT INTO {table_name} (term, definition, term_html, definition_html, length) VALUES (?, ?, ?, ?, ?)",
            [
                (e.term, e.definition, e.term_html, e.definition_html, len(e.definition))
                for e in entries
            ]
        )

        # إنشاء جدول البيانات الوصفية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.executemany(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            [
                ('title', self.metadata.title),
                ('source_lang', self.metadata.source_lang),
                ('target_lang', self.metadata.target_lang),
                ('total_entries', str(len(entries))),
                ('format_version', self.metadata.format_version),
                ('description', self.metadata.description),
            ]
        )

        conn.commit()
        conn.close()

    def _convert_to_sqlite_omni(self, entries: List[DictionaryEntry],
                                output_path: str, **kwargs) -> None:
        """
        تحويل إلى قاعدة بيانات SQLite بتنسيق OmniMedical.
        
        يتوافق مع جدول medical_terms_cache في init.sql
        """
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        conn = sqlite3.connect(output_path)
        cursor = conn.cursor()

        # إنشاء جدول medical_terms_cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_terms_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_ar TEXT NOT NULL,
                term_en TEXT,
                category VARCHAR(100),
                definition TEXT,
                frequency INTEGER DEFAULT 1,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # إنشاء الفهارس
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_term_ar ON medical_terms_cache(term_ar)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_term_en ON medical_terms_cache(term_en)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_category ON medical_terms_cache(category)")

        # إدراج البيانات مع محاولة تحديد اللغة والتصنيف
        arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
        now = "CURRENT_TIMESTAMP"

        for entry in entries:
            term = entry.term
            definition = entry.definition

            # تحديد ما إذا كان المصطلح عربياً
            has_arabic = bool(arabic_pattern.search(term))
            has_english = bool(re.search(r'[a-zA-Z]', term))

            if has_arabic:
                term_ar = term
                term_en = None
            elif has_english:
                term_ar = None
                term_en = term
            else:
                term_ar = term
                term_en = None

            # محاولة استخراج التصنيف من التعريف
            category = kwargs.get('category', '')
            if not category:
                # استخراج التصنيف بين أقواس
                match = re.search(r'\[([^\]]+)\]', definition)
                if match:
                    category = match.group(1)

            # محاولة استخراج المصطلح الآخر من التعريف
            if has_arabic and not term_en:
                en_match = re.search(r'[a-zA-Z][a-zA-Z\s]+', definition)
                if en_match:
                    term_en = en_match.group().strip()
            elif has_english and not term_ar:
                ar_match = re.search(r'[\u0600-\u06FF][\u0600-\u06FF\s]+', definition)
                if ar_match:
                    term_ar = ar_match.group().strip()

            cursor.execute("""
                INSERT OR IGNORE INTO medical_terms_cache
                (term_ar, term_en, category, definition, frequency)
                VALUES (?, ?, ?, ?, 1)
            """, (term_ar, term_en, category, definition))

        # إنشاء جدول البيانات الوصفية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dictionary_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dict_name TEXT UNIQUE,
                title TEXT,
                source_lang TEXT,
                target_lang TEXT,
                total_entries INTEGER,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                format_version TEXT
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO dictionary_metadata
            (dict_name, title, source_lang, target_lang, total_entries, format_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.metadata.title,
            self.metadata.title,
            self.metadata.source_lang,
            self.metadata.target_lang,
            len(entries),
            self.metadata.format_version,
        ))

        conn.commit()
        conn.close()

        logger.info(f"تم إنشاء قاعدة بيانات OmniMedical: {output_path}")

    @staticmethod
    def _get_extension(output_format: str) -> str:
        """الحصول على امتداد الملف حسب الصيغة"""
        extensions = {
            'json': '.json',
            'dic': '.dic',
            'csv': '.csv',
            'sqlite': '.db',
            'sqlite_omni': '_omni.db',
        }
        return extensions.get(output_format.lower(), '.json')

    def batch_convert(self, input_dir: str, output_format: str = "json",
                      output_dir: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        تحويل مجموعة ملفات قاموس دفعة واحدة.
        
        المعاملات:
            input_dir: مجلد ملفات الإدخال
            output_format: صيغة الإخراج
            output_dir: مجلد الإخراج (اختياري)
            
        العائد:
            قائمة نتائج التحويل لكل ملف
        """
        input_path = Path(input_dir)
        if not input_path.is_dir():
            raise ValueError(f"المسار ليس مجلداً: {input_dir}")

        supported_extensions = {'.bgl', '.dic', '.json', '.csv'}
        files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]

        if not files:
            logger.warning(f"لم يتم العثور على ملفات قاموس في: {input_dir}")
            return []

        output_dir = output_dir or str(input_path)
        results = []

        for filepath in files:
            try:
                result = self.convert(
                    str(filepath),
                    output_format=output_format,
                    output_dir=output_dir,
                    **kwargs,
                )
                result['source_file'] = str(filepath)
                results.append(result)
            except Exception as e:
                logger.error(f"فشل تحويل {filepath}: {e}")
                results.append({
                    'source_file': str(filepath),
                    'error': str(e),
                    'total_entries': 0,
                })

        success = sum(1 for r in results if 'error' not in r)
        logger.info(f"تحويل دفعة: {success}/{len(files)} نجح")
        return results
