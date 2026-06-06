# Architecture Decision Records

This directory contains ADRs for the hotel-ai project.
Each ADR captures one meaningful decision: what was chosen, why, and what tradeoffs were accepted.

## How to use
- Read before making a change that touches a recorded decision
- Add a new ADR when you make a significant new choice
- Update status to **Superseded** (link to new ADR) if a decision is reversed

## Status values
`Accepted` | `Superseded` | `Deprecated` | `Proposed`

## Index

| # | Title | Status |
|---|-------|--------|
| [001](ADR-001-polyglot-monorepo.md) | Polyglot monorepo (Go + Python) | Accepted |
| [002](ADR-002-separate-gitops-repo.md) | Separate GitOps repo for deployment manifests | Accepted |
| [003](ADR-003-postgresql-qdrant-no-elasticsearch.md) | PostgreSQL + Qdrant, no Elasticsearch | Accepted |
| [004](ADR-004-sqlc-pgx-no-orm.md) | sqlc + pgx instead of ORM | Accepted |
| [005](ADR-005-chi-http-router.md) | Chi as HTTP router | Accepted |
| [006](ADR-006-hotel-code-as-text.md) | hotel_code as TEXT primary key | Accepted |
| [007](ADR-007-availability-derived-from-bookings.md) | Availability derived from bookings, no separate table | Accepted |
| [008](ADR-008-event-sourcing-dual-write.md) | Event sourcing via dual-write (bookings + booking_events) | Accepted |
| [009](ADR-009-optimistic-locking.md) | Optimistic locking with version column | Accepted |
| [010](ADR-010-exclusion-constraint-double-booking.md) | DB exclusion constraint for double-booking prevention | Accepted |
| [011](ADR-011-cross-service-no-foreign-keys.md) | No cross-service foreign keys | Accepted |
| [012](ADR-012-langgraph-over-langchain.md) | LangGraph over LangChain chains | Accepted |
| [013](ADR-013-litellm-gateway.md) | LiteLLM gateway — all LLM calls centralised | Accepted |
| [014](ADR-014-mcp-servers-thin-facades.md) | MCP servers as thin HTTP facades | Accepted |
| [015](ADR-015-python-ai-kafka-consumers.md) | Python AI services consume Kafka, not sync HTTP | Accepted |
| [016](ADR-016-phase-branching-strategy.md) | phase/NN-name Git branching strategy | Accepted |
| [017](ADR-017-pgx-simple-protocol-numeric.md) | QueryExecModeSimpleProtocol for NUMERIC columns | Accepted |
