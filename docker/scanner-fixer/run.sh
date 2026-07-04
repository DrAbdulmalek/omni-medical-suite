#!/bin/bash
# ============================================================================
# Scanner Fixer Pro - Docker Runner Script
# Supports Linux, macOS, and Windows (WSL2)
# ============================================================================

set -e

# Colors for output
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
BLUE='[0;34m'
NC='[0m' # No Color

# Default values
MODE="web"
IMAGE_NAME="scanner-fixer-pro"
CONTAINER_NAME="scanner-fixer"

# Detect OS
OS="linux"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
fi

# Help function
show_help() {
    echo -e "${BLUE}Scanner Fixer Pro - Docker Runner${NC}"
    echo ""
    echo "Usage: ./run.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -m, --mode MODE       Run mode: web|desktop|build|shell (default: web)"
    echo "  -t, --token TOKEN     Hugging Face token"
    echo "  -n, --name NAME       Container name (default: scanner-fixer)"
    echo "  -b, --build           Force rebuild image"
    echo "  -h, --help            Show this help"
    echo ""
    echo "Modes:"
    echo "  web       - Run Gradio web interface (port 7860)"
    echo "  desktop   - Run Tkinter GUI (requires X11)"
    echo "  build     - Build image only"
    echo "  shell     - Open shell in container"
    echo ""
    echo "Examples:"
    echo "  ./run.sh -m web -t hf_xxxxxxxx"
    echo "  ./run.sh -m desktop"
    echo "  ./run.sh --build"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -t|--token)
            export HF_TOKEN="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -b|--build)
            BUILD_FLAG="--build"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# ============================================================================
# BUILD IMAGE
# ============================================================================
build_image() {
    echo -e "${BLUE}Building Docker image...${NC}"
    # Resolve project root (2 levels up from docker/scanner-fixer/)
    PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
    docker build -f docker/scanner-fixer/Dockerfile -t "$IMAGE_NAME" "$PROJECT_ROOT" --target final
    echo -e "${GREEN}Image built successfully!${NC}"
}

# ============================================================================
# WEB MODE (Gradio)
# ============================================================================
run_web() {
    echo -e "${BLUE}Starting Scanner Fixer Pro - Web Mode${NC}"
    echo -e "${YELLOW}Access at: http://localhost:7860${NC}"

    docker run -d         --name "$CONTAINER_NAME"         -p 7860:7860         -e HF_TOKEN="${HF_TOKEN:-}"         -e HF_USERNAME="${HF_USERNAME:-DrAbdulmalek}"         -e GRADIO_SERVER_NAME=0.0.0.0         -e GRADIO_SERVER_PORT=7860         -v "$(pwd)/data:/app/data"         -v "$(pwd)/output:/app/output"         -v "$(pwd)/local_dataset_backups:/app/local_dataset_backups"         --restart unless-stopped         "$IMAGE_NAME"         python gradio_scanner_app.py

    echo -e "${GREEN}Container started: $CONTAINER_NAME${NC}"
    echo -e "${GREEN}Logs: docker logs -f $CONTAINER_NAME${NC}"
}

# ============================================================================
# DESKTOP MODE (Tkinter via X11)
# ============================================================================
run_desktop() {
    echo -e "${BLUE}Starting Scanner Fixer Pro - Desktop Mode${NC}"

    # Setup X11 based on OS
    if [[ "$OS" == "linux" ]]; then
        # Linux: use host X11 socket
        xhost +local:docker 2>/dev/null || true
        X11_FLAGS="-e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw"

    elif [[ "$OS" == "macos" ]]; then
        # macOS: requires XQuartz
        if ! command -v xquartz &> /dev/null; then
            echo -e "${RED}XQuartz not found. Install from: https://www.xquartz.org/${NC}"
            exit 1
        fi

        # Start XQuartz if not running
        open -a XQuartz
        sleep 2

        # Allow connections
        xhost + $(hostname) 2>/dev/null || xhost + 2>/dev/null

        # Get IP address
        IP=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}')
        export DISPLAY="$IP:0"
        X11_FLAGS="-e DISPLAY=$DISPLAY"

    elif [[ "$OS" == "windows" ]]; then
        # Windows: requires VcXsrv or similar
        echo -e "${YELLOW}Windows detected. Ensure VcXsrv is running.${NC}"
        echo -e "${YELLOW}Set DISPLAY environment variable before running.${NC}"
        X11_FLAGS="-e DISPLAY=$DISPLAY"
    fi

    docker run -it --rm         --name "$CONTAINER_NAME-desktop"         $X11_FLAGS         -e HF_TOKEN="${HF_TOKEN:-}"         -e HF_USERNAME="${HF_USERNAME:-DrAbdulmalek}"         -v "$(pwd)/data:/app/data"         -v "$(pwd)/output:/app/output"         -v "$(pwd)/local_dataset_backups:/app/local_dataset_backups"         "$IMAGE_NAME"         python desktop_scanner_fixer_pro_v2.py
}

# ============================================================================
# SHELL MODE
# ============================================================================
run_shell() {
    echo -e "${BLUE}Opening shell in container...${NC}"
    docker run -it --rm         --name "$CONTAINER_NAME-shell"         -e HF_TOKEN="${HF_TOKEN:-}"         -v "$(pwd)/data:/app/data"         -v "$(pwd)/output:/app/output"         "$IMAGE_NAME"         /bin/bash
}

# ============================================================================
# MAIN
# ============================================================================

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker first.${NC}"
    exit 1
fi

# Build image if needed or requested
if [[ "$MODE" == "build" ]] || [[ -n "$BUILD_FLAG" ]] || ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    build_image
fi

# Stop existing container if running
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo -e "${YELLOW}Stopping existing container...${NC}"
    docker stop "$CONTAINER_NAME" &> /dev/null || true
    docker rm "$CONTAINER_NAME" &> /dev/null || true
fi

# Run based on mode
case "$MODE" in
    web)
        run_web
        ;;
    desktop)
        run_desktop
        ;;
    build)
        echo -e "${GREEN}Build complete!${NC}"
        ;;
    shell)
        run_shell
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        show_help
        exit 1
        ;;
esac
