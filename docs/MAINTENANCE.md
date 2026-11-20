# OmniMedical Suite — Maintenance Runbook

> **Last updated:** 2025-01-01  
> **Audience:** DevOps engineers, on-call responders, and project maintainers  
> **Scope:** All production, staging, and HF Space deployments of the OmniMedical Suite

---

## Table of Contents

1. [Maintenance Schedule](#1-maintenance-schedule)
2. [Runbook: High Error Rate](#2-runbook-high-error-rate)
3. [Runbook: High Latency](#3-runbook-high-latency)
4. [Runbook: OCR Processing Failures](#4-runbook-ocr-processing-failures)
5. [Runbook: Model Accuracy Degradation](#5-runbook-model-accuracy-degradation)
6. [Runbook: HF Space Build Failure](#6-runbook-hf-space-build-failure)
7. [Runbook: Database Issues](#7-runbook-database-issues)
8. [Backup Strategy](#8-backup-strategy)
9. [Disaster Recovery](#9-disaster-recovery)
10. [Dependency Management](#10-dependency-management)
11. [Improvement Tracking](#11-improvement-tracking)

---

## 1. Maintenance Schedule

The following table defines all recurring maintenance tasks for the OmniMedical Suite. Tasks marked **automated** run via cron schedules or GitHub Actions; tasks marked **manual** require a maintainer's attention on the stated cadence.

| Task | Frequency | Owner | Command / Script | Automation |
|------|-----------|-------|-------------------|------------|
| Dependency updates (pip packages) | Monthly | DevOps / Dependabot | `python scripts/update_dependencies.py --all` | Dependabot PRs + manual merge |
| Security scanning (pip-audit, bandit) | Weekly | Security lead | GitHub Actions: `.github/workflows/security-scan.yml` | Automated |
| Backup verification | Weekly | DevOps | `bash apps/handwriting-demo/scripts/backup.sh --dry-run` then `bash apps/handwriting-demo/scripts/backup_verify.sh` | Cron: `0 3 * * 1` |
| Full backup execution | Daily | DevOps | `bash apps/handwriting-demo/scripts/backup.sh` | Cron: `0 2 * * *` |
| Model retraining evaluation | Monthly | ML engineer | `python evaluation/benchmark_runner.py --full` | Manual trigger |
| Performance review (latency, throughput) | Monthly | Backend lead | Prometheus dashboard review + `python tests/test_performance.py` | Manual review |
| Ruff lint check | Per PR | All contributors | `ruff check .` / `ruff check . --fix` | CI gate on PR |
| Full test suite | Per PR | All contributors | `pytest tests/ -v --tb=short` | CI gate on PR |
| Load testing | Monthly | QA / DevOps | `locust -f tests/loadtest/locustfile.py --headless -u 50 -r 10 -t 5m` | Manual trigger |
| Docker image rebuild | On dependency change | DevOps | `docker compose -f docker-compose.prod.yml build --no-cache` | Triggered by Dependabot merge |
| Alembic migration check | Per PR | Backend lead | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | CI gate |
| HF Space health check | Weekly | DevOps | `python hf-space/deploy_space.py --dry-run` | Manual or cron |
| Trainer-UI backup | Weekly | DevOps | `bash apps/trainer-ui/scripts/backup.sh` | Cron: `0 2 * * 0` |
| Golden dataset integrity check | Monthly | ML engineer | `python -c "from evaluation.benchmark import BenchmarkRunner; BenchmarkRunner().validate_golden()"` | Manual |

### Cron Configuration Example

Add the following to the production server's crontab (`crontab -e`):

```cron
# OmniMedical Suite automated maintenance
0 2 * * * cd /opt/omni-medical-suite && bash apps/handwriting-demo/scripts/backup.sh >> /var/log/omni-backup.log 2>&1
0 3 * * 1 cd /opt/omni-medical-suite && bash apps/handwriting-demo/scripts/backup_verify.sh >> /var/log/omni-backup-verify.log 2>&1
0 2 * * 0 cd /opt/omni-medical-suite && bash apps/trainer-ui/scripts/backup.sh >> /var/log/trainer-backup.log 2>&1
```

---

## 2. Runbook: High Error Rate

### Symptoms

- **5xx error rate exceeds 5%** of total requests over a 5-minute window.
- Alert fires from Prometheus: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05`
- Users report "Internal Server Error" or "Service Unavailable" in the Gradio UI and API responses.
- Sentry or error tracking shows a spike in unhandled exceptions.

### Diagnosis Steps

**Step 1 — Check application logs for error patterns:**

```bash
# Tail recent API server logs (Docker)
docker compose -f docker-compose.prod.yml logs --tail=500 api-server 2>&1 | \
  jq -r 'select(.level == "ERROR") | "\(.timestamp) \(.message)"' | \
  tail -50

# Count errors by type in the last hour
docker compose -f docker-compose.prod.yml logs --since=1h api-server 2>&1 | \
  jq -r 'select(.level == "ERROR") | .message' | \
  sort | uniq -c | sort -rn | head -20
```

**Step 2 — Check Prometheus metrics:**

```bash
# Query error rate by endpoint
curl -s 'http://localhost:9090/api/v1/query?query=topk(10,sum(rate(http_requests_total{status=~"5.."}[5m]))by(endpoint))' | \
  jq '.data.result[] | "\(.metric.endpoint): \(.value[1]) req/s"'

# Check if any service is down
curl -s 'http://localhost:9090/api/v1/query?query=up' | \
  jq '.data.result[] | "\(.metric.job): \(.value[1])"'
```

**Step 3 — Check database connectivity:**

```bash
# Test PostgreSQL connection from the API container
docker compose -f docker-compose.prod.yml exec api-server python -c "
import psycopg2
conn = psycopg2.connect(host='postgres', port=5432, dbname='medical_ocr', user='ocr_user', password='ocr_password_123')
cur = conn.cursor()
cur.execute('SELECT 1')
print('Database connection: OK')
conn.close()
"
```

**Step 4 — Check Redis connectivity:**

```bash
# Test Redis from the API container
docker compose -f docker-compose.prod.yml exec api-server python -c "
import redis
r = redis.Redis(host='redis', port=6379, decode_responses=True)
print('Redis PING:', r.ping())
print('Redis INFO keyspace:', r.info('keyspace'))
"
```

### Resolution Steps

**Step 1 — Restart affected services:**

```bash
# Restart API server only
docker compose -f docker-compose.prod.yml restart api-server

# If errors persist, restart all services
docker compose -f docker-compose.prod.yml restart

# If still failing, full recreate
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

**Step 2 — Check for dependency conflicts after a recent deploy:**

```bash
# Verify installed packages match requirements
docker compose -f docker-compose.prod.yml exec api-server pip check

# Check for recent dependency changes
git log --oneline -10 -- requirements/

# If a bad dependency was introduced, rollback
git log --oneline -5
git revert <bad-commit-hash>
docker compose -f docker-compose.prod.yml up -d --build api-server
```

**Step 3 — Rollback to previous Docker image if needed:**

```bash
# List recent images
docker images | grep omni-medical

# Re-tag and rollback to previous known-good image
docker tag omni-medical-api:<previous-tag> omni-medical-api:latest
docker compose -f docker-compose.prod.yml up -d api-server
```

**Step 4 — If database is the root cause, see [Runbook: Database Issues](#7-runbook-database-issues).**

### Escalation

If error rate remains above 5% after 15 minutes of troubleshooting, escalate to the backend lead and notify the team via the `#incidents` Slack channel. If the issue involves patient data exposure, also notify the security lead immediately per the incident response plan in `SECURITY.md`.

---

## 3. Runbook: High Latency

### Symptoms

- **P95 response latency exceeds 5 seconds** sustained over a 10-minute window.
- Prometheus alert: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[10m])) > 5`
- Users report timeouts when processing medical documents, especially multi-page PDFs.
- Gradio UI shows "Processing..." for extended periods without results.

### Diagnosis Steps

**Step 1 — Identify slow endpoints via Prometheus:**

```bash
# Top 10 slowest endpoints by P95 latency
curl -s 'http://localhost:9090/api/v1/query?query=topk(10,histogram_quantile(0.95,sum(rate(http_request_duration_seconds_bucket[10m]))by(le,endpoint)))' | \
  jq '.data.result[] | "\(.metric.endpoint): P95=\(.value[1])s"'

# Check average latency per endpoint
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(http_request_duration_seconds_sum[10m]))by(endpoint)/sum(rate(http_request_duration_seconds_count[10m]))by(endpoint)' | \
  jq '.data.result[] | "\(.metric.endpoint): avg=\(.value[1])s"'
```

**Step 2 — Profile the OCR processing pipeline:**

```bash
# Run a profiling trace on the API server
docker compose -f docker-compose.prod.yml exec api-server python -c "
import cProfile, pstats, io
from hf_space.packages.vision.ocr_engine import OCREngine
pr = cProfile.Profile()
pr.enable()
engine = OCREngine()
result = engine.process('samples/test_prescription.png')
pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(30)
print(s.getvalue())
"
```

**Step 3 — Check system resource utilization:**

```bash
# CPU and memory for all containers
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Disk I/O (if available)
iostat -x 1 3 2>/dev/null || echo "iostat not available"

# Check if GPU is saturated (OCR workloads)
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader
```

**Step 4 — Check Redis cache hit rate:**

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO stats | \
  awk '/keyspace_hits|keyspace_misses/ {print $0}'

# Calculate hit rate manually
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO stats | \
  awk '/keyspace_hits/{h=$3} /keyspace_misses/{m=$3} END{if(h+m>0) printf "Cache hit rate: %.2f%%\n", h/(h+m)*100; else print "No cache traffic"}'
```

### Resolution Steps

**Step 1 — Enable or expand caching for frequent queries:**

```bash
# Increase Redis max memory if needed
docker compose -f docker-compose.prod.yml exec redis redis-cli CONFIG SET maxmemory 2gb
docker compose -f docker-compose.prod.yml exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Warm the cache with common medical terms
docker compose -f docker-compose.prod.yml exec api-server python -c "
from app.core.monitoring.logging import warm_cache
warm_cache()
print('Cache warmed successfully')
"
```

**Step 2 — Optimize slow database queries:**

```bash
# Find the slowest queries currently running
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"

# Add missing indexes if identified
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_corrections_word ON corrections(word);
"
```

**Step 3 — Scale horizontally:**

```bash
# Scale API workers to handle more load
docker compose -f docker-compose.prod.yml up -d --scale api-server=3

# If using the worker service, scale OCR workers
docker compose -f docker-compose.prod.yml up -d --scale worker=2
```

**Step 4 — Reduce OCR batch size for large documents:**

```bash
# Update environment variable and restart
docker compose -f docker-compose.prod.yml exec api-server bash -c \
  'echo "OCR_BATCH_SIZE=4" >> /app/.env'
docker compose -f docker-compose.prod.yml restart api-server
```

### Prevention

- Set up a latency SLO alert at P95 < 3s (warning) and P95 < 5s (critical).
- Review and optimize the top 5 slowest endpoints monthly using the Prometheus dashboard.
- Run load tests (`locust`) after every dependency upgrade to catch regressions early.

---

## 4. Runbook: OCR Processing Failures

### Symptoms

- API returns **500 errors** on `/api/ocr/process` and `/api/ocr/batch` endpoints.
- Processing requests **time out** after 60+ seconds without returning results.
- PaddleOCR or EasyOCR engine fails to initialize with model loading errors.
- Logs show `CUDA out of memory`, `OOMKilled`, or `Model file not found` errors.

### Diagnosis Steps

**Step 1 — Check Docker container logs for OCR-specific errors:**

```bash
# API server logs filtered for OCR errors
docker compose -f docker-compose.prod.yml logs --tail=200 api-server 2>&1 | \
  jq -r 'select(.message | test("OCR|paddle|easyocr|CUDA|OOM|memory"; "i")) | "\(.timestamp) [\(.level)] \(.message)"'

# Worker container logs
docker compose -f docker-compose.prod.yml logs --tail=200 worker 2>&1 | \
  jq -r 'select(.level == "ERROR") | .message' | tail -30
```

**Step 2 — Check PaddleOCR model files and directories:**

```bash
# Verify model files exist and are not corrupted
docker compose -f docker-compose.prod.yml exec api-server bash -c '
echo "=== PaddleOCR Model Files ==="
ls -lh ~/.paddleocr/ 2>/dev/null || echo "No ~/.paddleocr directory"
echo ""
echo "=== Model Registry Check ==="
python -c "
from hf_space.packages.core.model_registry import ModelRegistry
reg = ModelRegistry()
print(\"Registered models:\", reg.list_models())
print(\"Health:\", reg.health_check())
" 2>&1
'
```

**Step 3 — Check GPU status and memory:**

```bash
# NVIDIA GPU utilization and memory
nvidia-smi

# If nvidia-smi is not available on host, check from container
docker compose -f docker-compose.prod.yml exec api-server nvidia-smi 2>&1 || \
  echo "GPU not available — check NVIDIA driver and container runtime"

# Check for OOM events in Docker
docker inspect $(docker compose -f docker-compose.prod.yml ps -q api-server) | \
  jq '.[0].State.OOMKilled'
```

**Step 4 — Check disk space for model caches:**

```bash
# Disk usage on the host
df -h /var/lib/docker /opt/omni-medical-suite

# Inside the container
docker compose -f docker-compose.prod.yml exec api-server df -h /
```

### Resolution Steps

**Step 1 — Restart the OCR services to reload models:**

```bash
# Restart only the API server (faster recovery)
docker compose -f docker-compose.prod.yml restart api-server
sleep 10

# Verify OCR is working
curl -X POST http://localhost:8000/api/ocr/process \
  -F "file=@samples/test_prescription.png" \
  -F "engine=paddleocr" | jq '.status, .text[:100]'

# If that fails, restart worker too
docker compose -f docker-compose.prod.yml restart worker
```

**Step 2 — Clear stale model caches and re-download:**

```bash
# Remove corrupted PaddleOCR cache
docker compose -f docker-compose.prod.yml exec api-server bash -c '
rm -rf ~/.paddleocr/whl/
rm -rf ~/.paddleocr/inference/
echo "Cleared PaddleOCR caches"
'

# Re-download models
docker compose -f docker-compose.prod.yml exec api-server python -c "
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='ar')
print('PaddleOCR models re-downloaded and initialized successfully')
"

# Clear Hugging Face model caches if used
docker compose -f docker-compose.prod.yml exec api-server bash -c '
find /root/.cache/huggingface/ -name "*.lock" -delete 2>/dev/null
echo "Cleared HF cache locks"
'
```

**Step 3 — Reduce batch size to avoid OOM:**

```bash
# Set a smaller batch size via environment variable
docker compose -f docker-compose.prod.yml exec api-server bash -c '
export OCR_BATCH_SIZE=2
export PADDLEOCR_USE_GPU=true
export PADDLEOCR_LIMIT_GPU_MEM=0.5
'
docker compose -f docker-compose.prod.yml restart api-server
```

**Step 4 — If GPU is unavailable, fall back to CPU mode:**

```bash
# Disable GPU and use CPU-only processing
docker compose -f docker-compose.prod.yml exec api-server bash -c '
echo "PADDLEOCR_USE_GPU=false" >> /app/.env
echo "EASYOCR_GPU=false" >> /app/.env
'
docker compose -f docker-compose.prod.yml restart api-server

# Verify CPU mode is active
docker compose -f docker-compose.prod.yml logs --tail=20 api-server 2>&1 | \
  jq -r 'select(.message | test("CPU|GPU")) | .message'
```

### Prevention

- Set up GPU memory monitoring alerts at 85% utilization.
- Pre-warm OCR models on container startup (already configured in `Dockerfile.api`).
- Keep PaddleOCR model versions pinned in `requirements/base.txt` to avoid unexpected model downloads.

---

## 5. Runbook: Model Accuracy Degradation

### Symptoms

- **Character Error Rate (CER) exceeds 10%** on the benchmark evaluation set.
- Users submit feedback via `app/core/monitoring/feedback.py` with low ratings (1-2 stars) and complaints about incorrect OCR output.
- Medical term recognition accuracy drops noticeably — common drug names, dosages, or patient identifiers are misread.
- The `model_accuracy` Prometheus gauge drops below the 0.90 threshold.

### Diagnosis Steps

**Step 1 — Run the benchmark evaluation suite:**

```bash
# Run full benchmark to get current CER, WER, and BLEU scores
cd /opt/omni-medical-suite
python evaluation/benchmark_runner.py --full --output benchmarks/results/latest_eval.json

# Compare against the previous known-good benchmark
python -c "
import json
with open('benchmarks/results/latest_eval.json') as f:
    latest = json.load(f)
with open('benchmarks/results/v2.0_improvement.json') as f:
    previous = json.load(f)
print('=== Accuracy Comparison ===')
for metric in ['cer', 'wer', 'bleu']:
    curr = latest.get(metric, 'N/A')
    prev = previous.get(metric, 'N/A')
    print(f'  {metric.upper()}: current={curr}, previous={prev}')
"
```

**Step 2 — Check model version and registry:**

```bash
# Verify which model version is loaded
docker compose -f docker-compose.prod.yml exec api-server python -c "
from hf_space.packages.core.model_registry import ModelRegistry
reg = ModelRegistry()
models = reg.list_models()
for m in models:
    info = reg.get_model_info(m)
    print(f'Model: {m}, Version: {info.get(\"version\", \"unknown\")}, Path: {info.get(\"path\", \"unknown\")}')
"

# Check if model files have been modified or corrupted
docker compose -f docker-compose.prod.yml exec api-server bash -c '
echo "=== Model file checksums ==="
find /app/models/ -type f -name "*.pt" -o -name "*.pth" -o -name "*.onnx" | \
  while read f; do
    echo "$(md5sum "$f")  $f"
  done
'
```

**Step 3 — Review user feedback trends:**

```bash
# Analyze recent feedback from the JSONL store
docker compose -f docker-compose.prod.yml exec api-server python -c "
from app.core.monitoring.feedback import FeedbackCollector
fc = FeedbackCollector('/app/data/feedback.jsonl')
stats = fc.get_stats()
print('=== Feedback Summary ===')
print(f'Total feedback: {stats[\"total\"]}')
print(f'Average rating: {stats[\"avg_rating\"]}')
print('By category:')
for cat, data in stats.get('by_category', {}).items():
    print(f'  {cat}: {data[\"count\"]} entries, avg={data[\"avg_rating\"]}')

# Get recent low-rating feedback
recent = fc.get_recent(20)
low = [r for r in recent if r['rating'] <= 2]
if low:
    print(f'\n=== Recent Low Ratings ({len(low)} entries) ===')
    for r in low[-5:]:
        print(f'  [{r[\"category\"]}] Rating={r[\"rating\"]}: {r[\"message\"][:100]}')
"
```

### Resolution Steps

**Step 1 — Rollback to the previous known-good model version:**

```bash
# List available model versions from backup
ls -la /opt/omni-medical-suite/backups/latest/models/

# Restore the previous model from backup
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id <previous-backup-timestamp> \
  --component models \
  --force

# Restart services to load the restored model
docker compose -f docker-compose.prod.yml restart api-server worker

# Re-run benchmark to verify improvement
python evaluation/benchmark_runner.py --full
```

**Step 2 — Retrain the model with recent training data:**

```bash
# Collect new training data from feedback and corrections
docker compose -f docker-compose.prod.yml exec api-server python -c "
from hf_space.packages.vision.dataset_builder import DatasetBuilder
builder = DatasetBuilder()
builder.build_from_feedback(output_path='/app/data/training_set_latest.jsonl')
print(f'Built training set: {builder.stats()}')
"

# Run fine-tuning
docker compose -f docker-compose.prod.yml exec api-server python -c "
from hf_space.packages.vision.finetuning import FineTuner
ft = FineTuner(
    base_model='microsoft/trocr-base-handwritten',
    train_data='/app/data/training_set_latest.jsonl',
    output_dir='/app/models/retrained_latest'
)
ft.train(epochs=5, batch_size=8, learning_rate=3e-5)
print('Fine-tuning complete')
"

# Register the retrained model
docker compose -f docker-compose.prod.yml exec api-server python -c "
from hf_space.packages.core.model_registry import ModelRegistry
reg = ModelRegistry()
reg.register_model('ocr-retrained-latest', '/app/models/retrained_latest', version='auto')
print('Model registered')
"
```

**Step 3 — Check and fix data quality issues:**

```bash
# Inspect the training data for corruption or mislabeling
docker compose -f docker-compose.prod.yml exec api-server python -c "
import json
bad = 0
total = 0
with open('/app/data/training_set_latest.jsonl') as f:
    for line in f:
        total += 1
        entry = json.loads(line)
        if not entry.get('text') or not entry.get('image_path'):
            bad += 1
        elif len(entry.get('text', '')) < 2:
            bad += 1
print(f'Data quality: {total - bad}/{total} valid entries ({bad} bad)')
"
```

### Prevention

- Run `evaluation/benchmark_runner.py --full` weekly and track results in a time-series.
- Set a Prometheus alert on `model_accuracy < 0.90` with a 1-hour window.
- Review low-rating feedback entries weekly and add corrections to the golden dataset.

---

## 6. Runbook: HF Space Build Failure

### Symptoms

- The Hugging Face Space at `https://huggingface.co/spaces/<org>/omni-medical-suite` shows a **"Build Error"** or **"Space not loading"** message.
- The Dockerfile build fails during `hf-space/Dockerfile` execution.
- After pushing to the `main` branch, the Space does not update within 15 minutes.
- Gradio app fails to start with import errors or missing dependencies.

### Diagnosis Steps

**Step 1 — Check GitHub Actions CI logs:**

```bash
# If using CI to deploy to HF Space
gh run list --workflow=deploy-hf-space.yml --limit 5

# Get logs for the latest failed run
gh run view --log-failed $(gh run list --workflow=deploy-hf-space.yml --status=failure --json databaseId -q '.[0].databaseId')
```

**Step 2 — Check HF Space build logs:**

```bash
# Via huggingface-cli
huggingface-cli repo info <org>/omni-medical-suite

# Or check the Space logs directly
curl -s "https://huggingface.co/api/spaces/<org>/omni-medical-suite" | jq '.runtime, .sdk, .lastModified'
```

**Step 3 — Test the Dockerfile locally:**

```bash
# Build the HF Space Dockerfile locally to reproduce the error
cd /opt/omni-medical-suite/hf-space
docker build -t omni-hf-test -f Dockerfile . 2>&1 | tee /tmp/hf-build.log

# Check for the specific failure
grep -i "error\|failed\|exception" /tmp/hf-build.log | tail -20
```

**Step 4 — Check for dependency conflicts:**

```bash
# Verify all requirements are installable together
cd /opt/omni-medical-suite/hf-space
python -m venv /tmp/hf-venv-test
source /tmp/hf-venv-test/bin/activate
pip install -r requirements.txt 2>&1 | tee /tmp/hf-pip-install.log
grep -i "error\|conflict\|incompatible" /tmp/hf-pip-install.log
deactivate
rm -rf /tmp/hf-venv-test
```

### Resolution Steps

**Step 1 — Fix the Dockerfile:**

```bash
# Common fix: reduce image size by combining RUN layers
# Before (slow and large):
#   RUN pip install -r requirements.txt
#   RUN python download_models.py
# After (optimized):
#   RUN pip install --no-cache-dir -r requirements.txt && \
#       python download_models.py && \
#       rm -rf /root/.cache/pip

# Rebuild and test
cd /opt/omni-medical-suite/hf-space
docker build -t omni-hf-test -f Dockerfile .
docker run --rm -p 7860:7860 omni-hf-test
# Verify Gradio loads at http://localhost:7860
```

**Step 2 — Pin dependency versions to prevent breaking changes:**

```bash
# Generate pinned requirements
cd /opt/omni-medical-suite/hf-space
pip freeze > requirements.lock

# Replace unpinned versions in requirements.txt with exact versions
# Example: gradio>=4.0.0 -> gradio==4.44.1

# Verify the locked requirements build cleanly
docker build --no-cache -t omni-hf-pinned -f Dockerfile .
```

**Step 3 — Reduce Docker image size to stay under HF limits:**

```bash
# Check current image size
docker images omni-hf-test --format "{{.Size}}"

# If over 10GB, optimize:
# 1. Use multi-stage builds
# 2. Remove model caches after download if they can be re-downloaded at runtime
# 3. Use .dockerignore to exclude unnecessary files
cat > /opt/omni-medical-suite/hf-space/.dockerignore << 'EOF'
__pycache__
*.pyc
.git
tests/
docs/
*.md
EOF
```

**Step 4 — Redeploy to HF Space:**

```bash
# Using the deploy script
cd /opt/omni-medical-suite
python hf-space/deploy_space.py

# Or manual push
cd /opt/omni-medical-suite/hf-space
git add -A
git commit -m "fix: resolve Dockerfile build failure"
git push origin main
```

### Prevention

- Always test the Dockerfile locally before pushing to the HF Space repo.
- Pin all dependency versions in `hf-space/requirements.txt`.
- Use `hf-space/deploy_space.py --dry-run` to validate before deployment.
- Set up a GitHub Actions workflow that builds the HF Space Dockerfile on every PR targeting the HF repo.

---

## 7. Runbook: Database Issues

### Symptoms

- Application returns **"Connection refused"** or **"could not connect to server"** errors when accessing any database-dependent endpoint.
- Data inconsistency: documents appear missing, corrections are not persisted, or user sessions are lost.
- PostgreSQL logs show `FATAL: the database system is in recovery mode` or `out of shared memory`.
- Query performance degrades significantly, with simple SELECTs taking > 5 seconds.

### Diagnosis Steps

**Step 1 — Connect to PostgreSQL and check status:**

```bash
# Connect to the database container
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr

# Inside psql, run these diagnostic queries:
-- Check database size and table sizes
SELECT pg_size_pretty(pg_database_size('medical_ocr')) AS db_size;
SELECT relname AS table_name, pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;

-- Check for long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
  AND state != 'idle'
ORDER BY duration DESC;

-- Check for blocked queries
SELECT blocked.pid AS blocked_pid, blocked.query AS blocked_query,
       blocking.pid AS blocking_pid, blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
  AND blocked_locks.database IS NOT DISTINCT FROM blocking_locks.database
  AND blocked_locks.relation IS NOT DISTINCT FROM blocking_locks.relation
  AND blocked_locks.page IS NOT DISTINCT FROM blocking_locks.page
  AND blocked_locks.tuple IS NOT DISTINCT FROM blocking_locks.tuple
  AND blocked.pid != blocking.pid
JOIN pg_stat_activity blocking ON blocking.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Check for table bloat
SELECT relname, n_live_tup, n_dead_tup,
       ROUND(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_tuple_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY dead_tuple_pct DESC LIMIT 10;
```

**Step 2 — Check disk space:**

```bash
# Host disk space
df -h

# Docker volume disk usage
docker system df -v

# PostgreSQL data directory inside container
docker compose -f docker-compose.prod.yml exec postgres df -h /var/lib/postgresql/data

# Check if WAL files are accumulating
docker compose -f docker-compose.prod.yml exec postgres bash -c '
ls -lh /var/lib/postgresql/data/pg_wal/ | tail -5
du -sh /var/lib/postgresql/data/pg_wal/
'
```

**Step 3 — Check replication and WAL status (if applicable):**

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
SELECT pg_is_in_recovery();
SELECT pg_current_wal_lsn(), pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0') AS wal_bytes;
"
```

### Resolution Steps

**Step 1 — Terminate long-running or blocked queries:**

```bash
# Terminate a specific problematic query (replace <pid>)
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
SELECT pg_terminate_backend(<pid>);
"

# Terminate all idle connections older than 1 hour
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND (now() - query_start) > interval '1 hour';
"
```

**Step 2 — Vacuum and reindex the database:**

```bash
# Run VACUUM ANALYZE on all tables to reclaim space and update statistics
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
VACUUM ANALYZE;
"

# Rebuild indexes that may be corrupted or bloated
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
REINDEX DATABASE medical_ocr;
"

# For a single heavily-bloated table (replace <table_name>):
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
VACUUM FULL ANALYZE <table_name>;
"
```

**Step 3 — Restore from backup if data is corrupted:**

```bash
# List available backups
bash apps/handwriting-demo/scripts/restore.sh

# Restore only the database component
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id <timestamp> \
  --component db \
  --force

# Or restore using pg_restore directly
docker compose -f docker-compose.prod.yml exec postgres bash -c '
pg_restore -Fc -j 4 -U ocr_user -d medical_ocr \
  /backups/<timestamp>/db_medical_ocr.dump \
  --no-owner --no-privileges --clean --if-exists
'
```

**Step 4 — Restart PostgreSQL if it is in an unrecoverable state:**

```bash
# Graceful restart
docker compose -f docker-compose.prod.yml restart postgres

# If PostgreSQL won't start, check logs
docker compose -f docker-compose.prod.yml logs --tail=100 postgres

# If recovery is needed, start in single-user mode
docker compose -f docker-compose.prod.yml exec postgres bash -c '
pg_ctl -D /var/lib/postgresql/data -m immediate stop
pg_ctl -D /var/lib/postgresql/data start
'
```

### Prevention

- Monitor PostgreSQL disk usage and set alerts at 80% capacity.
- Schedule `VACUUM ANALYZE` daily via cron: `0 4 * * * docker compose -f docker-compose.prod.yml exec -T postgres psql -U ocr_user -d medical_ocr -c "VACUUM ANALYZE;"`.
- Enable `pg_stat_statements` in PostgreSQL to track slow queries over time.
- Keep WAL archiving configured if using replication.

---

## 8. Backup Strategy

### Overview

The OmniMedical Suite uses two complementary backup scripts depending on the deployment context:

1. **`apps/handwriting-demo/scripts/backup.sh`** — Full production backup for the handwriting-demo deployment with PostgreSQL, MinIO, model files, and configuration.
2. **`apps/trainer-ui/scripts/backup.sh`** — Lightweight backup for the Trainer-UI focused on SQLite databases, exported training data, and golden evaluation datasets.

### What Gets Backed Up

#### Production Backup (`apps/handwriting-demo/scripts/backup.sh`)

| Component | Method | Details |
|-----------|--------|---------|
| PostgreSQL database | `pg_dump -Fc -Z9` | Custom-format compressed dump of the `medical_ocr` database |
| MinIO bucket data | `mc mirror` | All objects in the `ocr-crops` bucket (crop images, training data) |
| Model files | `rsync --checksum` | All files under `models/` (PaddleOCR, TrOCR, fine-tuned weights) |
| Configuration | `cp` + optional `gpg` encrypt | `.env`, `config.py`, docker-compose files, k8s manifests |

Each backup includes **MD5 checksum manifests** for every component to verify integrity during restore.

#### Trainer-UI Backup (`apps/trainer-ui/scripts/backup.sh`)

| Component | Method | Details |
|-----------|--------|---------|
| SQLite database | `cp` | `data/corrections.db` (user corrections and learning data) |
| Exported data | `cp -r` | `exports/` directory (exported training datasets) |
| Golden datasets | `cp -r` | `data/golden/` (evaluation benchmark datasets) |

### Where Backups Are Stored

- **Default local path:** `$BACKUP_DIR/<timestamp>/` (defaults to `./backups/` within the project root)
- **Optional S3 upload:** Set `AWS_S3_BUCKET` and `AWS_REGION` environment variables to enable automatic S3 sync after each backup
- **Optional GPG encryption:** If `gpg` is available, the `.env` file is encrypted with AES256 before being stored in the backup

### Retention Policy

The production backup script implements a tiered retention strategy:

| Tier | Retention Period | Criteria |
|------|-----------------|----------|
| Daily | 7 days | All backups within the last 7 days are kept |
| Weekly | 4 weeks | Sunday backups are kept for up to 4 weeks |
| Monthly | 6 months | First-of-month backups are kept for up to 6 months |

The Trainer-UI backup keeps the **30 most recent** backups, deleting older ones automatically.

### Scheduling

Add to the production server's crontab:

```cron
# Daily full backup at 2:00 AM
0 2 * * * cd /opt/omni-medical-suite && bash apps/handwriting-demo/scripts/backup.sh >> /var/log/omni-backup.log 2>&1

# Weekly backup verification at 3:00 AM on Mondays
0 3 * * 1 cd /opt/omni-medical-suite && bash apps/handwriting-demo/scripts/backup_verify.sh >> /var/log/omni-backup-verify.log 2>&1

# Weekly Trainer-UI backup on Sundays at 2:00 AM
0 2 * * 0 cd /opt/omni-medical-suite && bash apps/trainer-ui/scripts/backup.sh >> /var/log/trainer-backup.log 2>&1
```

### Dry-Run Mode

Both backup scripts support a `--dry-run` flag that prints all actions without executing them. Use this to verify the backup configuration before running a real backup:

```bash
# Production backup dry-run
bash apps/handwriting-demo/scripts/backup.sh --dry-run

# Production backup with custom directory
BACKUP_DIR=/mnt/backups bash apps/handwriting-demo/scripts/backup.sh --dry-run
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — all components backed up |
| 1 | Partial — some components failed |
| 2 | Total failure — no usable backup created |

### Verification

After each backup, the script automatically verifies MD5 checksums for all components. To manually verify a specific backup:

```bash
# Verify the latest backup
cd /opt/omni-medical-suite/backups
LATEST=$(ls -d */ | sort -r | head -1)
cd "$LATEST"
md5sum -c db_medical_ocr.dump.md5
md5sum -c models_manifest.md5
md5sum -c minio_manifest.md5
```

---

## 9. Disaster Recovery

This section covers recovery procedures for catastrophic failures. All procedures assume you have at least one verified backup available (see [Backup Strategy](#8-backup-strategy)).

### 9.1 Database Corruption Recovery

When the PostgreSQL database becomes corrupted due to disk failure, accidental data deletion, or software bug:

```bash
# Step 1: Stop all application services to prevent further damage
docker compose -f docker-compose.prod.yml stop api-server worker

# Step 2: Identify a good backup (before corruption occurred)
bash apps/handwriting-demo/scripts/restore.sh
# Note the backup ID from the list, e.g. 2025-01-10_02-00-00

# Step 3: Restore the database (this drops and recreates the DB)
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id 2025-01-10_02-00-00 \
  --component db \
  --force

# Step 4: Verify the restore
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id 2025-01-10_02-00-00 \
  --component db

# Step 5: Run Alembic migrations to catch up if the backup is older
docker compose -f docker-compose.prod.yml exec api-server bash -c '
alembic upgrade head
'

# Step 6: Restart all services
docker compose -f docker-compose.prod.yml up -d

# Step 7: Verify data integrity
docker compose -f docker-compose.prod.yml exec postgres psql -U ocr_user -d medical_ocr -c "
SELECT count(*) AS documents FROM documents;
SELECT count(*) AS corrections FROM corrections;
SELECT count(*) AS users FROM users;
"
```

### 9.2 Model File Corruption Recovery

When trained model weights become corrupted or accidentally deleted:

```bash
# Step 1: Stop services that load models
docker compose -f docker-compose.prod.yml stop api-server worker

# Step 2: Restore model files from backup
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id <timestamp> \
  --component models \
  --force

# Step 3: Verify model file integrity via checksums
cd /opt/omni-medical-suite/backups/<timestamp>
md5sum -c models_manifest.md5

# Step 4: Restart services
docker compose -f docker-compose.prod.yml up -d api-server worker

# Step 5: Verify models load correctly
docker compose -f docker-compose.prod.yml exec api-server python -c "
from hf_space.packages.vision.ocr_engine import OCREngine
engine = OCREngine()
print('OCR Engine initialized:', type(engine))
result = engine.process('samples/test_prescription.png')
print('Test OCR result:', result.get('text', 'N/A')[:100])
"
```

### 9.3 Full System Failure Recovery

When the entire server or all Docker containers are lost (hardware failure, catastrophic misconfiguration):

```bash
# Step 1: Provision a new server with Docker and Docker Compose installed

# Step 2: Clone the repository (or restore from git bundle backup)
git clone https://github.com/<org>/omni-medical-suite.git /opt/omni-medical-suite
cd /opt/omni-medical-suite

# Step 3: If GitHub is unavailable, restore from git bundle
# (See 9.4 below for git bundle recovery)

# Step 4: Download the latest backup from S3 (if S3 sync is configured)
aws s3 sync s3://$AWS_S3_BUCKET/omni-medical-suite/ /opt/omni-medical-suite/backups/ \
  --region $AWS_REGION

# Step 5: Restore all components from the latest backup
bash apps/handwriting-demo/scripts/restore.sh \
  --backup-id <latest-timestamp> \
  --component all \
  --force

# Step 6: Decrypt the .env file if it was GPG-encrypted
gpg --batch --yes --decrypt \
  --output /opt/omni-medical-suite/.env \
  /opt/omni-medical-suite/backups/<timestamp>/config/.env.gpg

# Step 7: Start the full stack
docker compose -f docker-compose.prod.yml up -d --build

# Step 8: Verify all services are healthy
docker compose -f docker-compose.prod.yml ps
curl -f http://localhost:8000/health || echo "Health check failed"
curl -f http://localhost:7860/ || echo "Gradio UI failed"

# Step 9: Run the test suite to verify functionality
pytest tests/ -v --tb=short -x
```

### 9.4 GitHub Repository Loss Recovery

If the GitHub repository is accidentally deleted or becomes inaccessible, use the git bundle archives maintained by the backup system:

```bash
# Step 1: Check if git bundles exist in the backup
ls -la /opt/omni-medical-suite/backups/<timestamp>/config/
# Look for: medical-ocr-archived-*.bundle files

# Step 2: Clone from the git bundle
git clone /opt/omni-medical-suite/backups/<timestamp>/config/medical-ocr-archived-<date>.bundle \
  /opt/omni-medical-suite-restored

cd /opt/omni-medical-suite-restored
git log --oneline -10

# Step 3: Re-push to GitHub (if the repo was recreated)
git remote add origin https://github.com/<org>/omni-medical-suite.git
git push --all origin
git push --tags origin

# Step 4: Verify all branches are present
git branch -a
```

### Recovery Time Objectives

| Scenario | Target RTO | Target RPO |
|----------|-----------|-----------|
| Database corruption | 30 minutes | 24 hours (last daily backup) |
| Model corruption | 15 minutes | 7 days (last weekly backup) |
| Full system failure | 2 hours | 24 hours |
| GitHub repo loss | 1 hour | Last bundle date |

---

## 10. Dependency Management

### Dependabot Configuration

The OmniMedical Suite uses GitHub Dependabot for automated dependency updates, configured in `.github/dependabot.yml`. The configuration covers multiple ecosystems:

```yaml
# .github/dependabot.yml (reference)
version: 2
updates:
  # Python pip dependencies
  - package-ecosystem: "pip"
    directory: "/requirements"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 10
    reviewers:
      - "devops-team"
    labels:
      - "dependencies"
      - "automated"

  # Docker dependencies
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
      - "docker"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
```

Dependabot opens PRs automatically on the configured schedule. Each PR includes:
- Updated `requirements/*.txt` files with version bumps
- Changelog links for each updated package
- A CI test run to verify compatibility

### Manual Dependency Updates

For updates that require more control (e.g., major version bumps, breaking changes), use the manual update script:

```bash
# Update all dependencies across all requirement files
python scripts/update_dependencies.py --all

# Update only a specific package
python scripts/update_dependencies.py --package paddleocr

# Update with a specific version constraint
python scripts/update_dependencies.py --package gradio --constraint ">=4.40,<5.0"

# Dry-run to see what would change without modifying files
python scripts/update_dependencies.py --all --dry-run

# Update and automatically rebuild Docker images
python scripts/update_dependencies.py --all --rebuild-docker
```

### Handling Security Vulnerabilities

**Automated scanning via GitHub Actions (`.github/workflows/security-scan.yml`):**

```bash
# Trigger a manual security scan
gh workflow run security-scan.yml

# View security scan results
gh run list --workflow=security-scan.yml --limit 5
gh run view --log $(gh run list --workflow=security-scan.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

**Manual security audit using pip-audit:**

```bash
# Scan all installed packages for known vulnerabilities
pip-audit -r requirements/base.txt -r requirements/api.txt -r requirements/ml.txt

# Scan with severity filtering (only HIGH and CRITICAL)
pip-audit --severity high -r requirements/base.txt

# Generate a SARIF report for GitHub integration
pip-audit -r requirements/base.txt --format sarif --output security-audit.sarif
```

**Using bandit for Python code security analysis:**

```bash
# Run bandit on the entire codebase
bandit -r hf_space/ app/ packages/ -f json -o bandit-report.json

# Run bandit with severity threshold (skip LOW findings)
bandit -r hf_space/ app/ packages/ -ll

# Exclude test directories from scanning
bandit -r hf_space/ app/ packages/ --exclude tests/,tests/
```

**Response process for a discovered vulnerability:**

1. **Assess severity** — Check CVE database and advisories for the affected package.
2. **Check if exploitable** — Determine if the vulnerable code path is actually used in production.
3. **Update immediately** — If HIGH/CRITICAL and exploitable, update the dependency:
   ```bash
   pip-audit --fix -r requirements/base.txt
   ```
4. **Test thoroughly** — Run the full test suite after any security update:
   ```bash
   pytest tests/ -v --tb=short
   ```
5. **Rebuild and deploy** — Rebuild Docker images and redeploy:
   ```bash
   docker compose -f docker-compose.prod.yml build --no-cache
   docker compose -f docker-compose.prod.yml up -d
   ```
6. **Document** — Record the vulnerability and resolution in `CHANGELOG.md` and `SECURITY.md`.

---

## 11. Improvement Tracking

### Key Metrics to Track

The following metrics should be continuously monitored and tracked over time to measure the health and accuracy of the OmniMedical Suite:

| Metric | Description | Target | Source |
|--------|-------------|--------|--------|
| **CER** (Character Error Rate) | Percentage of characters incorrectly recognized | < 5% | `evaluation/benchmark_runner.py` |
| **WER** (Word Error Rate) | Percentage of words incorrectly recognized | < 10% | `evaluation/benchmark_runner.py` |
| **BLEU Score** | Bilingual Evaluation Understudy for translation quality | > 0.85 | `evaluation/benchmark_runner.py` |
| **P95 Latency** | 95th percentile response time for OCR requests | < 3s | Prometheus: `http_request_duration_seconds` |
| **Uptime** | Percentage of time the service is available | > 99.5% | Prometheus: `up` metric |
| **Error Rate** | Percentage of requests returning 5xx errors | < 1% | Prometheus: `http_requests_total{status=~"5.."}` |
| **Model Accuracy** | Overall accuracy gauge exposed by the model registry | > 0.90 | Prometheus: `model_accuracy` gauge |
| **Feedback Rating** | Average user rating from the feedback system | > 4.0/5.0 | `app/core/monitoring/feedback.py` |
| **Cache Hit Rate** | Redis cache hit ratio for frequently accessed data | > 80% | Redis: `INFO stats` |
| **GPU Utilization** | Percentage of GPU compute capacity used | 60-90% | `nvidia-smi` / DCGM exporter |

### Feedback Collection

The OmniMedical Suite includes a built-in feedback collection system in `app/core/monitoring/feedback.py`. This system collects user ratings and freeform text feedback, storing entries either in a database (production) or a local JSONL file (standalone/Gradio mode).

**How it works:**

```python
# Import and use the feedback collector
from app.core.monitoring.feedback import FeedbackCollector

collector = FeedbackCollector(storage_path="/app/data/feedback.jsonl")

# Submit feedback
collector.submit(
    rating=4,                          # 1-5 scale
    category="ocr",                    # ocr, translation, ui, performance, bug, feature_request
    message="Great Arabic recognition on prescription!",
    metadata={"document_type": "prescription", "engine": "paddleocr"}
)

# Get aggregated statistics
stats = collector.get_stats()
# {"total": 142, "avg_rating": 4.2, "by_category": {"ocr": {"count": 98, "avg_rating": 4.3}, ...}}

# Get recent entries for review
recent = collector.get_recent(n=50)
```

**Feedback analysis workflow:**

```bash
# Weekly feedback review
docker compose -f docker-compose.prod.yml exec api-server python -c "
from app.core.monitoring.feedback import FeedbackCollector
fc = FeedbackCollector('/app/data/feedback.jsonl')
stats = fc.get_stats()
print(f'Total feedback: {stats[\"total\"]}')
print(f'Average rating: {stats[\"avg_rating\"]}')
for cat, data in stats.get('by_category', {}).items():
    print(f'  {cat}: count={data[\"count\"]}, avg_rating={data[\"avg_rating\"]}')
"

# Export feedback data for ML training
docker compose -f docker-compose.prod.yml exec api-server python -c "
from app.core.monitoring.feedback import FeedbackCollector
fc = FeedbackCollector('/app/data/feedback.jsonl')
import json
with open('/app/data/feedback_export.jsonl', 'w') as f:
    for entry in fc.get_recent(n=500):
        f.write(json.dumps(entry, default=str, ensure_ascii=False) + '\n')
print(f'Exported {min(500, fc.get_stats()[\"total\"])} feedback entries')
"
```

### Improvement Backlog Management

To maintain a structured improvement process:

1. **Weekly metric review** — Run the benchmark suite and compare against historical data:
   ```bash
   python evaluation/benchmark_runner.py --full --output benchmarks/results/weekly_$(date +%Y%m%d).json
   ```

2. **Feedback triage** — Review low-rating feedback entries (< 3 stars) and categorize into:
   - **Bug**: Incorrect behavior that should be fixed immediately
   - **Accuracy issue**: Model output quality below expectations
   - **Feature request**: New capability requested by users
   - **Performance**: Slow response times or resource issues

3. **Backlog prioritization** — Use the following framework:
   - **P0 (Critical)**: CER > 10%, error rate > 5%, data loss — fix within 24 hours
   - **P1 (High)**: CER > 7%, P95 > 5s, user complaints — fix within 1 week
   - **P2 (Medium)**: CER 5-7%, minor UX issues — schedule for next sprint
   - **P3 (Low)**: New features, nice-to-haves — add to roadmap

4. **Quarterly improvement review** — Compare metrics quarter-over-quarter and produce an improvement report:
   ```bash
   # Generate a quarterly comparison
   python -c "
   import json, glob
   results = {}
   for f in sorted(glob.glob('benchmarks/results/*.json')):
       with open(f) as fh:
           data = json.load(fh)
           results[f] = data
   # Compare first and latest
   keys = sorted(results.keys())
   print('Quarterly Improvement Report')
   print(f'Comparing {keys[0]} -> {keys[-1]}')
   for metric in ['cer', 'wer', 'bleu']:
       old = results[keys[0]].get(metric, 0)
       new = results[keys[-1]].get(metric, 0)
       delta = new - old
       direction = 'improved' if (metric == 'bleu' and delta > 0) or (metric in ['cer', 'wer'] and delta < 0) else 'regressed'
       print(f'  {metric.upper()}: {old} -> {new} ({direction})')
   "
   ```

5. **Feedback-driven model improvement** — Use collected feedback to generate training data:
   ```bash
   # Convert high-quality corrections from feedback into training data
   python scripts/train_from_feedback.py \
     --feedback-path data/feedback.jsonl \
     --output data/training_from_feedback.jsonl \
     --min-rating 4
   ```
---

# Appendix: Maintenance Log

> **Last updated:** 2026-07-09 (Phase 7)

## Maintenance Schedule

| Task | Frequency | Last Run | Next Run | Owner |
|------|-----------|----------|----------|-------|
| Check Grafana dashboards | Daily | — | — | ZAI |
| Review error logs | Daily | — | — | ZAI |
| Verify backups | Daily | — | — | ZAI |
| Test database restore | Weekly | — | — | ZAI |
| Test Redis restore | Weekly | — | — | ZAI |
| Review update logs | Weekly | — | — | ZAI |
| Clean up old logs | Weekly | — | — | ZAI |
| Full system test | Monthly | — | — | ZAI |
| Dependency updates | Monthly | — | — | ZAI |
| Security audit | Monthly | — | — | ZAI |
| Performance benchmarking | Monthly | — | — | ZAI |

## Maintenance Commands

### Start Monitoring Stack
```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml up -d
```

### Stop Monitoring Stack
```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml down
```

### Check All Services
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f gradio
```

### Backup Now
```bash
docker-compose exec backup python -m scripts.backup
```

### Check Updates
```bash
docker-compose exec update-checker python -m scripts.update_checker
```

### Health Check
```bash
curl http://localhost:8000/health
```

## Performance Benchmarks

| Metric | Target | Current | Last Measured |
|--------|--------|---------|---------------|
| OCR Processing Time | < 5s | — | — |
| CER (Arabic) | < 5% | — | — |
| WER (Arabic) | < 10% | — | — |
| API Response Time | < 200ms | — | — |
| Memory Usage | < 8GB | — | — |
| CPU Usage | < 70% | — | — |

## Improvement Roadmap

| Improvement | Priority | Status | ETA |
|-------------|----------|--------|-----|
| Add more Grafana dashboards | Medium | Not Started | Q3 2026 |
| Implement alerting (Alertmanager) | High | Not Started | Q3 2026 |
| Add SLO tracking | Medium | Not Started | Q3 2026 |
| Automate dependency updates | Low | Not Started | Q4 2026 |
| Add load testing | Medium | Not Started | Q3 2026 |

## Maintenance History

### 2026-07-09 — Phase 7: Monitoring + Maintenance Setup
- Added Prometheus + Grafana monitoring stack (`infra/monitoring/`)
- Implemented structured JSON logging (`app/core/logging.py`)
- Added health check endpoints (`app/routers/health.py`)
- Added update checker service (`scripts/update_checker.py`)
- Added backup system (`scripts/backup.py`)
- Created RUNBOOK.md and MAINTENANCE_LOG.md
- Updated README.md with monitoring section
