"""golden_harness — عَرْجة المعيار الذهبي العربي (T1).

يشغّل كل محرك مرشّح على كل عينة من golden_set ويُخرج JSONL provenance:

    {sample_id, pdf_sha256, page, engine, model, raw_text, normalized_text,
     cer, wer, audit{latency_ms, chars, cloud, cost_estimate_usd?}}

قواعد حاكمة مطبقة هنا:
- **A2:** التطبيع بترتيب منطقي حصراً (packages.evaluation.arabic_normalize.normalize_v1)
  — لا get_display/arabic_reshaper في أي مسار.
- **A3:** المحرك السحابي (MISTRAL) مرشّح قياس بعلامة cloud=true، والبوابة
  ``OMNI_ALLOW_CLOUD`` (fail-closed عبر packages.omni_ocr.adapter._cloud_allowed)
  تُفحص **قبل** أي استدعاء سحابي. الاختبارات لا تستدعيه أبداً.
- **§3.8:** الثقة (confidence) تُستبعد من الترتيب والمقارنة كلياً؛ نتائج
  Mistral تُسجَّل مع ``confidence_excluded=true`` لأن القيمة مُخترَعة
  (confidence_is_estimate=True من adapter) — CER/WER على النص فقط.

الاستخدام:
    python golden_harness.py --engines tesseract_ara --out results.jsonl
    python golden_harness.py --ingest captured_mistral.jsonl --out results.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# إقلاع مسار: يجعل التشغيل المباشر كسكربت أو بـ -m يعمل دائماً من أي cwd
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.evaluation.arabic_normalize import NORMALIZE_V1_VERSION, normalize_v1  # noqa: E402
from packages.evaluation.metrics import calculate_cer, calculate_wer

SET_DIR = Path(__file__).parent / "golden_set"
GT_PATH = SET_DIR / "ground_truth.jsonl"
MANIFEST_PATH = SET_DIR / "manifest.json"
LOCK_PATH = SET_DIR / "engines.lock.json"


def set_dataset_dir(path: "Path | str") -> None:
    """F-14: أعد ربط مسارات مجموعة البيانات في وقت التشغيل.

    SET_DIR كان مثبّتاً صلباً، فكان قياس عينات حقيقية يستلزم الكتابة فوق
    ``golden_set/`` — أي تدمير المعيار الاصطناعي الذي هو **بوابة الانحدار في CI**.
    هذه الدالة تفصل المجموعتين:
      ``golden_set/``       اصطناعية، ثابتة، بوابة CI (الافتراضي)
      ``golden_set_real/``  من القناة الحقيقية، متنامية، أساس قرار المحرك

    تُستدعى من ``main()`` قبل أي قراءة. لا تغيّر السلوك الافتراضي.
    """
    global SET_DIR, GT_PATH, MANIFEST_PATH, LOCK_PATH
    SET_DIR = Path(path).expanduser().resolve()
    if not (SET_DIR / "manifest.json").exists():
        raise FileNotFoundError(
            f"--set-dir: لا manifest.json في {SET_DIR} — هل هو مجلد مجموعة بيانات؟"
        )
    GT_PATH = SET_DIR / "ground_truth.jsonl"
    MANIFEST_PATH = SET_DIR / "manifest.json"
    LOCK_PATH = SET_DIR / "engines.lock.json"


TESSDATA_BEST_ARA_SHA256 = "ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896"

# محركات القياس المحلية فقط افتراضياً. أي محرك سحابي يدخل هذا السجل بعلامة
# cloud=true ويخضع لبوابة OMNI_ALLOW_CLOUD قبل أي استدعاء.
LOCAL_ENGINES = ("tesseract_ara",)


_LFS_MAGIC = b"version https://git-lfs.github.com/spec/v1"


def _reject_lfs_pointer(path: "Path") -> None:
    """LFS: افشل بصراحة إن كان الملف مؤشراً لا محتوى.

    ``.gitattributes`` يتتبّع ``*.jsonl`` والصور بلا عتبة حجم، فاستنساخ عادي بلا
    ``git lfs pull`` يعطي ملفات من 129/130 بايت مكان ``ground_truth.jsonl`` والـPNGs.
    النتيجة السابقة كانت ``json.decoder.JSONDecodeError: Expecting value: line 1
    column 1`` — رسالة **مضلِّلة** تُشير إلى بيانات تالفة لا إلى LFS، وقد كلّفت
    4 اختبارات فاشلة في ``test_golden_harness.py`` على كل استنساخ متفرّق.
    """
    try:
        head = path.open("rb").read(len(_LFS_MAGIC))
    except FileNotFoundError:
        raise
    if head.startswith(_LFS_MAGIC):
        raise RuntimeError(
            f"{path} is a Git LFS pointer ({len(head)} B header), not content. "
            f"Run: git lfs pull   (or: git lfs install && git lfs pull)"
        )


def load_samples() -> list[dict]:
    """حمّل العينات وتحقق من sha256 لكل ملف (ثبات القياس)."""
    _reject_lfs_pointer(MANIFEST_PATH)
    _reject_lfs_pointer(GT_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    gt = {
        row["id"]: row
        for row in (json.loads(l) for l in GT_PATH.read_text(encoding="utf-8").splitlines() if l.strip())
    }
    out = []
    for entry in manifest:
        path = SET_DIR / "samples" / entry["file"]
        # قبل فحص sha256: المؤشر يعطي "drifted" وهي تشخيص خاطئ للسبب الحقيقي.
        _reject_lfs_pointer(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise RuntimeError(f"sample {entry['id']} drifted: sha256 mismatch")
        out.append({"id": entry["id"], "category": entry["category"], "path": path,
                    "reference": gt[entry["id"]]["text"]})
    return out


def _tesseract_env() -> dict:
    """بيئة tesseract — TESSDATA_PREFIX يُورَّث من البيئة كما هو (لا افتراضي صامت)."""
    return dict(os.environ)

_LANG_CACHE: dict[str, list[str]] = {}


def _require_tess_language(lang: str) -> list[str]:
    """A3/الصدق البيئي: فشل صريح عند غياب حزمة اللغة — لا نتائج فارغة صامتة."""
    if lang not in _LANG_CACHE:
        proc = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=30,
            env=_tesseract_env(),
        )
        langs = [l.strip() for l in proc.stdout.splitlines()[1:] if l.strip()]
        _LANG_CACHE[lang] = langs
        if lang not in langs:
            raise RuntimeError(
                f"tesseract: language '{lang}' not available. "
                "Set TESSDATA_PREFIX to a tessdata dir containing "
                f"{lang}.traineddata (tessdata_best sha256={TESSDATA_BEST_ARA_SHA256[:12]}...)"
            )
    return _LANG_CACHE[lang]


def run_tesseract_ara(sample: dict) -> dict:
    """المحرك المحلي الأول: tesseract/ara (tessdata_best) بمعاملات مثبتة.

    يفشل صراحة عند غياب حزمة ara — لا يُرجع نصاً فارغاً صامتاً أبداً.
    """
    _require_tess_language("ara")
    cmd = ["tesseract", str(sample["path"]), "-", "-l", "ara", "--psm", "6"]
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          env=_tesseract_env())
    latency_ms = (time.perf_counter() - start) * 1000.0
    if proc.returncode != 0:
        return {"text": "", "model": "tesseract-ara", "cloud": False,
                "error": proc.stderr.strip()[-200:], "latency_ms": latency_ms}
    return {"text": proc.stdout, "model": "tesseract 5 ara (tessdata_best)",
            "cloud": False, "latency_ms": latency_ms}


ENGINE_RUNNERS = {"tesseract_ara": run_tesseract_ara}


def check_cloud_gate() -> None:
    """A3: البوابة fail-closed تُفحص قبل أي استدعاء سحابي — إعادة استخدام
    تنفيذ PR#137 حصراً، بلا إعادة بناء."""
    from packages.omni_ocr.adapter import _cloud_allowed
    if not _cloud_allowed():
        raise RuntimeError("cloud gate closed: OMNI_ALLOW_CLOUD not set to a truthy value")


def _provenance_row(sample: dict, engine: str, out: dict, page: int = 1) -> dict:
    raw = (out.get("text") or "").strip()
    hyp_norm, hyp_policy = normalize_v1(raw)
    ref_norm, ref_policy = normalize_v1(sample["reference"])
    cer_n, _, _ = calculate_cer(ref_norm, hyp_norm)
    wer_n, _, _ = calculate_wer(ref_norm, hyp_norm)
    cer_r, _, _ = calculate_cer(sample["reference"], raw)
    wer_r, _, _ = calculate_wer(sample["reference"], raw)
    encoding_artifact_share = max(0.0, (cer_r or 0.0) - (cer_n or 0.0))
    return {
        "sample_id": sample["id"],
        "category": sample["category"],
        "pdf_sha256": hashlib.sha256(sample["path"].read_bytes()).hexdigest(),
        "page": page,
        "engine": engine,
        "model": out.get("model", ""),
        "raw_text": raw,
        "normalized_text": hyp_norm,
        "normalize_policy": {
            "version": hyp_policy["version"],
            "fold_hamza": hyp_policy["fold_hamza"],
            "symmetric": True,
            "hyp": hyp_policy,
            "ref": ref_policy,
        },
        "cer": round(cer_n, 6),
        "wer": round(wer_n, 6),
        "cer_normalized": round(cer_n, 6),
        "wer_normalized": round(wer_n, 6),
        "cer_raw": round(cer_r, 6),
        "wer_raw": round(wer_r, 6),
        "encoding_artifact_share": round(encoding_artifact_share, 6),
        "audit": {
            "latency_ms": round(out.get("latency_ms", 0.0), 2),
            "chars": len(raw),
            "cloud": bool(out.get("cloud", False)),
            "confidence_excluded": True,  # §3.8 — الثقة خارج المقارنة دائماً
        },
        **({"error": out["error"]} if out.get("error") else {}),
    }


def run_local(engines: list[str]) -> list[dict]:
    samples = load_samples()
    rows = []
    for engine in engines:
        runner = ENGINE_RUNNERS[engine]
        for sample in samples:
            rows.append(_provenance_row(sample, engine, runner(sample)))
    return rows


def ingest_captured(path: Path, engine: str = "mistral") -> list[dict]:
    """أدخل نتائج سحابية ملتقطة يدوياً (بلا شبكة هنا) واحسب مقاييسها.

    كل سجل: {sample_id, model, raw_text, cost_estimate_usd?, page?}.
    الثقة إن وردت في الملف تُسجَّل كمُستبعدة ولا تُستخدم في أي مقارنة.
    """
    samples = {s["id"]: s for s in load_samples()}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sample = samples[rec["sample_id"]]
        out = {"text": rec.get("raw_text", ""), "model": rec.get("model", "mistral-ocr-3"),
               "cloud": True, "latency_ms": rec.get("latency_ms", 0.0)}
        row = _provenance_row(sample, engine, out, page=rec.get("page", 1))
        row["audit"]["confidence_excluded"] = True
        if rec.get("cost_estimate_usd") is not None:
            row["audit"]["cost_estimate_usd"] = rec["cost_estimate_usd"]
        rows.append(row)
    return rows


def write_lock() -> dict:
    """ثبات القياس: بصمات أدوات القياس الحية في engines.lock.json."""
    import PIL
    import numpy
    import pytesseract
    tessdata_prefix = os.environ.get("TESSDATA_PREFIX", "")
    ara_langs = _require_tess_language("ara")
    lock = {
        "normalize": NORMALIZE_V1_VERSION,
        "engines": {
            "tesseract_ara": {
                "tesseract": str(pytesseract.get_tesseract_version()),
                "pytesseract": pytesseract.__version__,
                "ara_traineddata_sha256": TESSDATA_BEST_ARA_SHA256,
                "tessdata_prefix": tessdata_prefix,
                "languages_available": ara_langs,
                "psm": "6",
            },
        },
        "environment": {"PIL": PIL.__version__, "numpy": numpy.__version__},
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    LOCK_PATH.write_text(json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
    return lock


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engines", nargs="*", default=list(LOCAL_ENGINES))
    # F-14: default=None لأن SET_DIR قد يُعاد ربطه أدناه؛ يُحلّ المسار بعده.
    ap.add_argument("--out", default=None,
                    help="مسار النتائج (افتراضياً <set-dir>/results.jsonl)")
    ap.add_argument("--set-dir", default=None,
                    help="مجلد مجموعة بديلة تحوي manifest.json + samples/ + "
                         "ground_truth.jsonl. الافتراضي golden_set/ (المعيار "
                         "الاصطناعي = بوابة CI). استخدم golden_set_real/ "
                         "لصفحات القناة الحقيقية كي لا تدهس البوابة.")
    ap.add_argument("--ingest", help="JSONL نتيج سحابية ملتقطة يدوياً (بلا شبكة)")
    ap.add_argument("--allow-cloud", action="store_true",
                    help="يتطلب OMNI_ALLOW_CLOUD — يستخدم فقط خارج الاختبارات")
    ap.add_argument("--write-lock", action="store_true")
    args = ap.parse_args()

    # F-14: أعِد الربط **قبل** أي قراءة للمسارات، ثم احسم --out.
    if args.set_dir:
        set_dataset_dir(args.set_dir)
    if args.out is None:
        args.out = str(SET_DIR / "results.jsonl")

    if args.write_lock:
        print(json.dumps(write_lock(), indent=2))
        return 0
    unknown = [e for e in args.engines if e not in ENGINE_RUNNERS]
    if unknown:
        print(f"unknown engines: {unknown}", file=sys.stderr)
        return 2
    if args.ingest:
        rows = ingest_captured(Path(args.ingest))
    else:
        rows = run_local(args.engines)
    out = Path(args.out)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
