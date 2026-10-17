#!/usr/bin/env python3
"""تدقيق الشجرة الكاملة بحثًا عن مواد اعتماد — بلا نقاط عمياء للفرق (diff).

لماذا هذا الملف منفصل عن `scan_diff_secrets.py`؟
  * `scan_diff_secrets.py` يفحص **الأسطر المضافة في فرق** — ضروري لمنع الجديد،
    لكنه **لا يرى ما سبق تسريبه**.
  * هذا التدقيق يفحص **كل ملف مُتتبَّع في الشجرة**، فيلتقط الأسرار المُودَعة
    مسبقًا. هذا بالضبط ما كشف مفتاحًا حيًّا بطول 51 حرفًا في
    `docs/prompts/omni_ocr_adapter_change.md` على `main` العام.

قواعد الإخراج:
  * **لا تُطبع أي قيمة سرية** — النوع والطول ورقم السطر فقط.
  * `BLOCK` = مادة اعتماد حقيقية الشكل في غير مواضع الاختبار → خروج 1.
  * `WARN`  = ثابت اختبار (fixture) أو مثال موثَّق → لا يحجب، لكنه يظهر.
  * `BASELINED` = موضع معروف مُدرَج في خط الأساس → لا يحجب (نمط ratchet).

الاستخدام:
    python3 scripts/audit_tree_secrets.py                       # كل الشجرة
    python3 scripts/audit_tree_secrets.py --baseline .github/secret-audit-baseline.json
    python3 scripts/audit_tree_secrets.py --write-baseline .github/secret-audit-baseline.json
    python3 scripts/audit_tree_secrets.py --json report.json --strict
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "openai-style-key":   r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}\b",
    "github-classic-pat": r"\bghp_[A-Za-z0-9]{20,}\b",
    "github-fine-pat":    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    "github-other":       r"\bgh[ousr]_[A-Za-z0-9]{20,}\b",
    "huggingface":        r"\bhf_[A-Za-z0-9]{20,}\b",
    "aws-access-key":     r"\bAKIA[0-9A-Z]{16}\b",
    "google-api-key":     r"\bAIza[0-9A-Za-z_\-]{30,}\b",
    "slack-token":        r"\bxox[bpars]-[A-Za-z0-9\-]{10,}\b",
    "telegram-bot-token": r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}\b",
    "npm-token":          r"\bnpm_[A-Za-z0-9]{30,}\b",
    "stripe-key":         r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{15,}\b",
    "private-key-block":  r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----",
    "jwt":                r"\bey[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}",
    # عنوان يحمل userinfo مع متغير سرّي (يتسرب عبر .git/config و ps و remote -v)
    "credential-in-url":  r"://[^\s/\"']*[:@]\s*(?:[\"']\s*)?[\$\{]\s*"
                          r"(?:GITHUB_TOKEN|GH_TOKEN|HF_TOKEN|HUGGINGFACE_TOKEN|TOKEN|SECRET|PASSWORD)\b",
}
COMPILED = {k: re.compile(v, re.IGNORECASE if k == "credential-in-url" else 0)
            for k, v in PATTERNS.items()}

PLACEHOLDER = re.compile(
    r"(?i)(xxx{2,}|example|your[-_]|changeme|change_me|placeholder|dummy|sample|"
    r"token[_-]?here|<[^>]{1,40}>|\{\{|\$\{|REDACTED|fake|not[_-]real|sk-123|"
    r"hf_REPLACE|ghp_REPLACE|\*\*\*)"
)
FIXTURE_CALL = re.compile(r"(scan_text|write_text|assert|mock|fixture|monkeypatch|"
                          r"sample_|_sample|dummy|fake|test_|=\s*[\"'])")
TEST_PATH = re.compile(r"(?:^|/)(?:tests?|spec|__tests__)/|(?:^|/)test_[^/]*\.py$|conftest\.py$")

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".pdf",
               ".zip", ".gz", ".tgz", ".bz2", ".7z", ".rar", ".xz", ".pyc", ".so",
               ".o", ".a", ".dll", ".dylib", ".bin", ".dat", ".db", ".sqlite",
               ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".wav", ".pt",
               ".pth", ".onnx", ".safetensors", ".npy", ".npz", ".pkl"}
MAX_BYTES = 3_000_000
SELF_NAMES = {"audit_tree_secrets.py", "scan_diff_secrets.py", "redact_exposed_key.py"}

# ── أي الأنماط يجوز إدراجها في خط الأساس؟ ───────────────────────────────────
# `credential-in-url` **نمط شيفرة** (قالب `${TOKEN}@host`) لا قيمة مسرَّبة،
# فمعالجته تدريجية مشروعة عبر خط أساس متناقص.
# أما أنواع المفاتيح الحيّة فإدراجها في خط الأساس يعني **تطبيع سرّ منشور** —
# وهذا مرفوض بنيويًا: لا يمكن إخراس مفتاح حيّ بخط أساس، بل يجب حجبه وإبطاله.
BASELINABLE_KINDS = frozenset({"credential-in-url"})
NEVER_BASELINABLE = frozenset({
    "openai-style-key", "github-classic-pat", "github-fine-pat", "github-other",
    "huggingface", "aws-access-key", "google-api-key", "slack-token",
    "telegram-bot-token", "npm-token", "stripe-key", "private-key-block",
})


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("git ls-files failed — must run inside a git checkout")
    return [p for p in out.stdout.splitlines() if p.strip()]


def scan_file(rel: str, path: Path) -> list[dict]:
    hits: list[dict] = []
    try:
        if path.stat().st_size > MAX_BYTES:
            return hits
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    if "\x00" in text[:4096]:
        return hits
    is_test = bool(TEST_PATH.search(rel))
    for line_no, line in enumerate(text.splitlines(), start=1):
        for kind, rx in COMPILED.items():
            m = rx.search(line)
            if not m:
                continue
            value = m.group(0)
            if PLACEHOLDER.search(line) or PLACEHOLDER.search(value):
                verdict, reason = "WARN", "placeholder-example"
            elif is_test and FIXTURE_CALL.search(line):
                verdict, reason = "WARN", "test-fixture"
            elif is_test:
                verdict, reason = "WARN", "inside-tests-dir"
            else:
                verdict, reason = "BLOCK", ""
            hits.append({
                "file": rel, "line": line_no, "kind": kind, "verdict": verdict,
                "reason": reason, "length": len(value),
                "charset": len(set(value)),
                # لا تُطبع القيمة — بادئة قصيرة + الطول فقط
                "masked": (value[:4] + "<REDACTED:%d>" % (len(value) - 4)) if len(value) > 8 else "<short>",
            })
    return hits


def fingerprint(f: dict) -> str:
    """بصمة الموضع — لا تحتوي أي قيمة سرية."""
    return "%s:%d:%s" % (f["file"], f["line"], f["kind"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--strict", action="store_true", help="اعتبار WARN حجبًا أيضًا")
    ap.add_argument("--quiet-on-clean", action="store_true")
    ap.add_argument("--baseline", metavar="FILE",
                    help="المواضع المعروفة لا تحجب؛ أي موضع **جديد** يحجب (ratchet)")
    ap.add_argument("--write-baseline", metavar="FILE",
                    help="أنشئ خط الأساس من الحالة الحالية ثم اخرج بـ0")
    args = ap.parse_args()

    findings: list[dict] = []
    scanned = 0
    for rel in tracked_files():
        if Path(rel).name in SELF_NAMES or Path(rel).suffix.lower() in SKIP_SUFFIX:
            continue
        p = REPO_ROOT / rel
        if not p.is_file():
            continue
        scanned += 1
        findings.extend(scan_file(rel, p))

    baseline_keys: set[str] = set()
    bpath = Path(args.write_baseline or args.baseline) if (args.write_baseline or args.baseline) else None
    if bpath and bpath.is_file():
        try:
            baseline_keys = set(json.loads(bpath.read_text(encoding="utf-8")).get("findings") or [])
        except (OSError, ValueError) as exc:
            print("::warning::cannot read baseline %s (%s)" % (bpath, exc), file=sys.stderr)

    if args.write_baseline:
        blocked = [f for f in findings if f["verdict"] == "BLOCK"]
        refused = [f for f in blocked if f["kind"] in NEVER_BASELINABLE]
        current = sorted({fingerprint(f) for f in blocked
                          if f["kind"] in BASELINABLE_KINDS})
        if refused:
            print("::error::لا يمكن إدراج %d finding من نوع مفاتيح حيّة في خط الأساس "
                  "(سياسة: لا يُطبع سرّ منشور بخط أساس):" % len(refused), file=sys.stderr)
            for f in refused[:20]:
                print("   %s:%d %s (len=%d)" % (f["file"], f["line"], f["kind"], f["length"]),
                      file=sys.stderr)
            print("   المعالجة: python3 scripts/redact_exposed_key.py --apply  ثم الإبطال "
                  "من لوحة المزوّد.", file=sys.stderr)
            return 2
        bpath.write_text(json.dumps({
            "_comment": [
                "خط أساس مواضع مواد الاعتماد المعروفة في الشجرة المُتتبَّعة.",
                "الغاية: منع **الجديد** فورًا بدل تجميد CI على المتراكم الحالي.",
                "القاعدة: هذا الملف يجب أن يتناقص فقط. لا تُضف مواضع جديدة — أصلحها.",
                "البصمات ملف:سطر:نوع ولا تحتوي أي قيمة سرية.",
            ],
            "generated_from_commit": subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                capture_output=True, text=True).stdout.strip(),
            "count": len(current),
            "findings": current,
        }, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote baseline with %d finding(s) -> %s" % (len(current), bpath))
        return 0

    for f in findings:
        if f["verdict"] != "BLOCK":
            continue
        if f["kind"] in NEVER_BASELINABLE:
            continue          # سرّ حيّ: يبقى BLOCK حتى لو أُدرج في خط الأساس يدويًا
        if fingerprint(f) in baseline_keys:
            f["verdict"] = "BASELINED"

    blocks = [f for f in findings if f["verdict"] == "BLOCK"]
    warns = [f for f in findings if f["verdict"] == "WARN"]
    based = [f for f in findings if f["verdict"] == "BASELINED"]

    for f in findings:
        note = f["reason"] or (f["verdict"].lower() if f["verdict"] == "BASELINED" else "")
        print("%-9s %s:%d %s (len=%d, charset=%d)%s"
              % (f["verdict"], f["file"], f["line"], f["kind"], f["length"], f["charset"],
                 "  [%s]" % note if note else ""))

    if not args.quiet_on_clean or blocks or warns or based:
        print("\ntree-audit: %d file(s) scanned, %d NEW-BLOCK, %d BASELINED, %d WARN"
              % (scanned, len(blocks), len(based), len(warns)))
        if based:
            print("note: %d baselined finding(s) must shrink over time, not grow (%s)"
                  % (len(based), bpath or "no baseline file"))

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"scanned_files": scanned, "new_blocks": blocks,
             "baselined": based, "warnings": warns}, indent=1, ensure_ascii=False),
            encoding="utf-8")

    if blocks:
        print("\n::error::مواد اعتماد **جديدة** (خارج خط الأساس) في الشجرة المُتتبَّعة. "
              "أبطِلها من مصدرها أولًا — الحذف من الملف لا يُبطلها — ثم أزلها "
              "وأعِد توليد أي ملفات مشتقة مثل project_context.txt.", file=sys.stderr)
        return 1
    if args.strict and warns:
        print("\n::error::--strict: %d تحذير يُعامل كحجب." % len(warns), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
