#!/usr/bin/env python3
"""
postbuild.py — Post-build hook for buildozer
============================================
يجري بعد بناء APK. مهامّه:
  1. العثور على ملف APK المُولَّد في bin/.
  2. التحقق من الحجم (<150MB).
  3. حساب SHA256.
  4. طباعة ملخص.
"""
from pathlib import Path
import hashlib
import sys
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("postbuild")

ROOT = Path(__file__).parent.resolve()
BIN = ROOT / "bin"

if not BIN.exists():
    log.error("bin/ directory missing — build did not produce output")
    sys.exit(1)

apks = sorted(BIN.glob("*.apk"))
if not apks:
    log.error("no APK found in bin/")
    sys.exit(1)

for apk in apks:
    size_mb = apk.stat().st_size / 1024 / 1024
    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    log.info("━━━ APK ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("name : %s", apk.name)
    log.info("path : %s", apk)
    log.info("size : %.1f MB", size_mb)
    log.info("sha256: %s", sha)
    if size_mb > 150:
        log.warning("⚠ APK exceeds 150MB target — review bundled assets")
    else:
        log.info("✓ size within 150MB target")

log.info("=== postbuild OK ===")
