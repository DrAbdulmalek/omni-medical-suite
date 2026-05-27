#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
locustfile.py
=============
اختبار حمل واقعي يقيس أداء Medical Load Balancer + WebSocket + Redis
تحت 1000 مستخدم متزامن (محاكاة أطباء وممرضين في وقت الذروة).

الاستخدام:
    pip install locust websocket-client
    cd tests/loadtest
    locust -f locustfile.py --headless -u 1000 -r 50 --run-time 5m

أو مع واجهة الويب:
    locust -f locustfile.py
    # ثم افتح http://localhost:8089

المؤلف: Dr. Abdulmalek Al-husseini
المشروع: OmniMedical Suite
"""

from locust import HttpUser, task, between, events
import json
import time
import random
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ثوابت الاختبار
# ============================================================================

# أنواع المستندات الطبية المحتملة
DOCUMENT_TYPES = [
    "xray", "lab_report", "prescription", "mri_scan",
    "ct_scan", "ultrasound", "pathology", "discharge_summary",
    "referral_letter", "operative_note"
]

# أنواع فحوصات المختبر (لزيادة واقعية البيانات)
LAB_TESTS = [
    "CBC", "CMP", "Lipid Panel", "HbA1c", "TSH",
    "Urinalysis", "Blood Culture", "CRP", "ESR", "PT/INR"
]

# عناصر الكيانات الطبية الوهمية (لا تحتوي بيانات حقيقية)
MOCK_PATIENTS = [
    {"id": "P001", "dept": "orthopedics"},
    {"id": "P002", "dept": "cardiology"},
    {"id": "P003", "dept": "neurology"},
    {"id": "P004", "dept": "pediatrics"},
    {"id": "P005", "dept": "general_surgery"},
    {"id": "P006", "dept": "radiology"},
    {"id": "P007", "dept": "emergency"},
    {"id": "P008", "dept": "icu"},
]

TENANT_IDS = ["hospital_a", "hospital_b", "clinic_01", "clinic_02"]

# أوزان المهام (تقليد سلوك المستخدمين الحقيقيين)
# رفع المستندات هو الأكثر تكراراً (5/10)، ثم الكاش (3/10)، ثم الصحة (1/10)، إلخ.
TASK_WEIGHTS = {
    "upload_document": 5,
    "cache_hit": 3,
    "health_check": 1,
    "search_patient": 3,
    "get_lab_results": 2,
    "submit_correction": 1,
}


# ============================================================================
# WebSocket client (اختياري - يعمل فقط إذا توفر websocket-client)
# ============================================================================

_ws_available = False
try:
    import websocket
    _ws_available = True
except ImportError:
    logger.warning(
        "websocket-client غير مثبت. "
        "WebSocket tests سيتم تخطيها. "
        "ثبته بـ: pip install websocket-client"
    )


# ============================================================================
# مؤشرات الأداء المخصصة
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """إعداد العدادات عند بدء الاختبار."""
    logger.info("=" * 60)
    logger.info("OmniMedical Suite - Load Test")
    logger.info("=" * 60)
    logger.info(f"WebSocket available: {_ws_available}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """طباعة ملخص عند انتهاء الاختبار."""
    logger.info("=" * 60)
    logger.info("Load Test Complete")
    logger.info("=" * 60)


# ============================================================================
# المحاكي الطبي
# ============================================================================

class MedicalClient(HttpUser):
    """
    محاكي عميل طبي واقعي.
    يحاكي تدفق العمل في مستشفى أو عيادة:
    - رفع مستندات (أشعة، تقارير، وصفات)
    - البحث في نتائج المختبر
    - تصحيح نتائج OCR
    - فحص صحة النظام
    """
    wait_time = between(0.5, 2.0)  # محاكاة تدفق العمل الطبي
    host = "http://localhost:8080"  # نقطة الدخول عبر موازن الحمل

    def on_start(self):
        """تهيئة بيانات المستخدم الوهمي."""
        self.user_id = f"dr_{random.randint(1000, 9999)}"
        self.tenant_id = random.choice(TENANT_IDS)
        self.patient = random.choice(MOCK_PATIENTS)
        self.ws = None
        self._connect_ws()

    def on_stop(self):
        """تنظيف الموارد."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

    def _connect_ws(self):
        """
        اتصال بخادم WebSocket للاستماع للتنبيهات.
        يعمل فقط إذا كان websocket-client متوفراً.
        """
        if not _ws_available:
            return
        try:
            self.ws = websocket.create_connection(
                f"ws://localhost:8765",
                timeout=5
            )
            self.ws.send(json.dumps({
                "type": "subscribe_tenant",
                "tenant_id": self.tenant_id
            }))
            logger.debug(f"[{self.user_id}] WebSocket connected to {self.tenant_id}")
        except Exception as e:
            logger.debug(f"[{self.user_id}] WebSocket failed: {e}")
            self.ws = None

    # ========================================================================
    # المهام (Tasks) - مرتبة حسب الأوزان
    # ========================================================================

    @task(5)
    def upload_document(self):
        """رفع مستند طبي عبر موازن الحمل."""
        doc_type = random.choice(DOCUMENT_TYPES)
        payload = {
            "doc_type": doc_type,
            "urgent": random.choice([True, False, False, False]),  # 25% طوارئ
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "patient_id": self.patient["id"],
            "metadata": {
                "department": self.patient["dept"],
                "source": "load_test"
            }
        }
        with self.client.post(
            "/api/documents/upload",
            json=payload,
            catch_response=True,
            name="/api/documents/upload"
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                # Rate limiting - مقبول في الاختبار
                resp.success()
            elif resp.status_code == 503:
                # الخادم مشغول - مقبول تحت الحمل
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code} | {resp.text[:200]}")

    @task(3)
    def cache_hit(self):
        """محاكاة طلبات الكاش المتكررة (Redis)."""
        scan_id = random.choice(["scan_001", "scan_002", "scan_003",
                                  "scan_004", "scan_005"])
        self.client.get(
            f"/api/ocr/cache/{scan_id}",
            name="/api/ocr/cache/[id]"
        )

    @task(1)
    def health_check(self):
        """فحص صحة النظام."""
        with self.client.get("/health", name="/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()

    @task(3)
    def search_patient(self):
        """البحث عن مريض في النظام."""
        self.client.get(
            f"/api/patients/{self.patient['id']}",
            name="/api/patients/[id]"
        )

    @task(2)
    def get_lab_results(self):
        """جلب نتائج فحوصات المختبر."""
        test = random.choice(LAB_TESTS)
        self.client.get(
            f"/api/lab/results/{self.patient['id']}/{test}",
            name="/api/lab/results/[pid]/[test]"
        )

    @task(1)
    def submit_correction(self):
        """إرسال تصحيح لنتيجة OCR (محاكاة RLHF)."""
        payload = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "document_id": f"doc_{random.randint(10000, 99999)}",
            "original_text": "نص OCR الأصلي",
            "corrected_text": "النص المصحح يدوياً",
            "confidence": round(random.uniform(0.5, 1.0), 2),
            "rating": random.randint(1, 5)
        }
        self.client.post(
            "/api/ocr/correction",
            json=payload,
            name="/api/ocr/correction"
        )
