#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_pipeline.py — Unified entry point for OmniMedical Suite.

Integrates: Redis Cache → WebSocket → FusionV3 → AutoPromotion → Benchmark

Usage:
    python main_pipeline.py              # Local demo (Redis + WS + Pipeline)
    python main_pipeline.py --mode colab # Colab mode (lightweight, no services)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project modules are importable
sys.path.insert(0, str(Path(__file__).parent / "services" / "api"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("omni.pipeline")


def run_local_demo() -> None:
    """Start all services locally: Redis, WebSocket, and the processing pipeline."""
    logger.info("Starting OmniMedical Unified Pipeline (local mode)...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 1. Redis (optional — skip if not available)
    try:
        from app.core.medical_redis import MedicalRedisServer
        redis_srv = MedicalRedisServer(host="127.0.0.1", port=6380)
        loop.run_in_executor(None, redis_srv.start)
        logger.info("[redis] Starting custom Redis on port 6380...")
        time.sleep(1)
    except Exception as exc:
        logger.warning("[redis] Skipping (not available): %s", exc)

    # 2. WebSocket (optional — skip if not available)
    try:
        from app.core.medical_websocket_server import MedicalWebSocketServer
        ws_srv = MedicalWebSocketServer(port=8765)
        loop.run_in_executor(None, lambda: loop.run_until_complete(ws_srv.start()))
        logger.info("[websocket] Starting WebSocket server on port 8765...")
        time.sleep(1)
    except Exception as exc:
        logger.warning("[websocket] Skipping (not available): %s", exc)

    # 3. Pipeline
    logger.info("[pipeline] Processing pipeline ready.")
    logger.info("[pipeline] In production, connect via FastAPI endpoints or PyQt5 GUI.")

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        loop.stop()


def run_colab_mode() -> None:
    """Lightweight Colab mode — loads models without starting background services."""
    logger.info("OmniMedical Suite — Colab Mode")
    logger.info("Loading lightweight models for notebook use...")

    try:
        from app.vision.ocr_fusion_system import OCRFusionV2
        fusion = OCRFusionV2()
        logger.info("[fusion] Fusion V2 engine ready.")
    except Exception as exc:
        logger.warning("[fusion] Not available: %s", exc)

    try:
        from app.evaluation.benchmark_suite import BenchmarkSuite
        bench = BenchmarkSuite()
        logger.info("[benchmark] BenchmarkSuite ready.")
    except Exception as exc:
        logger.warning("[benchmark] Not available: %s", exc)

    logger.info("Ready. Use `fusion.fuse(results, img)` to process documents.")


def main() -> None:
    parser = argparse.ArgumentParser(description="OmniMedical Suite Pipeline")
    parser.add_argument(
        "--mode",
        choices=["local", "colab", "auto"],
        default="auto",
        help="Run mode: local (full services), colab (lightweight), auto (detect)",
    )
    args = parser.parse_args()

    if args.mode == "auto":
        is_colab = "COLAB_GPU" in os.environ or "COLAB_TPU_ADDR" in os.environ
        mode = "colab" if is_colab else "local"
    else:
        mode = args.mode

    if mode == "colab":
        run_colab_mode()
    else:
        run_local_demo()


if __name__ == "__main__":
    main()
