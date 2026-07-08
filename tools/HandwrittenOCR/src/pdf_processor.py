"""
HandwrittenOCR - معالجة PDF v5.0
====================================
المحسنات الرئيسية:
- Batch TrOCR inference (3-6x تسريع)
- Smart Ensemble: تخطي TrOCR إذا ثقة EasyOCR عالية
- run_id tracking + processing_runs table
- DELETE-before-INSERT لمنع التكرار
- raw_text tracking
- Auto-export بعد المعالجة
- Checkpoint للاستئناف
- دعم PDF + صور منفصلة
- حماية قاعدة البيانات عند المزامنة (File Locking + Sync Status)
- دعم العمل المتزامن من عدة أجهزة
"""

import contextlib
import gc
import json
import logging
import os
import time
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import torch
from pdf2image import convert_from_path

from config import Config
from src.correction import (
    apply_correction_dict,
    build_correction_dict,
    spell_correct_word,
)
from src.database import HandwritingDB
from src.preprocessing import (
    crop_safe,
    match_boxes_with_detections,
    preprocess_image,
    smart_segmentation,
)
from src.recognition import OCREngine
from src.sync import FileLock, SyncManager

logger = logging.getLogger("HandwrittenOCR")


class PDFProcessor:
    """معالج ملفات PDF مع Batch TrOCR + Smart Ensemble + Run Tracking."""

    def __init__(self, config: Config, ocr_engine: OCREngine, db: HandwritingDB):
        self.config = config
        self.ocr = ocr_engine
        self.db = db

    def process(self, resume: bool = True) -> dict:
        """معالجة كاملة مع Batch TrOCR + run_id + auto-export + حماية المزامنة."""
        start_time = time.time()
        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        pages_start = self.config.pages_start
        pages_end = self.config.pages_end

        # حماية قاعدة البيانات عند تفعيل المزامنة
        sync_mgr = None
        lock = None
        if self.config.sync_enabled:
            sync_mgr = SyncManager(self.config)
            lock = FileLock(
                self.config.lock_file_path,
                timeout=self.config.sync_lock_timeout,
            )

            # كشف التعارضات قبل البدء
            conflicts = sync_mgr.detect_conflicts()
            if conflicts:
                for conflict in conflicts:
                    logger.warning(f"تعارض مزامنة: {conflict['message']}")

            try:
                lock.acquire()
            except TimeoutError as e:
                logger.error(str(e))
                return self._empty_stats(run_id, error="lock_timeout")

        try:
            stats = self._process_core(
                run_id, pages_start, pages_end, resume, start_time, sync_mgr
            )
            return stats
        finally:
            # تحرير القفل دائماً
            if lock:
                lock.release()

    def _process_core(self, run_id, pages_start, pages_end, resume, start_time, sync_mgr) -> dict:
        """المنطق الأساسي للمعالجة (يُستدعى داخل القفل)"""

        # بناء قاموس التصحيح
        correction_dict = build_correction_dict(
            self.config.feedback_csv,
            self.config.correction_dict_path,
            self.config.correction_min_votes,
        )
        if correction_dict:
            logger.info(f"قاموس التصحيح: {len(correction_dict)} كلمة")

        # استئناف من checkpoint
        checkpoint = self._load_checkpoint() if resume else None
        if checkpoint and checkpoint.get("input_path") == self.config.pdf_path:
            pages_start = int(
                checkpoint.get("next_page", self.config.pages_start)
            )
            logger.info(f"استئناف من الصفحة {pages_start}")

        # تسجيل بداية التشغيل
        self.db.insert_run(run_id, self.config.pdf_path)

        # تحويل PDF إلى صور
        try:
            images = convert_from_path(
                self.config.pdf_path,
                dpi=self.config.dpi,
                first_page=pages_start,
                last_page=pages_end,
            )
            page_nums = list(range(pages_start, pages_start + len(images)))
            logger.info(f"تم تحويل {len(images)} صفحة")
        except FileNotFoundError:
            logger.error(f"الملف غير موجود: {self.config.pdf_path}")
            return self._empty_stats(run_id)
        except Exception as e:
            logger.error(f"فشل تحويل PDF: {e}")
            return self._empty_stats(run_id, error=str(e))

        # حذف بيانات الصفحات المعاد معالجتها (منع التكرار)
        if page_nums:
            deleted = self.db.delete_pages(min(page_nums), max(page_nums))
            if deleted:
                logger.info(f"تم حذف {deleted} سجل قديم")

        total_words = 0
        conf_acc = []

        for _idx, (pil_img, actual_pg) in enumerate(zip(images, page_nums, strict=False)):
            logger.info(f"معالجة صفحة {actual_pg}/{pages_end}")

            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # كشف الكلمات باستخدام EasyOCR
            try:
                detections = self.ocr.detect_words_full(img_bgr)
            except Exception as e:
                detections = []
                logger.warning(f"EasyOCR p{actual_pg}: {e}")

            # معالجة مسبقة + تجزئة ذكية
            binary, _ = preprocess_image(img_bgr, self.config)
            boxes = smart_segmentation(img_bgr, binary, detections)
            boxes_info = match_boxes_with_detections(boxes, detections)

            # ---- BATCH TROCR ----
            need_trocr_idx, need_trocr_crops = [], []
            easy_results = []

            for i, ((x, y, w, h), easy_item) in enumerate(boxes_info):
                crop = crop_safe(img_bgr, x, y, w, h)
                if crop.size == 0:
                    easy_results.append(None)
                    continue

                if easy_item is not None:
                    _, txt, conf = easy_item
                    txt_str = txt.strip() if txt else ""
                    easy_results.append(("easyocr", txt_str, float(conf)))

                    # فقط الكلمات ذات ثقة منخفضة تحتاج TrOCR
                    if float(conf) < self.config.easy_conf_threshold:
                        need_trocr_idx.append(i)
                        need_trocr_crops.append(crop)
                else:
                    easy_results.append(None)
                    need_trocr_idx.append(i)
                    need_trocr_crops.append(crop)

            # Batch inference
            trocr_texts = {}
            for b_start in range(0, len(need_trocr_crops), self.ocr.trocr_batch_size):
                batch = need_trocr_crops[b_start:b_start + self.ocr.trocr_batch_size]
                texts = self.ocr.batch_predict(batch)
                for k, txt in enumerate(texts):
                    trocr_texts[need_trocr_idx[b_start + k]] = txt

            # الدمج والإدراج في DB
            for i, ((x, y, w, h), easy_item) in enumerate(boxes_info):
                crop = crop_safe(img_bgr, x, y, w, h)
                if crop.size == 0:
                    continue

                easy_res = easy_results[i]

                # اختيار أفضل نتيجة
                if easy_res and easy_res[2] >= self.config.easy_conf_threshold:
                    raw, conf, src = easy_res[1], easy_res[2], easy_res[0]
                elif trocr_texts.get(i):
                    raw = trocr_texts[i]
                    conf = self.config.trocr_default_confidence
                    src = "trocr"
                    if easy_res and easy_res[2] > conf:
                        raw, conf, src = easy_res[1], easy_res[2], easy_res[0]
                elif easy_res:
                    raw, conf, src = easy_res[1], easy_res[2], easy_res[0]
                else:
                    raw, conf, src = "", 0.0, "none"

                # التصحيح الإملائي + قاموس التصحيح
                corrected = apply_correction_dict(
                    spell_correct_word(raw), correction_dict
                )

                _, buf = cv2.imencode(".png", crop)
                self.db.insert_word(
                    image_data=buf.tobytes(),
                    predicted_text=corrected,
                    raw_text=raw,
                    status="unverified",
                    confidence=conf,
                    model_source=src,
                    x=x, y=y, w=w, h=h,
                    page_num=actual_pg,
                    run_id=run_id,
                )
                total_words += 1
                conf_acc.append(conf)

            # حفظ checkpoint
            self._save_checkpoint({
                "run_id": run_id,
                "input_path": self.config.pdf_path,
                "next_page": actual_pg + 1,
                "words": total_words,
                "ts": datetime.now().isoformat(),
            })

        # مسح checkpoint عند الاكتمال
        self._clear_checkpoint()

        duration = time.time() - start_time
        avg_conf = float(np.mean(conf_acc)) if conf_acc else 0.0

        # إنهاء تسجيل التشغيل
        self.db.finish_run(run_id, len(page_nums), total_words, avg_conf)

        stats = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "input": self.config.pdf_path,
            "pages": len(page_nums),
            "words": total_words,
            "avg_confidence": round(avg_conf, 4),
            "duration_sec": round(duration, 2),
        }

        # حفظ الإحصائيات
        os.makedirs(os.path.dirname(self.config.stats_json), exist_ok=True)
        with open(self.config.stats_json, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        # سجل التشغيلات
        self._save_run_history(stats)

        # تحديث حالة المزامنة
        if sync_mgr:
            sync_mgr.update_device_status(
                action="process",
                details={
                    "words": total_words,
                    "pages": len(page_nums),
                    "avg_conf": round(avg_conf, 4),
                }
            )

        # تنظيف الذاكرة
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info(
            f"اكتملت المعالجة: {total_words} كلمة في {duration:.1f}s"
        )
        return stats

    def _save_checkpoint(self, data: dict) -> None:
        """حفظ checkpoint لاستئناف المعالجة"""
        ckpt_path = self.config.checkpoint_file
        os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
        try:
            with open(ckpt_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"فشل حفظ checkpoint: {e}")

    def _load_checkpoint(self) -> dict | None:
        """تحميل checkpoint"""
        ckpt_path = self.config.checkpoint_file
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _clear_checkpoint(self) -> None:
        """مسح checkpoint عند الاكتمال"""
        ckpt_path = self.config.checkpoint_file
        if os.path.exists(ckpt_path):
            with contextlib.suppress(Exception):
                os.remove(ckpt_path)

    def _save_run_history(self, stats: dict) -> None:
        """حفظ سجل التشغيل في CSV"""
        os.makedirs(os.path.dirname(self.config.runs_csv), exist_ok=True)
        runs = pd.read_csv(self.config.runs_csv, encoding="utf-8-sig")
        runs = pd.concat([
            runs,
            pd.DataFrame([{
                "run_id": stats["run_id"],
                "timestamp": stats["timestamp"],
                "pages": stats["pages"],
                "words": stats["words"],
                "avg_conf": stats["avg_confidence"],
                "duration_sec": stats["duration_sec"],
                "status": "completed",
            }]),
        ], ignore_index=True)
        runs.to_csv(self.config.runs_csv, index=False, encoding="utf-8-sig")

    def _empty_stats(self, run_id: str = "", error: str = "") -> dict:
        return {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "input": self.config.pdf_path,
            "pages": 0,
            "words": 0,
            "avg_confidence": 0.0,
            "duration_sec": 0.0,
            "error": error or True,
        }
