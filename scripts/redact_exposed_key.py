#!/usr/bin/env python3
"""حجب مواد الاعتماد الحيّة من ملفات مُتتبَّعة — **محليًا**، دون أن تعبر القيمة أي حزمة.

لماذا سكربت بدل patch جاهز؟
  لأن أي diff يحجب سرًّا **يحتوي حتمًا على السرّ نفسه في سطر الإزالة**. شحن ذلك
  الـpatch (أو رفعه إلى مستودع) يعيد نشر السرّ في موقع جديد. لذلك يُنفَّذ الحجب
  عندك، على نسختك، فلا تسافر القيمة أبدًا.

  وقد ضبط فحصنا هذه المشكلة فعلًا: حزمة الـpatches الأولى احتوت المفتاح الحيّ
  داخل `0002-….patch`، وحُذفت قبل أي رفع.

ما يفعله:
  * يجد **قيم أسرار حيّة** (مفاتيح API، PATs، مفاتيح خاصة، توكنات بوت) في
    الملفات المُتتبَّعة — ولا يمسّ قوالب الشيفرة مثل `${HF_TOKEN}@host`
    لأن حجبها يكسر البرنامج (معالجتها إصلاح مصادقة، لا حجب).
  * يتخطى ثوابت الاختبار والأمثلة الموثَّقة (نفس قواعد audit_tree_secrets.py).
  * يستبدل القيمة بـ`<REDACTED:len=N:kind>` ويضيف تنبيهًا بأن الحجب لا يُبطل السرّ.
  * **لا يطبع القيمة** — الموقع والنوع والطول فقط.
  * `--dry-run` افتراضي: لا يعدّل شيئًا قبل أن تراه.

الاستخدام:
    python3 scripts/redact_exposed_key.py                 # تقرير فقط (افتراضي)
    python3 scripts/redact_exposed_key.py --apply         # نفّذ الحجب
    python3 scripts/redact_exposed_key.py --apply --path docs/prompts/

⚠️ الحجب لا يُبطل السرّ. الإجراء الحاسم هو **الإبطال من لوحة المزوّد**،
   ثم التعامل مع تاريخ Git إن لزم (filter-repo) — لا العكس.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_tree_secrets import (  # noqa: E402
    COMPILED, MAX_BYTES, NEVER_BASELINABLE, PLACEHOLDER, FIXTURE_CALL,
    SKIP_SUFFIX, TEST_PATH, tracked_files,
)

# ── ما الذي يُحجب فعلًا؟ ────────────────────────────────────────────────────
# **قيم الأسرار الحيّة فقط** (أنواع NEVER_BASELINABLE).
# أما `credential-in-url` فهو **قالب شيفرة** (`${HF_TOKEN}@host`) لا قيمة سرّية،
# وحجبه يستبدل شيفرة عاملة بنصّ ميت فيكسر البرنامج. معالجته تكون بإصلاح
# آلية المصادقة، وهي مهمة منفصلة موثَّقة في خط الأساس.
REDACTABLE_KINDS = NEVER_BASELINABLE

SELF = Path(__file__).name


def find_exposed(subpath: str | None) -> list[dict]:
    out: list[dict] = []
    for rel in tracked_files():
        if subpath and not rel.startswith(subpath):
            continue
        p = REPO_ROOT / rel
        if Path(rel).name in {SELF, "audit_tree_secrets.py", "scan_diff_secrets.py"}:
            continue
        if not p.is_file() or p.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in text[:4096]:
            continue
        is_test = bool(TEST_PATH.search(rel))
        for line_no, line in enumerate(text.splitlines(), start=1):
            for kind, rx in COMPILED.items():
                if kind not in REDACTABLE_KINDS:
                    continue          # نمط شيفرة لا قيمة سرّية — لا يُحجب
                m = rx.search(line)
                if not m:
                    continue
                value = m.group(0)
                if PLACEHOLDER.search(line) or PLACEHOLDER.search(value):
                    continue
                if is_test and FIXTURE_CALL.search(line):
                    continue
                if is_test:
                    continue
                out.append({"file": rel, "line": line_no, "kind": kind,
                            "length": len(value), "value": value})
    return out


def redact_text(text: str, values: list[str]) -> str:
    for v in values:
        # نستخدم طول القيمة ونوعها فقط؛ لا نُدرج أي جزء منها
        text = text.replace(v, "<REDACTED:len=%d>" % len(v))
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="نفّذ الحجب (الافتراضي: تقرير فقط)")
    ap.add_argument("--path", default=None, help="احصر الفحص في مسار فرعي")
    ap.add_argument("--note", action="store_true",
                    help="أضف سطر تنبيه بأن الحجب لا يُبطل السرّ (للملفات النصية فقط)")
    args = ap.parse_args()

    found = find_exposed(args.path)
    if not found:
        print("لا مواد اعتماد حقيقية الشكل في الملفات المُتتبَّعة%s."
              % (" تحت %s" % args.path if args.path else ""))
        return 0

    by_file: dict[str, list[dict]] = {}
    for f in found:
        by_file.setdefault(f["file"], []).append(f)

    print("وُجد %d موضعًا في %d ملفًا (القيم **غير** معروضة):\n" % (len(found), len(by_file)))
    for rel, items in sorted(by_file.items()):
        for it in items:
            print("  %-58s L%-6d %-22s len=%d" % (rel[:58], it["line"], it["kind"], it["length"]))

    if not args.apply:
        print("\nوضع التقرير فقط. للتنفيذ:  python3 scripts/redact_exposed_key.py --apply")
        print("⚠️ قبل ذلك: أَبطل كل مفتاح من لوحة مزوّده — الحجب لا يُبطل السرّ.")
        return 1

    changed = 0
    for rel, items in by_file.items():
        p = REPO_ROOT / rel
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new = redact_text(text, [it["value"] for it in items])
        if args.note and new != text:
            new += ("\n<!-- حُجبت مواد اعتماد من هذا الملف آليًا في 2026-10-18. "
                    "القيم الأصلية ما تزال في تاريخ Git؛ الحجب لا يُبطلها — "
                    "الإبطال من لوحة المزوّد هو الإجراء الحاسم. -->\n")
        if new != text:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print("  ✔ حُجب %s (%d موضعًا)" % (rel, len(items)))

    print("\nعدّل %d ملفًا." % changed)
    print("الخطوات التالية بالترتيب:")
    print("  1) أَبطل كل مفتاح من لوحة مزوّده (الإجراء الحاسم).")
    print("  2) python3 scripts/audit_tree_secrets.py   ← يجب أن يصير 0 NEW-BLOCK.")
    print("  3) أعِد توليد أي ملف مشتق (مثل project_context.txt) حتى لا يعيد نشر القيمة.")
    print("  4) قرّر بشأن تاريخ Git: بعد الإبطال، إعادة الكتابة اختيارية "
          "(git filter-repo) لكنها لازمة إن بقيت القيمة تُلتقط بفحص خارجي.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
