---
name: concepts-learned
description: Conceptual gaps filled during Phase 0/1 discussions — terminology, trade-offs, and mental models built
metadata:
  type: user
---

## Vector Search Terminology

**Gap:** Assumed "sparse" = fuzzy/imprecise and "dense" = exact/precise.

**Correction:** The names describe the mathematical structure of the vector, not the matching behaviour.

- **Sparse vector:** One dimension per vocabulary term (~50K–100K dims). A document with 300 unique words has 300 non-zero entries and ~49,700 zeros. Mostly zeros → sparse. BM25 and SPLADE both produce sparse vectors.
- **Dense vector:** Neural embedding (e.g. text-embedding-3-large) maps text to 3072 dims where nearly all values are non-zero. Meaning distributed across all dimensions → dense.
- **SPLADE:** Neural model that outputs sparse vectors — a neural network decides which vocabulary dimensions to activate (not just literal word presence). Gives BM25-like efficiency with semantic expansion ("car" also activates "vehicle", "automobile").

---

## Why Both PostgreSQL and Qdrant

**Gap:** Assumed storing the same data in both systems is redundant duplication.

**Correction:** They serve completely different queries.

- PostgreSQL: CRUD, JOINs, transactions, availability locking, aggregations, source of truth.
- Qdrant: ANN vector search + filter. Returns IDs → you batch-fetch full data from PostgreSQL. Only stores vectors + minimal filter payload (rating, city, lat/lng). The description text never lives in Qdrant — it's encoded in the vector.

**Why Qdrant can't replace PostgreSQL for rooms/availability:** No ACID, no row-level locking (`SELECT FOR UPDATE`). Two users booking the same room simultaneously → double booking with no way to prevent it. Availability is a concurrency problem, not a search problem.

---

## PostgreSQL TEXT vs VARCHAR

**Gap:** Assumed declaring `VARCHAR(n)` makes indexes more efficient.

**Correction:** PostgreSQL indexes on the actual data size, not the declared column type. `TEXT` and `VARCHAR` without a limit are identical in storage, performance, and indexing. `VARCHAR(n)` is only useful when the length limit itself is a business rule (e.g. `CHAR(3)` for a currency code).

---

## What "Migration" Means

**Gap:** Assumed "migration" meant moving data from one place to another (data migration).

**Correction:** In schema management, migration = moving the schema from one version to the next. The "from" is always the previous version. Version 0 = empty database. The first migration moves from v0 → v1. Every environment runs the same sequence of migration files to reach the same schema state — no special "first time setup" path.

---

## RETURNING * in SQL

**Gap:** Not clear what `RETURNING *` adds to INSERT/UPDATE.

**Correction:** PostgreSQL's INSERT and UPDATE normally execute silently — they return nothing. `RETURNING *` tells PostgreSQL to send back the full row after the operation, including any database-generated values (UUID primary keys, `DEFAULT NOW()` timestamps). Without it, you'd need a separate SELECT query to retrieve the generated fields. sqlc maps `RETURNING *` to the `:one` return type — the Go function returns the full typed struct.

---

## Optimistic Locking

**Gap:** Not clear what the `version INT` column does.

**Correction:** Prevents lost updates under concurrent writes without holding a lock.

Flow:
1. Request A reads booking: `{id: X, version: 1, status: pending}`
2. Request B reads booking: `{id: X, version: 1, status: pending}`
3. Request A: `UPDATE ... SET status='confirmed', version=2 WHERE id=X AND version=1` → 1 row affected ✓
4. Request B: `UPDATE ... SET status='cancelled', version=2 WHERE id=X AND version=1` → 0 rows affected (version is now 2)
5. Application sees 0 rows → conflict → retry or return error

No row is silently overwritten. Cheaper than `SELECT FOR UPDATE` for most cases.

---

## Monorepo vs Polyrepo in Production

**Gap:** Assumed production companies use polyrepo (one repo per service).

**Correction:** It's mixed. Google/Meta/Twitter use monorepos (with Bazel). Netflix/Uber early days used polyrepo. Most mid-size companies use monorepo or hybrid. The splitting boundary that matters is by team ownership, not by service count. Full polyrepo (per-service) only pays off when you have separate on-call rotations per service and a platform team managing the registry/versioning overhead.

---

## Git Migrations — Numbering Per Service

**Gap:** Concerned that both services start at `000001`.

**Correction:** Each service has its own independent database. `golang-migrate` tracks migration versions inside each database separately via a `schema_migrations` table it creates. `000001` in booking-ops and `000001` in hotel-inventory are in completely different databases — no conflict. The 6-digit padding is convention for alphabetical sort stability up to 999,999 migrations.
