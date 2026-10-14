"""License gate for the Readiris teacher pipeline.

Readiris (IRIS/Canon) is proprietary software. This package consumes only
the text exports (TXT/HTML/RTF) produced by a locally licensed (or official
trial) copy that the repository owner runs on their own documents. To keep
that boundary explicit and auditable, every CLI command that ingests a
Readiris export must clear this gate:

1. CLI flag  ``--i-own-license``   (an explicit per-run declaration), AND
2. environment variable      ``READIRIS_LICENSE_CONFIRMED=1``

This gate is deliberately stricter than the ABBYY teacher's (which relies on
documentation alone): Readiris has no documented public XML layout dialect,
so the "consume exports only" boundary is the only legal line, and we make
the operator assert it on every run.
"""

from __future__ import annotations

import os

LICENSE_ENV_VAR = "READIRIS_LICENSE_CONFIRMED"

LICENSE_NOTICE = (
    "[license-gate] This tool only consumes text exports (TXT/HTML/RTF) of a "
    "Readiris copy you are licensed to run locally (paid licence or official "
    "IRIS trial). It never ships, downloads or embeds Readiris binaries, "
    "installers, serials or weights - and no such artefact may be committed "
    "to any repository.\n"
    "[بوابة الترخيص] تستهلك هذه الأداة مخرجات نصية فقط من نسخة Readiris "
    "مرخصة أو تجريبية رسمية تعمل بها محلياً؛ ولا تُشحن أو تنزّل أي ثنائيات "
    "أو مثبتات أو أرقام تسلسلية من البرنامج نفسه.\n"
    "Re-run with: --i-own-license  AND  READIRIS_LICENSE_CONFIRMED=1\n"
    "Official trial: https://www.irislink.com"
)


class LicenseGateError(RuntimeError):
    """Raised when a command tries to ingest Readiris exports without the
    license declaration (flag + env var) being present."""


def require_license(i_own_license: bool, env_var: str = LICENSE_ENV_VAR) -> None:
    """Raise :class:`LicenseGateError` unless the operator declared licensing.

    Args:
        i_own_license: value of the CLI ``--i-own-license`` flag.
        env_var: environment variable that must equal ``"1"``.
    """
    if i_own_license and os.environ.get(env_var, "") == "1":
        return
    raise LicenseGateError(LICENSE_NOTICE)
