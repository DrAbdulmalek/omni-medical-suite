#!/usr/bin/env python3
# packages/core/api_server_v3.py
# نسخة محدثة تدعم Mistral AI OCR + Classification + Extraction + FHIR

import os
import sys
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_processor import (
    smart_auto_crop,
    auto_detect_skew,
    apply_deskew,
    remove_gray_borders,
    detect_blur_laplacian
)
from encryption import MedicalDocEncryption
from db_manager import MedicalDB
from mistral_integration import MistralIntegration, convert_to_fhir

app = FastAPI(title="Medical Doc Core API v3.2", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "app://.*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== التكامل مع Mistral ======
mistral = MistralIntegration()

# ====== نماذج البيانات ======
class ProcessRequest(BaseModel):
    auto_crop: bool = True
    deskew: bool = True
    remove_borders: bool = True
    blur_threshold: float = 100.0
    output_format: str = "png"
    encrypt: bool = False
    patient_id: Optional[str] = None
    use_mistral: bool = True  # هل نستخدم Mistral AI؟
    mistral_structured: bool = True  # هل نستخرج بيانات منظمة؟

class DBInitRequest(BaseModel):
    db_path: str
    encryption_password: str

class DocumentInsertRequest(BaseModel):
    db_path: str
    encryption_password: str
    filename: str
    original_path: str
    processed_path: Optional[str] = None
    blur_before: Optional[float] = None
    blur_after: Optional[float] = None
    skew_angle: Optional[float] = None
    patient_id: Optional[str] = None

# ====== نقاط النهاية الأساسية ======

@app.post("/process")
async def process_image(
    file: UploadFile = File(...),
    options: str = Form('{}')
):
    """معالجة صورة واحدة (محلي + اختياري Mistral)"""
    opts = ProcessRequest(**json.loads(options))

    suffix = f".{file.filename.split('.')[-1]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    try:
        img = cv2.imread(input_path)
        if img is None:
            raise HTTPException(400, "تعذر قراءة الصورة")

        original = img.copy()
        blur_before = detect_blur_laplacian(original)

        if opts.remove_borders:
            img = remove_gray_borders(img)

        skew_angle = None
        if opts.deskew:
            skew_angle = auto_detect_skew(img)
            if abs(skew_angle) > 0.3:
                img = apply_deskew(img, skew_angle)

        if opts.auto_crop:
            img = smart_auto_crop(img)

        blur_after = detect_blur_laplacian(img)

        out_suffix = f".{opts.output_format}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=out_suffix) as out_tmp:
            output_path = out_tmp.name

        if opts.output_format.lower() in ["jpg", "jpeg"]:
            cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            cv2.imwrite(output_path, img)

        # تشفير
        encrypted_path = None
        if opts.encrypt:
            enc_pass = json.loads(options).get('encryption_password', 'default_medical_pass')
            encrypted_path = output_path + ".enc"
            MedicalDocEncryption.encrypt_file(output_path, encrypted_path, enc_pass)

        # base64
        import base64
        output_b64 = None
        if os.path.getsize(output_path) < 2 * 1024 * 1024:
            with open(output_path, "rb") as f:
                output_b64 = base64.b64encode(f.read()).decode()

        # ====== Mistral Integration (اختياري) ======
        mistral_result = None
        if opts.use_mistral and mistral.is_available():
            try:
                mistral_result = mistral.process_document(
                    file_path=input_path,
                    use_mistral=True,
                    include_structured=opts.mistral_structured
                )
            except Exception as e:
                mistral_result = {"error": str(e)}

        return {
            "success": True,
            "message": "تمت المعالجة بنجاح",
            "blur_before": round(blur_before, 2),
            "blur_after": round(blur_after, 2),
            "skew_angle": round(skew_angle, 2) if skew_angle else 0.0,
            "output_path": output_path,
            "encrypted_path": encrypted_path,
            "output_base64": output_b64,
            "mistral": mistral_result  # بيانات Mistral إذا كانت متوفرة
        }

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


@app.post("/batch")
async def batch_process(files: List[UploadFile] = File(...)):
    """معالجة دفعة"""
    results = []
    for file in files:
        result = await process_image(file, '{}')
        results.append(result)
    return {"results": results}


# ====== نقاط نهاية Mistral المخصصة ======

@app.post("/mistral/ocr")
async def mistral_ocr(file: UploadFile = File(...)):
    """OCR فقط باستخدام Mistral"""
    if not mistral.is_available():
        return {"error": "Mistral not available. Set MISTRAL_API_KEY."}

    suffix = f".{file.filename.split('.')[-1]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    try:
        result = mistral.engine.process_document(input_path)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        os.remove(input_path)


@app.post("/mistral/classify")
async def mistral_classify(file: UploadFile = File(...)):
    """تصنيف المستند باستخدام Mistral"""
    if not mistral.is_available():
        return {"error": "Mistral not available"}

    suffix = f".{file.filename.split('.')[-1]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    try:
        result = mistral.engine.classify_document(input_path)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        os.remove(input_path)


@app.post("/mistral/extract")
async def mistral_extract(
    file: UploadFile = File(...),
    doc_type: str = Form(...)
):
    """استخراج منظم حسب نوع المستند"""
    if not mistral.is_available():
        return {"error": "Mistral not available"}

    from document_schemas import EXTRACTION_SCHEMAS
    if doc_type not in EXTRACTION_SCHEMAS:
        return {"error": f"Unknown doc_type. Available: {list(EXTRACTION_SCHEMAS.keys())}"}

    suffix = f".{file.filename.split('.')[-1]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    try:
        result = mistral.engine.extract_by_type(input_path, doc_type)

        # تحويل إلى FHIR تلقائياً
        fhir_bundle = None
        if result and result.get("annotation"):
            try:
                fhir_bundle = convert_to_fhir(doc_type, result["annotation"])
            except Exception as e:
                pass

        return {
            "success": True,
            "extraction": result,
            "fhir_bundle": fhir_bundle
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        os.remove(input_path)


@app.post("/mistral/batch")
async def mistral_batch(files: List[UploadFile] = File(...)):
    """معالجة دفعة باستخدام Mistral"""
    if not mistral.is_available():
        return {"error": "Mistral not available"}

    paths = []
    for file in files:
        suffix = f".{file.filename.split('.')[-1]}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            paths.append(tmp.name)

    try:
        results = mistral.engine.batch_process(paths)
        return {"success": True, "results": results}
    finally:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)


# ====== نقاط نهاية قاعدة البيانات (كما هي) ======

@app.post("/db/init")
async def db_init(req: DBInitRequest):
    try:
        db = MedicalDB(req.db_path, req.encryption_password)
        db.close()
        return {"success": True, "db_path": req.db_path}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/db/documents")
async def db_insert_doc(req: DocumentInsertRequest):
    try:
        db = MedicalDB(req.db_path, req.encryption_password)
        doc_id = db.insert_document(
            filename=req.filename,
            original_path=req.original_path,
            processed_path=req.processed_path,
            blur_before=req.blur_before,
            blur_after=req.blur_after,
            skew_angle=req.skew_angle,
            patient_id=req.patient_id
        )
        db.close()
        return {"success": True, "id": doc_id}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/db/documents")
async def db_list_docs(db_path: str, patient_id: Optional[str] = None, limit: int = 50):
    try:
        db = MedicalDB(db_path)
        docs = db.list_documents(patient_id, limit)
        db.close()
        return {"success": True, "documents": docs}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "opencv_version": cv2.__version__,
        "mistral_available": mistral.is_available(),
        "features": [
            "deskew", "blur_detection", "encryption", "sqlite_wal",
            "mistral_ocr", "document_classification", "structured_extraction", "fhir"
        ]
    }


def start_server(port: int = 0):
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    start_server(args.port)
