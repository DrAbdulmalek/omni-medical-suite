"""
مدير القواميس الطبية — OmniMedical Suite

نظام متكامل لإدارة واستيراد وتصدير وبحث القواميس الطبية.
يدعم ملفات BGL و DIC و JSON و CSV، ويتكامل مع قاعدة بيانات المشروع.

الاستخدام:
    from packages.medical.dictionary_manager import MedicalDictionaryManager
    
    manager = MedicalDictionaryManager(db_path="data/dictionaries/medical_terms.db")
    
    # استيراد قاموس
    result = manager.import_dictionary("path/to/dictionary.bgl", title="Stedman's Medical")
    
    # بحث
    results = manager.search("fracture", language="en")
    
    # الحصول على مصحح OCR
    corrections = manager.get_ocr_corrections()
"""

import json
import os
import sqlite3
import re
import logging
import csv
import shutil
from typing import Dict, List, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from packages.medical.bgl_converter import BGLConverter, DictionaryEntry, OutputFormat

logger = logging.getLogger(__name__)


# ============ أنواع البيانات ============

@dataclass
class ImportResult:
    """نتيجة استيراد قاموس"""
    success: bool
    dict_id: Optional[int] = None
    title: str = ""
    total_entries: int = 0
    duplicates_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    source_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResult:
    """نتيجة بحث في القاموس"""
    term_ar: str = ""
    term_en: str = ""
    definition: str = ""
    category: str = ""
    frequency: int = 0
    source_dict: str = ""
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DictionaryInfo:
    """معلومات عن قاموس مُستورد"""
    id: int
    name: str
    title: str = ""
    source_lang: str = "ar"
    target_lang: str = "en"
    total_entries: int = 0
    format_version: str = "1.0"
    import_date: str = ""
    file_path: str = ""
    file_size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ============ مدير القواميس ============

class MedicalDictionaryManager:
    """
    مدير القواميس الطبية المتكامل.
    
    يوفر واجهة موحدة لاستيراد وبحث وتصدير القواميس الطبية
    مع دعم كامل لعمليات CRUD والتكامل مع خط أنابيب OCR و NLP.
    
    الميزات:
    - استيراد من BGL و DIC و JSON و CSV
    - بحث ثنائي اللغة (عربي/إنجليزي) مع دعم البحث الجزئي
    - تصدير إلى صيغ متعددة
    - تكامل مع نظام تصحيح OCR
    - تتبع تكرار المصطلحات
    - دعم مصادر قاموس متعددة
    """

    # الأنماط لتحديد اللغة
    ARABIC_PATTERN = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
    ENGLISH_PATTERN = re.compile(r'[a-zA-Z]{2,}')

    # التصنيفات الطبية الافتراضية
    DEFAULT_CATEGORIES = [
        "anatomy", "fractures", "diseases", "medications",
        "procedures", "instruments", "lab_values", "diagnosis",
        "symptoms", "general_medical", "orthopedic", "radiology",
        "pathology", "pharmacology", "surgical", "emergency",
    ]

    def __init__(self, db_path: str = "data/dictionaries/medical_terms.db"):
        """
        تهيئة مدير القواميس.
        
        المعاملات:
            db_path: مسار قاعدة بيانات SQLite
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        self.converter = BGLConverter()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """الحصول على اتصال بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_database(self):
        """تهيئة جداول قاعدة البيانات"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # جدول القواميس المستوردة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dictionaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                title TEXT,
                source_lang TEXT DEFAULT 'ar',
                target_lang TEXT DEFAULT 'en',
                total_entries INTEGER DEFAULT 0,
                format_version TEXT DEFAULT '1.0',
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                last_imported TIMESTAMP
            )
        """)

        # جدول المصطلحات الطبية (الجدول الرئيسي)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_ar TEXT,
                term_en TEXT,
                definition TEXT,
                category TEXT,
                frequency INTEGER DEFAULT 1,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                dict_id INTEGER,
                source_entry_id INTEGER,
                FOREIGN KEY (dict_id) REFERENCES dictionaries(id) ON DELETE CASCADE,
                CONSTRAINT unique_term UNIQUE(term_ar, term_en)
            )
        """)

        # جدول تصحيحات OCR
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wrong_term TEXT NOT NULL,
                correct_term TEXT NOT NULL,
                language TEXT CHECK(language IN ('ar', 'en', 'both')) DEFAULT 'ar',
                confidence REAL DEFAULT 0.0,
                usage_count INTEGER DEFAULT 0,
                source TEXT,
                dict_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (dict_id) REFERENCES dictionaries(id) ON DELETE SET NULL
            )
        """)

        # جدول المصطلحات المحمية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS protected_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT UNIQUE NOT NULL,
                language TEXT DEFAULT 'both',
                category TEXT,
                reason TEXT,
                dict_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول المرادفات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synonyms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term1_id INTEGER NOT NULL,
                term2_id INTEGER NOT NULL,
                similarity REAL DEFAULT 1.0,
                FOREIGN KEY (term1_id) REFERENCES medical_terms(id) ON DELETE CASCADE,
                FOREIGN KEY (term2_id) REFERENCES medical_terms(id) ON DELETE CASCADE
            )
        """)

        # جدول سجل الاستيراد
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dict_id INTEGER,
                action TEXT NOT NULL,
                entries_processed INTEGER DEFAULT 0,
                entries_added INTEGER DEFAULT 0,
                entries_skipped INTEGER DEFAULT 0,
                errors TEXT,
                duration_ms INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dict_id) REFERENCES dictionaries(id) ON DELETE SET NULL
            )
        """)

        # === الفهارس ===
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_ar ON medical_terms(term_ar)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_en ON medical_terms(term_en)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_category ON medical_terms(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_frequency ON medical_terms(frequency)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_terms_dict ON medical_terms(dict_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_wrong ON ocr_corrections(wrong_term)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_correct ON ocr_corrections(correct_term)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_corrections_lang ON ocr_corrections(language)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_protected_term ON protected_terms(term)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dicts_active ON dictionaries(is_active)")

        conn.commit()
        conn.close()
        logger.info(f"تم تهيئة قاعدة البيانات: {self.db_path}")

    # ============ عمليات الاستيراد ============

    def import_dictionary(self, file_path: str, title: Optional[str] = None,
                          source_lang: str = "ar", target_lang: str = "en",
                          category: Optional[str] = None,
                          import_corrections: bool = True,
                          import_protected: bool = True,
                          dict_name: Optional[str] = None) -> ImportResult:
        """
        استيراد قاموس طبي من ملف.
        
        المعاملات:
            file_path: مسار ملف القاموس (BGL, DIC, JSON, CSV)
            title: عنوان القاموس (اختياري)
            source_lang: لغة المصدر
            target_lang: لغة الهدف
            category: تصنيف افتراضي
            import_corrections: هل يتم استيراد التصحيحات تلقائياً
            import_protected: هل يتم حماية المصطلحات المستوردة
            dict_name: اسم فريد للقاموس
            
        العائد:
            ImportResult مع تفاصيل الاستيراد
        """
        start_time = datetime.now()
        result = ImportResult(
            success=False,
            title=title or Path(file_path).stem,
            source_file=file_path,
        )

        try:
            # التحقق من الملف
            if not os.path.exists(file_path):
                result.errors.append(f"الملف غير موجود: {file_path}")
                return result

            file_size = os.path.getsize(file_path)

            # قراءة المداخل باستخدام المحول
            entries = self.converter.read_file(file_path)

            if not entries:
                result.errors.append(f"لم يتم العثور على مداخل في الملف: {file_path}")
                return result

            # تحديد اسم القاموس
            name = dict_name or Path(file_path).stem

            # تسجيل القاموس في قاعدة البيانات
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO dictionaries (name, title, source_lang, target_lang, 
                                               total_entries, file_path, file_size, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        total_entries = excluded.total_entries,
                        last_imported = CURRENT_TIMESTAMP,
                        file_size = excluded.file_size
                """, (name, title or name, source_lang, target_lang,
                      len(entries), file_path, file_size, ""))
                
                cursor.execute("SELECT id FROM dictionaries WHERE name = ?", (name,))
                row = cursor.fetchone()
                dict_id = row['id']
                result.dict_id = dict_id

                # استيراد المداخل
                added = 0
                skipped = 0
                corrections_list = []
                protected_list = []

                for entry in entries:
                    term = entry.term.strip()
                    definition = entry.definition.strip()

                    if not term:
                        continue

                    # تحديد اللغة والتصنيف
                    term_ar, term_en, entry_category = self._classify_entry(
                        term, definition, category, source_lang, target_lang
                    )

                    if not term_ar and not term_en:
                        skipped += 1
                        continue

                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO medical_terms
                            (term_ar, term_en, definition, category, frequency, dict_id)
                            VALUES (?, ?, ?, ?, 1, ?)
                        """, (term_ar, term_en, definition, entry_category, dict_id))

                        if cursor.rowcount > 0:
                            added += 1
                        else:
                            skipped += 1

                            # تحديث التكرار
                            cursor.execute("""
                                UPDATE medical_terms 
                                SET frequency = frequency + 1,
                                    last_seen = CURRENT_TIMESTAMP
                                WHERE (term_ar = ? OR (term_ar IS NULL AND ? IS NULL))
                                  AND (term_en = ? OR (term_en IS NULL AND ? IS NULL))
                            """, (term_ar, term_ar, term_en, term_en))

                    except sqlite3.IntegrityError:
                        skipped += 1

                    # جمع التصحيحات المحتملة
                    if import_corrections and entry_category == "ocr_correction":
                        corrections_list.append((term, definition, source_lang))

                    # جمع المصطلحات المحمية
                    if import_protected and term and definition:
                        protected_list.append((term, entry_category))

                # استيراد التصحيحات
                if corrections_list:
                    self._import_corrections(cursor, corrections_list, dict_id)

                # استيراد المصطلحات المحمية
                if protected_list:
                    self._import_protected_terms(cursor, protected_list, dict_id)

                # تسجيل عملية الاستيراد
                duration = (datetime.now() - start_time).total_seconds()
                cursor.execute("""
                    INSERT INTO import_log (dict_id, action, entries_processed,
                                           entries_added, entries_skipped, duration_ms)
                    VALUES (?, 'import', ?, ?, ?, ?)
                """, (dict_id, len(entries), added, skipped, int(duration * 1000)))

                conn.commit()

                result.success = True
                result.total_entries = added
                result.duplicates_skipped = skipped
                result.duration_seconds = duration

                logger.info(
                    f"استيراد ناجح: {name} — {added} مدخلة مُضافة, "
                    f"{skipped} مكررة, {duration:.2f} ثانية"
                )

            finally:
                conn.close()

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"فشل استيراد القاموس: {e}", exc_info=True)

        return result

    def _classify_entry(self, term: str, definition: str,
                        default_category: Optional[str],
                        source_lang: str, target_lang: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        تصنيف مدخلة قاموسية: تحديد اللغة والتصنيف.
        
        العائد:
            (term_ar, term_en, category)
        """
        has_arabic = bool(self.ARABIC_PATTERN.search(term))
        has_english = bool(self.ENGLISH_PATTERN.search(term))

        term_ar = None
        term_en = None

        if has_arabic and has_english:
            # مصطلح مختلط — فصل اللغات
            ar_match = self.ARABIC_PATTERN.findall(term)
            en_match = self.ENGLISH_PATTERN.findall(term)
            term_ar = ''.join(ar_match).strip() if ar_match else None
            term_en = ' '.join(en_match).strip() if en_match else None
        elif has_arabic:
            term_ar = term.strip()
            # محاولة استخراج المصطلح الإنجليزي من التعريف
            if definition:
                en_words = self.ENGLISH_PATTERN.findall(definition)
                term_en = ' '.join(en_words[:5]).strip() if en_words else None
        elif has_english:
            term_en = term.strip()
            # محاولة استخراج المصطلح العربي من التعريف
            if definition:
                ar_chars = self.ARABIC_PATTERN.findall(definition)
                term_ar = ''.join(ar_chars).strip() if ar_chars else None
        else:
            # لا يمكن تحديد اللغة
            if source_lang in ('ar', 'arabic'):
                term_ar = term.strip()
            else:
                term_en = term.strip()

        # تحديد التصنيف
        category = default_category or "general_medical"
        if definition:
            extracted_cat = self._extract_category(definition)
            if extracted_cat:
                category = extracted_cat

        # كشف تصحيحات OCR
        if definition and re.search(r'التصحيح|correction|correct', definition, re.IGNORECASE):
            category = "ocr_correction"

        return term_ar, term_en, category

    def _extract_category(self, text: str) -> Optional[str]:
        """استخراج التصنيف من النص"""
        # البحث عن تصنيف بين أقواس
        match = re.search(r'\[([^\]]+)\]', text)
        if match:
            cat_text = match.group(1).strip().lower()
            for cat in self.DEFAULT_CATEGORIES:
                if cat in cat_text:
                    return cat

        # البحث عن كلمات مفتاحية
        category_keywords = {
            "anatomy": ["anatomy", "تشريح", "عظم", "joint", "مفصل"],
            "fractures": ["fracture", "كسر", "break"],
            "medications": ["drug", "medication", "دواء", "عقار", "medicine"],
            "procedures": ["procedure", "surgery", "عملية", "جراحة"],
            "lab_values": ["lab", "normal", "مخبري", "مختبر"],
            "diseases": ["disease", "مرض", "syndrome", "متلازمة"],
            "diagnosis": ["diagnosis", "تشخيص"],
            "symptoms": ["symptom", "عرض", "علامة"],
            "radiology": ["x-ray", "xray", "أشعة", "imaging", "تصوير"],
            "pathology": ["pathology", "علم الأمراض"],
            "pharmacology": ["dose", "جرعة", "mg", "tablet"],
        }

        text_lower = text.lower()
        for cat, keywords in category_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return cat

        return None

    def _import_corrections(self, cursor, corrections: List[Tuple[str, str, str]],
                            dict_id: int):
        """استيراد تصحيحات OCR"""
        for wrong, correct, lang in corrections:
            # تنظيف النص
            clean_wrong = wrong.strip()
            clean_correct = correct.strip().replace("التصحيح:", "").strip()

            if not clean_wrong or not clean_correct:
                continue

            language = 'ar' if self.ARABIC_PATTERN.search(clean_wrong) else 'en'

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO ocr_corrections
                    (wrong_term, correct_term, language, confidence, source, dict_id)
                    VALUES (?, ?, ?, 0.8, 'import', ?)
                """, (clean_wrong, clean_correct, language, dict_id))
            except sqlite3.IntegrityError:
                pass

    def _import_protected_terms(self, cursor, terms: List[Tuple[str, str]],
                                dict_id: int):
        """استيراد مصطلحات محمية"""
        for term, category in terms:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO protected_terms (term, category, dict_id)
                    VALUES (?, ?, ?)
                """, (term.strip(), category, dict_id))
            except sqlite3.IntegrityError:
                pass

    # ============ عمليات البحث ============

    def search(self, query: str, language: Optional[str] = None,
               category: Optional[str] = None, limit: int = 50,
               exact: bool = False, dict_id: Optional[int] = None) -> List[SearchResult]:
        """
        بحث في القاموس الطبي.
        
        المعاملات:
            query: نص البحث
            language: لغة البحث ('ar', 'en', أو None للبحث في كليهما)
            category: تصفية حسب التصنيف
            limit: الحد الأقصى للنتائج
            exact: بحث مطابق تماماً
            dict_id: تصفية حسب قاموس محدد
            
        العائد:
            قائمة نتائج البحث
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query_clean = query.strip()
        results = []

        try:
            if exact:
                # بحث مطابق
                if language == 'ar' or (language is None and self.ARABIC_PATTERN.search(query_clean)):
                    cursor.execute("""
                        SELECT mt.*, d.title as dict_title
                        FROM medical_terms mt
                        LEFT JOIN dictionaries d ON mt.dict_id = d.id
                        WHERE mt.term_ar = ? AND mt.is_active = 1
                        ORDER BY mt.frequency DESC
                        LIMIT ?
                    """, (query_clean, limit))
                else:
                    cursor.execute("""
                        SELECT mt.*, d.title as dict_title
                        FROM medical_terms mt
                        LEFT JOIN dictionaries d ON mt.dict_id = d.id
                        WHERE mt.term_en = ?
                        ORDER BY mt.frequency DESC
                        LIMIT ?
                    """, (query_clean, limit))
            else:
                # بحث جزئي (LIKE)
                like_pattern = f"%{query_clean}%"
                
                conditions = []
                params = []

                if language == 'ar' or (language is None and self.ARABIC_PATTERN.search(query_clean)):
                    conditions.append("mt.term_ar LIKE ?")
                    params.append(like_pattern)
                if language == 'en' or (language is None and self.ENGLISH_PATTERN.search(query_clean)):
                    conditions.append("mt.term_en LIKE ?")
                    params.append(like_pattern)
                if language is None:
                    conditions.append("mt.definition LIKE ?")
                    params.append(like_pattern)

                if not conditions:
                    conditions.append("mt.term_ar LIKE ?")
                    params.append(like_pattern)

                where_clause = " OR ".join(conditions)

                if category:
                    where_clause += " AND mt.category = ?"
                    params.append(category)

                if dict_id:
                    where_clause += " AND mt.dict_id = ?"
                    params.append(dict_id)

                params.append(limit)

                cursor.execute(f"""
                    SELECT mt.*, d.title as dict_title
                    FROM medical_terms mt
                    LEFT JOIN dictionaries d ON mt.dict_id = d.id
                    WHERE ({where_clause})
                    ORDER BY mt.frequency DESC, mt.last_seen DESC
                    LIMIT ?
                """, params)

            rows = cursor.fetchall()
            for row in rows:
                results.append(SearchResult(
                    term_ar=row['term_ar'] or "",
                    term_en=row['term_en'] or "",
                    definition=row['definition'] or "",
                    category=row['category'] or "",
                    frequency=row['frequency'] or 0,
                    source_dict=row['dict_title'] or "",
                    relevance_score=self._compute_relevance(query_clean, row),
                ))

        finally:
            conn.close()

        return results

    def _compute_relevance(self, query: str, row: sqlite3.Row) -> float:
        """حساب درجة صلة النتيجة"""
        score = 0.0
        query_lower = query.lower()

        # تطابق تام
        term_ar = (row['term_ar'] or "").lower()
        term_en = (row['term_en'] or "").lower()

        if term_ar == query_lower or term_en == query_lower:
            score += 10.0

        # تطابق جزئي
        if query_lower in term_ar:
            score += 5.0 * (len(query) / max(len(term_ar), 1))
        if query_lower in term_en:
            score += 5.0 * (len(query) / max(len(term_en), 1))

        # عامل التكرار
        score += min(row['frequency'] or 0, 10) * 0.1

        # عامل التصنيف
        if row['category']:
            score += 0.5

        return round(score, 2)

    def search_by_prefix(self, prefix: str, language: str = "ar",
                         limit: int = 20) -> List[SearchResult]:
        """بحث بالمصطلحات التي تبدأ ببادئة معينة"""
        return self.search(prefix, language=language, limit=limit)

    def search_by_category(self, category: str, limit: int = 100) -> List[SearchResult]:
        """بحث حسب التصنيف"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT mt.*, d.title as dict_title
                FROM medical_terms mt
                LEFT JOIN dictionaries d ON mt.dict_id = d.id
                WHERE mt.category = ?
                ORDER BY mt.frequency DESC
                LIMIT ?
            """, (category, limit))

            return [
                SearchResult(
                    term_ar=row['term_ar'] or "",
                    term_en=row['term_en'] or "",
                    definition=row['definition'] or "",
                    category=row['category'] or "",
                    frequency=row['frequency'] or 0,
                    source_dict=row['dict_title'] or "",
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_categories(self) -> List[Dict[str, Any]]:
        """الحصول على قائمة التصنيفات مع عدد المصطلحات"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT category, COUNT(*) as count, AVG(frequency) as avg_frequency
                FROM medical_terms
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
            return [
                {"category": row['category'], "count": row['count'],
                 "avg_frequency": round(row['avg_frequency'], 2)}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ============ عمليات التصحيح ============

    def get_ocr_corrections(self, language: Optional[str] = None) -> Dict[str, str]:
        """
        الحصول على جميع تصحيحات OCR.
        
        العائد:
            {wrong_term: correct_term}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if language:
                cursor.execute("""
                    SELECT wrong_term, correct_term
                    FROM ocr_corrections
                    WHERE language = ? AND usage_count >= 0
                    ORDER BY confidence DESC, usage_count DESC
                """, (language,))
            else:
                cursor.execute("""
                    SELECT wrong_term, correct_term
                    FROM ocr_corrections
                    WHERE usage_count >= 0
                    ORDER BY confidence DESC, usage_count DESC
                """)

            return {row['wrong_term']: row['correct_term'] for row in cursor.fetchall()}
        finally:
            conn.close()

    def add_correction(self, wrong: str, correct: str, language: str = "ar",
                       confidence: float = 0.9) -> bool:
        """إضافة تصحيح OCR جديد"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO ocr_corrections
                (wrong_term, correct_term, language, confidence, usage_count, source)
                VALUES (?, ?, ?, ?, 0, 'user')
            """, (wrong, correct, language, confidence))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"فشل إضافة تصحيح: {e}")
            return False
        finally:
            conn.close()

    def lookup_correction(self, term: str) -> Optional[str]:
        """البحث عن تصحيح لمصطلح"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT correct_term
                FROM ocr_corrections
                WHERE wrong_term = ?
                ORDER BY confidence DESC, usage_count DESC
                LIMIT 1
            """, (term,))
            row = cursor.fetchone()
            return row['correct_term'] if row else None
        finally:
            conn.close()

    # ============ عمليات المصطلحات المحمية ============

    def get_protected_terms(self, language: Optional[str] = None) -> List[str]:
        """الحصول على قائمة المصطلحات المحمية"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if language:
                cursor.execute(
                    "SELECT term FROM protected_terms WHERE language IN (?, 'both')",
                    (language,))
            else:
                cursor.execute("SELECT term FROM protected_terms")

            return [row['term'] for row in cursor.fetchall()]
        finally:
            conn.close()

    def is_protected(self, term: str) -> bool:
        """التحقق مما إذا كان مصطلح محمياً"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT 1 FROM protected_terms WHERE term = ?", (term,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    # ============ عمليات إدارة القواميس ============

    def list_dictionaries(self) -> List[DictionaryInfo]:
        """قائمة جميع القواميس المستوردة"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM dictionaries
                ORDER BY import_date DESC
            """)
            return [
                DictionaryInfo(
                    id=row['id'],
                    name=row['name'],
                    title=row['title'] or "",
                    source_lang=row['source_lang'] or "ar",
                    target_lang=row['target_lang'] or "en",
                    total_entries=row['total_entries'] or 0,
                    format_version=row['format_version'] or "1.0",
                    import_date=row['import_date'] or "",
                    file_path=row['file_path'] or "",
                    file_size=row['file_size'] or 0,
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_dictionary_stats(self) -> Dict[str, Any]:
        """إحصائيات عامة عن القواميس"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # إجمالي القواميس
            cursor.execute("SELECT COUNT(*) FROM dictionaries WHERE is_active = 1")
            total_dicts = cursor.fetchone()[0]

            # إجمالي المصطلحات
            cursor.execute("SELECT COUNT(*) FROM medical_terms")
            total_terms = cursor.fetchone()[0]

            # المصطلحات العربية
            cursor.execute("SELECT COUNT(*) FROM medical_terms WHERE term_ar IS NOT NULL")
            arabic_terms = cursor.fetchone()[0]

            # المصطلحات الإنجليزية
            cursor.execute("SELECT COUNT(*) FROM medical_terms WHERE term_en IS NOT NULL")
            english_terms = cursor.fetchone()[0]

            # التصحيحات
            cursor.execute("SELECT COUNT(*) FROM ocr_corrections")
            total_corrections = cursor.fetchone()[0]

            # المصطلحات المحمية
            cursor.execute("SELECT COUNT(*) FROM protected_terms")
            total_protected = cursor.fetchone()[0]

            # التصنيفات
            cursor.execute("SELECT COUNT(DISTINCT category) FROM medical_terms WHERE category IS NOT NULL")
            total_categories = cursor.fetchone()[0]

            # حجم قاعدة البيانات
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            return {
                "total_dictionaries": total_dicts,
                "total_terms": total_terms,
                "arabic_terms": arabic_terms,
                "english_terms": english_terms,
                "bilingual_terms": total_terms - arabic_terms - english_terms + min(arabic_terms, english_terms),
                "total_corrections": total_corrections,
                "total_protected_terms": total_protected,
                "total_categories": total_categories,
                "database_size_bytes": db_size,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
            }
        finally:
            conn.close()

    def remove_dictionary(self, dict_id: int, remove_entries: bool = True) -> bool:
        """إزالة قاموس"""
        conn = self._get_connection()
        try:
            if remove_entries:
                conn.execute("DELETE FROM medical_terms WHERE dict_id = ?", (dict_id,))
                conn.execute("DELETE FROM ocr_corrections WHERE dict_id = ?", (dict_id,))
                conn.execute("DELETE FROM protected_terms WHERE dict_id = ?", (dict_id,))

            conn.execute("DELETE FROM dictionaries WHERE id = ?", (dict_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"فشل إزالة القاموس {dict_id}: {e}")
            return False
        finally:
            conn.close()

    # ============ عمليات التصدير ============

    def export_to_json(self, output_path: str, dict_id: Optional[int] = None,
                       include_metadata: bool = True) -> bool:
        """تصدير القاموس إلى JSON"""
        conn = self._get_connection()
        try:
            if dict_id:
                terms = conn.execute("""
                    SELECT term_ar, term_en, definition, category, frequency
                    FROM medical_terms WHERE dict_id = ?
                    ORDER BY frequency DESC
                """, (dict_id,)).fetchall()
            else:
                terms = conn.execute("""
                    SELECT term_ar, term_en, definition, category, frequency
                    FROM medical_terms ORDER BY frequency DESC
                """).fetchall()

            data = {}
            if include_metadata:
                data["_metadata"] = {
                    "export_date": datetime.now().isoformat(),
                    "total_entries": len(terms),
                    "source": "OmniMedical Suite Dictionary Manager",
                }

            data["entries"] = [
                {k: row[k] for k in row.keys()} for row in terms
            ]

            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            return True
        except Exception as e:
            logger.error(f"فشل التصدير: {e}")
            return False
        finally:
            conn.close()

    def export_to_csv(self, output_path: str, dict_id: Optional[int] = None) -> bool:
        """تصدير القاموس إلى CSV"""
        conn = self._get_connection()
        try:
            if dict_id:
                terms = conn.execute("""
                    SELECT term_ar, term_en, definition, category, frequency
                    FROM medical_terms WHERE dict_id = ?
                    ORDER BY frequency DESC
                """, (dict_id,)).fetchall()
            else:
                terms = conn.execute("""
                    SELECT term_ar, term_en, definition, category, frequency
                    FROM medical_terms ORDER BY frequency DESC
                """).fetchall()

            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['term_ar', 'term_en', 'definition', 'category', 'frequency'])
                writer.writeheader()
                for row in terms:
                    writer.writerow({k: row[k] for k in row.keys()})

            return True
        except Exception as e:
            logger.error(f"فشل التصدير: {e}")
            return False
        finally:
            conn.close()

    def export_to_omni_format(self, output_path: str) -> bool:
        """
        تصدير القاموس بتنسيق OmniMedical المتوافق مع medical_dictionary.json
        """
        conn = self._get_connection()
        try:
            # تجميع التصنيفات
            categories_data = {}
            corrections_ar = {}
            corrections_en = {}

            terms = conn.execute("""
                SELECT term_ar, term_en, definition, category, frequency
                FROM medical_terms ORDER BY category, frequency DESC
            """).fetchall()

            for row in terms:
                term_ar = row['term_ar']
                term_en = row['term_en']
                definition = row['definition']
                category = row['category'] or 'general_medical'

                if category == 'ocr_correction' and definition:
                    if term_ar:
                        corrections_ar[term_ar] = definition.replace("التصحيح:", "").strip()
                    elif term_en:
                        corrections_en[term_en] = definition.replace("Correction:", "").strip()
                    continue

                if category not in categories_data:
                    categories_data[category] = []

                entry = {}
                if term_en:
                    entry['term'] = term_en
                if term_ar:
                    entry['ar'] = term_ar
                if definition:
                    entry['definition'] = definition
                categories_data[category].append(entry)

            data = {
                "version": "2.0",
                "source": "OmniMedical Dictionary Manager",
                "export_date": datetime.now().isoformat(),
                "arabic_corrections": corrections_ar,
                "english_corrections": corrections_en,
            }

            # إضافة كل تصنيف كقسم
            for cat, entries in categories_data.items():
                data[cat] = entries

            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            return True
        except Exception as e:
            logger.error(f"فشل التصدير بتنسيق OmniMedical: {e}")
            return False
        finally:
            conn.close()

    # ============ تكامل مع النظام ============

    def get_correction_dict_for_pipeline(self) -> Dict[str, str]:
        """
        الحصول على قاموس التصحيحات بصيغة مناسبة لخط أنابيب OCR/NLP.
        يُستخدم مباشرة مع SpellCorrector و MedicalOCR.
        """
        return self.get_ocr_corrections()

    def get_protected_terms_for_pipeline(self) -> List[str]:
        """
        الحصول على المصطلحات المحمية بصيغة مناسبة لخط أنابيب NLP.
        يُستخدم مباشرة مع ProtectedWordsManager.
        """
        return self.get_protected_terms()

    def get_medical_terms_set(self, language: str = "en") -> set:
        """
        الحصول على مجموعة مصطلحات طبية للبحث السريع.
        يُستخدم في FeatureExtractor و MedicalContextProtector.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if language == "ar":
                cursor.execute("SELECT term_ar FROM medical_terms WHERE term_ar IS NOT NULL")
            else:
                cursor.execute("SELECT term_en FROM medical_terms WHERE term_en IS NOT NULL")

            col = 'term_ar' if language == 'ar' else 'term_en'
            return {row[col] for row in cursor.fetchall()}
        finally:
            conn.close()

    def record_term_usage(self, term: str, language: str = "auto") -> None:
        """تسجيل استخدام مصطلح (لتحديث التكرار)"""
        conn = self._get_connection()
        try:
            if language == "auto":
                language = "ar" if self.ARABIC_PATTERN.search(term) else "en"

            if language == "ar":
                conn.execute("""
                    UPDATE medical_terms 
                    SET frequency = frequency + 1, last_seen = CURRENT_TIMESTAMP
                    WHERE term_ar = ?
                """, (term,))
            else:
                conn.execute("""
                    UPDATE medical_terms 
                    SET frequency = frequency + 1, last_seen = CURRENT_TIMESTAMP
                    WHERE term_en = ?
                """, (term,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
