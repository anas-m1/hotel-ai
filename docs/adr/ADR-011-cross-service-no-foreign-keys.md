# ADR-011: No Cross-Service Foreign Keys

**Date:** Phase 1  
**Status:** Accepted

## Context
`bookings.hotel_code` references a hotel that lives in the `hotel_inventory` database. A foreign key would enforce referential integrity but would require both services to share a database.

## Decision
Cross-service references are plain TEXT fields (e.g. `hotel_code TEXT`, `room_id UUID`). No database-level foreign keys across service boundaries. Each service owns its own database.

## Why
- A shared database is a deployment coupling: both services must be on the same DB instance, schema migrations must coordinate, one service's table lock can affect the other.
- Microservice boundary means: you own your data. If hotel-inventory goes down, booking-ops should still be able to read and update existing bookings.
- Referential integrity across services is enforced at the application layer: booking-ops validates `hotel_code` and `room_id` exist before creating a booking (via HTTP calls to hotel-inventory).

## Consequences
- Stale references are possible: a room can be deleted from hotel-inventory while a booking still references it. Acceptable — the booking record is the historical truth; the room may no longer be available.
- Cascading deletes across services require explicit orchestration (a saga), not a DB cascade.
