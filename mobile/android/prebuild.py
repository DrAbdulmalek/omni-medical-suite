#!/usr/bin/env python3
"""
prebuild.py — Pre-build hook for buildozer
==========================================
يجري قبل بناء APK. مهامّه:
  1. التحقق من وجود main.py و buildozer.spec.
  2. التأكد من وجود assets/icons/icon.png (إن لم يوجد، يولّد placeholder).
  3. التحقق من حجم النماذج في assets/models/ (تحذير إذا تجاوز 60MB).
  4. توليد version.code من version regex إن لزم.
"""
from pathlib import Path
import sys
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("prebuild")

ROOT = Path(__file__).parent.resolve()

# 1. existence checks
required = ["main.py", "buildozer.spec"]
for f in required:
    if not (ROOT / f).exists():
        log.error("missing required file: %s", f)
        sys.exit(1)
log.info("✓ required files present")

# 2. icon
icons = ROOT / "assets" / "icons"
icons.mkdir(parents=True, exist_ok=True)
icon_path = icons / "icon.png"
presplash_path = icons / "presplash.png"

if not icon_path.exists():
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (512, 512), (14, 124, 123, 255))
        d = ImageDraw.Draw(img)
        # cross symbol (medical)
        d.rectangle([220, 100, 292, 412], fill=(244, 162, 97, 255))
        d.rectangle([100, 220, 412, 292], fill=(244, 162, 97, 255))
        img.save(icon_path)
        log.info("✓ generated placeholder icon.png")
    except Exception as e:
        log.warning("could not generate icon.png: %s", e)

if not presplash_path.exists():
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (1080, 1920), (14, 124, 123, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([440, 600, 640, 1320], fill=(244, 162, 97, 255))
        d.rectangle([200, 860, 880, 1060], fill=(244, 162, 97, 255))
        img.save(presplash_path)
        log.info("✓ generated placeholder presplash.png")
    except Exception as e:
        log.warning("could not generate presplash.png: %s", e)

# 3. models size
models_dir = ROOT / "assets" / "models"
if models_dir.exists():
    total = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
    mb = total / 1024 / 1024
    log.info("models size: %.1f MB", mb)
    if mb > 60:
        log.warning("⚠ models exceed 60MB — APK may exceed 150MB target")
    elif mb == 0:
        log.warning("⚠ no models bundled — APK will require 'Download Models' on first run")

log.info("=== prebuild OK ===")
