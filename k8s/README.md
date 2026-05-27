# Kubernetes Deployment

## Quick Start
kubectl apply -k k8s/

## Prerequisites
- Kubernetes 1.28+
- kubectl
- Ingress NGINX Controller
- cert-manager (for TLS)

## Services
| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI backend |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache & Celery broker |
| Qdrant | 6333 | Vector database |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboards |
| Tempo | 3200 | Tracing |

## Scaling
The API deployment uses HPA with 2-10 replicas based on CPU/memory.
