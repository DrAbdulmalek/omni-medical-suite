"""
محرك البحث الشامل (Global Semantic Search Engine)
=====================================================
محرك بحث متقدم في أرشيف الملفات المعالجة.

الميزات:
- بحث نصي كامل مع سياق (context snippet)
- بحث بالتصنيف واللغة
- بحث بالتاريخ
- تصفية حسب نسبة الثقة
- بحث متقدم (AND, OR, NOT)
- تصدير النتائج

الاستخدام:
    from packages.core.search_engine import SearchEngine
    engine = SearchEngine(db_path="omni_processor.db")
    results = engine.search("كسر عنق الفخذ", limit=20)
    for r in results:
        print(f"{r['file_name']}: {r['snippet']}")
"""

import logging
import os
import re
from typing import Any

from packages.core.base_db import BaseDB

logger = logging.getLogger(__name__)

_SAFE_COLUMNS = frozenset([
    "file_name", "file_path", "category", "subcategory", "tags",
    "confidence_score", "ocr_engine", "language", "page_count",
    "process_date", "processing_time", "extracted_text",
])

# SQL keywords / aliases allowed inside dynamically built WHERE clauses
_SAFE_WHERE_TOKENS = frozenset({
    *_SAFE_COLUMNS,
    "p", "f",
    "AND", "OR", "NOT", "IN", "LIKE", "MATCH", "BETWEEN",
    "IS", "NULL", "ASC", "DESC",
})
_SAFE_WHERE_TOKENS_UPPER = {t.upper() for t in _SAFE_WHERE_TOKENS}


class SearchEngine(BaseDB):
    """
    محرك بحث شامل في الأرشيف الرقمي.

    يدعم البحث في:
    - النصوص المستخرجة (extracted_text)
    - أسماء الملفات (file_name)
    - التصنيفات (category, tags)
    - الملاحظات والتعليقات
    """

    @staticmethod
    def _validate_column(col: str) -> str:
        """Validate column name to prevent SQL injection."""
        if col not in _SAFE_COLUMNS:
            raise ValueError(f"Invalid column: {col}")
        return col

    @staticmethod
    def _validate_where_clause(clause: str) -> None:
        """Validate that all identifiers in *clause* are in the safe set.

        Called on WHERE clauses assembled internally from hardcoded
        condition strings — every word-boundary token must be an
        expected column name, table alias, or SQL keyword.
        """
        if not clause:
            return
        tokens = re.findall(r'\b[a-zA-Z_]\w*\b', clause)
        for tok in tokens:
            if tok.upper() not in _SAFE_WHERE_TOKENS_UPPER:
                raise ValueError(f"Unsafe identifier in WHERE clause: {tok!r}")

    def __init__(self, db_path: str = "omni_processor.db"):
        """
        تهيئة محرك البحث.

        Args:
            db_path: مسار قاعدة بيانات OmniDatabase
        """
        super().__init__(db_path)
        logger.info("تم الاتصال بقاعدة البيانات: %s", db_path)

    @property
    def is_connected(self) -> bool:
        """هل قاعدة البيانات متصلة؟ (دائماً True مع BaseDB)"""
        return True

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        language: str | None = None,
        min_confidence: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search_mode: str = "standard",
    ) -> dict[str, Any]:
        """
        البحث الشامل في الأرشيف.

        Args:
            query: كلمة أو جملة البحث
            limit: الحد الأقصى للنتائج
            offset: عدد النتائج المتخطاة (للتصفح)
            category: تصفية حسب التصنيف
            language: تصفية حسب اللغة
            min_confidence: الحد الأدنى لنسبة الثقة
            date_from: تاريخ البداية (YYYY-MM-DD)
            date_to: تاريخ النهاية (YYYY-MM-DD)
            search_mode: نمط البحث ('standard', 'fts5', 'like', 'advanced')

        Returns:
            قاموس يحتوي على results, total_count, query, filters
        """
        if not query or not query.strip():
            return {"results": [], "total_count": 0, "query": query}

        try:
            if search_mode == "fts5":
                return self._search_fts5(
                    query, limit, offset, category, language,
                    min_confidence, date_from, date_to
                )
            elif search_mode == "advanced":
                return self._search_advanced(
                    query, limit, offset, category, language,
                    min_confidence, date_from, date_to
                )
            else:
                return self._search_standard(
                    query, limit, offset, category, language,
                    min_confidence, date_from, date_to
                )
        except Exception as e:
            logger.error("خطأ في البحث: %s", e)
            return {"results": [], "total_count": 0, "query": query, "error": str(e)}

    def _search_standard(
        self, query: str, limit: int, offset: int,
        category: str | None, language: str | None,
        min_confidence: float | None, date_from: str | None,
        date_to: str | None,
    ) -> dict[str, Any]:
        """بحث قياسي باستخدام LIKE مع سياق."""
        conditions = []
        params = []

        # شرط البحث النصي
        conditions.append(
            "(extracted_text LIKE ? OR file_name LIKE ? OR category LIKE ? OR tags LIKE ?)"
        )
        search_term = f"%{query}%"
        params.extend([search_term, search_term, search_term, search_term])

        # الفلاتر
        if category:
            conditions.append("category = ?")
            params.append(category)

        if language:
            conditions.append("language = ?")
            params.append(language)

        if min_confidence is not None:
            conditions.append("confidence_score >= ?")
            params.append(min_confidence)

        if date_from:
            conditions.append("process_date >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("process_date <= ?")
            params.append(date_to)

        where_clause = " AND ".join(conditions)
        self._validate_where_clause(where_clause)

        # عدد النتائج الإجمالي
        with self.connection() as conn:
            count_sql = f"SELECT COUNT(*) as cnt FROM processed_files WHERE {where_clause}"
            cursor = conn.execute(count_sql, params)
            total = cursor.fetchone()["cnt"]

            # استعلام النتائج
            sql = f"""
                SELECT
                    id, file_name, file_path, category, subcategory, tags,
                    confidence_score, ocr_engine, language, page_count,
                    process_date, processing_time,
                    SUBSTR(extracted_text, 1, 500) as preview
                FROM processed_files
                WHERE {where_clause}
                ORDER BY confidence_score DESC, process_date DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor = conn.execute(sql, params)

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # استخراج سياق البحث
                snippet = self._extract_context(
                    result.get("preview", ""), query, context_length=100
                )
                result["snippet"] = snippet
                result.pop("preview", None)
                results.append(result)

        return {
            "results": results,
            "total_count": total,
            "query": query,
            "limit": limit,
            "offset": offset,
            "filters": {
                "category": category,
                "language": language,
                "min_confidence": min_confidence,
                "date_from": date_from,
                "date_to": date_to,
            },
        }

    def _search_fts5(
        self, query: str, limit: int, offset: int,
        category: str | None, language: str | None,
        min_confidence: float | None, date_from: str | None,
        date_to: str | None,
    ) -> dict[str, Any]:
        """بحث باستخدام محرك FTS5 (أسرع)."""
        try:
            fts_query = self._to_fts5_query(query)

            conditions = ["files_fts MATCH ?"]
            params = [fts_query]

            if category:
                conditions.append("p.category = ?")
                params.append(category)
            if language:
                conditions.append("p.language = ?")
                params.append(language)
            if min_confidence is not None:
                conditions.append("p.confidence_score >= ?")
                params.append(min_confidence)

            where_clause = " AND ".join(conditions)
            self._validate_where_clause(where_clause)

            with self.connection() as conn:
                # عدد النتائج
                count_sql = f"""
                    SELECT COUNT(*) as cnt
                    FROM processed_files p JOIN files_fts f ON p.id = f.file_id
                    WHERE {where_clause}
                """
                cursor = conn.execute(count_sql, params)
                total = cursor.fetchone()["cnt"]

                # النتائج مع سياق
                sql = f"""
                    SELECT
                        p.id, p.file_name, p.file_path, p.category, p.subcategory,
                        p.confidence_score, p.ocr_engine, p.language, p.process_date,
                        snippet(files_fts, 0, '>>>', '<<<', '...', 64) as snippet
                    FROM processed_files p
                    JOIN files_fts f ON p.id = f.file_id
                    WHERE {where_clause}
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                cursor = conn.execute(sql, params)
                results = [dict(row) for row in cursor.fetchall()]

            return {
                "results": results,
                "total_count": total,
                "query": query,
                "search_mode": "fts5",
            }
        except Exception as e:
            logger.warning("FTS5 غير متاح، السقوط إلى البحث القياسي: %s", e)
            return self._search_standard(
                query, limit, offset, category, language,
                min_confidence, date_from, date_to
            )

    def _search_advanced(
        self, query: str, limit: int, offset: int,
        category: str | None, language: str | None,
        min_confidence: float | None, date_from: str | None,
        date_to: str | None,
    ) -> dict[str, Any]:
        """بحث متقدم يدعم عوامل AND, OR, NOT."""
        # تحليل الاستعلام المتقدم
        terms = self._parse_advanced_query(query)

        conditions = []
        params = []

        for operator, term in terms:
            if operator == "AND" or operator == "OR":
                conditions.append("(extracted_text LIKE ? OR file_name LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])
            elif operator == "NOT":
                conditions.append("(extracted_text NOT LIKE ? AND file_name NOT LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])

        if not conditions:
            return {"results": [], "total_count": 0, "query": query}

        # دمج شروط OR والأخرى
        and_conditions = []
        or_conditions = []
        not_conditions = []

        for i, (op, _) in enumerate(terms):
            if op == "NOT":
                not_conditions.append(conditions[i])
            elif op == "OR":
                or_conditions.append(conditions[i])
            else:
                and_conditions.append(conditions[i])

        where_parts = []
        all_params = []

        if and_conditions:
            and_sql = " AND ".join(and_conditions)
            where_parts.append(f"({and_sql})")

        if or_conditions:
            or_sql = " OR ".join(or_conditions)
            where_parts.append(f"({or_sql})")

        if not_conditions:
            not_sql = " AND ".join(not_conditions)
            where_parts.append(f"({not_sql})")

        if not where_parts:
            return {"results": [], "total_count": 0, "query": query}

        where_clause = " AND ".join(where_parts)

        # تجميع المعاملات بالترتيب الصحيح
        for i, (_, term) in enumerate(terms):
            if terms[i][0] != "NOT":
                params_all = [f"%{term}%", f"%{term}%"]
                all_params.extend(params_all)
        for i, (_, term) in enumerate(terms):
            if terms[i][0] == "NOT":
                params_all = [f"%{term}%", f"%{term}%"]
                all_params.extend(params_all)

        # فلاتر إضافية
        if category:
            where_clause += " AND category = ?"
            all_params.append(category)

        if language:
            where_clause += " AND language = ?"
            all_params.append(language)

        self._validate_where_clause(where_clause)

        # تنفيذ الاستعلام
        sql = f"""
            SELECT
                id, file_name, file_path, category, confidence_score,
                ocr_engine, language, process_date,
                SUBSTR(extracted_text, 1, 500) as preview
            FROM processed_files
            WHERE {where_clause}
            ORDER BY confidence_score DESC
            LIMIT ? OFFSET ?
        """
        all_params.extend([limit, offset])

        try:
            with self.connection() as conn:
                cursor = conn.execute(sql, all_params)
                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    snippet = self._extract_context(
                        result.get("preview", ""), query, context_length=100
                    )
                    result["snippet"] = snippet
                    result.pop("preview", None)
                    results.append(result)

            return {
                "results": results,
                "total_count": len(results),
                "query": query,
                "search_mode": "advanced",
            }
        except Exception as e:
            logger.error("خطأ في البحث المتقدم: %s", e)
            return {"results": [], "total_count": 0, "query": query, "error": str(e)}

    @staticmethod
    def _to_fts5_query(query: str) -> str:
        """تحويل استعلام نصي إلى صيغة FTS5."""
        # إزالة الأحرف الخاصة
        clean = re.sub(r'[(){}[\]\\^*:"+-]', ' ', query)
        # تقسيم إلى كلمات
        words = clean.split()
        if not words:
            return query
        # ربط الكلمات بـ AND
        return " AND ".join(f'"{w}"' for w in words if w)

    @staticmethod
    def _parse_advanced_query(query: str) -> list[tuple[str, str]]:
        """
        تحليل استعلام متقدم مع عوامل AND, OR, NOT.

        أمثلة:
        - "كسر AND فخذ" → [("AND", "كسر"), ("AND", "فخذ")]
        - "قلب OR عظام" → [("OR", "قلب"), ("OR", "عظام")]
        - "جراحة NOT قلب" → [("AND", "جراحة"), ("NOT", "قلب")]
        """
        re.findall(r'\b(AND|OR|NOT)\b', query.upper())
        parts = re.split(r'\b(AND|OR|NOT)\b', query, flags=re.IGNORECASE)

        result = []
        current_op = "AND"  # الافتراضي

        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.upper() in ("AND", "OR", "NOT"):
                current_op = part.upper()
            else:
                result.append((current_op, part))

        return result

    @staticmethod
    def _extract_context(text: str, query: str, context_length: int = 100) -> str:
        """
        استخراج سياق البحث من النص.

        Args:
            text: النص الكامل
            query: كلمة البحث
            context_length: عدد الأحرف قبل وبعد الكلمة

        Returns:
            مقتطف من النص مع السياق
        """
        if not text or not query:
            return text[:200] if text else ""

        text_lower = text.lower()
        query_lower = query.lower()

        # البحث عن أول ظهور
        idx = text_lower.find(query_lower)
        if idx == -1:
            # البحث عن أي كلمة من الاستعلام
            words = query_lower.split()
            for word in words:
                idx = text_lower.find(word)
                if idx != -1:
                    break

        if idx == -1:
            return text[:200]

        start = max(0, idx - context_length)
        end = min(len(text), idx + len(query) + context_length)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def search_files(
        self,
        directory: str,
        query: str,
        extensions: list[str] | None = None,
        recursive: bool = True,
    ) -> list[dict[str, Any]]:
        """
        بحث مباشر في ملفات .txt في مجلد (بدون قاعدة بيانات).

        مفيد للبحث السريع في مجلدات التصدير.

        Args:
            directory: مسار المجلد
            query: كلمة البحث
            extensions: قائمة الامتدادات
            recursive: البحث في المجلدات الفرعية

        Returns:
            قائمة نتائج البحث
        """
        if extensions is None:
            extensions = ['.txt']

        results = []
        query_lower = query.lower()

        for root, _, files in os.walk(directory):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in extensions:
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = f.read()

                    if query_lower in content.lower():
                        idx = content.lower().find(query_lower)
                        start = max(0, idx - 60)
                        end = min(len(content), idx + len(query) + 80)
                        snippet = f"...{content[start:end]}..."

                        results.append({
                            "file_name": filename,
                            "file_path": filepath,
                            "snippet": snippet,
                            "size": os.path.getsize(filepath),
                        })
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue

            if not recursive:
                break

        logger.info(
            "بحث ملفات: '%s' في %s → %d نتيجة",
            query, directory, len(results)
        )
        return results

    def get_categories(self) -> list[str]:
        """الحصول على قائمة التصنيفات المتاحة في الأرشيف."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT category FROM processed_files ORDER BY category"
            )
            return [row["category"] for row in cursor.fetchall()]

    def get_languages(self) -> list[str]:
        """الحصول على قائمة اللغات المتاحة في الأرشيف."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT language FROM processed_files ORDER BY language"
            )
            return [row["language"] for row in cursor.fetchall()]

    def export_results(
        self,
        results: list[dict[str, Any]],
        output_path: str,
        format_type: str = "json",
    ) -> bool:
        """
        تصدير نتائج البحث إلى ملف.

        Args:
            results: نتائج البحث
            output_path: مسار الملف
            format_type: التنسيق ('json', 'csv', 'txt')

        Returns:
            True إذا تم التصدير بنجاح
        """
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            if format_type == "json":
                import json
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2, default=str)

            elif format_type == "csv":
                import csv
                if not results:
                    return False
                with open(output_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)

            elif format_type == "txt":
                with open(output_path, "w", encoding="utf-8") as f:
                    for r in results:
                        f.write(f"--- {r.get('file_name', 'Unknown')} ---\n")
                        f.write(f"  التصنيف: {r.get('category', 'N/A')}\n")
                        f.write(f"  الثقة: {r.get('confidence_score', 'N/A')}\n")
                        f.write(f"  السياق: {r.get('snippet', 'N/A')}\n\n")

            logger.info("تم تصدير %d نتيجة إلى %s", len(results), output_path)
            return True
        except Exception as e:
            logger.error("خطأ في تصدير النتائج: %s", e)
            return False

    def close(self):
        """إغلاق الاتصال بقاعدة البيانات (no-op: BaseDB manages connections)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        connected = self.db_path.exists()
        status = "متصل" if connected else "غير متصل"
        return f"SearchEngine(db='{self.db_path}', status={status})"
