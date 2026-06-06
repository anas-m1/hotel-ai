# ADR-008: Event Sourcing via Dual-Write (bookings + booking_events)

**Date:** Phase 1  
**Status:** Accepted

## Context
Booking state changes (created, confirmed, cancelled) need to be auditable and replayable by AI agents in later phases. Two approaches: pure event sourcing (derive current state by replaying events) or dual-write (mutable state table + immutable event log).

## Decision
Dual-write: every booking operation writes to `bookings` (current state, mutable) and appends to `booking_events` (immutable log). The `bookings` table is the source of truth for current state; `booking_events` is the audit trail.

## Why
- Pure event sourcing requires replaying potentially thousands of events to answer "what is the current status?" — unacceptable latency for a booking API.
- `booking_events` with a `triggered_by` field and structured JSON payload is sufficient for the agent tracing use case (Phase 4+): agents can inspect what happened to a booking and why.
- Dual-write is a well-understood pattern with a simple failure mode: if the event insert fails, the booking mutation is still committed (event loss, not data loss). Acceptable tradeoff for Phase 1; a transactional outbox pattern can replace this in Phase 7.

## Consequences
- Two writes per booking mutation — slightly more latency, acceptable.
- Columnar analytics (CDC → columnar store) deferred to Phase 7. `booking_events.payload` is JSONB today; schema migration to a columnar format is straightforward when needed.
