#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
websocket_integration.py
========================
تكامل WebSocket Server مع:
1. Celery tasks (إرسال تحديثات فورية من المهام الخلفية)
2. Gradio UI (عرض حالة المعالجة في الوقت الحقيقي)
3. FastAPI endpoint (للاشتراك في التحديثات)

الاستخدام:
    # 1. تشغيل WebSocket Server
    python medical_websocket_server.py --port 8765

    # 2. تشغيل هذا الملف (Celery worker + Gradio)
    python websocket_integration.py
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Celery
from celery import Celery, Task
from celery.signals import task_prerun, task_postrun, task_success, task_failure

# Gradio
import gradio as gr

# FastAPI (للـ REST API)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# استيراد خادم WebSocket المخصص
import sys
sys.path.append(".")
from medical_websocket_server import (
    MedicalWebSocketServer, WebSocketNotifier, 
    ProcessingUpdate, RoomManager
)


# =============================================================================
# Celery Integration
# =============================================================================

# إعداد Celery (استخدم Redis كـ broker)
celery_app = Celery(
    'omnimedical',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# كائن notifier مشترك (سيتم تهيئته لاحقاً)
ws_notifier: Optional[WebSocketNotifier] = None

def set_ws_notifier(notifier: WebSocketNotifier):
    """تعيين notifier للاستخدام في المهام"""
    global ws_notifier
    ws_notifier = notifier


class ProcessingTask(Task):
    """مهمة Celery مخصصة مع دعم WebSocket updates"""

    def __call__(self, *args, **kwargs):
        # استخراج معرف المستند والمستأجر من kwargs
        self.document_id = kwargs.get('document_id', 'unknown')
        self.tenant_id = kwargs.get('tenant_id', 'default')
        return self.run(*args, **kwargs)

    def update_progress(self, stage: str, progress: int, message: str, 
                       metadata: Optional[Dict] = None):
        """إرسال تحديث للـ WebSocket"""
        if ws_notifier:
            asyncio.create_task(ws_notifier.send_processing_update(
                document_id=self.document_id,
                stage=stage,
                progress=progress,
                message=message,
                tenant_id=self.tenant_id,
                metadata=metadata
            ))


@celery_app.task(base=ProcessingTask, bind=True)
def process_document_pipeline(self, image_path: str, document_id: str, 
                              tenant_id: str = "default"):
    """
    خط أنابيب المعالجة الكامل مع تحديثات WebSocket فورية.
    """
    self.document_id = document_id
    self.tenant_id = tenant_id

    # المرحلة 1: رفع الصورة
    self.update_progress("uploaded", 5, "Image uploaded successfully")
    time.sleep(0.5)

    # المرحلة 2: تصحيح الميلان
    self.update_progress("deskew_started", 10, "Detecting skew angle...")
    time.sleep(1.0)
    self.update_progress("deskew_finished", 20, "Skew corrected: 2.3°")

    # المرحلة 3: القص الذكي
    self.update_progress("crop_started", 25, "Detecting page boundaries...")
    time.sleep(0.5)
    self.update_progress("crop_finished", 30, "Page cropped successfully")

    # المرحلة 4: OCR
    self.update_progress("ocr_started", 35, "Running OCR engines...")
    time.sleep(2.0)
    ocr_text = "كسر في عظم الفخذ الأيمن مع نزيف حاد"
    self.update_progress("ocr_finished", 50, "OCR completed", 
                        metadata={"extracted_text": ocr_text})

    # المرحلة 5: Fusion V3
    self.update_progress("fusion_started", 55, "Fusing OCR results...")
    time.sleep(1.5)
    fused_text = "كسر في عظم الفخذ الأيمن مع نزيف حاد"
    self.update_progress("fusion_finished", 75, "Fusion completed", 
                        metadata={"fused_text": fused_text, 
                                 "engines_used": ["tesseract", "easyocr", "paddleocr"]})

    # المرحلة 6: Semantic Dedup
    self.update_progress("dedup_started", 80, "Checking for duplicates...")
    time.sleep(1.0)
    self.update_progress("dedup_finished", 90, "No duplicates found")

    # المرحلة 7: اكتمال
    self.update_progress("completed", 100, "Document processing completed successfully",
                        metadata={"final_text": fused_text, 
                                 "word_count": len(fused_text.split())})

    return {
        "document_id": document_id,
        "status": "completed",
        "final_text": fused_text
    }


@celery_app.task(base=ProcessingTask, bind=True)
def process_with_medical_check(self, image_path: str, document_id: str,
                                tenant_id: str = "default"):
    """
    خط أنابيب مع فحص طبي (MedicalContextProtector) وإرسال تنبيهات عاجلة.
    """
    self.document_id = document_id
    self.tenant_id = tenant_id

    # ... معالجة ...

    # محاكاة اكتشاف تعارض طبي
    if ws_notifier:
        asyncio.create_task(ws_notifier.send_medical_conflict_alert(
            document_id=document_id,
            conflict_reason="Laterality conflict: right vs left femur",
            tenant_id=tenant_id
        ))

    return {"status": "alert_sent"}


# =============================================================================
# Gradio UI with Real-time Updates
# =============================================================================

class GradioWebSocketClient:
    """عميل WebSocket يعمل داخل Gradio لاستقبال التحديثات"""

    def __init__(self):
        self.connected = False
        self.updates = []
        self.ws = None

    async def connect(self, uri: str = "ws://localhost:8765"):
        import websockets
        self.ws = await websockets.connect(uri)
        self.connected = True

        # الاشتراك في المستند
        await self.ws.send(json.dumps({
            "type": "subscribe_document",
            "document_id": "doc_001",
            "tenant_id": "hospital_a"
        }))

    async def receive_updates(self):
        """استقبال التحديثات في loop منفصل"""
        while self.connected and self.ws:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                data = json.loads(msg)
                self.updates.append(data)
                return data
            except asyncio.TimeoutError:
                return None
            except Exception as e:
                print(f"WebSocket error: {e}")
                self.connected = False
                return None

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.connected = False


def create_gradio_interface():
    """إنشاء واجهة Gradio مع دعم WebSocket"""

    client = GradioWebSocketClient()
    update_history = []

    async def start_processing(image, tenant_id):
        """بدء المعالجة وإعداد WebSocket"""
        # بدء Celery task
        task = process_document_pipeline.delay(
            image_path="/tmp/uploaded.png",
            document_id="doc_001",
            tenant_id=tenant_id
        )

        # الاتصال بـ WebSocket
        await client.connect()

        return f"Task started: {task.id}", "Connecting to WebSocket..."

    async def poll_updates():
        """استقبال التحديثات"""
        data = await client.receive_updates()
        if data:
            update_history.append(data)
            stage = data.get('stage', 'unknown')
            progress = data.get('progress', 0)
            msg = data.get('message', '')

            # بناء شريط التقدم
            bar_length = 30
            filled = int(bar_length * progress / 100)
            bar = '█' * filled + '░' * (bar_length - filled)

            status_text = f"Stage: {stage}\nProgress: [{bar}] {progress}%\nMessage: {msg}"

            # إذا كان هناك تنبيه طبي
            if data.get('type') == 'medical_alert':
                status_text = f"🚨 MEDICAL ALERT 🚨\n{data.get('message', '')}"

            return status_text, "\n".join([
                f"[{u.get('stage', '?')}] {u.get('progress', 0)}% - {u.get('message', '')}"
                for u in update_history[-10:]
            ])

        return "Waiting for updates...", "\n".join([
            f"[{u.get('stage', '?')}] {u.get('progress', 0)}% - {u.get('message', '')}"
            for u in update_history[-10:]
        ]) if update_history else "No updates yet"

    with gr.Blocks(title="OmniMedical - Real-time Processing") as demo:
        gr.Markdown("""
        # 🏥 OmniMedical Suite - معالجة فورية
        **راقب حالة معالجة المستندات في الوقت الحقيقي عبر WebSocket**
        """)

        with gr.Row():
            with gr.Column():
                image_input = gr.Image(type="filepath", label="📸 رفع مستند طبي")
                tenant_input = gr.Textbox(value="hospital_a", label="معرف المستأجر (Tenant ID)")
                start_btn = gr.Button("▶️ بدء المعالجة", variant="primary")

            with gr.Column():
                status_output = gr.Textbox(label="📊 الحالة الحالية", lines=5, 
                                          value="Ready to process...")
                history_output = gr.Textbox(label="📜 سجل التحديثات", lines=10,
                                           value="No updates yet")

        # زر التحديث اليدوي (أو يمكن استخدام auto-refresh)
        refresh_btn = gr.Button("🔄 تحديث الحالة")

        start_btn.click(
            fn=start_processing,
            inputs=[image_input, tenant_input],
            outputs=[status_output, history_output]
        )

        refresh_btn.click(
            fn=poll_updates,
            inputs=[],
            outputs=[status_output, history_output]
        )

        gr.Markdown("""
        ---
        ### 🔔 التحديثات الفورية:
        - **uploaded** → تم رفع الصورة
        - **deskew_finished** → تم تصحيح الميلان
        - **ocr_finished** → اكتمل OCR
        - **fusion_finished** → اكتمل Fusion V3
        - **completed** → اكتملت المعالجة
        - **medical_alert** → 🚨 تعارض طبي يحتاج مراجعة!
        """)

    return demo


# =============================================================================
# FastAPI Endpoint (Alternative to Gradio)
# =============================================================================

app = FastAPI(title="OmniMedical WebSocket API")

@app.get("/")
async def root():
    return {"message": "OmniMedical WebSocket Integration API"}

@app.post("/process")
async def start_processing(document_id: str, tenant_id: str = "default"):
    """بدء معالجة مستند وإرسال تحديثات عبر WebSocket"""
    task = process_document_pipeline.delay(
        image_path="/tmp/uploaded.png",
        document_id=document_id,
        tenant_id=tenant_id
    )
    return {"task_id": task.id, "status": "started"}

@app.get("/ws-stats")
async def websocket_stats():
    """إحصائيات اتصالات WebSocket"""
    # يمكن ربطها بخادم WebSocket الفعلي
    return {"status": "active", "connections": 0}


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """تشغيل كل المكونات معاً"""

    # 1. تهيئة WebSocket Server
    ws_server = MedicalWebSocketServer(host="0.0.0.0", port=8765)
    notifier = WebSocketNotifier(ws_server)
    set_ws_notifier(notifier)

    # 2. تشغيل WebSocket Server في background
    ws_task = asyncio.create_task(ws_server.start())

    # 3. انتظار بدء الخادم
    await asyncio.sleep(1)

    # 4. تشغيل Gradio
    demo = create_gradio_interface()

    # 5. تشغيل FastAPI (اختياري - يمكن تشغيله منفصلاً)
    # import uvicorn
    # api_task = asyncio.create_task(uvicorn.run(app, host="0.0.0.0", port=8000))

    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║           🏥 OmniMedical WebSocket Integration              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  WebSocket Server: ws://localhost:8765                      ║
    ║  Gradio UI: http://localhost:7860                          ║
    ║  FastAPI: http://localhost:8000                            ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Celery Worker: celery -A websocket_integration worker     ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    # تشغيل Gradio (يحظر حتى الإغلاق)
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)

    # إيقاف WebSocket Server عند الإغلاق
    ws_server.running = False
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
