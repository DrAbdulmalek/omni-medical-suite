"""
SQLite Database Manager with WAL mode for medical documents.
"""

import sqlite3
import json
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite manager with WAL mode."""

    def __init__(self, db_path: str = "medical_docs.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._local = None

    def initialize(self, encryption_password: Optional[str] = None) -> None:
        """Initialize database with WAL mode and create tables."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA synchronous = NORMAL")

        self._create_tables()

        # Ensure default settings row exists
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO app_settings (id) VALUES ('main')"
            )
            self.conn.commit()
        except Exception:
            pass

    def _create_tables(self) -> None:
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                date_of_birth TEXT,
                mrn TEXT UNIQUE,
                phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                filename TEXT NOT NULL,
                original_path TEXT,
                processed_path TEXT,
                encrypted_path TEXT,
                document_type TEXT DEFAULT 'unknown',
                status TEXT DEFAULT 'pending',
                blur_before REAL,
                blur_after REAL,
                skew_angle REAL,
                quality_label TEXT,
                encryption_password_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                quality TEXT,
                duration_ms INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS training_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_name TEXT NOT NULL,
                features TEXT NOT NULL,
                initial_params TEXT,
                final_params TEXT,
                operations TEXT,
                quality TEXT,
                confidence REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                id TEXT PRIMARY KEY DEFAULT 'main',
                page_threshold INTEGER DEFAULT 200,
                gray_threshold INTEGER DEFAULT 230,
                auto_save INTEGER DEFAULT 1,
                auto_deskew INTEGER DEFAULT 1,
                auto_crop INTEGER DEFAULT 1,
                padding INTEGER DEFAULT 10,
                min_confidence REAL DEFAULT 0.85,
                mistral_api_key TEXT,
                mistral_enabled INTEGER DEFAULT 0,
                encryption_enabled INTEGER DEFAULT 0,
                theme TEXT DEFAULT 'light',
                language TEXT DEFAULT 'ar'
            );

            CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_id);
            CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
            CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
            CREATE INDEX IF NOT EXISTS idx_logs_document ON processing_logs(document_id);
            CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON processing_logs(timestamp);
        """)

        self.conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ---- Patient Operations ----

    def add_patient(self, patient_id: str, name: str, **kwargs) -> bool:
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO patients (id, name, date_of_birth, mrn, phone) VALUES (?, ?, ?, ?, ?)",
                (patient_id, name, kwargs.get('date_of_birth'), kwargs.get('mrn'), kwargs.get('phone'))
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add patient: {e}")
            return False

    def get_patients(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT * FROM patients ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ---- Document Operations ----

    def add_document(self, filename: str, patient_id: Optional[str] = None,
                      **kwargs) -> int:
        cursor = self.conn.execute(
            """INSERT INTO documents
               (patient_id, filename, original_path, processed_path, encrypted_path,
                document_type, status, blur_before, blur_after, skew_angle, quality_label)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, filename,
             kwargs.get('original_path'), kwargs.get('processed_path'), kwargs.get('encrypted_path'),
             kwargs.get('document_type', 'unknown'), kwargs.get('status', 'pending'),
             kwargs.get('blur_before'), kwargs.get('blur_after'),
             kwargs.get('skew_angle'), kwargs.get('quality_label'))
        )
        self.conn.commit()
        return cursor.lastrowid

    def _row_to_dict(self, row) -> Dict:
        return dict(row) if hasattr(row, 'keys') else row

    def get_documents(self, patient_id: Optional[str] = None, status: Optional[str] = None,
                       doc_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        query = "SELECT d.*, p.name as patient_name FROM documents d LEFT JOIN patients p ON d.patient_id = p.id WHERE 1=1"
        params = []

        if patient_id:
            query += " AND d.patient_id = ?"
            params.append(patient_id)
        if status:
            query += " AND d.status = ?"
            params.append(status)
        if doc_type:
            query += " AND d.document_type = ?"
            params.append(doc_type)

        query += " ORDER BY d.created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_document(self, doc_id: int, **kwargs) -> bool:
        allowed = ['patient_id', 'filename', 'processed_path', 'encrypted_path',
                    'document_type', 'status', 'blur_before', 'blur_after',
                    'skew_angle', 'quality_label']
        sets = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)

        if not sets:
            return False

        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(doc_id)

        try:
            self.conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", params)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return False

    def delete_document(self, doc_id: int) -> bool:
        try:
            self.conn.execute("DELETE FROM processing_logs WHERE document_id = ?", (doc_id,))
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    # ---- Processing Log Operations ----

    def add_log(self, document_id: Optional[int], action: str, details: str = "",
                quality: str = "", duration_ms: int = 0) -> int:
        cursor = self.conn.execute(
            "INSERT INTO processing_logs (document_id, action, details, quality, duration_ms) VALUES (?, ?, ?, ?, ?)",
            (document_id, action, details, quality, duration_ms)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_logs(self, document_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        if document_id:
            cursor = self.conn.execute(
                "SELECT * FROM processing_logs WHERE document_id = ? ORDER BY timestamp DESC LIMIT ?",
                (document_id, limit)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM processing_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    # ---- Statistics ----

    def get_stats(self) -> Dict[str, Any]:
        cursor = self.conn.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'processed'")
        processed_docs = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM documents WHERE encrypted_path IS NOT NULL")
        encrypted_docs = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM documents WHERE created_at >= date('now')")
        today_docs = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT document_type, COUNT(*) as count FROM documents GROUP BY document_type")
        by_type = [dict(row) for row in cursor.fetchall()]

        cursor = self.conn.execute("SELECT AVG(blur_after) as avg_blur, AVG(skew_angle) as avg_skew FROM documents WHERE status = 'processed'")
        avg_row = cursor.fetchone()

        return {
            "total_documents": total_docs,
            "processed_documents": processed_docs,
            "encrypted_documents": encrypted_docs,
            "today_documents": today_docs,
            "total_patients": total_patients,
            "by_type": by_type,
            "avg_blur": round(avg_row[0] or 0, 2) if avg_row else 0,
            "avg_skew": round(avg_row[1] or 0, 2) if avg_row else 0,
        }

    # ---- Settings Operations ----

    def get_settings(self) -> Dict[str, Any]:
        cursor = self.conn.execute("SELECT * FROM app_settings WHERE id = 'main'")
        row = cursor.fetchone()
        return dict(row) if row else {"id": "main"}

    def update_settings(self, **kwargs) -> bool:
        allowed = ['page_threshold', 'gray_threshold', 'auto_save', 'auto_deskew',
                    'auto_crop', 'padding', 'min_confidence', 'mistral_api_key',
                    'mistral_enabled', 'encryption_enabled', 'theme', 'language']
        sets = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)

        if not sets:
            return False

        try:
            self.conn.execute(
                f"UPDATE app_settings SET {', '.join(sets)} WHERE id = 'main'",
                params
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            return False
