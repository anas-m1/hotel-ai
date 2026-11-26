from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request

from ..indexer.hotels import index_hotels

log = structlog.get_logger()
router = APIRouter()


@router.post("/index/hotels")
async def trigger_hotel_index(request: Request) -> dict[str, Any]:
    """
    Trigger a full re-index of all hotels from the hotel-inventory service.
    Fetches every hotel, embeds its description, and upserts into Qdrant.
    Safe to call repeatedly — uses stable IDs so existing points are updated,
    not duplicated.
    """
    log.info("index_triggered")
    try:
        count = await index_hotels(request.app.state.qdrant)
    except Exception as exc:
        log.error("index_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Indexing failed: {exc}") from exc

    log.info("index_complete", indexed=count)
    return {"indexed": count}
