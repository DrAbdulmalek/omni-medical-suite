#!/usr/bin/env python3
# packages/core/mistral_ocr_engine.py
# محرك OCR باستخدام Mistral OCR 3 API
# يدعم: PDF, PNG, JPEG, TIFF + HTML tables + image annotations

import os
import base64
import json
import time
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import tempfile

# يفترض تثبيت: pip install mistralai
from mistralai import Mistral
from mistralai.models import OCRResponse


class MistralOCREngine:
    """
    محرك OCR متقدم باستخدام Mistral AI
    - يدعم PDF متعدد الصفحات
    - يستخرج الجداول بصيغة HTML
    - يستخرج الصور المضمنة بـ base64
    - يدعم Document Annotations للاستخراج المنظم
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY required. Set env var or pass api_key.")

        self.client = Mistral(api_key=self.api_key)
        self.model = "mistral-ocr-latest"

    def _encode_file(self, file_path: str) -> str:
        """ترميز ملف إلى base64"""
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def process_document(
        self,
        file_path: str,
        pages: Optional[List[int]] = None,
        include_images: bool = True,
        table_format: str = "html"
    ) -> Dict[str, Any]:
        """
        معالجة مستند (PDF أو صورة) وإرجاع OCR + جداول + صور

        Args:
            file_path: مسار الملف
            pages: قائمة بأرقام الصفحات (None = الكل)
            include_images: تضمين الصور المضمنة
            table_format: "html" أو "markdown"

        Returns:
            dict يحتوي pages, tables, images, raw_markdown
        """
        base64_data = self._encode_file(file_path)

        # تحديد نوع الملف
        ext = Path(file_path).suffix.lower()
        mime_type = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"

        kwargs = {
            "model": self.model,
            "document": {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{base64_data}"
            },
            "include_image_base64": include_images,
            "table_format": table_format,
        }

        if pages is not None:
            kwargs["pages"] = pages

        response = self.client.ocr.process(**kwargs)

        # تحويل إلى dict
        result = json.loads(response.model_dump_json())

        # تسهيل الوصول
        output = {
            "num_pages": len(result.get("pages", [])),
            "pages": [],
            "all_markdown": "",
            "tables": [],
            "images": [],
        }

        for i, page in enumerate(result.get("pages", [])):
            page_data = {
                "index": page.get("index", i),
                "markdown": page.get("markdown", ""),
                "tables": page.get("tables", []),
                "images": []
            }

            # استخراج الصور من الصفحة
            if include_images and i < len(response.pages):
                for img in response.pages[i].images:
                    page_data["images"].append({
                        "id": img.id,
                        "base64": img.image_base64,
                        "mime_type": "image/png"  # افتراضي
                    })
                    output["images"].append({
                        "page": i,
                        "id": img.id,
                        "base64": img.image_base64
                    })

            # استخراج الجداول
            for tbl in page.get("tables", []):
                output["tables"].append({
                    "page": i,
                    "id": tbl.get("id"),
                    "content": tbl.get("content"),  # HTML
                    "rows": tbl.get("rows"),
                    "columns": tbl.get("columns")
                })

            output["pages"].append(page_data)
            output["all_markdown"] += f"\n\n--- Page {i+1} ---\n\n" + page_data["markdown"]

        return output

    def process_with_annotation(
        self,
        file_path: str,
        response_format: Any,  # Pydantic model class
        pages: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        معالجة مع استخراج منظم (Document Annotation)
        يستخدم Pydantic model لتوجيه الاستخراج
        """
        from mistralai.models import response_format_from_pydantic_model

        base64_data = self._encode_file(file_path)
        ext = Path(file_path).suffix.lower()
        mime_type = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"

        kwargs = {
            "model": self.model,
            "document": {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{base64_data}"
            },
            "document_annotation_format": response_format_from_pydantic_model(response_format),
            "include_image_base64": False,
        }

        if pages is not None:
            kwargs["pages"] = pages  # max 8 pages for annotations

        response = self.client.ocr.process(**kwargs)

        # الاستخراج المنظم
        annotation = json.loads(response.document_annotation)

        return {
            "annotation": annotation,
            "raw_markdown": "".join([p.markdown for p in response.pages]) if response.pages else "",
            "num_pages": len(response.pages) if response.pages else 0,
        }

    def classify_document(self, file_path: str) -> Dict[str, Any]:
        """
        تصنيف المستند تلقائياً
        """
        from document_schemas import DocumentClassification
        return self.process_with_annotation(file_path, DocumentClassification, pages=[0])

    def extract_by_type(self, file_path: str, doc_type: str) -> Optional[Dict[str, Any]]:
        """
        استخراج بيانات حسب نوع المستند
        """
        from document_schemas import EXTRACTION_SCHEMAS

        schema = EXTRACTION_SCHEMAS.get(doc_type)
        if not schema:
            return None

        return self.process_with_annotation(file_path, schema)

    def batch_process(
        self,
        file_paths: List[str],
        rate_limit_delay: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        معالجة دفعة من المستندات مع rate limiting
        """
        results = []
        for path in file_paths:
            try:
                time.sleep(rate_limit_delay)
                result = self.process_document(path)
                result["file_path"] = path
                result["status"] = "success"
                results.append(result)
            except Exception as e:
                results.append({
                    "file_path": path,
                    "status": "error",
                    "error": str(e)
                })
        return results
