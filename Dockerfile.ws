FROM python:3.11-slim

# ============================================================================
# OmniMedical Suite — WebSocket Server Dockerfile
# ============================================================================
# خادم WebSocket للتنبيهات الفورية والمزامنة التلقائية
# ============================================================================

LABEL maintainer="Dr. Abdulmalek Al-husseini"
LABEL description="OmniMedical WebSocket Server — Real-time Notifications"

WORKDIR /app

# تثبيت التبعيات
COPY services/ws/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY services/ws/ .

# المنفذ
EXPOSE 8765

# تشغيل
CMD ["python", "ws_server.py"]
