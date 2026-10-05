#!/usr/bin/env python3
# scripts/trainingdb_sync.py
"""Push the local OCR training database to GitHub — مزامنة قاعدة بيانات التدريب

Target repo (private): DrAbdulmalek/omni-ocr-training-db
    slices/<id>.png + slices.jsonl      # annotated clips (قصاصات)
    patterns/patterns.json              # learned glyph patterns (أنماط/字模)
    exports/…                            # training-ready dataset bundles
    stats.json + README.md              # auto-generated

Behavior:
    1. Refresh generated views (slices.jsonl copy, stats.json, README.md)
    2. Secret-scan all text files about to be committed (abort on hit)
    3. Commit changes (if any)
    4. Push using the token from env GH_TOKEN / /home/z/.zai-gh-token —
       the token is used ONLY in the push URL on the command line and is
       NEVER written to .git/config, logs, or the pushed tree.
    5. Mark pushed slice ids as synced (sync_state.json)

Usage:
    python scripts/trainingdb_sync.py [--dry-run] [--export]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List

SUITE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(SUITE_ROOT, "src", "ocr"))

DEFAULT_REPO = "DrAbdulmalek/omni-ocr-training-db"
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def training_db_dir() -> str:
    return os.getenv("OMNI_TRAINING_DB_DIR") or os.path.join(SUITE_ROOT, "data", "training_db")


def read_token() -> str:
    tok = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not tok and os.path.exists("/home/z/.zai-gh-token"):
        with open("/home/z/.zai-gh-token") as fh:
            tok = fh.read().strip()
    if not tok:
        raise SystemExit("NO_TOKEN: set GH_TOKEN or provide /home/z/.zai-gh-token")
    return tok


def git(repo: str, *args: str, env: Dict[str, str] | None = None) -> str:
    res = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {res.stderr.strip()[:300]}")
    return res.stdout.strip()


def secret_scan(repo: str) -> List[str]:
    hits: List[str] = []
    for root, _dirs, files in os.walk(repo):
        if os.sep + ".git" in root:
            continue
        for name in files:
            if not re.search(r"\.(json|jsonl|md|txt|csv|py|ts|js)$", name):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except Exception:
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    hits.append(os.path.relpath(path, repo))
                    break
    return hits


def build_stats(training_db: str) -> Dict[str, Any]:
    from pattern_store import PatternStore
    from slice_store import SliceStore
    s_stats = SliceStore(training_db).stats()
    p_stats = PatternStore(training_db).stats()
    exports = []
    exp_dir = os.path.join(training_db, "exports")
    if os.path.isdir(exp_dir):
        exports = sorted(os.listdir(exp_dir))[-10:]
    return {"generated_at": int(time.time()), "slices": s_stats,
            "patterns": p_stats, "exports": exports,
            "repo": os.getenv("OMNI_TRAINING_DB_REPO", DEFAULT_REPO)}


def write_readme(training_db: str, stats: Dict[str, Any]) -> None:
    s, p = stats["slices"], stats["patterns"]
    with open(os.path.join(training_db, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(f"""# omni-ocr-training-db — قاعدة بيانات تدريب التعرف الضوئي

نسخة مطابقة (mirror) لقاعدة بيانات التدريب المحلية في `omni-medical-suite` —
تجمع **القصاصات** ( slices مقتطعة من المستندات مع نصها الصحيح) و**الأنماط**
(قوالب الحروف/الكلمات المتعلمة بأسلوب ABBYY FineReader) لتدريب نماذج ذكاء
اصطناعي عربية مستقبلاً (CRNN / TrOCR).

## الأرقام الحالية
| المؤشر | القيمة |
|---|---|
| القصاصات الكلية | {s['slices']} |
| متزامنة مع هذا المستودع | {s['synced']} |
| قيد الانتظار | {s['pending']} |
| الأنماط المتعلمة | {p['patterns']} |
| مرات استخدام الأنماط | {p['occurrences']} |

## البنية
- `slices/` — صور القصاصات PNG + `slices.jsonl` (سجل توضيحي لكل قصاصة)
- `patterns/` — مؤشر الأنماط `patterns.json` (كل نمط = نص + مصفوفة ثنائية 96×48)
- `exports/` — حزم جاهزة للتدريب (train/val/test) من `src/ocr/training_export.py`
- `stats.json` — إحصاءات مولّدة آلياً

## المخطط (slices.jsonl)
```json
{{"id": "...", "level": "char|word|line", "text": "النص الصحيح", "lang": "ar",
  "bbox": [x, y, w, h], "image": "slices/<id>.png", "source": {{"channel": "...", "msg_id": 123}}}}
```

> مصدر البيانات: مستندات وأرشيف المالك الخاص — المستودع **خاص**.
> آخر تحديث آلي: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(stats['generated_at']))}
""")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    do_export = "--export" in sys.argv
    training_db = training_db_dir()
    if not os.path.isdir(training_db):
        raise SystemExit(f"training db dir missing: {training_db}")

    from slice_store import SliceStore  # noqa: E402  (after sys.path setup)
    slices_store = SliceStore(training_db)

    # 1. refresh generated views
    stats = build_stats(training_db)
    with open(os.path.join(training_db, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)
    write_readme(training_db, stats)

    # 1b. optional training-ready export bundle
    if do_export:
        from training_export import export_all
        summary = export_all(training_db)
        print("EXPORT:", json.dumps(summary["slices"], ensure_ascii=False)[:300])

    # 2. git bootstrap
    if not os.path.isdir(os.path.join(training_db, ".git")):
        git(training_db, "init", "-b", "main")
        git(training_db, "remote", "add", "origin",
            f"https://github.com/{os.getenv('OMNI_TRAINING_DB_REPO', DEFAULT_REPO)}.git")
    git(training_db, "config", "user.name", "omni-training-bot")
    git(training_db, "config", "user.email", "omni-training-bot@users.noreply.github.com")

    # 3. secret gate
    hits = secret_scan(training_db)
    if hits:
        print("SECRET_SCAN_FAIL:", hits[:10])
        return 2

    # 4. commit if changes
    git(training_db, "add", "-A")
    status = git(training_db, "status", "--porcelain")
    if not status.strip():
        print("NOTHING_TO_PUSH: local training DB already in sync")
        return 0
    msg = f"training-db sync: {stats['slices']['slices']} slices, {stats['patterns']['patterns']} patterns"
    if dry_run:
        print("DRY_RUN — would commit:", status[:400])
        return 0
    git(training_db, "commit", "-m", msg)

    # 5. push using a process environment, never putting the token in argv.
    # Git receives credentials through a temporary shell helper that reads GH_TOKEN;
    # the token therefore does not appear in the process command line or git config.
    token = read_token()
    repo_slug = os.getenv("OMNI_TRAINING_DB_REPO", DEFAULT_REPO)
    push_url = f"https://github.com/{repo_slug}.git"
    push_env = os.environ.copy()
    push_env["GH_TOKEN"] = token
    push_env["GIT_TERMINAL_PROMPT"] = "0"
    push_env["GIT_CONFIG_COUNT"] = "1"
    push_env["GIT_CONFIG_KEY_0"] = "credential.helper"
    push_env["GIT_CONFIG_VALUE_0"] = "!f() { echo username=x-access-token; echo password=$GH_TOKEN; }; f"

    def try_push() -> "subprocess.CompletedProcess":
        return subprocess.run(["git", "-C", training_db, "push", push_url, "main"],
                              capture_output=True, text=True, env=push_env)

    res = try_push()
    if res.returncode != 0 and "fetch first" in (res.stdout + res.stderr):
        # remote moved (repo auto-init README, push from another device):
        # merge remote history preferring local generated views, then retry.
        print("REMOTE_MOVED: merging with -X ours …")
        subprocess.run(["git", "-C", training_db, "fetch", push_url, "main"], capture_output=True, text=True, env=push_env)
                       capture_output=True, text=True)
        merge = subprocess.run(
            ["git", "-C", training_db, "merge", "-X", "ours",
             "--allow-unrelated-histories", "--no-edit", "FETCH_HEAD"],
            capture_output=True, text=True)
        if merge.returncode != 0:
            print("MERGE_FAIL:", (merge.stdout + merge.stderr)[-400:])
            return 1
        res = try_push()
    if res.returncode != 0:
        print("PUSH_FAIL:", (res.stdout + res.stderr)[-500:])
        return 1
    sha = git(training_db, "rev-parse", "HEAD")

    # 6. mark synced and push the sync-state follow-up commit
    pending = slices_store.list_slices(limit=10_000, pending_only=True)
    slices_store.mark_synced([r["id"] for r in pending], commit=sha[:12])
    git(training_db, "add", "sync_state.json")
    if git(training_db, "status", "--porcelain").strip():
        git(training_db, "commit", "-m", "sync state update")
        res2 = try_push()
        if res2.returncode != 0:
            print("PUSH_STATE_FAIL (data already pushed):",
                  (res2.stdout + res2.stderr)[-300:])
    print(f"PUSHED: {sha[:12]} — slices={stats['slices']['slices']} "
          f"patterns={stats['patterns']['patterns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
