"""
GraphRAG: fuses graph traversal results with vector search results.

Pipeline:
  1. Extract entities from query (cities, amenities, attractions)
  2. Graph traversal: fetch hotels matching entities from Neo4j
  3. Vector search: semantic similarity from rag-pipeline
  4. RRF fusion: merge the two ranked lists
  5. Return top-N fused results
"""

from __future__ import annotations

import httpx
import structlog

from config import settings
from graph.queries import find_by_entities
from retrieval.entity_extractor import ExtractedEntities, extract_entities

log = structlog.get_logger()


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score for a result at position `rank` (0-indexed)."""
    return 1.0 / (k + rank + 1)


async def _vector_search(query: str, city_code: str, limit: int) -> list[dict]:
    """Call rag-pipeline for semantic search results."""
    body: dict = {"query": query, "limit": limit}
    if city_code:
        body["city_code"] = city_code
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.rag_pipeline_url}/v1/search/hotels", json=body
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
    except Exception as exc:
        log.warning("vector_search_failed", error=str(exc))
        return []


async def graphrag_search(
    query: str,
    limit: int | None = None,
) -> tuple[list[dict], ExtractedEntities]:
    """
    Run GraphRAG: graph + vector search fused via RRF.
    Returns (results, extracted_entities).
    """
    final_limit = limit or settings.final_limit

    entities = await extract_entities(query)
    log.info("entities_extracted", cities=entities.cities, amenities=entities.amenities)

    # Run graph and vector search concurrently
    import asyncio

    primary_city = entities.cities[0].upper() if entities.cities else ""

    graph_task = asyncio.create_task(
        find_by_entities(
            city_codes=[c.upper() for c in entities.cities if len(c) <= 3],
            city_names=[c for c in entities.cities if len(c) > 3],
            amenity_names=entities.amenities,
            attraction_names=entities.attractions,
            min_star_rating=entities.min_star_rating,
            limit=settings.graph_candidates,
        )
    )
    vector_task = asyncio.create_task(
        _vector_search(query, primary_city, settings.vector_candidates)
    )

    graph_results, vector_results = await asyncio.gather(graph_task, vector_task)

    # Build RRF score map keyed by hotel_code
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    for rank, hotel in enumerate(graph_results):
        code = hotel["hotel_code"]
        scores[code] = scores.get(code, 0.0) + _rrf_score(rank)
        meta[code] = {
            "hotel_code": code,
            "name": hotel.get("name", ""),
            "city_code": hotel.get("city_code", ""),
            "star_rating": hotel.get("star_rating", 0),
            "source": "graph",
        }

    for rank, hotel in enumerate(vector_results):
        code = hotel["hotel_code"]
        scores[code] = scores.get(code, 0.0) + _rrf_score(rank)
        if code not in meta:
            meta[code] = {
                "hotel_code": code,
                "name": hotel.get("name", ""),
                "city_code": hotel.get("city_code", ""),
                "star_rating": hotel.get("rating", 0),
                "source": "vector",
            }
        else:
            meta[code]["source"] = "both"

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = [
        {**meta[code], "rrf_score": round(score, 6)}
        for code, score in ranked[:final_limit * 2]  # over-fetch for Self-RAG to filter
        if code in meta
    ]

    return fused, entities
