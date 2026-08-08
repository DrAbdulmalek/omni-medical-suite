# ============================================================================
# Scanner Fixer Pro v2.0 - Final Production Dockerfile
# Fixes: huggingface_hub<1.0, pydantic<2.11, gradio_client compatibility
# Supports: Web (Gradio 7860) + Desktop (Tkinter via X11)
# ============================================================================

# ============================================================================
# STAGE 1: Dependencies builder
# ============================================================================
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     libgl1-mesa-glx     libglib2.0-0     libsm6     libxext6     libgomp1     gcc     g++     && rm -rf /var/lib/apt/lists/*

# Create requirements with pinned versions to avoid compatibility issues
RUN cat > requirements.txt << 'EOF'
# Core image processing
opencv-python>=4.8.0,<5.0.0
Pillow>=10.0.0,<11.0.0
numpy>=1.24.0,<2.0.0

# Gradio web interface - pinned for stability
gradio>=4.44.0,<5.0.0
gradio-client>=0.8.0,<1.0.0

# Hugging Face - CRITICAL PINS to avoid HfFolder and pydantic issues
huggingface-hub>=0.19.0,<1.0.0
datasets>=2.14.0,<3.0.0

# Pydantic - MUST be <2.11 to avoid gradio_client crash on boolean JSON schema
# See: gradio-app/gradio#11722
pydantic>=2.0.0,<2.11.0

# Data processing
pandas>=2.0.0,<3.0.0

# Utilities
requests>=2.31.0
EOF

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 2: Final production image
# ============================================================================
FROM python:3.11-slim-bookworm

LABEL maintainer="Dr. Abdulmalek Tamer Al-husseini"
LABEL description="Scanner Fixer Pro v2.0 - Medical Document Image Enhancement"
LABEL version="2.0.0"
LABEL org.opencontainers.image.source="https://github.com/DrAbdulmalek/omni-medical-suite"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     # OpenCV runtime
    libgl1-mesa-glx     libglib2.0-0     libsm6     libxext6     libxrender-dev     libgomp1     # Tkinter + X11 for desktop mode
    python3-tk     tk-dev     libx11-6     libxext-dev     libxinerama-dev     libxi-dev     libxrandr-dev     libxcursor-dev     libxtst-dev     libxft-dev     libfontconfig1     # Arabic fonts
    fonts-noto     fonts-noto-cjk     fonts-noto-color-emoji     fonts-arabeyes     # Utilities
    curl     ca-certificates     && rm -rf /var/lib/apt/lists/*     && apt-get clean     && fc-cache -fv

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create application directories
RUN mkdir -p /app/data /app/output /app/local_dataset_backups /app/logs

# Copy application files (build context = project root)
COPY desktop/desktop_scanner_fixer_pro_v2.py .
COPY desktop/hf_connector.py .
COPY desktop/hf_auto_dataset.py .
COPY desktop/gradio_scanner_app.py .

# Environment variables
ENV HF_TOKEN=""
ENV HF_USERNAME="DrAbdulmalek"
ENV DISPLAY=:0
ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV GRADIO_SERVER_PORT="7860"
ENV GRADIO_ANALYTICS_ENABLED="false"

# Expose Gradio web port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3     CMD curl -sf http://localhost:7860/ || exit 1

# Default: run Gradio web interface
# For desktop mode, override with:
#   docker run -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ... python desktop_scanner_fixer_pro_v2.py
CMD ["python", "gradio_scanner_app.py"]
