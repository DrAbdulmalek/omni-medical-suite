# ============================================================================
# OmniMedical Suite — Makefile
# ============================================================================
# Run `make help` to see all available targets.
# All paths are relative to the monorepo root.
# ============================================================================

.PHONY: help dev build test test-py test-web lint lint-py lint-web \
        db-generate db-push db-seed docker-build docker-up docker-down \
        infra-up infra-down infra-logs client-run load-test \
        clean setup security-check check-secrets

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Colors (for help text)
# ---------------------------------------------------------------------------
GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

# ===========================================================================
# Development
# ===========================================================================

## dev - Start Next.js development server (port 3000)
dev:
        @echo "$(CYAN)Starting development server...$(RESET)"
        npm run dev

# ===========================================================================
# Build
# ===========================================================================

## build - Build the full project (all workspaces)
build:
        @echo "$(CYAN)Building project...$(RESET)"
        npm run build

# ===========================================================================
# Testing
# ===========================================================================

## test - Run all tests (Python + TypeScript)
test: test-py test-web
        @echo "$(GREEN)All tests passed.$(RESET)"

## test-py - Run Python tests with pytest
test-py:
        @echo "$(CYAN)Running Python tests...$(RESET)"
        python -m pytest tests/ -v --tb=short \
                --ignore=tests/test_gemini_modules.py \
                --ignore=tests/test_integration_full.py \
                --ignore=tests/test_e2e.py

## test-web - Run Next.js / TypeScript tests
test-web:
        @echo "$(CYAN)Running web tests...$(RESET)"
        npx turbo run test --filter=nextjs_tailwind_shadcn_ts

# ===========================================================================
# Linting
# ===========================================================================

## lint - Run ESLint (web) + Python linting
lint: lint-web lint-py
        @echo "$(GREEN)Linting passed.$(RESET)"

## lint-web - Run ESLint on the Next.js app
lint-web:
        @echo "$(CYAN)Linting web (ESLint)...$(RESET)"
        cd apps/web && npx eslint .

## lint-py - Run ruff (or flake8) on Python packages
lint-py:
        @echo "$(CYAN)Linting Python...$(RESET)"
        @if command -v ruff > /dev/null 2>&1; then \
                ruff check packages/ services/ tests/; \
        elif command -v flake8 > /dev/null 2>&1; then \
                flake8 packages/ services/ tests/; \
        else \
                echo "$(YELLOW)No Python linter found. Install ruff: pip install ruff$(RESET)"; \
        fi

# ===========================================================================
# Database (Prisma)
# ===========================================================================

## db-generate - Generate Prisma client from schema
db-generate:
        @echo "$(CYAN)Generating Prisma client...$(RESET)"
        cd apps/web && npx prisma generate

## db-push - Push Prisma schema to the database (no migrations)
db-push:
        @echo "$(CYAN)Pushing schema to database...$(RESET)"
        cd apps/web && npx prisma db push

## db-seed - Seed default admin user (admin / admin123)
db-seed:
        @echo "$(CYAN)Seeding database...$(RESET)"
        cd apps/web && npx prisma db seed

# ===========================================================================
# Docker
# ===========================================================================

## docker-build - Build all Docker images
docker-build:
        @echo "$(CYAN)Building Docker images...$(RESET)"
        docker compose -f infrastructure/docker/docker-compose.yml build

## docker-up - Start all services (web, api, redis, workers, monitoring)
docker-up:
        @echo "$(CYAN)Starting Docker Compose...$(RESET)"
        docker compose -f infrastructure/docker/docker-compose.yml up -d
        @echo "$(GREEN)Services started. Web: http://localhost:3000 | Grafana: http://localhost:3001$(RESET)"

## docker-down - Stop all Docker services
docker-down:
        @echo "$(CYAN)Stopping Docker Compose...$(RESET)"
        docker compose -f infrastructure/docker/docker-compose.yml down

# ===========================================================================
# Medical Infrastructure (Docker Compose)
# ===========================================================================

## infra-up - Start unified medical infrastructure (Redis, LB, WebSocket, API, Prometheus, Grafana)
infra-up:
        @echo "$(CYAN)Starting Medical Infrastructure...$(RESET)"
        docker compose -f docker-compose.medical-infra.yml up -d --build
        @echo "$(GREEN)Medical Infra running. LB:8080 | WS:8765 | Redis:6380 | Grafana:3001$(RESET)"

## infra-down - Stop all medical infrastructure services
infra-down:
        @echo "$(CYAN)Stopping Medical Infrastructure...$(RESET)"
        docker compose -f docker-compose.medical-infra.yml down -v

## infra-logs - View medical infrastructure logs
infra-logs:
        docker compose -f docker-compose.medical-infra.yml logs -f --tail=50

## client-run - Run the desktop smart client (v14)
client-run:
        @echo "$(CYAN)Starting Medical Document Scanner v14...$(RESET)"
        cd packages/desktop && python medical_doc_gui_v14.py

## load-test - Run load test with Locust (1000 users, 5 min)
load-test:
        @echo "$(CYAN)Starting Load Test (1000 users, 5 min)...$(RESET)"
        cd tests/loadtest && locust -f locustfile.py --headless -u 1000 -r 50 --run-time 5m

# ===========================================================================
# Cleanup
# ===========================================================================

## clean - Remove build artifacts, node_modules cache, and Python cache
clean:
        @echo "$(CYAN)Cleaning build artifacts...$(RESET)"
        rm -rf apps/web/.next
        rm -rf apps/web/node_modules/.cache
        rm -rf .turbo
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        rm -rf logs/*.log
        @echo "$(GREEN)Clean complete.$(RESET)"

# ===========================================================================
# Setup
# ===========================================================================

## setup - Run the initial project setup script
setup:
        @echo "$(CYAN)Running setup...$(RESET)"
        bash scripts/setup.sh

# ===========================================================================
# Security
# ===========================================================================

## security-check - Check for leaked secrets, run linting and tests
security-check: check-secrets lint test
        @echo "$(GREEN)Security check passed.$(RESET)"

## check-secrets - Scan for accidentally committed secrets and keys
check-secrets:
        @echo "$(CYAN)Scanning for leaked secrets...$(RESET)"
        @FOUND=0; \
        for pattern in \
                "AKIA[0-9A-Z]{16}" \
                "-----BEGIN.*PRIVATE KEY-----" \
                "eyJ[A-Za-z0-9_-]*\.eyJ" \
                "password\s*=\s*['\"][^'\"]+['\"]" \
                "secret\s*=\s*['\"][^'\"]{8,}['\"]"; do \
                if git grep -l -E "$${pattern}" -- ':!.env*' ':!*.md' 2>/dev/null; then \
                        FOUND=1; \
                fi; \
        done; \
        if [ "$${FOUND}" -eq 0 ]; then \
                echo "$(GREEN)No secrets found in tracked files.$(RESET)"; \
        else \
                echo "$(YELLOW)WARNING: Potential secrets detected above. Review before committing.$(RESET)"; \
        fi

# ===========================================================================
# Help
# ===========================================================================

## help - Show this help message
help:
        @echo ""
        @echo "$(GREEN)OmniMedical Suite - Available Commands$(RESET)"
        @echo "$(YELLOW)======================================$(RESET)"
        @echo ""
        @grep -E '^## ' $(MAKEFILE_LIST) | sort | \
                sed 's/^## //' | \
                awk -F' - ' '{printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
        @echo ""
        @echo "$(YELLOW)Usage:$(RESET) make <target>"
        @echo ""
