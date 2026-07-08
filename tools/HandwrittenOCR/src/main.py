"""
HandwrittenOCR - الوحدة الرئيسية v5.0
========================================
نقطة الدخول الرئيسية - تجمع بين جميع المكونات.
يدعم: التشغيل المحلي (Offline)، المزامنة بين الأجهزة، واجهة الشبكة المحلية.
"""

import time

from config import Config
from src.correction import init_correctors
from src.database import HandwritingDB
from src.logger import setup_logging
from src.metrics import compute_metrics
from src.pdf_processor import PDFProcessor
from src.recognition import OCREngine
from src.review_ui import ReviewUI


def main(config: Config | None = None):
    if config is None:
        config = Config()

    # إعداد شامل
    config.setup()
    config.apply_hf_token()
    config.apply_cache_env()
    if not config.is_colab:
        # لا حاجة لربط EasyOCR بالـ Drive محلياً
        pass
    else:
        config.setup_easyocr_symlink()

    logger = setup_logging(config)
    logger.info("بدء تشغيل HandwrittenOCR v5.0")
    logger.info(f"ملف PDF: {config.pdf_path}")
    logger.info(f"مجلد الإخراج: {config.output_dir or config.project_root}")
    if config.model_cache_dir or config.cache_dir:
        logger.info(f"تخزين مؤقت: {config.model_cache_dir or config.cache_dir}")

    # عرض معلومات المزامنة
    if config.sync_enabled:
        from src.sync import SyncManager
        sync_mgr = SyncManager(config)
        network = sync_mgr.get_network_info()

        print("\n" + "=" * 50)
        print("  نظام المزامنة: مفعّل")
        print("=" * 50)
        print(f"  معرف الجهاز:  {sync_mgr.device_id}")
        print(f"  شبكة محلية:   {network.get('local_ip', 'N/A')}")
        print(f"  واجهة المراجعة: {network.get('server_url', 'N/A')}")
        print(f"  API:           {network.get('api_url', 'N/A')}")
        print("=" * 50)

        # كشف التعارضات
        conflicts = sync_mgr.detect_conflicts()
        if conflicts:
            for c in conflicts:
                print(f"  تحذير: {c['message']}")

    # تحميل المدققات الإملائية
    init_correctors()

    # تحميل محرك التعرف (مع LoRA تلقائي)
    start = time.time()
    ocr_engine = OCREngine(
        trocr_model_name=config.trocr_model_name,
        ocr_languages=config.ocr_languages,
        max_text_length=config.max_text_length,
        cache_dir=config.model_cache_dir or config.cache_dir,
        hf_token=config.hf_token,
        trocr_default_confidence=config.trocr_default_confidence,
        easy_conf_threshold=config.easy_conf_threshold,
        num_beams=config.num_beams,
        trocr_batch_size=config.trocr_batch_size,
        lora_save_path=config.lora_save_path,
    )
    logger.info(f"تم تحميل النماذج في {time.time() - start:.2f} ثانية")
    if ocr_engine.lora_loaded:
        print("تم تحميل النموذج المُحسَّن (LoRA)")
    else:
        print("يستخدم النموذج الأساسي")

    # تهيئة قاعدة البيانات
    db = HandwritingDB(config.db_path)

    # معالجة PDF
    processor = PDFProcessor(config, ocr_engine, db)
    stats = processor.process()

    if stats.get("error"):
        logger.error("فشلت المعالجة!")
        if isinstance(stats.get("error"), str):
            logger.error(f"السبب: {stats['error']}")
            if stats.get("error") == "lock_timeout":
                print("\nتعذر الحصول على قفل المعالجة - جهاز آخر يعمل حالياً.")
                print("انتظر حتى يكتمل الجهاز الآخر أو أوقف المعالجة عليه.")
        return

    # عرض الإحصائيات
    print("\n" + "=" * 50)
    print("  إحصائيات المعالجة v5.0")
    print("=" * 50)
    print(f"  Run ID:        {stats.get('run_id', 'N/A')}")
    print(f"  الصفحات:       {stats.get('pages', 0)}")
    print(f"  الكلمات:       {stats.get('words', 0)}")
    print(f"  متوسط الثقة:   {stats.get('avg_confidence', 0):.2%}")
    print(f"  الوقت:         {stats.get('duration_sec', 0):.1f} ثانية")
    print("=" * 50)

    # حساب المقاييس (WER/CER)
    if config.metrics_log:
        try:
            m = compute_metrics(db, metrics_log=config.metrics_log)
            if m.get("wer") is not None:
                print(f"\n  WER: {m['wer']:.2%} | CER: {m['cer']:.2%} ({m['samples']} عينة)")
        except Exception as e:
            logger.debug(f"Metrics: {e}")

    # ملفات المراقبة
    print("\nملفات المراقبة:")
    print(f"  سجل الأحداث:   {config.log_file}")
    print(f"  إحصائيات:      {config.stats_json}")
    print(f"  تصحيحات:       {config.feedback_csv}")
    print(f"  قاموس التصحيح: {config.correction_dict_path}")

    if config.sync_enabled:
        print(f"  حالة المزامنة: {config.sync_status_path}")

    # تشغيل واجهة المراجعة
    print("\nتشغيل واجهة المراجعة...")
    review_ui = ReviewUI(db, config.feedback_csv)
    review_ui.launch()


if __name__ == "__main__":
    main()
