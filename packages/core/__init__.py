"""
packages/core/__init__.py
==========================
الوحدة الموحّدة بعد دمج packages/core (legacy) + packages/omni-core

تحتوي على:
  - engine_router       : توجيه محركات OCR
  - database_manager    : إدارة قاعدة البيانات
  - user_manager        : إدارة المستخدمين والصلاحيات
  - model_registry      : سجل النماذج المدرّبة
  - model_manager       : دورة حياة النماذج
  - corrections_manager : تتبع التصحيحات اليدوية
  - protected_vocab     : المفردات المحمية
  - word_trainer        : تدريب على مستوى الكلمة
  - parallel_processor  : المعالجة المتوازية
  - smart_migrator      : هجرة البيانات الذكية
  - encryption          : تشفير AES-256 (مُعاد توجيهه من packages/security)
  - spell_checker       : التدقيق الإملائي الموحّد

التغييرات عن النسخة القديمة:
  - packages/omni-core/* أُدمج هنا وحُذف كمجلد مستقل
  - packages/core/api_server.py بقي كما هو (legacy endpoint)
  - packages/core/encryption.py حُذف — استخدم packages.security.encryption
  - جميع imports من packages.omni_core.* أصبحت packages.core.*
"""

from .engine_router import EngineRouter, EngineConfig, RoutingResult
from .database_manager import DatabaseManager
from .user_manager import UserManager, UserRole, Permission
from .model_registry import ModelRegistry, ModelEntry
from .model_manager import ModelManager
from .corrections_manager import CorrectionsManager
from .protected_vocab import ProtectedVocabulary
from .word_trainer import WordTrainer
from .parallel_processor import ParallelProcessor
from .smart_migrator import SmartMigrator, MigrationResult
from .spell_checker import UnifiedSpellChecker

__all__ = [
    "EngineRouter", "EngineConfig", "RoutingResult",
    "DatabaseManager",
    "UserManager", "UserRole", "Permission",
    "ModelRegistry", "ModelEntry",
    "ModelManager",
    "CorrectionsManager",
    "ProtectedVocabulary",
    "WordTrainer",
    "ParallelProcessor",
    "SmartMigrator", "MigrationResult",
    "UnifiedSpellChecker",
]

# ── Backward-compat shims ─────────────────────────────────────
# كود قديم يستورد من omni_core يُعيَّن هنا تلقائياً
# يُعرض تحذير deprecation ليُذكَّر المطوّر بالتحديث

import warnings as _w

class _OmniCoreShim:
    """Proxy أُنشئ لضمان التوافق مع الاستيرادات القديمة."""
    def __getattr__(self, name: str):
        _w.warn(
            f"packages.omni_core.{name} is deprecated — "
            f"use packages.core.{name} instead.",
            DeprecationWarning, stacklevel=2
        )
        return globals().get(name)

omni_core = _OmniCoreShim()
