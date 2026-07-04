# hf_connector.py
"""
HF Connector - ربط تطبيق سطح المكتب مع Hugging Face Space
يدعم:
- رفع الصور إلى HF Space للمعالجة
- استدعاء API من تطبيق سطح المكتب
- جمع التصحيحات ودفعها إلى Dataset
- Batch processing عبر HF
"""

import os
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import tempfile
import json

# For HF API calls
try:
    from gradio_client import Client, handle_file
except ImportError:
    Client = None
    handle_file = None

try:
    from huggingface_hub import HfApi, create_repo, upload_file, dataset_upload
except ImportError:
    HfApi = None


class HFConnector:
    """موصل Hugging Face للتطبيق المحلي"""

    def __init__(self, 
                 space_name: str = "DrAbdulmalek/medical-ocr-demo",
                 dataset_name: str = "DrAbdulmalek/arabic-medical-ocr-corrections",
                 hf_token: Optional[str] = None):
        """
        تهيئة الموصل

        Args:
            space_name: اسم HF Space (مثال: "username/space-name")
            dataset_name: اسم Dataset للتصحيحات
            hf_token: توكن Hugging Face (اختياري للمساحات العامة)
        """
        self.space_name = space_name
        self.dataset_name = dataset_name
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.client = None
        self.api = None

        if self.hf_token and HfApi:
            self.api = HfApi(token=self.hf_token)

    def connect_to_space(self) -> bool:
        """الاتصال بـ HF Space"""
        if Client is None:
            print("❌ gradio_client not installed. Run: pip install gradio-client")
            return False

        try:
            self.client = Client(
                self.space_name,
                hf_token=self.hf_token,
                verbose=False
            )
            print(f"✅ Connected to {self.space_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    def view_api(self):
        """عرض نقاط API المتاحة"""
        if not self.client:
            print("❌ Not connected. Call connect_to_space() first.")
            return
        self.client.view_api()

    def process_image_via_hf(self, image_path: str, mode: str = "standard") -> Dict:
        """
        معالجة صورة عبر HF Space

        Args:
            image_path: مسار الصورة المحلية
            mode: "standard" أو "handwriting"

        Returns:
            dict مع النتائج: {cleaned_image, raw_text, corrected_text, entities, status}
        """
        if not self.client:
            if not self.connect_to_space():
                return {"error": "Failed to connect to HF Space"}

        try:
            # رفع الصورة واستدعاء API
            result = self.client.predict(
                image=handle_file(image_path),
                mode=mode,
                api_name="/predict"
            )

            # النتيجة تعتمد على تعريف Gradio app
            # افتراضياً: (cleaned_image, corrected_text, raw_text, entities, status)
            return {
                "cleaned_image": result[0] if len(result) > 0 else None,
                "corrected_text": result[1] if len(result) > 1 else "",
                "raw_text": result[2] if len(result) > 2 else "",
                "entities": result[3] if len(result) > 3 else {},
                "status": result[4] if len(result) > 4 else "done",
                "success": True
            }
        except Exception as e:
            return {"error": str(e), "success": False}

    def send_correction_to_hf(self, 
                             image_path: str, 
                             raw_text: str, 
                             corrected_text: str,
                             category: str = "prescription") -> bool:
        """
        إرسال تصحيح إلى HF Dataset

        Args:
            image_path: مسار الصورة
            raw_text: النص الأصلي من OCR
            corrected_text: النص المصحح
            category: نوع المستند

        Returns:
            True if successful
        """
        if not self.hf_token:
            print("❌ HF_TOKEN required for dataset uploads")
            return False

        try:
            from datasets import Dataset
            import pandas as pd

            # إنشاء سجل
            record = {
                "image_path": str(image_path),
                "incorrect_ocr_output": raw_text,
                "correct_text": corrected_text,
                "category": category,
                "timestamp": datetime.now().isoformat()
            }

            # حفظ محلي مؤقت
            temp_dir = Path(tempfile.gettempdir()) / "hf_corrections"
            temp_dir.mkdir(exist_ok=True)

            csv_path = temp_dir / f"correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df = pd.DataFrame([record])
            df.to_csv(csv_path, index=False)

            # دفع إلى HF (يتطلب datasets library)
            try:
                from datasets import load_dataset
                existing = load_dataset(self.dataset_name, split="train")
                combined = pd.concat([existing.to_pandas(), df], ignore_index=True)
            except:
                combined = df

            dataset = Dataset.from_pandas(combined)
            dataset.push_to_hub(self.dataset_name, token=self.hf_token)

            print(f"✅ Correction saved to {self.dataset_name}")
            return True

        except Exception as e:
            print(f"❌ Failed to upload correction: {e}")
            # حفظ محلي كاحتياطي
            self._save_local_backup(record)
            return False

    def _save_local_backup(self, record: dict):
        """حفظ احتياطي محلي"""
        backup_dir = Path("local_corrections_backup")
        backup_dir.mkdir(exist_ok=True)

        with open(backup_dir / f"correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                  'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        print(f"💾 Local backup saved to {backup_dir}")

    def batch_process_via_hf(self, 
                            image_folder: str, 
                            output_folder: str,
                            mode: str = "standard") -> List[Dict]:
        """
        معالجة مجلد كامل عبر HF Space

        Args:
            image_folder: مجلد الصور
            output_folder: مجلد النتائج
            mode: وضع المعالجة

        Returns:
            قائمة بالنتائج
        """
        if not self.client:
            if not self.connect_to_space():
                return []

        image_files = list(Path(image_folder).glob("*.jpg")) +                      list(Path(image_folder).glob("*.png")) +                      list(Path(image_folder).glob("*.jpeg"))

        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)

        results = []
        for i, img_file in enumerate(image_files):
            print(f"Processing {i+1}/{len(image_files)}: {img_file.name}")

            result = self.process_image_via_hf(str(img_file), mode)

            if result.get("success"):
                # حفظ الصورة المحسنة
                if result.get("cleaned_image"):
                    cleaned = cv2.imread(result["cleaned_image"])
                    if cleaned is not None:
                        cv2.imwrite(str(output_path / f"fixed_{img_file.name}"), cleaned)

                # حفظ النص
                with open(output_path / f"{img_file.stem}_text.txt", 'w', encoding='utf-8') as f:
                    f.write(result.get("corrected_text", ""))

                results.append({
                    "file": img_file.name,
                    "status": "success",
                    "text": result.get("corrected_text", "")
                })
            else:
                results.append({
                    "file": img_file.name,
                    "status": "failed",
                    "error": result.get("error", "Unknown")
                })

        # حفظ ملخص
        with open(output_path / "batch_summary.json", 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"✅ Batch complete: {len(results)} files processed")
        return results

    def sync_local_to_hf(self, local_dataset_path: str):
        """مزامنة Dataset محلي مع HF"""
        if not self.hf_token:
            print("❌ HF_TOKEN required")
            return False

        try:
            from datasets import Dataset, load_dataset
            import pandas as pd

            # قراءة البيانات المحلية
            df = pd.read_csv(local_dataset_path)
            dataset = Dataset.from_pandas(df)

            # دفع إلى HF
            dataset.push_to_hub(self.dataset_name, token=self.hf_token)
            print(f"✅ Synced {len(df)} records to {self.dataset_name}")
            return True
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            return False


# ==================== INTEGRATION WITH DESKTOP APP ====================

class DesktopHFIntegration:
    """تكامل بين تطبيق سطح المكتب و HF"""

    def __init__(self, connector: HFConnector):
        self.connector = connector
        self.local_preprocessor = None

        try:
            from desktop_scanner_fixer_pro import AdvancedScannerFixer
            self.local_preprocessor = AdvancedScannerFixer()
        except ImportError:
            pass

    def hybrid_process(self, image_path: str, use_hf: bool = True) -> Dict:
        """
        معالجة هجينة: محلية أولاً ثم HF

        Args:
            image_path: مسار الصورة
            use_hf: استخدام HF للمعالجة الثانوية

        Returns:
            نتائج المعالجة
        """
        # المعالجة المحلية أولاً
        if self.local_preprocessor:
            img = cv2.imread(image_path)
            cleaned_local = self.local_preprocessor.process(img)

            # حفظ مؤقت
            temp_path = Path(tempfile.gettempdir()) / "temp_cleaned.jpg"
            cv2.imwrite(str(temp_path), cleaned_local)

            if use_hf and self.connector.client:
                # إرسال إلى HF للـ OCR
                return self.connector.process_image_via_hf(str(temp_path))
            else:
                return {
                    "cleaned_image": str(temp_path),
                    "status": "local_only",
                    "success": True
                }
        else:
            # مباشرة إلى HF
            if use_hf:
                return self.connector.process_image_via_hf(image_path)
            else:
                return {"error": "No preprocessor available"}

    def auto_upload_corrections(self, corrections_folder: str):
        """رفع تصحيحات محلية تلقائياً"""
        folder = Path(corrections_folder)
        if not folder.exists():
            print(f"❌ Folder not found: {corrections_folder}")
            return

        json_files = list(folder.glob("*.json"))
        for jf in json_files:
            with open(jf, 'r', encoding='utf-8') as f:
                record = json.load(f)

            self.connector.send_correction_to_hf(
                image_path=record.get("image_path", ""),
                raw_text=record.get("incorrect_ocr_output", ""),
                corrected_text=record.get("correct_text", ""),
                category=record.get("category", "prescription")
            )


# ==================== CLI INTERFACE ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HF Connector for Scanner Fixer Pro")
    parser.add_argument("--space", default="DrAbdulmalek/medical-ocr-demo", help="HF Space name")
    parser.add_argument("--token", default=None, help="HF Token")
    parser.add_argument("--image", help="Image path to process")
    parser.add_argument("--batch", help="Batch process folder")
    parser.add_argument("--mode", default="standard", choices=["standard", "handwriting"])
    parser.add_argument("--view-api", action="store_true", help="View API endpoints")

    args = parser.parse_args()

    connector = HFConnector(
        space_name=args.space,
        hf_token=args.token
    )

    if args.view_api:
        connector.connect_to_space()
        connector.view_api()

    elif args.image:
        result = connector.process_image_via_hf(args.image, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.batch:
        results = connector.batch_process_via_hf(args.batch, f"{args.batch}/hf_output", args.mode)
        print(f"Processed {len(results)} images")

    else:
        print("Use --image, --batch, or --view-api")
