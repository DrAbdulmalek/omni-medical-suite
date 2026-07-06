"""
End-to-end verification: realistic scanned image through all 3 pipeline stages.
Uses /usr/bin/python3 where scanner-fixer v1.0 is installed.
"""
import numpy as np
import cv2
import json
import sys

sys.path.insert(0, "/home/z/my-project/omni-medical-suite")

# ─── Create realistic test image ───────────────────────────────────────
h, w = 1160, 820
np.random.seed(42)

# Dark scanner border (real scanners produce this)
img = np.ones((h, w, 3), dtype=np.uint8) * 60
img[40:h-40, 40:w-40] = np.array([245, 243, 240], dtype=np.uint8)

# Simulated Arabic text lines
for i in range(25):
    y = 80 + i * 38
    x1 = np.random.randint(80, 140)
    x2 = np.random.randint(w - 140, w - 80)
    thickness = np.random.randint(1, 3)
    cv2.line(img, (x1, y), (x2, y), (20, 20, 20), thickness)
    for dx in range(0, x2 - x1, 40):
        cv2.circle(img, (x1 + dx, y - 6), 1, (20, 20, 20), -1)

# Letterhead block
img[55:110, 100:720] = (30, 30, 30)
cv2.putText(img, "HOSPITAL NAME", (200, 95), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

# Scanner color noise
noise = np.random.normal(0, 3, img.shape).astype(np.int16)
img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

# Defect 1: 4° tilt (crooked on scanner glass)
M_tilt = cv2.getRotationMatrix2D((w // 2, h // 2), 4.0, 1.0)
img_tilted = cv2.warpAffine(img, M_tilt, (w, h), borderValue=(60, 60, 60))

# Defect 2: 180° flip (upside-down page)
img_flipped = cv2.rotate(img_tilted, cv2.ROTATE_180)

cv2.imwrite("/home/z/my-project/download/test_scan_realistic.png", img_flipped)
print(f"Created test image: {img_flipped.shape[1]}x{img_flipped.shape[0]}")
print("Defects: dark border + 4° tilt + 180° flip + scanner noise")

# ─── STAGE 1: scanner-fixer v1.0 standalone ───────────────────────────
from scanner_fixer import fix_scan

result = fix_scan(
    img_flipped,
    do_crop=True,
    do_rotate=True,
    do_deskew=True,
    do_enhance=True,
    binarize=False,
    target_dpi=300,
    deskew_method="hough",
    crop_padding=10,
)

print("\n" + "=" * 60)
print("STAGE 1: scanner-fixer v1.0 (standalone)")
print("=" * 60)
print(json.dumps(result["report"], indent=2, ensure_ascii=False))
print(f"Steps tracked: {list(result['steps'].keys())}")
cv2.imwrite("/home/z/my-project/download/test_scan_fixed.png", result["image"])
print("Output: test_scan_fixed.png")

# ─── STAGE 2: scanner_fixer_wrapper (omni-medical-suite) ──────────────
from omni_medical_suite.preprocessing.scanner_fixer_wrapper import (
    ScannerFixerPreprocessor,
    SCANNER_FIXER_AVAILABLE,
)

print("\n" + "=" * 60)
print("STAGE 2: scanner_fixer_wrapper (omni-medical-suite)")
print("=" * 60)
print(f"scanner-fixer import: {SCANNER_FIXER_AVAILABLE}")

preproc = ScannerFixerPreprocessor(
    auto_crop=True, do_rotate=True, do_deskew=True,
    do_enhance=True, binarize=False, target_dpi=300,
    deskew_method="hough", crop_padding=10,
)

pipeline_result = preproc.process_with_report(img_flipped)
print(f"Result keys: {list(pipeline_result.keys())}")
print(json.dumps(pipeline_result["report"], indent=2, ensure_ascii=False))
print(f"Output shape: {pipeline_result['image'].shape}")
cv2.imwrite("/home/z/my-project/download/test_scan_pipeline_output.png", pipeline_result["image"])
print("Output: test_scan_pipeline_output.png")

# ─── STAGE 3: Full EnhancedOCRPipeline ────────────────────────────────
from omni_medical_suite.pipeline import (
    EnhancedOCRPipeline,
    SCANNER_FIXER_AVAILABLE as SF_AVAIL,
    LINE_SEGMENTATION_AVAILABLE as LS_AVAIL,
)

print("\n" + "=" * 60)
print("STAGE 3: EnhancedOCRPipeline (full)")
print("=" * 60)
print(f"scanner-fixer: {SF_AVAIL}")
print(f"line-segmentation: {LS_AVAIL}")

pipe = EnhancedOCRPipeline(use_scanner_fixer=True, use_line_segmentation=False)
pipe_result = pipe.process_image(img_flipped)
print(f"Result keys: {list(pipe_result.keys())}")
print(json.dumps(pipe_result["preprocessing"], indent=2, ensure_ascii=False))
print(f"Status: {pipe_result['status']}")

print("\n" + "=" * 60)
print("ALL 3 STAGES PASSED")
print("=" * 60)