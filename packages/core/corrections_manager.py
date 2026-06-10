"""
packages/core/corrections_manager.py
=======================================
مدير التصحيحات اليدوية — Active Learning
نُقل من packages/omni-core/ ودُمجت فيه نسخ متعددة

يتتبع التصحيحات اليدوية التي يجريها المستخدمون على نتائج OCR
ويُصدّرها لإعادة تدريب النماذج (Active Learning Pipeline)

الدورة:
  OCR → نتيجة خام → تصحيح المستخدم → حفظ هنا →
  تجميع دوري → إعادة تدريب → نموذج أدق
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CorrectionRecord:
    """سجل تصحيح واحد."""
    correction_id: str
    document_id: str
    original_text: str       # النص الخام من OCR
    corrected_text: str      # النص بعد تصحيح المستخدم
    engine: str
    language: str
    confidence_before: float
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_exported: bool = False    # هل صُدِّر لإعادة التدريب؟
    quality_score: Optional[float] = None  # تقييم جودة التصحيح نفسه

    @property
    def edit_distance(self) -> int:
        """حساب مسافة Levenshtein تقريبياً (للتصفية)."""
        a, b = self.original_text, self.corrected_text
        if abs(len(a) - len(b)) > 500:
            return 999
        if len(a) > 1000 or len(b) > 1000:
            # نسبة التغيير التقريبية للنصوص الطويلة
            return abs(len(a) - len(b))
        # Levenshtein بسيط للنصوص القصيرة
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                dp[j] = prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
                prev = temp
        return dp[n]

    @property
    def similarity(self) -> float:
        """نسبة التشابه بين الخام والمصحَّح (0.0–1.0)."""
        max_len = max(len(self.original_text), len(self.corrected_text), 1)
        return 1.0 - (self.edit_distance / max_len)

    @property
    def is_significant(self) -> bool:
        """هل التصحيح ذو قيمة للتدريب؟ (ليس تغييراً طفيفاً ولا مختلفاً كلياً)."""
        sim = self.similarity
        return 0.30 < sim < 0.98  # تجاهل التصحيحات الطفيفة جداً والمختلفة كلياً

    def to_training_pair(self) -> dict:
        """تحويل إلى زوج تدريب لـ TrOCR fine-tuning."""
        return {
            "source": self.original_text,
            "target": self.corrected_text,
            "language": self.language,
            "engine": self.engine,
            "quality": self.quality_score or self.similarity,
        }

    def to_dict(self) -> dict:
        return asdict(self)


class CorrectionsManager:
    """
    مدير التصحيحات للتعلم النشط.

    الاستخدام:
        cm = CorrectionsManager(db=DatabaseManager.get_instance())
        cm.add(CorrectionRecord(...))
        pairs = cm.export_for_training(min_samples=50)
    """

    def __init__(self, db=None, corrections_dir: str = "./corrections"):
        self._db = db
        self._dir = Path(corrections_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Add ───────────────────────────────────────────────────

    def add(self, record: CorrectionRecord) -> None:
        """أضف تصحيحاً جديداً."""
        # حفظ محلي (JSON) كـ backup
        self._save_local(record)

        # حفظ في قاعدة البيانات
        if self._db:
            self._save_to_db(record)

        if record.is_significant:
            logger.info(
                f"Significant correction added: doc={record.document_id}, "
                f"similarity={record.similarity:.2f}"
            )

    def add_from_api(
        self,
        document_id: str,
        original_text: str,
        corrected_text: str,
        engine: str,
        language: str,
        confidence: float,
        user_id: str,
    ) -> CorrectionRecord:
        """واجهة مبسّطة من الـ API."""
        record = CorrectionRecord(
            correction_id=hashlib.md5(
                f"{document_id}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16],
            document_id=document_id,
            original_text=original_text,
            corrected_text=corrected_text,
            engine=engine,
            language=language,
            confidence_before=confidence,
            user_id=user_id,
        )
        self.add(record)
        return record

    # ── Query ─────────────────────────────────────────────────

    def get_pending_export(self, limit: int = 1000) -> list[CorrectionRecord]:
        """جلب التصحيحات التي لم تُصدَّر بعد."""
        if self._db:
            return self._load_from_db(exported=False, limit=limit)
        return self._load_from_files(exported=False, limit=limit)

    def get_stats(self) -> dict:
        """إحصائيات التصحيحات."""
        all_records = self._load_from_files(limit=10000)
        total = len(all_records)
        exported = sum(1 for r in all_records if r.is_exported)
        significant = sum(1 for r in all_records if r.is_significant)
        by_engine = {}
        by_language = {}
        for r in all_records:
            by_engine[r.engine] = by_engine.get(r.engine, 0) + 1
            by_language[r.language] = by_language.get(r.language, 0) + 1

        return {
            "total": total,
            "exported": exported,
            "pending_export": total - exported,
            "significant": significant,
            "by_engine": by_engine,
            "by_language": by_language,
            "avg_similarity": round(
                sum(r.similarity for r in all_records) / max(total, 1), 3
            ),
        }

    # ── Export for Training ───────────────────────────────────

    def export_for_training(
        self,
        output_path: str = "./training_data/corrections.json",
        min_similarity: float = 0.30,
        max_similarity: float = 0.98,
        min_samples: int = 10,
        languages: Optional[list[str]] = None,
    ) -> dict:
        """
        صدّر تصحيحات للتدريب بتنسيق Hugging Face datasets.

        يُرجع إحصائيات التصدير.
        """
        records = self.get_pending_export()

        # فلترة
        filtered = [
            r for r in records
            if min_similarity < r.similarity < max_similarity
            and (languages is None or r.language in languages)
        ]

        if len(filtered) < min_samples:
            logger.warning(
                f"Only {len(filtered)} corrections available "
                f"(min_samples={min_samples}) — skipping export"
            )
            return {"exported": 0, "reason": "insufficient_samples"}

        # تصدير
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        pairs = [r.to_training_pair() for r in filtered]
        export_data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(pairs),
            "pairs": pairs,
        }
        out_path.write_text(
            json.dumps(export_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # ضع علامة على المُصدَّر
        for r in filtered:
            r.is_exported = True
            self._save_local(r)

        logger.info(f"Exported {len(pairs)} correction pairs to {output_path}")
        return {
            "exported": len(pairs),
            "output_path": str(out_path),
            "by_language": {
                lang: sum(1 for p in pairs if p["language"] == lang)
                for lang in set(p["language"] for p in pairs)
            },
        }

    # ── Persistence ───────────────────────────────────────────

    def _save_local(self, record: CorrectionRecord) -> None:
        """حفظ محلي كـ JSON backup."""
        date_dir = self._dir / datetime.utcnow().strftime("%Y-%m")
        date_dir.mkdir(parents=True, exist_ok=True)
        path = date_dir / f"{record.correction_id}.json"
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_from_files(
        self,
        exported: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[CorrectionRecord]:
        records = []
        for json_file in sorted(self._dir.rglob("*.json"), reverse=True):
            if len(records) >= limit:
                break
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                record = CorrectionRecord(**data)
                if exported is None or record.is_exported == exported:
                    records.append(record)
            except Exception as exc:
                logger.warning(f"Skip {json_file.name}: {exc}")
        return records

    def _save_to_db(self, record: CorrectionRecord) -> None:
        if not self._db:
            return
        try:
            with self._db.session() as s:
                from sqlalchemy import text
                s.execute(text("""
                    INSERT INTO "CorrectionRecord"
                    (correction_id, document_id, original_text, corrected_text,
                     engine, language, confidence_before, user_id, created_at, is_exported)
                    VALUES
                    (:cid, :did, :orig, :corr, :eng, :lang, :conf, :uid, :cat, :exp)
                    ON CONFLICT (correction_id) DO UPDATE SET
                      is_exported = EXCLUDED.is_exported
                """), {
                    "cid": record.correction_id, "did": record.document_id,
                    "orig": record.original_text, "corr": record.corrected_text,
                    "eng": record.engine, "lang": record.language,
                    "conf": record.confidence_before, "uid": record.user_id,
                    "cat": record.created_at, "exp": record.is_exported,
                })
        except Exception as exc:
            logger.warning(f"DB save failed, using local only: {exc}")

    def _load_from_db(self, exported: bool = False, limit: int = 1000) -> list[CorrectionRecord]:
        if not self._db:
            return []
        try:
            with self._db.session() as s:
                from sqlalchemy import text
                rows = s.execute(text("""
                    SELECT * FROM "CorrectionRecord"
                    WHERE is_exported = :exp
                    ORDER BY created_at DESC
                    LIMIT :lim
                """), {"exp": exported, "lim": limit}).fetchall()
                return [CorrectionRecord(**dict(r._mapping)) for r in rows]
        except Exception as exc:
            logger.warning(f"DB load failed: {exc}")
            return []
