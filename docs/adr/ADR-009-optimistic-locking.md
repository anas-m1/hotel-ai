# ADR-009: Optimistic Locking with version Column

**Date:** Phase 1  
**Status:** Accepted

## Context
Booking status updates (pending → confirmed, confirmed → cancelled) are concurrent. Two agents or two browser tabs can read the same booking and attempt conflicting updates. Need to prevent lost updates without holding a database row lock for the duration of a request.

## Decision
`bookings` table has `version INT NOT NULL DEFAULT 1`. Every UPDATE includes `WHERE id = $1 AND version = $N` and increments version. Zero rows affected = conflict → return `ErrVersionConflict` → HTTP 409.

## Why
- Pessimistic locking (`SELECT FOR UPDATE`) holds a lock from read to write — any delay (network, LLM inference) blocks every other writer for that booking. Unacceptable when agents are in the write path.
- Optimistic locking has no lock contention: readers never block writers. Conflicts only materialise on the final write and are rare in practice (two agents modifying the same booking simultaneously).
- Version conflicts are detected at the application layer with a clean error code, not a PostgreSQL lock timeout.

## Consequences
- Callers must retry on 409 (version conflict). The LangGraph agent's reflection node handles this.
- Does not prevent the TOCTOU race in availability check + INSERT — that is handled by the btree_gist exclusion constraint (ADR-010).
