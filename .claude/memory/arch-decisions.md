---
name: arch-decisions
description: Architecture decisions made during Phase 0/1 setup with rationale — the why behind every major call
metadata:
  type: project
---

## Repo Structure

**Decision: Single polyglot monorepo**
Go services + Python AI services + Python MCP servers all in one repo.

**Why:** `go.work` is designed for exactly this. Shared Kafka schemas in `shared/events/` work trivially. Atomic commits across service boundaries. One developer, no team access-control overhead. The Kafka coupling between Go producers and Python consumers makes polyrepo actively harmful (shared schemas would need versioning + a private registry).

**Evolution path:** When collaborating with others, split at the layer boundary — `hotel-ai-services` (Go) + `hotel-ai-ai` (Python). Never split individual services unless you have one team per service.

---

## Separate GitOps Repo

**Decision: `hotel-ai-gitops` will be a separate repo, created at Phase 7.**

**Why:** Clean separation between source code (devs) and deployment manifests (ops). ArgoCD watches the GitOps repo; CI in `hotel-ai` builds images and bumps image tags there. Access control and audit trail for production deployments stays separate.

**How to apply:** Do not add Helm charts or ArgoCD configs to `hotel-ai`. `infra/k8s/` is a placeholder only. See [[project-gitops-repo]].

---

## Database Layer

**Decision: PostgreSQL (Go services) + Qdrant (search/RAG) — NOT Elasticsearch/OpenSearch.**

**Why:** Elasticsearch relicensed in 2021 (no longer open source). OpenSearch is the true open-source fork but adds a system we don't need. Qdrant handles both dense (text-embedding-3-large) and sparse (SPLADE) vectors natively with RRF hybrid fusion — one system replaces both Qdrant and any keyword search engine.

**Decision: PostgreSQL is the source of truth. Qdrant is the search index.**

**Why:** Qdrant has no ACID transactions, no row-level locking, eventual consistency. Rooms, availability, and bookings require `SELECT FOR UPDATE` to prevent double-booking — that's only possible in PostgreSQL. Qdrant stores vectors + minimal filter payload (hotel_code, rating, city, lat/lng). Full hotel data fetched from PostgreSQL after search returns IDs. No meaningful duplication.

**What lives where:**
- PostgreSQL: hotels, locations, rooms, bookings, booking_events, guests (source of truth, relational, transactional)
- Qdrant: dense + sparse vectors per hotel, minimal payload for filtering (Phase 3 onwards)

---

## Go Query Layer

**Decision: sqlc + pgx (not GORM, not Ent)**

**Why:** CQRS and event sourcing require explicit SQL control. GORM is CRUD-oriented and fights event sourcing. sqlc generates type-safe Go code from hand-written SQL — zero reflection, compile-time safety, explicit queries. pgx is the canonical PostgreSQL driver for Go.

**Decision: golang-migrate for schema migrations.**

**Why:** Plain SQL up/down files, widest ecosystem, any DBA can read them, simple version tracking via `schema_migrations` table.

---

## hotel_code as TEXT (not INT)

**Decision: `hotel_code TEXT PRIMARY KEY`**

**Why:** Hotel codes are external identifiers from a third-party system — opaque strings that happen to look numeric today. Future data sources or API integrations may return `"HT-1003300"` or prefixed formats. Declared column type doesn't affect index performance in PostgreSQL (actual data size determines B-tree entry size, not the type declaration).

**Qdrant implication:** Qdrant point IDs must be `uint64` or UUID. Since hotel_code is TEXT, Qdrant uses UUID as the point ID; hotel_code is stored in the payload for lookup.

---

## Bookings — Availability Model

**Decision: Availability is derived from the `bookings` table. No separate availability table.**

**Why:** Pre-computing an availability calendar creates a sync problem — it goes stale the moment a booking is made. Deriving it from bookings is always consistent: available = room exists AND no confirmed booking overlaps requested dates. The partial index `idx_bookings_room_dates WHERE status NOT IN ('cancelled', 'no_show')` makes this query fast.

**Decision: No channel manager integration in Phase 1.**

**Why:** Hotels receive bookings from multiple sources (Amadeus GDS, Sabre, Booking.com, front desk). A full solution requires a channel manager (ARI sync). For Phase 1, this system is the source of record for bookings it creates. Phase 6 adds an `external-integrations` MCP server to connect a channel manager.

---

## Optimistic Locking

**Decision: `version INT` column on `bookings` table.**

**Why:** Prevents lost updates when two requests update the same booking simultaneously. The UPDATE checks `WHERE version = $current` and increments it. Zero rows affected = conflict detected → retry or error. Avoids the overhead of pessimistic `SELECT FOR UPDATE` locks for most cases.

---

## Migration Numbering

**Decision: Each service has its own independent migration sequence starting at `000001`.**

**Why:** Each service has its own database. `golang-migrate` tracks versions inside each database independently via its own `schema_migrations` table. `000001` in booking-ops (guests) and `000001` in hotel-inventory (locations) are in different databases — no conflict, no unified sequence needed.
