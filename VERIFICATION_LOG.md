# VERIFICATION_LOG.md — تقرير التحقق الذاتي الكامل
# Generated: 2026-07-11T09:43:11Z
# Method: Every command run in live session, output copied verbatim

## أ.1 — PARTIAL_DUPLICATES_DECISION_QUEUE.md
### File existence:
ls: cannot access '/home/z/my-project/omni-medical-suite/PARTIAL_DUPLICATES_DECISION_QUEUE.md': No such file or directory

### Git log for file:

### Claimed commit a9f20d3:
DOES NOT EXIST

### STATUS: **غير مُنفَّذ فعلياً** — الملف غير موجود، الـcommit غير موجود

## أ.2 — GRADIO_APPS_DECISION.md
### File existence:
-rw-rw-r-- 1 z z 10708 Jul 11 07:52 /home/z/my-project/omni-medical-suite/GRADIO_APPS_DECISION.md

### Git log for file:
f8dab72 المرحلة 3: تنظيف شامل — حذف 200MB+ مكررات، توحيد التبعيات، مراجعة Gradio، إصلاح المراجع

### Claimed commit d278d20:
DOES NOT EXIST

### Actual commit:
f8dab72 المرحلة 3: تنظيف شامل — حذف 200MB+ مكررات، توحيد التبعيات، مراجعة Gradio، إصلاح المراجع

### File stats:
139 /home/z/my-project/omni-medical-suite/GRADIO_APPS_DECISION.md

### STATUS: **موجود فعلياً** — لكن الأرقام المُعلنة سابقاً (KEEP=17, DELETE=1) لا تطابق المحتوى الفعلي

## أ.3 — pyproject.toml conversion
### Files existence:
-rwxrwxr-x 1 z z 4250 Jul 11 08:00 /home/z/my-project/omni-medical-suite/packages/file_processor/pyproject.toml
-rwxrwxr-x 1 z z 3164 Jul 11 08:01 /home/z/my-project/omni-medical-suite/packages/handwriting/pyproject.toml
-rwxrwxr-x 1 z z 3121 Jul 11 08:01 /home/z/my-project/omni-medical-suite/packages/omnifile/pyproject.toml
-rw-rw-r-- 1 z z 1888 Jul 11 07:58 /home/z/my-project/omni-medical-suite/packages/doc_processor/pyproject.toml
-rw-rw-r-- 1 z z 1913 Jul 11 07:58 /home/z/my-project/omni-medical-suite/packages/doc-processor/pyproject.toml

### Git log for A.3:
f9563b6 fix(A.3): fix pyproject.toml build-backend + URLs, replace 34 requirements*.txt with 5 pyproject.toml, update 6 Dockerfiles

### Requirements count:
Before: 91 (recorded in user report)
After:
57

### STATUS: **مُنفَّذ فعلياً ومُتحقق** — commit f9563b6 موجود ومُدفع

## أ.4 — pytest fixes (3 specific bugs + 91 skip marks)
### Check for skipif markers:

### Check STATE_OF_TRUTH.md for A.4 entry:
(no A.4 entry)

### STATUS: **غير مُنفَّذ** — لا وجود لأي إصلاح pytest مُحدد أو skipif markers

## أ.5 — Fix 4 broken cross-repo README references
### Check for broken references in README.md:

### STATUS: **غير مُنفَّذ** — لا يوجد دليل على إصلاح مراجع README

## أ.6 — DOCS_CONSOLIDATION_PLAN.md
### File existence:
ls: cannot access '/home/z/my-project/omni-medical-suite/DOCS_CONSOLIDATION_PLAN.md': No such file or directory

### Git log for file:

### Claimed commit 18f689e:
DOES NOT EXIST

### STATUS: **غير مُنفَّذ فعلياً** — الملف غير موجود، الـcommit غير موجود

---

## ب.1 — GLOSSARY_SOURCES_AUDIT.md
### File existence:
ls: cannot access '/home/z/my-project/arabic-medical-glossary/GLOSSARY_SOURCES_AUDIT.md': No such file or directory

### Git log:

### STATUS: **غير مُنفَّذ فعلياً** — الملف غير موجود

## ب.2 — Deduplicate CSV/JSONL (174MB waste)
### Files existence:
-rwxr-xr-x 1 z z 1765052 Jul 10 14:23 /home/z/my-project/arabic-medical-glossary/data/all_pairs.csv
-rwxr-xr-x 1 z z 1596850 Jul 10 14:23 /home/z/my-project/arabic-medical-glossary/data/all_pairs.jsonl

### Scripts:
ls: cannot access '/home/z/my-project/arabic-medical-glossary/scripts/export_format.py': No such file or directory

### STATUS: **غير مُنفَّذ** — لا يوجد scripts/export_format.py

## ب.3 — Git LFS for >5MB files
### .gitattributes existence:
ls: cannot access '/home/z/my-project/arabic-medical-glossary/.gitattributes': No such file or directory

### STATUS: **غير مُنفَّذ** — لا يوجد .gitattributes

## ب.4 — Rename hama_pharma_master files
### Current files:
-rwxr-xr-x 1 z z 12245 Jul  9 23:38 /home/z/my-project/arabic-medical-glossary/terms/hama_pharma_master.csv
-rwxr-xr-x 1 z z 15830 Jul  9 23:38 /home/z/my-project/arabic-medical-glossary/terms/hama_pharma_master_terms.csv

### STATUS: **غير مُنفَّذ** — الملفات لا تزال بأسمائها القديمة

## ب.5 — Move working files out of root
### Working files in root:
ls: cannot access '/home/z/my-project/arabic-medical-glossary/_batch_progress.json': No such file or directory
ls: cannot access '/home/z/my-project/arabic-medical-glossary/_progress_v2.json': No such file or directory
-rwxr-xr-x 1 z z 5586 Jul 10 13:27 /home/z/my-project/arabic-medical-glossary/collection.log
-rwxr-xr-x 1 z z  150 Jul  9 23:38 /home/z/my-project/arabic-medical-glossary/ocr_ar_log.txt
-rwxr-xr-x 1 z z   68 Jul  9 23:38 /home/z/my-project/arabic-medical-glossary/ocr_auto.log
-rwxr-xr-x 1 z z   53 Jul  9 23:38 /home/z/my-project/arabic-medical-glossary/ocr_batch.log

/home/z/my-project/arabic-medical-glossary/ocr_output:
total 1352
drwxr-xr-x  2 z z  4096 Jul 10 13:27 .
drwxr-xr-x 11 z z  4096 Jul 10 13:27 ..
-rwxr-xr-x  1 z z 34349 Jul  9 23:38 ABESTOL_ocr.txt
-rwxr-xr-x  1 z z 31745 Jul  9 23:38 AGILOMOX_ocr.txt
-rwxr-xr-x  1 z z 24503 Jul  9 23:38 ALOGLIPTIN_ocr.txt
-rwxr-xr-x  1 z z 13522 Jul  9 23:38 ANTI-STONE_ocr.txt
-rwxr-xr-x  1 z z  8198 Jul  9 23:38 ANTI-TUSSIVE_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 47473 Jul  9 23:38 ARIPIPRAZOLE_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 36389 Jul  9 23:38 ARTHROBYE_ocr.txt
-rwxr-xr-x  1 z z 17848 Jul  9 23:38 ARTHROSIN_ocr.txt
-rwxr-xr-x  1 z z  9221 Jul  9 23:38 BY-TUBIN_ocr.txt
-rwxr-xr-x  1 z z    50 Jul  9 23:38 CARDEF_ar_ocr.txt
-rwxr-xr-x  1 z z  9611 Jul  9 23:38 CARDEF_ocr.txt
-rwxr-xr-x  1 z z  9029 Jul  9 23:38 CHOLVIT_ar_ocr.txt
-rwxr-xr-x  1 z z 13331 Jul  9 23:38 CHOLVIT_ocr.txt
-rwxr-xr-x  1 z z  4812 Jul  9 23:38 CIPROFLOXACIN_HAMA_PARMA_ar_ocr.txt
-rwxr-xr-x  1 z z 22747 Jul 10 13:27 CIPROFLOXACIN_HAMA_PARMA_ocr.txt
-rwxr-xr-x  1 z z  2176 Jul  9 23:38 CLOZAPINE_HAMA_PHARMA_ar_ocr.txt
-rwxr-xr-x  1 z z 31708 Jul 10 13:27 CLOZAPINE_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  2914 Jul  9 23:38 CONVAL_ar_ocr.txt
-rwxr-xr-x  1 z z  4009 Jul  9 23:38 CYAMOCET_ar_ocr.txt
-rwxr-xr-x  1 z z  5348 Jul  9 23:38 DEFORCE_ar_ocr.txt
-rwxr-xr-x  1 z z   907 Jul  9 23:38 DIATAMB_PLUS_ar_ocr.txt
-rwxr-xr-x  1 z z  4568 Jul  9 23:38 DIATAMB_ar_ocr.txt
-rwxr-xr-x  1 z z 15083 Jul  9 23:38 DIAZEPAM_HAMA_PHARMA_ar_ocr.txt
-rwxr-xr-x  1 z z 10857 Jul 10 13:27 DICLOFENAC_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  9888 Jul 10 13:27 DILTIAZEM_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  8483 Jul 10 13:27 DRNA_STOP_ocr.txt
-rwxr-xr-x  1 z z 20931 Jul 10 13:27 ENALAPRIL_PLUS_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 26020 Jul 10 13:27 FAST-VOL_ocr.txt
-rwxr-xr-x  1 z z 15031 Jul 10 13:27 FEDROFEN_ocr.txt
-rwxr-xr-x  1 z z  8933 Jul 10 13:27 FEDROLIDINE_ocr.txt
-rwxr-xr-x  1 z z  4358 Jul 10 13:27 FEM-RELIEVE_ocr.txt
-rwxr-xr-x  1 z z  4444 Jul 10 13:27 FERULA-Z_ocr.txt
-rwxr-xr-x  1 z z  5065 Jul 10 13:27 FERULA_ocr.txt
-rwxr-xr-x  1 z z 30749 Jul 10 13:27 FUROLACT_ocr.txt
-rwxr-xr-x  1 z z  7432 Jul 10 13:27 FUROPOT_ocr.txt
-rwxr-xr-x  1 z z 33067 Jul 10 13:27 GLIFOLONG_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 GLUCOBYE_PLUS_ocr.txt
-rwxr-xr-x  1 z z 13078 Jul 10 13:27 GLUCOBYE_ocr.txt
-rwxr-xr-x  1 z z  3683 Jul 10 13:27 HAMA_PHARMA_C_and_Z_ocr.txt
-rwxr-xr-x  1 z z  2998 Jul 10 13:27 HAMA_PHARMA_C_ocr.txt
-rwxr-xr-x  1 z z 13187 Jul 10 13:27 IMPROMOOD_SR_ocr.txt
-rwxr-xr-x  1 z z  9209 Jul 10 13:27 KETOTIFEN_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 21714 Jul 10 13:27 LINAVUS_ocr.txt
-rwxr-xr-x  1 z z 19004 Jul 10 13:27 LOSSPAL_ocr.txt
-rwxr-xr-x  1 z z 11043 Jul 10 13:27 MELATONIN_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  8654 Jul 10 13:27 METRONIDAZOLE_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 11877 Jul 10 13:27 METRONIDAZOLE_PLUS_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 13138 Jul 10 13:27 MULER_ocr.txt
-rwxr-xr-x  1 z z 12923 Jul 10 13:27 NIVOLTIC_ocr.txt
-rwxr-xr-x  1 z z 12981 Jul 10 13:27 NODEMENT_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 NORTRIPTYLINE_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 OFLOXAZOLE_ocr.txt
-rwxr-xr-x  1 z z  3148 Jul 10 13:27 ORFAM_ocr.txt
-rwxr-xr-x  1 z z 12392 Jul 10 13:27 ORLISTAT_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  6659 Jul 10 13:27 ORVAN_ocr.txt
-rwxr-xr-x  1 z z  6775 Jul 10 13:27 PARACETAMOL_ADVANCE_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 17972 Jul 10 13:27 PARACETAMOL_EXTRA_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 12404 Jul 10 13:27 PARACETAMOL_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 12404 Jul 10 13:27 PARACETAMOL_SR_HAMA_PHARMA_1000_ocr.txt
-rwxr-xr-x  1 z z 12304 Jul 10 13:27 PHENOBARBITAL_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 17345 Jul 10 13:27 PHENYTOIN_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z 12490 Jul 10 13:27 PIZET_ocr.txt
-rwxr-xr-x  1 z z 20286 Jul 10 13:27 PLEXADOL_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 POSACAR_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 PRECOBAL_ocr.txt
-rwxr-xr-x  1 z z 24280 Jul  9 23:38 PRICKSAGE_ocr.txt
-rwxr-xr-x  1 z z  3837 Jul 10 13:27 PULSA_ocr.txt
-rwxr-xr-x  1 z z 12845 Jul 10 13:27 REVMAT_ocr.txt
-rwxr-xr-x  1 z z 11727 Jul 10 13:27 REVMOX_ocr.txt
-rwxr-xr-x  1 z z 16568 Jul 10 13:27 ROVALTRO_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 SIMVATROL_ocr.txt
-rwxr-xr-x  1 z z 13565 Jul 10 13:27 SLEETOMEN_ocr.txt
-rwxr-xr-x  1 z z 31786 Jul 10 13:27 SOMATRA_ocr.txt
-rwxr-xr-x  1 z z 14358 Jul 10 13:27 SUMATRIPTAN_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z  4486 Jul 10 13:27 TERPOPHEREN_ocr.txt
-rwxr-xr-x  1 z z 13180 Jul 10 13:27 THEOLONG_ocr.txt
-rwxr-xr-x  1 z z 20309 Jul 10 13:27 TIBISTOP_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TRAKINZA_ocr.txt
-rwxr-xr-x  1 z z 15744 Jul 10 13:27 TRAMADOL_HAMA_PHARMA_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TRIODEF_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TRIOSAR_ocr.txt
-rwxr-xr-x  1 z z  5836 Jul 10 13:27 TRIOVITABIN_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TRI_DIAB_10-5-1000_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TROMBO_STOP_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 TUBOZID_ocr.txt
-rwxr-xr-x  1 z z  9821 Jul 10 13:27 ULCER-STOP_ocr.txt
-rwxr-xr-x  1 z z 15074 Jul 10 13:27 VALSABITRIL_ocr.txt
-rwxr-xr-x  1 z z 16596 Jul 10 13:27 VARDETRA_ocr.txt
-rwxr-xr-x  1 z z 11448 Jul 10 13:27 VITEOCTIN_ocr.txt
-rwxr-xr-x  1 z z  6897 Jul 10 13:27 VITOREX_ocr.txt
-rwxr-xr-x  1 z z  6200 Jul 10 13:27 VOLU-COLD_ocr.txt
-rwxr-xr-x  1 z z  6462 Jul 10 13:27 VOLU-GRIPP_ocr.txt
-rwxr-xr-x  1 z z  9719 Jul 10 13:27 WELL_FER_ocr.txt
-rwxr-xr-x  1 z z    50 Jul 10 13:27 XITAT_ocr.txt
-rwxr-xr-x  1 z z  7853 Jul 10 13:27 ZYBIAX_ocr.txt
-rwxr-xr-x  1 z z   619 Jul  9 23:38 _batch_progress.json
-rwxr-xr-x  1 z z  1652 Jul 10 13:27 _progress_v2.json
-rwxr-xr-x  1 z z 24280 Jul  9 23:38 pricksage_ocr.txt

### STATUS: **غير مُنفَّذ** — الملفات لا تزال في root

## ب.6 — Rewrite README.md
### Current README size:
17 /home/z/my-project/arabic-medical-glossary/README.md

### STATUS: **غير مُنفَّذ فعلياً** — يحتاج مراجعة وتحديث

