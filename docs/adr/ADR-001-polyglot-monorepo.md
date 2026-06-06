# ADR-001: Polyglot Monorepo (Go + Python)

**Date:** Phase 0  
**Status:** Accepted

## Context
The system has two distinct layers: a Go-based booking domain (hotel-inventory, booking-ops, pricing-engine) and a Python-based AI layer (LangGraph agents, RAG pipeline, LiteLLM gateway, MCP servers). Decision needed on repo structure.

## Decision
Single polyglot monorepo. Go services and Python AI services live in the same repository under `services/` and `ai/` respectively. Shared Kafka event schemas live in `shared/events/`.

## Why
- `go.work` is designed for multi-module Go repos — no special tooling needed
- Atomic commits across service boundaries (e.g. adding a Kafka event type used by both Go and Python)
- Go/Python integration is via Kafka (async) and HTTP (MCP) — not shared libraries — so language tooling stays independent
- One developer: no team access-control overhead that justifies polyrepo complexity
- The Kafka coupling between Go producers and Python consumers makes polyrepo actively harmful (shared schemas would need versioning + a private registry)

## Consequences
- Two build systems (go mod + uv), two lint setups, two CI steps
- Evolution path: if collaborating with others, split at the layer boundary — `hotel-ai-services` (Go) + `hotel-ai-ai` (Python). Never split individual services unless one team per service.
