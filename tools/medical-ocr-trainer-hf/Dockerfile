# =============================================================
# Medical OCR Trainer — Docker HF Space (Free Tier Optimized)
# 3 Engines: PaddleOCR + EasyOCR + Tesseract
# Removed: TrOCR (~1.5GB) + Surya (~800MB) to fit 16GB RAM limit
# =============================================================
FROM python:3.10-slim

# تثبيت نظام الحزم المطلوبة
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# تعيين متغيرات البيئة
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# مجلدات التخزين المؤقت للنماذج
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV TORCH_HOME=/app/.cache/torch
ENV PADDLE_HOME=/app/.cache/paddleocr

# إنشاء مجلدات العمل والتخزين الدائم
RUN mkdir -p /app/.cache/huggingface /app/.cache/torch /app/.cache/paddleocr \
    /data/uploads /data/crops /data/db /data/exports

WORKDIR /app

# نسخ ملف المتطلبات أولاً (للاستفادة من Docker cache)
COPY requirements.txt .

# تثبيت torch CPU-only أولاً (يوفر ~10GB مقارنة بنسخة CUDA)
# ثم تثبيت باقي المتطلبات
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# نسخ ملفات المشروع
COPY . .

# التأكد من تثبيت نماذج PaddleOCR مسبقاً (lightweight)
RUN python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_textline_orientation=True, lang='ar', show_log=False); del ocr" || true

# التأكد من تثبيت نماذج EasyOCR مسبقاً
RUN python -c "import easyocr; reader = easyocr.Reader(['ar','en'], gpu=False, download_enabled=True); del reader" || true

EXPOSE 7860

# تشغيل Streamlit — محسّن لـ Hugging Face Spaces proxy
CMD ["streamlit", "run", "app.py", \
    "--server.port=7860", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false", \
    "--server.enableCORS=false", \
    "--server.enableXsrfProtection=false"]
