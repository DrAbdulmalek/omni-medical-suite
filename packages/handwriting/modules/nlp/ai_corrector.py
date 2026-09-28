"""Consolidation shim (2026-09-21, PR consolidation of ai_corrector.py).

The five byte-identical copies of this module were consolidated into the
canonical implementation at ``packages/nlp/ai_corrector.py`` (md5
2f53a5ea6dd82944e6fe42eddc9a217f, 393 lines).  This file is now a thin
re-export so that existing imports

    from modules.nlp.ai_corrector import AICorrector

keep working unchanged.  Evidence for the consolidation (pairwise byte
comparison, import-site map, no standalone-deploy consumers) is recorded in
docs/portfolio/PORTFOLIO_TRUTH.md and the consolidating pull request.

If ``packages.nlp`` is not importable in your runtime (e.g. a standalone
deployment that never had the monorepo root on ``sys.path``), the import
raises ImportError and the surrounding try/except in ``modules/nlp/__init__``
degrades to ``AICorrector = None`` exactly as it did for missing optional
dependencies before the consolidation.
"""

__all__ = ["AICorrector"]

try:
    from packages.nlp.ai_corrector import AICorrector
except ImportError as _exc:  # pragma: no cover - depends on runtime sys.path
    raise ImportError(
        "modules.nlp.ai_corrector is now a re-export of "
        "packages.nlp.ai_corrector (consolidation 2026-09-21). "
        "Run from the monorepo root or add it to sys.path. "
        f"Original error: {_exc}"
    ) from _exc
