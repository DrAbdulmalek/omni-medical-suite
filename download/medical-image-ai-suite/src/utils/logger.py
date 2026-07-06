"""
نظام التسجيل الموحد - Unified Logging System
يوفر نظام تسجيل مركزي مع دعم الألوان والملفات والدوال المخصصة
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """منسق رسائل التسجيل مع ألوان للطرفية"""

    COLORS = {
        "DEBUG": "\033[36m",     # أزرق فاتح
        "INFO": "\033[32m",      # أخضر
        "WARNING": "\033[33m",   # أصفر
        "ERROR": "\033[31m",     # أحمر
        "CRITICAL": "\033[1;31m", # أحمر عريض
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str = "medical-ai",
    level: str = "INFO",
    log_dir: Optional[str] = None,
    console: bool = True,
    file_logging: bool = True,
) -> logging.Logger:
    """
    إعداد مسجّل موحد مع دعم الطرفية والملفات

    Args:
        name: اسم المسجّل
        level: مستوى التسجيل (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: مجلد حفظ ملفات السجل (لا شيء = logs/)
        console: تفعيل الإخراج للطرفية
        file_logging: تفعيل حفظ في الملف

    Returns:
        logging.Logger: كائن المسجّل المُعدّ
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    # تنسيق الرسائل
    fmt_console = ColoredFormatter(
        fmt="%(asctime)s │ %(name)-18s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    fmt_file = logging.Formatter(
        fmt="%(asctime)s │ %(name)-18s │ %(levelname)-8s │ %(filename)s:%(lineno)d │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # معالج الطرفية
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt_console)
        logger.addHandler(ch)

    # معالج الملف
    if file_logging:
        log_directory = Path(log_dir) if log_dir else Path("logs")
        log_directory.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_directory / f"{name}_{timestamp}.log"

        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt_file)
        logger.addHandler(fh)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    الحصول على مسجّل فرعي من المسجّل الرئيسي

    Args:
        name: اسم الوحدة الفرعية

    Returns:
        logging.Logger: مسجّل فرعي مُعدّ
    """
    return logging.getLogger(f"medical-ai.{name}")
