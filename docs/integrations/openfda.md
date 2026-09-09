# openFDA Integration

## Purpose
Drug metadata lookup — generic/brand names, FDA drug labels, adverse events, NDC directory.

## API
- **Base URL**: `https://api.fda.gov`
- **Documentation**: https://open.fda.gov
- **Auth**: apiKey (optional — 240 req/min without, 120K/day with)
- **HTTPS**: Yes
- **License**: Open FDA data — public domain (US Government work)

## Endpoints
- `GET /drug/label.json` — Drug labeling information (262K+ records)
- `GET /drug/ndc.json` — National Drug Code directory (137K+ records)
- `GET /drug/drugsfda.json` — FDA-approved drugs (29K+ records)

## Configuration
```bash
# Optional — works without key at 240 req/min
OPENFDA_API_KEY=your_api_key_here
```

## Caching
- **TTL**: 7 days (drug metadata is stable)
- **Cache key**: Full request URL
- **No patient data cached**: Only drug name/metadata queries

## Privacy
- Only drug name queries are sent — **no patient data**
- No clinical notes, no patient identifiers

## Failure Behavior
- Rate limited (429): Retry with backoff (max 3 retries)
- Timeout (30s): Fail gracefully, fall back to local glossary
- HTTP error: Log error, fall back to local dictionary
- **Application continues without internet access**

## Testing
- Unit tests with mocked HTTP responses
- Failure tests: timeout, rate limit, invalid response, HTTP error
- No external internet dependency in test suite
