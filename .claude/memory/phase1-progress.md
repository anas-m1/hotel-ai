---
name: phase1-progress
description: Phase 1 implementation status — what's done, what's pending, where to start next
metadata:
  type: project
---

## Current status: Phase 1 — Foundation (in progress)

Active branch: `phase/01-foundation` (local only, not pushed to remote yet).
Last commit: `3ef8f46` — "feat(phase-1): implement hotel-inventory service and booking-ops schema"

---

## Done

### hotel-inventory service (`services/hotel-inventory/`)
- Domain model: `Hotel`, `Room`, `Location`, `HotelRating`, `RoomType` enums, sentinel errors (`ErrNotFound`, `ErrConflict`)
- DB migrations: `locations` → `hotels` → `rooms` (correct dependency order)
- sqlc queries: hotels (get, list by city, list by rating, FTS search, upsert, count), rooms (get, list, list active, list by type, create, update, deactivate, count), locations (get, list by county, upsert)
- sqlc config (`sqlc.yaml`): uuid and numeric type overrides, emit_empty_slices, emit_pointers_for_null_types
- Repository layer: `HotelRepository`, `RoomRepository`, `LocationRepository` interfaces + postgres implementations (mapping helpers included)
- HTTP handlers (Chi): hotels (GET /v1/hotels/{code}, GET /v1/hotels?city=|rating=|q=, PUT /v1/hotels/{code}), rooms (GET/POST /v1/hotels/{code}/rooms, GET/PUT/DELETE /v1/rooms/{id}), locations (GET /v1/locations/{code}, GET /v1/locations?county=, PUT /v1/locations/{code})
- Server `cmd/server/main.go`: full wiring (pgxpool with SimpleProtocol, Chi router)
- Migration runner `cmd/migrate/main.go`: `up`/`down` via golang-migrate
- Makefile: generate, build, test, lint, migrate-up, migrate-down targets

### booking-ops service (`services/booking-ops/`)
- DB migrations: `guests` → `bookings` (optimistic locking via `version` column, date overlap constraint) → `booking_events` (immutable event log, agent-triggered partial index)
- sqlc queries: guests (get by id, get by email, create, update, upsert), bookings (get, list by guest, list by hotel, create, update status with optimistic locking, check room availability), booking_events (insert, list by booking, list by type)
- sqlc config (`sqlc.yaml`): same type override pattern as hotel-inventory

### Infra
- `infra/docker/docker-compose.yml`: postgres 16-alpine with healthcheck (only `hotel_inventory` DB; `booking_ops` DB not added yet)

---

## Pending (to complete Phase 1)

### Step 1 — Install Go toolchain
Go is NOT installed on the Windows machine (not in PATH). Need to install Go 1.23+ from golang.org before any build/generate step can run. User runs commands in a PowerShell terminal; suggest: `! go version` to confirm once installed.

### Step 2 — Run `sqlc generate` for both services
```
cd services/hotel-inventory && sqlc generate
cd services/booking-ops   && sqlc generate
```
This produces `internal/repository/db/` (DBTX interface, Queries struct, model types, query method implementations) for each service. sqlc does NOT need a running database — it reads SQL files only.

### Step 3 — Implement booking-ops Go layer ✓ DONE
All files written:
- `internal/domain/booking.go` ✓
- `internal/domain/errors.go` ✓ (ErrNotFound, ErrConflict, ErrVersionConflict)
- `internal/repository/booking.go` ✓ (GuestRepository, BookingRepository, BookingEventRepository)
- `internal/handler/guest.go` ✓ (POST /v1/guests, GET /v1/guests/{id})
- `internal/handler/booking.go` ✓ (create, get with events, update status, list by guest/hotel, availability check)
- `internal/handler/routes.go` ✓
- `cmd/server/main.go` ✓ (port 8081, SimpleProtocol)
- `cmd/migrate/main.go` ✓
- `go.mod` ✓
- `Makefile` ✓
- `sqlc.yaml` ✓ (uuid, numeric, jsonb overrides)
- `db/migrations/000004` ✓ — btree_gist exclusion constraint (no_double_booking)

### Step 4 — `go mod tidy` for both services ← NEXT after Go installed

### Step 5 — Add booking_ops database to docker-compose ✓ DONE
- `infra/docker/init-db.sh` creates `booking_ops` DB on first container start
- `docker-compose.yml` mounts init script

### Step 6 — Config package + pagination from config ← TODO
Pagination limits (default 20, max 100) are still hardcoded in handler/routes.go for both services. Extract to a Config struct loaded from env vars.

### Step 7 — Test suite ← TODO
Handler tests (httptest), repository unit tests (mock sqlc Querier interface), integration tests tagged `//go:build integration`. Priority: optimistic locking race, date overlap constraint, availability TOCTOU.

### Step 4 — `go mod tidy` for both services
Run after sqlc generate to produce go.sum files.

### Step 5 — Add booking_ops database to docker-compose
Add a second DB (or use `POSTGRES_MULTIPLE_DATABASES` pattern) for booking-ops.

### Step 6 — Phase 1 verification
- `docker compose up -d` → run migrations for both services → hit REST endpoints manually
- Add booking-ops sqlc.yaml to .gitignore or commit the generated db/ packages

**Why:** All Go implementations reference `internal/repository/db` (the sqlc output) which doesn't exist yet, so neither service compiles until steps 1–2 are done.
