.PHONY: help install test test-core core docker-build docker-up docker-down build lint clean

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install all dependencies
	cd packages/core && pip install -r requirements.txt
	bun install

# Testing
test: ## Run all tests
	cd packages/core && python -m pytest test_core.py -v --tb=short
	bun run lint

test-core: ## Run Python core tests only
	cd packages/core && python -m pytest test_core.py -v --tb=short

# Python Core API
core: ## Start Python Core API server
	cd packages/core && python api_server.py --port 8000

core-reload: ## Start Python Core with auto-reload
	cd packages/core && python api_server.py --port 8000 --reload

# Docker
docker-build: ## Build Docker image
	docker-compose build

docker-up: ## Start services with Docker
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

# Web App
dev: ## Start Next.js dev server
	bun run dev

build: ## Build Next.js for production
	bun run build

lint: ## Lint TypeScript
	bun run lint

# Database
db-push: ## Push Prisma schema to database
	bun run db:push

db-studio: ## Open Prisma Studio
	bun run db:studio

# Clean
clean: ## Clean temporary files
	rm -rf .next
	rm -rf packages/core/__pycache__
	rm -rf packages/core/*.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
