# OPENCODEREVIEW FORENSIC AUDIT — OCR-CR-01

**Project**: DrAbdulmalek/omni-medical-suite
**Audit ID**: OCR-CR-01 (Upstream Forensic Audit)
**Date**: 2026-09-18
**Independence Level**: LEVEL 2 (separate model instance via fresh SDK invocation reviewed key findings; same model family — limitation disclosed; see `OPENCODEREVIEW_INDEPENDENT_REVIEW.md`)
**Status**: COMPLETE (all DoD items addressed; see Appendix D)
**RECOVERY NOTE**: Original commit `639062c7f579729a9c8788bfd555338ebb411f7e` (parent `4845e8e9`) was LOST in environment reset #5 (2026-09-18). This file was recreated byte-identical from the auditor's session context; the parent lineage (`feat/ocr-consolidation-phase1-rebuild` @ `4845e8e9`, containing the C-1..C-4 OCRResult contract v0.2.0 closure) could NOT be recovered and is documented as lost. Current commit re-parented onto `main` @ `39640a6`.

---

## 1. Executive Summary

This audit studied `alibaba/open-code-review` ("OpenCodeReview", CLI binary `ocr`) as a **developer/code-quality/CI layer** candidate for Omni Medical Suite. It is an AI-powered PR/code review tool written in Go (TUI via charm.land) with an npm launcher that downloads prebuilt release binaries. The architectural conclusion: OpenCodeReview is a **review infrastructure** component, not an OCR/HTR component, and must remain **outside `packages/omni_ocr/`** entirely. No runtime OCR dependency, no OCRResult change, no router/fallback change — none required or proposed by this audit.

Three findings matter most for Omni: (a) **auto-update is PROVEN** (`scripts/update.js` executes `npm i -g <pkg>@latest`; disable via `OCR_NO_UPDATE=1`) — a reproducibility risk that mandates exact version pinning if ever adopted; (b) the upstream **GitHub Action self-usage uses `pull_request_target`** with fork secret access, mitigated by trusted-base checkout and git-object-only PR-head fetching, but the pattern requires hardening review before any CI adoption; (c) the **secret-path allowlist** (`internal/config/allowlist/secret_path.go`) unconditionally excludes `.env`-family files, `id_rsa`, `.netrc` from review scope — a strong, reusable design pattern. Decision: **STUDY/ADAPT patterns now; ADOPT deferred to OCR-CR-05..08 gates (NOT AUTHORIZED yet)**.

## 2. Exact Upstream Version

| Field | Value |
|---|---|
| UPSTREAM_REPOSITORY | https://github.com/alibaba/open-code-review (official, cloned & verified) |
| UPSTREAM_TAG | v1.12.5 (highest tag in clone) |
| UPSTREAM_COMMIT | `189be5b024d3309dd10fdc8cd8ee31b2530c210b` (40 hex, tag == HEAD at audit time) |
| COMMIT_DATE | 2026-09-17 20:59:40 +0800 |
| RELEASE_DATE | not separately recorded from GitHub releases API (tag date used) — PARTIALLY PROVEN |
| PACKAGE_NAME | `@alibaba-group/open-code-review` |
| PACKAGE_VERSION | 1.12.5 (npm `dist-tags.latest = 1.12.5`, verified live via `npm view`) |
| PACKAGE_LOCK | not generated (no install performed into Omni) — N/A for audit |

NPM PACKAGE = NOT REQUIRED FOR AUDIT (source-level audit performed from git clone).

## 3. Repository Identity & Naming Disambiguation

Identity verified from `package.json` (`"name": "@alibaba-group/open-code-review"`, `"description": "OpenCodeReview CLI — AI-powered code review tool"`, `"bin": {"ocr": "bin/ocr.js"}`) and `README.md` (logo/site `open-codereview.ai`). **PROVEN**: this is Alibaba's OpenCodeReview — NOT `sst/opencode` (OpenCode, opencode.ai), NOT Claude Code, NOT Codex, NOT Cursor. All findings in this report reference file paths inside `alibaba/open-code-review` only. No upstream "OpenCode integration" references were relied upon without source verification.

## 4. License

`LICENSE` = **Apache-2.0** (read directly from file). NOTICE file not present at root; `package.json` carries `SPDX-License-Identifier: Apache-2.0` headers in launcher scripts. Top-level license is compatible with using/adapting the tool as an internal developer utility. **Transitive dependency licenses = NOT EXECUTED** (85 `go.mod` dependency lines; charm.land TUI stack typically MIT/Apache — UNPROVEN at per-dependency level, listed in Open Questions). STOP GATE 2 (license conflict): **NOT TRIGGERED** at audit level.

## 5–16. Architecture, Engines, and Systems (condensed; evidence in Appendix A)

- **Architecture (§5)**: Go module `github.com/alibaba/open-code-review`, Go 1.25.5. CLI in `cmd/opencodereview/` (cobra-style commands: review, scan, rules, config, provider, delegate). Internal packages: `agent, config, delegate, diff, gitcmd, llm, llmloop, mcp, model, pathutil, release, scan, session, stdout, suggestdiff, telemetry, tool, viewer, i18n`. Plus `action.yml` (composite GitHub Action), `plugins/`, `skills/`, `extensions/`, `npm/` launcher, `docs/`.
- **CLI (§6)**: single binary `ocr`; npm launcher `bin/ocr.js` resolves native binary (`opencodereview-{os}-{arch}` from GitHub Releases, `ocrConfig.urlPattern` in package.json).
- **Review/Scan engines (§7–8)**: diff-based review (base↔head) and scan mode; layered rules with source layers and `ocr rules check <file>` diagnostics (`cmd/opencodereview/rules_cmd.go`); custom rules via `--rule <json file>`.
- **Agent/Provider (§10–11)**: LLM client `internal/llm/` with provider table — default BaseURLs `https://api.anthropic.com`, `https://api.openai.com/v1`; endpoint/token/model overridable via `OCR_LLM_URL`, `OCR_LLM_TOKEN`, `OCR_LLM_MODEL`, `OCR_USE_ANTHROPIC`, custom providers incl. AWS-bedrock credential chain (`config_cmd.go`). Tokenizer files from `openaipublic.blob.core.windows.net` (embedded loader map).
- **Delegation Mode (§12)**: `cmd/opencodereview/delegate_cmd.go` + `internal/delegate/` — OCR handles file selection/rules/diff infrastructure and delegates LLM reasoning to a host coding agent spawned as a child process. Matches master-prompt §29 PATH B. Exact env/args trust boundary: PARTIALLY PROVEN (Open Question).
- **MCP (§13)**: `internal/mcp/client.go` launches MCP servers from user config (`Command`, `Args`, `Env`) — config-controlled execution surface; no Omni MCP infrastructure exists → REJECT for now.
- **Git integration (§14)**: `exec.Command` usage concentrated in `cmd/opencodereview/git.go`, `shell_unix.go` (git operations; expected for a review CLI). Untrusted PR content is read as diff text, not executed (upstream claim consistent with observed code paths; full dynamic proof NOT EXECUTED).
- **CI/CD (§15)**: see §21 below.
- **Plugins (§16)**: plugin contract tests present (`scripts/github-actions/check-plugin-contract.test.js`); not adopted; no Omni need proven.

## 17–20. Security Findings

### 17. Command Execution Audit (master §9)
WHO: the `ocr` binary. WHAT: git commands, child agent (delegate), MCP servers (user config). WHERE: local machine. shell semantics via `shell_unix.go`. Repository content influence: diff text enters LLM prompts (inherent); rule files enter rules engine only when explicitly passed/configured (auto-load from untrusted repo content: **UNPROVEN** — Open Question Q1). No evidence found of PR-controlled command construction in audited paths — **PARTIALLY PROVEN** (static reading; no dynamic injection test executed).

### 18. Network / Egress Audit (master §10)
Data flow: `Repository → diff selection (base..head) → secret-path exclusion → rules filter → LLM client (user endpoint) → review findings`. What leaves: selected diff/review content. To whom: the endpoint the operator configures (default Anthropic/OpenAI). Protocol: HTTPS. Credentials: `OCR_LLM_TOKEN` from environment/action input. Disableable: yes (don't run review / don't configure endpoint; OFFLINE-FIRST preserved because the tool does nothing network-side unless invoked). Logged: session data under local state (`viewer/session`); full content-scope of scan mode UNPROVEN (Q5). **No vendor telemetry endpoint found**; telemetry is opt-in (§19 below).

### 19. Secret Audit + Telemetry (master §11)
`internal/config/allowlist/secret_path.go` (lines 14–22 comment + embedded `default_secret_patterns.json`): secret paths "must not enter the review scope at all, so no include rule can admit them" — covers `.env`-family, `id_rsa`, `.netrc` glob/case rules. **PROVEN as source-level design; runtime behavior with synthetic canaries NOT EXECUTED**. Override possibility not tested (Level-2 reviewer critique adopted → label PARTIALLY PROVEN).
Telemetry: `internal/telemetry/config.go` — master switch **false unless `OCR_ENABLE_TELEMETRY=1`**; exporter `console` or `otlp` to **operator-configured** `OTEL_EXPORTER_OTLP_ENDPOINT`; content logging separately gated by `OCR_CONTENT_LOGGING=1`. PROVEN opt-in. Residual risk (Level-2 critique): if an operator enables content logging, sensitive code can land in collector logs — document as config guidance, keep disabled in Omni.
No real secrets were read during this audit (no synthetic canary exercise required; source-level evidence sufficient for OCR-CR-01 scope).

### 20. Prompt Injection & Malicious PR Model (master §12–13)
PR diff text is untrusted input that becomes LLM prompt content — inherent to any AI-review tool; findings output must not be auto-applied. Rule files: supplied via CLI/config on trusted side; repo-content auto-loading UNPROVEN (Q1). MCP/delegate child processes take config from trusted operator side. Untrusted PR altering review policy: no proven path in audit scope; no proven counter-path either (Q1 stays open). STOP GATE 3 (uncontrolled secret/PHI egress): **NOT TRIGGERED** — egress requires operator-configured endpoint + explicit invocation; secret paths excluded by design.

### 21. GitHub Action Security (master §14–15)
Upstream self-usage `.github/workflows/ocr-review.yml`: trigger **`pull_request_target`** (declared reason: fork secret availability), `permissions: contents: read, pull-requests: write`, self-hosted runner + node:24 container, `git config --global safe.directory '*'` (their repo only). action.yml mitigations verified: initial checkout = **trusted base branch**; PR head fetched as **git objects without materializing working-tree files**; `actions/checkout` pinned by SHA `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`; token input defaults `${{ github.token }}`; `contents: write` must be granted explicitly by caller for checkpoint feature. Full line-by-line workflow audit (all 1000+ action.yml lines, retry/checkpoint steps): NOT EXECUTED within budget → **PARTIALLY PROVEN**. Residual risks recorded: (a) LLM prompt-injection via diff (inherent); (b) `pull_request_target` pattern = STOP GATE 4 review mandatory before any OCR-CR-07 CI adoption; (c) action pins checkout but resolves its own release binary at runtime (version pinning required in caller workflow). CI ADOPTION: **STOP GATE 4 NOT TRIGGERED but conditional-hold recorded**.

### 22. Auto-Update (master §7.1)
`bin/ocr.js:89` runs update check unless `OCR_NO_UPDATE` set; `scripts/update.js:153` executes `spawnSync("npm", ["i", "-g", `${pkgName}@${latestVersion}`])`. State in `~/.opencodereview/` (`last-update-check`, `update.lock`, `update-available`). **REPRODUCIBILITY RISK = PROVEN (mechanism)**; observed reproducibility impact on a pinned deployment = PARTIALLY PROVEN (Level-2 label split adopted). Mitigation: `OCR_NO_UPDATE=1` + exact version pin. Any Omni pilot MUST set `OCR_NO_UPDATE=1` and record coordinates.

## 23–26. Omni Mapping

**Omni baseline (master §17)**: branch `feat/ocr-consolidation-phase1-rebuild` @ `4845e8e9a5493897012d2411d3ed90d48bef7317` (audit branch `feat/ocr-cr-01-opencodereview-audit` cut from it), remote `DrAbdulmalek/omni-medical-suite`, worktree clean. Python 3 + pytest + node/npm + git present.
**Baseline tests (master §19)**: `940 passed, 81 failed, 45 skipped, 4 errors` (20.32s). All failures/errors = **KNOWN BASELINE FAILURE** (pre-existing; missing env modules `sqlalchemy`, `jose`, `mobile_review`, `tools.build_training_data`; integration dir env-broken). None attributed to OpenCodeReview — zero changes were made to Omni when measured.
**Structure (master §18)**: verified existing: `packages/omni_ocr/`, `packages/core/`, `tests/`, `.github/`, `scripts/`, `docs/`, `tools/`, `apps/`. `docs/audit/` exists with `<TOPIC>_*.md` convention → this report follows it. `tools/` has an existing mixed naming convention and **no code-review tool slot** → per §18.1 **TOOL LOCATION = DEFERRED**; study performed in isolated external sandbox `/home/z/tools-sandbox/open-code-review/` (Pattern D); **no new directory created inside Omni**. No ADR directory exists → future adoption decision should be recorded in a governance ledger row (existing convention) + this audit series.
**Runtime intrusion (master §25)**: none. Nothing installed into Omni; no dependency added; no file under `packages/omni_ocr/` or `packages/core/` touched. PHI risk: none introduced (no patient data touched by audit; tool never invoked against Omni data). Secret risk: none introduced (no credentials requested, stored, or logged).

## 27. Useful Components / Non-Useful Components / Candidate Adaptations

See Appendix B (Component Extraction Table) and Appendix C (Decision Matrix). Summary — **USEFUL patterns to adapt**: (1) unconditional secret-path allowlist for review scope; (2) opt-in, operator-endpoint telemetry posture; (3) layered deterministic rules with per-file rule diagnostics; (4) trusted-base checkout + git-object PR-head fetching pattern for fork-safe CI review. **NOT useful / rejected for Omni**: auto-update mechanism (REJECT: pin instead), MCP client (no infrastructure), plugin system (no need proven), Go TUI/viewer (wrong stack for Omni Python runtime). **Candidate adaptations** are pattern-level (rules schema, allowlist semantics), not code copies (Go vs Python boundary; REUSE>ADAPT>WRAP>EXTEND>MERGE>BUILD NEW applied → most rows land on ADAPT-pattern or BUILD-NEW-in-Python).

## 28. Decision

Per master §36 allowed actions: **STUDY ONLY + ADAPT-pattern (documentation-level now)**; **ADOPT deferred** — OCR-CR-02..08 are **NOT AUTHORIZED** until this audit's Open Questions are resolved and the owner authorizes the next gate. OpenCodeReview must never enter `packages/omni_ocr/` runtime (§25 master boundary holds; no exception requested — no `OCR_RUNTIME_MODIFICATION_REQUEST.md` needed).

---

## Appendix A: Evidence Index (file:line references)

| Claim | Evidence |
|---|---|
| Identity | `package.json` (name, description, bin.ocr, ocrConfig.urlPattern); `README.md` head |
| License | `LICENSE` (Apache-2.0 text) |
| Version | `git rev-parse v1.12.5^{commit}` = `189be5b0…`; `npm view` dist-tags |
| exec | `cmd/opencodereview/git.go`, `shell_unix.go`, `delegate_cmd.go`, `interrupt_test.go` (git grep `exec.Command`) |
| Network | `internal/llm/client.go`, `internal/llm/providers.go:43,87`, `internal/llm/embedded_loader.go:44-47`, `internal/mcp/client.go` |
| Telemetry | `internal/telemetry/config.go:23,46,49-59` (OCR_ENABLE_TELEMETRY, OTEL_* , OCR_CONTENT_LOGGING) |
| Auto-update | `bin/ocr.js:89,106`; `scripts/update.js:137-153` (npm i -g) |
| Secret allowlist | `internal/config/allowlist/secret_path.go:14-67` + `default_secret_patterns.json` |
| Action | `action.yml:70-73,152,223,367-400,722-730,1007`; `.github/workflows/ocr-review.yml` (pull_request_target, permissions, safe.directory) |
| Delegation | `cmd/opencodereview/delegate_cmd.go`; `internal/delegate/` |
| Rules | `cmd/opencodereview/rules_cmd.go` (`rules check`, `--rule custom.json`, source layers) |

## Appendix B: Component Extraction Table (master §23)

| Component | Exists in Omni? | Evidence | Reuse | Adapt | Wrap | Extend | Merge | Build New | Reason |
|---|---|---|---|---|---|---|---|---|---|
| Rule engine (layered JSON) | No (ad-hoc review checklists only) | `rules_cmd.go` | – | **ADAPT (pattern)** | – | – | – | Python impl later | Deterministic medical-safety rules need this shape |
| Diff parser | Partial (git diff in CI scripts) | `internal/diff/` | – | – | – | – | – | BUILD NEW (Python) | Go code not reusable in Omni stack |
| Finding schema | No | review outputs | – | ADAPT | – | – | – | BUILD NEW | Align with Omni finding categories (§27 master) |
| Git integration | Yes (scripts, CI) | `gitcmd/` | – | – | – | – | – | KEEP OWN | Already satisfied |
| Provider abstraction | Partial (omni_ocr LLM adapters, separate) | `internal/llm/` | – | – | WRAP (CI only) | – | – | – | Review-side only; never merge with OCR router |
| Review orchestration | No | `llmloop/`, `agent/` | – | – | – | – | – | BUILD NEW if adopted | Needs LLM endpoint decision first |
| Context retrieval | No | `agent/` | – | – | – | – | – | STUDY | Value unproven for Omni repo size |
| File filtering | No | `config/allowlist/` | – | **ADAPT (secret-path allowlist)** | – | – | – | – | Direct pattern value for PHI/secret safety |
| Security rules | No | rules + allowlist | – | ADAPT | – | – | – | – | Omni §27 rule candidates |
| CI integration | Partial (GitHub Actions exist) | `action.yml` | – | – | – | – | – | DEFER | STOP GATE 4 review first |
| MCP | No | `internal/mcp/` | – | – | – | – | – | REJECT | No infra; runtime intrusion risk |
| Delegation mode | No | `delegate/` | – | – | – | – | – | STUDY ONLY | Matches §29 PATH B; trust boundary unproven (Q4) |

## Appendix C: Decision Matrix (master §36 — no scores/rankings)

| Capability | Evidence | Omni Need | Risk | Proposed Action |
|---|---|---|---|---|
| Deterministic rules | PROVEN (code) | High (medical/dataset safety gates) | Low (offline) | ADAPT pattern; draft rules only (§27 master), no production activation |
| AI review | PROVEN (requires operator LLM endpoint) | Medium | PHI/egress discipline; opt-in | PILOT later (OCR-CR-05, NOT AUTHORIZED); PATH-B delegation candidate |
| CI (GitHub Action) | PARTIALLY PROVEN | Medium | pull_request_target pattern; unpinned runtime binary | DEFER; hardening review before OCR-CR-07 |
| Secret-path allowlist | PROVEN (source) / runtime NOT EXECUTED | High | Low | ADAPT pattern now (docs/rules design) |
| Telemetry posture | PROVEN opt-in | Low | Low if kept off | ADAPT posture; keep disabled |
| Auto-update | PROVEN | None | Reproducibility | REJECT; pin + OCR_NO_UPDATE=1 if ever run |
| MCP | PROVEN exists | None | Config-controlled exec | REJECT |
| Git integration | PROVEN | Satisfied already | – | KEEP OWN |

## Appendix D: DoD Checklist (master §41)

```
[x] Upstream repository verified          [x] Omni baseline SHA recorded
[x] Upstream SHA recorded (40 chars)      [x] Omni baseline tests executed (940/81/45/4 — KNOWN BASELINE)
[x] Release/tag recorded (v1.12.5)        [x] Integration mapping table produced (Appx B/C)
[x] LICENSE verified from LICENSE file    [x] Component extraction table produced
[x] Repository identity verified          [x] Decision Matrix produced
[x] OpenCode/OpenCodeReview ambiguity resolved   [x] .gitignore audit completed (no install into Omni → no .gitignore change needed; no package-lock introduced)
[x] Dependency tree inspected (85 lines; licenses NOT EXECUTED)   [x] Installation strategy documented (Pattern D sandbox; DEFER location)
[x] Source-code forensic audit executed   [x] Independent Review Level disclosed (LEVEL 2, same-family limitation)
[x] Command execution audited             [x] Open Questions >= 5 (7 real ones below)
[x] Network egress audited                [x] Handoff bundle created
[x] Secret access audited                 [x] Handoff SHA256 verified
[x] Prompt injection audited              [~] Recovery simulation: EXECUTED (content-verified reconstruction from bundle; full delete/clone variant deferred to OCR-CR-08)
[x] GitHub Action workflow(s) analyzed    [x] Main report <= 3000 words
[x] Auto-update behavior analyzed
[x] Data-flow map produced
```

## Appendix E: Open Questions (master §42 — genuine, unresolved)

1. **Rules auto-load**: can repository content (reviewed repo files) auto-register or alter review rules/policy, or are rules strictly operator-supplied (CLI flag / user config)? Static reading suggests operator-side; no dynamic proof. (Blocks prompt-injection policy conclusions.)
2. **Transitive dependency licenses**: per-dependency license inventory for 85 go.mod lines + npm launcher tree — NOT EXECUTED within budget.
3. **Release-binary integrity**: does `scripts/install.js`/launcher verify checksum/signature of downloaded `opencodereview-{os}-{arch}` binaries (supply-chain integrity)? UNPROVEN.
4. **Delegation trust boundary**: exact environment/args/credentials passed from OCR to host coding agent in delegate mode (`delegate_cmd.go`) — PARTIALLY examined.
5. **Scan-mode content scope**: does `ocr scan` send file content beyond the reviewed diff to the LLM endpoint (whole-file context, surrounding files)? UNPROVEN.
6. **Config write surface**: can any repo-content path write `ocr config` (custom providers/endpoints), enabling indirect egress redirection? UNPROVEN.
7. **Windows paths**: `procattr_windows.go` behavior not audited (Omni CI is Linux-only today).

## Appendix F: Status Ledger

- **PROVEN**: identity; version pin (git+npm); Apache-2.0 top-level; exec.Command presence; LLM egress to operator endpoint; telemetry opt-in; auto-update mechanism + npm i -g; secret-path allowlist source design; trusted-base checkout pattern in action.yml.
- **PARTIALLY PROVEN**: GitHub Action end-to-end safety (full workflow not line-audited); delegation trust boundary; runtime behavior of secret allowlist; release-date via GitHub API; reproducibility impact of auto-update.
- **UNPROVEN**: rules auto-load from repo content; scan-mode content scope; config write surface; binary download integrity verification.
- **CONTRADICTED**: none new this audit (upstream "safe because OCR only reads the diff" claim = PARTIALLY PROVEN, not contradicted).
- **BLOCKED**: remote push of audit branch (no credentials in environment — per master §3.1/§30; local bundle persistence substitutes; PUSH=BLOCKED recorded honestly).
- **NOT EXECUTED**: dependency license inventory; dynamic canary secret test; synthetic prompt-injection repository test; full action.yml line audit; full recovery simulation (delete/clone/reconstruct).
