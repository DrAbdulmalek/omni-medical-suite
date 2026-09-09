# PubMed Integration

## Purpose
Biomedical literature search and metadata retrieval — terminology verification.

## API
- **Base URL**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- **Documentation**: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- **Auth**: apiKey (optional — 3 req/sec without, 10/sec with)
- **HTTPS**: Yes
- **License**: NCBI terms of use — metadata only, no full text redistribution

## Endpoints
- `GET /esearch.fcgi` — Search PubMed by term
- `GET /esummary.fcgi` — Get article metadata (title, authors, journal)
- `GET /efetch.fcgi` — Get article abstract (NOT full text — respect copyright)

## Configuration
```bash
# Optional — works without key at 3 req/sec
NCBI_API_KEY=your_api_key_here
```

## Caching
- **TTL**: 7 days (article metadata is immutable)
- **Cache key**: Full request URL

## Privacy
- Search terms are **medical terminology** — NOT patient data
- No clinical notes or patient documents sent

## Failure Behavior
- Rate limited (429): Retry with backoff
- Timeout (30s): Fail gracefully, fall back to local glossary
- **PubMed is an optional enrichment provider** — not in critical translation path
- **Application continues without internet access**
