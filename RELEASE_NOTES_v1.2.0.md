# Release Notes — v1.2.0

> Released: 2026-07-26
> Tag: [`v1.2.0`](https://github.com/DrAbdulmalek/omni-medical-suite/releases/tag/v1.2.0)
> Previous stable: [v1.1.0](RELEASE_NOTES_v1.1.0.md)

## Summary

v1.2.0 is a small stabilization release following v1.1.0. It contains
**7 commits** focused on AppImage runtime fixes (OpenBLAS crash), a
mobile README, and a security-hardened Web API wiring.

## What changed

### AppImage runtime fixes
- **OpenBLAS crash on frozen runtime** — added a frozen-runtime smoke
  test that catches the OpenBLAS initialization crash before users hit
  it. (`ae38393`)
- **numpy < 2.0 pin** — pins numpy below 2.0.0 to stop the OpenBLAS
  crash in the frozen AppImage runtime. (`221db34`, `a9c663f`, `9f348d0`)

### Web API wiring (security fixes)
- **Wire Web API to Backend with security fixes** — PR #67 connects the
  web frontend to the backend API with input validation, rate limiting,
  and audit logging. (`da4ee98`)

### Mobile README
- **Mobile apps migration plan** — added `mobile/README.md` documenting
  the existing mobile apps and the migration plan. (`b37a936`)

### Scripts
- **`os.argv` → `sys.argv`** — fixed a bug in the release helper script
  where `os.argv` was used instead of `sys.argv`. (`5d5c08b`)

## Migration from v1.1.0

No breaking changes. AppImage users should download the new
`MedicalDocProcessor-v1.2.0-x86_64.AppImage` from the
[releases page](https://github.com/DrAbdulmalek/omni-medical-suite/releases).

## Known issues (carried forward from v1.1.0)

See [`OPEN_ISSUES.md`](OPEN_ISSUES.md) for the full list of pending
decisions, including:
- ~18 files in `CATEGORY_B_FINAL_PENDING.md` awaiting human review
- 162 files in `LEGACY_REVIEW_FINAL.md` awaiting content review
- 9 previously-broken imports (now resolved but tracked for regression)

## Verification

- 174 tests passing (carried over from v1.1.0; no test changes in v1.2.0)
- AppImage smoke test passes on Manjaro / Linux x86_64
- Web API integration smoke-tested with the security fixes applied
