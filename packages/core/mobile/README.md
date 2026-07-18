# OmniFile Mobile Review Server (PWA + Learning Loop)

> **Single canonical location**: `packages/core/mobile/`
>
> This directory consolidates what was previously duplicated across 4
> package locations (handwriting, omnifile, file_processor, apps/handwriting-demo).
> See the consolidation commit `chore/unify-mobile-and-learning` for details.

## What this is

A Flask server + PWA shell that lets users review OCR results on their
phone and **teaches the system from their corrections**:

1. User opens the PWA on their phone (`http://<host>:5000`)
2. Uploads a medical document image
3. Reviews the OCR output, corrects mistakes
4. Each correction is persisted to THREE stores simultaneously:
   - `CorrectionsDictManager` (JSON dictionary)
   - `WordCorrectionDB` (SQLite)
   - `ActiveLearner` (SQLite — triggers retraining when threshold reached)
5. On the next OCR request, `HybridSpellChecker` automatically picks up
   the new corrections — no restart needed.

See [`docs/MOBILE_LEARNING_LOOP.md`](../../docs/MOBILE_LEARNING_LOOP.md)
for the full data-flow diagram.

## Quick start

### Option 1: Run directly (development)

```bash
# From the monorepo root
PYTHONPATH=. python -m packages.core.mobile.server --host 0.0.0.0 --port 5000
```

Then open `http://localhost:5000` in your browser, or
`http://<your-lan-ip>:5000` from a phone on the same network.

For remote access: `ngrok http 5000`.

### Option 2: Run via Docker (production)

```bash
# Build + run via docker compose
docker compose -f docker-compose.mobile.yml up --build

# Or just the image:
docker build -f Dockerfile.mobile -t omni-medical-suite:mobile .
docker run -p 5000:5000 -v $(pwd)/data:/app/data omni-medical-suite:mobile
```

## Endpoints

| Method | Path                              | Description                                    |
|--------|-----------------------------------|------------------------------------------------|
| GET    | `/`                               | PWA shell (templated review page)              |
| GET    | `/mobile/ocr-review.html`         | Standalone PWA shell (manifest start_url)      |
| GET    | `/manifest.json`                  | PWA manifest (correct MIME type)               |
| GET    | `/service-worker.js`              | PWA offline cache (service worker)             |
| GET    | `/static/offline.html`            | Offline fallback page                          |
| GET    | `/static/<filename>`              | Static assets                                  |
| GET    | `/images/<filename>`              | Original uploaded images                       |
| POST   | `/process`                        | Upload image → live OCR pipeline               |
| POST   | `/save`                           | Save user corrections → learning loop          |
| GET    | `/load`                           | Reload saved corrections (resume session)      |
| GET    | `/stats`                          | Learning-loop stats dashboard                  |
| GET    | `/health`                         | Docker / load-balancer healthcheck             |

## PWA installability checklist

All 11 standard PWA installability requirements are met:

- ✅ `name`, `short_name`
- ✅ `start_url`, `scope`
- ✅ `display: standalone`
- ✅ `theme_color`, `background_color`
- ✅ `lang: ar`, `dir: rtl`
- ✅ Icons at 192×192 and 512×512 (SVG, maskable)
- ✅ `shortcuts` (review + stats)
- ✅ Service worker registered (`/service-worker.js`)
- ✅ Offline fallback page (`/static/offline.html`)
- ✅ Manifest linked from HTML (`<link rel="manifest">`)
- ✅ HTTPS-ready (use ngrok or a reverse proxy for production)

## Environment variables

| Variable              | Default                  | Purpose                                     |
|-----------------------|--------------------------|---------------------------------------------|
| `OMNI_MOBILE_DB_DIR`  | `<monorepo>/data`        | Where SQLite DBs + JSON dictionaries live   |
| `ENABLE_LLM`          | `false`                  | Enable Jais proofreading (requires GPU)     |
| `PYTHONPATH`          | `/app` (in Docker)       | Module resolution                           |

## Files

```
packages/core/mobile/
├── __init__.py            # Package marker
├── README.md              # This file
├── manifest.json          # PWA manifest (with icons, shortcuts, scope)
├── ocr-review.html        # PWA shell (single-file HTML+CSS+JS)
├── server.py              # Flask server (shares app.services.*)
├── static/
│   ├── offline.html       # Offline fallback page
│   └── service-worker.js  # PWA offline cache strategy
└── templates/
    └── review.html        # Server-rendered review page (legacy)
```

## Architecture

The mobile server is **not an isolated Flask app**. It imports
`app.services.ocr_service` and `app.services.review_service` directly —
the same modules used by `app/gradio_full_hitl.py`. This means:

- Image preprocessing, OCR ensemble, spell checking, and NER all run
  through the SAME code path regardless of whether the request came
  from the web (Gradio) or the mobile (Flask/PWA).
- Any improvement to `app.services.*` automatically benefits both
  frontends.
- No second parallel pipeline to maintain.

The learning loop is wired in `POST /save`:

```python
# Each correction is routed to three stores simultaneously:
corrections_mgr.add(predicted, corrected)        # JSON dict
word_trainer_db.save_batch([{...}])                # SQLite (HybridSpellChecker)
active_learner.log_correction(...)                 # SQLite (retraining trigger)
```

Live-verified: after `POST /save {predicted: 'السللام', corrected: 'السلام'}`,
the next call to `HybridSpellChecker.get_suggestions('السللام')` returns
`['السلام']` automatically.

## Related files

- `docs/MOBILE_LEARNING_LOOP.md` — Full data-flow diagram
- `Dockerfile.mobile` — Docker build for this server
- `docker-compose.mobile.yml` — Docker Compose for standalone deployment
- `app/services/ocr_service.py` — Shared OCR pipeline
- `packages/core/corrections_manager.py` — JSON dictionary manager
- `packages/core/word_trainer.py` — SQLite corrections DB
- `packages/ai/active_learning.py` — Active learner (triggers retraining)
