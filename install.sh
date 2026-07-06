#!/usr/bin/env bash
# install.sh - تثبيت الاعتماديات على Manjaro/Ubuntu

set -e

echo "🚀 بدء تثبيت معالج الوثائق الطبية..."

# إنشاء بيئة افتراضية
if [ ! -d ".venv" ]; then
    echo "📦 إنشاء بيئة افتراضية..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "📦 تثبيت الحزم المطلوبة..."
pip install --upgrade pip
pip install opencv-python numpy PyQt5 pytesseract pdf2image pillow

# تثبيت Tesseract OCR و Poppler حسب التوزيعة
if command -v pacman &> /dev/null; then
    echo "🖥️ الكشف عن نظام Arch/Manjaro..."
    sudo pacman -S --needed tesseract tesseract-data-eng tesseract-data-ara poppler
elif command -v apt &> /dev/null; then
    echo "🖥️ الكشف عن نظام Ubuntu/Debian..."
    sudo apt update
    sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara poppler-utils
else
    echo "⚠️ لم يتم التعرف على مدير الحزم. يرجى تثبيت Tesseract و Poppler يدوياً."
fi

echo "✅ التثبيت اكتمل. لتشغيل التطبيق استخدم: ./run.sh"
