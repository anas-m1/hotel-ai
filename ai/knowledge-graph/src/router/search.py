from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from retrieval.graphrag import graphrag_search
from retrieval.self_rag import self_rag_filter

log = structlog.get_logger()
router = APIRouter()


class SearchResult(BaseModel):
    hotel_code: str
    name: str
    city_code: str
    star_rating: float
    rrf_score: float
    source: str   # "graph", "vector", or "both"


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    entities_extracted: dict
    total_candidates: int
    self_rag_filtered: bool


@router.get("/v1/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., description="Natural language hotel search query"),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    if not query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")

    candidates, entities = await graphrag_search(query, limit=limit)

    filtered = await self_rag_filter(query, candidates, final_limit=limit)

    return SearchResponse(
        query=query,
        results=[SearchResult(**h) for h in filtered],
        entities_extracted=entities.model_dump(),
        total_candidates=len(candidates),
        self_rag_filtered=settings.self_rag_enabled,
    )
