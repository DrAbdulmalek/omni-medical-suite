# RISK REGISTER (PLANNED — living document)

| # | المخاطرة | الشدة | الاحتمال | التخفيف | المرحلة |
|---|---|---|---|---|---|
| R1 | فقدان بيانات VPS (قرص/حذف/إعادة إنشاء) | HIGH | متوسطة | نسخ يومية مشفرة → GitHub private + B2؛ تحقق استعادة شهري | V-4 |
| R2 | اختراق VPS | CRITICAL | منخفضة | SSH keys فقط، ufw، fail2ban، تحديثات تلقائية، خدمات loopback+nginx | V-1 |
| R3 | Oracle يرفض الحساب/يعلقه | MEDIUM | **عالية** | بديل فوري: Codespaces+Colab؛ عدم تخزين المصدر الوحيد على Oracle | V-0 |
| R4 | تسرب PHI عبر الشبكة | CRITICAL | منخفضة | HTTPS إلزامي، تشفير GPG قبل أي مغادرة، لا PHI على خدمات عامة، انظر PRIVACY_COMPLIANCE | V-1+ |
| R5 | تسرب مفتاح GPG/أسرار | CRITICAL | منخفضة | passphrase قوي، المفتاح الخاص خارج VPS، تدوير مفاتيح، GitHub Secrets فقط | V-6 |
| R6 | انقطاع جلسات Colab أثناء التدريب | MEDIUM | عالية | checkpoints دورية + استئناف؛ دفعات بيانات صغيرة | V-6 |
| R7 | نموذج سيئ يُرقَّى للإنتاج | HIGH | متوسطة | validate_model (CER عتبة) + promote/rollback آلي + 50 عينة | V-6 |
| R8 | حدود GitHub (حجم/معدل) | LOW | متوسطة | datasets مضغوطة مشفرة؛ LFS عند الحاجة؛ releases للنماذج | V-6 |
| R9 | تغيّر سياسات الخطط المجانية | MEDIUM | متوسطة | مراجعة Sources قبل كل مرحلة؛ بدائل جاهزة (ALTERNATIVES) | دائمًا |
| R10 | اعتماد الوكيل/المطور الواحد (bus factor) | MEDIUM | عالية | هذه الحزمة نفسها + PROGRESS.md + handoff bundles | — |
| R11 | استهلاك موارد ARM غير متوافق (whl غير متوفر لمعمارية aarch64 لبعض الحزم) | MEDIUM | متوسطة | فحص مسبق للحرجة؛ fallback AMD micro؛ بناء wheels | V-2 |
