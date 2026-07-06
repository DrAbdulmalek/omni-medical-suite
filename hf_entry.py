"""
Medical OCR Trainer — HF Space Entry Point
==========================================
واجهة Streamlit للتجريب على Hugging Face Spaces.
تستخدم /data/ للتخزين الدائم (يصمد أمام إعادة تشغيل الحاوية).
"""

import os

# === HF Space Persistent Storage ===
# على HF Spaces، يتم تخزين البيانات في /data/ لضمان البقاء
# بعد إعادة تشغيل الحاوية
if os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE"):
    os.environ.setdefault("DIR_UPLOADS", "/data/uploads")
    os.environ.setdefault("DIR_CROPS", "/data/crops")
    os.environ.setdefault("DIR_DB", "/data")
    os.environ.setdefault("DB_PATH", "/data/corrections.db")

    # Ensure directories exist
    for d in ["/data/uploads", "/data/crops", "/data/exports", "/data"]:
        os.makedirs(d, exist_ok=True)

# Import and run the main app
from app import main

if __name__ == "__main__":
    main()
