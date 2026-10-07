<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 71 -->

# MASTER PROMPT — GitHub Codespaces Integration
## Omni Medical Suite — Deploy in the Cloud (Browser-Based)

## 0. الهوية والنطاق

أنت تعمل كـ DevOps Engineer على:
/home/z/my-project/repos/omni-medical-suite

المهمة: تجهيز المشروع ليعمل في GitHub Codespaces بنقرة واحدة، 
دون أي تعديل على كود production، ودون أي تثبيت محلي.

النمط: EXECUTE — يمكنك إنشاء ملفات الإعداد، لكن:
- لا تعدّل أي ملف .py
- لا تعدّل أي محرك OCR
- لا تعدّل main
- لا ترفع أي بيانات حقيقية أو PHI

## 1. القواعد المطلقة

ممنوع:
- تعديل server.py, segment.py, train_server.py, train_trocr.py
- تعديل أي ملف داخل packages/omni_ocr/
- push مباشر إلى main
- رفع مجلد output/ أو models/ أو *.db
- رفع أي بيانات من output/S001 (قد تحتوي خط يد شخصي)
- تثبيت أي حزمة على النظام المحلي (كل شيء داخل devcontainer)

مسموح:
- إنشاء .devcontainer/devcontainer.json
- إنشاء .devcontainer/Dockerfile
- إنشاء .devcontainer/post-create.sh
- إضافة قسم جديد في README.md بعنوان "Run in Codespaces"
- إنشاء .gitpod.yml (بديل)
- إنشاء scripts/codespaces_smoke_test.sh

## 2. Pre-Flight

git -C /home/z/my-project/repos/omni-medical-suite status
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
ls -la /home/z/my-project/repos/omni-medical-suite/.devcontainer 2>/dev/null
grep -r "codespaces" /home/z/my-project/repos/omni-medical-suite/README.md 2>/dev/null

إذا .devcontainer موجود: أبلغ، ادمج بدل الاستبدال.
إذا Worktree غير نظيف: أنشئ فرع feature/codespaces-setup من HEAD.

## 3. المخرجات

### 3.1 .devcontainer/devcontainer.json
{
  "name": "Omni Medical Suite — AHW",
  "build": { "dockerfile": "Dockerfile" },
  "features": {
    "ghcr.io/devcontainers/features/python:1": { "version": "3.10" }
  },
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "ms-python.vscode-pylance"],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python"
      }
    }
  },
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "forwardPorts": [5000, 5001],
  "portsAttributes": {
    "5000": { "label": "Correction Server", "onAutoForward": "notify" },
    "5001": { "label": "Training UI", "onAutoForward": "notify" }
  },
  "remoteUser": "vscode",
  "hostRequirements": { "cpus": 2, "memory": "4gb", "storage": "32gb" }
}

### 3.2 .devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.10-bullseye

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 poppler-utils \
    tesseract-ocr tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

### 3.3 .devcontainer/post-create.sh
#!/bin/bash
set -e
echo "🚀 Setting up Omni Medical Suite..."

# venv
python -m venv /workspace/.venv
source /workspace/.venv/bin/activate

# تثبيت المتطلبات الأساسية فقط (بدون torch الثقيل)
grep -v "^torch" /workspace/requirements.txt | pip install -r /dev/stdin || true
pip install flask flask-socketio opencv-python PyMuPDF pandas openpyxl

# تحقق
python -c "import cv2, fitz, flask, pandas; print('✅ Core imports OK')"

# لا تُنزّل أي نموذج
echo "⚠️  Models NOT downloaded (do manually if needed)"
echo "✅ Setup complete. Run: python server.py --sample S001"
chmod +x /workspace/scripts/*.sh 2>/dev/null || true

### 3.4 scripts/codespaces_smoke_test.sh
#!/bin/bash
# يتحقق أن المشروع جاهز للتشغيل في Codespaces
set -e
cd "$(dirname "$0")/.."

echo "1. Checking Python..."
python --version

echo "2. Checking imports..."
python -c "import cv2, fitz, flask, pandas, openpyxl; print('✅ OK')"

echo "3. Checking files..."
for f in server.py segment.py templates/; do
    test -e "$f" && echo "✅ $f" || echo "❌ MISSING: $f"
done

echo "4. Checking ports..."
lsof -i:5000 2>/dev/null && echo "⚠️  Port 5000 busy" || echo "✅ Port 5000 free"

echo "5. Sample check..."
if [ -d "output" ]; then
    echo "⚠️  output/ exists — will NOT commit"
else
    echo "✅ No output/ (clean)"
fi

echo "✅ Smoke test complete"

### 3.5 .gitpod.yml (بديل)
image:
  file: .devcontainer/Dockerfile
tasks:
  - init: bash .devcontainer/post-create.sh
    command: echo "Ready. Run: python server.py"
ports:
  - port: 5000
    onOpen: notify
  - port: 5001
    onOpen: notify

### 3.6 إضافة إلى README.md
أضف قسم "## ☁️ Run in GitHub Codespaces" بعد قسم التثبيت:
- خطوات فتح Codespaces
- الأوامر لتشغيل server.py
- كيف يفتح المنفذ أمام المتصفح
- تحذير: لا ترفع PHI إلى Codespaces

### 3.7 .gitignore
أضف (إذا غير موجود):
output/
models/
*.db
*.xlsx
corrections*.csv
batch_*/
.devcontainer/.env
secrets/
tokens/

## 4. Testing

نفّذ:
bash scripts/codespaces_smoke_test.sh

إن نجح: سجّل النتيجة كـ SMOKE_PASSED
إن فشل: أبلغ بالسبب، لا تعدّل الكود لحل المشكلة

## 5. Stop Gates

V-STOP-1: إذا فشل smoke test → أبلغ، لا تكمل
V-STOP-2: إذا حاول النظام رفع PHI → STOP فوراً
V-STOP-3: إذا احتجت تعديل كود production → STOP، أعد التقييم

## 6. Handoff Bundle

بعد commit:
download/OMNI-EXECUTION/handovers/<sha>/
  - COMMIT_SHA.txt
  - FILES_CREATED.txt
  - SMOKE_TEST_RESULTS.txt
  - RECONSTRUCTION.md
  - NEXT_STEPS.md

## 7. التقرير النهائي

=== CODESPACES SETUP ===
Branch:        feature/codespaces-setup
HEAD SHA:      <full>
Remote SHA:    <verified>

FILES CREATED:
  .devcontainer/devcontainer.json
  .devcontainer/Dockerfile
  .devcontainer/post-create.sh
  .gitpod.yml
  scripts/codespaces_smoke_test.sh
  README.md (updated section)
  .gitignore (updated)

SMOKE TEST:    PASSED | FAILED | BLOCKED

PROVEN:
PARTIALLY PROVEN:
UNVERIFIED:
BLOCKED:

NEXT STEPS FOR USER:
  1. افتح المستودع على github.com
  2. اضغط Code → Codespaces → Create
  3. انتظر ~3 دقائق
  4. في Terminal: python server.py --sample S001
  5. افتح المنفذ 5000 من تبويب Ports

PERSISTENCE:   OK | BLOCKED
