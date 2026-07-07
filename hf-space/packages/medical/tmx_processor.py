"""
معالج ملفات TMX (Translation Memory eXchange) — OmniMedical Suite

نظام متكامل لاستيراد ومعالجة ومراجعة ملفات TMX الطبية مع دعم:
- استيراد ملفات TMX 1.1/1.2/1.3/1.4
- مراجعة المصطلحات يدوياً
- اقتراحات الذكاء الاصطناعي للتصحيح
- استخراج المصطلحات الطبية
- تصدير المصطلحات المُنقّحة

الاستخدام:
    from packages.medical.tmx_processor import TMXProcessor

    processor = TMXProcessor()
    result = processor.import_tmx("medical_terms.tmx")
    entries = processor.get_entries_for_review(status="pending")
"""

import xml.etree.ElementTree as ET
import re
import os
import json
import csv
import sqlite3
import logging
import html
from typing import Dict, List, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


# ============ أنواع البيانات ============

class EntryStatus(Enum):
    """حالة المدخلة في عملية المراجعة"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    AUTO_APPROVED = "auto_approved"


class TMXVersion(Enum):
    """إصدارات TMX المدعومة"""
    V1_1 = "1.1"
    V1_2 = "1.2"
    V1_3 = "1.3"
    V1_4 = "1.4"


@dataclass
class TMXHeader:
    """بيانات رأس ملف TMX"""
    creationtool: str = ""
    creationtoolversion: str = ""
    datatype: str = "plaintext"
    segtype: str = "sentence"
    adminlang: str = "en"
    srclang: str = "en"
    o_tmf: str = ""
    creationdate: str = ""
    changedate: str = ""
    encoding: str = "UTF-8"


@dataclass
class TMXEntry:
    """مدخلة من ملف TMX (وحدة ترجمة)"""
    tu_id: str = ""
    source_lang: str = "en"
    target_lang: str = "ar"
    source_text: str = ""
    target_text: str = ""
    context: str = ""
    notes: str = ""
    creator: str = ""
    change_date: str = ""
    status: str = "pending"
    confidence: float = 0.0
    medical_category: str = ""
    is_medical: bool = False
    original_source: str = ""
    original_target: str = ""

    def to_dict(self) -> dict:
        return {
            "tu_id": self.tu_id,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "source_text": self.source_text,
            "target_text": self.target_text,
            "context": self.context,
            "notes": self.notes,
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "medical_category": self.medical_category,
            "is_medical": self.is_medical,
        }

    def to_pair(self) -> Dict[str, str]:
        """زوج ترجمة بسيط: {source_lang: text, target_lang: text}"""
        return {
            self.source_lang: self.source_text,
            self.target_lang: self.target_text,
        }


@dataclass
class MedicalTermEntry:
    """مصطلح طبي مستخرج من TMX"""
    term_source: str = ""
    term_target: str = ""
    source_lang: str = "en"
    target_lang: str = "ar"
    category: str = "general_medical"
    confidence: float = 0.0
    context: str = ""
    source: str = "tmx"
    tu_id: str = ""

    def to_dict(self) -> dict:
        return {
            "term_source": self.term_source,
            "term_target": self.term_target,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "context": self.context,
            "source": self.source,
        }


@dataclass
class TMXImportResult:
    """نتيجة استيراد ملف TMX"""
    success: bool
    file_path: str = ""
    total_tus: int = 0
    medical_terms: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    tmx_version: str = ""


# ============ أنماط طبية / Medical Patterns ============

MEDICAL_PATTERNS = {
    "anatomy": {
        "ar": r"(عظم|مفصل|عضلة|وتر|غضروف|عصب|شريان|وريد|أوردة|جمجمة|عمود|فقرات|فقرات|ضلع|كتف|كوع|رسغ|ورك|ركبة|كاحل|قدم|قَدَم|فخذ|ساق|ذراع)",
        "en": r"(bone|joint|muscle|tendon|cartilage|nerve|artery|vein|skull|spine|vertebr|rib|shoulder|elbow|wrist|hip|knee|ankle|foot|femur|tibia|fibula|humerus|radius|ulna)",
    },
    "fractures": {
        "ar": r"(كسر| fracture|مكسور|كسور|انكسار|شق|تشقق)",
        "en": r"(fracture|broken|crack|fissure|greenstick|comminuted|spiral|impacted|hairline)",
    },
    "medications": {
        "ar": r"(دواء|عقار|حبوب|كبسولة|شراب|حقنة|مضاد|مسكن|مضاد حيوي|antibiotic|analgesic|tablets|capsule)",
        "en": r"(drug|medication|tablet|capsule|syrup|injection|antibiotic|analgesic|NSAID|opioid|steroid|ibuprofen|paracetamol|aspirin|morphine|penicillin)",
    },
    "diseases": {
        "ar": r"(مرض|التهاب|ورم|سرطان|سكري|ضغط|قصور|خلل|متلازمة|تصلب|روماتيزم|نقرس)",
        "en": r"(disease|infection|tumor|cancer|diabetes|hypertension|failure|syndrome|sclerosis|arthritis|gout|osteoporosis|arthritis)",
    },
    "procedures": {
        "ar": r"(عملية|جراحة|منظار|بزل|تثبيت|تركيب|استئصال|خياطة|تجبير|جبس|إعادة تأهيل)",
        "en": r"(surgery|operation|arthroscopy|aspiration|fixation|implant|excision|repair|casting|rehabilitation|ORIF|THR|TKR)",
    },
    "lab_values": {
        "ar": r"(مخبر|فحص|تحليل|هيموغلوبين|صفيحات|كرات|بيضاء|حمراء|glucose|uric acid)",
        "en": r"(lab|test|hemoglobin|platelet|WBC|RBC|glucose|ESR|CRP|calcium|phosphorus|uric.acid|creatinine)",
    },
    "radiology": {
        "ar": r"(أشعة|صورة|إشعاع|رنين مغناطيسي|MRI|CT|سونار|تصوير|طاقة)",
        "en": r"(X-ray|radiograph|MRI|CT|ultrasound|scan|imaging|radiograph|fluoroscopy|sonograph)",
    },
}


# ============ محلل TMX / TMX Parser ============

class TMXParser:
    """
    محلل ملفات TMX.
    يدعم إصدارات TMX 1.1 حتى 1.4.
    """

    NAMESPACES = {
        "tmx": "http://www.lisa.org/tmx14",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(self, encoding: str = "UTF-8"):
        self.encoding = encoding

    def parse(self, filepath: str) -> Tuple[TMXHeader, List[TMXEntry]]:
        """
        تحليل ملف TMX واستخراج المداخل.
        
        المعاملات:
            filepath: مسار ملف TMX
            
        العائد:
            (TMXHeader, List[TMXEntry])
        """
        logger.info(f"تحليل ملف TMX: {filepath}")

        # قراءة الملف مع معالجة الترميز
        with open(filepath, "r", encoding=self.encoding, errors="replace") as f:
            content = f.read()

        # تنظيف المحتوى من وسوم غير صالحة
        content = self._sanitize_xml(content)

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"خطأ في تحليل XML: {e}")
            raise ValueError(f"ملف TMX غير صالح: {e}")

        # كشف إصدار TMX
        tmx_version = root.get("version", "1.4")
        logger.info(f"إصدار TMX: {tmx_version}")

        # تحليل الرأس
        header = self._parse_header(root)

        # تحليل المداخل
        entries = self._parse_body(root, header)

        logger.info(f"تم تحليل {len(entries)} مدخلة TMX")
        return header, entries

    def _sanitize_xml(self, content: str) -> str:
        """تنظيف محتوى XML من الأحرف غير الصالحة"""
        # إزالة BOM
        if content.startswith("\ufeff"):
            content = content[1:]
        # إزالة أحرف تحكم
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
        return content

    def _parse_header(self, root: ET.Element) -> TMXHeader:
        """تحليل رأس TMX"""
        header_el = root.find("header")
        if header_el is None:
            # البحث مع namespace
            header_el = root.find("tmx:header", self.NAMESPACES)

        header = TMXHeader()
        if header_el is not None:
            header.creationtool = header_el.get("creationtool", "")
            header.creationtoolversion = header_el.get("creationtoolversion", "")
            header.datatype = header_el.get("datatype", "plaintext")
            header.segtype = header_el.get("segtype", "sentence")
            header.adminlang = header_el.get("adminlang", "en")
            header.srclang = header_el.get("srclang", "en")
            header.creationdate = header_el.get("creationdate", "")
            header.changedate = header_el.get("changedate", "")
            header.o_tmf = header_el.get("o-tmf", "")
        else:
            header.srclang = root.get("srclang", "en")

        return header

    def _parse_body(self, root: ET.Element, header: TMXHeader) -> List[TMXEntry]:
        """تحليل جسم TMX واستخراج وحدات الترجمة"""
        entries = []

        body = root.find("body")
        if body is None:
            body = root.find("tmx:body", self.NAMESPACES)
        if body is None:
            return entries

        srclang = header.srclang or "en"

        for tu in body.findall("tu"):
            try:
                entry = self._parse_tu(tu, srclang)
                if entry and (entry.source_text.strip() or entry.target_text.strip()):
                    entries.append(entry)
            except Exception as e:
                logger.debug(f"خطأ في تحليل وحدة ترجمة: {e}")
                continue

        return entries

    def _parse_tu(self, tu: ET.Element, default_srclang: str) -> Optional[TMXEntry]:
        """تحليل وحدة ترجمة واحدة"""
        tu_id = tu.get("tuid", tu.get("id", ""))
        tu_srclang = tu.get("srclang", default_srclang)

        # استخراج جميع عناصر tuv
        tuvs = tu.findall("tuv")
        if not tuvs:
            tuvs = tu.findall("tmx:tuv", self.NAMESPACES)

        if len(tuvs) < 2:
            # محاولة استخراج من tuv واحد على الأقل
            if len(tuvs) == 1:
                lang = tuvs[0].get("xml:lang", tuvs[0].get("{http://www.w3.org/XML/1998/namespace}lang", default_srclang))
                seg = tuvs[0].find("seg") or tuvs[0].find("tmx:seg", self.NAMESPACES)
                text = self._get_element_text(seg) if seg is not None else ""
                return TMXEntry(
                    tu_id=tu_id,
                    source_lang=tu_srclang,
                    target_lang="ar",
                    source_text=text,
                    original_source=text,
                )
            return None

        # استخراج النصوص
        source_text = ""
        target_text = ""
        source_lang = tu_srclang
        target_lang = "ar"

        for tuv in tuvs:
            lang = tuv.get("xml:lang", "")
            if not lang:
                lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            if not lang:
                lang = tuv.get("lang", "")

            seg = tuv.find("seg")
            if seg is None:
                seg = tuv.find("tmx:seg", self.NAMESPACES)

            text = self._get_element_text(seg) if seg is not None else ""
            text = html.unescape(text)

            if lang.lower().startswith(source_lang.lower()):
                source_text = text
                source_lang = lang
            elif not target_text:
                target_text = text
                target_lang = lang
            elif not source_text:
                source_text = text
                source_lang = lang

        # استخراج الملاحظات
        notes = ""
        note_el = tu.find("note")
        if note_el is None:
            note_el = tu.find("tmx:note", self.NAMESPACES)
        if note_el is not None:
            notes = self._get_element_text(note_el)

        # استخراج السياق (prop)
        context = ""
        for prop in tu.findall("prop"):
            if prop.get("type", "").lower() in ("context", "domain", "subject"):
                context = self._get_element_text(prop)
                break

        return TMXEntry(
            tu_id=tu_id,
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=source_text.strip(),
            target_text=target_text.strip(),
            context=context,
            notes=notes,
            original_source=source_text.strip(),
            original_target=target_text.strip(),
            change_date=tu.get("changedate", ""),
            creator=tu.get("creationid", ""),
        )

    def _get_element_text(self, element: ET.Element) -> str:
        """استخراج النص من عنصر XML (مع معالجة العناصر المتداخلة)"""
        if element is None:
            return ""
        text = element.text or ""
        # جمع النص من العناصر الفرعية
        for child in element:
            child_text = child.text or ""
            text += child_text + (child.tail or "")
        return text.strip()

    def export_to_tmx(self, entries: List[TMXEntry], header: TMXHeader,
                      output_path: str) -> bool:
        """تصدير المداخل إلى ملف TMX"""
        logger.info(f"تصدير {len(entries)} مدخلة إلى TMX: {output_path}")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        lines = [
            '<?xml version="1.4" encoding="UTF-8"?>',
            '<!DOCTYPE tmx SYSTEM "tmx14.dtd">',
            f'<tmx version="1.4">',
            f'  <header',
            f'    creationtool="OmniMedical Suite"',
            f'    creationtoolversion="2.0"',
            f'    datatype="plaintext"',
            f'    segtype="sentence"',
            f'    adminlang="{header.adminlang}"',
            f'    srclang="{header.srclang}"',
            f'    o-tmf="OmniMedical"',
            f'    creationdate="{datetime.now().strftime("%Y%m%dT%H%M%SZ")}"',
            f'    changedate="{datetime.now().strftime("%Y%m%dT%H%M%SZ")}"',
            f'  />',
            '  <body>',
        ]

        for entry in entries:
            lines.append(f'    <tu tuid="{entry.tu_id}"'
                        f' srclang="{entry.source_lang}"'
                        f' changedate="{datetime.now().strftime("%Y%m%dT%H%M%SZ")}"'
                        f'>')
            lines.append(f'      <tuv xml:lang="{entry.source_lang}">')
            lines.append(f'        <seg>{self._escape_xml(entry.source_text)}</seg>')
            lines.append(f'      </tuv>')
            lines.append(f'      <tuv xml:lang="{entry.target_lang}">')
            lines.append(f'        <seg>{self._escape_xml(entry.target_text)}</seg>')
            lines.append(f'      </tuv>')
            if entry.notes:
                lines.append(f'      <note>{self._escape_xml(entry.notes)}</note>')
            lines.append(f'    </tu>')

        lines.extend(['  </body>', '</tmx>'])

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True
        except Exception as e:
            logger.error(f"فشل تصدير TMX: {e}")
            return False

    @staticmethod
    def _escape_xml(text: str) -> str:
        """هروب أحرف XML"""
        return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


# ============ مستخرج المصطلحات الطبية ============

class TMXMedicalExtractor:
    """
    مستخرج المصطلحات الطبية من مداخل TMX.
    يكشف المصطلحات الطبية ويعيّنها لتصنيفات مناسبة.
    """

    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF]')
    ENGLISH_PATTERN = re.compile(r'[a-zA-Z]{2,}')

    def __init__(self):
        self._compiled_patterns = {}
        for cat, langs in MEDICAL_PATTERNS.items():
            self._compiled_patterns[cat] = {
                "ar": re.compile(langs["ar"], re.IGNORECASE),
                "en": re.compile(langs["en"], re.IGNORECASE),
            }

    def extract_medical_terms(self, entries: List[TMXEntry],
                               confidence_threshold: float = 0.0) -> List[MedicalTermEntry]:
        """
        استخراج المصطلحات الطبية من مداخل TMX.
        
        المعاملات:
            entries: قائمة مداخل TMX
            confidence_threshold: الحد الأدنى للثقة
            
        العائد:
            قائمة المصطلحات الطبية المستخرجة
        """
        medical_terms = []
        seen = set()

        for entry in entries:
            # كشف المصطلحات الطبية
            result = self._analyze_entry(entry)
            
            if result and result.confidence >= confidence_threshold:
                key = (result.term_source.lower(), result.term_target.lower())
                if key not in seen:
                    seen.add(key)
                    medical_terms.append(result)

        logger.info(f"تم استخراج {len(medical_terms)} مصطلح طبي من {len(entries)} مدخلة")
        return medical_terms

    def _analyze_entry(self, entry: TMXEntry) -> Optional[MedicalTermEntry]:
        """تحليل مدخلة واحدة وكشف ما إذا كانت مصطلحاً طبياً"""
        source = entry.source_text.strip()
        target = entry.target_text.strip()

        if not source and not target:
            return None

        # كشف التصنيف
        category = self._detect_medical_category(source + " " + target)
        confidence = 0.0

        if category != "general_medical":
            confidence = self._compute_confidence(source, target, category)
        else:
            # فحص إضافي: هل المصطلح قصير ومحدد؟
            combined = source + target
            word_count = len(combined.split())
            if word_count <= 5:
                confidence = 0.3
            else:
                return None

        return MedicalTermEntry(
            term_source=source,
            term_target=target,
            source_lang=entry.source_lang,
            target_lang=entry.target_lang,
            category=category,
            confidence=confidence,
            context=entry.context or entry.notes,
            source="tmx",
            tu_id=entry.tu_id,
        )

    def _detect_medical_category(self, text: str) -> str:
        """كشف التصنيف الطبي للنص"""
        scores = {}
        for cat, patterns in self._compiled_patterns.items():
            score = 0
            for lang_pattern in patterns.values():
                matches = lang_pattern.findall(text)
                score += len(matches)
            if score > 0:
                scores[cat] = score

        if scores:
            return max(scores, key=scores.get)
        return "general_medical"

    def _compute_confidence(self, source: str, target: str,
                            category: str) -> float:
        """حساب مستوى الثقة للمصطلح"""
        confidence = 0.5  # أساسي لوجود تصنيف

        # مكافأة للقصر (المصطلحات القصيرة أكثر تحديداً)
        combined_len = len(source + target)
        if combined_len < 30:
            confidence += 0.2
        elif combined_len < 60:
            confidence += 0.1

        # مكافأة لوجود كلمات مفتاحية متعددة
        for patterns in self._compiled_patterns.get(category, {}).values():
            matches = patterns.findall(source + target)
            confidence += min(len(matches) * 0.1, 0.3)

        return min(confidence, 1.0)

    def filter_by_confidence(self, entries: List[MedicalTermEntry],
                              min_confidence: float) -> List[MedicalTermEntry]:
        """تصفية حسب مستوى الثقة"""
        return [e for e in entries if e.confidence >= min_confidence]

    def deduplicate(self, entries: List[MedicalTermEntry]) -> List[MedicalTermEntry]:
        """إزالة التكرار مع الاحتفاظ بالأعلى ثقة"""
        seen = {}
        for entry in entries:
            key = (entry.term_source.lower().strip(), entry.term_target.lower().strip())
            if key not in seen or entry.confidence > seen[key].confidence:
                seen[key] = entry
        return list(seen.values())

    def export_to_dictionary(self, entries: List[MedicalTermEntry],
                             output_path: str, format: str = "json") -> bool:
        """تصدير المصطلحات إلى ملف"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if format == "json":
            data = {
                "_metadata": {
                    "source": "TMX Medical Extraction - OmniMedical Suite",
                    "total_terms": len(entries),
                    "export_date": datetime.now().isoformat(),
                },
                "entries": [e.to_dict() for e in entries],
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        elif format == "csv":
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "term_source", "term_target", "source_lang",
                    "target_lang", "category", "confidence", "context"
                ])
                writer.writeheader()
                for e in entries:
                    writer.writerow(e.to_dict())
        return True

    def get_statistics(self, entries: List[MedicalTermEntry]) -> Dict[str, Any]:
        """إحصائيات المصطلحات المستخرجة"""
        categories = {}
        for e in entries:
            cat = e.category or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_terms": len(entries),
            "categories": categories,
            "avg_confidence": sum(e.confidence for e in entries) / max(len(entries), 1),
            "high_confidence": sum(1 for e in entries if e.confidence >= 0.7),
            "source_langs": list(set(e.source_lang for e in entries)),
            "target_langs": list(set(e.target_lang for e in entries)),
        }


# ============ معالج TMX الرئيسي ============

class TMXProcessor:
    """
    معالج TMX الرئيسي — يوفر واجهة موحدة لجميع عمليات TMX.
    
    يدمج بين محلل TMX، مستخرج المصطلحات، ونظام المراجعة.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.parser = TMXParser()
        self.extractor = TMXMedicalExtractor()
        self._entries: List[TMXEntry] = []
        self._header: Optional[TMXHeader] = None
        self._review_db: Optional[sqlite3.Connection] = None

        if db_path:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._init_review_db()

    def _init_review_db(self):
        """تهيئة قاعدة بيانات المراجعة"""
        self._review_db = sqlite3.connect(self.db_path)
        self._review_db.row_factory = sqlite3.Row
        cursor = self._review_db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tmx_entries (
                tu_id TEXT PRIMARY KEY,
                source_lang TEXT DEFAULT 'en',
                target_lang TEXT DEFAULT 'ar',
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                original_source TEXT,
                original_target TEXT,
                context TEXT,
                notes TEXT,
                status TEXT DEFAULT 'pending',
                confidence REAL DEFAULT 0.0,
                medical_category TEXT,
                is_medical INTEGER DEFAULT 0,
                creator TEXT,
                change_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tu_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_source TEXT,
                old_target TEXT,
                new_source TEXT,
                new_target TEXT,
                reviewer TEXT DEFAULT 'user',
                notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tu_id TEXT NOT NULL,
                suggested_source TEXT,
                suggested_target TEXT,
                suggestion_type TEXT,
                model TEXT DEFAULT 'default',
                confidence REAL DEFAULT 0.0,
                accepted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tu_id) REFERENCES tmx_entries(tu_id)
            )
        """)

        # الفهارس
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tmx_status ON tmx_entries(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tmx_medical ON tmx_entries(is_medical)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tmx_category ON tmx_entries(medical_category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_tu ON review_history(tu_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_tu ON ai_suggestions(tu_id)")

        self._review_db.commit()

    def import_tmx(self, filepath: str, auto_detect_medical: bool = True,
                   confidence_threshold: float = 0.0) -> TMXImportResult:
        """
        استيراد ملف TMX ومعالجته.
        
        المعاملات:
            filepath: مسار ملف TMX
            auto_detect_medical: كشف المصطلحات الطبية تلقائياً
            confidence_threshold: الحد الأدنى للثقة
            
        العائد:
            TMXImportResult
        """
        start = datetime.now()
        result = TMXImportResult(success=False, file_path=filepath)

        try:
            if not os.path.exists(filepath):
                result.errors.append(f"الملف غير موجود: {filepath}")
                return result

            # تحليل الملف
            self._header, self._entries = self.parser.parse(filepath)
            result.total_tus = len(self._entries)

            # كشف المصطلحات الطبية
            if auto_detect_medical:
                medical_terms = self.extractor.extract_medical_terms(
                    self._entries, confidence_threshold
                )
                result.medical_terms = len(medical_terms)

                # تحديث المداخل بالتصنيفات
                medical_map = {mt.tu_id: mt for mt in medical_terms if mt.tu_id}
                for entry in self._entries:
                    if entry.tu_id in medical_map:
                        mt = medical_map[entry.tu_id]
                        entry.is_medical = True
                        entry.medical_category = mt.category
                        entry.confidence = mt.confidence

            # حفظ في قاعدة بيانات المراجعة
            if self._review_db:
                self._save_entries_to_db(self._entries)

            result.success = True
            result.duration_seconds = (datetime.now() - start).total_seconds()

            logger.info(
                f"استيراد TMX ناجح: {result.total_tus} مدخلة, "
                f"{result.medical_terms} مصطلح طبي"
            )

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"فشل استيراد TMX: {e}", exc_info=True)

        return result

    def _save_entries_to_db(self, entries: List[TMXEntry]):
        """حفظ المداخل في قاعدة بيانات المراجعة"""
        cursor = self._review_db.cursor()
        batch = []
        for entry in entries:
            batch.append((
                entry.tu_id, entry.source_lang, entry.target_lang,
                entry.source_text, entry.target_text,
                entry.original_source, entry.original_target,
                entry.context, entry.notes, entry.status,
                entry.confidence, entry.medical_category,
                1 if entry.is_medical else 0,
                entry.creator, entry.change_date,
            ))
        cursor.executemany("""
            INSERT OR REPLACE INTO tmx_entries
            (tu_id, source_lang, target_lang, source_text, target_text,
             original_source, original_target, context, notes, status,
             confidence, medical_category, is_medical, creator, change_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        self._review_db.commit()

    # ============ عمليات المراجعة ============

    def get_entries_for_review(self, status: str = "pending",
                                medical_only: bool = False,
                                page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """
        الحصول على مداخل للمراجعة مع ترقيم الصفحات.
        """
        if not self._review_db:
            return {"entries": [], "total": 0, "page": page, "pages": 0}

        cursor = self._review_db.cursor()
        conditions = ["status = ?"]
        params: list = [status]

        if medical_only:
            conditions.append("is_medical = 1")

        where = " AND ".join(conditions)

        # العدد الكلي
        cursor.execute(f"SELECT COUNT(*) FROM tmx_entries WHERE {where}", params)
        total = cursor.fetchone()[0]

        # البيانات
        offset = (page - 1) * page_size
        params_with_limit = params + [offset, page_size]
        cursor.execute(
            f"SELECT * FROM tmx_entries WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params_with_limit,
        )

        entries = [dict(row) for row in cursor.fetchall()]

        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    def update_entry(self, tu_id: str, source_text: Optional[str] = None,
                     target_text: Optional[str] = None,
                     notes: Optional[str] = None,
                     status: Optional[str] = None) -> bool:
        """تحديث مدخلة (بعد مراجعة المستخدم)"""
        if not self._review_db:
            return False

        cursor = self._review_db.cursor()

        # قراءة القيمة الحالية
        cursor.execute("SELECT * FROM tmx_entries WHERE tu_id = ?", (tu_id,))
        row = cursor.fetchone()
        if not row:
            return False

        old_source = row["source_text"]
        old_target = row["target_text"]

        # التحديث
        updates = []
        params = []
        if source_text is not None:
            updates.append("source_text = ?")
            params.append(source_text)
        if target_text is not None:
            updates.append("target_text = ?")
            params.append(target_text)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(tu_id)
            cursor.execute(
                f"UPDATE tmx_entries SET {', '.join(updates)} WHERE tu_id = ?",
                params,
            )

            # تسجيل في سجل المراجعة
            action = "approve" if status == "approved" else ("reject" if status == "rejected" else "modify")
            cursor.execute("""
                INSERT INTO review_history (tu_id, action, old_source, old_target,
                                            new_source, new_target, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tu_id, action, old_source, old_target,
                source_text or old_source, target_text or old_target, notes,
            ))

            self._review_db.commit()
            return True

        return False

    def batch_update(self, tu_ids: List[str], status: str = "approved") -> int:
        """تحديث مجموعة مداخل دفعة واحدة"""
        if not self._review_db or not tu_ids:
            return 0

        cursor = self._review_db.cursor()
        placeholders = ",".join("?" * len(tu_ids))
        cursor.execute(
            f"UPDATE tmx_entries SET status = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE tu_id IN ({placeholders})",
            [status] + tu_ids,
        )
        self._review_db.commit()
        return cursor.rowcount

    def get_review_statistics(self) -> Dict[str, Any]:
        """إحصائيات المراجعة"""
        if not self._review_db:
            return {}

        cursor = self._review_db.cursor()

        # إحصائيات الحالات
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM tmx_entries GROUP BY status
        """)
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # إحصائيات التصنيفات الطبية
        cursor.execute("""
            SELECT medical_category, COUNT(*) as count
            FROM tmx_entries WHERE is_medical = 1 GROUP BY medical_category
        """)
        category_counts = {row["medical_category"]: row["count"] for row in cursor.fetchall()}

        total = sum(status_counts.values())

        return {
            "total_entries": total,
            "by_status": status_counts,
            "medical_terms": sum(category_counts.values()),
            "by_category": category_counts,
            "pending": status_counts.get("pending", 0),
            "approved": status_counts.get("approved", 0),
            "rejected": status_counts.get("rejected", 0),
            "modified": status_counts.get("modified", 0),
            "completion_rate": round(
                (status_counts.get("approved", 0) / total * 100) if total > 0 else 0, 1
            ),
        }

    # ============ اقتراحات الذكاء الاصطناعي ============

    def get_ai_suggestions(self, tu_id: str) -> List[Dict[str, Any]]:
        """الحصول على اقتراحات الذكاء الاصطناعي لمدخلة"""
        if not self._review_db:
            return []

        cursor = self._review_db.cursor()
        cursor.execute(
            "SELECT * FROM ai_suggestions WHERE tu_id = ? ORDER BY confidence DESC",
            (tu_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def save_ai_suggestion(self, tu_id: str, suggested_source: str,
                           suggested_target: str, suggestion_type: str = "correction",
                           model: str = "default", confidence: float = 0.5):
        """حفظ اقتراح الذكاء الاصطناعي"""
        if not self._review_db:
            return

        cursor = self._review_db.cursor()
        cursor.execute("""
            INSERT INTO ai_suggestions (tu_id, suggested_source, suggested_target,
                                       suggestion_type, model, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tu_id, suggested_source, suggested_target, suggestion_type, model, confidence))
        self._review_db.commit()

    def accept_ai_suggestion(self, suggestion_id: int) -> bool:
        """قبول اقتراح الذكاء الاصطناعي وتطبيقه"""
        if not self._review_db:
            return False

        cursor = self._review_db.cursor()
        cursor.execute(
            "SELECT * FROM ai_suggestions WHERE id = ?", (suggestion_id,)
        )
        suggestion = cursor.fetchone()
        if not suggestion:
            return False

        # تطبيق الاقتراح على المدخلة
        result = self.update_entry(
            tu_id=suggestion["tu_id"],
            source_text=suggestion["suggested_source"],
            target_text=suggestion["suggested_target"],
            status="modified",
        )

        if result:
            cursor.execute(
                "UPDATE ai_suggestions SET accepted = 1 WHERE id = ?",
                (suggestion_id,),
            )
            self._review_db.commit()

        return result

    # ============ التصدير ============

    def export_corrected(self, output_path: str,
                         status_filter: Optional[str] = None) -> bool:
        """تصدير المداخل المُنقّحة إلى ملف TMX"""
        if not self._review_db or not self._header:
            return False

        cursor = self._review_db.cursor()
        if status_filter:
            cursor.execute(
                "SELECT * FROM tmx_entries WHERE status = ?", (status_filter,)
            )
        else:
            cursor.execute("SELECT * FROM tmx_entries WHERE status != 'rejected'")

        entries = []
        for row in cursor.fetchall():
            entries.append(TMXEntry(
                tu_id=row["tu_id"],
                source_lang=row["source_lang"],
                target_lang=row["target_lang"],
                source_text=row["source_text"],
                target_text=row["target_text"],
                context=row["context"],
                notes=row["notes"],
                status=row["status"],
            ))

        return self.parser.export_to_tmx(entries, self._header, output_path)

    def export_medical_terms(self, output_path: str,
                             format: str = "json") -> bool:
        """تصدير المصطلحات الطبية المستخرجة"""
        if not self._review_db:
            return False

        cursor = self._review_db.cursor()
        cursor.execute("""
            SELECT * FROM tmx_entries WHERE is_medical = 1 AND status != 'rejected'
        """)

        entries = []
        for row in cursor.fetchall():
            entries.append(MedicalTermEntry(
                term_source=row["source_text"],
                term_target=row["target_text"],
                source_lang=row["source_lang"],
                target_lang=row["target_lang"],
                category=row["medical_category"],
                confidence=row["confidence"],
                context=row["context"],
                source="tmx_reviewed",
                tu_id=row["tu_id"],
            ))

        return self.extractor.export_to_dictionary(entries, output_path, format)

    def close(self):
        """إغلاق قاعدة البيانات"""
        if self._review_db:
            self._review_db.close()
            self._review_db = None
