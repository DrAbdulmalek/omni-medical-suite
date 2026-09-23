# Dev image for GitHub Codespaces / devcontainers (AHW planning phase).
# NOTE (documentation phase): this file only takes effect when someone opens a
# Codespace on a branch containing it. No PHI, no credentials, no external
# services beyond standard package indexes. See docs/future/codespaces/.
FROM mcr.microsoft.com/devcontainers/python:3.10-bullseye

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 poppler-utils \
    tesseract-ocr tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
