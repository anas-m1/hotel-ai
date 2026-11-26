# ADR-004: sqlc + pgx Instead of ORM

**Date:** Phase 1  
**Status:** Accepted

## Context
Go services need to talk to PostgreSQL. Options: GORM, Bun, Ent (ORMs), or sqlc + pgx (SQL-first).

## Decision
**sqlc** (compile-time code generator from SQL) + **pgx/v5** (PostgreSQL driver). No ORM.

## Why
- Writing real SQL is a learning goal (interview topic); ORMs hide it
- sqlc generates type-safe Go from hand-written SQL at build time — zero reflection, compile-time safety
- pgx/v5 is the fastest PostgreSQL driver for Go; pgxpool for connection pooling
- Full query control needed for event sourcing and CQRS read model projections
- No N+1 foot-guns from lazy loading

## Why not GORM
- Hides SQL; suboptimal queries for aggregate patterns; `interface{}` surface is not type-safe

## Consequences
- `sqlc generate` required as a build step; generated code committed (or regenerated in CI)
- No dynamic queries — every query must be a named SQL statement in a `.sql` file
- Requires Go + sqlc installed locally: `cd services/hotel-inventory && sqlc generate && go mod tidy`
