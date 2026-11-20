"""
PyInstaller runtime hook: fix numpy/OpenBLAS loading in frozen executables.

When PyInstaller bundles numpy 1.x or 2.x, the OpenBLAS shared library
may fail to load with "ELF load command address/offset not page-aligned"
on some Linux kernels (5.18+, especially on Manjaro/Arch).

This hook:
1. Pre-loads the OpenBLAS library before numpy tries to import it
2. Falls back to numpy without OpenBLAS if pre-loading fails
3. Sets environment variables to help numpy find the correct libraries

Works with numpy 1.24.x–1.26.x (recommended) and numpy 2.x (problematic).
"""
import os
import sys

def _fix_numpy_openblas():
    """Attempt to fix numpy/OpenBLAS loading in PyInstaller onefile mode."""
    # Only run in frozen (PyInstaller) mode
    if not getattr(sys, 'frozen', False):
        return

    # The PyInstaller onefile extracts to a temp directory
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        return

    # Strategy 1: Set OPENBLAS_NUM_THREADS to avoid threading issues
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')

    # Strategy 2: Set numpy config to use system BLAS if available
    # This avoids the bundled OpenBLAS entirely
    os.environ.setdefault('NPY_BLAS_ORDER', 'openblas64_')

    # Strategy 3: Find and pre-load the OpenBLAS shared library
    # before numpy tries to load it with dlopen()
    try:
        import ctypes
        import glob

        # Look for OpenBLAS in the extracted PyInstaller directory
        openblas_patterns = [
            os.path.join(base_dir, 'numpy', '.dylibs', '*openblas*'),
            os.path.join(base_dir, 'numpy', '.libs', '*openblas*'),
            os.path.join(base_dir, 'numpy.libs', '*openblas*'),
            os.path.join(base_dir, '*openblas*'),
            os.path.join(base_dir, 'scipy', '.dylibs', '*openblas*'),
            os.path.join(base_dir, 'scipy.libs', '*openblas*'),
        ]

        for pattern in openblas_patterns:
            for lib_path in glob.glob(pattern):
                try:
                    # Pre-load with RTLD_GLOBAL so numpy can find it
                    ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                    return  # Success — numpy should work now
                except OSError:
                    continue
    except Exception:
        pass

    # Strategy 4: If pre-loading failed, try setting LD_PRELOAD
    # (won't help the current process but helps child processes)
    try:
        import glob
        for pattern in openblas_patterns:
            for lib_path in glob.glob(pattern):
                os.environ.setdefault('LD_PRELOAD', lib_path)
                return
    except Exception:
        pass


# Run the fix at import time, before numpy is imported
_fix_numpy_openblas()
