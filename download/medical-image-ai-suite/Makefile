.PHONY: help install test test-infra test-dict clean preprocess train generate report all infra-up infra-down gradio-lab gradio-fusion

# ===== المتغيرات =====
PYTHON := python
PIP := pip
DATA_DIR := ./data
CONFIG := ./configs/config.yaml

help: ## عرض المساعدة
        @echo "Medical Image AI Suite - أوامر التحكم"
        @echo "==============================="
        @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## تثبيت التبعيات
        $(PIP) install -r requirements.txt
        $(PYTHON) -c "import torch; print(f'PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}')"

clean: ## تنظيف الملفات المؤقتة
        find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete
        rm -rf $(DATA_DIR)/processed/*
        rm -rf $(DATA_DIR)/synthetic/*
        rm -rf models/*
        rm -rf logs/*

# ===== المرحلة 1: المعالجة المسبقة =====
preprocess: ## معالجة وتوحيد البيانات
        $(PYTHON) main_pipeline.py --phase 1 \
                --config $(CONFIG) \
                --input $(DATA_DIR)/raw \
                --output $(DATA_DIR)/processed

preprocess-dicom: ## معالجة ملفات DICOM فقط
        $(PYTHON) main_pipeline.py --phase 1 \
                --modality dicom \
                --input $(DATA_DIR)/raw \
                --output $(DATA_DIR)/processed

preprocess-jpg: ## معالجة ملفات JPG فقط
        $(PYTHON) main_pipeline.py --phase 1 \
                --modality jpg \
                --input $(DATA_DIR)/raw \
                --output $(DATA_DIR)/processed

preprocess-3d: ## معالجة الشرائح كبيانات 3D
        $(PYTHON) main_pipeline.py --phase 1 \
                --volume \
                --input $(DATA_DIR)/raw \
                --output $(DATA_DIR)/processed

# ===== المرحلة 2: التدريب شبه الخاضع للإشراف =====
extract-ner: ## استخراج الكيانات الطبية من التقارير
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode ner \
                --input $(DATA_DIR)/reports \
                --output $(DATA_DIR)/labels

extract-labels: ## استخراج الإشارات الضعيفة
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode labels \
                --input $(DATA_DIR)/reports \
                --output $(DATA_DIR)/labels

train: ## تدريب النموذج شبه الخاضع للإشراف
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode train \
                --config $(CONFIG)

train-classifier: ## تدريب المصنف فقط
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode train \
                --task classification \
                --config $(CONFIG)

train-segmentor: ## تدريب مقسم الشرائح فقط
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode train \
                --task segmentation \
                --config $(CONFIG)

evaluate: ## تقييم النموذج
        $(PYTHON) main_pipeline.py --phase 2 \
                --mode evaluate \
                --config $(CONFIG)

# ===== المرحلة 3: توليد البيانات الاصطناعية =====
generate: ## توليد صور اصطناعية
        $(PYTHON) main_pipeline.py --phase 3 \
                --mode generate \
                --config $(CONFIG) \
                --num 100

generate-interactive: ## توليد صور اصطناعية تفاعلياً
        $(PYTHON) main_pipeline.py --phase 3 \
                --mode generate \
                --interactive \
                --config $(CONFIG)

# ===== المرحلة 4: توليد التقارير =====
report: ## توليد تقرير من صورة
        $(PYTHON) main_pipeline.py --phase 4 \
                --input $(DATA_DIR)/processed \
                --output $(DATA_DIR)/reports/generated \
                --config $(CONFIG)

report-batch: ## توليد تقارير بشكل جماعي
        $(PYTHON) main_pipeline.py --phase 4 \
                --mode batch \
                --input $(DATA_DIR)/processed \
                --output $(DATA_DIR)/reports/generated \
                --config $(CONFIG)

# ===== أوامر متنوعة =====
test: ## تشغيل الاختبارات
        $(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html

test-fast: ## تشغيل الاختبارات السريعة
        $(PYTHON) -m pytest tests/ -v -k "fast"

quality: ## فحص جودة الكود
        black --check src/ tests/
        flake8 src/ tests/
        mypy src/

format: ## تنسيق الكود
        black src/ tests/

all: preprocess extract-ner extract-labels train generate report ## تشغيل كامل

# ===== البنية التحتية (Build Your Own X) =====
infra-up: ## تشغيل البنية التحتية المخصصة (Redis + WebSocket + LB)
        $(PYTHON) services/infra/medical_redis.py &
        $(PYTHON) services/infra/medical_websocket.py &
        $(PYTHON) services/infra/medical_lb.py &
        @echo "البنية التحتية تعمل: Redis(:6380) + WebSocket(:8765) + LB(:8080)"

infra-down: ## إيقاف البنية التحتية
        @pkill -f medical_redis.py || true
        @pkill -f medical_websocket.py || true
        @pkill -f medical_lb.py || true
        @echo "تم إيقاف البنية التحتية"

test-infra: ## اختبار البنية التحتية
        $(PYTHON) -m pytest tests/test_infrastructure.py -v

test-dict: ## اختبار القاموس الطبي
        $(PYTHON) -m pytest tests/test_dictionary.py -v

test-all: test test-infra test-dict ## تشغيل جميع الاختبارات

gradio-lab: ## تشغيل واجهة Gradio للمرحلة 2 المتقدمة
        $(PYTHON) gradio_phase2_enhanced.py

gradio-fusion: ## تشغيل مختبر Fusion V3
        $(PYTHON) omni_gradio_fusion_v3.py

docker-up: ## تشغيل البنية بالحاويات
        docker compose -f docker-compose.medical-infra.yml up -d

docker-down: ## إيقاف الحاويات
        docker compose -f docker-compose.medical-infra.yml down

docker-logs: ## عرض سجلات الحاويات
        docker compose -f docker-compose.medical-infra.yml logs -f

manager: ## تشغيل المنسق المركزي
        $(PYTHON) services/core/omni_manager.py

# ===== الأوامر الافتراضية =====
.DEFAULT_GOAL := help
