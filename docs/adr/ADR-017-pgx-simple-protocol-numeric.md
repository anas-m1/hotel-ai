# ADR-017: QueryExecModeSimpleProtocol for NUMERIC Columns

**Date:** Phase 1  
**Status:** Accepted

## Context
PostgreSQL `NUMERIC` columns (used for `total_price`, `base_price`) are sent over the pgx extended protocol as binary format by default. pgx's default binary decoder for `NUMERIC` requires `pgtype.Numeric`, a struct with mantissa + exponent fields. This adds complexity to mapping layers.

## Decision
Set `pgxpool.Config.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol`. This forces all queries to use the PostgreSQL simple protocol, which sends and receives all values as text strings. `NUMERIC` columns arrive as `"450.00"` — a plain Go `string`.

## Why
- The sqlc type overrides map `pg_catalog.numeric` → `string`. With simple protocol, the wire value is already a string — no conversion needed.
- Simple protocol is slightly less efficient than extended protocol (no server-side prepared statement caching) but the difference is negligible for booking operations that are not high-frequency.
- The alternative — using `pgtype.Numeric` everywhere — requires wrapping/unwrapping in every mapping helper and every test fixture.

## Consequences
- Simple protocol does not support server-side prepared statements. Acceptable for Phase 1 scale.
- If query throughput becomes a bottleneck in Phase 7+, switch individual high-frequency queries to extended protocol while keeping simple protocol as the default. The repository interfaces abstract this change.
