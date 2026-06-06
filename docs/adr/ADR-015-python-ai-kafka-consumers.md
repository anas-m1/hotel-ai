# ADR-015: Python AI Services Consume Kafka, Not Sync HTTP

**Date:** Phase 0 (architecture)  
**Status:** Accepted

## Context
Go services generate events (booking created, payment processed). Python AI services (fraud detection, analytics, recommendation engine) need to react to these events. Two integration patterns: synchronous HTTP calls from Go to Python, or Python services consuming a Kafka topic.

## Decision
Go services publish domain events to Kafka topics. Python AI services are Kafka consumers — they never receive synchronous calls from Go services. The only synchronous calls from Python to Go are the MCP facades and internal tool calls in agents.

## Why
- Go services should not know about Python AI services. Adding a synchronous call from booking-ops to a fraud-detection Python service couples their availability: if fraud-detection is slow, booking creation is slow.
- Kafka decouples producers from consumers: Go publishes and moves on; Python processes at its own pace. A new Python consumer can be added without touching any Go code.
- Event replay: Kafka retains events, so a new consumer (or a redeployed one) can reprocess history from any offset. A synchronous call is gone once it completes.
- Fraud scoring and analytics are inherently async — they don't need to block the booking creation response.

## Consequences
- Python AI services have eventual consistency with respect to booking state — they see events with some lag.
- Kafka is a required infrastructure dependency from Phase 5 onward. Added to docker-compose in Phase 5.
- The `shared/events/` directory holds Kafka event schemas that both Go producers and Python consumers depend on.
