"""Safe compatibility entrypoint for the Gradio application.

The production application must be started through ``deploy/gradio_launcher.py``
so HTTP Basic authentication and the production confidence contract are always
installed.  The implementation lives in ``app_core.py`` and is imported here
for compatibility with code that imports ``hf-space/app.py``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


if __name__ == "__main__":
    raise SystemExit(
        "Direct execution of hf-space/app.py is disabled. "
        "Use deploy/gradio_launcher.py for the authenticated production entrypoint."
    )


_CORE_PATH = Path(__file__).with_name("app_core.py")
_spec = importlib.util.spec_from_file_location("omni_gradio_app_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load Gradio application core from {_CORE_PATH}")

_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Preserve the historical module API used by the production launcher/tests.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

del _name, _core, _spec, _CORE_PATH
