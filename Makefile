# ============================================================================
# OmniMedical Suite — Makefile
# ============================================================================
# Primary targets for local dev, production Docker, and common operations.
# Run `make` or `make help` to see all available targets.
# ============================================================================

.PHONY: dev prod prod-down install build test lint secrets check logs clean help

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

# ===========================================================================
# Development
# ===========================================================================

## dev - Start development Docker Compose (web + redis, SQLite)
dev:
	docker compose -f docker-compose.dev.yml up --build

# ===========================================================================
# Production
# ===========================================================================

## prod - Start production Docker Compose (web + postgres + redis) in background
prod:
	docker compose -f docker-compose.prod.yml up -d --build

## prod-down - Stop production Docker Compose and remove containers
prod-down:
	docker compose -f docker-compose.prod.yml down

# ===========================================================================
# Local Development (without Docker)
# ===========================================================================

## install - Install dependencies and initialize database
install:
	npm install
	npm run prisma:generate
	npm run prisma:migrate

## build - Build the full project
build:
	npm run build

## test - Run all tests
test:
	npm run test

## lint - Run linting across all packages
lint:
	npm run lint

# ===========================================================================
# Deployment Helpers
# ===========================================================================

## secrets - Generate secure production secrets
secrets:
	bash scripts/generate-secrets.sh

## check - Run pre-deployment readiness checks
check:
	bash scripts/pre-deploy-check.sh

## logs - Tail production Docker Compose logs (last 100 lines)
logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

# ===========================================================================
# Cleanup
# ===========================================================================

## clean - Remove all containers, volumes, node_modules, and build artifacts
clean:
	docker compose -f docker-compose.dev.yml down -v
	docker compose -f docker-compose.prod.yml down -v
	rm -rf node_modules .next

# ===========================================================================
# Help
# ===========================================================================

## help - Show this help message
help:
	@echo ""
	@echo "OmniMedical Suite - Available Commands"
	@echo "======================================"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sort | \
		sed 's/^## //' | \
		awk -F' - ' '{printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
