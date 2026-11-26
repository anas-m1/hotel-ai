# hotel-ai local development helpers
# Requires: GNU make, Docker, docker compose v2
# Windows: run via Git Bash or WSL

COMPOSE := docker compose -p docker -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.local-ports.yml
MODEL_PROFILE ?= --profile local-model

.PHONY: setup env infra wait-db create-dbs migrate seed \
        start stop restart logs clean help

# ── Top-level targets ─────────────────────────────────────────────────────────

## setup: Full first-time setup (env → infra → databases → migrations → seed)
setup: env infra wait-db create-dbs migrate seed
	@echo ""
	@echo "Setup complete."
	@echo "Configure the model in infra/docker/llm-gateway.env and booking-assistant.env, then: make start"

## start: Start the booking application and local model (optional modules stay off)
start:
	$(COMPOSE) $(MODEL_PROFILE) up -d

## stop: Stop the core booking application and local model (keeps containers and volumes)
stop:
	$(COMPOSE) --profile local-model --profile telegram stop hotel-ai-telegram-adapter booking-assistant rag-pipeline llm-gateway hotel-inventory booking-ops ollama qdrant redis postgres

## restart: Restart the core application
restart: stop start

## logs: Tail only the Telegram adapter (HTTP credentials are suppressed)
logs:
	$(COMPOSE) --profile telegram logs -f hotel-ai-telegram-adapter

## clean: Stop all services and delete all volumes (destructive!)
clean:
	$(COMPOSE) down -v
	@echo "All containers and volumes removed."

# ── Setup steps (also usable individually) ───────────────────────────────────

## env: Copy .env.example files to .env (skips existing)
env:
	@echo "▶ Env files"
	@for f in infra/docker/*.env.example; do \
		dest=$${f%.example}; \
		if [ ! -f "$$dest" ]; then \
			cp "$$f" "$$dest"; echo "  created  $$(basename $$dest)"; \
		else \
			echo "  exists   $$(basename $$dest)"; \
		fi; \
	done

## infra: Start core infrastructure services only
infra:
	@echo "▶ Starting infrastructure"
	$(COMPOSE) up -d postgres redis qdrant

## wait-db: Block until Postgres is accepting connections
wait-db:
	@echo "▶ Waiting for Postgres"; printf "  "
	@until $(COMPOSE) exec -T postgres pg_isready -U hotel -d postgres -q 2>/dev/null; do \
		printf '.'; sleep 2; \
	done; echo " ready"

## create-dbs: Create booking_ops and langfuse databases (idempotent)
create-dbs:
	@echo "▶ Creating databases"
	@for db in booking_ops langfuse; do \
		exists=$$($(COMPOSE) exec -T postgres psql -U hotel -d postgres -tAc \
			"SELECT 1 FROM pg_database WHERE datname='$$db'" 2>/dev/null | tr -d '[:space:]'); \
		if [ "$$exists" = "1" ]; then \
			echo "  exists   $$db"; \
		else \
			$(COMPOSE) exec -T postgres psql -U hotel -d postgres -c "CREATE DATABASE $$db" > /dev/null; \
			echo "  created  $$db"; \
		fi; \
	done

## migrate: Run all database migrations
migrate:
	@echo "▶ Running migrations"
	$(COMPOSE) --profile migrate run --rm migrate-hotel-inventory
	$(COMPOSE) --profile migrate run --rm migrate-booking-ops

## seed: Load seed data into hotel_inventory (idempotent)
seed:
	@echo "▶ Seeding data"
	@count=$$($(COMPOSE) exec -T postgres psql -U hotel -d hotel_inventory -tAc \
		"SELECT COUNT(*) FROM hotels" 2>/dev/null | tr -d '[:space:]'); \
	if [ "$${count:-0}" -gt 0 ]; then \
		echo "  skipped  hotels table already has $$count rows"; \
	else \
		$(COMPOSE) exec -T postgres psql -U hotel -d hotel_inventory < infra/docker/seed.sql; \
		echo "  seeded"; \
	fi

## help: Show this help
help:
	@grep -E '^## ' Makefile | sed 's/## /  make /'

.PHONY: demo observability mcp test test-go test-agent eval-agent eval-retrieval

## demo: Build/start the core application, local model, and Telegram adapter
demo:
	$(COMPOSE) $(MODEL_PROFILE) --profile telegram up -d --build

## observability: Start the optional Langfuse stack
observability:
	$(COMPOSE) --profile observability up -d clickhouse minio langfuse-redis langfuse-worker langfuse-web

## mcp: Start the optional MCP adapters and core application
mcp:
	$(COMPOSE) $(MODEL_PROFILE) --profile mcp up -d

## test: Run deterministic Go and booking-agent tests
test: test-go test-agent test-evals test-gateway

## test-go: Test both Go modules; package tests remain beside their code
test-go:
	go test ./services/hotel-inventory/... ./services/booking-ops/...

## test-agent: Run service-local Python tests without real model/backend calls
test-agent:
	uv run --locked --project ai/booking-assistant pytest ai/booking-assistant/tests/ -v

## eval-agent: Run live model/tool-selection evals without replacing saved baselines
eval-agent:
	python3 evals/agent/evaluate_agent.py --output /tmp/hotel-agent-eval.json

## eval-retrieval: Run live retrieval evals without replacing saved baselines
eval-retrieval:
	python3 evals/retrieval/evaluate_retrieval.py --output /tmp/hotel-retrieval-eval.json

.PHONY: test-backend-isolated
## test-backend-isolated: Verify backend lifecycle against temporary host PostgreSQL
test-backend-isolated:
	python3 scripts/test-backend-isolated.py

.PHONY: test-evals test-gateway
## test-evals: Test eval scoring and comparison without model requests
test-evals:
	uv run --locked --project ai/booking-assistant python -m unittest discover -s evals/tests -v

## test-gateway: Test provider routing with mocked completions
test-gateway:
	uv run --locked --project ai/llm-gateway pytest ai/llm-gateway/tests/ -v
