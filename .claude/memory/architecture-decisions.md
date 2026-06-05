---
name: architecture-decisions
description: Key architectural and tooling decisions, the discussions that led to them, and the tradeoffs accepted
metadata:
  type: project
---

## How to read this file

Each decision records: the question raised, the options considered, what was chosen, and why. These are decisions that would not be obvious from reading the code alone.

---

## Language split: Go for services, Python for AI

**Question:** What language for the microservices?

**Decision:** Polyglot monorepo — Go for all core booking domain services (hotel-inventory, booking-ops, pricing-engine, search, analytics, fraud-detection); Python for all AI services (LangGraph agents, RAG pipeline, LiteLLM gateway) and MCP servers.

**Why Go for domain services:**
- Compilation catches errors the AI domain (Python) can't afford to have at runtime in core booking logic
- pgx/sqlc gives typed, performant DB access with no reflection overhead
- Existing user expertise (5 yrs backend)
- Low memory footprint matters for K8s pod sizing

**Why Python for AI:**
- Dominant AI/ML ecosystem — LangGraph, LiteLLM, Qdrant client, HuggingFace, RAGAS all Python-first
- Async-native (asyncio) matches LLM streaming patterns
- Would be fighting the ecosystem in Go for AI work

**Tradeoff accepted:** Two build systems, two package managers (go mod + uv), two lint setups. Accepted because the AI/domain boundary is clean and the integration path is Kafka (async) and HTTP (MCP facades), not shared libraries.

---

## ORM vs sqlc + pgx

**Question:** How to talk to PostgreSQL from Go services?

**Decision:** sqlc (code generator from SQL) + pgx/v5 (PostgreSQL driver). No ORM.

**Alternatives considered:** GORM, Bun, Ent.

**Why sqlc + pgx:**
- SQL is the interview topic — writing real SQL is better learning than ORM magic
- sqlc generates type-safe Go from SQL at build time; runtime is just typed function calls
- pgx/v5 is the fastest PostgreSQL driver for Go; supports pgxpool for connection pooling
- Full control over query shape — important for event sourcing and CQRS read models
- No N+1 foot-guns from lazy loading

**Why not GORM:**
- Hides SQL; bad for learning and bad for debugging production query plans
- GORM's `interface{}` surface is not type-safe
- Generates suboptimal queries for aggregate patterns

**Tradeoff accepted:** Must run `sqlc generate` as a build step; generated code is committed or regenerated in CI. No dynamic queries — everything must be a named SQL query. Acceptable because the query surface is bounded.

---

## QueryExecModeSimpleProtocol for NUMERIC columns

**Question:** pgx/v5 maps PostgreSQL NUMERIC to `pgtype.Numeric` by default. The Go domain model wants `string` (to avoid floating-point precision loss). How to reconcile?

**Decision:** Set `cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol` on the connection pool. This makes pgx use PostgreSQL's simple query protocol, which sends/receives all values as text. NUMERIC comes back as the exact text representation ("123.45"), which maps cleanly to Go `string`.

**Why not pgtype.Numeric:**
- `pgtype.Numeric` requires explicit conversion everywhere; verbose
- Domain model should own the money representation (string keeps exact decimals, no float rounding)
- Simple protocol is acceptable for a learning/dev-stage project; extended protocol would be added if benchmarks showed it mattered

**sqlc config to match:** Added overrides in `sqlc.yaml`:
```yaml
overrides:
  - db_type: "uuid"
    go_type: { import: "github.com/google/uuid", type: "UUID" }
  - db_type: "pg_catalog.numeric"
    nullable: false
    go_type: "string"
  - db_type: "pg_catalog.numeric"
    nullable: true
    go_type: { spec: "*string" }
```

**Tradeoff accepted:** Simple protocol has higher per-query overhead than extended protocol (no server-side prepared statement reuse). Acceptable for now; revisit if latency profiling shows it matters.

---

## HTTP router: Chi

**Question:** Which Go HTTP router?

**Decision:** Chi (`github.com/go-chi/chi/v5`).

**Alternatives considered:** Gin, Echo, stdlib `net/http`.

**Why Chi:**
- Stdlib-compatible (`http.Handler`) — no framework lock-in; Chi middleware composes with anything
- Idiomatic Go: no magic, no reflection, no custom context
- `chi.URLParam` for path params is clean; middleware stack (`RequestID`, `RealIP`, `Logger`, `Recoverer`) covers the basics
- Lighter than Gin/Echo

**Tradeoff accepted:** Less built-in validation than Gin; manual request parsing. Accepted because validation is a domain concern, not a router concern.

---

## Cross-service data references without foreign keys

**Question:** `booking-ops` references `hotel_code` (owned by hotel-inventory) and `room_id` (owned by hotel-inventory). How to enforce referential integrity across service boundaries?

**Decision:** Store `hotel_code TEXT` and `room_id UUID` in the bookings table as plain columns with no database-level FK. Integrity is enforced at the application layer (booking-ops calls hotel-inventory API to verify before creating a booking).

**Why:**
- Cross-service FKs would couple the databases; violates microservice autonomy
- Each service owns its own schema — no cross-DB joins
- Standard microservices pattern: eventual consistency + application-layer validation

**Tradeoff accepted:** If hotel-inventory data is deleted (hotel removed), orphaned booking records can exist. Mitigation: soft-delete hotels (never hard-delete); booking-ops checks hotel status before allowing new bookings.

---

## Event sourcing for bookings

**Question:** How to model booking state changes?

**Decision:** Dual-write: `bookings` table is the current state (mutable, queryable), `booking_events` is the immutable append-only event log. Every state transition writes to both.

**Schema:**
- `bookings`: source of truth for current status, with `version` column for optimistic locking
- `booking_events`: `(booking_id, event_type, payload JSONB, triggered_by, created_at)` — never updated or deleted

**Why:**
- Phase 4 agentic work needs to replay/audit what agents did (`triggered_by = 'agent'` partial index)
- Supports CQRS: read model can be rebuilt from events
- Interview topic: event sourcing vs CRUD trade-offs

**Tradeoff accepted:** Two writes per state change (in a transaction); slightly higher write latency. Acceptable — bookings are low-volume operations vs. reads.

**Future Phase 7 addition:** CDC (Debezium → Kafka → ClickHouse) will be added for analytics/reporting on top of the existing `booking_events` table. The two serve different consumers: `booking_events` carries semantic context for agents (`triggered_by`, structured payload); the columnar store carries raw state changes for aggregate analytics. They are complementary, not alternatives.

---

## Optimistic locking for bookings

**Question:** How to handle concurrent booking status updates (e.g., two agents trying to confirm the same booking)?

**Decision:** `version INT` column on `bookings`. Every update increments version and checks that the supplied version matches:
```sql
UPDATE bookings SET status = $3, version = version + 1, updated_at = NOW()
WHERE id = $1 AND version = $2
RETURNING *;
```
If version mismatch: query returns no rows → `ErrVersionConflict` → caller retries.

**Why not row-level locking (`SELECT FOR UPDATE`):**
- Pessimistic locking holds a DB lock for the duration of the transaction; bad for agent-driven flows with external API calls inside the transaction
- Optimistic locking has zero contention in the happy path (vast majority of cases)

**Tradeoff accepted:** Retry logic required in callers. Accepted — this is standard practice and the booking domain has low enough concurrency that conflicts are rare.

**Why not pessimistic locking specifically for agentic flows:** In Phase 4, the booking agent makes external calls (payment gateway, pricing service) between reading and updating a booking. `SELECT FOR UPDATE` would hold the DB row lock for the full duration of those external calls (200ms–2s+), causing lock queuing under concurrent agent load and leaving locks dangling on agent crash. Optimistic locking holds the lock for microseconds (just the UPDATE statement). The version check is atomic. Conflicts trigger a clean retry with no lock held.

**When pessimistic would be right instead:** High-contention inventory (last-seat-grab). Even then, prefer a Redis atomic decrement on an inventory counter over a Postgres row lock.

---

## Agent framework: LangGraph over LangChain chains

**Question:** LangChain or LangGraph for the booking assistant agent (Phase 4)?

**Decision:** LangGraph.

**Why:**
- LangGraph supports stateful directed graphs with cycles — required for ReAct loops, self-correction, and Plan-and-Execute
- LangChain linear chains cannot easily model: retries, branching on tool output, interrupt-and-resume (human-in-the-loop)
- LangGraph is the production-grade successor; LangChain chains are increasingly legacy

**Tradeoff accepted:** LangGraph has a steeper learning curve than simple LangChain chains. Accepted — the learning is the point.

---

## LLM gateway: LiteLLM

**Question:** How do agents and RAG pipeline call LLMs?

**Decision:** All LLM calls route through a self-hosted LiteLLM gateway (`ai/llm-gateway`). No service calls OpenAI/Anthropic SDKs directly.

**Why:**
- Unified interface: swap models without touching calling code
- Cost tracking and rate limiting in one place
- Fallback routing: if primary model fails, route to backup
- Prompt caching configuration centralized

**Architecture rule recorded in `architecture.md`:** "All LLM calls go through `ai/llm-gateway` — no direct OpenAI/Anthropic SDK calls from agents or MCP servers."

**Tradeoff accepted:** Extra network hop per LLM call; adds latency. Acceptable — LLM latency dominates anyway (hundreds of ms to seconds).

---

## Vector DB: Qdrant (not pgvector, not Pinecone)

**Question:** Where to store embeddings for hotel content RAG?

**Decision:** Self-hosted Qdrant on K8s.

**Alternatives considered:** pgvector (PostgreSQL extension), Pinecone (managed), Weaviate.

**Why Qdrant:**
- Native hybrid search (dense + sparse vectors, RRF fusion) — critical for hotel search where keyword matching (hotel name, city) and semantic search both matter
- Self-hostable: full control, no external API costs, runs on EKS
- Production ops story: K8s deployment, snapshots, collections management
- Better HNSW tuning knobs than pgvector

**Why not pgvector:**
- pgvector is fine for simple use cases; poor at hybrid search
- Adding vector workload to the OLTP database creates resource contention
- IVFFlat index in pgvector is slower than Qdrant's HNSW at scale

**Why not Pinecone:**
- Managed = no ops learning; the ops story is part of Phase 7 AIOps work
- Cost at scale is higher than self-hosted

**Note on Elasticsearch:** The original plan included Elasticsearch for sparse BM25. This was removed in the final architecture — Qdrant's native sparse vector support (SPLADE) handles BM25-style retrieval without a separate Elasticsearch cluster. Recorded in `architecture.md`.

---

## MCP servers as thin facades

**Question:** Should MCP servers have direct database access or call Go service APIs?

**Decision:** MCP servers are thin HTTP facades — they call Go service REST APIs only. No direct DB, no Kafka.

**Why:**
- MCP servers are Python; giving them DB access would mean duplicating Go's data access logic in Python
- Go services are the single source of truth for domain data; MCP servers are just a translation layer (HTTP → MCP tool protocol)
- Keeps the MCP server stateless and easily replaceable

**Architecture rule recorded in `architecture.md`:** "MCP servers are thin facades — they call Go service HTTP APIs; they never connect to PostgreSQL or Kafka directly."

---

## Python AI services: Kafka consumers, not sync callers

**Question:** How should Python AI services get data from Go services?

**Decision:** Python AI services subscribe to Kafka topics published by Go services. No synchronous HTTP calls from Python AI to Go services in the hot path.

**Why:**
- Async event consumption decouples AI processing latency from booking transaction latency
- Go services don't need to know AI services exist
- Kafka gives replay, backpressure, and at-least-once delivery for free
- Exception: MCP servers call Go APIs (but that's a tooling/dev path, not a production hot path)

**Tradeoff accepted:** Eventual consistency between booking events and AI processing. Accepted — AI features (fraud detection, recommendations) are inherently post-hoc.

---

## Branching strategy

**Question:** How to organise Git branches for a 9-phase project?

**Decision:** `phase/0N-name` branches (e.g., `phase/01-foundation`). Each phase gets its own branch, merged to `master` when complete.

**Why:** Each phase is independently deliverable and reviewable. PRs per phase make progress visible and code reviewable phase by phase.

---

## Go not installed on dev machine

**Question (this session):** sqlc generate is needed to produce `internal/repository/db/` packages. Go and sqlc are not installed on the Windows machine being used for editing. What to do?

**Decision:** Commit the present code as-is (without generated db/ packages), document exactly what commands to run once Go is available. Do not hand-write the sqlc output — it's a build artifact that should be generated, not authored.

**Why:** Hand-writing sqlc output is error-prone and defeats the purpose of using sqlc. The right fix is to install Go 1.23+ and run `sqlc generate`, not to work around the missing tooling.

**Next action:** Install Go from golang.org, then:
```
cd services/hotel-inventory && sqlc generate && go mod tidy
cd services/booking-ops   && sqlc generate && go mod tidy
```

---

## Editable install with src layout: dev-mode-dirs over packages

**Question:** The package uses a `src/` layout (`src/agent/`, `src/router/`, `src/memory/`). How to make editable installs (`pip install -e`) resolve `import agent` correctly?

**Decision:** Add `dev-mode-dirs = ["src"]` to `[tool.hatch.build.targets.wheel]` in `pyproject.toml`.

**Problem:**
- `packages = ["src"]` tells hatchling to scan `src/` for Python packages during *build*, but doesn't help editable installs
- Without `dev-mode-dirs`, the editable install's `.pth` file adds the project root to `sys.path`, but `agent` lives at `src/agent/` — invisible
- `pip install -e` without hatchling's `editables` library available produces the same broken `.pth`

**Why not `packages = ["agent", "router", "memory"]`:**
- These don't exist at the project root; they're under `src/`. Would need `["src/agent", "src/router", "src/memory"]`
- `dev-mode-dirs` is cleaner — tells hatchling: "add `src/` to `sys.path` during dev mode"

**Why not just add `src/` manually to `PYTHONPATH`:**
- Not portable — every developer and CI environment would need to know
- The build system (pyproject.toml) should own this configuration

**Why not a non-src layout:**
- src layout is standard for Python projects — prevents accidental imports of `agent` from tests running in the project root
- The tradeoff is worth it: `dev-mode-dirs` is a one-line config fix

**Tradeoff accepted:** Requires `editables` library at install time (hatchling build dependency). Pip handles this automatically when building the editable wheel — only an issue when using `--no-build-isolation` without pre-installing `editables`.

---

## Relative imports in src layout: use absolute imports

**Question:** The `agent` package uses `from ..config import settings` to import the `config` module from the parent package. When the package is installed as editable, `agent` becomes a top-level package. `..config` tries to go above the top-level package, which Python forbids. How to fix?

**Decision:** Change `from ..config import settings` → `from config import settings` in all 4 files that use it.

**Why this works:**
- `dev-mode-dirs = ["src"]` adds `src/` to `sys.path`
- `config.py` lives at `src/config.py`, so `import config` resolves directly

**Alternatives considered:**
- Make `agent` a proper subpackage of a parent package (e.g., move to `booking_assistant.agent`) — scope creep, would break existing imports throughout the codebase
- Add `src/` to `sys.path` at runtime in every entry point — fragile, not portable

**Tradeoff accepted:** If someone runs code without the editable install (e.g., bare `python src/main.py`), `import config` will fail unless `PYTHONPATH=src` is set. Mitigation: all production entry points use the installed package (via Docker), not direct execution.

---

## pytest-asyncio for async test functions

**Decision:** Added `@pytest.mark.asyncio` decorator to async test functions instead of relying on auto-detection.

**Context:** pytest-asyncio 1.0+ defaults to STRICT mode, which requires `@pytest.mark.asyncio` on every async test. The plugin is listed as `asyncio: mode=Mode.STRICT`.

---

## Double-booking prevention: exclusion constraint over application locking

**Question:** The createBooking handler does a SELECT COUNT (availability check) then an INSERT — two separate statements. Two concurrent requests can both see "available" and both insert, creating a double booking. Neither optimistic nor pessimistic application-level locking fixes this cleanly for INSERTs.

**Decision:** PostgreSQL btree_gist exclusion constraint (migration 000004):
```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings ADD CONSTRAINT no_double_booking
    EXCLUDE USING gist (
        room_id WITH =,
        daterange(check_in_date, check_out_date, '[)') WITH &&
    )
    WHERE (status NOT IN ('cancelled', 'no_show'));
```

**Why not pessimistic locking (SELECT FOR UPDATE on room):**
- Locks a row in hotel-inventory from a booking-ops transaction — cross-service row lock, extremely fragile
- Holds lock for duration of the INSERT and any surrounding logic
- Doesn't model the constraint correctly (room row doesn't represent availability directly)

**Why not optimistic locking:**
- Optimistic locking (version column) protects UPDATE of an existing row
- It has no meaning for INSERT — there is no existing row to version-check

**Why the exclusion constraint:**
- Enforcement lives at the DB layer — cannot be bypassed by a bug or a race
- Atomic: the INSERT itself is rejected if it overlaps; no separate check needed
- `daterange '[)'` = inclusive check-in, exclusive check-out (standard hotel convention)
- The `WHERE` clause scopes it to active bookings — cancelled/no-show don't block re-booking

**Tradeoff accepted:** Requires `btree_gist` extension. Ships with standard PostgreSQL — no additional install.

**Note on the application-level CheckAvailability query:** Kept as a UX optimisation — returns a 409 with a friendly message before hitting the DB constraint. The constraint is the enforcement; the query is the UX.

**Why this wasn't in migration 002:** Design gap in the initial schema. The index on `(room_id, check_in_date, check_out_date)` in 002 is for query performance, not uniqueness enforcement. Caught during the locking discussion in this session.
