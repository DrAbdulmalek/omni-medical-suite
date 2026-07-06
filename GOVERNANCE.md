# Governance Policy — git-sync-system

## Overview
This document defines the governance rules for the git-sync-system tool that manages 28+ GitHub repos and 11 HF Spaces.

## Sync Policies

### Default Policy: Read-Only
- All repos default to READ-ONLY mode
- Sync operations (push, delete branches) require explicit opt-in
- Pull/fetch operations are always allowed

### Write Modes
| Mode | Description | Requires |
|------|-------------|----------|
| read-only | Pull only, no pushes | Default |
| safe-push | Push to non-protected branches only | --write flag |
| full-write | Push to any branch including main | --force-write + confirmation |

## Allowlist / Denylist

### Allowlist (repos that CAN receive pushes)
- omni-medical-suite
- scanner-fixer
- medical-handwriting-ocr
- medical-ocr-training-hub
- medical-ocr-benchmarks
- medical-ocr-trainer
- medical-ocr-ground-truth
- profile-readme (DrAbdulmalek/DrAbdulmalek)
- reset-net

### Denylist (repos that MUST NEVER receive auto-pushes)
- ocr-groundtruth (archived, merged into medical-ocr-ground-truth)
- ai-fuel-engine (archived)
- bilingual-extractor (archived)
- medical-doc-processor (archived)
- medical-ocr-postprocessor (archived)
- omniparse-study (archived)
- omniparse (archived)
- OmniFile_Processor (archived)
- ponytail (archived)
- telegram-forwarder (archived)
- tg-forwarder (archived)
- IntelliFile-app (archived)

### Sensitive Repos (require --force-write + explicit confirmation)
- omni-medical-suite (core platform)
- medical-ocr-ground-truth (contains training data)
- medical-ocr-benchmarks (benchmark authority)
- Any repo with 'private' visibility

## Branch Protection

### read_only_main (direct push to main is blocked)
These repos require PR-based workflow for main branch changes:
- omni-medical-suite
- medical-ocr-ground-truth
- medical-ocr-benchmarks

### Force Push Policy
Force push is **never allowed** on protected branches. The system checks branch protection rules before pushing:
1. Query GitHub API for branch protection status
2. If branch is protected: require PR workflow instead of direct push
3. Warn user and require explicit confirmation

### Dry-Run Requirement
The following repos require a dry-run pass before any actual sync:
- omni-medical-suite
- medical-ocr-ground-truth
- medical-ocr-benchmarks

## Audit Log

All sync operations are logged to `logs/audit.log`:
- Timestamp, operation type, repo, branch, result
- Push attempts (success/failure)
- Policy violations (denied writes to denylist repos)
- Manual overrides
- Governance check results (PASSED/DENIED/DRY_RUN_REQUIRED)

## Configuration

Policies are configured in `config/governance.yaml` (source of truth).