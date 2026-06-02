# ADR-003: Multi-Profile Docker Deployment

## Status
Accepted

## Context
Medical handwriting OCR has vastly different resource requirements depending on the deployment context. A developer testing locally has different needs than a hospital running in production. We need to support multiple deployment configurations without maintaining separate Dockerfiles.

## Decision
Adopt a profile-based Docker Compose structure:
- `docker/profiles/lite/` — CPU-only, SQLite, 2 engines (development/testing)
- `docker/profiles/standard/` — Multi-engine, PostgreSQL, GPU optional (staging)
- `docker/profiles/gpu-production/` — Full stack, all engines, monitoring (production)

Each profile has its own `docker-compose.yml` that references the same Dockerfile with different build targets.

## Consequences

### Positive
- Clear separation of dev/staging/prod configurations
- Easy to switch: `docker compose -f docker/profiles/<name>/docker-compose.yml up`
- Each profile documents its minimum resource requirements
- Production profile includes monitoring stack

### Negative
- Three compose files to maintain
- Profile-specific bugs may go unnoticed without testing each profile

### Guidelines
- New services should be added to all three profiles (or marked as profile-specific)
- Resource limits must be documented in DOCKER_PROFILES.md
