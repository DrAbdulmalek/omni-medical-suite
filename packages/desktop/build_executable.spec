# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Medical Document Processor (Linux/ELF)
=================================================================
Builds a single-file executable for Manjaro Linux (KDE Plasma).

Usage:
    pyinstaller build_executable.spec --clean

Output: dist/medical-doc-processor
"""

import os
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
SPEC_DIR = Path(SPECPATH)
PACKAGES_DIR = SPEC_DIR.parent  # packages/
SCANNER_FIXER_SRC = PACKAGES_DIR / "scanner_fixer" / "src"

block_cipher = None

a = Analysis(
    [str(SPEC_DIR / 'medical_doc_gui_final.py')],
    pathex=[
        str(SPEC_DIR),                        # desktop/ (for local imports)
        str(SCANNER_FIXER_SRC),               # scanner_fixer/src (for scanner_fixer.*)
    ],
    binaries=[],
    datas=[
        # Include scanner_fixer package data
        (str(SCANNER_FIXER_SRC / 'scanner_fixer'), 'scanner_fixer'),
    ],
    hiddenimports=[
        # scanner_fixer modules
        'scanner_fixer',
        'scanner_fixer.deskew',
        'scanner_fixer.crop',
        'scanner_fixer.normalize',
        'scanner_fixer.enhance',
        'scanner_fixer.dedup',
        'scanner_fixer.text_dedup',
        'scanner_fixer.rotate',
        'scanner_fixer.pipeline',
        'scanner_fixer.batch_pipeline',
        'scanner_fixer.cli',
        'scanner_fixer.enhanced_preprocessor',
        # Image processing
        'cv2',
        'numpy',
        'imagehash',
        'PIL',
        'PIL.Image',
        # OCR (optional)
        'pytesseract',
        # PDF (optional)
        'pdf2image',
        # PySide6
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        # Other dependencies
        'scipy',
        'pywt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(SPEC_DIR / 'hook_numpy_openblas.py'),  # Fix numpy/OpenBLAS ELF alignment
    ],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'IPython',
        'notebook',
        'jupyterlab',
        'pytest',
        # Exclude numpy 2.x problematic modules (only if numpy<2 is used)
        'numpy._core._methods',  # may differ between numpy versions
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='medical-doc-processor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,             # Don't strip — stripping numpy .so files causes alignment issues
    upx=False,               # Don't compress — UPX corrupts numpy/OpenBLAS shared libs
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
