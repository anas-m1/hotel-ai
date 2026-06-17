from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from graph.ingestion import run_ingestion

log = structlog.get_logger()
router = APIRouter()


class IngestResponse(BaseModel):
    hotels_ingested: int
    status: str


@router.post("/v1/admin/ingest", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Rebuild the Neo4j knowledge graph from hotel-inventory data."""
    count = await run_ingestion()
    return IngestResponse(hotels_ingested=count, status="ok")
