#!/usr/bin/env python3
"""
advanced_logger.py — نظام التسجيل المتقدم لـ Omni Medical Suite
════════════════════════════════════════════════════════════════════

نظام تسجيل مركزي يتتبع:
- إجراءات المستخدم (رفع ملف، تشغيل OCR، تصدير)
- نتائج المعالجة (OCR, NER, spell check)
- أخطاء النظام وأداءه
- جلسات العمل

الاستخدام:
    from scripts.advanced_logger import get_feedback_collector

    fb = get_feedback_collector()
    fb.log_action("ocr_process", {"file": "report.pdf", "pages": 15})
    fb.log_ocr_result("report.pdf", 15, 42, {"psm": 6, "dpi": 300})
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("advanced_logger")

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
DEFAULT_LOGS_DIR = Path(os.getenv("OMNI_LOGS_DIR", "logs"))
DEFAULT_SESSION_ID = os.getenv("OMNI_SESSION_ID", str(uuid.uuid4())[:8])


# ===========================================================================
# FeedbackCollector
# ===========================================================================
class FeedbackCollector:
    """
    جامع بيانات التغذية الراجعة والتسجيل المتقدم.

    يسجّل الأحداث في ملفات JSONL منظمة حسب التاريخ،
    ويتتبع جلسات العمل وإحصائيات الأداء.
    """

    def __init__(
        self,
        logs_dir: str | Path | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        تهيئة جامع التغذية الراجعة.

        Args:
            logs_dir: مجلد السجلات (افتراضي: logs/)
            session_id: معرّف الجلسة (افتراضي: UUID عشوائي)
        """
        self.logs_dir = Path(logs_dir or DEFAULT_LOGS_DIR)
        self.session_id = session_id or DEFAULT_SESSION_ID
        self.start_time = datetime.now()

        # Create directories
        (self.logs_dir / "user_actions").mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "ocr_results").mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "errors").mkdir(parents=True, exist_ok=True)

        # Session stats
        self._stats: dict[str, int] = {
            "actions_logged": 0,
            "ocr_processed": 0,
            "errors_logged": 0,
        }

        logger.info(
            "FeedbackCollector initialized — session=%s, logs_dir=%s",
            self.session_id,
            self.logs_dir,
        )

    # ------------------------------------------------------------------
    # Action logging
    # ------------------------------------------------------------------
    def log_action(
        self,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        تسجيل إجراء مستخدم.

        Args:
            action: اسم الإجراء (مثل: "file_upload", "ocr_process")
            details: تفاصيل إضافية
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "action": action,
            "details": details or {},
        }
        self._write_entry(entry, "user_actions")
        self._stats["actions_logged"] += 1

    # ------------------------------------------------------------------
    # OCR result logging
    # ------------------------------------------------------------------
    def log_ocr_result(
        self,
        file_name: str,
        pages: int,
        entries: int,
        config: dict[str, Any],
        source: str = "pdf_ocr_processor",
    ) -> None:
        """
        تسجيل نتيجة OCR.

        Args:
            file_name: اسم الملف المعالج
            pages: عدد الصفحات
            entries: عدد المُدخلات المستخرجة
            config: إعداد OCR المستخدم
            source: مصدر المعالجة
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "action": "ocr_processed",
            "details": {
                "file": file_name,
                "pages": pages,
                "entries_found": entries,
                "config": config,
                "source": source,
            },
        }
        self._write_entry(entry, "ocr_results")
        self._stats["ocr_processed"] += 1
        logger.info(
            "OCR logged: %s (%d pages, %d entries)", file_name, pages, entries
        )

    # ------------------------------------------------------------------
    # Error logging
    # ------------------------------------------------------------------
    def log_error(
        self,
        error_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        تسجيل خطأ.

        Args:
            error_type: نوع الخطأ (مثل: "import_error", "ocr_failure")
            message: رسالة الخطأ
            details: تفاصيل إضافية
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "action": "error",
            "error_type": error_type,
            "message": message,
            "details": details or {},
        }
        self._write_entry(entry, "errors")
        self._stats["errors_logged"] += 1

    # ------------------------------------------------------------------
    # Session summary
    # ------------------------------------------------------------------
    def get_session_summary(self) -> dict[str, Any]:
        """الحصول على ملخص الجلسة الحالية."""
        duration = (datetime.now() - self.start_time).total_seconds()
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": round(duration, 1),
            "stats": self._stats.copy(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _write_entry(
        self,
        entry: dict[str, Any],
        subdir: str,
    ) -> None:
        """كتابة مُدخلة سجل في ملف JSONL."""
        date_str = datetime.now().strftime("%Y%m%d")
        log_file = self.logs_dir / subdir / f"{subdir}_{date_str}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            logger.warning("Failed to write log entry: %s", exc)


# ===========================================================================
# Singleton instance
# ===========================================================================
_instance: Optional[FeedbackCollector] = None


def get_feedback_collector(
    logs_dir: str | Path | None = None,
    session_id: str | None = None,
) -> FeedbackCollector:
    """
    الحصول على مثيل FeedbackCollector المشترك (Singleton).

    Args:
        logs_dir: مجلد السجلات (يُستخدم فقط عند أول استدعاء)
        session_id: معرّف الجلسة (يُستخدم فقط عند أول استدعاء)

    Returns:
        مثيل FeedbackCollector
    """
    global _instance
    if _instance is None:
        _instance = FeedbackCollector(logs_dir=logs_dir, session_id=session_id)
    return _instance


def reset_feedback_collector() -> None:
    """إعادة تعيين المثيل المشترك (للاختبار فقط)."""
    global _instance
    _instance = None
