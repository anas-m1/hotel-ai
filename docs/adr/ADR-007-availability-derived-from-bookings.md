# ADR-007: Availability Derived from Bookings, No Separate Table

**Date:** Phase 1  
**Status:** Accepted

## Context
Room availability needs to be queryable (is this room free for these dates?). Two options: maintain a separate `availability` table updated on each booking change, or derive availability by querying the `bookings` table directly.

## Decision
Availability is derived: `SELECT COUNT(*) FROM bookings WHERE room_id = $1 AND daterange(...) && daterange(...) AND status NOT IN ('cancelled', 'no_show')`. No `availability` table.

## Why
- A separate availability table is a cache — it duplicates state that already lives in `bookings` and requires a two-write transaction on every booking change. Two writes means two failure modes.
- Derived queries are fast enough: the `room_id` + status partial index on `bookings` makes availability checks O(overlapping bookings), not O(all bookings).
- The btree_gist exclusion constraint enforces no-double-booking atomically at INSERT time, which is the enforcement that matters. The availability query is a UX optimisation (early 409), not the safety net.

## Consequences
- Availability queries hit the bookings table — acceptable at Phase 1 scale.
- At high read volume, a Redis cache layer in front of the availability check would be the right optimisation (Phase 7+), not a separate table.
