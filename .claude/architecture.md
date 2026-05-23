## Repository Layout

```
hotel-ai/
├── go.work                              # Go workspace linking all service modules
├── services/                            # Go microservices — core booking domain
│   ├── booking-ops/                     # Reservation lifecycle, CQRS, event sourcing
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── domain/
│   │   │   ├── handler/
│   │   │   ├── repository/
│   │   │   └── kafka/
│   │   └── go.mod
│   ├── hotel-inventory/                 # Hotel/room CRUD, availability
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── domain/
│   │   │   ├── handler/
│   │   │   └── repository/
│   │   └── go.mod
│   ├── pricing-engine/                  # Dynamic pricing, yield management
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── domain/
│   │   │   ├── handler/
│   │   │   └── repository/
│   │   └── go.mod
│   ├── search/                          # NL query → SQL/filter translation
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── handler/
│   │   │   └── repository/
│   │   └── go.mod
│   ├── analytics/                       # Occupancy reports, revenue forecasts
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── handler/
│   │   │   └── repository/
│   │   └── go.mod
│   └── fraud-detection/                 # Risk scoring, anomaly detection (Phase 5+)
│       ├── cmd/
│       │   └── server/
│       │       └── main.go
│       ├── internal/
│       │   ├── domain/
│       │   ├── handler/
│       │   └── kafka/
│       └── go.mod
├── ai/                                  # Python AI services
│   ├── llm-gateway/                     # LiteLLM gateway, cost tracking, prompt versioning
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── rag-pipeline/                    # Qdrant ingestion, hybrid search, re-ranking
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── booking-assistant/               # LangGraph ReAct agent, HITL (Phase 4+)
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── multi-agent/                     # Supervisor + specialist agents, Kafka bus (Phase 5+)
│   │   ├── src/
│   │   └── pyproject.toml
│   └── knowledge-graph/                 # GraphRAG, Neo4j, Self-RAG (Phase 8+)
│       ├── src/
│       └── pyproject.toml
├── mcp/                                 # Python MCP servers — facades over Go service APIs
│   ├── hotel-inventory/
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── booking-ops/
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── pricing-engine/
│   │   ├── src/
│   │   └── pyproject.toml
│   ├── analytics/
│   │   ├── src/
│   │   └── pyproject.toml
│   └── external-integrations/           # Stripe, SendGrid, Google Maps wrappers
│       ├── src/
│       └── pyproject.toml
├── shared/                              # Cross-language contracts
│   ├── events/                          # Kafka event schemas (JSON/Avro)
│   └── openapi/                         # OpenAPI specs generated from Go services
├── infra/
│   ├── docker/
│   │   └── docker-compose.yml
│   └── terraform/
└── phases/                              # Phase-by-phase learning docs & eval harnesses
    ├── 01_foundation/
    ├── 02_llm_integration/
    ├── 03_rag/
    ├── 04_agentic/
    ├── 05_multi_agent/
    ├── 06_mcp/
    ├── 07_aiops/
    ├── 08_knowledge_graph/
    └── 09_capstone/
```

## Key Patterns

- **Go services own all relational data** — direct PostgreSQL access via sqlc/pgx; no other service touches the DB directly
- **MCP servers are thin facades** — they call Go service HTTP APIs; they never connect to PostgreSQL or Kafka directly
- **Python AI services are event-driven consumers** — they subscribe to Kafka topics published by Go services; they never call Go services synchronously in the hot path
- **Shared contracts live in `shared/`** — `shared/events/` schemas are the only contract between Go producers and Python consumers; `shared/openapi/` specs are consumed by MCP servers
- **Qdrant handles all vector retrieval** — both dense (text-embedding-3-large) and sparse (SPLADE) vectors stored in Qdrant; hybrid search uses Qdrant's native RRF fusion. No Elasticsearch.
- **Each Go service has its own `go.mod`** — the root `go.work` links them; shared Go utilities go in a future `shared/go/` module
- **Each Python service is isolated** — its own `pyproject.toml`; no shared Python package between services (use Kafka/HTTP for integration)
- **Every AI feature has an eval harness** — in the phase's directory under `phases/{N}/eval/`

## Conventions

### Go
- Standard project layout: `cmd/server/main.go` entry point, all logic in `internal/`
- HTTP handlers in `internal/handler/`, data access in `internal/repository/`, domain types in `internal/domain/`
- All errors returned, not panicked; wrap with `fmt.Errorf("...: %w", err)`
- New Go service → add its module to `go.work`

### Python
- Strict typing: `mypy --strict`, Pydantic v2 for all schemas
- All LLM calls go through `ai/llm-gateway` — no direct OpenAI/Anthropic SDK calls from agents or MCP servers
- New Python service: `cd ai/{name} && uv init && uv add fastapi langchain-core ...`

## Do NOT

- Give any Python service direct database access — route through Go service APIs
- Give MCP servers direct Kafka or DB access — facades only
- Commit `.env` files, API keys, or secrets
- Call LLM providers directly — always through the LiteLLM gateway
- Put phase-specific implementation in `services/` or `ai/` — keep those clean; experiments go in `phases/`
