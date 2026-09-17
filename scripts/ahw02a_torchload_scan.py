#!/usr/bin/env python3
"""ahw02a_torchload_scan.py — AHW-02A bounded torch.load evidence scan (§K.5).

AST-based (no imports of target code), over an EXPLICITLY allow-listed set of
source directories, with a hard time bound. Classifies every ``torch.load(...)``
call site:
    SAFE   = keyword ``weights_only=True`` present
    UNSAFE = missing, or explicitly False

Re-created 2026-09-17 (SESSION-22) per docs/SESSION_ARTIFACTS_POLICY.md — the
original SESSION-21 scan artifacts were lost with the environment. Scope below
is the re-created allow-list (disclosed superset covering all six §K.5 hit
paths); numbers are honest for THIS scope.
"""
import ast
import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_JSON = REPO / "scripts" / "ahw02a_torchload_scan.json"
TIME_BUDGET_S = 60.0

SCOPE_DIRS = [
    "packages/core",
    "packages/vision",
    "packages/omni_ocr",
    "packages/interactive-learning",
    "packages/file_processor",
    "packages/handwriting",
    "packages/medical",
    "packages/segmentation",
    "packages/ocr_postprocess",
    "packages/scanner_fixer",
    "packages/training",
    "app",
    "apps",
    "src/ocr",
    "hf-space/packages/core",
    "hf-space/packages/vision",
]

# The three E1 remediation sites (AHW-02E) — full repo-relative paths.
E1_SITES = {
    "packages/interactive-learning/learning/online_learner.py",
    "packages/file_processor/interactive_learning/learning/online_learner.py",
    "apps/handwriting-demo/training/continual_trainer.py",
}


def classify_call(node: ast.Call):
    """Return weights_only state for a torch.load(...) call node."""
    for kw in node.keywords:
        if kw.arg == "weights_only":
            val = kw.value
            if isinstance(val, ast.Constant) and val.value is True:
                return True
            return False  # explicitly False / non-True expression
    return None  # absent


def main() -> int:
    started = time.perf_counter()
    hits = []
    files_scanned = 0
    timed_out = False

    py_files = []
    for d in SCOPE_DIRS:
        root = REPO / d
        if not root.is_dir():
            continue
        py_files.extend(sorted(root.rglob("*.py")))

    for path in py_files:
        if time.perf_counter() - started > TIME_BUDGET_S:
            timed_out = True
            break
        files_scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_torch_load = (
                isinstance(func, ast.Attribute)
                and func.attr == "load"
                and isinstance(func.value, ast.Name)
                and func.value.id == "torch"
            )
            if not is_torch_load:
                continue
            wo = classify_call(node)
            rel = path.relative_to(REPO).as_posix()
            safe = wo is True
            if rel in E1_SITES:
                remediation = "YES (E1)"
            elif "line_segmenter" in rel:
                remediation = "pre-existing safe"
            else:
                remediation = "n/a"
            hits.append(
                {
                    "path": rel,
                    "line": node.lineno,
                    "weights_only": wo,
                    "safe": safe,
                    "remediated_by_ahw02": remediation,
                }
            )

    elapsed = round(time.perf_counter() - started, 1)
    unsafe = [h for h in hits if not h["safe"]]
    result = {
        "scope_dirs": SCOPE_DIRS,
        "files_scanned": files_scanned,
        "elapsed_s": elapsed,
        "time_budget_s": TIME_BUDGET_S,
        "timed_out": timed_out,
        "hits": hits,
        "unsafe_count": len(unsafe),
        "verdict": (
            "ZERO unsafe torch.load sites remain within the declared scope"
            if not unsafe
            else f"{len(unsafe)} UNSAFE SITE(S) FOUND"
        ),
        "re_created": "2026-09-17 SESSION-22 per docs/SESSION_ARTIFACTS_POLICY.md",
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")

    print(f"scope dirs          : {len(SCOPE_DIRS)}")
    print(f"files scanned       : {files_scanned} (in {elapsed}s, timed_out={timed_out})")
    print(f"torch.load sites    : {len(hits)}")
    for h in sorted(hits, key=lambda x: (x["path"], x["line"])):
        print(
            f"  {h['path']}:{h['line']}  weights_only={h['weights_only']}  "
            f"{'SAFE' if h['safe'] else 'UNSAFE'}  [{h['remediated_by_ahw02']}]"
        )
    print(f"UNSAFE count        : {len(unsafe)}")
    print(f"VERDICT             : {result['verdict']}")
    return 0 if not unsafe and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
