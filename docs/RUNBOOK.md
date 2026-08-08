# RUNBOOK: Operations Guide for omni-medical-suite

> **Last updated:** 2026-07-09 (Phase 7)
> **Audience:** DevOps engineers, on-call responders, and project maintainers
> **Repository:** https://github.com/DrAbdulmalek/omni-medical-suite

---

## Emergency Procedures

### 1. Service Down

1. **Check health endpoints:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/health/liveness
   curl http://localhost:8000/health/readiness
   ```

2. **Check logs:**
   ```bash
   # Docker logs
   docker-compose logs api
   docker-compose logs gradio

   # Application logs
   tail -f logs/audit.log
   tail -f logs/errors.log
   ```

3. **Restart services:**
   ```bash
   docker-compose restart api
   docker-compose restart gradio
   ```

### 2. Database Issues

1. **Check connection:**
   ```bash
   docker-compose exec postgres psql -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1"
   ```

2. **Restore from backup:**
   ```bash
   # List backups
   ls -la backups/database/

   # Restore
   docker-compose exec -T postgres psql -U ${DB_USER} -d ${DB_NAME} < backups/database/omni_medical_20260709_120000.sql
   ```

### 3. Redis Issues

1. **Check connection:**
   ```bash
   docker-compose exec redis redis-cli ping
   ```

2. **Restore from backup:**
   ```bash
   docker-compose exec redis redis-cli --rdb backups/redis/redis_20260709_120000.rdb
   ```

---

## Monitoring

### Access Dashboards

- **Grafana:** http://localhost:3000 (admin / `${GRAFANA_ADMIN_PASSWORD}`)
- **Prometheus:** http://localhost:9090
- **Node Exporter:** http://localhost:9100

### Start Monitoring Stack

```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml up -d
```

### Stop Monitoring Stack

```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml down
```

### Key Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `ocr_requests_total` | Total OCR requests | — |
| `ocr_processing_time_seconds` | Processing time | < 5s |
| `ocr_cer` | Character Error Rate | < 5% |
| `ocr_wer` | Word Error Rate | < 10% |
| `database_query_time` | DB query time | < 100ms |
| `redis_response_time` | Redis response time | < 10ms |

---

## Maintenance

### Daily Tasks
- [ ] Check Grafana dashboards
- [ ] Review error logs (`tail -100 logs/errors.log`)
- [ ] Verify backups completed

### Weekly Tasks
- [ ] Test database restore
- [ ] Test Redis restore
- [ ] Review update checker logs
- [ ] Clean up old logs

### Monthly Tasks
- [ ] Full system test
- [ ] Dependency updates (`python -m scripts.update_dependencies`)
- [ ] Security audit
- [ ] Performance benchmarking

---

## Deployment

### Update Procedure

1. **Check for updates:**
   ```bash
   python -m scripts.update_checker
   ```

2. **Deploy update:**
   ```bash
   git pull origin main
   docker-compose build
   docker-compose up -d
   ```

3. **Verify deployment:**
   ```bash
   curl http://localhost:8000/health
   ```

### Rollback Procedure

1. **Revert to previous commit:**
   ```bash
   git checkout <previous-commit>
   ```

2. **Rebuild and restart:**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

---

## Troubleshooting

### Common Issues

#### 1. OCR Processing Slow
- **Cause:** Large files or high load
- **Solution:** Increase worker count, optimize batch size

#### 2. Memory Issues
- **Cause:** PaddleOCR models loading
- **Solution:** Use smaller models, increase Docker memory limit

#### 3. Connection Timeouts
- **Cause:** Network issues or service down
- **Solution:** Check health endpoints, restart services

#### 4. Authentication Failures
- **Cause:** Expired tokens or incorrect credentials
- **Solution:** Update tokens in .env file, restart services

---

## Support

### Contact Information
- **Primary:** DrAbdulmalek
- **Repository:** https://github.com/DrAbdulmalek/omni-medical-suite
- **Space:** https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr

### Escalation Path
1. Check RUNBOOK
2. Check logs
3. Check monitoring dashboards
4. Contact primary support