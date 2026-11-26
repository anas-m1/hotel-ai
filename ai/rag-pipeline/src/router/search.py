from typing import Any

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..search import hybrid

log = structlog.get_logger()
router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    city_code: str | None = None
    rating: str | None = None
    limit: int | None = None


class SearchResult(BaseModel):
    hotel_code: str
    name: str
    city_code: str
    rating: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


@router.post("/search/hotels", response_model=SearchResponse)
async def search_hotels(req: SearchRequest, request: Request) -> Any:
    log.info("search_request", query=req.query, city_code=req.city_code, rating=req.rating)

    results = await hybrid.search(
        request.app.state.qdrant,
        req.query,
        city_code=req.city_code,
        rating=req.rating,
        limit=req.limit,
    )

    return SearchResponse(query=req.query, results=results)
