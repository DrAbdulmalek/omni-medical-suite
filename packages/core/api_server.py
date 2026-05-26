"""
FastAPI Server for Medical Document Processing.
Integrates: Image Processing, Encryption, SQLite DB, Mistral AI.
"""

import os
import sys
import json
import shutil
import tempfile
import logging
import argparse
from typing import Optional
from datetime import datetime

# Add packages/core to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from image_processor import (
    find_page_bounds, auto_detect_skew, smart_auto_crop,
    remove_shadow, detect_blur_laplacian, assess_image_quality,
    apply_processing, extract_page_number, image_segmentation,
    sharpen_image
)
from encryption import MedicalDocEncryption
from db_manager import DatabaseManager
from mistral_integration import MistralIntegration

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---- App Factory ----

def create_app(db_path: str = "medical_docs.db") -> "FastAPI":
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")

    app = FastAPI(
        title="Medical Document Processor API",
        description="معالج المستندات الطبية - API Server v3.2",
        version="3.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize components
    db = DatabaseManager(db_path=db_path)
    mistral = MistralIntegration()
    upload_dir = os.path.join(tempfile.gettempdir(), "medical_docs", "uploads")
    processed_dir = os.path.join(tempfile.gettempdir(), "medical_docs", "processed")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Startup event
    @app.on_event("startup")
    async def startup():
        db.initialize()
        logger.info("Medical Document Processor API started")

    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown():
        db.close()

    # ---- Health Check ----
    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "version": "3.2.0",
            "mistral_available": mistral.is_available(),
            "db_path": db.db_path,
        }

    # ---- Image Processing ----
    @app.post("/process")
    async def process_image(
        file: UploadFile = File(...),
        options: str = Form("{}"),
    ):
        """Process a single image with full pipeline."""
        import cv2
        import numpy as np

        opts = json.loads(options) if isinstance(options, str) else options
        start_time = datetime.now()

        # Save uploaded file
        input_path = os.path.join(upload_dir, file.filename or "upload.png")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            # Read image
            image = cv2.imread(input_path)
            if image is None:
                raise HTTPException(400, "Could not read image file")

            # Get metrics before processing
            quality_before = assess_image_quality(image)
            blur_before = quality_before["blur_score"]

            # Auto deskew
            deskew_angle = 0.0
            if opts.get("deskew", True):
                deskew_angle = auto_detect_skew(image)

            # Apply processing pipeline
            result = apply_processing(
                img=image,
                rotation=opts.get("rotation", 0),
                deskew_angle=deskew_angle,
                flip_h=opts.get("flip_h", False),
                sharpen=opts.get("sharpen", False),
                remove_shadow_flag=opts.get("remove_shadow", False),
                gray_threshold=opts.get("gray_threshold", 230),
            )

            processed_image = result["image"]
            quality_after = result["quality"]

            # Save processed image
            base_name = os.path.splitext(file.filename or "upload")[0]
            output_filename = f"{base_name}_processed.png"
            output_path = os.path.join(processed_dir, output_filename)
            cv2.imwrite(output_path, processed_image)

            # Extract page number
            page_number = ""
            if opts.get("extract_page_number", False):
                page_number = extract_page_number(processed_image)

            # Save to database
            doc_id = db.add_document(
                filename=file.filename or "upload.png",
                original_path=input_path,
                processed_path=output_path,
                document_type="unknown",
                status="processed",
                blur_before=result["blur_before"],
                blur_after=result["blur_after"],
                skew_angle=deskew_angle,
                quality_label=quality_after["label"],
            )

            # Add processing log
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            db.add_log(doc_id, "process", json.dumps(result["operations"]), quality_after["label"], duration)

            # Encode processed image as base64 for response
            _, buffer = cv2.imencode('.png', processed_image)
            import base64
            output_b64 = base64.b64encode(buffer).decode('utf-8')

            return {
                "success": True,
                "document_id": doc_id,
                "blur_before": result["blur_before"],
                "blur_after": result["blur_after"],
                "skew_angle": deskew_angle,
                "quality": quality_after,
                "page_number": page_number,
                "operations": result["operations"],
                "output_base64": output_b64,
                "output_path": output_path,
                "duration_ms": duration,
            }

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise HTTPException(500, str(e))

    # ---- Word Segmentation ----
    @app.post("/segment-words")
    async def segment_words(file: UploadFile = File(...)):
        """Segment handwritten text into individual word images."""
        import cv2

        input_path = os.path.join(upload_dir, file.filename or "upload.png")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        image = cv2.imread(input_path)
        if image is None:
            raise HTTPException(400, "Could not read image")

        words = image_segmentation(image)
        word_results = []

        for i, word in enumerate(words):
            import base64
            _, buffer = cv2.imencode('.png', word["image"])
            b64 = base64.b64encode(buffer).decode('utf-8')

            word_results.append({
                "index": i,
                "bbox": word["bbox"],
                "area": word["area"],
                "image_base64": b64,
            })

        return {"words": word_results, "total": len(word_results)}

    # ---- Mistral OCR ----
    @app.post("/mistral/ocr")
    async def mistral_ocr(file: UploadFile = File(...)):
        """Run Mistral OCR 3 on a document."""
        if not mistral.is_available():
            raise HTTPException(503, "Mistral API not configured. Set MISTRAL_API_KEY.")

        input_path = os.path.join(upload_dir, file.filename or "upload.pdf")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        result = mistral.ocr.ocr_document(input_path)
        if result.get("error"):
            raise HTTPException(500, result["error"])

        return result

    # ---- Mistral Classification ----
    @app.post("/mistral/classify")
    async def mistral_classify(
        file: UploadFile = File(...),
        ocr_text: Optional[str] = Form(None),
    ):
        """Classify a medical document."""
        if not mistral.is_available():
            raise HTTPException(503, "Mistral API not configured.")

        text = ocr_text or ""
        if not text:
            input_path = os.path.join(upload_dir, file.filename or "upload.pdf")
            with open(input_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            ocr_result = mistral.ocr.ocr_document(input_path)
            if ocr_result.get("pages"):
                text = "\n".join(p.get("markdown", "") for p in ocr_result["pages"])

        if not text:
            raise HTTPException(400, "No text available for classification")

        result = mistral.classifier.classify_text(text)
        if result.get("error"):
            raise HTTPException(500, result["error"])

        return result

    # ---- Mistral Extract + FHIR ----
    @app.post("/mistral/extract")
    async def mistral_extract(
        file: UploadFile = File(...),
        doc_type: str = Form("unknown"),
        patient_id: str = Form("unknown"),
    ):
        """Extract structured data and generate FHIR."""
        if not mistral.is_available():
            raise HTTPException(503, "Mistral API not configured.")

        input_path = os.path.join(upload_dir, file.filename or "upload.pdf")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        result = mistral.process_document(input_path, patient_id, generate_fhir=True)
        if result.get("error"):
            raise HTTPException(500, result["error"])

        return result

    # ---- Encryption ----
    @app.post("/encrypt")
    async def encrypt_document(
        file: UploadFile = File(...),
        password: str = Form(...),
    ):
        """Encrypt a file with AES-256-GCM."""
        input_path = os.path.join(upload_dir, file.filename or "document.pdf")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        output_path = input_path + ".enc"
        metadata = MedicalDocEncryption.encrypt_file(input_path, output_path, password)

        return {
            "success": True,
            "encrypted_path": output_path,
            "metadata": metadata,
        }

    @app.post("/decrypt")
    async def decrypt_document(
        file: UploadFile = File(...),
        password: str = Form(...),
    ):
        """Decrypt a file."""
        input_path = os.path.join(upload_dir, file.filename or "document.enc")
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        output_path = input_path.replace(".enc", ".dec")
        success = MedicalDocEncryption.decrypt_file(input_path, output_path, password)

        if not success:
            raise HTTPException(400, "Decryption failed. Wrong password or corrupted file.")

        return {"success": True, "decrypted_path": output_path}

    # ---- Database Operations ----
    @app.get("/db/stats")
    async def get_stats():
        return db.get_stats()

    @app.get("/db/documents")
    async def get_documents(
        patient_id: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        doc_type: Optional[str] = Query(None),
        limit: int = Query(50),
    ):
        return db.get_documents(patient_id, status, doc_type, limit)

    @app.delete("/db/documents/{doc_id}")
    async def delete_document(doc_id: int):
        success = db.delete_document(doc_id)
        if not success:
            raise HTTPException(404, "Document not found")
        return {"success": True}

    @app.get("/db/logs")
    async def get_logs(document_id: Optional[int] = Query(None), limit: int = Query(100)):
        return db.get_logs(document_id, limit)

    @app.get("/db/settings")
    async def get_settings():
        return db.get_settings()

    @app.put("/db/settings")
    async def update_settings(settings: dict):
        success = db.update_settings(**settings)
        if not success:
            raise HTTPException(400, "Failed to update settings")
        return {"success": True}

    @app.post("/db/init")
    async def init_db(db_path: str = "medical_docs.db", encryption_password: str = ""):
        new_db = DatabaseManager(db_path=db_path)
        new_db.initialize(encryption_password)
        new_db.close()
        return {"success": True, "db_path": db_path}

    # ---- Batch Processing ----
    @app.post("/batch")
    async def batch_process(files: list[UploadFile] = File(...)):
        """Process multiple images in batch."""
        results = []
        for file in files:
            try:
                import cv2
                input_path = os.path.join(upload_dir, file.filename or "upload.png")
                with open(input_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)

                image = cv2.imread(input_path)
                if image is None:
                    results.append({"filename": file.filename, "error": "Could not read"})
                    continue

                deskew_angle = auto_detect_skew(image)
                proc = apply_processing(img=image, deskew_angle=deskew_angle)

                base_name = os.path.splitext(file.filename or "upload")[0]
                output_path = os.path.join(processed_dir, f"{base_name}_processed.png")
                cv2.imwrite(output_path, proc["image"])

                results.append({
                    "filename": file.filename,
                    "success": True,
                    "blur_before": proc["blur_before"],
                    "blur_after": proc["blur_after"],
                    "skew_angle": deskew_angle,
                    "quality": proc["quality"]["label"],
                })
            except Exception as e:
                results.append({"filename": file.filename, "error": str(e)})

        return {"results": results, "total": len(results)}

    return app


# ---- CLI Entry Point ----

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medical Document Processor API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--db", default="medical_docs.db", help="SQLite database path")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    app = create_app(db_path=args.db)

    if args.reload:
        uvicorn.run("api_server:create_app", host=args.host, port=args.port,
                     factory=True, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)
