# Phase 8 — Knowledge Graph

## What this phase builds

A knowledge graph layer (Neo4j) combined with the existing Qdrant vector search,
implementing **GraphRAG** and **Self-RAG** for richer, more accurate hotel retrieval.

## Architecture

```
User query: "beachfront hotel near the Eiffel Tower with a spa"
                          │
                          ▼
              ┌─────────────────────┐
              │  Entity Extraction  │  ← claude-haiku via llm-gateway
              │  cities: [Paris]    │
              │  amenities: [spa]   │
              │  attractions:       │
              │  [Eiffel Tower]     │
              └──────────┬──────────┘
                         │
           ┌─────────────┴──────────────┐
           ▼                            ▼
  ┌─────────────────┐         ┌──────────────────┐
  │  Graph Traversal│         │  Vector Search   │
  │  Neo4j Cypher   │         │  Qdrant RRF      │
  │  Match hotels   │         │  Semantic sim.   │
  │  near Eiffel    │         │  "beachfront spa"│
  │  Tower with spa │         │                  │
  └────────┬────────┘         └────────┬─────────┘
           │                           │
           └──────────┬────────────────┘
                      ▼
              ┌───────────────┐
              │  RRF Fusion   │  Merge + re-rank both lists
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │   Self-RAG    │  LLM relevance judge (ISREL)
              │  Filter pass  │  Drop irrelevant candidates
              └───────┬───────┘
                      ▼
              Top-10 results returned
```

## Neo4j graph schema

```
(:Hotel {hotel_code, name, star_rating, description, address})
    -[:IN_CITY]->(:City {code, name, country})
    -[:HAS_AMENITY]->(:Amenity {name, category})
    -[:NEAR_ATTRACTION {distance_km}]->(:Attraction {name, category})
```

## Service

| Endpoint | Purpose |
|---|---|
| `GET /v1/search?query=...` | GraphRAG + Self-RAG hotel search |
| `POST /v1/admin/ingest` | Rebuild knowledge graph from hotel-inventory |
| `GET /healthz` | Health check |

Port: **8094**. Neo4j browser UI: **http://localhost:7474**

## Running locally

```bash
cp infra/docker/knowledge-graph.env.example infra/docker/knowledge-graph.env

docker compose -f infra/docker/docker-compose.yml up -d

# Wait for Neo4j to start (~30s), then trigger ingestion
curl -X POST http://localhost:8094/v1/admin/ingest

# Run a GraphRAG search
curl "http://localhost:8094/v1/search?query=luxury+hotel+with+spa+near+Eiffel+Tower" | jq .

# Browse the graph visually
open http://localhost:7474
# Login: neo4j / hotel-password
# Run: MATCH (h:Hotel)-[:NEAR_ATTRACTION]->(a) RETURN h, a LIMIT 50

# Run evals
cd phases/08_knowledge_graph/eval && pytest -v
```

## What's next (Phase 9)

Capstone — integrate all phases into a production-ready system with Terraform
IaC for EKS deployment, full CI/CD pipeline, and end-to-end testing.
