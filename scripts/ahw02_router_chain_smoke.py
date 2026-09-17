#!/usr/bin/env python3
"""ahw02_router_chain_smoke.py — AHW-02 §K.6 live router→execution chain smoke.

Proves the FULL chain, live, in this environment:
    EngineRouter.select() (REAL router, selection never stubbed)
      → RouterExecutor.execute()
        → ExecutableEngineAdapter.run()
          → standard packages.omni_ocr.adapter.OCRResult
            (with provenance + fallback_status semantics)

SCENARIO 1 (declared fallback): real router handwriting selection
    [Qwen, QARI, TrOCR]; Qwen fails at runtime; QARI executes successfully
    → fallback_used=True, attempts=[failed Qwen, executed QARI].
SCENARIO 2 (explicit failure, CPU-only env): build_default_executor() with the
    REAL adapters (torch/transformers absent, olmocr absent) → every selected
    engine skipped with recorded reasons → explicit-error OCRResult,
    fallback_used=False, no cloud engine anywhere in attempts.

Adapters in scenario 1 are fakes BOUND TO REAL ROUTER ENGINE NAMES (same
technique as tests/test_router_executor.py) — selection itself is the real
router's, never stubbed.

Re-created 2026-09-17 (SESSION-22) per docs/SESSION_ARTIFACTS_POLICY.md.
Output: scripts/ahw02_router_chain_smoke_output.json
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from packages.core.engine_registry import EngineAdapter  # noqa: E402
from packages.core.engine_router import EngineRouter  # noqa: E402
from packages.core.router_executor import (  # noqa: E402
    ExecutableEngineAdapter,
    RouterExecutor,
    build_default_executor,
)
from packages.omni_ocr.adapter import OCRResult  # noqa: E402

OUT_JSON = REPO / "scripts" / "ahw02_router_chain_smoke_output.json"

EXPECTED_RESULT_KEYS = {
    "confidence", "engine", "error", "processing_time",
    "provenance", "text", "word_count", "words",
}
EXPECTED_PROVENANCE_KEYS = {
    "profile", "language", "script_kind", "normalization",
    "selection", "reasons", "attempts", "fallback_used",
}


class FakeRouterEngine(ExecutableEngineAdapter):
    """Fake adapter bound to a REAL router engine name (contract-complete)."""

    # class-level concrete implementations of the EngineAdapter ABC contract
    estimated_ram_gb = 1.0
    supported_tasks = ["handwriting", "printed"]

    def __init__(self, name, *, fail=False, text="نص مكتوب بخط اليد"):
        self._name = name
        self._fail = fail
        self._text = text
        self.calls = 0

    @property
    def name(self):
        return self._name

    def is_available(self):
        return True

    def healthcheck(self):
        return {"ok": True, "error": None, "version": "fake", "details": {}}

    def run(self, image, *, language="ar", block_type="paragraph"):
        self.calls += 1
        if self._fail:
            raise RuntimeError(f"simulated runtime failure in {self._name}")
        return OCRResult(
            text=self._text,
            confidence=0.90,
            engine=self._name,
            provenance={"script_kind": "handwriting"},
        )


def check(cond, msg, failures):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        failures.append(msg)


def scenario_1(failures):
    print("SCENARIO 1 — declared fallback (Qwen fails -> QARI executes)")
    # Real router engine names (verbatim from EngineRouter selection)
    QWEN = "Arabic-handwritten-OCR (Qwen)"
    QARI = "QARI"
    qwen = FakeRouterEngine(QWEN, fail=True)
    qari = FakeRouterEngine(QARI)
    router = EngineRouter(profile="balanced", max_engines=3, available_ram_gb=14.0)
    executor = RouterExecutor(router=router, adapters=[qwen, qari])
    selection, reasons = router.select(
        language="ar", block_type="handwriting", image_quality=0.30
    )
    print(f"  real router selection: {selection}")
    check(selection[:2] == [QWEN, QARI],
          "real router selects the declared handwriting chain", failures)

    result = executor.execute(object(), language="ar", block_type="handwriting",
                              image_quality=0.30)
    check(isinstance(result, OCRResult), "result is the standard OCRResult",
          failures)
    check(result.engine == QARI, "successful engine = QARI (second in chain)",
          failures)
    att = result.provenance["attempts"]
    check([a["engine"] for a in att] == [QWEN, QARI],
          "attempts only contain router-selected engines, router order", failures)
    check(att[0]["status"] == "failed" and att[1]["status"] == "executed",
          "attempts statuses = [failed(Qwen), executed(QARI)]", failures)
    check(result.provenance["fallback_used"] is True,
          "fallback_used=True (DECLARED, provenance-visible)", failures)
    check(set(EXPECTED_PROVENANCE_KEYS) <= set(result.provenance),
          "provenance carries full contract keys", failures)
    check(set(EXPECTED_RESULT_KEYS) <= set(result.to_dict()),
          "to_dict() carries full result contract keys", failures)
    print(f"  attempts: {json.dumps(att, ensure_ascii=False)}")
    return result


def scenario_2(failures):
    print("SCENARIO 2 — explicit failure in CPU-only env (no silent fallback)")
    executor = build_default_executor()  # real adapters: TrOCR HTR + OLMoCR
    result = executor.execute(object(), language="ar", block_type="handwriting",
                              image_quality=0.30)
    selection = result.provenance["selection"]
    attempts = result.provenance["attempts"]
    print(f"  real router selection: {selection}")
    check(isinstance(result, OCRResult), "result is the standard OCRResult",
          failures)
    check(result.text == "" and result.error != "",
          "explicit-error OCRResult (no text, error populated)", failures)
    check(all(a["status"] == "skipped" for a in attempts),
          f"every selected engine skipped with reason "
          f"({[a.get('reason') for a in attempts]})", failures)
    check(result.provenance["fallback_used"] is False,
          "fallback_used=False (nothing executed, nothing rescued)", failures)
    cloud = [a for a in attempts if "cloud" in a["engine"].lower()
             or "mistral" in a["engine"].lower()]
    check(not cloud, "no cloud engine in attempts (E3 posture)", failures)
    print(f"  error: {result.error[:120]}…")
    return result


def main() -> int:
    failures = []
    results = {"scenario_1": None, "scenario_2": None}
    r1 = scenario_1(failures)
    results["scenario_1"] = {
        "engine": r1.engine,
        "fallback_used": r1.provenance["fallback_used"],
        "attempts": r1.provenance["attempts"],
        "to_dict_keys": sorted(r1.to_dict()),
        "provenance_keys": sorted(r1.provenance),
    }
    print()
    r2 = scenario_2(failures)
    results["scenario_2"] = {
        "engine": r2.engine,
        "fallback_used": r2.provenance["fallback_used"],
        "attempts": r2.provenance["attempts"],
        "selection": r2.provenance["selection"],
        "error_state": r2.provenance.get("error_state"),
    }
    verdict = "ALL ASSERTIONS PASSED" if not failures else f"{len(failures)} FAILURE(S)"
    print()
    print(f"CHAIN SMOKE VERDICT: {verdict}")
    out = {
        "verdict": verdict,
        "failures": failures,
        "environment": {"torch": "absent (CPU-only)", "olmocr": "absent"},
        "re_created": "2026-09-17 SESSION-22 per docs/SESSION_ARTIFACTS_POLICY.md",
        **results,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
