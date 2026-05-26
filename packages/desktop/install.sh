#!/usr/bin/env bash
set -e

echo "🏥 Omni Medical Suite — installer"
if command -v pacman >/dev/null 2>&1; then
  DISTRO=arch
elif command -v apt-get >/dev/null 2>&1; then
  DISTRO=debian
else
  DISTRO=unknown
fi

if [ "$DISTRO" = "arch" ]; then
  sudo pacman -Sy --noconfirm python python-pip python-pyqt5 python-opencv python-numpy poppler tesseract tesseract-data-ara tesseract-data-eng
elif [ "$DISTRO" = "debian" ]; then
  sudo apt-get update -q
  sudo apt-get install -y python3 python3-pip python3-pyqt5 python3-opencv python3-numpy poppler-utils tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng fonts-noto-core
else
  echo "⚠️ Unsupported distro: install Python, Tesseract, and Poppler manually."
fi

python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Installation complete"
echo "Run: source .venv/bin/activate && python medical_doc_gui.py"
echo "Tests: QT_QPA_PLATFORM=offscreen pytest -q tests"
