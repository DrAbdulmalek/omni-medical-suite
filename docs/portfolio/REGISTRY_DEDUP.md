# REGISTRY DEDUP — TASK 002 (PHASE 1)

## Finding (PROVEN)
`sha256sum` at base 39640a6d:
- packages/core/engine_registry.py            = 63178968…c4a
- hf-space/packages/core/engine_registry.py   = 63178968…c4a
→ **byte-identical** copies. `diff` empty.

## Decision (evidence-based deviation, documented per E7)
Plan TASK 002 step 3 proposed converting the hf-space copy into an import shim.
**Deferred**, reason: hf-space/ is deployed standalone to Hugging Face Spaces
(workflows: deploy-to-hf.yml, hf-space-drift.yml, keep-spaces-awake.yml); an
in-repo import shim risks breaking the Space's isolated runtime, and the suite
already carries a drift-control mechanism. Instead:
1. Canonical source declared: `packages/core/engine_registry.py`.
2. Consistency guard added: `packages/core/tests/test_engine_registry_consistency.py`
   (fails CI if copies diverge; asserts canonical engine IDs).
3. Shim consolidation → moved to PHASE 5 (CANONICALIZATION) pending separate
   authorization + HF Space deploy verification.

## Tests added
- test_registry_copies_are_in_sync
- test_canonical_engine_ids_present (expects the 7 canonical IDs)

## LIMITS
No HF Space runtime verification in this environment (BLOCKED).

## Consumers / Rollback
Consumers: none changed (test-only commit). Rollback: revert single commit.
