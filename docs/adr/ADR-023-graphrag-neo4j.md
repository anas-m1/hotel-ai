# ADR-023: GraphRAG with Neo4j for Entity-Aware Hotel Retrieval

**Date:** Phase 8  
**Status:** Accepted

## Context

Phase 3's hybrid search (dense + sparse vectors via Qdrant) retrieves hotels
by semantic similarity. It works well for descriptions like "quiet boutique hotel"
but struggles with structural queries: "hotel near the Louvre with a spa in Paris"
requires knowing that The Louvre is an attraction in Paris, and which hotels are
nearby — relationships that don't live in a single text embedding.

## Decision

Add a knowledge graph layer (Neo4j) alongside the existing Qdrant vector store.
The `ai/knowledge-graph` service implements **GraphRAG**:

1. **Entity extraction**: call llm-gateway with claude-haiku to extract cities,
   amenities, and attractions from the user query.
2. **Graph traversal**: Cypher query on Neo4j finds hotels satisfying entity
   constraints, scored by how many constraints they match.
3. **Vector search**: existing Qdrant hybrid search runs in parallel.
4. **RRF fusion**: merge and re-rank both result lists using Reciprocal Rank Fusion.

## Why

- **Structural relationships**: Neo4j natively encodes `(:Hotel)-[:NEAR_ATTRACTION]->(:Attraction)`.
  A hotel that is walking distance from the Louvre scores higher than one across
  town, regardless of whether "Louvre" appears in its text description.
- **Complementary retrieval**: graph excels at filtered structural queries; vectors
  excel at fuzzy semantic similarity. RRF fusion captures the best of both.
- **Explainability**: the entity extraction step shows the user what the system
  understood from their query — useful for debugging and future UI features.

## Consequences

- Neo4j is a new infrastructure dependency. Added as `neo4j:5.18-community` to
  docker-compose with APOC plugin for utility procedures.
- Attraction data is seeded statically per city code (Phase 8). In production
  (Phase 9), this would be populated from a geo-data API or curated dataset.
- Entity extraction adds one LLM call per search request (claude-haiku, ~100ms).
  Acceptable: the search path already has Qdrant + Neo4j latency.
- If Neo4j is unreachable, the service falls back to vector-only results.
