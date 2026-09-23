# VPS SETUP (V-6 · PLANNED)

القوالب: `automation/vps/*.sh.template` + `automation/shared/*.template` (TEMPLATE ONLY — NOT EXECUTED — TESTED: NO).

## 1) gh CLI
تثبيت رسمي (apt repo من cli.github.com) → `gh auth login` بـPAT **ضيّق**
(contents:write على datasets-repo فقط) → التخزين في keyring/`.env` (0600).

## 2) GPG
استيراد المفتاح **العام** للمالك → `gpg --list-keys` للتأكيد → التشفير في
`encrypt.sh.template` (symmetric AES256 أو `-r OWNER-KEY`).

## 3) cron jobs (`crontab.template`)
```
# TEMPLATE — DO NOT EXECUTE
0 2 * * *   /opt/omni/automation/vps/01-export-dataset.sh >> /var/log/omni-export.log 2>&1
30 2 * * *  /opt/omni/automation/vps/02-encrypt-and-push.sh >> /var/log/omni-push.log 2>&1
0 4 * * 6   /opt/omni/automation/vps/03-pull-and-validate-model.sh >> /var/log/omni-model.log 2>&1
30 4 * * 6  /opt/omni/automation/vps/04-promote-or-rollback.sh >> /var/log/omni-promote.log 2>&1
```

## 4) validate + promote
`automation/shared/validate_model.py.template`: يقيس CER/WER على 50 عينة
(**اصطناعية أو معتمدة من المالك**) مقابل عتبات (مثلًا CER ≤ السابق + 2% —
يحددها المالك وقت V-6) → قرار `PROMOTE/REJECT` في metrics.json →
`04-promote-or-rollback` ينفذ القرار atomically (symlink `models/current`).

## شروط قبل التفعيل
☐ V-2..V-4 مكتملة ☐ المستودعان الخاصان ☐ المفاتيح بيد المالك ☐ دورة تجريبية على بيانات اصطناعية.
