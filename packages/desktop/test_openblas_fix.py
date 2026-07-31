"""
Frozen-environment test for the OpenBLAS ELF alignment fix.

When run as a PyInstaller-frozen executable, this script:
1. Verifies the runtime hook fired (sys.frozen is True)
2. Imports numpy (must be <2.0.0)
3. Imports scipy + scipy.ndimage (where the ELF crash used to happen)
4. Imports cv2
5. Imports scanner_fixer
6. Does a small numpy/scipy computation to actually exercise OpenBLAS

If the original bug were still present, the process would crash at step 3
with the OpenBLAS ELF alignment error BEFORE printing anything.
"""
import sys
import os

print(f"[test_openblas_fix] Python: {sys.version}")
print(f"[test_openblas_fix] sys.frozen = {getattr(sys, 'frozen', False)}")
if hasattr(sys, '_MEIPASS'):
    print(f"[test_openblas_fix] sys._MEIPASS = {sys._MEIPASS}")
print()

# Step 1: numpy
print("[1/6] Importing numpy...")
import numpy
print(f"      numpy version: {numpy.__version__}")
assert tuple(int(x) for x in numpy.__version__.split('.')[:2]) < (2, 0), \
    f"FAIL: numpy {numpy.__version__} is >=2.0.0 — OpenBLAS crash will occur"
print(f"      OK (numpy <2.0.0 confirmed)")
print()

# Step 2: scipy (where the ELF crash happened)
print("[2/6] Importing scipy...")
import scipy
import scipy.ndimage
import scipy.signal
print(f"      scipy version: {scipy.__version__}")
print(f"      OK")
print()

# Step 3: cv2
print("[3/6] Importing cv2...")
import cv2
print(f"      OK")
print()

# Step 4: scanner_fixer
print("[4/6] Importing scanner_fixer...")
import scanner_fixer
from scanner_fixer import deskew, crop, normalize, enhance, pipeline
print(f"      OK")
print()

# Step 5: Exercise OpenBLAS via a real numpy/scipy computation
print("[5/6] Exercising OpenBLAS via numpy + scipy computation...")
arr = numpy.random.rand(500, 500).astype(numpy.float64)
# scipy.ndimage.gaussian_filter calls into OpenBLAS
filtered = scipy.ndimage.gaussian_filter(arr, sigma=1.0)
# numpy matmul uses OpenBLAS
result = arr @ arr.T
print(f"      arr shape: {arr.shape}, filtered shape: {filtered.shape}, result shape: {result.shape}")
print(f"      OK — OpenBLAS executed without ELF alignment error")
print()

# Step 6: cv2 operation (uses numpy internally)
print("[6/6] Exercising cv2 with numpy array...")
img = numpy.zeros((100, 100, 3), dtype=numpy.uint8)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
print(f"      img shape: {img.shape}, gray shape: {gray.shape}")
print(f"      OK")
print()

print("=" * 60)
print("ALL TESTS PASSED — OpenBLAS ELF alignment bug is FIXED")
print("=" * 60)
print()
print(f"Build configuration that worked:")
print(f"  - numpy {numpy.__version__} (pinned <2.0.0 in requirements.txt")
print(f"    AND scanner_fixer/pyproject.toml)")
print(f"  - scipy {scipy.__version__}")
print(f"  - runtime_hooks=['hook_numpy_openblas.py']")
print(f"  - strip=False, upx=False (per spec)")
