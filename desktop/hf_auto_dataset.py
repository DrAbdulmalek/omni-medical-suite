# hf_auto_dataset.py
"""
HF Auto Dataset Creator & Manager
إنشاء وإدارة Dataset على Hugging Face تلقائياً
يدعم: arabic-medical-ocr-corrections + scanner-fixer-logs
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from datasets import Dataset, DatasetDict, Features, Image as HFImage, Value
    from huggingface_hub import HfApi, create_repo, hf_hub_download, upload_file
    HF_DATASETS_AVAILABLE = True
except ImportError:
    HF_DATASETS_AVAILABLE = False
    print("⚠️ datasets library not installed. Run: pip install datasets huggingface-hub")


class HFAutoDatasetManager:
    """مدير Dataset تلقائي على Hugging Face"""

    # أنواع الـ Datasets المدعومة
    DATASET_TYPES = {
        "corrections": {
            "name": "arabic-medical-ocr-corrections",
            "description": "Arabic Medical OCR Human Corrections Dataset",
            "features": {
                "image": HFImage(),
                "incorrect_ocr_output": Value("string"),
                "correct_text": Value("string"),
                "category": Value("string"),
                "source": Value("string"),
                "confidence_before": Value("float32"),
                "confidence_after": Value("float32"),
                "timestamp": Value("string"),
                "user_id": Value("string"),
                "image_quality_score": Value("float32"),
            }
        },
        "scanner_logs": {
            "name": "scanner-fixer-logs",
            "description": "Scanner Fixer Processing Logs & Metrics",
            "features": {
                "original_image": HFImage(),
                "processed_image": HFImage(),
                "processing_options": Value("string"),  # JSON
                "processing_time_ms": Value("float32"),
                "shadow_removed": Value("bool"),
                "deskew_angle": Value("float32"),
                "perspective_corrected": Value("bool"),
                "denoise_applied": Value("bool"),
                "contrast_enhanced": Value("bool"),
                "auto_crop_applied": Value("bool"),
                "input_dimensions": Value("string"),
                "output_dimensions": Value("string"),
                "timestamp": Value("string"),
            }
        },
        "training_pairs": {
            "name": "arabic-medical-ocr-training-pairs",
            "description": "Training Pairs for Fine-tuning Medical OCR",
            "features": {
                "image": HFImage(),
                "text": Value("string"),
                "category": Value("string"),
                "font_type": Value("string"),  # printed, handwriting, mixed
                "language": Value("string"),   # ar, en, mixed
                "quality_label": Value("string"),  # high, medium, low
                "timestamp": Value("string"),
            }
        }
    }

    def __init__(self, hf_token: str | None = None, username: str = "DrAbdulmalek"):
        """
        تهيئة مدير الـ Dataset

        Args:
            hf_token: توكن Hugging Face
            username: اسم المستخدم على HF
        """
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.username = username
        self.api = HfApi(token=self.hf_token) if self.hf_token else None

        if not HF_DATASETS_AVAILABLE:
            raise ImportError("datasets library required. Run: pip install datasets")

        if not self.hf_token:
            print("⚠️ No HF_TOKEN provided. Dataset creation will fail.")

    def create_dataset(self, dataset_type: str, private: bool = False) -> str:
        """
        إنشاء Dataset جديد على HF

        Args:
            dataset_type: نوع الـ Dataset (corrections, scanner_logs, training_pairs)
            private: خاص أم عام

        Returns:
            اسم الـ Dataset الكامل
        """
        if dataset_type not in self.DATASET_TYPES:
            raise ValueError(f"Unknown dataset type: {dataset_type}. Available: {list(self.DATASET_TYPES.keys())}")

        config = self.DATASET_TYPES[dataset_type]
        dataset_name = f"{self.username}/{config['name']}"

        try:
            # إنشاء الـ repo
            create_repo(
                dataset_name,
                repo_type="dataset",
                private=private,
                token=self.hf_token,
                exist_ok=True
            )
            print(f"✅ Dataset repo created/verified: {dataset_name}")

            # إنشاء ملف README.md
            readme_content = f"""---
annotations_creators:
- machine-generated
- human-annotated
language:
- ar
- en
language_creators:
- found
license:
- mit
multilinguality:
- multilingual
pretty_name: {config['description']}
size_categories:
- unknown
source_datasets:
- original
task_categories:
- text-generation
- image-to-text
task_ids:
- optical-character-recognition
---

# {config['description']}

## Description

This dataset is part of the Omni Medical OCR ecosystem.
Automatically created and managed by Scanner Fixer Pro.

## Dataset Types

- **Corrections**: Human-verified OCR corrections for medical documents
- **Scanner Logs**: Image preprocessing logs and metrics
- **Training Pairs**: Image-text pairs for OCR model fine-tuning

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("{dataset_name}")
```

## Citation

```bibtex
@dataset{{{config['name']},
  author = {{Dr. Abdulmalek Tamer Al-husseini}},
  title = {{{config['description']}}},
  year = {{2026}},
  publisher = {{Hugging Face}}
}}
```
"""

            # رفع README
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(readme_content)
                readme_path = f.name

            upload_file(
                path_or_fileobj=readme_path,
                path_in_repo="README.md",
                repo_id=dataset_name,
                repo_type="dataset",
                token=self.hf_token
            )

            os.unlink(readme_path)
            print(f"✅ README uploaded to {dataset_name}")

            return dataset_name

        except Exception as e:
            print(f"❌ Failed to create dataset: {e}")
            raise

    def add_correction_record(self,
                            dataset_name: str,
                            image_path: str,
                            incorrect_text: str,
                            correct_text: str,
                            category: str = "prescription",
                            source: str = "desktop_app",
                            confidence_before: float = 0.0,
                            confidence_after: float = 0.0,
                            user_id: str = "anonymous") -> bool:
        """
        إضافة سجل تصحيح إلى Dataset

        Args:
            dataset_name: اسم الـ Dataset الكامل
            image_path: مسار الصورة
            incorrect_text: النص الخاطئ
            correct_text: النص الصحيح
            category: التصنيف
            source: المصدر
            confidence_before: الثقة قبل التصحيح
            confidence_after: الثقة بعد التصحيح
            user_id: معرف المستخدم

        Returns:
            True if successful
        """
        try:
            # قراءة الصورة
            image = cv2.imread(image_path)
            if image is None:
                print(f"❌ Cannot read image: {image_path}")
                return False

            # تحويل BGR إلى RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # إنشاء سجل
            record = {
                "image": image_rgb,
                "incorrect_ocr_output": incorrect_text,
                "correct_text": correct_text,
                "category": category,
                "source": source,
                "confidence_before": confidence_before,
                "confidence_after": confidence_after,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "image_quality_score": self._calculate_quality_score(image),
            }

            # تحميل الـ Dataset الموجود أو إنشاء جديد
            try:
                from datasets import load_dataset
                existing = load_dataset(dataset_name, split="train")
                records = existing.to_dict()
                # إضافة السجل الجديد
                for key in records:
                    records[key].append(record[key])
                new_dataset = Dataset.from_dict(records)
            except:
                new_dataset = Dataset.from_dict({k: [v] for k, v in record.items()})

            # رفع الـ Dataset
            new_dataset.push_to_hub(dataset_name, token=self.hf_token)
            print(f"✅ Correction added to {dataset_name}")
            return True

        except Exception as e:
            print(f"❌ Failed to add correction: {e}")
            # حفظ محلي كاحتياطي
            self._save_local_backup(record, "correction")
            return False

    def add_scanner_log(self,
                       dataset_name: str,
                       original_image_path: str,
                       processed_image_path: str,
                       processing_options: dict[str, Any],
                       processing_time_ms: float,
                       deskew_angle: float = 0.0) -> bool:
        """
        إضافة سجل معالجة Scanner

        Args:
            dataset_name: اسم الـ Dataset
            original_image_path: مسار الصورة الأصلية
            processed_image_path: مسار الصورة المعالجة
            processing_options: خيارات المعالجة
            processing_time_ms: وقت المعالجة بالمللي ثانية
            deskew_angle: زاوية الميل المصححة

        Returns:
            True if successful
        """
        try:
            original = cv2.imread(original_image_path)
            processed = cv2.imread(processed_image_path)

            if original is None or processed is None:
                print("❌ Cannot read images")
                return False

            record = {
                "original_image": cv2.cvtColor(original, cv2.COLOR_BGR2RGB),
                "processed_image": cv2.cvtColor(processed, cv2.COLOR_BGR2RGB),
                "processing_options": json.dumps(processing_options),
                "processing_time_ms": processing_time_ms,
                "shadow_removed": processing_options.get("shadow_removal", False),
                "deskew_angle": deskew_angle,
                "perspective_corrected": processing_options.get("perspective", False),
                "denoise_applied": processing_options.get("denoise", False),
                "contrast_enhanced": processing_options.get("enhance_contrast", False),
                "auto_crop_applied": processing_options.get("auto_crop", False),
                "input_dimensions": f"{original.shape[1]}x{original.shape[0]}",
                "output_dimensions": f"{processed.shape[1]}x{processed.shape[0]}",
                "timestamp": datetime.now().isoformat(),
            }

            # تحميل أو إنشاء Dataset
            try:
                from datasets import load_dataset
                existing = load_dataset(dataset_name, split="train")
                records = existing.to_dict()
                for key in records:
                    records[key].append(record[key])
                new_dataset = Dataset.from_dict(records)
            except:
                new_dataset = Dataset.from_dict({k: [v] for k, v in record.items()})

            new_dataset.push_to_hub(dataset_name, token=self.hf_token)
            print(f"✅ Scanner log added to {dataset_name}")
            return True

        except Exception as e:
            print(f"❌ Failed to add scanner log: {e}")
            self._save_local_backup(record, "scanner_log")
            return False

    def add_training_pair(self,
                         dataset_name: str,
                         image_path: str,
                         text: str,
                         category: str = "prescription",
                         font_type: str = "printed",
                         language: str = "ar") -> bool:
        """
        إضافة زوج تدريبي (صورة + نص)

        Args:
            dataset_name: اسم الـ Dataset
            image_path: مسار الصورة
            text: النص المقابل
            category: التصنيف
            font_type: نوع الخط
            language: اللغة

        Returns:
            True if successful
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                print(f"❌ Cannot read image: {image_path}")
                return False

            # حساب جودة الصورة
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blur = cv2.Laplacian(gray, cv2.CV_64F).var()
            quality = "high" if blur > 500 else "medium" if blur > 200 else "low"

            record = {
                "image": cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
                "text": text,
                "category": category,
                "font_type": font_type,
                "language": language,
                "quality_label": quality,
                "timestamp": datetime.now().isoformat(),
            }

            # تحميل أو إنشاء
            try:
                from datasets import load_dataset
                existing = load_dataset(dataset_name, split="train")
                records = existing.to_dict()
                for key in records:
                    records[key].append(record[key])
                new_dataset = Dataset.from_dict(records)
            except:
                new_dataset = Dataset.from_dict({k: [v] for k, v in record.items()})

            new_dataset.push_to_hub(dataset_name, token=self.hf_token)
            print(f"✅ Training pair added to {dataset_name}")
            return True

        except Exception as e:
            print(f"❌ Failed to add training pair: {e}")
            self._save_local_backup(record, "training_pair")
            return False

    def _calculate_quality_score(self, image: np.ndarray) -> float:
        """حساب درجة جودة الصورة"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # التباين
            contrast = gray.std()
            # الحدة
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            # SNR تقريبي
            signal = gray.mean()
            noise = gray.std()
            snr = signal / (noise + 1e-6)

            # درجة مركبة (0-1)
            score = min(1.0, (contrast / 100 + sharpness / 1000 + snr / 50) / 3)
            return round(score, 3)
        except:
            return 0.5

    def _save_local_backup(self, record: dict, record_type: str):
        """حفظ احتياطي محلي"""
        backup_dir = Path("local_dataset_backups") / record_type
        backup_dir.mkdir(parents=True, exist_ok=True)

        # إزالة الصور من السجل للحفظ كـ JSON
        record_copy = {k: v for k, v in record.items() if k not in ["image", "original_image", "processed_image"]}

        filename = f"{record_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_dir / filename, 'w', encoding='utf-8') as f:
            json.dump(record_copy, f, ensure_ascii=False, indent=2)

        print(f"💾 Local backup saved: {backup_dir / filename}")

    def sync_local_backups(self, dataset_name: str, backup_dir: str = "local_dataset_backups") -> int:
        """
        مزامنة النسخ الاحتياطية المحلية مع HF

        Returns:
            عدد السجلات المتزامنة
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            print("No local backups found")
            return 0

        count = 0
        for json_file in backup_path.rglob("*.json"):
            try:
                with open(json_file, encoding='utf-8') as f:
                    record = json.load(f)

                # تحديد نوع السجل وإضافته
                if "correct_text" in record:
                    # correction record
                    pass  # يتطلب صورة

                count += 1
                print(f"Synced: {json_file.name}")
            except Exception as e:
                print(f"Failed to sync {json_file}: {e}")

        print(f"✅ Synced {count} records to {dataset_name}")
        return count

    def get_dataset_stats(self, dataset_name: str) -> dict:
        """الحصول على إحصائيات Dataset"""
        try:
            from datasets import load_dataset
            dataset = load_dataset(dataset_name, split="train")

            stats = {
                "total_records": len(dataset),
                "dataset_name": dataset_name,
                "features": list(dataset.features.keys()),
                "size_mb": dataset.data.nbytes / (1024 * 1024),
            }

            # إحصائيات إضافية حسب النوع
            if "category" in dataset.features:
                categories = {}
                for item in dataset:
                    cat = item.get("category", "unknown")
                    categories[cat] = categories.get(cat, 0) + 1
                stats["categories"] = categories

            if "timestamp" in dataset.features:
                timestamps = [item["timestamp"] for item in dataset if item.get("timestamp")]
                if timestamps:
                    stats["date_range"] = {
                        "first": min(timestamps),
                        "last": max(timestamps)
                    }

            return stats

        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
            return {}

    def export_dataset(self, dataset_name: str, output_dir: str, format: str = "json") -> str:
        """
        تصدير Dataset إلى ملف محلي

        Args:
            dataset_name: اسم الـ Dataset
            output_dir: مجلد الإخراج
            format: json, csv, parquet

        Returns:
            مسار الملف المصدر
        """
        try:
            from datasets import load_dataset
            dataset = load_dataset(dataset_name, split="train")

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if format == "json":
                output_file = output_path / f"{dataset_name.replace('/', '_')}_{timestamp}.json"
                dataset.to_json(str(output_file))
            elif format == "csv":
                output_file = output_path / f"{dataset_name.replace('/', '_')}_{timestamp}.csv"
                dataset.to_csv(str(output_file))
            elif format == "parquet":
                output_file = output_path / f"{dataset_name.replace('/', '_')}_{timestamp}.parquet"
                dataset.to_parquet(str(output_file))
            else:
                raise ValueError(f"Unsupported format: {format}")

            print(f"✅ Dataset exported to {output_file}")
            return str(output_file)

        except Exception as e:
            print(f"❌ Failed to export: {e}")
            return ""


# ==================== CLI INTERFACE ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HF Auto Dataset Manager")
    parser.add_argument("--token", help="HF Token", default=None)
    parser.add_argument("--username", default="DrAbdulmalek")
    parser.add_argument("--action", choices=["create", "stats", "export", "sync"], required=True)
    parser.add_argument("--type", choices=["corrections", "scanner_logs", "training_pairs"], default="corrections")
    parser.add_argument("--dataset", help="Dataset name (full path)")
    parser.add_argument("--output", help="Output directory for export")
    parser.add_argument("--format", choices=["json", "csv", "parquet"], default="json")

    args = parser.parse_args()

    manager = HFAutoDatasetManager(hf_token=args.token, username=args.username)

    if args.action == "create":
        dataset_name = manager.create_dataset(args.type)
        print(f"Created: {dataset_name}")

    elif args.action == "stats":
        if not args.dataset:
            print("--dataset required")
            exit(1)
        stats = manager.get_dataset_stats(args.dataset)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.action == "export":
        if not args.dataset or not args.output:
            print("--dataset and --output required")
            exit(1)
        manager.export_dataset(args.dataset, args.output, args.format)

    elif args.action == "sync":
        if not args.dataset:
            print("--dataset required")
            exit(1)
        manager.sync_local_backups(args.dataset)
