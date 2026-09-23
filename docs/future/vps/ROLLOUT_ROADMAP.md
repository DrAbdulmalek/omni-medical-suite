# ROLLOUT ROADMAP — V-0..V-7 (PLANNED)

| المرحلة | المدة | المخرج | شرط الانتقال (Exit Gate) |
|---|---|---|---|
| **V-0** | أسبوع | تسجيل Oracle (أو بديل مُفعَّل) | نجاح التسجيل + VM واحد يعمل |
| **V-1** | أسبوع | SSH + Nginx + SSL + hardening | [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) مكتمل وموثق |
| **V-2** | أسبوع | نشر correction/segment services 24/7 | `/api/status` يستجيب خلف HTTPS يومين بلا انقطاع |
| **V-3** | أسبوع | Migration بيانات التصحيح | SHA256 مطابق + عدّ صفوف مطابق + عينة بصرية |
| **V-4** | أسبوع | Backup + Monitoring | استعادة اختبارية ناجحة + إشعار UptimeRobot يصل |
| **V-5** | أسبوع | Docker اختياري (Stirling-PDF/Xberg كما بالمشروع) | حاويات تقلع وتخدم |
| **V-6** | أسبوع | Colab integration | تدريب آلي واحد ناجح + promote/rollback مُختبر |
| **V-7** | أسبوع | Full production | استقرار أسبوعين + runbook مُجرَّب |

## مبادئ

1. **لا مرحلة تتخطى بوابتها** — الترتيب إلزامي (أمن قبل نشر، نشر قبل بيانات).
2. كل مرحلة تبدأ بمراجعة وثيقتها هنا وتنتهي بتقرير حالة (Status: DONE/FAILED + أدلة).
3. الفشل في V-0 (رفض Oracle) → تفعيل [ALTERNATIVES.md](ALTERNATIVES.md) دون كسر التسلسل.
4. **البيانات الحقيقية لا تدخل قبل V-3 gates + استشارة PRIVACY_COMPLIANCE.**
5. كل قالب يُنفَّذ في مرحلته يُختبر على Codespaces أولًا (بيئة disposable).
