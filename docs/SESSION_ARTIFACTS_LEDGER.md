# SESSION ARTIFACTS LEDGER — سجل أصول الجلسات (APPEND-ONLY)

> قاعدة: صف لكل أصل إثبات مُلتزم. يُمنع الحذف أو التعديل — إضافة فقط.
> التحقق: `python scripts/verify_session_artifacts.py` (يجب PASS قبل إنهاء أي جلسة).
> السياسة: `docs/SESSION_ARTIFACTS_POLICY.md`.

| # | Session | Artifact path | sha256 (full) | Containing commit (full SHA) | Note |
|---|---------|---------------|---------------|------------------------------|------|
| 1 | SESSION-21 | docs/audit/AHW-02_IMPLEMENTATION_REPORT.md | c66f931e15f0db9465ca8464848ab53f889457e167d5e9145f03240ff04d5298 | 0198e47c594354493eb705f2ad862160e9b3b8f1 | AHW-02 implementation report + reconciliation addendum §K; sha256 prefix c66f931e… matches SESSION-21 worklog |
| 2 | SESSION-21 | docs/portfolio/AHW-02_B4_DECISION.md | c6da140caa816eeb3de03676660c924331380e618dfe1a738e9427b25e8f4bee | 0198e47c594354493eb705f2ad862160e9b3b8f1 | B4 hf-space divergence decision doc; sha256 prefix c6da140c… matches SESSION-21 worklog |
| 3 | SESSION-22 | docs/audit/AHW-02_IMPLEMENTATION_REPORT.md | d2d6125d0012f61d9a008cc18863b81777f5c2b95a488a7c38f7360839521b26 | 4486cf1b628f4d159460aecc001a873520b76813 | SUPERSEDES row 1 — adds §L evidence-persistence addendum (append-only correction) |
| 4 | SESSION-22 | docs/audit/AHW-02_GATE_CLOSURE_REPORT.md | 80b0bc032510f2b0288aa48066d1e61f7ac45ee55574fc422276f5cff0626907 | 4486cf1b628f4d159460aecc001a873520b76813 | Mandatory final closure record (directive item 8): GATE=PARTIAL, all fields |
| 5 | SESSION-22 | docs/SESSION_ARTIFACTS_POLICY.md | a7507b8db0d4837a8cd82e442211cd664f987939bcb4941cfa920ad1712afbc7 | 7924c95603f7953912b6e0230f5d6208c8e9d8b0 | Permanent persistence policy (owner directive) |
| 6 | SESSION-22 | scripts/ahw02_recon_base.json | 827e471abfbaaafa539db72d29563e7cf525b3ba1fe4ca06de5a65407be3f4cb | 59a9813d1e69d8713f1308f4adf4da8791890662 | Full-suite json-report, clean base @ 39640a6d (81F/868P/51S/9E) |
| 7 | SESSION-22 | scripts/ahw02_recon_branch.json | 780589bab722bb733e36ac8c67a43b1f19d17198baea1b5f97c1affbda049af2 | 59a9813d1e69d8713f1308f4adf4da8791890662 | Full-suite json-report, AHW-02 branch (81F/931P/51S/9E) |
| 8 | SESSION-22 | scripts/ahw02_recon_compare.py | f7887fa358ee8da3669329d75ace78f9808ab4e9e15eda1f14fc7e994c9a0f6b | 59a9813d1e69d8713f1308f4adf4da8791890662 | Identifier-level comparison machine |
| 9 | SESSION-22 | scripts/ahw02_recon_compare_result.json | a7d0f4d48cf9e9510d681ba145d0de6fdc5381df2211b5f239882e6eaa06e1e2 | 59a9813d1e69d8713f1308f4adf4da8791890662 | FAILURE SET IDENTITY = TRUE → REGRESSION = ZERO (sha256 7f24cfbf…/744d313a…/d94dd923… reproduce SESSION-21 worklog) |
| 10 | SESSION-22 | scripts/ahw02a_torchload_scan.py | 5ce95195198fc8b0895d91a7a04e56f7763ad9e7f267870139c0921011162391 | 59a9813d1e69d8713f1308f4adf4da8791890662 | Bounded AST torch.load scanner (16 scope dirs) |
| 11 | SESSION-22 | scripts/ahw02a_torchload_scan.json | 2e665efbe346ff280ef286cf2497c598e9d08e736e2710990e0f041c1b3c8623 | 59a9813d1e69d8713f1308f4adf4da8791890662 | 753 files, 6 sites ALL SAFE, 0 unsafe (§K.5 lines reproduced) |
| 12 | SESSION-22 | scripts/ahw02_router_chain_smoke.py | bdd6bf43c9a69a2b671349e9db62e645bfbacbfc7aaa9c2340dcc67579e795b5 | 59a9813d1e69d8713f1308f4adf4da8791890662 | Live router→executor→engine→OCRResult chain smoke (real router names) |
| 13 | SESSION-22 | scripts/ahw02_router_chain_smoke_output.json | a7296a3688da7cf3853f9080f620d0efa4e26d4de8a247a177be9c0925c8e90d | 59a9813d1e69d8713f1308f4adf4da8791890662 | Both scenarios ALL ASSERTIONS PASSED (declared fallback + explicit failure) |
| 14 | SESSION-22 | scripts/ahw02_targeted_tests_output.txt | 579b1c37f5a97746b35a17d08253811d5c741ed070980a0037880e0c71eb1302 | 59a9813d1e69d8713f1308f4adf4da8791890662 | 74 passed (63 AHW-02 + 11 legacy router baseline parity) |

Infra note: the ledger and `scripts/verify_session_artifacts.py` are protocol
infrastructure — their integrity rests on the git commit graph; the final
commit SHA of each session's ledger-closure is recorded in `worklog.md` and
the owner-facing closure message (policy §3 self-reference rule).
