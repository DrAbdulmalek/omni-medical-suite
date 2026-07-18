"""
scanner_fixer
=============

Image-correction pipeline for scanned medical documents.

Public API
----------
- ``fix_scanned_image(input_source, output_path=None)`` -> (np.ndarray, dict)
- ``batch_fix_folder(folder, output_dir=None)`` -> list[dict]
- ``detect_edges_strong(image)``
- ``text_aware_auto_crop(image)``
- ``auto_rotate_strong(image)``
"""

from .core import (
    fix_scanned_image,
    batch_fix_folder,
    detect_edges_strong,
    text_aware_auto_crop,
    auto_rotate_strong,
)

__all__ = [
    "fix_scanned_image",
    "batch_fix_folder",
    "detect_edges_strong",
    "text_aware_auto_crop",
    "auto_rotate_strong",
]

__version__ = "2.1.0"
