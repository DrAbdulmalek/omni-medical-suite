#!/usr/bin/env python3
"""
Live integration test for packages.core.mobile.server.

Verifies the full mobile learning loop:
  1. Start the Flask server on a random port (background thread)
  2. GET /stats → capture initial counter value
  3. POST /save with a sample correction payload
  4. GET /stats again → verify counter incremented
  5. GET /health → sanity check

This is the "independent verification step" requested after the mobile learning loop merge round.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, f"{REPO_ROOT}/packages")

# Import the Flask app — module-level side effects will fire (app.services.* load, learning loop wiring)
from packages.core.mobile import server  # noqa: E402

app = server.app


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_get(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        return e.code, e.read()
    except URLError as e:
        return -1, str(e).encode()


def http_post_json(url: str, payload: dict, timeout: float = 5.0) -> tuple[int, bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except HTTPError as e:
        return e.code, e.read()
    except URLError as e:
        return -1, str(e).encode()


def extract_counter(stats_body: bytes) -> dict[str, int]:
    """
    Extract all known counters from /stats response.
    Returns a dict mapping counter name → value.
    Multiple counters are tracked so we can verify ANY of them increments.
    """
    counters: dict[str, int] = {}
    try:
        data = json.loads(stats_body)
    except json.JSONDecodeError:
        return counters

    # corrections_dict.count
    cd = data.get("corrections_dict", {})
    if isinstance(cd, dict) and isinstance(cd.get("count"), int):
        counters["corrections_dict.count"] = cd["count"]
    if isinstance(cd, dict) and isinstance(cd.get("arabic_count"), int):
        counters["corrections_dict.arabic_count"] = cd["arabic_count"]

    # word_trainer.total
    wt = data.get("word_trainer", {})
    if isinstance(wt, dict) and isinstance(wt.get("total"), int):
        counters["word_trainer.total"] = wt["total"]

    # active_learning.training_stats_ar.total_corrections
    al = data.get("active_learning", {})
    if isinstance(al, dict):
        ts = al.get("training_stats_ar", {})
        if isinstance(ts, dict) and isinstance(ts.get("total_corrections"), int):
            counters["active_learning.total_corrections"] = ts["total_corrections"]

    return counters


def main() -> int:
    port = find_free_port()
    print(f"[live-test] starting Flask server on 127.0.0.1:{port}")

    # Disable Flask reloader + debug to keep threading.simple
    app.config["TESTING"] = True
    server_kwargs = dict(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    # Run Flask in a background thread (werkzeug.serving.make_server is the cleanest way)
    from werkzeug.serving import make_server

    httpd = make_server(app, **server_kwargs) if False else make_server(server_kwargs["host"], server_kwargs["port"], app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    # Wait for server to be ready (poll /health)
    base = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(20):
        time.sleep(0.25)
        status, body = http_get(f"{base}/health", timeout=2.0)
        if status == 200:
            ready = True
            break
    if not ready:
        print("[live-test] FAIL — server did not become ready on /health")
        httpd.shutdown()
        return 1
    print(f"[live-test] /health returned 200: {body[:200].decode('utf-8', errors='replace')}")

    # Step 1: GET /stats (initial)
    status, body = http_get(f"{base}/stats", timeout=5.0)
    print(f"[live-test] /stats (initial) status={status} body[:300]={body[:300].decode('utf-8', errors='replace')}")
    if status != 200:
        print(f"[live-test] FAIL — /stats returned {status}")
        httpd.shutdown()
        return 1
    counters_before = extract_counter(body)
    print(f"[live-test] counters_before = {counters_before}")

    # Step 2: POST /save with a sample correction (Shape A — list of corrections)
    # Use a unique original_text per run (timestamp suffix) so the active_learning
    # counter actually increments — the DB deduplicates identical corrections.
    import time as _time
    unique_suffix = str(int(_time.time()))
    sample_corrections = [
        {
            "id": f"live-test-blk-{unique_suffix}",
            "original_text": f"السللام عليكم {unique_suffix}",  # unique per run
            "corrected_text": "السلام عليكم",
            "bbox": [10, 20, 30, 40],
            "image_path": "/tmp/live-test-nonexistent.png",
            "source": "live-integration-test",
        }
    ]
    status, body = http_post_json(f"{base}/save", sample_corrections, timeout=10.0)
    print(f"[live-test] /save status={status} body[:300]={body[:300].decode('utf-8', errors='replace')}")
    if status not in (200, 201):
        print(f"[live-test] FAIL — /save returned {status}")
        httpd.shutdown()
        return 1

    # Step 3: GET /stats again — counter should have incremented
    time.sleep(0.5)  # give the learning loop a moment to flush
    status, body = http_get(f"{base}/stats", timeout=5.0)
    print(f"[live-test] /stats (after save) status={status} body[:300]={body[:300].decode('utf-8', errors='replace')}")
    if status != 200:
        print(f"[live-test] FAIL — /stats (after save) returned {status}")
        httpd.shutdown()
        return 1
    counters_after = extract_counter(body)
    print(f"[live-test] counters_after  = {counters_after}")

    # Step 4: Verify AT LEAST ONE counter incremented
    if not counters_before or not counters_after:
        print("[live-test] FAIL — could not extract any counters from /stats")
        httpd.shutdown()
        return 1

    incremented: list[str] = []
    for name, val_after in counters_after.items():
        val_before = counters_before.get(name)
        if val_before is not None and val_after > val_before:
            incremented.append(f"{name}: {val_before} → {val_after}")

    if not incremented:
        print(f"[live-test] FAIL — no counters incremented")
        print(f"  before: {counters_before}")
        print(f"  after:  {counters_after}")
        httpd.shutdown()
        return 1

    print(f"[live-test] PASS — counters incremented:")
    for inc in incremented:
        print(f"  ✅ {inc}")
    httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
