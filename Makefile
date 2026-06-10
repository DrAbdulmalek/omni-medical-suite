# =============================================================================
# OmniMedical Suite — Makefile
# =============================================================================
# Primary targets for local dev, production Docker, testing, and monitoring.
# Run `make` or `make help` to see all available targets.
# =============================================================================

.PHONY: dev prod test lint monitoring check secrets clean help

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

# ===========================================================================
# Development
# ===========================================================================

## dev - Start development environment (API + Redis + PostgreSQL)
dev:
	docker-compose -f docker-compose.dev.yml up --build

# ===========================================================================
# Production
# ===========================================================================

## prod - Start production environment in detached mode
prod:
	docker-compose -f docker-compose.prod.yml up -d --build

# ===========================================================================
# Testing & Quality
# ===========================================================================

## test - Run all tests with verbose output
test:
	pytest tests/ -v

## lint - Run ruff (linting) and mypy (type checking)
lint:
	ruff check . && mypy packages/

# ===========================================================================
# Monitoring
# ===========================================================================

## monitoring - Deploy Prometheus + Grafana monitoring stack
monitoring:
	bash scripts/deploy_monitoring.sh

# ===========================================================================
# Deployment Helpers
# ===========================================================================

## check - Run pre-deployment readiness checks
check:
	bash scripts/pre-deploy-check.sh

## secrets - Generate secure production secrets
secrets:
	bash scripts/generate-secrets.sh

# ===========================================================================
# Cleanup
# ===========================================================================

## clean - Stop all containers, remove volumes, and clean build artifacts
clean:
	docker-compose down -v
	rm -rf __pycache__ .pytest_cache

# ===========================================================================
# Help
# ===========================================================================

## help - Show this help message
help:
	@echo ""
	@echo "OmniMedical Suite — Available Commands"
	@echo "========================================"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sort | \
		sed 's/^## //' | \
		awk -F' - ' '{printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"
	@echo ""