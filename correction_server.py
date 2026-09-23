#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR — خادم تصحيح قصاصات الكلمات (Human-in-the-Loop).

    python correction_server.py --sample S001 --port 5000

يقرأ قصاصات `output/<sample>/batch_*/` (metadata_all.csv إن وُجد، وإلا دمج
batch_*/metadata.csv في الذاكرة)، ويعرضها شبكةً قابلة للتصحيح (عربي RTL).
الحفظ يكتب `corrections.xlsx` + `corrections.csv` في مجلد العينة — وهما
مدخل `train_server.py` (ATR-F3).

أمان PHI: الربط الافتراضي 127.0.0.1 فقط (محلي). لا شبكة، لا خدمات خارجية.
هذا الملف مستقل تمامًا عن محركات OCR المركزية (adapter/engines) — لا يستوردها.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from flask import Flask, abort, jsonify, request, send_from_directory

app = Flask(__name__)

DEFAULT_ROOT = Path("output")
_STATE: Dict[str, Any] = {"sample": None, "root": None}


def _sample_dir() -> Path:
    return Path(_STATE["root"]) / _STATE["sample"]


def load_words(sample_dir: Path) -> pd.DataFrame:
    """metadata_all.csv إن وجد، وإلا دمج batch_*/metadata.csv (مع عمود batch)."""
    merged = sample_dir / "metadata_all.csv"
    if merged.exists():
        df = pd.read_csv(merged)
    else:
        frames: List[pd.DataFrame] = []
        for bdir in sorted(sample_dir.glob("batch_*")):
            csv = bdir / "metadata.csv"
            if csv.exists():
                part = pd.read_csv(csv)
                part["batch"] = bdir.name
                frames.append(part)
        if not frames:
            return pd.DataFrame(columns=["word_id", "crop_path", "text",
                                         "status", "page", "batch"])
        df = pd.concat(frames, ignore_index=True)
    for col in ("text", "status"):
        if col not in df.columns:
            df[col] = ""
    df["text"] = df["text"].fillna("").astype(str)
    return df


@app.route("/")
def index():
    sample_dir = _sample_dir()
    if not sample_dir.exists():
        return (f"<html dir='rtl'><meta charset='utf-8'><body style='font-family:Tahoma'>"
                f"<h2>⚠️ العينة غير موجودة</h2><p>المجلد <code>{sample_dir}</code> "
                f"غير موجود. شغّل أولًا:</p><pre>python segment_batch.py SCAN.pdf "
                f"--sample {_STATE['sample']}</pre></body></html>"), 404
    return PAGE_HTML


@app.route("/api/words")
def api_words():
    df = load_words(_sample_dir())
    df = df.where(pd.notna(df), None)
    records = df.head(5000).to_dict(orient="records")
    # مسار التقديم الحقيقي = <batch>/<crop_path> (crop_path نسبي لمجلد الدفعة)
    for r in records:
        cp = r.get("crop_path") or ""
        b = r.get("batch")
        r["crop_url"] = f"{b}/{cp}" if b and not cp.startswith(str(b)) else cp
    return jsonify({"count": int(len(df)), "words": records})


@app.route("/api/save", methods=["POST"])
def api_save():
    payload = request.get_json(silent=True) or {}
    items = payload.get("words")
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "words مفقود"}), 400
    sample_dir = _sample_dir()
    if not sample_dir.exists():
        return jsonify({"ok": False, "error": "مجلد العينة غير موجود"}), 400

    df = load_words(sample_dir)
    index = {str(r["word_id"]): i for i, r in df.iterrows()} if "word_id" in df.columns else {}
    corrected = 0
    for item in items:
        wid = str(item.get("word_id", ""))
        if wid not in index:
            continue
        i = index[wid]
        new_text = str(item.get("text", "")).strip()
        df.at[i, "text"] = new_text
        df.at[i, "status"] = "CORRECTED" if new_text else "EMPTY"
        if new_text:
            corrected += 1

    xlsx = sample_dir / "corrections.xlsx"
    csv = sample_dir / "corrections.csv"
    keep = [c for c in ("word_id", "sample_id", "page", "batch", "column",
                        "line_idx", "word_idx", "crop_path", "source_page",
                        "text", "status") if c in df.columns]
    out = df[keep].copy()
    out["source_page"] = out.get("page", out.get("batch", ""))
    out.to_excel(xlsx, index=False, engine="openpyxl")
    out.to_csv(csv, index=False, encoding="utf-8-sig")
    return jsonify({"ok": True, "saved": int(len(out)),
                    "corrected": corrected, "files": [str(xlsx), str(csv)]})


@app.route("/crops/<path:relpath>")
def serve_crop(relpath: str):
    """يقدّم صورة القصاصة من مجلد العينة (مسار مقيد داخله)."""
    base = _sample_dir().resolve()
    target = (base / relpath).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        abort(404)
    return send_from_directory(base, relpath)


PAGE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><title>تصحيح قصاصات الكلمات — AHW</title>
<style>
body{font-family:Tahoma,sans-serif;background:#1a1a2e;color:#eee;margin:0;padding:16px}
h1{color:#00d4ff;font-size:22px}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.cell{background:#16213e;border-radius:8px;padding:8px;text-align:center}
.cell img{max-width:100%;height:64px;object-fit:contain;background:#fff;border-radius:4px}
.cell input{width:100%;box-sizing:border-box;margin-top:6px;padding:6px;border-radius:4px;
            border:1px solid #333;background:#0f3460;color:#eee;font-size:15px;text-align:right}
.cell .wid{font-size:10px;color:#777;margin-top:4px;direction:ltr}
.cell.dirty input{border-color:#fd7e14}
#bar{position:sticky;top:0;background:#16213e;padding:10px;border-radius:8px;
     margin-bottom:12px;display:flex;gap:12px;align-items:center;z-index:9}
button{background:#00d4ff;border:0;padding:10px 22px;border-radius:8px;font-weight:bold;
       font-size:15px;cursor:pointer}
#msg{color:#8f8}
</style></head>
<body>
<h1>✍️ تصحيح قصاصات الكلمات</h1>
<div id="bar">
  <button onclick="saveAll()">💾 حفظ corrections.xlsx</button>
  <span id="stats">…</span><span id="msg"></span>
</div>
<div id="grid"></div>
<script>
let WORDS=[];
async function load(){
  const r=await fetch('/api/words'); const d=await r.json();
  WORDS=d.words; document.getElementById('stats').textContent=`${d.count} كلمة`;
  const g=document.getElementById('grid'); g.innerHTML='';
  WORDS.forEach((w,i)=>{
    const cell=document.createElement('div'); cell.className='cell';
    cell.innerHTML=`<img loading="lazy" src="/crops/${w.crop_url||w.crop_path}" alt="">`+
      `<input dir="rtl" value="${(w.text||'').replace(/"/g,'&quot;')}" data-i="${i}">`+
      `<div class="wid">${w.word_id||''}</div>`;
    const inp=cell.querySelector('input');
    inp.addEventListener('input',()=>{WORDS[i].text=inp.value;cell.classList.add('dirty');});
    g.appendChild(cell);
  });
}
async function saveAll(){
  document.getElementById('msg').textContent='…جاري الحفظ';
  const r=await fetch('/api/save',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({words:WORDS.map(w=>({word_id:w.word_id,text:w.text||''}))})});
  const d=await r.json();
  document.getElementById('msg').textContent= d.ok?
    `✔ حُفظ ${d.saved} صفًا (${d.corrected} مصححًا)` : `✖ ${d.error}`;
  document.querySelectorAll('.cell.dirty').forEach(c=>c.classList.remove('dirty'));
}
load();
</script></body></html>"""


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", default="S001")
    ap.add_argument("--data-root", default=str(DEFAULT_ROOT))
    ap.add_argument("--host", default="127.0.0.1",
                    help="افتراضيًا محلي فقط (حماية PHI)")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args(argv)
    _STATE["sample"] = args.sample
    _STATE["root"] = args.data_root
    print(f"✍️  Correction UI: http://{args.host}:{args.port} "
          f"(sample={args.sample}, root={args.data_root})")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
