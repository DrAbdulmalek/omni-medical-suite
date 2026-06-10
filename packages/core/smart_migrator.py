"""
packages/core/smart_migrator.py
=================================
مُهاجر البيانات الذكي — نُقل من packages/omni-core/smart_migrator.py

يُهاجر البيانات من:
  - OmniFile_Processor (modules/ → packages/)
  - medical-doc-processor (SQLite v3.2 → Prisma schema v2)
  - JSON correction files القديمة → Pattern table

الاستخدام:
    migrator = SmartMigrator(target_db=DatabaseManager.get_instance())
    result = migrator.run_all(source_dir="/old/data")
"""

from __future__ import annotations

import json
import os
import logging
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    source: str
    records_found: int = 0
    records_migrated: int = 0
    records_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if not self.records_found:
            return 1.0
        return self.records_migrated / self.records_found

    def __str__(self) -> str:
        return (
            f"Migration({self.source}): "
            f"{self.records_migrated}/{self.records_found} migrated, "
            f"{len(self.errors)} errors"
        )


class SmartMigrator:
    """مُهاجر البيانات من المشاريع القديمة إلى omni-medical-suite."""

    def __init__(self, target_db=None, dry_run: bool = False):
        self._db = target_db
        self._dry_run = dry_run
        if dry_run:
            logger.info("SmartMigrator running in DRY RUN mode — no data will be written")

    # ── Public API ────────────────────────────────────────────

    def run_all(self, source_dir: str) -> list[MigrationResult]:
        """شغّل كل المهاجرات المتاحة من مجلد المصدر."""
        source = Path(source_dir)
        results = []

        # 1. JSON dictionaries
        for json_file in [
            "correction_dict.json",
            "correction_dict_seed.json",
            "arabic_fixes.json",
        ]:
            path = source / json_file
            if path.exists():
                results.append(self.migrate_correction_json(path))

        # 2. Medical dictionary
        med_dict = source / "medical_dictionary.json"
        if med_dict.exists():
            results.append(self.migrate_medical_dictionary(med_dict))

        # 3. Protected terms
        protected = source / "audit_logs" / "protected_terms.json"
        if protected.exists():
            results.append(self.migrate_protected_terms(protected))

        # 4. Old SQLite database
        for db_file in source.glob("**/*.db"):
            results.append(self.migrate_sqlite_database(db_file))

        # 5. Training records (JSON)
        training_dir = source / "training"
        if training_dir.exists():
            results.append(self.migrate_training_data(training_dir))

        logger.info(f"Migration complete: {len(results)} sources processed")
        for r in results:
            logger.info(str(r))

        return results

    def migrate_correction_json(self, path: Path) -> MigrationResult:
        """هجرة ملفات التصحيح JSON → Pattern table."""
        result = MigrationResult(source=str(path))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                items = list(data.items())
            elif isinstance(data, list):
                items = [(item.get("original", ""), item.get("correction", "")) for item in data]
            else:
                result.errors.append(f"Unknown format in {path}")
                return result

            result.records_found = len(items)
            for original, correction in items:
                if not original or not correction:
                    result.records_skipped += 1
                    continue
                if not self._dry_run:
                    self._upsert_pattern(original, correction, source=path.stem)
                result.records_migrated += 1

        except Exception as exc:
            result.errors.append(str(exc))
            logger.error(f"Error migrating {path}: {exc}")

        return result

    def migrate_medical_dictionary(self, path: Path) -> MigrationResult:
        """هجرة القاموس الطبي → protected_terms + correction patterns."""
        result = MigrationResult(source=str(path))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            terms = data if isinstance(data, list) else data.get("terms", [])
            result.records_found = len(terms)

            for term in terms:
                if isinstance(term, str):
                    if not self._dry_run:
                        self._upsert_protected_term(term, category="medical")
                elif isinstance(term, dict):
                    word = term.get("term") or term.get("word", "")
                    category = term.get("category", "medical")
                    if word and not self._dry_run:
                        self._upsert_protected_term(word, category=category)
                result.records_migrated += 1

        except Exception as exc:
            result.errors.append(str(exc))

        return result

    def migrate_protected_terms(self, path: Path) -> MigrationResult:
        """هجرة المصطلحات المحمية → ProtectedVocabulary."""
        result = MigrationResult(source=str(path))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            terms = data if isinstance(data, list) else data.get("protected_terms", [])
            result.records_found = len(terms)
            for term in terms:
                if not self._dry_run:
                    self._upsert_protected_term(str(term), category="protected")
                result.records_migrated += 1
        except Exception as exc:
            result.errors.append(str(exc))
        return result

    def migrate_sqlite_database(self, db_path: Path) -> MigrationResult:
        """هجرة بيانات SQLite القديمة (medical-doc-processor schema) → الـ schema الجديد."""
        result = MigrationResult(source=str(db_path))
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # جداول متوقعة من medical-doc-processor v3.2
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

            if "ProcessedImage" in tables:
                rows = conn.execute("SELECT * FROM ProcessedImage").fetchall()
                result.records_found += len(rows)
                for row in rows:
                    if not self._dry_run:
                        self._migrate_processed_image(dict(row))
                    result.records_migrated += 1

            if "TrainingWord" in tables:
                rows = conn.execute("SELECT * FROM TrainingWord").fetchall()
                result.records_found += len(rows)
                for row in rows:
                    if not self._dry_run:
                        self._migrate_training_word(dict(row))
                    result.records_migrated += 1

            if "Pattern" in tables:
                rows = conn.execute("SELECT * FROM Pattern").fetchall()
                result.records_found += len(rows)
                for row in rows:
                    if not self._dry_run:
                        self._upsert_pattern(
                            row["original_text"],
                            row["corrected_text"],
                            source="legacy_sqlite",
                        )
                    result.records_migrated += 1

            conn.close()
        except Exception as exc:
            result.errors.append(str(exc))
            logger.error(f"Error migrating SQLite {db_path}: {exc}")

        return result

    def migrate_training_data(self, training_dir: Path) -> MigrationResult:
        """هجرة بيانات التدريب JSON → TrainingRecord table."""
        result = MigrationResult(source=str(training_dir))
        for json_file in training_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                records = data if isinstance(data, list) else [data]
                result.records_found += len(records)
                for record in records:
                    if not self._dry_run:
                        self._upsert_training_record(record)
                    result.records_migrated += 1
            except Exception as exc:
                result.errors.append(f"{json_file.name}: {exc}")
        return result

    # ── Internal DB ops (stubs — يتصل بـ DatabaseManager فعلياً) ───

    def _upsert_pattern(self, original: str, correction: str, source: str = "") -> None:
        if not self._db:
            return
        fingerprint = hashlib.md5(original.encode()).hexdigest()
        with self._db.session() as s:
            from sqlalchemy import text
            s.execute(text("""
                INSERT INTO "Pattern" (original_text, corrected_text, source, use_count, created_at)
                VALUES (:orig, :corr, :src, 0, CURRENT_TIMESTAMP)
                ON CONFLICT (original_text) DO UPDATE SET
                  corrected_text = EXCLUDED.corrected_text,
                  source = EXCLUDED.source
            """), {"orig": original, "corr": correction, "src": source})

    def _upsert_protected_term(self, term: str, category: str = "medical") -> None:
        if not self._db:
            return
        # يُكمل الربط مع ProtectedVocabulary

    def _migrate_processed_image(self, row: dict) -> None:
        if not self._db:
            return
        # يُكمل الربط مع ProcessedImage model

    def _migrate_training_word(self, row: dict) -> None:
        if not self._db:
            return
        # يُكمل الربط مع TrainingWord model

    def _upsert_training_record(self, record: dict) -> None:
        if not self._db:
            return
        # يُكمل الربط مع TrainingRecord model
