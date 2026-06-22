# ADR-005: Repository Portfolio Strategy

## Status
Accepted

## Context
The DrAbdulmalek GitHub account contains 10 repositories with overlapping functionality, unclear status, and no unified documentation. Contributors and users struggled to understand which repository to use and how they relate to each other.

## Decision
Organize all repositories into a four-layer architecture:

1. **Platform Layer**: omni-medical-suite (main hub)
2. **Application Layer**: medical-handwriting-ocr, medical-ocr-trainer, medical-doc-processor
3. **Core Engines Layer**: medical-ocr-postprocessor (installable library)
4. **Support Layers**: Deployment (trainer-hf), Study (omniparse, omniparse-study), Independent (IntelliFile-app), Legacy (OmniFile_Processor)

Each repository receives:
- A descriptive README with: What, Who, Relation, Status, When to Use
- GitHub Topics for discoverability
- Status badge: Active, Legacy, Deployment, Study, Independent
- Clear linking to related repositories

A PORTFOLIO.md is maintained in omni-medical-suite as the central reference.

## Consequences

### Positive
- New contributors know exactly where to start
- No ambiguity about which repo is "the main one"
- Legacy repos are clearly marked, preventing confusion
- Each repo has a defined role in the ecosystem

### Negative
- Requires ongoing maintenance of PORTFOLIO.md
- Legacy repos may accumulate pull requests that should go to the main platform

### Governance
- New repositories must include "Repository Status" section in README
- Repository status changes require updating PORTFOLIO.md
- Deprecated repos should be archived, not deleted
