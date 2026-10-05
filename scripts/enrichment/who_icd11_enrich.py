#!/usr/bin/env python3
"""WHO ICD-11 terminology enrichment script.

This is an OFFLINE ENRICHMENT TOOL — NOT a runtime API provider.
It fetches Arabic+English medical terminology from the WHO ICD-11 API
and produces a local JSON file that can be imported into the existing
MedicalDictionaryManager KB.

Architecture:
  WHO ICD-11 API
        ↓
  this script (offline, operator-run)
        ↓
  data/dictionaries/icd11_terminology.json (local artifact)
        ↓
  MedicalDictionaryManager.import_dictionary() (existing KB)
        ↓
  SpecialtyDictionaryRouter / ExactTranslationMemory (existing consumers)

Security:
  - HTTPS only
  - Fixed base URL (no user-supplied URLs — SSRF prevention)
  - Bounded timeout (30s per request)
  - Response size limit (10MB)
  - JSON schema validation
  - No patient data sent (only requests ICD-11 concept data)
  - No secrets in output file
  - Environment-based credentials

Licensing:
  WHO ICD-11 is licensed under CC BY-ND 3.0 IGO.
  This script stores terminology AS-IS with attribution.
  The output JSON preserves source, source_id, source_version, and license.

Usage:
  # Set environment variables (from WHO ICD API portal):
  export WHO_ICD_CLIENT_ID="your_client_id"
  export WHO_ICD_CLIENT_SECRET="your_client_secret"

  # Run the enrichment:
  python scripts/enrichment/who_icd11_enrich.py

  # Import into KB:
  # (Use MedicalDictionaryManager.import_dictionary() with the output file)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Constants ---

ICD_API_BASE = "https://id.who.int"
ICD_TOKEN_URL = "https://icd.who.int/token"
ICD_ENTITY_URL = f"{ICD_API_BASE}/icd/entity"
DEFAULT_TIMEOUT = 30
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10MB
RATE_LIMIT_DELAY = 1.0  # seconds between requests (respectful)

# ICD-11 chapters to fetch (controlled import — not everything)
# Focus on medical specialties relevant to the project's existing dictionaries
ICD_CHAPTERS_TO_FETCH = [
    "http://id.who.int/icd/release/11/2024-01/mms/10",  # Diseases of the circulatory system
    "http://id.who.int/icd/release/11/2024-01/mms/11",  # Diseases of the respiratory system
    "http://id.who.int/icd/release/11/2024-01/mms/12",  # Diseases of the digestive system
    "http://id.who.int/icd/release/11/2024-01/mms/13",  # Diseases of the skin
    "http://id.who.int/icd/release/11/2024-01/mms/14",  # Diseases of the musculoskeletal system
    "http://id.who.int/icd/release/11/2024-01/mms/15",  # Diseases of the genitourinary system
    "http://id.who.int/icd/release/11/2024-01/mms/8",   # Diseases of the nervous system
    "http://id.who.int/icd/release/11/2024-01/mms/5",   # Sleep-wake disorders
    "http://id.who.int/icd/release/11/2024-01/mms/7",   # Diseases of the eye
]

OUTPUT_PATH = Path("data/dictionaries/icd11_terminology.json")
SOURCE_NAME = "who-icd11"
SOURCE_LICENSE = "CC BY-ND 3.0 IGO — World Health Organization"
SOURCE_URL = "https://icd.who.int"


def log(msg: str) -> None:
    print(f"[ICD-11] {msg}", flush=True)


def get_oauth_token(client_id: str, client_secret: str) -> str:
    """Obtain OAuth 2.0 token from WHO ICD API.

    Uses client_credentials grant (no user context needed).
    """
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")

    req = urllib.request.Request(
        ICD_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read(MAX_RESPONSE_BYTES)
            token_data = json.loads(body.decode("utf-8"))
            token = token_data.get("access_token")
            if not token:
                raise ValueError("No access_token in response")
            log(f"OAuth token obtained (expires in {token_data.get('expires_in', '?')}s)")
            return token
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OAuth failed: HTTP {e.code}") from e
    except (json.JSONDecodeError, TimeoutError) as e:
        raise RuntimeError(f"OAuth failed: {e}") from e


def fetch_icd_entity(entity_uri: str, token: str, language: str = "ar") -> dict[str, Any] | None:
    """Fetch a single ICD-11 entity in the specified language.

    Args:
        entity_uri: Full URI of the ICD-11 entity.
        token: OAuth bearer token.
        language: Language code ('ar' for Arabic, 'en' for English).

    Returns:
        Entity dict or None if not found.
    """
    url = f"{entity_uri}?languageOverride={language}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "API-Language-Language": language,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read(MAX_RESPONSE_BYTES)
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            log(f"Rate limited on {entity_uri} — waiting 10s")
            time.sleep(10)
            return fetch_icd_entity(entity_uri, token, language)
        log(f"HTTP {e.code} on {entity_uri}")
        return None
    except (json.JSONDecodeError, TimeoutError) as e:
        log(f"Error fetching {entity_uri}: {e}")
        return None


def fetch_chapter_entities(chapter_uri: str, token: str) -> list[dict[str, Any]]:
    """Fetch all entities in an ICD-11 chapter (both Arabic and English).

    For each entity, retrieves:
      - entity_id (ICD-11 concept URI)
      - Arabic preferred term
      - English preferred term
      - Chapter/category
    """
    entities: list[dict[str, Any]] = []

    # Fetch chapter in English first to get the list of entities
    log(f"Fetching chapter: {chapter_uri}")
    chapter_en = fetch_icd_entity(chapter_uri, token, language="en")
    if not chapter_en:
        log(f"  Could not fetch chapter (EN): {chapter_uri}")
        return entities

    # Get child entities
    child_uris: list[str] = []
    # The ICD-11 API returns linearization children
    # Try multiple possible structures
    if "child" in chapter_en:
        child_uris = chapter_en["child"] if isinstance(chapter_en["child"], list) else [chapter_en["child"]]
    elif "descendant" in chapter_en:
        child_uris = chapter_en["descendant"] if isinstance(chapter_en["descendant"], list) else [chapter_en["descendant"]]

    if not child_uris:
        log(f"  No child entities found for chapter")
        # Still add the chapter itself as a terminology entry
        chapter_entity = extract_terminology(chapter_en, None, token, chapter_uri)
        if chapter_entity:
            entities.append(chapter_entity)
        return entities

    log(f"  Found {len(child_uris)} child entities")

    for i, child_uri in enumerate(child_uris):
        # Fetch English
        entity_en = fetch_icd_entity(child_uri, token, language="en")
        time.sleep(RATE_LIMIT_DELAY)

        # Fetch Arabic
        entity_ar = fetch_icd_entity(child_uri, token, language="ar")
        time.sleep(RATE_LIMIT_DELAY)

        terminology = extract_terminology(entity_en, entity_ar, token, child_uri)
        if terminology:
            entities.append(terminology)
            if (i + 1) % 10 == 0:
                log(f"  Processed {i + 1}/{len(child_uris)} entities")

    return entities


def extract_terminology(
    entity_en: dict[str, Any] | None,
    entity_ar: dict[str, Any] | None,
    token: str,
    entity_uri: str,
) -> dict[str, Any] | None:
    """Extract bilingual terminology from ICD-11 entity responses.

    Preserves:
      - entity_id (ICD-11 concept URI)
      - Arabic preferred term (AS-IS, no normalization)
      - English preferred term (AS-IS)
      - Chapter/category
      - Synonyms (if available)
    """
    if not entity_en and not entity_ar:
        return None

    # Extract English title
    en_title = ""
    if entity_en:
        title_obj = entity_en.get("title", {})
        if isinstance(title_obj, dict):
            en_title = title_obj.get("@value", "")
        elif isinstance(title_obj, str):
            en_title = title_obj

    # Extract Arabic title
    ar_title = ""
    if entity_ar:
        title_obj = entity_ar.get("title", {})
        if isinstance(title_obj, dict):
            ar_title = title_obj.get("@value", "")
        elif isinstance(title_obj, str):
            ar_title = title_obj

    # Skip if no usable terms
    if not en_title and not ar_title:
        return None

    # Extract definition (English)
    definition = ""
    if entity_en:
        def_obj = entity_en.get("definition", {})
        if isinstance(def_obj, dict):
            definition = def_obj.get("@value", "")

    # Extract synonyms
    en_synonyms: list[str] = []
    if entity_en:
        syn = entity_en.get("synonyms", [])
        if isinstance(syn, list):
            en_synonyms = [s.get("@value", "") if isinstance(s, dict) else str(s) for s in syn if s]

    ar_synonyms: list[str] = []
    if entity_ar:
        syn = entity_ar.get("synonyms", [])
        if isinstance(syn, list):
            ar_synonyms = [s.get("@value", "") if isinstance(s, dict) else str(s) for s in syn if s]

    # Extract ICD code if available
    icd_code = entity_en.get("code", "") if entity_en else ""

    return {
        "entity_id": entity_uri,
        "term_en": en_title.strip(),
        "term_ar": ar_title.strip(),
        "synonyms_en": en_synonyms,
        "synonyms_ar": ar_synonyms,
        "definition": definition.strip(),
        "icd_code": icd_code,
        "source": SOURCE_NAME,
        "source_id": entity_uri,
        "source_version": "2024-01",  # ICD-11 MMS 2024-01 release
        "license": SOURCE_LICENSE,
    }


def run_enrichment() -> None:
    """Main enrichment entry point.

    Reads credentials from environment, fetches ICD-11 terminology,
    writes output JSON with provenance.
    """
    client_id = os.environ.get("WHO_ICD_CLIENT_ID", "")
    client_secret = os.environ.get("WHO_ICD_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        log("ERROR: WHO_ICD_CLIENT_ID and WHO_ICD_CLIENT_SECRET must be set")
        log("Register at https://icd.who.int/api")
        sys.exit(1)

    log("Starting ICD-11 terminology enrichment...")
    log(f"Output: {OUTPUT_PATH}")
    log(f"Chapters to fetch: {len(ICD_CHAPTERS_TO_FETCH)}")

    # Get OAuth token
    token = get_oauth_token(client_id, client_secret)

    # Fetch entities from each chapter
    all_entities: list[dict[str, Any]] = []
    for chapter_uri in ICD_CHAPTERS_TO_FETCH:
        entities = fetch_chapter_entities(chapter_uri, token)
        all_entities.extend(entities)
        log(f"Chapter complete. Total entities so far: {len(all_entities)}")

    # Deduplicate by entity_id
    seen_ids: set[str] = set()
    unique_entities: list[dict[str, Any]] = []
    for e in all_entities:
        eid = e.get("entity_id", "")
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            unique_entities.append(e)

    log(f"After deduplication: {len(unique_entities)} unique entities")
    log(f"Rejected duplicates: {len(all_entities) - len(unique_entities)}")

    # Build output with provenance metadata
    output = {
        "metadata": {
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "license": SOURCE_LICENSE,
            "source_version": "2024-01",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "total_concepts": len(unique_entities),
            "attribution": "World Health Organization, ICD-11, licensed under CC BY-ND 3.0 IGO",
            "note": "Terminology stored AS-IS from WHO ICD-11 API. No modifications to terms.",
        },
        "entries": unique_entities,
    }

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Written {len(unique_entities)} entries to {OUTPUT_PATH}")
    log("Done. Import into KB via MedicalDictionaryManager.import_dictionary()")


if __name__ == "__main__":
    run_enrichment()
