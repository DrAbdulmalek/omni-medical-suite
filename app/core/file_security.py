"""Security helpers for filesystem-backed document/image workflows.

The Gradio applications accept filesystem paths because they are also used as
local desktop-style tools. When such an app is exposed remotely, arbitrary
server-side paths become an unintended file-read/write primitive. These
helpers provide a single policy boundary for future upload/batch integrations.
"""

from __future__ import annotations

import os
from pathlib import Path

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pbm", ".pgm",
})

DEFAULT_WORKSPACE = Path.home() / ".omni" / "workspace"


def workspace_root() -> Path:
    """Return the configured filesystem workspace and create it if necessary."""
    root = Path(os.getenv("OMNI_WORKSPACE_DIR", str(DEFAULT_WORKSPACE))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(path: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    """Resolve a path and reject traversal outside the configured workspace."""
    if not path or not str(path).strip():
        raise ValueError("A filesystem path is required")

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace_root() / candidate
    candidate = candidate.resolve(strict=False)
    root = workspace_root()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Filesystem access outside OMNI_WORKSPACE_DIR is not allowed") from exc

    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def validate_image_path(path: str | os.PathLike[str]) -> Path:
    """Validate that a path is an existing regular image file in the workspace."""
    candidate = resolve_workspace_path(path, must_exist=True)
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError("Image path must refer to a regular file")
    if candidate.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {candidate.suffix or '<none>'}")
    return candidate
