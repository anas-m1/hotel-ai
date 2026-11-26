# ADR-022: Redis for LangGraph Checkpoint Storage

**Date:** Phase 7  
**Status:** Accepted

## Context

Phase 4 and 5 used `MemorySaver` as the LangGraph checkpointer — state was
stored in a Python dict inside the container process. This means:
- All conversation history is lost on container restart.
- HITL interrupts are lost if the container crashes between the user seeing the
  confirmation and clicking approve.
- Horizontal scaling is impossible: two instances of booking-assistant have
  separate in-memory stores, so a request routed to instance B can't resume a
  session started on instance A.

## Decision

Replace `MemorySaver` with `AsyncRedisSaver` (from `langgraph-checkpoint-redis`)
at startup. The checkpointer is created once, `asetup()` is called to create
Redis search indexes, and the compiled graph is built with it.

`MemorySaver` is kept as an automatic fallback: if Redis is unreachable at
startup (e.g., running tests without Docker), the service logs a warning and
continues with in-memory state. This prevents tests from requiring a live Redis.

## Why

- **HITL durability**: an `interrupt()` pause survives container restarts.
  The frozen state is in Redis; the user can approve hours later.
- **Horizontal scaling**: multiple booking-assistant instances share one Redis,
  so any instance can resume any session.
- **Session replay**: Redis stores the full message history per `thread_id`.
  The agent can be asked "what did I book last time?" without re-fetching from
  the database.

## Consequences

- Redis is a required dependency for stateful agent behaviour in production.
  Added to docker-compose as `redis:7-alpine` with AOF persistence.
- `thread_id` maps to the HTTP session's `session_id`. Clients must send the
  same `session_id` across turns to maintain conversation continuity.
- Redis memory grows with the number of active sessions. For Phase 7 scale,
  no eviction policy is needed; Phase 9 (capstone) should add a TTL-based
  eviction policy for sessions idle > 7 days.
