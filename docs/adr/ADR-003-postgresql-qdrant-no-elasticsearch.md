# ADR-003: PostgreSQL + Qdrant, No Elasticsearch

**Date:** Phase 0  
**Status:** Accepted

## Context
System needs: (1) a transactional relational store for bookings/rooms/guests, (2) a vector search engine for hotel content RAG. Original plan included Elasticsearch for BM25 sparse search.

## Decision
- **PostgreSQL 16** — source of truth for all domain data (hotels, rooms, bookings, guests)
- **Qdrant** — vector search index (dense + sparse, replaces Elasticsearch)
- **No Elasticsearch / OpenSearch**

## Why PostgreSQL as source of truth
Rooms, availability, and bookings require `SELECT FOR UPDATE` and ACID transactions to prevent double-booking. Qdrant has no row-level locking or transactions. PostgreSQL is the only option for the write path.

## Why Qdrant replaces Elasticsearch
- Elasticsearch relicensed in 2021 (no longer open source); OpenSearch is the fork but adds operational complexity
- Qdrant supports both dense vectors (text-embedding-3-large) and sparse vectors (SPLADE for BM25-style retrieval) natively with RRF hybrid fusion — one system replaces Qdrant + Elasticsearch
- Self-hostable on K8s; better HNSW tuning than pgvector

## What lives where
| Store | Data |
|-------|------|
| PostgreSQL | hotels, locations, rooms, bookings, booking_events, guests |
| Qdrant | dense + sparse vectors per hotel, minimal filter payload (hotel_code, rating, city, lat/lng) |

## Consequences
- Full hotel data is always fetched from PostgreSQL after Qdrant returns IDs — no meaningful duplication
- Qdrant point IDs must be `uint64` or UUID; hotel_code TEXT is stored in the payload, UUID used as point ID
