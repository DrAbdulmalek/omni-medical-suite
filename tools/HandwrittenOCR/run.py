"""
HandwrittenOCR - نقطة الدخول السريعة v5.0
============================================
تشغيل التطبيق من الجذر:
    python run.py
    python run.py --local                          # تشغيل محلي أوفلاين
    python run.py --pdf input.pdf --pages 1 5
    python run.py --local --host 0.0.0.0           # الاستماع على الشبكة المحلية
    python run.py --colab                          # وضع Google Colab
    python run.py --hf-token hf_xxx --cache-dir ./models_cache
"""

import argparse
import sys
from pathlib import Path

# إضافة مجلد المشروع إلى مسار Python
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from src.main import main


def parse_args():
    parser = argparse.ArgumentParser(
        description="HandwrittenOCR v5.0 - استخراج وتصحيح نصوص الخط اليدوي"
    )
    parser.add_argument(
        "--pdf", type=str, default=None,
        help="مسار ملف PDF (الافتراضي: input.pdf)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="مجلد الإخراج (الافتراضي: ~/Handwritten_OCR_Ultimate)"
    )
    parser.add_argument(
        "--pages", type=int, nargs=2, default=None,
        metavar=("START", "END"),
        help="نطاق الصفحات (مثال: --pages 1 5)"
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="DPI لتحويل PDF (الافتراضي: 300)"
    )
    parser.add_argument(
        "--hf-token", type=str, default="",
        help="توكن Hugging Face للنماذج المحمية"
    )
    parser.add_argument(
        "--cache-dir", type=str, default="",
        help="مسار التخزين المؤقت للنماذج (cache_dir)"
    )
    parser.add_argument(
        "--colab", action="store_true",
        help="وضع Google Colab (استخدام Google Drive + cache)"
    )
    parser.add_argument(
        "--local", action="store_true",
        help="وضع التشغيل المحلي (Offline) - يكتشف GPU والمسارات تلقائياً"
    )
    parser.add_argument(
        "--host", type=str, default=None,
        help="عنوان الاستماع (127.0.0.0 للجهاز فقط, 0.0.0.0 للشبكة المحلية)"
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="منفذ الخادم (الافتراضي: 7860)"
    )
    parser.add_argument(
        "--project-root", type=str, default=None,
        help="مسار مجلد المشروع (للتشغيل من مسار مخصص)"
    )
    parser.add_argument(
        "--no-sync", action="store_true",
        help="تعطيل نظام المزامنة (افتراضي: مفعل في الوضع المحلي)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.colab:
        # وضع Google Colab
        config = Config.from_colab_drive(hf_token=args.hf_token)
    elif args.local:
        # وضع التشغيل المحلي (Offline)
        project_root = args.project_root or ""
        pdf_path = args.pdf or ""
        config = Config.from_local(pdf_path=pdf_path, project_root=project_root)

        # تطبيق تجاوزات سطر الأوامر
        if args.output:
            config.output_dir = args.output
        if args.pages:
            config.pages_start, config.pages_end = args.pages
        if args.dpi != 300:
            config.dpi = args.dpi
        if args.hf_token:
            config.hf_token = args.hf_token
        if args.cache_dir:
            config.model_cache_dir = args.cache_dir
        if args.host:
            config.server_host = args.host
        if args.port:
            config.gradio_port = args.port
        if args.no_sync:
            config.sync_enabled = False
    else:
        # الوضع الافتراضي (متوافق مع الإصدارات السابقة)
        overrides = {}
        if args.pdf:
            overrides["pdf_path"] = args.pdf
        if args.output:
            overrides["output_dir"] = args.output
        if args.pages:
            overrides["pages_start"], overrides["pages_end"] = args.pages
        overrides["dpi"] = args.dpi
        if args.hf_token:
            overrides["hf_token"] = args.hf_token
        if args.cache_dir:
            overrides["model_cache_dir"] = args.cache_dir
        if args.host:
            overrides["server_host"] = args.host
        if args.port:
            overrides["gradio_port"] = args.port
        if args.no_sync:
            overrides["sync_enabled"] = False
        else:
            overrides["sync_enabled"] = True
        config = Config.from_dict(overrides)

    main(config)
