#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR-F3 — خادم التدريب التفاعلي (Flask + SocketIO, threading).

    python train_server.py --host 127.0.0.1 --port 5001

النقاط:
    GET  /              → templates/train_dashboard.html (عربي RTL)
    GET  /api/status    → حالة JSON كاملة
    POST /api/start     → بدء التدريب في Thread منفصل (يرفض المزدوج بـ 409،
                           ويرفض مجلد بيانات غير موجود بـ 400)
    POST /api/stop      → إيقاف تعاوني

أحداث SocketIO: training_started / training_update / eval_update /
training_done / training_error / training_log

الحالة العامة محمية بـ threading.Lock ضد سباقات البدء المزدوج.
منطق التدريب نفسه في ahw/train_trocr.py (قابل للاختبار headless).
"""
from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from ahw.train_trocr import TrainConfig, TrainingAborted, run_training

app = Flask(__name__)
app.config["SECRET_KEY"] = "ahw-training-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

_STATE_LOCK = threading.Lock()
_stop_event = threading.Event()

TRAINING_STATE: Dict[str, Any] = {
    "running": False,
    "status": "idle",            # idle | running | done | error | stopped
    "mode": None,
    "epoch": 0.0,
    "total_epochs": 0,
    "step": 0,
    "max_steps": 0,
    "loss": 0.0,
    "cer": None,
    "log": [],
    "output_dir": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
}


def _log_message(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _STATE_LOCK:
        TRAINING_STATE["log"].append(line)
        if len(TRAINING_STATE["log"]) > 500:
            del TRAINING_STATE["log"][:250]
    socketio.emit("training_log", {"message": line})


def _worker(cfg: TrainConfig) -> None:
    def progress(payload: Dict[str, Any]) -> None:
        if payload.get("event") == "started":
            socketio.emit("training_started", {
                "epochs": payload["epochs"], "total": payload["total_samples"],
                "mode": payload["mode"]})
            return
        with _STATE_LOCK:
            TRAINING_STATE.update({
                "epoch": payload.get("epoch", TRAINING_STATE["epoch"]),
                "step": payload.get("step", TRAINING_STATE["step"]),
                "max_steps": payload.get("max_steps",
                                         TRAINING_STATE["max_steps"]),
                "loss": payload.get("loss", TRAINING_STATE["loss"]),
            })
        socketio.emit("training_update", payload)

    def eval_upd(payload: Dict[str, Any]) -> None:
        if payload.get("cer", -1) >= 0:
            with _STATE_LOCK:
                TRAINING_STATE["cer"] = payload["cer"]
        socketio.emit("eval_update", payload)

    try:
        summary = run_training(cfg, progress_cb=progress, eval_cb=eval_upd,
                               log_cb=lambda p: _log_message(p["message"]),
                               stop_event=_stop_event)
        with _STATE_LOCK:
            TRAINING_STATE.update({"running": False, "status": "done",
                                   "loss": summary["final_loss"],
                                   "cer": summary.get("cer"),
                                   "finished_at": time.time()})
        socketio.emit("training_done", summary)
    except TrainingAborted as exc:
        with _STATE_LOCK:
            TRAINING_STATE.update({"running": False, "status": "stopped",
                                   "error": str(exc),
                                   "finished_at": time.time()})
        socketio.emit("training_error", {"error": str(exc),
                                         "status": "stopped"})
    except Exception as exc:  # noqa: BLE001 — يبث الخطأ للواجهة ثم يسجله
        with _STATE_LOCK:
            TRAINING_STATE.update({"running": False, "status": "error",
                                   "error": str(exc),
                                   "finished_at": time.time()})
        _log_message(f"خطأ: {exc}")
        socketio.emit("training_error", {"error": str(exc), "status": "error"})


def _public_state() -> Dict[str, Any]:
    with _STATE_LOCK:
        snap = dict(TRAINING_STATE)
    snap["log"] = list(snap["log"])[-200:]
    return snap


@app.route("/")
def index():
    return render_template("train_dashboard.html")


@app.route("/api/status")
def status():
    return jsonify(_public_state())


@app.route("/api/start", methods=["POST"])
def start_training():
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode", "full"))
    if mode not in ("smoke", "full"):
        return jsonify({"ok": False,
                        "error": f"mode غير صالح: {mode} (smoke|full)"}), 400

    with _STATE_LOCK:
        if TRAINING_STATE["running"]:
            return jsonify({"ok": False,
                            "error": "التدريب يعمل بالفعل — أوقفه أولًا"}), 409
        TRAINING_STATE.update({
            "running": True, "status": "running", "mode": mode,
            "epoch": 0.0, "step": 0, "max_steps": 0, "loss": 0.0, "cer": None,
            "log": [], "error": None, "started_at": time.time(),
            "finished_at": None,
            "output_dir": str(data.get("output_dir", "models/trocr-arabic")),
            "total_epochs": int(data.get("epochs", 1) or 1),
        })

    # التحقق من مجلد البيانات (full فقط — smoke اصطناعي بلا مجلد)
    if mode == "full":
        data_dir = Path(str(data.get("data_dir", "output/S001")))
        if not data_dir.exists():
            with _STATE_LOCK:
                TRAINING_STATE.update({"running": False, "status": "error",
                                       "error": f"مجلد البيانات غير موجود: {data_dir}"})
            return jsonify({"ok": False,
                            "error": f"مجلد البيانات غير موجود: {data_dir}"}), 400

    try:
        cfg = TrainConfig(
            data_dir=str(data.get("data_dir", "output/S001")),
            output_dir=str(data.get("output_dir", "models/trocr-arabic")),
            epochs=int(data.get("epochs", 1) or 1),
            batch=int(data.get("batch", 2) or 2),
            lr=float(data.get("lr", 5e-5) or 5e-5),
            base_model=str(data.get("base_model",
                                    "microsoft/trocr-base-handwritten")),
            mode=mode,
            dry_run_model=bool(data.get("dry_run_model", mode == "smoke")),
        )
    except (TypeError, ValueError) as exc:
        with _STATE_LOCK:
            TRAINING_STATE.update({"running": False, "status": "error",
                                   "error": f"معاملات غير صالحة: {exc}"})
        return jsonify({"ok": False, "error": f"معاملات غير صالحة: {exc}"}), 400

    _stop_event.clear()
    thread = threading.Thread(target=_worker, args=(cfg,), daemon=True,
                              name="atr-training")
    thread.start()
    _log_message(f"بدء تدريب mode={mode} epochs={cfg.epochs} "
                 f"batch={cfg.batch} lr={cfg.lr}")
    return jsonify({"ok": True, "mode": mode, "thread": thread.name})


@app.route("/api/stop", methods=["POST"])
def stop_training():
    with _STATE_LOCK:
        if not TRAINING_STATE["running"]:
            return jsonify({"ok": False, "error": "لا يوجد تدريب جارٍ"}), 400
    _stop_event.set()
    _log_message("طلب إيقاف تعاوني أُرسل")
    return jsonify({"ok": True})


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5001)
    args = ap.parse_args(argv)
    print(f"🌐 Training UI: http://{args.host}:{args.port}")
    socketio.run(app, host=args.host, port=args.port,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
