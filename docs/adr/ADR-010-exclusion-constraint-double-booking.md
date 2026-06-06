# ADR-010: DB Exclusion Constraint for Double-Booking Prevention

**Date:** Phase 1  
**Status:** Accepted

## Context
Two concurrent requests can both pass the availability check (SELECT COUNT = 0) and both proceed to INSERT a booking for the same room and overlapping dates. This TOCTOU race cannot be prevented at the application layer without a distributed lock.

## Decision
PostgreSQL btree_gist exclusion constraint on `bookings`:
```sql
EXCLUDE USING gist (
    room_id WITH =,
    daterange(check_in_date, check_out_date, '[)') WITH &&
) WHERE (status NOT IN ('cancelled', 'no_show'))
```

## Why
- The constraint is enforced atomically inside PostgreSQL's transaction machinery — no application-level coordination needed.
- `daterange ... WITH &&` (overlaps) catches all overlap cases: contained, containing, and partially overlapping.
- The `WHERE` partial clause exempts cancelled/no-show bookings so the same room can be re-booked after cancellation.
- `btree_gist` extension provides the GiST index operator class for UUID equality combined with range overlap.
- The application-level availability check (`CheckAvailability` → HTTP 409) is kept as a UX optimisation: it returns a friendly error before hitting the DB constraint. The constraint is the enforcement.

## Consequences
- Requires `CREATE EXTENSION IF NOT EXISTS btree_gist` — included in migration 000004.
- A failed INSERT due to exclusion violation returns a PostgreSQL error code `23P01` (exclusion_violation), which the repository layer maps to `ErrConflict`.
