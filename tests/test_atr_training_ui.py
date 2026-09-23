"""ATR-F3 — اختبارات واجهة التدريب (train_server) + خادم التصحيح + نواة التدريب.

كل البيانات اصطناعية (صفر PHI). اختبار smoke يثبت خط الأنابيب كاملًا بنموذج
dry_run صغير بلا أي تنزيل.
"""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

import pandas as pd
import pytest

import correction_server
import train_server
from ahw.train_trocr import (TrainConfig, load_corrections,
                             make_synthetic_samples, run_training,
                             split_by_source_page)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def client():
    """عميل اختبار مع عزل حالة التدريب العامة (منع تسرب بين الاختبارات)."""
    with train_server._STATE_LOCK:
        saved = copy.deepcopy(train_server.TRAINING_STATE)
    train_server.app.config["TESTING"] = True
    with train_server.app.test_client() as c:
        yield c
    with train_server._STATE_LOCK:
        train_server.TRAINING_STATE.clear()
        train_server.TRAINING_STATE.update(saved)
    train_server._stop_event.clear()


def _force_running(client):
    with train_server._STATE_LOCK:
        train_server.TRAINING_STATE["running"] = True
        train_server.TRAINING_STATE["status"] = "running"


# ---------------------------------------------------------------------------
# /api/status
# ---------------------------------------------------------------------------
def test_status_returns_required_fields(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    for field in ("running", "status", "epoch", "total_epochs", "step",
                  "loss", "cer", "log", "output_dir", "error", "mode"):
        assert field in data, f"الحقل {field} ناقص من /api/status"
    assert data["running"] is False


# ---------------------------------------------------------------------------
# /api/start — رفض البدء المزدوج والتحقق من المدخلات
# ---------------------------------------------------------------------------
def test_start_rejects_double_start_with_409(client):
    _force_running(client)
    r = client.post("/api/start", json={"mode": "smoke"})
    assert r.status_code == 409
    body = r.get_json()
    assert body["ok"] is False
    assert "بالفعل" in body["error"]


def test_start_rejects_missing_data_dir_with_400(client, tmp_path):
    missing = tmp_path / "no-such-sample-dir"
    r = client.post("/api/start",
                    json={"mode": "full", "data_dir": str(missing)})
    assert r.status_code == 400
    body = r.get_json()
    assert body["ok"] is False
    assert str(missing) in body["error"]
    # الحالة أعيدت إلى غير مشغولة بعد الرفض
    s = client.get("/api/status").get_json()
    assert s["running"] is False


def test_start_rejects_invalid_mode(client):
    r = client.post("/api/start", json={"mode": "nonsense"})
    assert r.status_code == 400


def test_start_accepts_smoke_and_marks_running(client):
    r = client.post("/api/start",
                    json={"mode": "smoke", "epochs": 1,
                          "output_dir": ""})
    # قد يكتمل العامل فورًا؛ المقبول: 200 وبدء مسجل
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    # انتظر اكتمال الـ smoke الخفيف (نموذج صغير) حتى لا يتسرب thread
    deadline = time.time() + 240
    while time.time() < deadline:
        s = client.get("/api/status").get_json()
        if not s["running"]:
            break
        time.sleep(0.5)
    s = client.get("/api/status").get_json()
    assert s["status"] in ("done", "error"), json.dumps(s, ensure_ascii=False)
    assert s["status"] == "done", f"فشل smoke: {s.get('error')}"


# ---------------------------------------------------------------------------
# الصفحة الرئيسية
# ---------------------------------------------------------------------------
def test_index_returns_200_with_core_elements(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert "startBtn" in html
    assert "statusBadge" in html
    assert "progressFill" in html
    assert "/socket.io/socket.io.js" in html  # بلا CDN خارجي


# ---------------------------------------------------------------------------
# نواة التدريب (headless) — split + smoke
# ---------------------------------------------------------------------------
def test_split_by_source_page_no_leak():
    df = pd.DataFrame({
        "text": ["كلمة"] * 30,
        "crop_path": [f"batch_001/crops/w{i}.png" for i in range(30)],
        "source_page": [f"page-{i % 10:02d}" for i in range(30)],
    })
    tr, va, te = split_by_source_page(df, seed=7)
    tr_pages = set(tr["source_page"])
    va_pages = set(va["source_page"])
    te_pages = set(te["source_page"])
    assert tr_pages.isdisjoint(va_pages)
    assert tr_pages.isdisjoint(te_pages)
    assert va_pages.isdisjoint(te_pages)
    assert len(tr) + len(va) + len(te) == len(df)
    assert 0.6 <= len(tr) / len(df) <= 0.95


def test_run_training_smoke_end_to_end(tmp_path):
    """epoch واحد على 10 عينات اصطناعية بنموذج dry_run — إثبات خط الأنابيب."""
    events = {"progress": 0, "logs": 0}
    summary = run_training(
        TrainConfig(mode="smoke", epochs=1, batch=2,
                    output_dir=str(tmp_path / "smoke-out")),
        progress_cb=lambda p: events.__setitem__("progress",
                                                 events["progress"] + 1),
        log_cb=lambda p: events.__setitem__("logs", events["logs"] + 1),
    )
    assert summary["mode"] == "smoke"
    assert summary["train_samples"] == 8
    assert summary["val_samples"] == 2
    assert summary["final_loss"] > 0.0
    assert summary["output_dir"] is None  # smoke لا يحفظ أوزانًا
    assert events["logs"] >= 2
    assert (tmp_path / "smoke-out").exists()


def test_load_corrections_reads_xlsx_and_csv(tmp_path):
    df = pd.DataFrame({
        "word_id": ["w1", "w2"],
        "crop_path": ["batch_001/crops/w1.png", "batch_001/crops/w2.png"],
        "text": ["المريض", "  ضغط "],
        "source_page": ["page-01", "page-01"],
        "status": ["CORRECTED", "CORRECTED"],
    })
    df.to_excel(tmp_path / "corrections.xlsx", index=False)
    loaded = load_corrections(tmp_path)
    assert len(loaded) == 2
    assert loaded.iloc[1]["text"] == "ضغط"  # trim
    (tmp_path / "corrections.xlsx").unlink()
    df.to_csv(tmp_path / "corrections.csv", index=False)
    assert len(load_corrections(tmp_path)) == 2


def test_synthetic_samples_have_no_phi():
    samples = make_synthetic_samples(n=4)
    assert len(samples) == 4
    for s in samples:
        assert s["image"].size == (96, 32)
        assert s["text"] in {"المريض", "ألم", "ضغط", "الدواء", "الجراحة",
                             "العظمية"}


# ---------------------------------------------------------------------------
# correction_server — خدمة القصاصات + الحفظ
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_tree(tmp_path, monkeypatch):
    root = tmp_path / "output"
    sdir = root / "S001" / "batch_001"
    (sdir / "crops").mkdir(parents=True)
    import cv2
    import numpy as np
    rows = []
    for i in range(3):
        rel = f"batch_001/crops/S001_P01_C01_L01_W{i:02d}.png"
        cv2.imwrite(str(root / "S001" / rel),
                    np.full((24, 64), 255, dtype=np.uint8))
        rows.append({"word_id": f"S001_P01_C01_L01_W{i:02d}",
                     "sample_id": "S001", "page": 1, "column": 1,
                     "line_idx": 1, "word_idx": i, "crop_path": rel,
                     "text": "", "status": "RAW"})
    pd.DataFrame(rows).to_csv(sdir / "metadata.csv", index=False,
                              encoding="utf-8-sig")
    monkeypatch.setitem(correction_server._STATE, "sample", "S001")
    monkeypatch.setitem(correction_server._STATE, "root", str(root))
    return root / "S001"


def test_correction_index_and_words(sample_tree):
    c = correction_server.app.test_client()
    assert c.get("/").status_code == 200
    r = c.get("/api/words")
    assert r.status_code == 200
    assert r.get_json()["count"] == 3


def test_correction_index_404_for_missing_sample(tmp_path, monkeypatch):
    monkeypatch.setitem(correction_server._STATE, "sample", "NOPE")
    monkeypatch.setitem(correction_server._STATE, "root", str(tmp_path))
    c = correction_server.app.test_client()
    assert c.get("/").status_code == 404


def test_correction_save_writes_xlsx_and_csv(sample_tree):
    c = correction_server.app.test_client()
    payload = {"words": [
        {"word_id": "S001_P01_C01_L01_W00", "text": "المريض"},
        {"word_id": "S001_P01_C01_L01_W01", "text": "ضغط"},
        {"word_id": "S001_P01_C01_L01_W02", "text": ""},
    ]}
    r = c.post("/api/save", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["corrected"] == 2
    xlsx = sample_tree / "corrections.xlsx"
    csv = sample_tree / "corrections.csv"
    assert xlsx.exists() and csv.exists()
    df = pd.read_excel(xlsx)
    assert "source_page" in df.columns and "status" in df.columns
    assert df.iloc[0]["text"] == "المريض"
    assert df.iloc[0]["status"] == "CORRECTED"
    assert df.iloc[2]["status"] == "EMPTY"
    # ما حُفظ قابل للاستهلاك مباشرة من نواة التدريب
    loaded = load_corrections(sample_tree)
    assert len(loaded) == 2  # الصف الفارغ مُستبعد


def test_crop_serving_blocks_path_traversal(sample_tree):
    c = correction_server.app.test_client()
    ok = c.get("/crops/batch_001/crops/S001_P01_C01_L01_W00.png")
    assert ok.status_code == 200
    bad = c.get("/crops/../../etc/passwd")
    assert bad.status_code == 404


def test_start_full_rejects_when_not_running_but_validates_first(client,
                                                                 tmp_path):
    """ترتيب التحقق: المجلد قبل بدء Thread — لا thread يتيم عند الرفض."""
    before = threading.active_count()
    r = client.post("/api/start",
                    json={"mode": "full",
                          "data_dir": str(tmp_path / "missing")})
    assert r.status_code == 400
    time.sleep(0.2)
    assert threading.active_count() <= before
