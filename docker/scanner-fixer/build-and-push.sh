#!/bin/bash
# ============================================================================
# Scanner Fixer Pro v2.0 - Build & Push Script
# Builds Docker image and pushes to Docker Hub / GitHub Container Registry
# ============================================================================

set -e

# Configuration
IMAGE_NAME="scanner-fixer-pro"
VERSION="2.0.0"
DOCKER_HUB_USER="${DOCKER_HUB_USER:-drabdulmalek}"
GITHUB_USER="${GITHUB_USER:-DrAbdulmalek}"
GITHUB_REPO="${GITHUB_REPO:-omni-medical-suite}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Scanner Fixer Pro v2.0 - Docker Build${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker not installed${NC}"
    exit 1
fi

# Parse arguments
PUSH_DOCKER_HUB=false
PUSH_GHCR=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --push-dockerhub)
            PUSH_DOCKER_HUB=true
            shift
            ;;
        --push-ghcr)
            PUSH_GHCR=true
            shift
            ;;
        --push-all)
            PUSH_DOCKER_HUB=true
            PUSH_GHCR=true
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--push-dockerhub] [--push-ghcr] [--push-all] [--version X.Y.Z]"
            exit 1
            ;;
    esac
done

# Build image
echo -e "${BLUE}[1/4] Building image...${NC}"
# Resolve project root (2 levels up from docker/scanner-fixer/)
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
docker build -f docker/scanner-fixer/Dockerfile -t "${IMAGE_NAME}:latest" -t "${IMAGE_NAME}:${VERSION}" "$PROJECT_ROOT"

echo -e "${GREEN}[OK] Image built: ${IMAGE_NAME}:${VERSION}${NC}"
echo ""

# Test image
echo -e "${BLUE}[2/4] Testing image...${NC}"
docker run --rm "${IMAGE_NAME}:${VERSION}" python -c "
import cv2
import numpy as np
from PIL import Image
import gradio
print('OpenCV:', cv2.__version__)
print('Gradio:', gradio.__version__)
print('All imports OK')
"
echo -e "${GREEN}[OK] Image test passed${NC}"
echo ""

# Push to Docker Hub
if $PUSH_DOCKER_HUB; then
    echo -e "${BLUE}[3/4] Pushing to Docker Hub...${NC}"
    docker tag "${IMAGE_NAME}:${VERSION}" "${DOCKER_HUB_USER}/${IMAGE_NAME}:${VERSION}"
    docker tag "${IMAGE_NAME}:latest" "${DOCKER_HUB_USER}/${IMAGE_NAME}:latest"
    docker push "${DOCKER_HUB_USER}/${IMAGE_NAME}:${VERSION}"
    docker push "${DOCKER_HUB_USER}/${IMAGE_NAME}:latest"
    echo -e "${GREEN}[OK] Pushed to Docker Hub${NC}"
fi

# Push to GitHub Container Registry
if $PUSH_GHCR; then
    echo -e "${BLUE}[4/4] Pushing to GHCR...${NC}"
    docker tag "${IMAGE_NAME}:${VERSION}" "ghcr.io/${GITHUB_USER}/${GITHUB_REPO}/${IMAGE_NAME}:${VERSION}"
    docker tag "${IMAGE_NAME}:latest" "ghcr.io/${GITHUB_USER}/${GITHUB_REPO}/${IMAGE_NAME}:latest"
    docker push "ghcr.io/${GITHUB_USER}/${GITHUB_REPO}/${IMAGE_NAME}:${VERSION}"
    docker push "ghcr.io/${GITHUB_USER}/${GITHUB_REPO}/${IMAGE_NAME}:latest"
    echo -e "${GREEN}[OK] Pushed to GHCR${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Run locally:"
echo "  docker run -d -p 7860:7860 ${IMAGE_NAME}:${VERSION}"
echo ""
if $PUSH_DOCKER_HUB; then
    echo "Docker Hub:"
    echo "  docker pull ${DOCKER_HUB_USER}/${IMAGE_NAME}:${VERSION}"
fi
if $PUSH_GHCR; then
    echo "GHCR:"
    echo "  docker pull ghcr.io/${GITHUB_USER}/${GITHUB_REPO}/${IMAGE_NAME}:${VERSION}"
fi
