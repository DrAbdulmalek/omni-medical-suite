# RxNorm Integration

## Purpose
Drug terminology normalization — brand→generic mapping, RxCUI lookup, drug interactions.

## API
- **Base URL**: `https://rxnav.nlm.nih.gov/REST`
- **Documentation**: https://rxnav.nlm.nih.gov/
- **Auth**: None required
- **HTTPS**: Yes
- **License**: NLM public data — terms of use apply

## Endpoints
- `GET /rxcui.json?name={drug}` — Lookup RxCUI by drug name
- `GET /rxcui/{rxcui}/allProperties.json` — Drug concept properties
- `GET /rxcui/{rxcui}/allrelated.json` — Related drug concepts

## Configuration
No configuration required — no API key needed.

## Caching
- **TTL**: 24 hours (terminology is relatively stable)
- **Cache key**: Full request URL

## Privacy
- Only drug name queries are sent — **no patient data**

## Failure Behavior
- Timeout: Fail gracefully, fall back to local drug dictionary
- HTTP error: Log error, use openFDA as secondary fallback
- **Application continues without internet access**
