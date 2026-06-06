# ADR-006: hotel_code as TEXT Primary Key

**Date:** Phase 1  
**Status:** Accepted

## Context
Hotels need a primary key. Codes currently look numeric (e.g. `1003300`).

## Decision
`hotel_code TEXT PRIMARY KEY`

## Why
Hotel codes are external identifiers from a third-party system — opaque strings that happen to look numeric today. Future data sources or API integrations may return `"HT-1003300"` or prefixed formats. Declared column type does not affect index performance in PostgreSQL.

## Consequences
- Qdrant point IDs must be `uint64` or UUID — hotel_code TEXT cannot be a Qdrant point ID directly. UUID used as Qdrant point ID; hotel_code stored in the payload for lookup.
