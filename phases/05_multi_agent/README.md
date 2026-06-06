# Phase 5 — Multi-Agent Systems

## What this phase builds

A **supervisor + worker** multi-agent system that replaces the single Phase 4 agent.
Complex requests are decomposed by a supervisor LLM and dispatched to specialist agents,
each with a focused tool set.

## Architecture

```
User request
     │
     ▼
┌─────────────┐
│  Supervisor │  (claude-sonnet — routing + synthesis)
│    Node     │
└──────┬──────┘
       │ structured routing decision
       ├──────────────────────┐
       ▼                      ▼
┌─────────────┐        ┌──────────────┐
│ search_agent│        │booking_agent │
│  (haiku)   │        │   (haiku)    │
│             │        │              │
│ Tools:      │        │ Tools:       │
│ - semantic_ │        │ - get_guest  │
│   search    │        │ - create_    │
│ - list_rooms│        │   guest      │
│ - check_    │        │ - book_room  │
│   avail.    │        │ - get_booking│
└──────┬──────┘        │ - cancel_   │
       │               │   booking   │
       │               └──────┬───────┘
       └──────────┬───────────┘
                  ▼
           Supervisor re-runs
           → synthesizes answer
```

**Key design decisions:**

- Supervisor uses `claude-sonnet` with structured output (Pydantic `RoutingDecision`) — guarantees the routing is always a valid worker name, never a hallucinated string.
- Workers use `claude-haiku` — cheaper, faster, sufficient for tool-calling tasks.
- Workers return to the supervisor after completing their task; the supervisor decides whether to call another worker or synthesize the final answer.
- The graph enforces a max-depth implicitly: if a worker has already been called, the supervisor won't call it again (tracked via `worker_results`).

## Kafka integration

Phase 5 introduces Apache Kafka (KRaft mode — no ZooKeeper):

```
booking-ops (Go)
    └─ publishes → hotel.booking.events
                        └─ consumed by → multi-agent
                                             └─ logs + placeholder handlers
                                                (fraud scoring, analytics in Phase 7)

multi-agent
    └─ publishes → hotel.agent.events
                        └─ consumed by → analytics services (Phase 7)
```

Topics:
| Topic | Producer | Consumer |
|---|---|---|
| `hotel.booking.events` | booking-ops (Go) | multi-agent |
| `hotel.agent.events` | multi-agent | analytics (Phase 7) |

## Running locally

```bash
# Copy and fill env
cp infra/docker/multi-agent.env.example infra/docker/multi-agent.env

# Start full stack including Kafka
docker compose -f infra/docker/docker-compose.yml up -d

# Kafka UI
open http://localhost:9000

# Test the agent
curl -s -X POST http://localhost:8093/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find a luxury hotel in Dubai and book it for jane@example.com"}' | jq .

# Run evals
cd phases/05_multi_agent/eval && pytest -v
```

## What's next (Phase 6)

MCP servers — thin HTTP facades over the Go service APIs, enabling Claude Desktop
and other MCP clients to interact with hotel booking capabilities via the MCP protocol.
