# 00 — Prerequisites (V-0 · PLANNED)

قبل أي خطوة جهّز:

1. **حساب Oracle Cloud** — انظر [01](01-oracle-account-setup.md) (بطاقة دفع للتحقق؛ الرفض شائع — الخطة البديلة جاهزة).
2. **بريد إلكتروني مستقر** تملكه (لا مؤسسي مؤقت).
3. **رقم هاتف** يستقبل SMS/مكالمات تحقق.
4. **مفتاح SSH خاص بك**: توليده على جهازك (لا على الخادم):
   ```bash
   # TEMPLATE — DO NOT EXECUTE الآن
   ssh-keygen -t ed25519 -C "owner@omni-vps"
   ```
   احفظ المفتاح الخاص **خارج** أي مستودع/سحابة.
5. **نطاق (اختياري)** ~$10/سنة، أو العمل بـIP (شهادة Let's Encrypt على IP لها قيود — الأنظف نطاق).
6. **مفاتيح GPG** (لـV-4/V-6): keypair passphrase-protected؛ العام يُرفع لـGitHub Secrets؛ **الخاص لا يلمس VPS ولا Git**.
7. **جهاز بديل/متصفح** لجلسة التسجيل (بعض المتصفحات/الشركات تُفشل تحقق Oracle).
8. **~2-4 ساعات عمل** موزعة على V-0.

## تحقق جاهزية (Checklist قبل 01)
☐ بريد ☐ هاتف ☐ بطاقة تحقق ☐ مفتاح SSH مولَّد ومحفوظ ☐ قرار نطاق/IP ☐ GPG keypair (يمكن تأجيله لـV-4)

**Status: PLANNED — لم تُنفَّذ أي خطوة. Sources: docs.oracle.com/en-us/iaas/Content/GSG (UNVERIFIED)**
