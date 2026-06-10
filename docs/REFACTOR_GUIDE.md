# خطة إعادة هيكلة packages/ في omni-medical-suite
## دليل تنفيذي خطوة بخطوة

---

## الوضع الحالي مقابل الهدف

```
الحالي:                          الهدف:
packages/
├── core/          (legacy)      packages/
├── omni-core/     (مكرر)  ───►  ├── core/         (موحّد نهائي)
├── ai/                          ├── ai/
│   └── pattern_db.py  ──────►  ├── learning/
├── learning/                    │   └── pattern_db.py  (مصدر واحد)
│   └── pattern_db.py  (مكرر)   ├── security/
├── security/                    │   ├── encryption.py
│   ├── encryption.py  ────────► │   └── audit_logger.py (مصدر واحد)
│   └── audit_logger.py (مكرر)  ├── audit/
├── audit/                       │   └── audit_logger.py  ← محذوف
│   └── audit_logger.py          └── export/
└── export/                          └── layout_preserving/  (مجلد فقط)
    ├── layout_preserving.py (مكرر)
    └── layout_preserving/
```

---

## الخطوة 1: تهيئة بيئة العمل

```bash
cd /path/to/omni-medical-suite

# احفظ الحالة في git أولاً
git add -A
git commit -m "chore: snapshot before structural refactor"

# شغّل الاختبارات الحالية لتأكيد أنها تعمل قبل التغيير
python -m pytest tests/ -q --tb=no -x
npm run build

# سجّل النتيجة للمقارنة بعد التغيير
echo "Pre-refactor test baseline saved"
```

---

## الخطوة 2: دمج packages/core + packages/omni-core

### 2a. نسخ الملفات الفريدة من omni-core إلى core
```bash
# الملفات الموجودة في omni-core فقط (غير موجودة في core)
UNIQUE_IN_OMNI_CORE=(
  smart_migrator.py
  model_registry.py
  model_manager.py
  corrections_manager.py
  word_trainer.py
  parallel_processor.py
  protected_vocab.py
)

for f in "${UNIQUE_IN_OMNI_CORE[@]}"; do
  if [ -f "packages/omni-core/$f" ]; then
    cp "packages/omni-core/$f" "packages/core/$f"
    echo "✅ Copied: $f"
  fi
done

# انسخ migration/ subdir إذا وجد
if [ -d "packages/omni-core/migration" ]; then
  cp -r packages/omni-core/migration packages/core/migration
fi
```

### 2b. معالجة الملفات المتعارضة
```bash
# engine_router.py — نسخة omni-core أحدث (دمج يدوي مطلوب)
diff packages/core/engine_router.py packages/omni-core/engine_router.py

# انسخ النسخ الجديدة المُسلَّمة في هذه الحزمة
cp omni-dev-v2/structure/packages/core/engine_router.py  packages/core/
cp omni-dev-v2/structure/packages/core/database_manager.py packages/core/
cp omni-dev-v2/structure/packages/core/smart_migrator.py packages/core/
cp omni-dev-v2/structure/packages/core/__init__.py packages/core/
```

### 2c. تحديث جميع الـ imports
```bash
# استبدل كل استيرادات omni-core بـ core
find packages/ apps/ services/ tests/ -name "*.py" | xargs grep -l "omni.core\|omni_core" | while read f; do
  sed -i \
    -e 's/from packages\.omni.core/from packages.core/g' \
    -e 's/from packages\.omni_core/from packages.core/g' \
    -e 's/import packages\.omni.core/import packages.core/g' \
    -e 's/import packages\.omni_core/import packages.core/g' \
    "$f"
  echo "Updated: $f"
done

# تحقق من أنه لم يبق أي استيراد قديم
grep -r "omni.core\|omni_core" packages/ apps/ services/ --include="*.py"
# إذا لم يظهر شيء — الخطوة مكتملة
```

### 2d. حذف packages/omni-core
```bash
# تأكد أولاً أن الاختبارات تمر
python -m pytest tests/ -q --tb=short -x

# ثم احذف
rm -rf packages/omni-core/
echo "✅ packages/omni-core deleted"
```

---

## الخطوة 3: إزالة الملفات المكررة

### 3a. pattern_db — الإبقاء على packages/learning/
```bash
# قارن أولاً
diff packages/ai/pattern_db.py packages/learning/pattern_db.py

# حدّث imports في packages/ai/ التي تستخدمها
find packages/ai/ -name "*.py" | xargs grep -l "pattern_db" | while read f; do
  sed -i 's/from packages\.ai\.pattern_db/from packages.learning.pattern_db/g' "$f"
  sed -i 's/from \.pattern_db/from packages.learning.pattern_db/g' "$f"
done

# احذف النسخة المكررة
rm packages/ai/pattern_db.py
echo "✅ Removed duplicate pattern_db"
```

### 3b. audit_logger — الإبقاء على packages/audit/
```bash
diff packages/security/audit_logger.py packages/audit/audit_logger.py

find packages/security/ services/ -name "*.py" | xargs grep -l "audit_logger" | while read f; do
  sed -i \
    -e 's/from packages\.security\.audit_logger/from packages.audit.audit_logger/g' \
    -e 's/from \.audit_logger/from packages.audit.audit_logger/g' \
    "$f"
done

rm packages/security/audit_logger.py
echo "✅ Removed duplicate audit_logger"
```

### 3c. encryption — الإبقاء على packages/security/
```bash
diff packages/core/encryption.py packages/security/encryption.py

find packages/core/ -name "*.py" | xargs grep -l "encryption" | while read f; do
  sed -i \
    -e 's/from packages\.core\.encryption/from packages.security.encryption/g' \
    -e 's/from \.encryption/from packages.security.encryption/g' \
    "$f"
done

# تأكد أن packages/core/__init__.py لا يُصدّر encryption
# ثم احذف
rm packages/core/encryption.py
echo "✅ Removed duplicate encryption"
```

### 3d. layout_preserving — الإبقاء على المجلد فقط
```bash
# فحص ما إذا كان الملف يحتوي على كود إضافي غير موجود في المجلد
diff packages/export/layout_preserving.py packages/export/layout_preserving/exporter.py 2>/dev/null || true

# حدّث imports
find packages/ apps/ services/ -name "*.py" | xargs grep -l "export\.layout_preserving" | while read f; do
  # استيرادات من الملف المفرد → من المجلد
  sed -i \
    -e 's/from packages\.export\.layout_preserving import LayoutPreservingExporter/from packages.export.layout_preserving.exporter import LayoutPreservingExporter/g' \
    -e 's/from packages\.export\.layout_preserving import/from packages.export.layout_preserving.exporter import/g' \
    "$f"
done

rm packages/export/layout_preserving.py
echo "✅ Removed duplicate layout_preserving.py"
```

---

## الخطوة 4: تنظيف packages/core من البقايا

```bash
# packages/core/api_server.py — بقية legacy لكنها قد تُستخدم
# راجع من يستوردها
grep -r "core.api_server\|core\.api_server" packages/ apps/ services/ --include="*.py"

# إذا لا أحد يستوردها — انقلها إلى legacy/
mkdir -p packages/legacy
mv packages/core/api_server.py packages/legacy/ 2>/dev/null || true
mv packages/core/mistral_integration.py packages/legacy/ 2>/dev/null || true
mv packages/core/document_schemas.py packages/legacy/ 2>/dev/null || true

echo "✅ Legacy files moved to packages/legacy/"
```

---

## الخطوة 5: تحديث packages/core/__init__.py

```bash
# انسخ الملف الجديد المُسلَّم
cp omni-dev-v2/structure/packages/core/__init__.py packages/core/
```

---

## الخطوة 6: تشغيل الاختبارات والتحقق

```bash
# 1. تحقق من عدم وجود imports مكسورة
python -c "
import sys
sys.path.insert(0, '.')
from packages.core import EngineRouter, DatabaseManager
from packages.learning.pattern_db import PatternDatabase
from packages.audit.audit_logger import AuditLogger
from packages.security.encryption import AESEncryption
print('✅ All critical imports OK')
"

# 2. شغّل الاختبارات
python -m pytest tests/ -v --tb=short

# 3. شغّل البناء
npm run build

# 4. Commit
git add -A
git commit -m "refactor: merge omni-core into core, remove 4 duplicate modules

- Merged packages/omni-core/* into packages/core/
- Removed duplicate: packages/ai/pattern_db.py
- Removed duplicate: packages/security/audit_logger.py  
- Removed duplicate: packages/core/encryption.py
- Removed duplicate: packages/export/layout_preserving.py
- Updated all import paths across packages/, apps/, services/
- Added backward-compat shim in packages/core/__init__.py

BREAKING: packages.omni_core.* is now deprecated — use packages.core.*
Downstream: update any external code that imports from omni_core
"
```

---

## الخطوة 7: هيكل المجلدات النهائي المتوقع

```
packages/
├── core/                    ✅ موحّد (من core + omni-core)
│   ├── __init__.py
│   ├── engine_router.py     ← نسخة جديدة محسّنة
│   ├── database_manager.py  ← تدعم PostgreSQL + SQLite
│   ├── smart_migrator.py    ← من omni-core
│   ├── model_registry.py    ← من omni-core
│   ├── model_manager.py     ← من omni-core
│   ├── corrections_manager.py
│   ├── protected_vocab.py
│   ├── word_trainer.py
│   ├── parallel_processor.py
│   ├── spell_checker.py
│   ├── user_manager.py
│   └── migration/
├── ai/                      ✅ بدون pattern_db (حُذف)
├── learning/                ✅ pattern_db.py المرجع الوحيد
├── security/                ✅ encryption + sensitive_data (بدون audit_logger)
├── audit/                   ✅ audit_logger.py المرجع الوحيد
├── export/                  ✅ layout_preserving/ المجلد فقط (الملف حُذف)
├── legacy/                  🗂 ملفات محفوظة مؤقتاً قبل الحذف
└── [بقية المجلدات كما هي]
```

---

## تحقق سريع بعد التنفيذ

```bash
# لا يجب أن يُرجع شيئاً
echo "=== Checking for stale omni-core imports ==="
grep -r "omni.core\|omni_core" packages/ apps/ services/ --include="*.py" | grep -v "__pycache__"

echo "=== Checking for duplicate pattern_db ==="
find packages/ -name "pattern_db.py" | grep -v __pycache__
# يجب أن يظهر: packages/learning/pattern_db.py فقط

echo "=== Checking for duplicate audit_logger ==="
find packages/ -name "audit_logger.py" | grep -v __pycache__
# يجب أن يظهر: packages/audit/audit_logger.py فقط

echo "=== Checking for duplicate encryption ==="
find packages/ -name "encryption.py" | grep -v __pycache__
# يجب أن يظهر: packages/security/encryption.py فقط

echo "=== Done ==="
```
