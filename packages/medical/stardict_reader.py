"""
قارئ قواميس StarDict — OmniMedical Suite
StarDict Dictionary Reader for OmniMedical Suite

قارئ متقدم لملفات قاموس StarDict (.ifo, .idx, .dict, .syn).
يدعم الترميزات UTF-8 و GBK، وصيغ الإزاحة 32-bit و 64-bit.
يتكامل مع نظام القواميس الطبية في OmniMedical Suite.

An advanced reader for StarDict dictionary files (.ifo, .idx, .dict, .syn).
Supports UTF-8 and GBK encodings, and both 32-bit and 64-bit offset formats.
Integrates with the OmniMedical Suite medical dictionary system.

الصيغة المدعومة:
    - StarDict 3.0 (إزاحة 32-bit)
    - StarDict 3.0 مع إزاحة 64-bit
    - ملفات مرادفات .syn اختيارية

الاستخدام:
    from packages.medical.stardict_reader import StarDictReader

    reader = StarDictReader("/path/to/dict/")
    reader.read_ifo()
    reader.read_idx()
    definition = reader.get_definition("fracture")
    results = reader.search("cardio", limit=20)

تنسيق ملفات StarDict:
    - .ifo: ملف البيانات الوصفية (bookname, wordcount, idxfilesize, sametypesequence)
    - .idx: قائمة الكلمات المرتبة مع إزاحات ثنائية
    - .dict: بيانات التعريفات عند الإزاحات المحددة في .idx
    - .syn: مرادفات إضافية (اختياري، نفس صيغة .idx)
"""

import struct
import os
import json
import sqlite3
import gzip
import bz2
import logging
from typing import Dict, List, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from bisect import bisect_left

logger = logging.getLogger(__name__)


# ============ أنواع البيانات / Data Types ============

@dataclass
class StarDictMetadata:
    """
    بيانات وصفية لقاموس StarDict.
    Metadata for a StarDict dictionary.
    """
    bookname: str = ""
    wordcount: int = 0
    idxfilesize: int = 0
    sametypesequence: str = ""
    description: str = ""
    author: str = ""
    email: str = ""
    website: str = ""
    version: str = ""
    date: str = ""
    source_lang: str = ""
    target_lang: str = ""
    is_64bit: bool = False
    idx_offset_bits: int = 32

    def to_dict(self) -> dict:
        """تحويل إلى قاموس / Convert to dictionary."""
        return {
            "bookname": self.bookname,
            "wordcount": self.wordcount,
            "idxfilesize": self.idxfilesize,
            "sametypesequence": self.sametypesequence,
            "description": self.description,
            "author": self.author,
            "email": self.email,
            "website": self.website,
            "version": self.version,
            "date": self.date,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "is_64bit": self.is_64bit,
        }


@dataclass
class StarDictEntry:
    """
    مدخلة من قاموس StarDict.
    A single entry from a StarDict dictionary.
    """
    word: str
    definition: str = ""
    definition_html: str = ""
    offset: int = 0
    size: int = 0
    synonyms: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """تحويل إلى قاموس / Convert to dictionary."""
        return {
            "word": self.word,
            "definition": self.definition,
            "definition_html": self.definition_html,
            "synonyms": self.synonyms,
        }


@dataclass
class StarDictError:
    """
    خطأ في قراءة StarDict.
    Error encountered during StarDict reading.
    """
    message: str
    file_path: str = ""
    offset: int = 0
    severity: str = "warning"  # warning, error, critical


# ============ قارئ StarDict / StarDict Reader ============

class StarDictReader:
    """
    قارئ ملفات قاموس StarDict (.ifo, .idx, .dict).
    StarDict dictionary file reader (.ifo, .idx, .dict).

    يدعم:
    - Reading .ifo metadata files with key=value pairs
    - Parsing .idx binary index files (word → offset mapping)
    - Reading .dict definition files with multiple encodings
    - Optional .syn synonym files
    - Both 32-bit and 64-bit offset formats
    - Compressed .dict.dz (gzip) and .dict.bz2 files

    المثال / Example:
        reader = StarDictReader("/path/to/stardict/")
        reader.read_ifo()
        reader.read_idx()

        # الحصول على تعريف / Get definition
        entry = reader.get_definition("fracture")

        # بحث بالبادئة / Prefix search
        matches = reader.search("cardio", limit=20)

        # تصدير / Export
        reader.export_to_json("output.json")
        reader.export_to_sqlite("output.db", "medical_dict")
    """

    # أنماط الترميز المدعومة / Supported encoding patterns
    COMMON_ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb18030", "gb2312", "big5",
                        "shift-jis", "euc-jp", "euc-kr", "iso-8859-6"]

    def __init__(self, dict_dir: str, encoding: Optional[str] = None):
        """
        تهيئة قارئ StarDict.
        Initialize the StarDict reader.

        المعاملات / Parameters:
            dict_dir: مسار المجلد المحتوي على ملفات StarDict
                     Directory containing .ifo/.idx/.dict files
            encoding: الترميز المُراد استخدامه (اختياري، يُكشف تلقائياً)
                     Encoding to use (optional, auto-detected)
        """
        self.dict_dir = Path(dict_dir)
        self.encoding = encoding
        self.metadata = StarDictMetadata()
        self._idx_entries: List[Tuple[str, int, int]] = []  # (word, offset, size)
        self._word_list: List[str] = []
        self._synonym_map: Dict[str, int] = {}  # synonym → word index
        self._dict_file = None
        self._dict_data: Optional[bytes] = None
        self._errors: List[StarDictError] = []

        # التحقق من المجلد / Verify directory
        if not self.dict_dir.is_dir():
            raise ValueError(f"المجلد غير موجود / Directory not found: {dict_dir}")

        logger.info(f"تهيئة قارئ StarDict: {dict_dir}")

    # ============ قراءة ملف .ifo / Read .ifo file ============

    def read_ifo(self) -> StarDictMetadata:
        """
        قراءة وتحليل ملف البيانات الوصفية (.ifo).
        Parse the metadata file (.ifo).

        ملف .ifo يحتوي على أزواج مفتاح=قيمة مثل:
        The .ifo file contains key=value pairs such as:
            bookname=Medical Dictionary
            wordcount=50000
            idxfilesize=1048576
            sametypesequence=m

        العائد / Returns:
            StarDictMetadata: البيانات الوصفية المحللة / Parsed metadata

        الاستثناءات / Raises:
            FileNotFoundError: إذا لم يُعثر على ملف .ifo
            ValueError: إذا كان تنسيق الملف غير صالح
        """
        ifo_path = self._find_file(".ifo")
        if not ifo_path:
            raise FileNotFoundError(
                f"لم يُعثر على ملف .ifo في / No .ifo file found in: {self.dict_dir}"
            )

        logger.info(f"قراءة ملف .ifo: {ifo_path}")

        with open(ifo_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # تخطي سطر بداية StarDict / Skip StarDict header line
        lines = content.strip().split("\n")
        if lines and lines[0].strip().lower().startswith("stardict"):
            lines = lines[1:]

        # تحليل الأزواج / Parse key=value pairs
        for line in lines:
            line = line.strip()
            if not line or "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()

            # استخراج القيمة بين علامات اقتباس / Extract value between quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            self._parse_ifo_field(key, value)

        # تحديد صيغة الإزاحة / Determine offset format
        self._determine_offset_format()

        logger.info(
            f"بيانات .ifo: bookname='{self.metadata.bookname}', "
            f"wordcount={self.metadata.wordcount}, "
            f"64bit={self.metadata.is_64bit}"
        )

        return self.metadata

    def _parse_ifo_field(self, key: str, value: str):
        """
        تحليل حقل من ملف .ifo.
        Parse a single field from the .ifo file.

        المعاملات / Parameters:
            key: اسم المفتاح / Key name
            value: قيمة المفتاح / Key value
        """
        field_map = {
            "bookname": "bookname",
            "wordcount": "wordcount",
            "idxfilesize": "idxfilesize",
            "sametypesequence": "sametypesequence",
            "description": "description",
            "author": "author",
            "email": "email",
            "website": "website",
            "version": "version",
            "date": "date",
        }

        if key in field_map:
            attr = field_map[key]
            if attr in ("wordcount", "idxfilesize"):
                try:
                    setattr(self.metadata, attr, int(value))
                except (ValueError, TypeError):
                    logger.warning(f"قيمة عددية غير صالحة / Invalid numeric value for {key}: {value}")
            else:
                setattr(self.metadata, attr, value)

        # كشف اللغات من اسم القاموس / Detect languages from bookname
        if key == "bookname":
            self._detect_languages(value)

    def _detect_languages(self, bookname: str):
        """
        كشف لغات المصدر والهدف من اسم القاموس.
        Detect source and target languages from dictionary name.

        المعاملات / Parameters:
            bookname: اسم القاموس / Dictionary bookname
        """
        # أنماط شائعة في أسماء القواميس / Common patterns in dictionary names
        ar_en_patterns = [
            "العربي الإنجليزي", "Arabic-English", "ar-en", "arabic_english",
            "English-Arabic", "en-ar", "english_arabic", "En-Ar", "Ar-En",
            "العربية-الإنجليزية", "الإنجليزية-العربية",
        ]

        bookname_lower = bookname.lower()
        for pattern in ar_en_patterns:
            if pattern.lower() in bookname_lower:
                self.metadata.source_lang = "ar"
                self.metadata.target_lang = "en"
                return

        # كشف اللغة العربية من النص / Detect Arabic from text
        if any("\u0600" <= ch <= "\u06FF" for ch in bookname):
            self.metadata.source_lang = "ar"
            self.metadata.target_lang = "en"
        else:
            self.metadata.source_lang = "en"
            self.metadata.target_lang = "ar"

    def _determine_offset_format(self):
        """
        تحديد صيغة الإزاحة (32-bit أو 64-bit) بناءً على حجم ملف .idx.
        Determine offset format (32-bit or 64-bit) based on .idx file size.

        في StarDict، حجم ملف .idx المُسجل في .ifo يحدد الصيغة:
        - إذا كان الحجم الفعلي = الحجم المُسجل: 32-bit (word\\0 + 4-byte offset)
        - إذا كان الحجم الفعلي ≠ الحجم المُسجل: 64-bit (word\\0 + 8-byte offset)
        """
        idx_path = self._find_file(".idx")
        if not idx_path:
            return

        actual_size = os.path.getsize(idx_path)
        expected_size = self.metadata.idxfilesize

        if expected_size > 0 and actual_size != expected_size:
            # فحص ما إذا كان الفرق متوافقاً مع صيغة 64-bit
            # Check if difference is consistent with 64-bit format
            # في صيغة 64-bit، كل مدخلة لها 4 بايت إضافية للإزاحة
            # In 64-bit format, each entry has 4 extra bytes for offset
            wordcount = self.metadata.wordcount
            if wordcount > 0:
                extra_per_entry = (actual_size - expected_size) / wordcount
                if abs(extra_per_entry - 4.0) < 1.0:
                    self.metadata.is_64bit = True
                    self.metadata.idx_offset_bits = 64
                    logger.info("تم كشف صيغة 64-bit / Detected 64-bit offset format")

    # ============ قراءة ملف .idx / Read .idx file ============

    def read_idx(self) -> int:
        """
        قراءة وتحليل ملف الفهرس (.idx).
        Parse the index file (.idx).

        يُنشئ خريطة: كلمة → (إزاحة، حجم) للاستعلام السريع.
        Builds a map: word → (offset, size) for fast lookup.

        تنسيق .idx:
        - 32-bit: word\\0 + uint32_offset + uint32_size
        - 64-bit: word\\0 + uint32_offset + uint32_offset_high + uint32_size

        العائد / Returns:
            int: عدد المداخل المُقرأة / Number of entries read
        """
        idx_path = self._find_file(".idx")
        if not idx_path:
            raise FileNotFoundError(
                f"لم يُعثر على ملف .idx في / No .idx file found in: {self.dict_dir}"
            )

        logger.info(f"قراءة ملف .idx: {idx_path}")

        with open(idx_path, "rb") as f:
            idx_data = f.read()

        # تجربة كشف الترميز من أول الكلمات / Try detecting encoding from first words
        if self.encoding is None:
            self.encoding = self._detect_encoding(idx_data)

        self._idx_entries = []
        self._word_list = []
        pos = 0
        data_len = len(idx_data)

        while pos < data_len:
            try:
                # البحث عن فاصل NULL / Find NULL separator
                null_pos = idx_data.find(b"\x00", pos)
                if null_pos == -1:
                    break

                # قراءة الكلمة / Read word
                word_bytes = idx_data[pos:null_pos]
                try:
                    word = word_bytes.decode(self.encoding, errors="replace")
                except (UnicodeDecodeError, LookupError):
                    word = word_bytes.decode("utf-8", errors="replace")

                word = word.strip()
                if not word:
                    pos = null_pos + 1
                    continue

                # قراءة الإزاحة والحجم / Read offset and size
                next_pos = null_pos + 1

                if self.metadata.is_64bit:
                    # صيغة 64-bit: 8 بايت إزاحة + 4 بايت حجم
                    # 64-bit format: 8-byte offset + 4-byte size
                    if next_pos + 12 > data_len:
                        self._errors.append(StarDictError(
                            message="بيانات ناقصة لصيغة 64-bit / Insufficient data for 64-bit",
                            offset=pos,
                        ))
                        break

                    offset_lo = struct.unpack_from(">I", idx_data, next_pos)[0]
                    offset_hi = struct.unpack_from(">I", idx_data, next_pos + 4)[0]
                    offset = (offset_hi << 32) | offset_lo
                    size = struct.unpack_from(">I", idx_data, next_pos + 8)[0]
                    next_pos += 12

                else:
                    # صيغة 32-bit: 4 بايت إزاحة + 4 بايت حجم
                    # 32-bit format: 4-byte offset + 4-byte size
                    if next_pos + 8 > data_len:
                        self._errors.append(StarDictError(
                            message="بيانات ناقصة لصيغة 32-bit / Insufficient data for 32-bit",
                            offset=pos,
                        ))
                        break

                    offset = struct.unpack_from(">I", idx_data, next_pos)[0]
                    size = struct.unpack_from(">I", idx_data, next_pos + 4)[0]
                    next_pos += 8

                self._idx_entries.append((word, offset, size))
                self._word_list.append(word)
                pos = next_pos

            except struct.error as e:
                self._errors.append(StarDictError(
                    message=f"خطأ في تحليل البنية / Struct parse error: {e}",
                    offset=pos,
                    severity="error",
                ))
                pos += 1

        logger.info(
            f"تم قراءة {len(self._idx_entries)} مدخلة فهرس / "
            f"Read {len(self._idx_entries)} index entries"
        )

        # قراءة المرادفات إن وجدت / Read synonyms if available
        self._read_synonyms()

        return len(self._idx_entries)

    def _detect_encoding(self, idx_data: bytes) -> str:
        """
        كشف ترميز النص من بيانات الفهرس.
        Detect text encoding from index data.

        المعاملات / Parameters:
            idx_data: بيانات ملف .idx الثنائية / Raw .idx file data

        العائد / Returns:
            str: الترميز المُكشف / Detected encoding
        """
        # محاولة UTF-8 أولاً / Try UTF-8 first
        null_pos = idx_data.find(b"\x00")
        if null_pos > 0:
            sample = idx_data[:null_pos]
            try:
                sample.decode("utf-8")
                return "utf-8"
            except UnicodeDecodeError:
                pass

        # تجربة ترميزات أخرى / Try other encodings
        for enc in self.COMMON_ENCODINGS:
            try:
                sample.decode(enc)
                logger.info(f"تم كشف الترميز / Detected encoding: {enc}")
                return enc
            except (UnicodeDecodeError, LookupError):
                continue

        logger.warning("لم يتم كشف الترميز، استخدام UTF-8 / Encoding not detected, using utf-8")
        return "utf-8"

    # ============ قراءة المرادفات / Read Synonyms ============

    def _read_synonyms(self):
        """
        قراءة ملف المرادفات (.syn) اختيارياً.
        Optionally read the synonym file (.syn).

        ملف .syn له نفس صيغة .idx لكن كل مدخلة تُشير إلى فهرس الكلمة
        الرئيسية في قائمة _word_list.
        The .syn file has the same format as .idx but each entry points to
        the main word index in _word_list.
        """
        syn_path = self._find_file(".syn")
        if not syn_path:
            logger.info("لا يوجد ملف مرادفات / No synonym file found")
            return

        logger.info(f"قراءة ملف المرادفات: {syn_path}")

        try:
            with open(syn_path, "rb") as f:
                syn_data = f.read()

            pos = 0
            data_len = len(syn_data)
            synonym_count = 0

            while pos < data_len:
                null_pos = syn_data.find(b"\x00", pos)
                if null_pos == -1:
                    break

                synonym_bytes = syn_data[pos:null_pos]
                try:
                    synonym = synonym_bytes.decode(self.encoding or "utf-8", errors="replace")
                except (UnicodeDecodeError, LookupError):
                    synonym = synonym_bytes.decode("utf-8", errors="replace")

                synonym = synonym.strip()
                next_pos = null_pos + 1

                # قراءة فهرس الكلمة الرئيسية / Read main word index
                if next_pos + 4 > data_len:
                    break

                word_index = struct.unpack_from(">I", syn_data, next_pos)[0]
                next_pos += 4

                if synonym and 0 <= word_index < len(self._word_list):
                    main_word = self._word_list[word_index]
                    self._synonym_map[synonym] = word_index
                    synonym_count += 1

                pos = next_pos

            logger.info(
                f"تم قراءة {synonym_count} مرادف / Read {synonym_count} synonyms"
            )

        except Exception as e:
            logger.warning(f"خطأ في قراءة المرادفات / Error reading synonyms: {e}")

    # ============ قراءة التعريفات / Read Definitions ============

    def _ensure_dict_loaded(self):
        """
        التأكد من تحميل ملف .dict في الذاكرة.
        Ensure the .dict file is loaded into memory.

        يدعم الملفات المضغوطة .dict.dz (gzip) و .dict.bz2.
        Supports compressed .dict.dz (gzip) and .dict.bz2 files.
        """
        if self._dict_data is not None:
            return

        dict_path = self._find_file(".dict.dz")
        is_compressed = False

        if dict_path:
            is_compressed = True
        else:
            dict_path = self._find_file(".dict.bz2")
            if dict_path:
                is_compressed = True
            else:
                dict_path = self._find_file(".dict")

        if not dict_path:
            raise FileNotFoundError(
                f"لم يُعثر على ملف .dict في / No .dict file found in: {self.dict_dir}"
            )

        logger.info(f"تحميل ملف التعريفات: {dict_path}")

        with open(dict_path, "rb") as f:
            raw_data = f.read()

        if is_compressed and str(dict_path).endswith(".dict.dz"):
            try:
                self._dict_data = gzip.decompress(raw_data)
                logger.info(
                    f"فك ضغط gzip: {len(raw_data)} → {len(self._dict_data)} بايت"
                )
            except Exception as e:
                logger.error(f"فشل فك ضغط gzip / gzip decompression failed: {e}")
                raise
        elif is_compressed and str(dict_path).endswith(".dict.bz2"):
            try:
                self._dict_data = bz2.decompress(raw_data)
                logger.info(
                    f"فك ضغط bz2: {len(raw_data)} → {len(self._dict_data)} بايت"
                )
            except Exception as e:
                logger.error(f"فشل فك ضغط bz2 / bz2 decompression failed: {e}")
                raise
        else:
            self._dict_data = raw_data

    def _read_definition_at(self, offset: int, size: int) -> str:
        """
        قراءة تعريف من ملف .dict عند إزاحة معينة.
        Read a definition from the .dict file at a given offset.

        المعاملات / Parameters:
            offset: إزاحة البداية / Start offset
            size: حجم البيانات / Data size

        العائد / Returns:
            str: النص المُفك ترميزه / Decoded text
        """
        self._ensure_dict_loaded()

        if offset < 0 or size < 0 or offset + size > len(self._dict_data):
            logger.warning(
                f"إزاحة غير صالحة / Invalid offset: offset={offset}, size={size}, "
                f"file_size={len(self._dict_data)}"
            )
            return ""

        raw_data = self._dict_data[offset:offset + size]

        # معالجة أنواع المحتوى بناءً على sametypesequence
        # Handle content types based on sametypesequence
        sametypeseq = self.metadata.sametypesequence

        if sametypeseq and len(raw_data) > 0:
            type_char = sametypeseq[0].lower() if sametypeseq else None

            # نوع 'm' أو 'h': نص عادي / HTML
            # Type 'm' or 'h': plain text / HTML
            if type_char in ("m", "h"):
                # البايت الأول هو نوع المحتوى، والباقي هو البيانات
                # First byte is content type, rest is data
                if raw_data[0:1] in (b"m", b"h", b"M", b"H"):
                    raw_data = raw_data[1:]

            # نوع 'g': بيانات Pango markup
            # Type 'g': Pango markup data
            elif type_char == "g":
                if raw_data[0:1] in (b"g", b"G"):
                    raw_data = raw_data[1:]

            # نوع 't': ترجمة / Type 't': translation
            elif type_char == "t":
                if raw_data[0:1] in (b"t", b"T"):
                    raw_data = raw_data[1:]

        # فك الترميز / Decode
        try:
            encoding = self.encoding or "utf-8"
            text = raw_data.decode(encoding, errors="replace")
        except (UnicodeDecodeError, LookupError):
            # تجربة GBK إذا فشل UTF-8 / Try GBK if UTF-8 fails
            try:
                text = raw_data.decode("gbk", errors="replace")
            except (UnicodeDecodeError, LookupError):
                text = raw_data.decode("utf-8", errors="replace")

        return text.strip()

    # ============ واجهات عامة / Public Interfaces ============

    def get_definition(self, word: str) -> Optional[StarDictEntry]:
        """
        الحصول على تعريف كلمة معينة.
        Get the definition for a specific word.

        المعاملات / Parameters:
            word: الكلمة المراد البحث عنها / Word to look up

        العائد / Returns:
            StarDictEntry: المدخلة مع التعريف، أو None إذا لم تُعثر
                          Entry with definition, or None if not found
        """
        if not self._idx_entries:
            logger.warning("لم يتم تحميل الفهرس / Index not loaded, call read_idx() first")
            return None

        # بحث ثنائي / Binary search
        idx = self._find_word_index(word)

        if idx is not None:
            entry_word, offset, size = self._idx_entries[idx]
            definition = self._read_definition_at(offset, size)

            # جمع المرادفات / Gather synonyms
            synonyms = [
                syn for syn, syn_idx in self._synonym_map.items()
                if syn_idx == idx and syn != word
            ]

            return StarDictEntry(
                word=entry_word,
                definition=definition,
                definition_html=definition,
                offset=offset,
                size=size,
                synonyms=synonyms,
            )

        # البحث في المرادفات / Search synonyms
        if word in self._synonym_map:
            syn_idx = self._synonym_map[word]
            if 0 <= syn_idx < len(self._idx_entries):
                entry_word, offset, size = self._idx_entries[syn_idx]
                definition = self._read_definition_at(offset, size)

                synonyms = [
                    syn for syn, si in self._synonym_map.items()
                    if si == syn_idx and syn != word
                ]

                return StarDictEntry(
                    word=entry_word,
                    definition=definition,
                    definition_html=definition,
                    offset=offset,
                    size=size,
                    synonyms=synonyms,
                )

        return None

    def _find_word_index(self, word: str) -> Optional[int]:
        """
        البحث عن فهرس كلمة باستخدام البحث الثنائي.
        Find the index of a word using binary search.

        المعاملات / Parameters:
            word: الكلمة المراد البحث عنها / Word to search for

        العائد / Returns:
            int: فهرس الكلمة، أو None
                Index of the word, or None
        """
        word_lower = word.lower()
        idx = bisect_left(self._word_list, word_lower)

        if idx < len(self._word_list) and self._word_list[idx].lower() == word_lower:
            return idx

        # البحث التسلسلي القريب (للكلمات القريبة في الترتيب)
        # Nearby sequential search (for close words in order)
        for i in range(max(0, idx - 2), min(len(self._word_list), idx + 3)):
            if self._word_list[i].lower() == word_lower:
                return i

        return None

    def get_all_entries(self, limit: Optional[int] = None) -> Iterator[StarDictEntry]:
        """
        التكرار على جميع المداخل في القاموس.
        Iterate over all entries in the dictionary.

        المعاملات / Parameters:
            limit: الحد الأقصى للمداخل (اختياري) / Maximum entries (optional)

        العائد / Returns:
            Iterator[StarDictEntry]: مولّد للمداخل / Generator of entries
        """
        if not self._idx_entries:
            logger.warning("لم يتم تحميل الفهرس / Index not loaded")
            return

        count = 0
        for word, offset, size in self._idx_entries:
            if limit is not None and count >= limit:
                break

            definition = self._read_definition_at(offset, size)

            # جمع المرادفات / Gather synonyms
            synonyms = [
                syn for syn, syn_idx in self._synonym_map.items()
                if syn_idx == count and syn != word
            ]

            yield StarDictEntry(
                word=word,
                definition=definition,
                definition_html=definition,
                offset=offset,
                size=size,
                synonyms=synonyms,
            )
            count += 1

    def search(self, prefix: str, limit: int = 50) -> List[StarDictEntry]:
        """
        بحث بالبادئة في القاموس.
        Prefix search in the dictionary.

        يستخدم البحث الثنائي لتحديد نطاق المداخل المطابقة.
        Uses binary search to find the range of matching entries.

        المعاملات / Parameters:
            prefix: بادئة البحث / Search prefix
            limit: الحد الأقصى للنتائج / Maximum results

        العائد / Returns:
            List[StarDictEntry]: قائمة المداخل المطابقة / List of matching entries
        """
        if not self._word_list:
            logger.warning("لم يتم تحميل الفهرس / Index not loaded")
            return []

        prefix_lower = prefix.lower()

        # البحث الثنائي عن نقطة البداية / Binary search for start point
        start_idx = bisect_left(self._word_list, prefix_lower)

        results = []
        for i in range(start_idx, len(self._word_list)):
            if len(results) >= limit:
                break

            word = self._word_list[i]
            if not word.lower().startswith(prefix_lower):
                break

            word_entry, offset, size = self._idx_entries[i]
            definition = self._read_definition_at(offset, size)

            results.append(StarDictEntry(
                word=word_entry,
                definition=definition,
                definition_html=definition,
                offset=offset,
                size=size,
            ))

        return results

    # ============ التصدير / Export ============

    def export_to_json(self, output_path: str) -> bool:
        """
        تصدير جميع المداخل إلى صيغة OmniMedical JSON.
        Export all entries to OmniMedical JSON format.

        المعاملات / Parameters:
            output_path: مسار ملف الإخراج / Output file path

        العائد / Returns:
            bool: True إذا نجح التصدير / True if export succeeded
        """
        logger.info(f"تصدير إلى JSON: {output_path}")

        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            entries = []
            for entry in self.get_all_entries():
                entries.append(entry.to_dict())

            data = {
                "_metadata": {
                    "title": self.metadata.bookname,
                    "source_lang": self.metadata.source_lang or "ar",
                    "target_lang": self.metadata.target_lang or "en",
                    "total_entries": len(entries),
                    "format_version": "1.0",
                    "description": self.metadata.description,
                    "author": self.metadata.author,
                    "format": "stardict",
                },
                "entries": entries,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"تم تصدير {len(entries)} مدخلة إلى JSON")
            return True

        except Exception as e:
            logger.error(f"فشل التصدير إلى JSON / JSON export failed: {e}")
            self._errors.append(StarDictError(
                message=str(e),
                severity="error",
            ))
            return False

    def export_to_sqlite(self, output_path: str, table_name: str = "stardict") -> bool:
        """
        تصدير جميع المداخل إلى قاعدة بيانات SQLite.
        Export all entries to an SQLite database.

        المعاملات / Parameters:
            output_path: مسار قاعدة البيانات / Database file path
            table_name: اسم الجدول / Table name

        العائد / Returns:
            bool: True إذا نجح التصدير / True if export succeeded
        """
        logger.info(f"تصدير إلى SQLite: {output_path} (جدول: {table_name})")

        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()

            # إنشاء الجدول / Create table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    definition TEXT,
                    definition_html TEXT,
                    synonyms TEXT,
                    offset INTEGER,
                    size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # إنشاء الفهارس / Create indexes
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_word "
                f"ON {table_name}(word)"
            )

            # إدراج البيانات / Insert data
            batch_size = 1000
            batch = []

            for entry in self.get_all_entries():
                batch.append((
                    entry.word,
                    entry.definition,
                    entry.definition_html,
                    json.dumps(entry.synonyms, ensure_ascii=False),
                    entry.offset,
                    entry.size,
                ))

                if len(batch) >= batch_size:
                    cursor.executemany(
                        f"INSERT INTO {table_name} "
                        f"(word, definition, definition_html, synonyms, offset, size) "
                        f"VALUES (?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    batch.clear()

            if batch:
                cursor.executemany(
                    f"INSERT INTO {table_name} "
                    f"(word, definition, definition_html, synonyms, offset, size) "
                    f"VALUES (?, ?, ?, ?, ?, ?)",
                    batch,
                )

            # إنشاء جدول البيانات الوصفية / Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.executemany(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                [
                    (k, str(v)) for k, v in self.metadata.to_dict().items()
                ],
            )

            conn.commit()
            conn.close()

            total = len(self._idx_entries)
            logger.info(f"تم تصدير {total} مدخلة إلى SQLite")
            return True

        except Exception as e:
            logger.error(f"فشل التصدير إلى SQLite / SQLite export failed: {e}")
            self._errors.append(StarDictError(
                message=str(e),
                severity="error",
            ))
            return False

    # ============ أدوات مساعدة / Utility Methods ============

    def _find_file(self, suffix: str) -> Optional[Path]:
        """
        البحث عن ملف باللاحقة المحددة في مجلد القاموس.
        Find a file with the given suffix in the dictionary directory.

        المعاملات / Parameters:
            suffix: اللاحقة (مثل ".ifo", ".idx", ".dict") / File suffix

        العائد / Returns:
            Path: مسار الملف، أو None
                  File path, or None
        """
        # البحث عن ملف باللاحقة المحددة / Search for file with exact suffix
        for f in self.dict_dir.iterdir():
            if f.is_file() and f.name.lower().endswith(suffix.lower()):
                return f
        return None

    def get_errors(self) -> List[StarDictError]:
        """
        الحصول على قائمة الأخطاء التي حدثت أثناء القراءة.
        Get the list of errors encountered during reading.

        العائد / Returns:
            List[StarDictError]: الأخطاء المُسجّلة / Recorded errors
        """
        return self._errors.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        الحصول على إحصائيات القاموس.
        Get dictionary statistics.

        العائد / Returns:
            dict: الإحصائيات / Statistics
        """
        return {
            "bookname": self.metadata.bookname,
            "wordcount": self.metadata.wordcount,
            "actual_entries": len(self._idx_entries),
            "synonym_count": len(self._synonym_map),
            "is_64bit": self.metadata.is_64bit,
            "encoding": self.encoding or "auto",
            "source_lang": self.metadata.source_lang,
            "target_lang": self.metadata.target_lang,
            "errors": len(self._errors),
        }

    def __repr__(self) -> str:
        return (
            f"StarDictReader(bookname='{self.metadata.bookname}', "
            f"entries={len(self._idx_entries)}, "
            f"encoding='{self.encoding or 'auto'}')"
        )
