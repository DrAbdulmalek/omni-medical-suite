#!/usr/bin/env python3
"""
Medical Image AI Suite - نقطة الدخول الموحدة
خط أنابيب متكامل لتجهيز وتدريب وتوليد الصور الطبية

الاستخدام:
    python main_pipeline.py --phase 1 --input ./data/raw --output ./data/processed
    python main_pipeline.py --phase 2 --mode train --config ./configs/config.yaml
    python main_pipeline.py --phase 3 --mode generate --num 100
    python main_pipeline.py --phase 4 --input ./data/processed
"""

import argparse
import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np


def setup_project():
    """إعداد مسارات المشروع"""
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    # إنشاء المجلدات المطلوبة
    for subdir in ["data/raw", "data/processed", "data/labels", "data/synthetic",
                    "data/reports", "logs", "models", "configs"]:
        (project_root / subdir).mkdir(parents=True, exist_ok=True)

    return project_root


def phase1_preprocess(args, config: Dict[str, Any], root: Path):
    """
    المرحلة 1: توحيد وتجهيز البيانات
    تحويل DICOM/JPG إلى صيغ موحدة
    """
    from src.preprocessing.dicom_handler import DICOMHandler
    from src.preprocessing.image_handler import ImageHandler
    from src.utils.logger import setup_logger

    logger = setup_logger("phase1", config.get("general", {}).get("log_level", "INFO"))

    input_dir = Path(args.input) if args.input else root / "data" / "raw"
    output_dir = Path(args.output) if args.output else root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("المرحلة 1: توحيد وتجهيز البيانات (Preprocessing)")
    logger.info("=" * 60)

    prep_config = config.get("preprocessing", {})
    target_size = tuple(prep_config.get("target_size", [512, 512]))
    normalize = prep_config.get("normalize", True)
    normalize_range = tuple(prep_config.get("normalize_range", [0.0, 1.0]))

    total_stats = {"dicom": 0, "jpg": 0, "other": 0, "errors": []}

    # معالجة DICOM
    if args.modality in (None, "dicom"):
        try:
            handler = DICOMHandler(
                target_size=target_size,
                normalize=normalize,
                normalize_range=normalize_range,
                default_window=prep_config.get("dicom_to_jpg", {}).get("default_window", "lung"),
            )

            # البحث عن ملفات DICOM
            dcm_output = output_dir / "dicom"
            stats = handler.batch_process(
                input_dir, dcm_output,
                modality_filter=args.modality_filter,
                window=prep_config.get("dicom_to_jpg", {}).get("default_window", "lung"),
                format=args.format or "npy",
            )
            total_stats["dicom"] = stats["success"]
            total_stats["errors"].extend(stats["errors"])

            logger.info(f"DICOM: نجح={stats['success']}, فشل={stats['failed']}")

        except Exception as e:
            logger.error(f"خطأ في معالجة DICOM: {e}")

    # معالجة JPG/PNG
    if args.modality in (None, "jpg"):
        try:
            img_handler = ImageHandler(
                target_size=target_size,
                normalize=normalize,
                normalize_range=normalize_range,
            )

            jpg_output = output_dir / "images"
            images, paths = img_handler.load_batch(input_dir, max_files=args.max_files)

            # حفظ المصفوفات
            for i, (img, path) in enumerate(zip(images, paths)):
                out_path = jpg_output / f"image_{i:05d}.npy"
                np.save(str(out_path), img)

            total_stats["jpg"] = len(images)
            logger.info(f"JPG/PNG: تم معالجة {len(images)} صورة")

        except Exception as e:
            logger.error(f"خطأ في معالجة JPG: {e}")

    # حفظ الإحصائيات
    stats_file = output_dir / "preprocessing_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(total_stats, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"تم الانتهاء من المرحلة 1 | الإحصائيات: {total_stats}")
    return total_stats


def phase2_semisupervised(args, config: Dict[str, Any], root: Path):
    """
    المرحلة 2: التعلّم شبه الخاضع للإشراف
    استخراج الإشارات الضعيفة وتدريب النماذج
    """
    from src.ner.arabic_ner import ArabicMedicalNER
    from src.ner.medical_entities import MedicalDictionary
    from src.preprocessing.text_handler import TextHandler
    from src.semisupervised.weak_labels import WeakLabelExtractor, BinaryLabelExtractor
    from src.semisupervised.trainer import SemiSupervisedTrainer
    from src.utils.logger import setup_logger

    logger = setup_logger("phase2", config.get("general", {}).get("log_level", "INFO"))

    mode = args.mode or "labels"
    input_dir = Path(args.input) if args.input else root / "data" / "reports"
    output_dir = Path(args.output) if args.output else root / "data" / "labels"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"المرحلة 2: التعلّم شبه الخاضع للإشراف (الوضع: {mode})")
    logger.info("=" * 60)

    if mode == "ner":
        # استخراج الكيانات من التقارير
        text_handler = TextHandler()
        ner = ArabicMedicalNER(
            use_dictionary=True,
            use_patterns=True,
            use_model=args.use_model,
        )

        reports = []
        report_dir = input_dir
        for f in report_dir.rglob("*.txt"):
            try:
                text = f.read_text(encoding="utf-8")
                reports.append(text)
            except Exception:
                continue

        logger.info(f"تم تحميل {len(reports)} تقرير")

        all_ner_results = []
        for i, report in enumerate(reports):
            cleaned = text_handler.clean(report)
            results = ner.extract(cleaned)
            all_ner_results.append(results)

        # حفظ النتائج
        ner_file = output_dir / "ner_results.json"
        # تحويل np arrays لـ lists
        for r in all_ner_results:
            for k, v in r.items():
                if isinstance(v, np.ndarray):
                    r[k] = v.tolist()
        with open(ner_file, "w", encoding="utf-8") as f:
            json.dump(all_ner_results, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"تم حفظ نتائج NER: {ner_file}")

    elif mode == "labels":
        # استخراج الإشارات الضعيفة
        text_handler = TextHandler()
        extractor = BinaryLabelExtractor()

        reports = []
        for f in input_dir.rglob("*.txt"):
            try:
                reports.append(f.read_text(encoding="utf-8"))
            except Exception:
                continue

        if not reports:
            logger.warning("لم يتم العثور على تقارير")
            return

        label_matrix, class_names, stats = extractor.extract_batch(reports)

        # حفظ
        np.save(str(output_dir / "label_matrix.npy"), label_matrix)
        with open(output_dir / "class_names.json", "w", encoding="utf-8") as f:
            json.dump(class_names, f, ensure_ascii=False, indent=2)
        with open(output_dir / "label_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"الإشارات: {label_matrix.shape}, الفئات: {len(class_names)}")

    elif mode == "train":
        # تدريب النموذج
        processed_dir = root / "data" / "processed"

        # تحميل البيانات المصنفة
        labeled_path = processed_dir / "images"
        if labeled_path.exists():
            images = []
            for f in sorted(labeled_path.glob("*.npy")):
                images.append(np.load(f))
            labeled_images = np.array(images)
        else:
            logger.error("لا توجد بيانات مُعالجة. يرجى تشغيل المرحلة 1 أولاً.")
            return

        # تحميل الإشارات الضعيفة
        label_path = output_dir / "label_matrix.npy"
        if label_path.exists():
            weak_labels = np.load(label_path)
        else:
            weak_labels = None

        semiconfig = config.get("semisupervised", {})
        trainer = SemiSupervisedTrainer(
            num_classes=semiconfig.get("num_classes", 10),
            architecture=semiconfig.get("backbone", "resnet50"),
            pretrained=semiconfig.get("pretrained", True),
        )

        # تسميات وهمية للتوضيح (في الواقع: استخدم الـ weak_labels)
        dummy_labels = np.random.randint(0, semiconfig.get("num_classes", 10), len(labeled_images))

        history = trainer.train(
            labeled_images=labeled_images,
            labeled_labels=dummy_labels,
            epochs=semiconfig.get("training", {}).get("epochs", 50),
            batch_size=semiconfig.get("training", {}).get("batch_size", 16),
            learning_rate=semiconfig.get("training", {}).get("learning_rate", 1e-4),
            save_dir=str(root / "models"),
        )

        # حفظ السجل
        with open(output_dir / "training_history.json", "w") as f:
            json.dump(history, f, indent=2)

        logger.info("انتهى التدريب")

    elif mode == "evaluate":
        logger.info("وضع التقييم - قريباً")


def phase3_synthetic(args, config: Dict[str, Any], root: Path):
    """
    المرحلة 3: توليد بيانات اصطناعية
    """
    from src.synthetic.medgan import MedGAN
    from src.utils.logger import setup_logger

    logger = setup_logger("phase3", config.get("general", {}).get("log_level", "INFO"))

    output_dir = Path(args.output) if args.output else root / "data" / "synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("المرحلة 3: توليد بيانات اصطناعية (Synthetic Data)")
    logger.info("=" * 60)

    synconfig = config.get("synthetic", {})

    if args.mode == "generate":
        gan = MedGAN(
            image_size=64,
            latent_dim=synconfig.get("generator", {}).get("latent_dim", 128),
            gan_type=synconfig.get("method", "WGAN-GP"),
        )

        # محاولة تحميل بيانات حقيقية
        processed_dir = root / "data" / "processed"
        real_images = None
        for subdir in ["images", "dicom"]:
            img_dir = processed_dir / subdir
            if img_dir.exists():
                images = []
                for f in sorted(img_dir.glob("*.npy"))[:500]:
                    img = np.load(f)
                    if img.shape[0] == img.shape[1]:
                        # تغيير الحجم إلى 64x64
                        from PIL import Image
                        pil_img = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
                        pil_img = pil_img.resize((64, 64), Image.BILINEAR)
                        images.append(np.array(pil_img).astype(np.float32) / 255.0)
                if images:
                    real_images = np.array(images)
                    break

        num_gen = args.num or synconfig.get("num_synthetic", 100)

        if real_images is not None and len(real_images) >= 50:
            logger.info(f"تدريب GAN على {len(real_images)} صورة حقيقية")
            gan.train(
                real_images,
                epochs=100,
                batch_size=synconfig.get("training", {}).get("batch_size", 32),
                save_dir=str(output_dir),
            )

        # توليد الصور
        synthetic = gan.generate(num_gen)

        # حفظ
        for i, img in enumerate(synthetic):
            np.save(str(output_dir / f"synthetic_{i:05d}.npy"), img)

        logger.info(f"تم توليد {num_gen} صورة اصطناعية")

    else:
        logger.warning("الوضع غير مدعوم. استخدم --mode generate")


def phase4_reportgen(args, config: Dict[str, Any], root: Path):
    """
    المرحلة 4: توليد تقارير تلقائية من الصور
    """
    from src.reportgen.vlm_reporter import VLMReporter, ReportGenerator
    from src.utils.logger import setup_logger

    logger = setup_logger("phase4", config.get("general", {}).get("log_level", "INFO"))

    input_dir = Path(args.input) if args.input else root / "data" / "processed" / "images"
    output_dir = Path(args.output) if args.output else root / "data" / "reports" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("المرحلة 4: توليد تقارير تلقائية (Report Generation)")
    logger.info("=" * 60)

    repconfig = config.get("reportgen", {})
    reporter = VLMReporter(
        language=repconfig.get("report_language", "ar"),
    )

    # تحميل الصور
    images = []
    for f in sorted(input_dir.glob("*.npy"))[:args.max_files or 20]:
        images.append(np.load(f))

    if not images:
        logger.warning("لم يتم العثور على صور في المجلد")
        return

    logger.info(f"توليد تقارير لـ {len(images)} صورة")

    reports = reporter.generate_batch(np.array(images))

    # حفظ التقارير
    for i, report in enumerate(reports):
        report_file = output_dir / f"report_{i:05d}.txt"
        report_file.write_text(report, encoding="utf-8")

    logger.info(f"تم توليد {len(reports)} تقرير")


def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """تحميل ملف الإعدادات"""
    import yaml

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # إعدادات افتراضية
    return {
        "general": {"seed": 42, "log_level": "INFO"},
        "preprocessing": {"target_size": [512, 512], "normalize": True},
    }


def main():
    parser = argparse.ArgumentParser(
        description="Medical Image AI Suite - خط أنابيب متكامل للصور الطبية",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:
  # المرحلة 1: معالجة البيانات
  python main_pipeline.py --phase 1 --input ./data/raw --output ./data/processed

  # المرحلة 2: استخراج الكيانات
  python main_pipeline.py --phase 2 --mode ner --input ./data/reports

  # المرحلة 2: تدريب النموذج
  python main_pipeline.py --phase 2 --mode train

  # المرحلة 3: توليد بيانات اصطناعية
  python main_pipeline.py --phase 3 --mode generate --num 100

  # المرحلة 4: توليد تقارير
  python main_pipeline.py --phase 4 --input ./data/processed/images
        """,
    )

    parser.add_argument("--phase", type=int, required=True, choices=[1, 2, 3, 4],
                        help="رقم المرحلة (1=معالجة, 2=تدريب, 3=توليد, 4=تقارير)")
    parser.add_argument("--mode", type=str, help="وضع العمل (ner, labels, train, generate, batch)")
    parser.add_argument("--input", type=str, help="مسار الإدخال")
    parser.add_argument("--output", type=str, help="مسار الإخراج")
    parser.add_argument("--config", type=str, default="./configs/config.yaml", help="ملف الإعدادات")
    parser.add_argument("--modality", type=str, choices=["dicom", "jpg"], help="نوع الملفات")
    parser.add_argument("--format", type=str, choices=["npy", "jpg", "png"], help="صيغة الإخراج")
    parser.add_argument("--num", type=int, help="عدد العينات")
    parser.add_argument("--max-files", type=int, help="أقصى عدد ملفات")
    parser.add_argument("--modality-filter", type=str, help="تصفية حسب نوع الفحص")
    parser.add_argument("--use-model", action="store_true", help="استخدام نموذج NER")

    args = parser.parse_args()

    # إعداد المشروع
    root = setup_project()
    config = load_config(args.config)

    # تنفيذ المرحلة المطلوبة
    start_time = time.time()

    if args.phase == 1:
        phase1_preprocess(args, config, root)
    elif args.phase == 2:
        phase2_semisupervised(args, config, root)
    elif args.phase == 3:
        phase3_synthetic(args, config, root)
    elif args.phase == 4:
        phase4_reportgen(args, config, root)

    elapsed = time.time() - start_time
    print(f"\n✓ انتهت المرحلة {args.phase} في {elapsed:.1f} ثانية")


if __name__ == "__main__":
    main()
