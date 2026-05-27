# Legacy Code

This directory contains deprecated code that has been superseded by newer implementations.

## api_server.py

**Status:** Deprecated — use `services/api/app/main.py` instead.

This was a simple HTTP stub using `BaseHTTPRequestHandler`. The production API
is now a full FastAPI application located at `services/api/app/main.py`.

### Migration

- Old: `python services/api/api_server.py`
- New: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

All Dockerfiles, CI, and documentation now reference the FastAPI entry-point.
