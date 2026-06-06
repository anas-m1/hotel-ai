# ADR-019: Kafka in KRaft Mode (No ZooKeeper)

**Date:** Phase 5  
**Status:** Accepted

## Context

Phase 5 introduces Apache Kafka as the event bus between Go services and Python AI
consumers. Kafka traditionally required a separate ZooKeeper ensemble for cluster
coordination, adding operational overhead and a second system to understand.

## Decision

Run Kafka in **KRaft mode** (Kafka Raft metadata protocol, GA since Kafka 3.3).
A single Kafka broker acts as both broker and controller. No ZooKeeper process.

## Why

- ZooKeeper is deprecated and will be removed in a future Kafka major version.
  Starting with KRaft now avoids a future migration.
- One fewer container in docker-compose — simpler local setup.
- KRaft is production-ready for single-broker deployments (our Phase 5 target).
- For Phase 7+ multi-broker production clusters on EKS, KRaft supports full HA
  with controller quorum voters — the same config, scaled out.

## Consequences

- CLUSTER_ID must be set explicitly in KRaft mode. We use a fixed value in
  docker-compose so the volume survives container restarts without re-formatting.
- Single broker means replication factor is 1 — no fault tolerance for local dev.
  Acceptable: Kafka data loss in dev is recoverable by re-running migrations and
  re-seeding data. For production (Phase 7), replication factor will be 3.
