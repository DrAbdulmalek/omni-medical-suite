#!/bin/bash
# ============================================================================
# Medical Document Processor - Setup Script
# الميزات 1-7: إصلاح Core + FastAPI + Encryption + SQLite + Docker
# ============================================================================

set -euo pipefail

# الألوان
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# متغيرات
PROJECT_ROOT="$(pwd)"
CORE_DIR="$PROJECT_ROOT/packages/core"
DESKTOP_DIR="$PROJECT_ROOT/packages/desktop"
PRISMA_DIR="$PROJECT_ROOT/prisma"
LOG_FILE="$PROJECT_ROOT/setup_medical.log"

# دوال مساعدة
log_info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"; }
log_warn() { echo -e "${YELLOW}[⚠]${NC} $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"; }
log_step() { echo -e "\n${CYAN}${BOLD}▶ $1${NC}" | tee -a "$LOG_FILE"; }

# ============================================================================
# 0. التحقق من المتطلبات المسبقة
# ============================================================================
check_prerequisites() {
    log_step "التحقق من المتطلبات المسبقة"

    local missing=()

    # Python 3.11+
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
        log_success "Python موجود: $PY_VER"
    else
        missing+=("python3")
    fi

    # pip
    if ! command -v pip3 &>/dev/null; then
        missing+=("pip3")
    fi

    # Node.js 18+
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VER" -ge 18 ]; then
            log_success "Node.js موجود: $(node --version)"
        else
            log_warn "Node.js إصدار قديم (يجب >= 18)"
        fi
    else
        missing+=("node")
    fi

    # Bun
    if command -v bun &>/dev/null; then
        log_success "Bun موجود: $(bun --version)"
    else
        missing+=("bun")
        log_warn "Bun غير مثبت. التثبيت عبر: curl -fsSL https://bun.sh/install | bash"
    fi

    # Tesseract
    if command -v tesseract &>/dev/null; then
        log_success "Tesseract موجود: $(tesseract --version 2>&1 | head -1)"
        # التحقق من اللغة العربية
        if tesseract --list-langs 2>/dev/null | grep -q "ara"; then
            log_success "اللغة العربية (ara) متوفرة في Tesseract"
        else
            log_warn "اللغة العربية غير مثبتة في Tesseract. ثبتها عبر:"
            log_warn "  Ubuntu: sudo apt install tesseract-ocr-ara"
            log_warn "  macOS: brew install tesseract-lang"
        fi
    else
        missing+=("tesseract-ocr")
    fi

    # Docker (اختياري)
    if command -v docker &>/dev/null; then
        log_success "Docker موجود"
        if command -v docker-compose &>/dev/null || docker compose version &>/dev/null; then
            log_success "Docker Compose موجود"
        else
            log_warn "Docker Compose غير موجود (اختياري للميزة 7)"
        fi
    else
        log_warn "Docker غير مثبت (اختياري للميزة 7)"
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "المتطلبات التالية ناقصة: ${missing[*]}"
        echo ""
        echo "تثبيت سريع (Ubuntu/Debian):"
        echo "  sudo apt update"
        echo "  sudo apt install -y python3 python3-pip tesseract-ocr tesseract-ocr-ara"
        echo ""
        echo "تثبيت Bun:"
        echo "  curl -fsSL https://bun.sh/install | bash"
        exit 1
    fi

    log_success "جميع المتطلبات الأساسية متوفرة!"
}

# ============================================================================
# 1. إنشاء هيكل المجلدات
# ============================================================================
setup_directories() {
    log_step "إنشاء هيكل المجلدات"

    mkdir -p "$CORE_DIR"
    mkdir -p "$DESKTOP_DIR/src/main"
    mkdir -p "$DESKTOP_DIR/src/preload"
    mkdir -p "$PRISMA_DIR"
    mkdir -p "$PROJECT_ROOT/.github/workflows"

    log_success "تم إنشاء المجلدات"
}

# ============================================================================
# 2. نسخ ملفات Python Core (الميزات 1, 2, 4, 5)
# ============================================================================
setup_python_core() {
    log_step "إعداد Python Core (الميزات 1, 2, 4, 5)"

    # نسخ الملفات من /mnt/agents/output
    local files=(
        "image_processor.py"
        "api_server_v2.py:api_server.py"
        "db_manager.py"
        "encryption.py"
        "test_core.py"
        "requirements_v2.txt:requirements.txt"
    )

    for item in "${files[@]}"; do
        local src="${item%%:*}"
        local dst="${item##*:}"
        local src_path="/mnt/agents/output/$src"
        local dst_path="$CORE_DIR/$dst"

        if [ -f "$src_path" ]; then
            # نسخ احتياطي للملف القديم
            if [ -f "$dst_path" ]; then
                cp "$dst_path" "$dst_path.backup.$(date +%s)" 2>/dev/null || true
            fi
            cp "$src_path" "$dst_path"
            log_success "نسخ: $src → packages/core/$dst"
        else
            log_warn "الملف المصدر غير موجود: $src_path"
        fi
    done

    # تثبيت التبعيات
    log_info "تثبيت تبعيات Python..."
    cd "$CORE_DIR"
    pip3 install -r requirements.txt --quiet 2>&1 | tee -a "$LOG_FILE"
    log_success "تم تثبيت تبعيات Python"
}

# ============================================================================
# 3. نسخ ملفات Electron (الميزة 3)
# ============================================================================
setup_electron() {
    log_step "إعداد Electron Bridge (الميزة 3)"

    # نسخ ملفات TypeScript
    local ts_files=(
        "python-bridge.ts:$DESKTOP_DIR/src/main/python-bridge.ts"
        "db.ts:$DESKTOP_DIR/src/main/db.ts"
    )

    for item in "${ts_files[@]}"; do
        local src="${item%%:*}"
        local dst="${item##*:}"
        local src_path="/mnt/agents/output/$src"

        if [ -f "$src_path" ]; then
            if [ -f "$dst" ]; then
                cp "$dst" "$dst.backup.$(date +%s)" 2>/dev/null || true
            fi
            cp "$src_path" "$dst"
            log_success "نسخ: $src → $dst"
        else
            log_warn "الملف المصدر غير موجود: $src_path"
        fi
    done

    # تثبيت تبعيات Bun
    if [ -d "$DESKTOP_DIR" ] && [ -f "$DESKTOP_DIR/package.json" ]; then
        log_info "تثبيت تبعيات Electron..."
        cd "$DESKTOP_DIR"
        bun add axios form-data 2>&1 | tee -a "$LOG_FILE" || npm install axios form-data 2>&1 | tee -a "$LOG_FILE"
        log_success "تم تثبيت axios و form-data"
    else
        log_warn "مجلد packages/desktop غير موجود أو لا يحتوي package.json"
    fi
}

# ============================================================================
# 4. إعداد Prisma Schema (الميزة 6)
# ============================================================================
setup_prisma() {
    log_step "إعداد Prisma Schema (الميزة 6)"

    local src="/mnt/agents/output/schema.prisma"
    local dst="$PRISMA_DIR/schema.prisma"

    if [ -f "$src" ]; then
        if [ -f "$dst" ]; then
            cp "$dst" "$dst.backup.$(date +%s)"
        fi
        cp "$src" "$dst"
        log_success "نسخ: schema.prisma → prisma/"
    fi

    # إنشاء .env.local إذا لم يكن موجوداً
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Medical Document Processor - Environment
DATABASE_URL="file:./db/dev.db"
PYTHON_CORE_PORT=0
ENCRYPTION_KEY="change_this_in_production"
EOF
        log_success "تم إنشاء .env.local"
    else
        log_warn ".env.local موجود مسبقاً (لم يُعدل)"
    fi

    # إنشاء db directory
    mkdir -p "$PROJECT_ROOT/db"

    # محاولة دفع Prisma schema إذا كان Bun/Prisma متوفر
    if command -v bun &>/dev/null && [ -f "$PROJECT_ROOT/package.json" ]; then
        log_info "محاولة دفع Prisma schema..."
        cd "$PROJECT_ROOT"
        bun run db:push 2>&1 | tee -a "$LOG_FILE" || log_warn "فشل db:push (قد تحتاج تثبيت Prisma CLI)"
    fi
}

# ============================================================================
# 5. تشغيل اختبارات Python (الميزة 4)
# ============================================================================
run_tests() {
    log_step "تشغيل اختبارات Python Core (الميزة 4)"

    cd "$CORE_DIR"

    if command -v pytest &>/dev/null; then
        pytest test_core.py -v --tb=short 2>&1 | tee -a "$LOG_FILE"
        local pytest_exit=${PIPESTATUS[0]}

        if [ $pytest_exit -eq 0 ]; then
            log_success "جميع الاختبارات نجحت!"
        else
            log_error "بعض الاختبارات فشلت (exit code: $pytest_exit)"
            log_warn "تحقق من $LOG_FILE للتفاصيل"
        fi
    else
        log_warn "pytest غير مثبت، جاري التثبيت..."
        pip3 install pytest --quiet
        pytest test_core.py -v --tb=short 2>&1 | tee -a "$LOG_FILE"
    fi
}

# ============================================================================
# 6. اختبار FastAPI يدوياً (الميزة 2)
# ============================================================================
test_fastapi() {
    log_step "اختبار FastAPI Server (الميزة 2)"

    cd "$CORE_DIR"

    # تشغيل الخادم في الخلفية
    log_info "تشغيل Python Core API على منفذ عشوائي..."
    python3 api_server.py --port 8765 &
    local server_pid=$!

    # انتظار الخادم
    sleep 3

    # اختبار health endpoint
    if curl -s http://127.0.0.1:8765/health | grep -q "ok"; then
        log_success "✅ FastAPI يعمل! (PID: $server_pid)"
        log_info "Swagger UI: http://127.0.0.1:8765/docs"

        # اختبار قاعدة البيانات
        curl -s -X POST http://127.0.0.1:8765/db/init             -H "Content-Type: application/json"             -d '{"db_path":"/tmp/test_medical_setup.db","encryption_password":"TestPIN123"}' |             grep -q "success" && log_success "✅ DB init يعمل!"

        # إيقاف الخادم
        kill $server_pid 2>/dev/null || true
        wait $server_pid 2>/dev/null || true
        log_success "تم إيقاف خادم الاختبار"
    else
        log_error "❌ FastAPI لم يستجب"
        kill $server_pid 2>/dev/null || true
    fi
}

# ============================================================================
# 7. Docker Setup (الميزة 7)
# ============================================================================
setup_docker() {
    log_step "إعداد Docker (الميزة 7)"

    if ! command -v docker &>/dev/null; then
        log_warn "Docker غير مثبت، تخطي هذه الخطوة"
        return 0
    fi

    local dockerfiles=("Dockerfile" "docker-compose.yml")
    for f in "${dockerfiles[@]}"; do
        local src="/mnt/agents/output/$f"
        local dst="$PROJECT_ROOT/$f"
        if [ -f "$src" ]; then
            cp "$src" "$dst"
            log_success "نسخ: $f → $dst"
        fi
    done

    # بناء الصورة
    log_info "بناء صورة Docker..."
    cd "$PROJECT_ROOT"
    if docker-compose build 2>&1 | tee -a "$LOG_FILE"; then
        log_success "✅ تم بناء صورة Docker بنجاح"
        log_info "للتشغيل: docker-compose up -d python-core"
    else
        log_warn "فشل بناء Docker (قد تحتاج إعدادات إضافية)"
    fi
}

# ============================================================================
# 8. إنشاء package.json scripts
# ============================================================================
update_package_json() {
    log_step "تحديث package.json"

    local pkg="$PROJECT_ROOT/package.json"
    if [ -f "$pkg" ]; then
        # إنشاء نسخة احتياطية
        cp "$pkg" "$pkg.backup.$(date +%s)"

        # إضافة scripts إذا لم تكن موجودة (باستخدام node)
        if command -v node &>/dev/null; then
            node -e "
                const fs = require('fs');
                const pkg = JSON.parse(fs.readFileSync('$pkg', 'utf8'));
                pkg.scripts = pkg.scripts || {};
                pkg.scripts['test:core'] = pkg.scripts['test:core'] || 'cd packages/core && pytest test_core.py -v';
                pkg.scripts['core:dev'] = pkg.scripts['core:dev'] || 'cd packages/core && python api_server.py --port 8000';
                pkg.scripts['core:docker'] = pkg.scripts['core:docker'] || 'docker-compose up -d python-core';
                fs.writeFileSync('$pkg', JSON.stringify(pkg, null, 2));
                console.log('✅ package.json تم تحديثه');
            " 2>/dev/null && log_success "تم تحديث package.json" || log_warn "تعذر تحديث package.json تلقائياً"
        fi
    else
        log_warn "package.json غير موجود في جذر المشروع"
    fi
}

# ============================================================================
# 9. تقرير نهائي
# ============================================================================
final_report() {
    log_step "التقرير النهائي"

    echo ""
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║     تم إعداد Medical Document Processor بنجاح!          ║${NC}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}📁 الملفات المُنشأة:${NC}"
    echo "   packages/core/image_processor.py    ← إصلاح Deskew/Blur/Borders"
    echo "   packages/core/api_server.py         ← FastAPI + DB + Encryption"
    echo "   packages/core/db_manager.py         ← SQLite WAL Manager"
    echo "   packages/core/encryption.py          ← AES-256-GCM"
    echo "   packages/core/test_core.py          ← اختبارات الوحدة"
    echo "   packages/core/requirements.txt      ← تبعيات Python"
    echo "   packages/desktop/src/main/python-bridge.ts  ← Electron Bridge"
    echo "   packages/desktop/src/main/db.ts     ← Electron DB Module"
    echo "   prisma/schema.prisma                ← Prisma Schema"
    echo "   Dockerfile                          ← Docker Image"
    echo "   docker-compose.yml                  ← Docker Compose"
    echo ""
    echo -e "${CYAN}⚡ الأوامر السريعة:${NC}"
    echo "   bun run test:core          ← تشغيل اختبارات Python"
    echo "   bun run core:dev           ← تشغيل Python Core محلياً"
    echo "   bun run core:docker        ← تشغيل Python Core عبر Docker"
    echo "   python packages/core/api_server.py --port 8000"
    echo ""
    echo -e "${CYAN}🔗 نقاط النهاية المتاحة:${NC}"
    echo "   GET  /health              ← فحص الصحة"
    echo "   POST /process             ← معالجة صورة"
    echo "   POST /batch               ← معالجة دفعة"
    echo "   POST /db/init             ← تهيئة قاعدة البيانات"
    echo "   POST /db/documents        ← إدراج مستند"
    echo "   GET  /db/documents        ← قائمة المستندات"
    echo ""
    echo -e "${CYAN}📋 الخطوات التالية:${NC}"
    echo "   1. عدّل packages/desktop/src/main/main.ts لاستيراد PythonBridge"
    echo "   2. أضف preload script في packages/desktop/src/preload.ts"
    echo "   3. جرّب: curl http://localhost:8000/health"
    echo ""
    echo -e "${YELLOW}📄 السجل الكامل محفوظ في: $LOG_FILE${NC}"
    echo ""
}

# ============================================================================
# Main
# ============================================================================
main() {
    echo -e "${CYAN}${BOLD}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║    Medical Document Processor - Automated Setup            ║"
    echo "║    الميزات 1-7: Core + FastAPI + Encryption + SQLite      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # إنشاء ملف السجل
    echo "Setup started at $(date)" > "$LOG_FILE"

    check_prerequisites
    setup_directories
    setup_python_core
    setup_electron
    setup_prisma
    run_tests
    test_fastapi
    setup_docker
    update_package_json
    final_report

    echo "Setup completed at $(date)" >> "$LOG_FILE"
}

# تشغيل
main "$@"
