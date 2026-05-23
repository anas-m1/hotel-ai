## Go Stack (`services/`)

| Layer | Technology |
|---|---|
| Language | Go 1.23 |
| Router | Chi |
| DB layer | sqlc + pgx (PostgreSQL 16) |
| Messaging | confluent-kafka-go |
| Testing | testify |
| Linting | golangci-lint |

### Go Commands

- **Build all services:** `go build ./...`
- **Test all:** `go test ./...`
- **Test single service:** `go test ./services/booking-ops/...`
- **Lint:** `golangci-lint run`
- **Vet:** `go vet ./...`
- **Run a service:** `go run services/booking-ops/cmd/server/main.go`
- **Generate SQL:** `sqlc generate`
- **Sync workspace:** `go work sync`

---

## Python Stack (`ai/`, `mcp/`)

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package manager | uv |
| AI API framework | FastAPI |
| Agent framework | LangGraph |
| LLM gateway | LiteLLM |
| Embeddings | text-embedding-3-large via LiteLLM |
| Vector DB | Qdrant |
| Observability | OpenTelemetry + Langfuse |
| Testing | pytest + anyio |
| Linting | ruff |

### Python Commands

- **Dev (from service dir):** `uv run uvicorn src.main:app --reload`
- **Test:** `uv run pytest`
- **Lint:** `uv run ruff check .`
- **Format:** `uv run ruff format .`
- **Type check:** `uv run mypy .`

---

## Shared Infrastructure

| Component | Purpose |
|---|---|
| PostgreSQL 16 | Primary relational DB for all Go services |
| Apache Kafka | Event bus between Go services and Python AI services |
| Redis | Agent memory, session state, rate limiting |
| Qdrant | Vector DB for dense + sparse hybrid search, RAG, and semantic agent memory |
| AWS EKS + Terraform | Production deployment |

### Docker / Infra Commands

- **Start local stack:** `docker compose -f infra/docker/docker-compose.yml up -d`
- **Stop stack:** `docker compose -f infra/docker/docker-compose.yml down`
- **DB migrations:** `cd services/{name} && sqlc generate && go run cmd/migrate/main.go`
- **Terraform plan:** `cd infra/terraform && terraform plan`
