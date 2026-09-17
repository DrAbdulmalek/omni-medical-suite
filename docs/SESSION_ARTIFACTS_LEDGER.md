# SESSION ARTIFACTS LEDGER — سجل أصول الجلسات (APPEND-ONLY)

> قاعدة: صف لكل أصل إثبات مُلتزم. يُمنع الحذف أو التعديل — إضافة فقط.
> التحقق: `python scripts/verify_session_artifacts.py` (يجب PASS قبل إنهاء أي جلسة).
> السياسة: `docs/SESSION_ARTIFACTS_POLICY.md`.

| # | Session | Artifact path | sha256 (full) | Containing commit (full SHA) | Note |
|---|---------|---------------|---------------|------------------------------|------|
| 1 | SESSION-21 | docs/audit/AHW-02_IMPLEMENTATION_REPORT.md | c66f931e15f0db9465ca8464848ab53f889457e167d5e9145f03240ff04d5298 | 0198e47c594354493eb705f2ad862160e9b3b8f1 | AHW-02 implementation report + reconciliation addendum §K; sha256 prefix c66f931e… matches SESSION-21 worklog |
| 2 | SESSION-21 | docs/portfolio/AHW-02_B4_DECISION.md | c6da140caa816eeb3de03676660c924331380e618dfe1a738e9427b25e8f4bee | 0198e47c594354493eb705f2ad862160e9b3b8f1 | B4 hf-space divergence decision doc; sha256 prefix c6da140c… matches SESSION-21 worklog |
