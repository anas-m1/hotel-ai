# Architecture decisions

ADRs stay with the code they explain. Read the applicable record before changing
a boundary; update its status when a decision is reversed. Numbering is preserved
so historical references remain identifiable.

- [ADR-001: Polyglot Monorepo (Go + Python)](ADR-001-polyglot-monorepo.md)
- [ADR-003: PostgreSQL + Qdrant, No Elasticsearch](ADR-003-postgresql-qdrant-no-elasticsearch.md)
- [ADR-004: sqlc + pgx Instead of ORM](ADR-004-sqlc-pgx-no-orm.md)
- [ADR-005: Chi as HTTP Router](ADR-005-chi-http-router.md)
- [ADR-006: hotel_code as TEXT Primary Key](ADR-006-hotel-code-as-text.md)
- [ADR-007: Availability Derived from Bookings, No Separate Table](ADR-007-availability-derived-from-bookings.md)
- [ADR-008: Event Sourcing via Dual-Write (bookings + booking_events)](ADR-008-event-sourcing-dual-write.md)
- [ADR-009: Optimistic Locking with version Column](ADR-009-optimistic-locking.md)
- [ADR-010: DB Exclusion Constraint for Double-Booking Prevention](ADR-010-exclusion-constraint-double-booking.md)
- [ADR-011: No Cross-Service Foreign Keys](ADR-011-cross-service-no-foreign-keys.md)
- [ADR-012: LangGraph over LangChain Chains](ADR-012-langgraph-over-langchain.md)
- [ADR-013: LiteLLM Gateway — All LLM Calls Centralised](ADR-013-litellm-gateway.md)
- [ADR-014: MCP Servers as Thin HTTP Facades](ADR-014-mcp-servers-thin-facades.md)
- [ADR-017: QueryExecModeSimpleProtocol for NUMERIC Columns](ADR-017-pgx-simple-protocol-numeric.md)
- [ADR-020: MCP Servers Use SSE Transport, Not stdio](ADR-020-mcp-sse-transport.md)
- [ADR-021: Langfuse for Centralized LLM Observability](ADR-021-langfuse-centralized-tracing.md)
- [ADR-022: Redis for LangGraph Checkpoint Storage](ADR-022-redis-agent-memory.md)
- [ADR-027: Product, experiments, learning and test ownership](ADR-027-product-learning-separation.md)

Records specific to experimental Kafka/multi-agent/GraphRAG designs, the learning
branching strategy and AWS deployment blueprints are archived in hotel-ai-lab.
ADR-027 records the repository split.

Some historical wording describes intent rather than completed behavior:
ADR-008 is a reservation table plus audit log, not a fully event-sourced system;
those writes are not atomic. Current architecture and implementation evidence
take precedence over a historical Accepted label.
