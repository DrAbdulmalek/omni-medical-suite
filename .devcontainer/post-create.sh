#!/bin/bash
# Runs automatically on Codespace creation (postCreateCommand).
# Safety rules honored: no PHI, no credentials, no external services beyond
# PyPI/apt indexes; no model weights downloaded.
set -e
echo "🚀 Setting up Omni Medical Suite..."
python -m venv /workspace/.venv
source /workspace/.venv/bin/activate
grep -v "^torch" /workspace/requirements.txt | pip install -r /dev/stdin || true
pip install flask flask-socketio opencv-python PyMuPDF pandas openpyxl
python -c "import cv2, fitz, flask, pandas; print('✅ Core imports OK')"
echo "⚠️  Models NOT downloaded (do manually if needed)"
echo "✅ Setup complete. Run: python server.py --sample S001"
