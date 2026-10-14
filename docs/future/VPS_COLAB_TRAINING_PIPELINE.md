<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 71 -->

# MASTER PROMPT — VPS ↔ Colab Training Pipeline
## Omni Medical Suite — Automated Dataset Sync & Training Loop

## 0. النطاق

المهمة: تصميم وتوثيق pipeline كامل يربط:
- VPS (تخزين التصحيحات)
- Google Colab (تدريب GPU)
- GitHub (وسيط آمن للنقل)

النمط: TEMPLATE_ONLY — لا تنفيذ، لا SSH، لا Colab، لا VPS.

الفرع: feature/vps-colab-pipeline

## 1. القواعد المطلقة

ممنوع:
- تنفيذ أي شيء
- الاتصال بأي خدمة
- تعديل train_trocr.py أو train_server.py
- رفع أي بيانات حقيقية

مسموح:
- إنشاء templates + notebooks + workflows كملفات
- إنشاء documentation شامل

## 2. المعمارية

VPS (SQLite corrections.db)
    │
    │ 1. Export daily/weekly (cron)
    │ 2. Encrypt + push to GitHub Private
    ▼
GitHub Private Repo (datasets/encrypted-<hash>.tar.gz.gpg)
    │
    │ 3. Trigger via GitHub Actions (workflow_dispatch)
    │ 4. Colab pulls via gh CLI
    ▼
Colab (Train TrOCR/AraBERT, 4-6 hours)
    │
    │ 5. Push trained model to GitHub Releases
    ▼
GitHub Releases (trocr-arabic-v<n>.safetensors)
    │
    │ 6. VPS pulls via cron (weekly check)
    │ 7. Validate (test on 50 samples)
    │ 8. Promote or reject
    ▼
VPS (models/trocr-arabic-v<n>/)

## 3. المخرجات

### 3.1 الهيكل
automation/
├── README.md
├── ARCHITECTURE.md
├── vps/
│   ├── 01-export-dataset.sh
│   ├── 02-encrypt-and-push.sh
│   ├── 03-pull-and-validate-model.sh
│   ├── 04-promote-or-rollback.sh
│   └── crontab.template
├── colab/
│   ├── train_arabic_trocr.ipynb
│   └── README.md
├── github/
│   ├── .github/workflows/
│   │   ├── trigger-training.yml
│   │   └── validate-model.yml
│   └── PRIVATE_REPO_SETUP.md
├── shared/
│   ├── encrypt.sh
│   ├── decrypt.sh
│   └── validate_model.py
└── SECURITY.md

### 3.2 vps/01-export-dataset.sh
#!/bin/bash
# يصدّر التصحيحات من SQLite إلى dataset مصحح
set -euo pipefail

SAMPLE_ID="${1:-S001}"
DB="/home/ubuntu/omni-medical-suite/output/$SAMPLE_ID/corrections.db"
OUT="/tmp/dataset-$SAMPLE_ID-$(date +%Y%m%d)"

mkdir -p "$OUT"

# استخراج البيانات
sqlite3 "$DB" <<SQL
.mode csv
.headers on
.output $OUT/corrections.csv
SELECT word_id, page, column_idx, line_idx, word_idx, 
       crop_path, text, status
FROM words
WHERE text IS NOT NULL AND text != '' 
  AND status IN ('USER_CORRECTED', 'VALIDATED');
SQL

# نسخ الصور
cp -r "/home/ubuntu/omni-medical-suite/output/$SAMPLE_ID/crops" "$OUT/"

# إحصاء
COUNT=$(tail -n +2 "$OUT/corrections.csv" | wc -l)
echo "Exported $COUNT corrections from $SAMPLE_ID"

# كتابة manifest
cat > "$OUT/manifest.json" <<JSON
{
  "sample_id": "$SAMPLE_ID",
  "exported_at": "$(date -Iseconds)",
  "count": $COUNT,
  "min_required": 500,
  "ready_for_training": $([ $COUNT -ge 500 ] && echo true || echo false)
}
JSON

echo "$OUT"

### 3.3 vps/02-encrypt-and-push.sh
#!/bin/bash
# يشفّر البيانات ويدفعها إلى GitHub Private
set -euo pipefail

DATASET_DIR="$1"
RECIPIENT="${GPG_RECIPIENT:?GPG_RECIPIENT not set}"
TARGET_REPO="${DATASET_REPO:?DATASET_REPO not set}"

# تحقق أن الـmanifest جاهز
COUNT=$(jq -r .count "$DATASET_DIR/manifest.json")
READY=$(jq -r .ready_for_training "$DATASET_DIR/manifest.json")

if [ "$READY" != "true" ]; then
    echo "❌ Dataset not ready ($COUNT < 500)"
    exit 1
fi

# ضغط
ARCHIVE="/tmp/dataset-$(date +%Y%m%d).tar.gz"
tar -czf "$ARCHIVE" -C "$DATASET_DIR" .

# تشفير (GPG بمفتاح عام)
ENCRYPTED="${ARCHIVE}.gpg"
gpg --batch --yes --encrypt --recipient "$RECIPIENT" \
    --output "$ENCRYPTED" "$ARCHIVE"

# SHA256
SHA=$(sha256sum "$ENCRYPTED" | cut -d' ' -f1)
echo "SHA256: $SHA"

# push إلى GitHub Private
cd /tmp
git clone "git@github.com:$TARGET_REPO.git" dataset-repo || \
    (cd dataset-repo && git pull)
cp "$ENCRYPTED" dataset-repo/datasets/
echo "$SHA" > dataset-repo/datasets/latest.sha256
echo "$(date -Iseconds)" > dataset-repo/datasets/latest.timestamp

cd dataset-repo
git add datasets/
git commit -m "dataset: $(date +%Y%m%d) ($COUNT samples)"
git push

# تنظيف محلي
shred -u "$ARCHIVE" 2>/dev/null || rm -f "$ARCHIVE"
echo "✅ Pushed to $TARGET_REPO"

### 3.4 colab/train_arabic_trocr.ipynb (outline)

الخلايا:
1. Markdown: عنوان + تحذير
2. Code: تركيب المتطلبات
3. Code: استنساخ GitHub Private (يستخدم GH_TOKEN من Colab secrets)
4. Code: فك تشفير dataset
5. Code: تحميل النماذج الأساسية
6. Code: إعداد AraBERT tokenizer
7. Code: load ArabicTrOCR
8. Code: تهيئة Dataset
9. Code: تدريب (30 epoch)
10. Code: تقييم CER/WER
11. Code: حفظ النموذج
12. Code: رفع إلى GitHub Releases
13. Code: إرسال Webhook إلى VPS

### 3.5 github/.github/workflows/trigger-training.yml
name: Trigger Colab Training

on:
  workflow_dispatch:
    inputs:
      sample_id:
        description: 'Sample ID'
        required: true
        default: 'S001'
      epochs:
        description: 'Epochs'
        required: true
        default: '30'

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Notify Colab
        run: |
          echo "Training triggered for ${{ inputs.sample_id }}"
          # يدوياً: افتح Colab واضغط Run All
          # أو استخدم Colab API مستقبلاً

### 3.6 vps/03-pull-and-validate-model.sh
#!/bin/bash
set -euo pipefail

VERSION="${1:?usage: $0 <version>}"
MODEL_DIR="/home/ubuntu/omni-medical-suite/models"
NEW_MODEL="/tmp/model-$VERSION"
BACKUP_DIR="/home/ubuntu/models-backup"

# تحميل من GitHub Release
gh release download "trocr-v$VERSION" \
    --repo "${MODEL_REPO}" \
    --pattern "*.tar.gz" \
    --dir "$NEW_MODEL"

# SHA256 verify
gh release download "trocr-v$VERSION" \
    --repo "${MODEL_REPO}" \
    --pattern "*.sha256" \
    --dir "$NEW_MODEL"

cd "$NEW_MODEL"
sha256sum -c *.sha256

# فك ضغط
tar -xzf *.tar.gz

# اختبار على 50 عينة
python /home/ubuntu/omni-medical-suite/scripts/validate_model.py \
    --model "$NEW_MODEL" \
    --test-data "/home/ubuntu/omni-medical-suite/output/S001/test_subset" \
    --min-cer-improvement 0.05 \
    --output /tmp/validation.json

# قرار
if jq -e '.promote == true' /tmp/validation.json > /dev/null; then
    echo "✅ Model approved"
    # نسخ احتياطي
    rsync -a "$MODEL_DIR/current/" "$BACKUP_DIR/$(date +%Y%m%d)/"
    # ترقية
    rsync -a "$NEW_MODEL/" "$MODEL_DIR/current/"
    systemctl restart ahw-correction
    echo "$VERSION" > "$MODEL_DIR/current/.version"
else
    echo "❌ Model rejected"
    cat /tmp/validation.json
    exit 1
fi

### 3.7 shared/validate_model.py
#!/usr/bin/env python3
"""
يقيس CER/WER للنموذج الجديد مقابل القديم.
يُرجع قرار promote=true/false.
"""
import argparse, json
from pathlib import Path
# ... (تطبيق كامل)

def main():
    # ...
    result = {
        "old_cer": 0.25,
        "new_cer": 0.18,
        "improvement": 0.07,
        "min_required": 0.05,
        "promote": True,
        "medical_cer_ok": True,
        "recommendation": "promote"
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

### 3.8 SECURITY.md

يشرح:
- لماذا نستخدم GitHub Private كوسيط
- لماذا التشفير بـGPG إلزامي
- لماذا لا نرسل PHI
- كيفية تدوير مفاتيح GPG سنوياً
- كيفية التحقق من SHA256
- آلية rollback عند فشل النموذج

### 3.9 ARCHITECTURE.md

Diagram + شرح:
- المنافذ المستخدمة
- نقاط الفشل
- كيف يُستأنف العمل بعد الانقطاع
- سياسات retention
- SLA المتوقع

## 4. القيود الصارمة

- كل ملف يحمل: `# STATUS: TEMPLATE — NOT EXECUTED`
- لا تشغيل أي سكربت
- لا اتصال بأي GitHub repo
- لا توليد أي مفتاح GPG حقيقي
- لا تجريب Colab

## 5. Stop Gates

P-STOP-1: أي محاولة اتصال → STOP
P-STOP-2: أي بيانات حقيقية في الأمثلة → STOP
P-STOP-3: أي ادعاء أن شيئاً "يعمل" → STOP

## 6. التقرير النهائي

=== VPS ↔ COLAB PIPELINE ===
Branch:          feature/vps-colab-pipeline
HEAD SHA:        <full>

FILES CREATED:   <list>
NOTEBOOKS:       1 (train_arabic_trocr.ipynb)
WORKFLOWS:       2
SCRIPTS:         <count>

EXECUTION:       NONE
NETWORK CALLS:   NONE

PROVEN:
  - Architecture is documented
  - All scripts are idempotent templates

NOT EXECUTED:
  - All (by design)

PREREQUISITES FOR USE:
  1. Oracle VPS or equivalent
  2. GitHub Private repo for datasets
  3. GPG keypair
  4. Google Colab account
  5. gh CLI on VPS

NEXT STEPS:
  1. راجع ARCHITECTURE.md
  2. جهّز GitHub Private repo
  3. ولّد GPG keypair (انظر SECURITY.md)
  4. على VPS: انسخ scripts + عدّل env vars
  5. افتح Colab notebook واختبره بعينة صغيرة

PERSISTENCE:     OK
